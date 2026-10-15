"""Independent AI source/metadata review; no producer imports, genomes, or lives."""
from pathlib import Path
import ast
import hashlib
import io
import json
import math
import xml.etree.ElementTree as ET
import zipfile
import numpy as np
ROOT = Path(__file__).resolve().parents[2]
AUDIT = Path(__file__).resolve().parent
STUDY = ROOT / 'outputs/autonomous_exploratory_reserve_replication_20261014'
AH = ROOT / 'results/exploratory_reserve_20261014'
AE = ROOT / 'results/prediction_gradient_20261014'
def sha(path): return hashlib.sha256(path.read_bytes()).hexdigest()
def read(path): return json.loads(path.read_text())
def definitions(path): return {n.name:n for n in ast.parse(path.read_text()).body if isinstance(n,ast.FunctionDef)}
def npy(archive,name): return np.load(io.BytesIO(archive.read(name+'.npy')),allow_pickle=False)
def main():
    author=read(AUDIT/'producer_source_review.json')
    assert author['status']=='source_only_reviewed_unregistered'
    pins=author['source_pins']
    assert len(pins)==14
    for name,digest in pins.items(): assert sha(STUDY/name)==digest,name
    for name in author['absent_before_registration']: assert not (STUDY/name).exists(),name
    origin=read(AUDIT/'producer_source_origins.json')
    assert sha(AUDIT/'producer_source_origins.json')==author['origin_receipt_sha256']
    for name,digest in origin['source_pins'].items():
        assert sha(AH/name)==sha(AUDIT/'source_history/AH'/name)==digest,name
    for name in author['byte_exact_AH_files']: assert pins[name]==origin['source_pins'][name]
    normalized={}
    for name in ('prepare.py','measure.py','run_budgeted.py'):
        tree=ast.parse((STUDY/name).read_text())
        for node in ast.walk(tree):
            if isinstance(node,ast.Constant) and isinstance(node.value,str):
                for old,new in author['allowed_string_replacements']: node.value=node.value.replace(new,old)
        assert ast.dump(tree,include_attributes=False)==ast.dump(ast.parse((AH/name).read_text()),include_attributes=False),name
        normalized[name]=True
    tests=ET.parse(AUDIT/'producer_tests_final.xml').getroot()
    suites=[tests] if tests.tag=='testsuite' else list(tests)
    assert sum(int(x.attrib['tests']) for x in suites)==5
    assert all(int(x.attrib.get('errors',0))==int(x.attrib.get('failures',0))==0 for x in suites)
    assert sha(AUDIT/'producer_tests_final.xml')==author['tests']['junit_sha256']
    assert sha(AUDIT/'producer_tests_final.log')==author['tests']['log_sha256']
    protocol = read(AE / 'protocol.json')
    assert sha(AE / 'protocol.json') == '0f5a591fbfb66fd29b5f9cd11d42b482eb8cb09e74613b17cc384ed2c3daa849'
    vp = ROOT / 'results/prediction_information_20261014/protocol.json'
    assert sha(vp) == protocol['V_protocol_sha256']
    assert read(vp)['world'] == protocol['world']
    packing = protocol['world_packing']
    assert packing['abi'] == 3 and len(packing['keys']) == len(packing['values']) == 66
    assert hashlib.sha256(np.array(packing['values'], dtype=np.float64).tobytes()).hexdigest() == packing['raw_sha256']
    assert protocol['world']['R_cap'] == 500 and protocol['world']['T'] == 1024
    summary = read(AE / 'analysis_result/summary.json')
    old_cost = read(AUDIT / 'historical_cost_review.json')
    assert sha(AUDIT / 'historical_cost_review.json') == author['historical_cost_review_sha256']
    assert sha(AE / 'analysis_result/summary.json') == old_cost['AE_summary_sha256']
    index_name = 'measurement/screen/L92/row_index.json'
    index = read(AE / index_name)
    assert sha(AE / index_name) == summary['input_pins'][index_name] == old_cost['source_pins'][str((AE / index_name).relative_to(ROOT))]
    rates = []
    for row_index in range(65):
        name = f'measurement/screen/L92/screen/row_{row_index:04d}.npz'
        path = AE / name
        entry = index[f'screen/row_{row_index:04d}.npz']
        assert sha(path) == entry['sha256'] == summary['input_pins'][name] == old_cost['source_pins'][str(path.relative_to(ROOT))]
        with zipfile.ZipFile(path) as archive:
            identity = json.loads(str(npy(archive, 'identity')))
            assert identity == {'protocol_sha256': sha(AE / 'protocol.json'), 'background': 'L92',
                'world': 'persistent', 'stage': 'screen', 'genome_index': row_index,
                'genome_sha256': protocol['panel_genotype_sha256']['L92'][row_index], 'seeds': protocol['seeds']['screen']}
            seeds = npy(archive, 'seeds')
            assert seeds.dtype == np.uint64 and seeds.tolist() == identity['seeds']
            assert int(npy(archive, 'genome_index')) == row_index
            cpu, wall = float(npy(archive, 'cpu_seconds')), float(npy(archive, 'wall_seconds'))
            assert cpu == entry['cpu_seconds'] and math.isfinite(cpu) and cpu > 0
            assert math.isfinite(wall) and wall >= 0
            with archive.open('ledger.npy') as stream:
                version = np.lib.format.read_magic(stream)
                assert version in ((1, 0), (2, 0))
                header_reader = (np.lib.format.read_array_header_1_0 if version == (1, 0)
                                 else np.lib.format.read_array_header_2_0)
                shape, fortran, dtype = header_reader(stream)
                assert shape == (32, 57) and dtype == np.float64 and not fortran
            rates.append(cpu / 32)
    assert rates == old_cost['rates_cpu_per_life']
    node = definitions(STUDY / 'prepare.py')['cost_projection']
    namespace = {'math': math}
    exec(compile(ast.Module(body=[node], type_ignores=[]), str(STUDY / 'prepare.py'), 'exec'), namespace)
    projection = namespace['cost_projection'](rates)
    assert projection == old_cost['projection'] and projection['feasible']
    assert projection['startup_search_projection'] == 180 + 1.5 * 8268 * max(rates)
    assert projection['confirmation_projection'] == 180 + 1.5 * 512 * 5 * max(rates)
    old_review=AH/'release_review/independent_source_design_review.json'
    assert sha(old_review)=='21b3de28540ba54a2304dabfdbdfe0c9454925691ab815f6aee58fe00beb9b6c'
    root_review=read(AUDIT/'root_helper_source_review.json')
    for name in ('register_study.py','release_study.py','clear_terminal.py'): ast.parse((AUDIT/name).read_text())
    paths=[Path(__file__),AUDIT/'producer_source_review.json',AUDIT/'producer_source_origins.json',AUDIT/'historical_cost_review.json',
           AUDIT/'producer_tests_final.xml',AUDIT/'producer_tests_final.log',AUDIT/'root_helper_source_review.json',
           *[AUDIT/n for n in ('register_study.py','release_study.py','clear_terminal.py')],old_review,
           AH/'prelaunch/manifest.json',AH/'manifest.json',AE/'protocol.json',AE/'analysis_result/summary.json',vp]
    result={'status':'approved_source_only_unregistered','producer_source_pins':pins,
      'source_pins':{str(p.relative_to(ROOT)):sha(p) for p in paths},'blockers':[],
      'prior_design_review_sha256':sha(old_review),'entire_module_AST_metadata_only':normalized,
      'byte_exact_AH_files':author['byte_exact_AH_files'],
      'review':{
       'world_and_prices':'Exact V/AE ABI3 world,66 packedfloat64 values and unchanged scorer. No in-life or price changes.',
       'policy_and_rng':'Byte-exact AH adapter/search preserve original AH lottery domain, two uniforms without replacement among224, existing native tie streams and three rank calls. Shared new native seed intentionally pairs botharms; later populations may diverge.',
       'identity_and_replay':'Exact AH checkpoint/driver/source identity, durable fullbase/rank metadata, one original identity per worker, same first-cohort metadata checks. Independent recorded-operation replay remains required after completion.',
       'lifecycle_and_cost':'Entire monitor AST unchanged after study-label replacements;5400total/3400search/2000reserve with3390/5390stop. Parent/group/subreaper/CPU cleanup retained. Same6goldens+9804research calls. Historical AE65-row max retained; faster AH realized cost is not substituted.',
       'interpretation':'Independent repetition openly motivated by AH. Botharms fresh from AE L92row31, not AHendpoints. Primary captures with F/cost decomposition; report signs independently. Confirmation seeds are not evolutionary replicates; no general reliability or protected-ancestor mechanism claim.',
       'authorization':'Root-only future registration/preparation/release remains separate. Source review creates no candidateinputs, new behavior, ABI, clock, channel, world response or paidcompute.'},
      'timing_review':{'row_count':65,'row_lives':32,'identity_and_index_checks':'all65passed','ledger_access':'NPY header only; no outcomes/genotypes read',
       'maximum_cpu_per_life':max(rates),'maximum_row':int(np.argmax(rates)),
       'startup_search_projection':projection['startup_search_projection'],'confirmation_projection':projection['confirmation_projection'],
       'thresholds':[3390,1990],'limitation':'Historical maxima plus margins do not bound unseen offspring costs; monitor caps decisive.'},
      'existing_author_checks_verified':5,'new_test_cases':0,'simulation_calls':0,'compiled_libraries':0,'genetic_draws':0,'genotype_copies':0,'production_edits':0,'prepared_inputs':0}
    target=AUDIT/'independent_source_design_review.json'
    target.write_text(json.dumps(result,indent=2)+'\n')
    print(json.dumps({'status':result['status'],'sha256':sha(target),'historical_rows':65,'search_projection':projection['startup_search_projection'],'confirmation_projection':projection['confirmation_projection']}))
if __name__=='__main__': main()
