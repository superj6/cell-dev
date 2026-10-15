"""AH independent prepared-byte/config review; no draws, builds or simulation."""
from pathlib import Path
import hashlib
import json

import numpy as np
from omegaconf import OmegaConf

ROOT = Path(__file__).resolve().parents[2]
AUDIT = Path(__file__).resolve().parent
STUDY = ROOT / 'outputs/autonomous_exploratory_reserve_20261014'
AE = ROOT / 'results/prediction_gradient_20261014'
PROTO = '0a9e505969ed11cd8f240f9404bbff2adf9a91d91d5387252fd9595874c61be4'


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def read(path):
    return json.loads(path.read_text())


def differences(a, b, path=''):
    if isinstance(a, dict) and isinstance(b, dict):
        assert set(a) == set(b)
        return sum((differences(a[key], b[key], path + '.' + key) for key in a), [])
    return [] if a == b else [path.lstrip('.')]


def main():
    assert sha(STUDY / 'protocol.json') == PROTO
    p, reg = read(STUDY / 'protocol.json'), read(STUDY / 'registration.json')
    for base, pins in ((STUDY, p['file_pins']), (ROOT, p['production_pins']), (ROOT, reg['review_pins'])):
        for name, digest in pins.items():
            assert sha(base / name) == digest, name
    assert len(p['file_pins']) == 102 and len(p['production_pins']) == 35
    assert sha(STUDY / 'registration.json') == '29b7c72950f5727c603e68f12ce06fe85386a184c570fa00233741334322f19f'
    clearance = read(STUDY / 'resource_clearance.json')
    assert sha(STUDY / 'resource_clearance.json') == reg['resource_clearance_sha256']
    assert clearance['all_processes_exited'] and clearance['status'] == 'cleared'
    assert (len(clearance['processes']), len(clearance['process_groups']), len(clearance['budget_pins'])) == (40, 28, 14)
    for name, digest in clearance['budget_pins'].items():
        assert sha(ROOT / name) == digest
    seed = read(STUDY / 'seed_audit.json')
    assert sha(STUDY / 'seed_audit.json') == reg['native_seed_audit_sha256'] == '27e0bff8abe641322398d9743012650148c741527ce172dc33d54698a7de6877'
    assert p['paired_native_seed'] == reg['paired_native_seed'] == seed['paired_native_seed'] == 53226
    assert p['confirmation']['seeds'] == reg['confirmation_seeds'] == seed['confirmation_seeds']
    assert seed['run_life_seeds']['control'] == seed['run_life_seeds']['reserve'] == seed['intentional_overlap']
    assert len(set(seed['intentional_overlap'] + seed['confirmation_seeds'])) == 576
    author = read(AUDIT / 'producer_source_review.json')
    assert all(sha(STUDY / name) == digest for name, digest in author['producer_source_pins'].items())
    old = read(AE / 'protocol.json')
    assert p['world'] == old['world'] == read(ROOT / 'results/prediction_information_20261014/protocol.json')['world']
    assert p['world_packing'] == old['world_packing']
    assert len(p['world_packing']['values']) == 66
    assert hashlib.sha256(np.array(p['world_packing']['values'], dtype=np.float64).tobytes()).hexdigest() == p['world_packing']['raw_sha256']
    assert p['production_pins'] == old['production_pins']
    copied = {}
    for path in sorted((STUDY / 'inputs/AE').rglob('*')):
        if not path.is_file():
            continue
        name = str(path.relative_to(STUDY / 'inputs/AE'))
        original = AE / ('operations/budget.json' if name == 'budget.json' else name)
        assert path.read_bytes() == original.read_bytes(), name
        copied[name] = sha(path)
    assert (STUDY / 'inputs/AE_summary.json').read_bytes() == (AE / 'analysis_result/summary.json').read_bytes()
    assert (STUDY / 'inputs/U_template.yaml').read_bytes() == (ROOT / 'results/decoy_evolution_20261014/runs/s53091/config.yaml').read_bytes()
    cost = read(STUDY / 'inputs/AE_cost_rows.json')
    historical = read(AUDIT / 'historical_cost_review.json')
    assert cost['rates'] == historical['rates_cpu_per_life'] and cost['projection'] == historical['projection'] == p['cost_projection']
    assert len(cost['rates']) == 65 and len(cost['source_pins']) == 66
    cfg = {mode: OmegaConf.to_container(OmegaConf.load(STUDY / p['configs'][mode]['path']), resolve=True)
           for mode in p['runs']}
    assert differences(cfg['control'], cfg['reserve']) == ['logging.output_dir', 'exploratory_reserve.mode']
    for mode, c in cfg.items():
        assert c['seed'] == 53226 and c['threads'] == 2
        assert c['world'] == {'d0': 1., 'd_min': .5, 'v_t': .3, 'tau_turn': 200.}
        assert c['life']['abi'] == 3 and c['life']['T'] == 1024 and c['life']['T_choices'] is None
        assert c['costs_life'] == {} and c['envelope'] == {'enabled': False}
        assert c['life']['extinct_charge'] and c['life']['fast_kernel']
        assert [c['evolve'][k] for k in ('mu', 'lam', 'generations', 'recheck_k', 'recheck_lives')] == [32, 224, 4, 64, 4]
        assert c['evolve']['recheck_key'] == 'all' and c['evolve']['random_ties'] and c['evolve']['heldout_every'] == 4
        assert [c['life'][k] for k in ('lives', 'valid_lives', 'final_lives', 'final_top', 'final_fork_lives')] == [3, 16, 2, 1, 0]
        assert not c['life']['heldout'] and not c['life']['size_curve'] and not c['clones']['conditions'] and c['clones']['every'] == 0
        ext = c['exploratory_reserve']
        assert ext['mode'] == mode and ext['policy'] == p['reserve_policy']
        assert ext['policy_sha256'] == hashlib.sha256(json.dumps(p['reserve_policy'], sort_keys=True, separators=(',', ':')).encode()).hexdigest()
        assert ext['source_pins'] == {name: sha(STUDY / name) for name in ('reserve_adapter.py', 'search.py')}
    init = read(STUDY / 'initialization.json')
    assert init['runs'] == {'control': 'L92', 'reserve': 'L92'} and set(init['backgrounds']) == {'L92'}
    item = init['backgrounds']['L92']
    array = np.load(STUDY / item['population_file'], allow_pickle=False)
    assert array.shape == (32, 875) and array.dtype == np.float32 and np.isfinite(array).all()
    assert sha(STUDY / item['population_file']) == item['file_sha256']
    assert hashlib.sha256(array.tobytes()).hexdigest() == item['population_raw_sha256']
    with np.load(STUDY / 'inputs/AE/confirmation_genotypes.npz', allow_pickle=False) as rows:
        assert rows['roles'].tolist()[3] == 'H_L92' and array[0].tobytes() == rows['genomes'][3].tobytes()
    assert hashlib.sha256(array[0].tobytes()).hexdigest() == p['founder_mapping']['L92']['raw_sha256']
    assert [x['id'] for x in item['copies']] == list(range(1, 32))
    assert all(x['parent'] == 0 and set(x['ops']) == {'mut'} and len(x['ops']['mut']) == 2 for x in item['copies'])
    assert read(STUDY / 'generation_claim.json')['populations_to_generate'] == 1
    assert [x.name for x in (STUDY / 'initialization').iterdir()] == ['L92.npy']
    forbidden = ('ready.json', 'attempt.json', 'budget.json', 'runs', 'confirmation', 'logs', 'build-cache')
    assert not any((STUDY / name).exists() for name in forbidden)
    assert not list(STUDY.rglob('*.so'))
    paths = [Path(__file__), AUDIT / 'independent_source_design_review.json', AUDIT / 'historical_cost_review.json',
             STUDY / 'protocol.json', STUDY / 'initialization.json', STUDY / 'registration.json',
             STUDY / 'resource_clearance.json', STUDY / 'seed_audit.json', STUDY / 'preparation_claim.json', STUDY / 'generation_claim.json']
    receipt = {'status': 'passed_actual_input_review', 'protocol_sha256': PROTO,
        'source_pins': {str(path.relative_to(ROOT)): sha(path) for path in paths},
        'local_protocol_pins': 102, 'production_pins': 35, 'exact_AE_copies': copied,
        'world_coordinates': 66, 'world_matches_V_and_AE': True, 'config_differences': differences(cfg['control'], cfg['reserve']),
        'initial_population': {'tables': 1, 'shape': [32, 875], 'dtype': 'float32', 'recorded_additions': 62,
            'raw_sha256': item['population_raw_sha256'], 'fixed_start_exact': True,
            'replay_scope': 'Recorded-operation byte replay is independently performed by the bound reader, then repeated from the public archive; this check inspected the retained table without new draws.'},
        'historical_timing_rows': 65, 'cost_projection': p['cost_projection'],
        'namespace': {'shared_native_seed': 53226, 'shared_native_ids': 64, 'fresh_confirmation_ids': 512, 'total_unique': 576},
        'resource_clearance_counts': {'identities': 40, 'groups': 28, 'budgets': 14},
        'blockers': [], 'simulation_calls': 0, 'compiled_libraries': 0, 'new_genetic_draws': 0,
        'copied_genotypes_by_reviewer': 0, 'released': False}
    target = AUDIT / 'independent_actual_input_review.json'
    target.write_text(json.dumps(receipt, indent=2) + '\n')
    print(json.dumps({'status': receipt['status'], 'sha256': sha(target), 'exact_AE_copies': len(copied),
                      'local_pins': 102, 'production_pins': 35, 'initial_rows': 32, 'recorded_additions': 62}))


if __name__ == '__main__':
    main()
