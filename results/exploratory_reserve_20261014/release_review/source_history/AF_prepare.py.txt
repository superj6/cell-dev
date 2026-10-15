"""AF source-only preparation; native initialization requires later root registration.

The default command performs no input copying, genetic draws, builds or lives.
Exactly one --prepare is permitted after complete AE publication and authorization.
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
PARENTS = ('D90', 'L92')
LABELS = ['AE_D90', 'AE_L92', 'AF_D90', 'AF_L92']
AE_PROTOCOL = '0f5a591fbfb66fd29b5f9cd11d42b482eb8cb09e74613b17cc384ed2c3daa849'
AE_SOURCE_MAP = {'budget.json': 'operations/budget.json'}


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def read(path):
    return json.loads(Path(path).read_text())


def historical_source(name):
    return AE / AE_SOURCE_MAP.get(name, name)


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
    if set(rates) != set(PARENTS):
        raise ValueError('both developed backgrounds required')
    for item in rates.values():
        if (set(item) != {'H_screen', 'H_confirm', 'P_confirm'}
                or any(not math.isfinite(v) or v <= 0 for v in item.values())):
            raise ValueError('positive measured developed-body costs required')
    maxima = {p: max(rates[p].values()) for p in PARENTS}
    search = 180 + 1.5 * 4134 * sum(maxima.values())
    confirmation = 180 + 1.5 * 512 * sum(3 * maxima[p] for p in PARENTS)
    return {'rates_cpu_per_life': rates, 'lineage_max_cpu_per_life': maxima,
            'startup_search_projection': search, 'confirmation_projection': confirmation,
            'feasible': search <= 3390 and confirmation <= 1990,
            'limitation': 'Observed AE timing maxima and fixed margins do not bound new mutants/endpoints; hard caps remain decisive.'}


def measured_costs(base, protocol, summary, selected, roles):
    """Read six exact AE timing rows; no outcome/fitness calculation or genotype loading."""
    import numpy as np
    if (roles != summary['roles'] or roles['roles'] != ['P_D90', 'P_L92', 'H_D90', 'H_L92']
            or roles['protocol_sha256'] != AE_PROTOCOL
            or roles['selection_sha256'] != sha(base / 'selection.json')):
        raise ValueError('complete AE fixed role mapping differs')
    rates, pins = {}, {}
    for j, parent in enumerate(PARENTS):
        winner = selected[parent]
        if (roles['panel_rows']['H_' + parent] != winner['genome_row']
                or roles['genotype_sha256']['H_' + parent] != winner['raw_sha256']):
            raise ValueError('fixed AE start differs from complete role mapping')
        rates[parent] = {}
        requests = [('H_screen', f'measurement/screen/{parent}', 'screen', winner['genome_row'], 32, 'H_' + parent),
                    ('H_confirm', 'measurement/confirm/persistent', 'confirm', j + 2, 512, 'H_' + parent),
                    ('P_confirm', 'measurement/confirm/persistent', 'confirm', j, 512, 'P_' + parent)]
        for role, folder, stage, index, n, old_role in requests:
            relative = f'{folder}/{stage}/row_{index:04d}.npz'
            path = base / relative
            index_name = folder + '/row_index.json'
            saved_index = read(base / index_name)
            entry = saved_index[f'{stage}/row_{index:04d}.npz']
            if (summary['input_pins'][relative] != sha(path) or entry['sha256'] != sha(path)
                    or summary['input_pins'][index_name] != sha(base / index_name)):
                raise ValueError('complete AE timing row or index differs')
            seeds = protocol['seeds'][stage]
            expected = {'protocol_sha256': AE_PROTOCOL, 'world': 'persistent', 'stage': stage,
                        'genome_index': index, 'genome_sha256': roles['genotype_sha256'][old_role], 'seeds': seeds}
            if stage == 'screen':
                expected['background'] = parent
            else:
                expected.update(roles=roles['roles'], confirmation_roles_sha256=sha(base / 'confirmation_roles.json'))
            with np.load(path, allow_pickle=False) as row:
                cpu, wall = float(row['cpu_seconds']), float(row['wall_seconds'])
                if (json.loads(str(row['identity'])) != expected or row['ledger'].shape != (n, 57)
                        or row['ledger'].dtype != np.float64 or row['seeds'].dtype != np.uint64
                        or row['seeds'].tolist() != seeds or int(row['genome_index']) != index
                        or len(seeds) != n or cpu != entry['cpu_seconds'] or not math.isfinite(cpu) or cpu <= 0
                        or not math.isfinite(wall) or wall < 0):
                    raise ValueError('exact AE timing scalar/header identity required')
            rates[parent][role] = cpu / n
            pins[relative], pins[index_name] = sha(path), sha(base / index_name)
    return rates, pins


def checked_registration():
    reg = read(STUDY / 'registration.json')
    if (reg.get('status') != 'registered'
            or reg.get('founder_policy') != 'both_AE_selected_regardless_of_confirmation_sign'):
        raise ValueError('explicit fixed-start root registration required')
    runs, seeds = reg['runs'], reg['confirmation_seeds']
    if (len(runs) != 2 or len(set(runs)) != 2 or len(seeds) != 512 or len(set(seeds)) != 512
            or any(type(x) is not int or x < 0 for x in runs + seeds) or 11 in seeds):
        raise ValueError('exact two search seeds and 512 fresh confirmation seeds required')
    if sha(AE / 'protocol.json') != AE_PROTOCOL:
        raise ValueError('frozen AE protocol differs')
    dependency = reg['AE_complete']
    verify_pins(dependency['file_pins'], AE)
    required = ('protocol.json', 'selection.json', 'operations/budget.json', 'analysis_result/summary.json',
                'confirmation_roles.json', 'confirmation_genotypes.npz', 'startup_identity.json')
    if not set(required).issubset(dependency['file_pins']):
        raise ValueError('complete AE dependency pins required')
    summary, budget = read(AE / 'analysis_result/summary.json'), read(historical_source('budget.json'))
    if (summary.get('status') != 'complete' or summary.get('protocol_sha256') != AE_PROTOCOL
            or budget.get('status') != 'complete' or budget.get('running') or budget.get('queued')
            or budget.get('cleanup_error') or budget.get('exit_code') != 0):
        raise ValueError('AE must be completely analyzed and cleanly terminal')
    audit = read(STUDY / 'seed_audit.json')
    if (audit.get('status') != 'passed' or audit.get('runs') != runs
            or audit.get('confirmation_seeds') != seeds
            or sha(STUDY / 'seed_audit.json') != reg['native_seed_audit_sha256']
            or reg['run_backgrounds'] != dict(zip(map(str, runs), PARENTS))):
        raise ValueError('independent exact namespace audit required')
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


def search_config(seed, start_file):
    """Declarative only; exact V fields are independently checked before any genetics."""
    from omegaconf import OmegaConf
    cfg = OmegaConf.load(TEMPLATE)
    cfg.seed, cfg.threads = seed, 2
    cfg.evolve.generations, cfg.evolve.seed_genome = 4, str(STUDY / start_file)
    cfg.evolve.dup_rate, cfg.evolve.del_rate, cfg.evolve.dup_split = 0., 0., False
    cfg.logging.output_dir = str(STUDY / f'runs/s{seed}')
    cfg.logging.checkpoint_every, cfg.logging.lineage = 1, 'all'
    cfg.life.abi, cfg.life.world, cfg.life.control = 3, 'catch_speck_l4', 'ordinary_persistent_AE_selected'
    cfg.life.T, cfg.life.T_choices = 1024, None
    cfg.life.flags, cfg.life.freeze_frac, cfg.life.t_open = [], None, 0.
    cfg.world = {'d0': 1., 'd_min': .5, 'v_t': .3, 'tau_turn': 200.}
    cfg.costs_life, cfg.envelope = {}, {'enabled': False}
    return cfg


def prepare():
    forbidden = ('protocol.json', 'inputs', 'configs', 'initialization', 'preparation_claim.json',
                 'generation_claim.json', 'ready.json', 'attempt.json', 'budget.json', 'runs',
                 'confirmation', 'logs', 'build-cache')
    if any((STUDY / name).exists() for name in forbidden):
        raise ValueError('first preparation refuses prior generated/runtime work')
    reg, summary, seed_audit = checked_registration()
    import numpy as np
    import torch
    from numerical import check
    from omegaconf import OmegaConf
    from world_contract import check_world

    from src.evolve import fill, setup
    from src.genome import Layout
    from src.life import spec

    ap = read(AE / 'protocol.json')
    verify_pins(ap['file_pins'], AE)
    check(ap['numerical_identity'])  # Metadata only: never checkpoint.numerical_identity here.
    expected_identity = read(AE / 'startup_identity.json')['identity']
    production = {str(p.relative_to(ROOT)): sha(p) for p in sorted((ROOT / 'src').rglob('*.py'))}
    production['src/life/kernel.c'] = sha(ROOT / 'src/life/kernel.c')
    if production != expected_identity['sources']:
        raise ValueError('source/runtime changes invalidate direct AE timing reuse')
    for name in ('taskvar_confirm.py', 'taskvar_gradient.py', 'taskvar_gates.py'):
        production['scripts/' + name] = sha(ROOT / 'scripts' / name)
    if production != ap['production_pins']:
        raise ValueError('AE production/scoring source closure changed')
    world = spec.World(**ap['world'])
    check_world(asdict(world), ap['world'])
    packed = spec.V3.pack_world(world)
    packing = {'abi': 3, 'keys': list(spec.V3.WORLD_KEYS), 'values': packed.tolist(),
               'raw_sha256': hashlib.sha256(packed.tobytes()).hexdigest()}
    if packed.shape != (66,) or packed.dtype != np.float64 or packing != ap['world_packing']:
        raise ValueError('exact complete AE/V ABI3 packing differs')
    selected, roles = read(AE / 'selection.json'), read(AE / 'confirmation_roles.json')
    rates, cost_pins = measured_costs(AE, ap, summary, selected, roles)
    projection = cost_projection(rates)
    if not projection['feasible']:
        raise ValueError('unchanged scope does not fit developed-body cost projection')
    lists = {str(seed): planned_search_seeds(seed) for seed in reg['runs']}
    if seed_audit['run_life_seeds'] != lists:
        raise ValueError('native hash namespaces disagree with independent audit')
    flat = [x for values in lists.values() for x in values] + reg['confirmation_seeds']
    if len(set(flat)) != len(flat) or 11 in flat:
        raise ValueError('search, diagnostic or confirmation seed overlap')
    table_path = AE / 'confirmation_genotypes.npz'
    if sha(table_path) != roles['genotypes_sha256']:
        raise ValueError('complete AE role table differs')
    with np.load(table_path, allow_pickle=False) as archive:
        table = archive['genomes'].copy()
        if archive['roles'].tolist() != roles['roles']:
            raise ValueError('complete AE role order differs')
    if table.shape != (4, 875) or table.dtype != np.float32 or not np.isfinite(table).all():
        raise ValueError('complete AE four-role genotype table differs')
    if any(hashlib.sha256(row.tobytes()).hexdigest() != roles['genotype_sha256'][label]
           for label, row in zip(roles['roles'], table)):
        raise ValueError('complete AE role genotype identities differ')
    u_archive = ROOT / 'results/decoy_evolution_20261014'
    if sha(TEMPLATE) != read(u_archive / 'provenance.json')['artifacts'][str(TEMPLATE.relative_to(u_archive))]['sha256']:
        raise ValueError('reviewed U search template changed')
    # From this exclusive claim onward, any partial failure is preserved and cannot be retried.
    freeze_json(STUDY / 'preparation_claim.json', {'registration_sha256': sha(STUDY / 'registration.json'),
                                                'simulation_calls': 0, 'compiled_libraries': 0})
    freeze_json(STUDY / 'inputs/AE_summary.json', summary)
    for name in ('protocol.json', 'selection.json', 'budget.json', 'startup_identity.json',
                 'confirmation_roles.json', 'confirmation_genotypes.npz'):
        freeze(STUDY / 'inputs/AE' / name, historical_source(name).read_bytes())
    freeze(STUDY / 'inputs/U_template.yaml', TEMPLATE.read_bytes())
    freeze_json(STUDY / 'inputs/AE_cost_rows.json', {'rates': rates, 'source_pins': cost_pins, 'projection': projection})
    for relative in cost_pins:
        freeze(STUDY / 'inputs/AE' / relative, (AE / relative).read_bytes())
    refs, starts, mapping = [], {}, {}
    for j, (parent, seed) in enumerate(zip(PARENTS, reg['runs'])):
        prefix = Path('inputs/Y/inputs') / parent
        for name in ('parent.json', 'config.yaml', 'genomes.npy', 'panel_manifest.json', 'mutation_ops.json'):
            freeze(STUDY / 'inputs/AE' / prefix / name, (AE / prefix / name).read_bytes())
        layout, founder = Layout.load(AE / prefix / 'parent.json')
        panel = np.load(AE / prefix / 'genomes.npy', allow_pickle=False)
        if (panel.shape != (65, 875) or panel.dtype != np.float32 or not np.isfinite(panel).all()
                or panel[0].tobytes() != founder.numpy().tobytes()
                or [hashlib.sha256(row.tobytes()).hexdigest() for row in panel] != ap['panel_genotype_sha256'][parent]
                or panel[selected[parent]['genome_row']].tobytes() != table[j + 2].tobytes()):
            raise ValueError('complete AE selected row differs from original Y panel')
        genome = torch.from_numpy(table[j + 2].copy())
        path = STUDY / 'inputs' / ('AE_' + parent + '.json')
        freeze_json(path, {'dims': layout.dims.__dict__, 'params': layout.to_dict(genome)})
        if Layout.load(path)[1].numpy().tobytes() != genome.numpy().tobytes():
            raise ValueError('start JSON roundtrip differs')
        refs.append(str(path.relative_to(STUDY)))
        starts[seed] = genome
        mapping[str(seed)] = {'background': parent, 'AE_selection': selected[parent],
                             'start_file': refs[-1], 'raw_sha256': selected[parent]['raw_sha256']}
    freeze_json(STUDY / 'generation_claim.json', {'registration_sha256': sha(STUDY / 'registration.json'), 'runs': reg['runs']})
    configs, initializations = {}, {}
    for seed in reg['runs']:
        cfg = search_config(seed, mapping[str(seed)]['start_file'])
        _, layout, _, evaluator = setup(cfg)
        check_world(asdict(evaluator.world()), ap['world'])
        if (evaluator.abi.version != 3 or not evaluator.extinct_charge or not evaluator.fast or evaluator.has_envelope
                or (cfg.evolve.mu, cfg.evolve.lam, cfg.life.lives, cfg.evolve.recheck_k, cfg.evolve.recheck_lives) != (32, 224, 3, 64, 4)
                or cfg.life.heldout or cfg.life.size_curve or cfg.clones.conditions or cfg.clones.every
                or (cfg.life.final_top, cfg.life.final_lives, cfg.life.final_fork_lives, cfg.life.valid_lives) != (1, 2, 0, 16)):
            raise ValueError('native four-generation scope/world differs')
        path = STUDY / f'configs/s{seed}.yaml'
        freeze(path, OmegaConf.to_yaml(cfg, resolve=True).encode())
        configs[str(seed)] = {'path': str(path.relative_to(STUDY)), 'sha256': sha(path)}
        generator = torch.Generator().manual_seed(seed)
        before = hashlib.sha256(generator.get_state().numpy().tobytes()).hexdigest()
        operations = []
        population = fill(starts[seed][None], 32, layout, generator, cfg.evolve, ops=operations).numpy()
        if population.shape != (32, 875) or population[0].tobytes() != starts[seed].numpy().tobytes() or len(operations) != 31:
            raise ValueError('native initialization differs')
        if any(set(item) != {'mut'} or len(item['mut']) != 2 for item in operations):
            raise ValueError('initialization must use only ordinary two-point mutations')
        data = io.BytesIO()
        np.save(data, population, allow_pickle=False)
        path = STUDY / f'initialization/s{seed}.npy'
        freeze(path, data.getvalue())
        initializations[str(seed)] = {'population_file': str(path.relative_to(STUDY)), 'file_sha256': sha(path),
            'population_raw_sha256': hashlib.sha256(population.tobytes()).hexdigest(),
            'generator_before_sha256': before, 'generator_after_sha256': hashlib.sha256(generator.get_state().numpy().tobytes()).hexdigest(),
            'copies': [{'id': i + 1, 'parent': 0, 'ops': item} for i, item in enumerate(operations)]}
    freeze_json(STUDY / 'initialization.json', {'status': 'pure_genetic_preparation', 'simulation_calls': 0, 'runs': initializations})
    pinned = [p for folder in ('inputs', 'configs', 'initialization') for p in (STUDY / folder).rglob('*') if p.is_file()]
    pinned += list(STUDY.glob('*.py')) + [STUDY / n for n in ('README.md', 'PREREG.md', 'SCHEMA.md',
        'registration.json', 'seed_audit.json', 'initialization.json', 'generation_claim.json', 'preparation_claim.json')]
    protocol = {'study': 'AF ordinary persistent-target continuation', 'abi': 3, 'runs': reg['runs'], 'generations': 4,
        'configs': configs, 'founder_mapping': mapping, 'reference_files': refs, 'world': ap['world'], 'world_packing': packing,
        'AE_protocol_sha256': AE_PROTOCOL, 'expected_numerical_identity': expected_identity, 'numerical_identity': ap['numerical_identity'],
        'production_pins': production, 'cost_projection': projection,
        'search_genome_lives': 8268, 'confirmation_genome_lives': 2048, 'planned_genome_lives': 10316,
        'startup_validation_genome_lives': 6, 'max_cpu_seconds': 5400, 'search_cpu_seconds': 3400, 'max_simulation_threads': 4,
        'confirmation': {'labels': LABELS, 'seeds': reg['confirmation_seeds'], 'threads': 2, 'primary_pairs': [[2, 0], [3, 1]]},
        'file_pins': {str(p.relative_to(STUDY)): sha(p) for p in sorted(pinned)}}
    freeze_json(STUDY / 'protocol.json', protocol)
    print(json.dumps({'status': 'prepared_unreleased', 'simulation_calls': 0, 'compiled_libraries': 0,
                      'initial_populations': 2, 'protocol_sha256': sha(STUDY / 'protocol.json')}))


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--prepare', action='store_true')
    args = parser.parse_args()
    if not args.prepare:
        print(json.dumps({'status': 'source_only_unregistered', 'research_lives': 10316, 'startup_validation_lives': 6,
                          'simulation_calls': 0, 'generated_populations': 0, 'requires': 'complete reviewed AE and root registration'}))
        return
    prepare()


if __name__ == '__main__':
    main()
