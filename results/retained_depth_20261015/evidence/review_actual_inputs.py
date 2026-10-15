"""Independent AO metadata verification, no engine or genetic draws."""
import hashlib
import importlib.util
import json
import sys
from pathlib import Path

import yaml

ROOT = Path(__file__).resolve().parents[2]
STUDY = ROOT / 'outputs/autonomous_retained_depth_20261015'
OUT = Path(__file__).resolve().parent

def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()

def read(path):
    return json.loads(path.read_text())

spec = importlib.util.spec_from_file_location('AO_independent_actual_reader', STUDY / 'analyze.py')
reader = importlib.util.module_from_spec(spec)
spec.loader.exec_module(reader)
p = reader.verify_protocol(STUDY)
assert p['native_seed'] == 53232 and p['seeds'] == list(range(52420000,52420512))
assert p['roles'] == ['AM_reference','AN_start','unchanged8','unchanged24','balanced8','balanced24']
assert p['research_lives'] == 138476 and p['startup_lives'] == 12 and p['total_calls'] == 138488
assert p['search'] == {'arms':['unchanged','balanced'],'generations':24,'research_lives_per_arm':61558,
    'startup_lives_per_arm':4,'initial_lives':8,'recheck_lives':8,'parents':32,'offspring':224}
assert list(p['worlds']) == ['pool','persistent','blink80_5','blink80_20','turn100_blink80_20']
prior = read(STUDY / 'inputs/AN_protocol.json')
assert p['worlds'] == prior['worlds']
assert p['selection_worlds'] == {name:p['worlds'][name]['world'] for name in ('pool','persistent','blink80_20')}
assert all(w['world']['R_cap'] == 500 for w in p['worlds'].values())
assert p['primary'] == [{'world':w,'new':'balanced24','old':'unchanged24','metric':'captures'} for w in ('pool','blink80_20')]
assert p['ancestral_reference']['role'] == 'AM_reference' and p['reference']['role'] == 'AN_start'
assert p['population_start'] == read(STUDY/'inputs/population_import.json')
copies = {}
for source,digest in p['original_input_pins'].items():
    assert sha(ROOT/source) == digest
    matches = [name for name,value in p['input_pins'].items() if value == digest]
    assert matches and all(sha(STUDY/name) == digest for name in matches)
    copies[source] = matches
for source,digest in p['review_pins'].items():
    assert sha(ROOT/source) == digest
patterns = {'unchanged':['pool','persistent','blink80_20','blink80_20']*2,
            'balanced':['pool','persistent','pool','blink80_20']*2}
for arm in ('unchanged','balanced'):
    cfg = yaml.safe_load((STUDY / p['configs'][arm]['path']).read_text())
    prior_cfg = yaml.safe_load((STUDY / 'inputs/AN_config.yaml').read_text())
    assert cfg['world'] == prior_cfg['world'] and cfg['costs_life'] == {}
    assert cfg['envelope'] == {'enabled':False}
    assert cfg['seed'] == 53232 and cfg['threads'] == 2
    assert cfg['population_start'] == {'version':1, **p['population_start'], 'source_pins':{
        name:sha(STUDY/name) for name in ('population_loader.py','search.py')}}
    assert cfg['retention_selection'] == {'version':1,'arm':arm,'worlds':p['selection_worlds'],
        'rule':'gen fixed per-arm allocation per8 repeated for recheck; unchanged2/2/4 balanced4/2/2; diagnostics=persistent neutral; R_cap500',
        'pattern':patterns[arm],
        'source_pins':{'selection.py':sha(STUDY/'selection.py')}}
    for key,value in {'generations':24,'mu':32,'lam':224,'recheck_k':64,'recheck_lives':8,'recheck_key':'all',
                      'dup_rate':0.,'del_rate':0.,'dup_split':False,'n_mut':2,'p_cell':.5,'n_mut_scale':True,
                      'heldout_every':4}.items():
        assert cfg['evolve'][key] == value
    assert cfg['evolve']['seed_genome'] == str(STUDY/'inputs/input_population.json')
    for key,value in {'abi':4,'lives':8,'T':1024,'valid_lives':16,'final_lives':2,'final_top':1,
                      'final_fork_lives':0,'heldout':[],'size_curve':[],'T_choices':None,'t_open':0.,
                      'flags':[],'extinct_charge':True}.items():
        assert cfg['life'][key] == value
    assert cfg['logging']['checkpoint_every'] == 1 and cfg['logging']['lineage'] == 'all'
    assert cfg['logging']['output_dir'] == str(STUDY/'runs'/arm)
absent = ['release.json','attempt.json','budget.json','runs','raw','build-cache','startup.json','endpoints.json']
assert not any((STUDY/name).exists() for name in absent)
assert not any(n == 'torch' or n == 'src' or n.startswith('src.') for n in sys.modules)
result = {'status':'passed','protocol_sha256':sha(STUDY/'protocol.json'),
    'analyzer_sha256':sha(STUDY/'analyze.py'),'prepare_sha256':sha(STUDY/'prepare.py'),
    'script_sha256':sha(Path(__file__)),'pin_counts':{k:len(p[k]) for k in
    ('source_pins','input_pins','production_pins','original_input_pins','review_pins')},
    'exact_original_copy_mapping':copies,'imported_rows':32,'shape':[32,875],
    'population_raw_sha256':p['population_start']['population_raw_sha256'],
    'reference_raw_sha256':p['reference']['raw_sha256'],'all_worlds_exact_AN':True,
    'new_world_changes':[],
    'all_capture_prices':500,'native_diagnostic_base_physics_exact_AN':True,
    'runtime_paths_absent':absent,'engine_imports':False,'simulations':0,'builds':0,'genetic_draws':0}
(OUT/'actual_input_review.json').open('x').write(json.dumps(result,indent=2)+'\n')
print(json.dumps({'status':'passed','protocol_sha256':result['protocol_sha256'],
                  'receipt_sha256':sha(OUT/'actual_input_review.json'),**result['pin_counts']}))
