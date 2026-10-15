"""AF bound input verification and recorded initialization replay; no engine imports."""
from __future__ import annotations

import ast
import copy
import hashlib
import importlib.util
import json
import sys
from pathlib import Path

sys.dont_write_bytecode = True
HERE = Path(__file__).resolve().parent
ROOT = next(p for p in HERE.parents if (p / 'src/life/spec.py').is_file())
STUDY = ROOT / 'outputs/autonomous_prediction_continuation_20261014'

def module(name, path):
    spec = importlib.util.spec_from_file_location(name, path)
    obj = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(obj)
    return obj


def main():
    M = module('AF_bound_reader', HERE / 'analysis/analyze.py')
    p = M.verify_protocol(STUDY)
    old_ast = ast.parse((HERE / 'analysis_history/analyze_unbound.py').read_text())
    new_ast = ast.parse((HERE / 'analysis/analyze.py').read_text())
    for tree in (old_ast, new_ast):
        node = next(n for n in tree.body if isinstance(n, ast.Assign) and any(isinstance(t, ast.Name) and t.id == 'PROTOCOL_SHA' for t in n.targets))
        node.value = ast.Constant(None)
    assert ast.dump(old_ast, include_attributes=False) == ast.dump(new_ast, include_attributes=False)
    from omegaconf import OmegaConf
    template = OmegaConf.to_container(OmegaConf.load(STUDY / 'inputs/U_template.yaml'), resolve=True)
    configs = {}
    for seed in p['runs']:
        expected = copy.deepcopy(template)
        expected['seed'], expected['threads'] = seed, 2
        expected['evolve'].update(generations=4, seed_genome=str(STUDY / p['founder_mapping'][str(seed)]['start_file']), dup_rate=0., del_rate=0., dup_split=False)
        expected['logging'].update(output_dir=str(STUDY / f'runs/s{seed}'), checkpoint_every=1, lineage='all')
        expected['life'].update(abi=3, world='catch_speck_l4', control='ordinary_persistent_AE_selected', T=1024, T_choices=None, flags=[], freeze_frac=None, t_open=0.)
        expected['world'] = {'d0':1., 'd_min':.5, 'v_t':.3, 'tau_turn':200.}
        expected['costs_life'], expected['envelope'] = {}, {'enabled':False}
        path = STUDY / p['configs'][str(seed)]['path']
        actual = OmegaConf.to_container(OmegaConf.load(path), resolve=True)
        assert actual == expected
        configs[str(seed)] = {'sha256':M.sha(path),'exact_U_template_declared_overrides':True,'abi':actual['life']['abi'],'world':actual['world']}
    old = M.read(STUDY / 'inputs/AE/protocol.json')
    copied_panels = {}
    for background in M.BACKGROUNDS:
        for name in ('parent.json','config.yaml','genomes.npy','panel_manifest.json','mutation_ops.json'):
            key = f'inputs/Y/inputs/{background}/{name}'
            digest = M.sha(STUDY / 'inputs/AE' / key)
            assert digest == old['file_pins'][key]
            copied_panels[key] = digest
    N = module('AF_bound_native', HERE / 'analysis/native_audit.py')
    N.torch.set_num_threads(1)
    replay = N.initialization_audit(STUDY,p,M.external)
    (HERE/'initialization_replay.json').write_bytes(M.json_bytes(replay))
    forbidden = [x for x in sys.modules if x.startswith(('src.life.build','src.life.evaluate','src.life.reference','src.checkpoint','src.evolve','src.run'))]
    assert not forbidden
    absent = ('ready.json','attempt.json','budget.json','runs','confirmation','build-cache','logs')
    assert not any((STUDY/x).exists() for x in absent)
    summary,vectors = M.analyze(STUDY)
    assert summary['status']=='incomplete' and summary['scientific_outcomes_emitted'] is False and not vectors
    assert 'ready.json' in summary['error']
    assert sum(x['rows'] for x in replay['runs'].values()) == 64
    assert sum(x['recorded_mutations'] for x in replay['runs'].values()) == 124
    receipt = {'status':'passed_prepared_unreleased','protocol_sha256':M.PROTOCOL_SHA,'analyzer_sha256':M.sha(HERE/'analysis/analyze.py'),'native_audit_sha256':M.sha(HERE/'analysis/native_audit.py'),'unbound_analyzer_sha256':M.sha(HERE/'analysis_history/analyze_unbound.py'),'entire_AST_equal_except_protocol_literal':True,'file_pins_verified':len(p['file_pins']),'production_pins_verified':len(p['production_pins']),'configs':configs,'retained_AE_panel_file_pins':copied_panels,'world':p['world'],'world_packing':p['world_packing'],'cost_projection':p['cost_projection'],'fixed_start_sha256':M.REFERENCES,'run_life_id_counts':{k:len(v) for k,v in M.read(STUDY/'seed_audit.json')['run_life_seeds'].items()},'confirmation_seed_count':len(p['confirmation']['seeds']),'initialization_replay_sha256':M.sha(HERE/'initialization_replay.json'),'initial_rows_replayed':64,'recorded_point_operations':124,'forbidden_modules_loaded':forbidden,'runtime_artifacts_absent':list(absent),'prelaunch_analysis':summary,'vectors_emitted':0,'compilation_calls':0,'simulation_calls':0,'genetic_random_draws':0,'script_sha256':M.sha(Path(__file__))}
    (HERE/'actual_preparation_verification.json').write_bytes(M.json_bytes(receipt))
    print(json.dumps({'status':receipt['status'],'protocol_sha256':M.PROTOCOL_SHA,'file_pins':len(p['file_pins']),'production_pins':len(p['production_pins']),'initial_rows':64,'recorded_point_operations':124,'receipt_sha256':M.sha(HERE/'actual_preparation_verification.json'),'replay_sha256':M.sha(HERE/'initialization_replay.json')},indent=2))

if __name__ == '__main__':
    main()
