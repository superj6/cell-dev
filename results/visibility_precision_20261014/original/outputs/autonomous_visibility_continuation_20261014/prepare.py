"""Prepare Z only after terminal Y, reviewed registration and namespace evidence.

Dry-run default. This source-only draft never invokes setup/fill or reads Y runtime
artifacts until --prepare is explicitly invoked with the required root records.
"""
from __future__ import annotations

import argparse
import hashlib
import io
import json
import os
import sys
from dataclasses import asdict
from pathlib import Path

os.environ.setdefault('ATEN_CPU_CAPABILITY', 'avx2')
sys.dont_write_bytecode = True
STUDY = Path(__file__).resolve().parent
ROOT = STUDY.parents[1]
Y = ROOT / 'outputs/autonomous_visibility_gradient_20261014'
TEMPLATE = ROOT / 'results/decoy_evolution_20261014/runs/s53091/config.yaml'
sys.path.insert(0, str(ROOT))
PARENTS = ('D90', 'L92')
LABELS = ['D90', 'L92', 'Y_D90', 'Y_L92', 'Z_D90', 'Z_L92']
Y_PROTOCOL = '1880ff6e21b4689031e892d9dc6765a8d9673a35efeefb213acf268f5370adf4'


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def read(path):
    return json.loads(Path(path).read_text())


def freeze(path, data):
    path.parent.mkdir(parents=True, exist_ok=True)
    if path.exists() and path.read_bytes() != data:
        raise ValueError('prepared input changed: ' + str(path))
    path.write_bytes(data)


def freeze_json(path, value):
    freeze(path, (json.dumps(value, indent=2, allow_nan=False) + '\n').encode())


def cost_projection(rates):
    if set(rates) != set(PARENTS):
        raise ValueError('both developed backgrounds required')
    import math
    for item in rates.values():
        if set(item) != {'founder', 'Y_start'} or any(not math.isfinite(v) or v <= 0 for v in item.values()):
            raise ValueError('positive measured developed-body costs required')
    maxima = {p: max(rates[p].values()) for p in PARENTS}
    search = 180 + 1.5 * 4134 * sum(maxima.values())
    confirmation = 180 + 1.5 * 512 * sum(sum(rates[p].values()) + 2 * maxima[p] for p in PARENTS)
    return {'rates_cpu_per_life': rates, 'startup_search_projection': search,
            'confirmation_projection': confirmation, 'feasible': search <= 3590 and confirmation <= 3590,
            'limitation': 'Observed developed-body costs and fixed margins do not bound new mutants/endpoints.'}


def checked_registration():
    reg = read(STUDY / 'registration.json')
    if reg.get('status') != 'registered' or reg.get('founder_policy') != 'both_Y_selected_regardless_of_confirmation_sign':
        raise ValueError('explicit fixed-start root registration required')
    runs, seeds = reg['runs'], reg['confirmation_seeds']
    if (len(runs) != 2 or len(set(runs)) != 2 or len(seeds) != 512 or len(set(seeds)) != 512
            or any(type(x) is not int or x < 0 for x in runs + seeds) or 11 in seeds):
            raise ValueError('exact two search seeds and 512 fresh confirmation seeds required')
    if sha(Y / 'protocol.json') != Y_PROTOCOL:
        raise ValueError('frozen Y protocol differs')
    dependency = reg['Y_complete']
    for name, digest in dependency['file_pins'].items():
        if sha(Y / name) != digest:
            raise ValueError('terminal Y input changed: ' + name)
    summary_path = (ROOT / dependency['summary_path']).resolve()
    if not summary_path.is_relative_to(ROOT) or sha(summary_path) != dependency['summary_sha256']:
        raise ValueError('reviewed complete Y analysis required')
    summary, budget = read(summary_path), read(Y / 'budget.json')
    if (summary.get('status') != 'complete' or summary.get('protocol_sha256') != Y_PROTOCOL
            or budget.get('status') != 'complete' or budget.get('running') or budget.get('queued')
            or budget.get('cleanup_error') or budget.get('exit_code') != 0):
        raise ValueError('Y must be completely analyzed and cleanly terminal')
    audit = read(STUDY / 'seed_audit.json')
    if (audit.get('status') != 'passed' or audit.get('runs') != runs
            or audit.get('confirmation_seeds') != seeds
            or sha(STUDY / 'seed_audit.json') != reg['native_seed_audit_sha256']
            or reg['run_backgrounds'] != dict(zip(map(str, runs), PARENTS))):
        raise ValueError('independent exact namespace audit required')
    return reg, summary, summary_path, audit


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
    """Only declarative configuration; no setup, genetics, compilation or lives."""
    from omegaconf import OmegaConf
    cfg = OmegaConf.load(TEMPLATE)
    cfg.seed, cfg.threads = seed, 2
    cfg.evolve.generations, cfg.evolve.seed_genome = 4, str(STUDY / start_file)
    cfg.evolve.dup_rate, cfg.evolve.del_rate, cfg.evolve.dup_split = 0., 0., False
    cfg.logging.output_dir = str(STUDY / f'runs/s{seed}')
    cfg.logging.checkpoint_every, cfg.logging.lineage = 1, 'all'
    cfg.life.abi, cfg.life.world, cfg.life.control = 4, 'catch_speck_blink20_20_l4', 'ordinary_blink_Y_selected'
    cfg.life.T, cfg.life.T_choices = 1024, None
    cfg.life.flags, cfg.life.freeze_frac, cfg.life.t_open = [], None, 0.
    cfg.world, cfg.costs_life, cfg.envelope = {}, {}, {'enabled': False}
    return cfg


def prepare():
    if any((STUDY / name).exists() for name in ('ready.json', 'attempt.json', 'budget.json', 'runs', 'confirmation', 'build-cache', 'generation_claim.json')):
        raise ValueError('first preparation refuses prior generated/runtime work')
    reg, summary, _, seed_audit = checked_registration()
    import numpy as np
    import torch
    from numerical import check
    from omegaconf import OmegaConf

    from src.evolve import fill, setup
    from src.genome import Layout
    from src.life import spec

    yp = read(Y / 'protocol.json')
    for name, digest in yp['file_pins'].items():
        if sha(Y / name) != digest:
            raise ValueError('frozen Y input differs: ' + name)
    check(yp['numerical_identity'])  # Source/runtime checks only: no numerical_identity build/golden prepass.
    expected_identity = read(Y / 'startup_identity.json')['identity']
    production = {str(p.relative_to(ROOT)): sha(p) for p in sorted((ROOT / 'src').rglob('*.py'))}
    production['src/life/kernel.c'] = sha(ROOT / 'src/life/kernel.c')
    if production != expected_identity['sources']:
        raise ValueError('source/runtime changes invalidate direct Y timing reuse')
    for name in ('taskvar_confirm.py', 'taskvar_gradient.py', 'taskvar_gates.py'):
        production['scripts/' + name] = sha(ROOT / 'scripts' / name)
        if production['scripts/' + name] != yp['production_pins']['scripts/' + name]:
            raise ValueError('Y scoring helper changed')
    world = spec.world('catch_speck_blink20_20_l4', T=1024)
    if asdict(world) != yp['world']:
        raise ValueError('complete Y world differs')
    rates, cost_pins, selected = {}, {}, read(Y / 'selection.json')
    for parent in PARENTS:
        if selected[parent] != summary['backgrounds'][parent]['selection']:
            raise ValueError('both fixed Y selected rows must match complete analysis')
        rates[parent] = {}
        for role, index in (('founder', 0), ('Y_start', selected[parent]['genome_row'])):
            path = Y / f'measurement/{parent}/confirm/row_{index:04d}.npz'
            relative = str(path.relative_to(Y))
            if summary['input_pins'][relative] != sha(path):
                raise ValueError('complete Y timing row changed')
            with np.load(path, allow_pickle=False) as row:
                if row['ledger'].shape != (512, 58):
                    raise ValueError('developed-body calibration requires 512 real ABI4 lives')
                rates[parent][role] = float(row['cpu_seconds']) / 512
            cost_pins[relative] = sha(path)
    projection = cost_projection(rates)
    if not projection['feasible']:
        raise ValueError('unchanged scope does not fit developed-body cost projection')
    lists = {str(seed): planned_search_seeds(seed) for seed in reg['runs']}
    if seed_audit['run_life_seeds'] != lists:
        raise ValueError('native hash namespaces disagree with independent audit')
    flat = [x for values in lists.values() for x in values] + reg['confirmation_seeds']
    if len(set(flat)) != len(flat) or 11 in flat:
        raise ValueError('search, diagnostic or confirmation seed overlap')
    freeze_json(STUDY / 'inputs/Y_summary.json', summary)
    for name in ('protocol.json', 'selection.json', 'budget.json', 'startup_identity.json'):
        freeze(STUDY / 'inputs/Y' / name, (Y / name).read_bytes())
    freeze(STUDY / 'inputs/U_template.yaml', TEMPLATE.read_bytes())
    u_archive = ROOT / 'results/decoy_evolution_20261014'
    u_provenance = read(u_archive / 'provenance.json')
    if sha(TEMPLATE) != u_provenance['artifacts'][str(TEMPLATE.relative_to(u_archive))]['sha256']:
        raise ValueError('reviewed U search template changed')
    freeze_json(STUDY / 'inputs/Y_cost_rows.json', {'rates': rates, 'source_pins': cost_pins})
    for relative in cost_pins:
        freeze(STUDY / 'inputs/Y' / relative, (Y / relative).read_bytes())
    refs, starts, mapping = [], {}, {}
    for parent, seed in zip(PARENTS, reg['runs']):
        for name in ('parent.json', 'config.yaml', 'genomes.npy', 'panel_manifest.json', 'mutation_ops.json'):
            freeze(STUDY / 'inputs/Y/inputs' / parent / name, (Y / 'inputs' / parent / name).read_bytes())
        layout, founder = Layout.load(Y / 'inputs' / parent / 'parent.json')
        panel = np.load(Y / 'inputs' / parent / 'genomes.npy', allow_pickle=False)
        if (panel.shape != (65, 875) or panel.dtype != np.float32 or not np.isfinite(panel).all()
                or panel[0].tobytes() != founder.numpy().tobytes()):
            raise ValueError('frozen Y founder/table layout differs')
        index = selected[parent]['genome_row']
        if hashlib.sha256(panel[index].tobytes()).hexdigest() != selected[parent]['raw_sha256']:
            raise ValueError('selected start differs from frozen Y table')
        for label, genome in ((parent, founder), ('Y_' + parent, torch.from_numpy(panel[index].copy()))):
            path = STUDY / 'inputs' / (label + '.json')
            freeze_json(path, {'dims': layout.dims.__dict__, 'params': layout.to_dict(genome)})
            if Layout.load(path)[1].numpy().tobytes() != genome.numpy().tobytes():
                raise ValueError('genome JSON roundtrip differs')
        refs.append('inputs/' + parent + '.json')
        starts[seed] = torch.from_numpy(panel[index].copy())
        mapping[str(seed)] = {'background': parent, 'Y_selection': selected[parent],
                             'start_file': 'inputs/Y_' + parent + '.json', 'raw_sha256': selected[parent]['raw_sha256']}
    refs += ['inputs/Y_' + p + '.json' for p in PARENTS]
    with (STUDY / 'generation_claim.json').open('x') as stream:
        json.dump({'registration_sha256': sha(STUDY / 'registration.json'), 'runs': reg['runs']}, stream)
        stream.flush()
        os.fsync(stream.fileno())
    configs, initializations = {}, {}
    for seed in reg['runs']:
        cfg = search_config(seed, mapping[str(seed)]['start_file'])
        _, layout, _, evaluator = setup(cfg)
        if (evaluator.abi.version != 4 or asdict(evaluator.world()) != asdict(world)
                or not evaluator.extinct_charge or not evaluator.fast or evaluator.has_envelope
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
    pinned += list(STUDY.glob('*.py')) + [STUDY / n for n in ('README.md', 'PREREG.md', 'registration.json', 'seed_audit.json', 'initialization.json', 'generation_claim.json')]
    protocol = {'study': 'Z ordinary blink continuation', 'runs': reg['runs'], 'generations': 4,
        'configs': configs, 'founder_mapping': mapping, 'reference_files': refs, 'world': asdict(world),
        'expected_numerical_identity': expected_identity, 'numerical_identity': yp['numerical_identity'],
        'production_pins': production, 'cost_projection': projection,
        'search_genome_lives': 8268, 'confirmation_genome_lives': 3072, 'planned_genome_lives': 11340,
        'startup_validation_genome_lives': 6, 'max_cpu_seconds': 7200, 'search_cpu_seconds': 3600, 'max_simulation_threads': 4,
        'confirmation': {'labels': LABELS, 'seeds': reg['confirmation_seeds'], 'threads': 2,
                         'primary_pairs': [[4, 2], [5, 3]], 'cumulative_pairs': [[4, 0], [5, 1]], 'start_pairs': [[2, 0], [3, 1]]},
        'file_pins': {str(p.relative_to(STUDY)): sha(p) for p in sorted(pinned)}}
    freeze_json(STUDY / 'protocol.json', protocol)
    print(json.dumps({'status': 'prepared_unreleased', 'simulation_calls': 0, 'compiled_libraries': 0,
                      'initial_populations': 2, 'protocol_sha256': sha(STUDY / 'protocol.json')}))


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--prepare', action='store_true')
    args = parser.parse_args()
    if not args.prepare:
        print(json.dumps({'status': 'dry_run', 'research_lives': 11340, 'startup_validation_lives': 6,
                          'simulation_calls': 0, 'generated_populations': 0, 'requires': 'complete reviewed Y and root registration'}))
        return
    prepare()


if __name__ == '__main__':
    main()
