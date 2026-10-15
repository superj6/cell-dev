"""AH source-only draft. One shared initialization requires later root registration.

Default invocation creates no inputs, genotypes, libraries, or lives.
"""
from __future__ import annotations

import argparse
import hashlib
import io
import json
import math
import os
import sys
from dataclasses import asdict
from pathlib import Path

os.environ.setdefault('ATEN_CPU_CAPABILITY', 'avx2')
sys.dont_write_bytecode = True
STUDY = Path(__file__).resolve().parent
ROOT = STUDY.parents[1]
sys.path.insert(0, str(ROOT))
AE = ROOT / 'results/prediction_gradient_20261014'
TEMPLATE = ROOT / 'results/decoy_evolution_20261014/runs/s53091/config.yaml'
AE_PROTOCOL = '0f5a591fbfb66fd29b5f9cd11d42b482eb8cb09e74613b17cc384ed2c3daa849'
RUNS = ['control', 'reserve']
LABELS = ['AE_L92', 'AH_control', 'AH_reserve']


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def read(path):
    return json.loads(Path(path).read_text())


def historical_source(name):
    return AE / ('operations/budget.json' if name == 'budget.json' else name)


def verify_pins(pins, base):
    for name, digest in pins.items():
        path = (base / name).resolve()
        if not path.is_relative_to(base.resolve()) or sha(path) != digest:
            raise ValueError('changed pinned input: ' + name)


def freeze(path, data):
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open('xb') as stream:
        stream.write(data)
        stream.flush()
        os.fsync(stream.fileno())


def freeze_json(path, value):
    freeze(path, (json.dumps(value, indent=2, allow_nan=False) + '\n').encode())


def cost_projection(rates):
    if len(rates) != 65 or any(not isinstance(v, (int, float)) or not math.isfinite(v) or v <= 0 for v in rates):
        raise ValueError('all 65 positive same-world AE L92 timing rates required')
    maximum = max(rates)
    search = 180 + 1.5 * 8268 * maximum
    confirmation = 180 + 1.5 * 512 * 5 * maximum
    return {'rates_cpu_per_life': rates, 'max_cpu_per_life': maximum,
            'startup_search_projection': search, 'confirmation_projection': confirmation,
            'confirmation_allowance': 'one historical maximum for start, twice maximum for each unknown endpoint',
            'feasible': search <= 3390 and confirmation <= 1990,
            'limitation': 'Historical maxima and margins do not bound new reserve offspring; hard caps are decisive.'}


def measured_costs(base, protocol, summary):
    """Timing scalars only; all 65 exact AE L92 rows, no outcome selection."""
    import numpy as np
    index_name = 'measurement/screen/L92/row_index.json'
    index = read(base / index_name)
    if summary['input_pins'][index_name] != sha(base / index_name):
        raise ValueError('reviewed historical timing index changed')
    pins, rates = {index_name: sha(base / index_name)}, []
    for i in range(65):
        name = f'measurement/screen/L92/screen/row_{i:04d}.npz'
        path = base / name
        entry = index[f'screen/row_{i:04d}.npz']
        if sha(path) != entry['sha256'] or sha(path) != summary['input_pins'][name]:
            raise ValueError('reviewed historical timing row changed')
        expected = {'protocol_sha256': AE_PROTOCOL, 'background': 'L92', 'world': 'persistent',
                    'stage': 'screen', 'genome_index': i, 'genome_sha256': protocol['panel_genotype_sha256']['L92'][i],
                    'seeds': protocol['seeds']['screen']}
        with np.load(path, allow_pickle=False) as row:
            cpu, wall = float(row['cpu_seconds']), float(row['wall_seconds'])
            if (json.loads(str(row['identity'])) != expected or row['ledger'].shape != (32, 57)
                    or row['ledger'].dtype != np.float64 or row['seeds'].dtype != np.uint64
                    or row['seeds'].tolist() != expected['seeds'] or int(row['genome_index']) != i
                    or cpu != entry['cpu_seconds'] or not math.isfinite(cpu) or cpu <= 0
                    or not math.isfinite(wall) or wall < 0):
                raise ValueError('historical timing identity or scalar differs')
            rates.append(cpu / 32)
        pins[name] = sha(path)
    return rates, pins


def checked_registration():
    reg = read(STUDY / 'registration.json')
    if (reg.get('status') != 'registered' or reg.get('runs') != RUNS
            or reg.get('founder_policy') != 'fixed_AE_L92_row31'):
        raise ValueError('explicit matched reserve registration required')
    seed, seeds = reg['paired_native_seed'], reg['confirmation_seeds']
    if (type(seed) is not int or not 0 <= seed < 2**64 or len(seeds) != 512 or len(set(seeds)) != 512
            or any(type(x) is not int or not 0 <= x < 2**64 for x in seeds) or 11 in seeds):
        raise ValueError('one shared native seed and fresh confirmation seeds required')
    audit = read(STUDY / 'seed_audit.json')
    if (audit.get('status') != 'passed' or audit.get('paired_native_seed') != seed
            or audit.get('confirmation_seeds') != seeds
            or sha(STUDY / 'seed_audit.json') != reg['native_seed_audit_sha256']):
        raise ValueError('reviewed exact namespace required')
    if sha(AE / 'protocol.json') != AE_PROTOCOL:
        raise ValueError('exact AE protocol required')
    verify_pins(reg['AE_complete']['file_pins'], AE)
    required = {'protocol.json', 'selection.json', 'operations/budget.json', 'analysis_result/summary.json',
                'confirmation_roles.json', 'confirmation_genotypes.npz', 'startup_identity.json'}
    if not required.issubset(reg['AE_complete']['file_pins']):
        raise ValueError('complete AE fixed-start provenance required')
    summary, budget = read(AE / 'analysis_result/summary.json'), read(historical_source('budget.json'))
    if (summary.get('status') != 'complete' or summary.get('protocol_sha256') != AE_PROTOCOL
            or budget.get('status') != 'complete' or budget.get('running') or budget.get('queued') or budget.get('cleanup_error')):
        raise ValueError('complete reviewed AE inputs required')
    terminal = reg['AG_terminal']['file_pins']
    name = 'outputs/autonomous_visibility_dark_tail_gradient_20261014/budget.json'
    if name not in terminal:
        raise ValueError('AG clean terminal resource receipt required')
    verify_pins(terminal, ROOT)
    old = read(ROOT / name)
    if (old.get('status') not in ('complete', 'incomplete', 'monitor_failed', 'job_failed', 'cpu_budget_exhausted', 'interrupted')
            or old.get('running') or old.get('queued') or old.get('cleanup_error')):
        raise ValueError('AG must be cleanly terminal; scientific success is not required')
    return reg, summary, audit


def planned_search_seeds(seed):
    from src.life.evaluate import life_seed
    result = []
    for g in range(4):
        result.extend(life_seed(seed, 'gen', g, j) for j in range(7))
        if g in (0, 3):
            result.extend(life_seed(seed, 'valid', g, j) for j in range(16))
    for index in (0, 1):
        result.extend(life_seed(seed, 'final', index, j) for j in range(2))
    return result


def search_config(run, seed, start_file):
    from omegaconf import OmegaConf
    from reserve_adapter import selection_identity
    if run not in RUNS:
        raise ValueError('unknown arm')
    cfg = OmegaConf.load(TEMPLATE)
    cfg.seed, cfg.threads = seed, 2
    cfg.evolve.generations, cfg.evolve.seed_genome = 4, str(STUDY / start_file)
    cfg.evolve.dup_rate, cfg.evolve.del_rate, cfg.evolve.dup_split = 0., 0., False
    cfg.logging.output_dir = str(STUDY / 'runs' / run)
    cfg.logging.checkpoint_every, cfg.logging.lineage = 1, 'all'
    cfg.life.abi, cfg.life.world, cfg.life.control = 3, 'catch_speck_l4', 'exploratory_reserve_AE_L92'
    cfg.life.T, cfg.life.T_choices = 1024, None
    cfg.life.flags, cfg.life.freeze_frac, cfg.life.t_open = [], None, 0.
    cfg.world = {'d0': 1., 'd_min': .5, 'v_t': .3, 'tau_turn': 200.}
    cfg.costs_life, cfg.envelope = {}, {'enabled': False}
    cfg.exploratory_reserve = selection_identity(run)
    return cfg


def prepare():
    forbidden = ('protocol.json', 'inputs', 'configs', 'initialization', 'preparation_claim.json', 'generation_claim.json',
                 'ready.json', 'attempt.json', 'budget.json', 'runs', 'confirmation', 'logs', 'build-cache')
    if any((STUDY / name).exists() for name in forbidden):
        raise ValueError('first preparation refuses previous generated or runtime work')
    reg, summary, audit = checked_registration()
    import numpy as np
    import torch
    from numerical import check
    from omegaconf import OmegaConf
    from reserve_adapter import POLICY
    from world_contract import check_world

    from src.evolve import fill, setup
    from src.genome import Layout
    from src.life import spec

    ap = read(AE / 'protocol.json')
    verify_pins(ap['file_pins'], AE)
    check(ap['numerical_identity'])  # Metadata only, no original numerical_identity call.
    expected_identity = read(AE / 'startup_identity.json')['identity']
    production = {str(p.relative_to(ROOT)): sha(p) for p in sorted((ROOT / 'src').rglob('*.py'))}
    production['src/life/kernel.c'] = sha(ROOT / 'src/life/kernel.c')
    if production != expected_identity['sources']:
        raise ValueError('production source changed')
    for name in ('taskvar_confirm.py', 'taskvar_gradient.py', 'taskvar_gates.py'):
        production['scripts/' + name] = sha(ROOT / 'scripts' / name)
    if production != ap['production_pins']:
        raise ValueError('unchanged production/scoring closure required')
    world = spec.World(**ap['world'])
    check_world(asdict(world), ap['world'])
    packed = spec.V3.pack_world(world)
    packing = {'abi': 3, 'keys': list(spec.V3.WORLD_KEYS), 'values': packed.tolist(),
               'raw_sha256': hashlib.sha256(packed.tobytes()).hexdigest()}
    if packed.shape != (66,) or packing != ap['world_packing']:
        raise ValueError('exact V/AE ABI3 world packing differs')
    selected, roles = read(AE / 'selection.json'), read(AE / 'confirmation_roles.json')
    if (selected['L92']['genome_row'] != 31 or roles != summary['roles'] or roles['roles'] != ['P_D90', 'P_L92', 'H_D90', 'H_L92']
            or roles['panel_rows']['H_L92'] != 31 or roles['genotype_sha256']['H_L92'] != selected['L92']['raw_sha256']
            or roles['selection_sha256'] != sha(AE / 'selection.json')):
        raise ValueError('fixed AE L92 selection differs')
    rates, cost_pins = measured_costs(AE, ap, summary)
    projection = cost_projection(rates)
    if not projection['feasible']:
        raise ValueError('fixed candidate scope does not fit historical cost gate')
    planned = planned_search_seeds(reg['paired_native_seed'])
    lists = {run: planned for run in RUNS}
    if (audit['run_life_seeds'] != lists or audit['intentional_overlap'] != planned or len(set(planned)) != 64
            or set(planned) & set(reg['confirmation_seeds']) or 11 in planned):
        raise ValueError('exact shared native schedule differs from audited intentional overlap')
    if sha(AE / 'confirmation_genotypes.npz') != roles['genotypes_sha256']:
        raise ValueError('fixed AE role table changed')
    with np.load(AE / 'confirmation_genotypes.npz', allow_pickle=False) as table:
        if table['roles'].tolist() != roles['roles'] or table['genomes'].shape != (4, 875) or table['genomes'].dtype != np.float32:
            raise ValueError('AE role-table schema differs')
        genome = torch.from_numpy(table['genomes'][3].copy())
    prefix = Path('inputs/Y/inputs/L92')
    layout, founder = Layout.load(AE / prefix / 'parent.json')
    panel = np.load(AE / prefix / 'genomes.npy', allow_pickle=False)
    if (panel.dtype != np.float32 or panel.shape != (65, 875) or not np.isfinite(panel).all()
            or panel[0].tobytes() != founder.numpy().tobytes() or panel[31].tobytes() != genome.numpy().tobytes()
            or [hashlib.sha256(row.tobytes()).hexdigest() for row in panel] != ap['panel_genotype_sha256']['L92']):
        raise ValueError('AE start differs from exact original Y panel')
    u = ROOT / 'results/decoy_evolution_20261014'
    if sha(TEMPLATE) != read(u / 'provenance.json')['artifacts'][str(TEMPLATE.relative_to(u))]['sha256']:
        raise ValueError('retained native template differs')
    freeze_json(STUDY / 'preparation_claim.json', {'registration_sha256': sha(STUDY / 'registration.json'),
                                                'simulation_calls': 0, 'compiled_libraries': 0})
    freeze(STUDY / 'inputs/AE_summary.json', (AE / 'analysis_result/summary.json').read_bytes())
    for name in ('protocol.json', 'selection.json', 'budget.json', 'startup_identity.json', 'confirmation_roles.json', 'confirmation_genotypes.npz'):
        freeze(STUDY / 'inputs/AE' / name, historical_source(name).read_bytes())
    for name in ('parent.json', 'config.yaml', 'genomes.npy', 'panel_manifest.json', 'mutation_ops.json'):
        freeze(STUDY / 'inputs/AE' / prefix / name, (AE / prefix / name).read_bytes())
    for name in cost_pins:
        freeze(STUDY / 'inputs/AE' / name, (AE / name).read_bytes())
    freeze(STUDY / 'inputs/U_template.yaml', TEMPLATE.read_bytes())
    freeze_json(STUDY / 'inputs/AE_cost_rows.json', {'rates': rates, 'source_pins': cost_pins, 'projection': projection})
    start_file = 'inputs/AE_L92.json'
    freeze_json(STUDY / start_file, {'dims': layout.dims.__dict__, 'params': layout.to_dict(genome)})
    if Layout.load(STUDY / start_file)[1].numpy().tobytes() != genome.numpy().tobytes():
        raise ValueError('start JSON roundtrip differs')
    configs = {}
    cfg = search_config('control', reg['paired_native_seed'], start_file)
    _, _, _, ev = setup(cfg)
    check_world(asdict(ev.world()), ap['world'])
    if (ev.abi.version != 3 or not ev.fast or not ev.extinct_charge or ev.has_envelope
            or (cfg.evolve.mu, cfg.evolve.lam, cfg.life.lives, cfg.evolve.recheck_k, cfg.evolve.recheck_lives) != (32, 224, 3, 64, 4)
            or cfg.life.heldout or cfg.life.size_curve or cfg.clones.conditions or cfg.clones.every
            or (cfg.life.final_top, cfg.life.final_lives, cfg.life.final_fork_lives, cfg.life.valid_lives) != (1, 2, 0, 16)):
        raise ValueError('native fixed scope differs')
    freeze_json(STUDY / 'generation_claim.json', {'registration_sha256': sha(STUDY / 'registration.json'),
                                               'paired_native_seed': reg['paired_native_seed'], 'populations_to_generate': 1})
    generator = torch.Generator().manual_seed(reg['paired_native_seed'])
    before = hashlib.sha256(generator.get_state().numpy().tobytes()).hexdigest()
    operations = []
    population = fill(genome[None], 32, layout, generator, cfg.evolve, ops=operations).numpy()
    if (population.dtype != np.float32 or population.shape != (32, 875) or population[0].tobytes() != genome.numpy().tobytes()
            or len(operations) != 31 or any(set(o) != {'mut'} or len(o['mut']) != 2 for o in operations)):
        raise ValueError('ordinary shared initialization differs')
    data = io.BytesIO()
    np.save(data, population, allow_pickle=False)
    pop_path = STUDY / 'initialization/L92.npy'
    freeze(pop_path, data.getvalue())
    init = {'population_file': 'initialization/L92.npy', 'file_sha256': sha(pop_path),
            'population_raw_sha256': hashlib.sha256(population.tobytes()).hexdigest(), 'generator_before_sha256': before,
            'generator_after_sha256': hashlib.sha256(generator.get_state().numpy().tobytes()).hexdigest(),
            'copies': [{'id': i + 1, 'parent': 0, 'ops': item} for i, item in enumerate(operations)]}
    for run in RUNS:
        current = search_config(run, reg['paired_native_seed'], start_file)
        path = STUDY / f'configs/{run}.yaml'
        freeze(path, OmegaConf.to_yaml(current, resolve=True).encode())
        configs[run] = {'path': str(path.relative_to(STUDY)), 'sha256': sha(path)}
    freeze_json(STUDY / 'initialization.json', {'status': 'pure_genetic_preparation', 'simulation_calls': 0,
        'backgrounds': {'L92': init}, 'runs': {'control': 'L92', 'reserve': 'L92'}})
    pinned = [p for folder in ('inputs', 'configs', 'initialization') for p in (STUDY / folder).rglob('*') if p.is_file()]
    pinned += list(STUDY.glob('*.py')) + [STUDY / n for n in ('README.md', 'PREREG.md', 'SCHEMA.md', 'registration.json',
        'seed_audit.json', 'initialization.json', 'generation_claim.json', 'preparation_claim.json')]
    protocol = {'study': 'AH fresh-offspring exploratory reserve', 'abi': 3, 'runs': RUNS,
        'paired_native_seed': reg['paired_native_seed'], 'generations': 4, 'reserve_policy': POLICY,
        'configs': configs, 'reference_files': [start_file],
        'founder_mapping': {'L92': {'background': 'L92', 'AE_selection': selected['L92'],
                                  'start_file': start_file, 'raw_sha256': selected['L92']['raw_sha256']}},
        'world': ap['world'], 'world_packing': packing, 'AE_protocol_sha256': AE_PROTOCOL,
        'expected_numerical_identity': expected_identity, 'numerical_identity': ap['numerical_identity'],
        'production_pins': production, 'cost_projection': projection,
        'search_genome_lives': 8268, 'confirmation_genome_lives': 1536, 'planned_genome_lives': 9804,
        'startup_validation_genome_lives': 6, 'max_cpu_seconds': 5400, 'search_cpu_seconds': 3400, 'max_simulation_threads': 4,
        'confirmation': {'labels': LABELS, 'seeds': reg['confirmation_seeds'], 'threads': 2,
                         'primary_pairs': [[2, 1]], 'gain_pairs': [[1, 0], [2, 0]]},
        'file_pins': {str(p.relative_to(STUDY)): sha(p) for p in sorted(pinned)}}
    freeze_json(STUDY / 'protocol.json', protocol)
    print(json.dumps({'status': 'prepared_unreleased', 'simulation_calls': 0, 'compiled_libraries': 0,
                      'initial_populations': 1, 'native_jobs': 2, 'protocol_sha256': sha(STUDY / 'protocol.json')}))


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--prepare', action='store_true')
    args = parser.parse_args()
    if not args.prepare:
        print(json.dumps({'status': 'source_only_unregistered', 'research_lives': 9804,
                          'startup_validation_lives': 6, 'simulation_calls': 0, 'generated_populations': 0,
                          'requires': 'root registration and clean AG terminal resource clearance'}))
        return
    prepare()


if __name__ == '__main__':
    main()
