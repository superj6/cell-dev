"""AM metadata-only verification; no engine, Torch, build, life or genetic imports."""
import copy
import hashlib
import importlib.util
import json
import sys
from pathlib import Path

import yaml

ROOT = Path(__file__).resolve().parents[2]
STUDY = ROOT / 'outputs/autonomous_capture_value_selection_20261015'
OUT = Path(__file__).resolve().parent
EXPECTED = '9210e218d92d912f8b63822980de7fab868ad8904417d0f438a55e2b42922294'


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def read(path):
    return json.loads(path.read_text())


assert sha(STUDY/'protocol.json') == EXPECTED
spec = importlib.util.spec_from_file_location('AM_independent_actual_reader', STUDY/'analyze.py')
reader = importlib.util.module_from_spec(spec)
spec.loader.exec_module(reader)
p = reader.verify_protocol(STUDY)
assert p['worlds'] == read(STUDY/'inputs/AL_protocol.json')['worlds']
assert p['population_start'] == read(STUDY/'inputs/population_import.json')
assert all(w['world']['R_cap'] == 500 for w in p['worlds'].values())
copies = {}
for source, digest in p['original_input_pins'].items():
    assert sha(ROOT/source) == digest
    matches = [name for name, value in p['input_pins'].items() if value == digest]
    assert matches and all(sha(STUDY/name) == digest for name in matches)
    copies[source] = matches
for source, digest in p['review_pins'].items():
    assert sha(ROOT/source) == digest
configs = {arm:yaml.safe_load((STUDY/record['path']).read_text()) for arm,record in p['configs'].items()}
prior = yaml.safe_load((STUDY/'inputs/AL_config.yaml').read_text())
normalized = []
for arm, cfg in configs.items():
    assert cfg['seed'] == p['native_seed'] and cfg['threads'] == 2
    assert cfg['world'] == prior['world'] and cfg['costs_life'] == {}
    assert cfg['envelope'] == {'enabled':False}
    assert cfg['evolve']['seed_genome'] == str(STUDY/'inputs/input_population.json')
    assert cfg['population_start'] == {'version':1, **p['population_start'], 'source_pins':{
        name:sha(STUDY/name) for name in ('population_loader.py','search.py')}}
    assert cfg['retention_selection'] == {'version':1, 'arm':arm,'worlds':p['selection_worlds'],
        'rule':'gen indices even=pool odd=persistent; gen R_cap by arm; diagnostics=persistent R_cap500',
        'selection_capture_value':500. if arm == 'current_value' else 2000.,
        'source_pins':{'selection.py':sha(STUDY/'selection.py')}}
    for key, expected in {'generations':4,'mu':32,'lam':224,'recheck_k':64,'recheck_lives':8,
                           'recheck_key':'all','dup_rate':0.,'del_rate':0.,'dup_split':False,
                           'n_mut':2,'p_cell':.5,'n_mut_scale':True,'heldout_every':4}.items():
        assert cfg['evolve'][key] == expected
    for key, expected in {'abi':3,'lives':8,'T':1024,'valid_lives':16,'final_lives':2,
                           'final_top':1,'final_fork_lives':0,'heldout':[],'size_curve':[],
                           'T_choices':None,'t_open':0.,'flags':[],'extinct_charge':True}.items():
        assert cfg['life'][key] == expected
    assert cfg['logging']['checkpoint_every'] == 1 and cfg['logging']['lineage'] == 'all'
    x=copy.deepcopy(cfg)
    x['logging']['output_dir']='ARM_PATH'
    x['retention_selection']['arm']='ARM_LABEL'
    x['retention_selection']['selection_capture_value']='ARM_PRICE'
    normalized.append(x)
assert normalized[0] == normalized[1]
absent = ['release.json','attempt.json','budget.json','runs','raw','build-cache','startup.json','endpoints.json']
assert not any((STUDY/name).exists() for name in absent)
assert not any(n == 'torch' or n == 'src' or n.startswith('src.') for n in sys.modules)
result = {'status':'passed','protocol_sha256':EXPECTED,'analyzer_sha256':sha(STUDY/'analyze.py'),
    'prepare_sha256':sha(STUDY/'prepare.py'),'script_sha256':sha(Path(__file__)),
    'pin_counts':{k:len(p[k]) for k in ('source_pins','input_pins','production_pins','original_input_pins','review_pins')},
    'exact_original_copy_mapping':copies,'imported_rows':32,'shape':[32,875],
    'population_raw_sha256':p['population_start']['population_raw_sha256'],
    'row_zero_AL_reference_raw_sha256':p['reference']['raw_sha256'],
    'AI_ancestral_reference_raw_sha256':p['ancestral_reference']['raw_sha256'],
    'four_confirmation_worlds_exact_AL':True,'confirmation_capture_value':500,
    'config_pair_differences':['logging.output_dir','retention_selection.arm','retention_selection.selection_capture_value'],
    'selection_capture_values':{'current_value':500,'high_value':2000},
    'native_diagnostic_base_physics_exact_AL':True,
    'runtime_paths_absent':absent,'engine_imports':False,'simulations':0,'builds':0,'genetic_draws':0,
    'limitations':['Initial full population bytes are verified; no future genetic or simulation outcome exists yet.']}
(OUT/'actual_input_review.json').write_text(json.dumps(result,indent=2)+'\n')
print(json.dumps({'status':'passed','receipt_sha256':sha(OUT/'actual_input_review.json'),**result['pin_counts']}))
