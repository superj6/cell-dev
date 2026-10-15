"""Review the one authorized AH preparation without importing an engine or drawing genetics."""
from __future__ import annotations

import datetime
import hashlib
import json
import sys
from pathlib import Path

import numpy as np
from omegaconf import OmegaConf

sys.dont_write_bytecode = True
AUDIT = Path(__file__).resolve().parent
ROOT = AUDIT.parents[1]
STUDY = ROOT / 'outputs/autonomous_exploratory_reserve_20261014'
AE = ROOT / 'results/prediction_gradient_20261014'


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def read(path):
    return json.loads(path.read_text())


def save(path, value):
    with path.open('x') as stream:
        stream.write(json.dumps(value, indent=2, allow_nan=False) + '\n')


def main():
    protocol = read(STUDY / 'protocol.json')
    assert sha(STUDY / 'protocol.json') == '0a9e505969ed11cd8f240f9404bbff2adf9a91d91d5387252fd9595874c61be4'
    reg, audit = read(STUDY / 'registration.json'), read(STUDY / 'seed_audit.json')
    assert sha(STUDY / 'registration.json') == '29b7c72950f5727c603e68f12ce06fe85386a184c570fa00233741334322f19f'
    for key, base in (('file_pins', STUDY), ('production_pins', ROOT)):
        for name, digest in protocol[key].items():
            assert sha(base / name) == digest, name
    source = read(AUDIT / 'producer_source_review.json')
    for name, digest in source['producer_source_pins'].items():
        assert sha(STUDY / name) == digest, name
    copies = {}
    for path in sorted((STUDY / 'inputs/AE').rglob('*')):
        if not path.is_file():
            continue
        relative = str(path.relative_to(STUDY / 'inputs/AE'))
        original = AE / ('operations/budget.json' if relative == 'budget.json' else relative)
        assert path.read_bytes() == original.read_bytes(), relative
        copies[str(path.relative_to(STUDY))] = {'source': str(original.relative_to(ROOT)), 'sha256': sha(path)}
    for name, original in (
        ('inputs/AE_summary.json', AE / 'analysis_result/summary.json'),
        ('inputs/U_template.yaml', ROOT / 'results/decoy_evolution_20261014/runs/s53091/config.yaml'),
    ):
        assert (STUDY / name).read_bytes() == original.read_bytes()
        copies[name] = {'source': str(original.relative_to(ROOT)), 'sha256': sha(original)}
    old = read(AE / 'protocol.json')
    assert protocol['world'] == old['world'] and protocol['world_packing'] == old['world_packing']
    packing = protocol['world_packing']
    values = np.asarray([protocol['world'][key] for key in packing['keys']], dtype=np.float64)
    assert len(values) == 66 and packing['abi'] == protocol['abi'] == 3
    assert values.tolist() == packing['values']
    assert hashlib.sha256(values.tobytes()).hexdigest() == packing['raw_sha256']
    assert protocol['production_pins'] == old['production_pins']
    assert protocol['expected_numerical_identity'] == read(STUDY / 'inputs/AE/startup_identity.json')['identity']
    assert protocol['numerical_identity'] == old['numerical_identity']
    template = OmegaConf.load(STUDY / 'inputs/U_template.yaml')
    template.seed, template.threads = reg['paired_native_seed'], 2
    template.evolve.generations = 4
    template.evolve.seed_genome = str(STUDY / 'inputs/AE_L92.json')
    template.evolve.dup_rate, template.evolve.del_rate, template.evolve.dup_split = 0., 0., False
    template.logging.checkpoint_every, template.logging.lineage = 1, 'all'
    template.life.abi, template.life.world, template.life.control = 3, 'catch_speck_l4', 'exploratory_reserve_AE_L92'
    template.life.T, template.life.T_choices = 1024, None
    template.life.flags, template.life.freeze_frac, template.life.t_open = [], None, 0.
    template.world = {'d0': 1., 'd_min': .5, 'v_t': .3, 'tau_turn': 200.}
    template.costs_life, template.envelope = {}, {'enabled': False}
    configurations = {}
    policy = protocol['reserve_policy']
    policy_sha = hashlib.sha256(json.dumps(policy, sort_keys=True, separators=(',', ':'), allow_nan=False).encode()).hexdigest()
    for run in protocol['runs']:
        path = STUDY / protocol['configs'][run]['path']
        assert sha(path) == protocol['configs'][run]['sha256']
        template.logging.output_dir = str(STUDY / 'runs' / run)
        template.exploratory_reserve = {'mode': run, 'policy': policy, 'policy_sha256': policy_sha,
            'source_pins': {name: sha(STUDY / name) for name in ('reserve_adapter.py', 'search.py')}}
        cfg = OmegaConf.to_container(OmegaConf.load(path), resolve=True)
        assert cfg == OmegaConf.to_container(template, resolve=True), run
        normalized = json.loads(json.dumps(cfg))
        normalized['logging'].pop('output_dir')
        normalized['exploratory_reserve']['mode'] = 'normalized'
        configurations[run] = normalized
    assert configurations['control'] == configurations['reserve']
    seed = reg['paired_native_seed']
    assert seed == protocol['paired_native_seed'] == audit['paired_native_seed'] == 53226
    native = audit['run_life_seeds']
    assert native['control'] == native['reserve'] == audit['intentional_overlap']
    assert len(native['control']) == len(set(native['control'])) == 64
    confirm = protocol['confirmation']['seeds']
    assert confirm == reg['confirmation_seeds'] == audit['confirmation_seeds']
    assert confirm == list(range(52350000, 52350512)) and len(set(native['control'] + confirm)) == 576
    assert 11 not in native['control'] + confirm
    assert sha(STUDY / 'seed_audit.json') == reg['native_seed_audit_sha256']
    init = read(STUDY / 'initialization.json')
    assert init['runs'] == {'control': 'L92', 'reserve': 'L92'} and init['simulation_calls'] == 0
    assert set(init['backgrounds']) == {'L92'}
    item = init['backgrounds']['L92']
    table = np.load(STUDY / item['population_file'], allow_pickle=False)
    assert table.shape == (32, 875) and table.dtype == np.float32 and np.isfinite(table).all()
    assert sha(STUDY / item['population_file']) == item['file_sha256']
    assert hashlib.sha256(table.tobytes()).hexdigest() == item['population_raw_sha256']
    assert [x['id'] for x in item['copies']] == list(range(1, 32))
    assert all(x['parent'] == 0 and set(x['ops']) == {'mut'} and len(x['ops']['mut']) == 2 for x in item['copies'])
    assert len(item['generator_before_sha256']) == len(item['generator_after_sha256']) == 64
    assert item['generator_before_sha256'] != item['generator_after_sha256']
    with np.load(STUDY / 'inputs/AE/confirmation_genotypes.npz', allow_pickle=False) as old_table:
        assert old_table['genomes'][3].tobytes() == table[0].tobytes()
    panel = np.load(STUDY / 'inputs/AE/inputs/Y/inputs/L92/genomes.npy', allow_pickle=False)
    assert panel[31].tobytes() == table[0].tobytes()
    fields = ('W', 'b', 'lam', 's0', 'Q', 'act', 'A', 'a0', 'Dm', 'km')
    founder = read(STUDY / 'inputs/AE_L92.json')['params']
    reconstructed = np.concatenate([np.asarray(founder[key], dtype=np.float32).reshape(-1) for key in fields])
    assert reconstructed.tobytes() == table[0].tobytes()
    assert hashlib.sha256(table[0].tobytes()).hexdigest() == protocol['founder_mapping']['L92']['raw_sha256']
    cost = read(STUDY / 'inputs/AE_cost_rows.json')
    historical = read(AUDIT / 'historical_cost_review.json')
    assert cost['rates'] == historical['rates_cpu_per_life'] and cost['projection'] == historical['projection']
    assert cost['projection'] == protocol['cost_projection'] and cost['projection']['feasible'] is True
    for name, digest in cost['source_pins'].items():
        assert sha(STUDY / 'inputs/AE' / name) == digest
    assert len(cost['source_pins']) == 66
    assert read(STUDY / 'generation_claim.json') == {'registration_sha256': sha(STUDY / 'registration.json'),
        'paired_native_seed': seed, 'populations_to_generate': 1}
    absent = ['ready.json', 'attempt.json', 'budget.json', 'runs', 'confirmation', 'logs', 'build-cache']
    assert all(not (STUDY / name).exists() for name in absent)
    assert not list(STUDY.rglob('*.so')) and not list(STUDY.rglob('*.pyc'))
    assert not any(name == 'src' or name.startswith('src.') for name in sys.modules)
    assert (AUDIT / 'preparation_stderr.txt').read_bytes() == b''
    assert read(AUDIT / 'preparation_stdout.json')['protocol_sha256'] == sha(STUDY / 'protocol.json')
    result = {'status': 'passed_prepared_unreleased', 'protocol_sha256': sha(STUDY / 'protocol.json'),
        'initialization_sha256': sha(STUDY / 'initialization.json'), 'initial_population_raw_sha256': item['population_raw_sha256'],
        'registration_sha256': sha(STUDY / 'registration.json'), 'local_pins_verified': len(protocol['file_pins']),
        'production_pins_verified': len(protocol['production_pins']), 'copied_inputs': copies,
        'historical_timing_rows_verified': 65, 'world_field_count': 66, 'world_abi': 3,
        'configs': 'Exact declared U-template overrides; only output path and selection mode differ.',
        'shared_initial_populations': 1, 'initial_rows': 32, 'recorded_point_operations': 62,
        'independent_recorded_operation_replay': 'Delegated to the independent reader before release; this author review verifies bytes, records and fixed founder.',
        'native_unique_life_ids': 64, 'native_shared_ids': 64, 'fresh_confirmation_ids': 512,
        'initialization_scope': 'Exactly one authorized preparation generated the shared table; this review makes no genetic draws.',
        'preparation_invocations': 1, 'preparation_exit_code': 0,
        'console_pins': {name: sha(AUDIT / name) for name in ('preparation_command.json', 'preparation_stdout.json', 'preparation_stderr.txt')},
        'source_review_sha256': sha(AUDIT / 'producer_source_review.json'), 'source_unchanged': True,
        'absent_runtime_paths': absent, 'review_engine_imports': [], 'review_genetic_draws': 0,
        'simulation_calls': 0, 'compiled_libraries': 0}
    save(AUDIT / 'actual_preparation_review.json', result)
    status = {'status': 'prepared_unreleased', 'protocol_sha256': result['protocol_sha256'],
        'preparation_invocations': 1, 'initial_populations': 1, 'native_jobs': 2,
        'simulation_calls': 0, 'compiled_libraries': 0, 'producer_sources_unchanged': True,
        'author_review_sha256': sha(AUDIT / 'actual_preparation_review.json'),
        'note': 'Pinned README and schema retain the earlier source-only description. This separate receipt records authorized preparation. Independent binding/replay and prospective publication precede root runtime release.'}
    save(STUDY / 'PREPARED_STATUS.json', status)
    save(AUDIT / 'preparation_execution_review.json', {'status': 'single_preparation_completed',
        'completed_at_utc': datetime.datetime.now(datetime.timezone.utc).isoformat(), 'exit_code': 0,
        'invocations': 1, 'stderr_bytes': 0, 'console_pins': result['console_pins'],
        'actual_review_sha256': sha(AUDIT / 'actual_preparation_review.json'),
        'prepared_status_sha256': sha(STUDY / 'PREPARED_STATUS.json')})
    print(json.dumps({key: result[key] for key in ('status', 'protocol_sha256', 'initialization_sha256',
        'local_pins_verified', 'production_pins_verified', 'initial_rows')}, indent=2))


if __name__ == '__main__':
    main()
