"""AB source-only preparation; actual inputs and native fill require explicit root registration."""
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
Z = ROOT / 'outputs/autonomous_visibility_continuation_20261014'
Z_PROTOCOL = '2e3e2a2f7bd19f8a10620f8bf4c23a5eb31d4c033a48c0939bf421d234be2935'
TEMPLATE = Z / 'configs/s53220.yaml'
PARENTS = ('D90', 'L92')
RUNS = ('D90_depth', 'D90_precision', 'L92_depth', 'L92_precision')
LABELS = ['Z_D90', 'Z_L92', 'depth_D90', 'precision_D90', 'depth_L92', 'precision_L92']
Z_LABELS = ['D90', 'L92', 'Y_D90', 'Y_L92', 'Z_D90', 'Z_L92']
sys.path.insert(0, str(ROOT))


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


def settings(run, seed):
    if run not in RUNS:
        raise ValueError('unknown fixed background/policy')
    background, policy = run.split('_')
    return {'background': background, 'policy': policy, 'seed': seed,
            'generations': 4 if policy == 'depth' else 1,
            'initial_lives': 3 if policy == 'depth' else 12, 'recheck_lives': 4 if policy == 'depth' else 16}


def cost_projection(rates):
    if set(rates) != set(Z_LABELS) or any(not math.isfinite(v) or v <= 0 for v in rates.values()):
        raise ValueError('all six positive actual Z confirmation costs required')
    maxima = {p: max(rates[p], rates['Y_' + p], rates['Z_' + p]) for p in PARENTS}
    search = 180 + 1.5 * 8252 * sum(maxima.values())
    confirmation = 180 + 1.5 * 512 * sum(rates['Z_' + p] + 2 * maxima[p] for p in PARENTS)
    return {'rates_cpu_per_life': rates, 'lineage_maxima': maxima,
            'startup_search_projection': search, 'confirmation_projection': confirmation,
            'search_release_threshold': 7190, 'confirmation_release_threshold': 1790,
            'feasible': search <= 7190 and confirmation <= 1790,
            'limitation': 'Observed developed-body costs and fixed margins do not bound new mutants/endpoints.'}


def planned_search_seeds(run, seed):
    from src.life.evaluate import life_seed
    item = settings(run, seed)
    count = item['generations']
    result = []
    for g in range(count):
        result.extend(life_seed(seed, 'gen', g, j)
                      for j in range(item['initial_lives'] + item['recheck_lives']))
        if g % 4 == 0 or g == count - 1:
            result.extend(life_seed(seed, 'valid', g, j) for j in range(16))
    for index in (0, 1):
        result.extend(life_seed(seed, 'final', index, j) for j in range(2))
    return result


def search_config(run, seed, start_file):
    """Declarative only: no setup, fill, compilation, numerical golden or life."""
    from omegaconf import OmegaConf
    item = settings(run, seed)
    cfg = OmegaConf.load(TEMPLATE)
    cfg.seed, cfg.threads = seed, 2
    cfg.evolve.generations = item['generations']
    cfg.life.lives, cfg.evolve.recheck_lives = item['initial_lives'], item['recheck_lives']
    cfg.evolve.seed_genome = str(STUDY / start_file)
    cfg.life.control = 'blink_precision_allocation_' + item['policy']
    cfg.logging.output_dir = str(STUDY / 'runs' / run)
    return cfg


def registration():
    item = read(STUDY / 'registration.json')
    if (item.get('status') != 'registered' or item.get('runs') != list(RUNS)
            or item.get('founder_policy') != 'both_Z_final_rank0_regardless_of_AA_or_confirmation'):
        raise ValueError('root registration of both fixed founders and four policy jobs required')
    paired, seeds = item['paired_native_seeds'], item['confirmation_seeds']
    if (set(paired) != set(PARENTS) or len(set(paired.values())) != 2
            or len(seeds) != 512 or len(set(seeds)) != 512 or 11 in seeds
            or any(type(x) is not int or x < 0 for x in list(paired.values()) + seeds)):
        raise ValueError('two paired native seeds and 512 fresh confirmation seeds required')
    audit = read(STUDY / 'seed_audit.json')
    if (audit.get('status') != 'passed' or audit.get('paired_native_seeds') != paired
            or audit.get('confirmation_seeds') != seeds
            or sha(STUDY / 'seed_audit.json') != item['seed_audit_sha256']):
        raise ValueError('root-reviewed exact paired namespace required')
    dep = item['Z_complete']
    if sha(Z / 'protocol.json') != Z_PROTOCOL:
        raise ValueError('fixed Z protocol differs')
    for name, digest in dep['file_pins'].items():
        path = (Z / name).resolve()
        if not path.is_relative_to(Z.resolve()) or sha(path) != digest:
            raise ValueError('terminal Z dependency differs: ' + name)
    required = {'protocol.json', 'budget.json', 'confirmation/endpoints.json', 'confirmation/genotypes.npz',
                'confirmation/row_index.json', 'confirmation/report.json'}
    if not required.issubset(dep['file_pins']):
        raise ValueError('terminal Z evidence pins incomplete')
    summary_path = (ROOT / dep['summary_path']).resolve()
    if not summary_path.is_relative_to(ROOT) or sha(summary_path) != dep['summary_sha256']:
        raise ValueError('reviewed complete Z analysis required')
    summary, budget = read(summary_path), read(Z / 'budget.json')
    if (summary.get('status') != 'complete' or summary.get('protocol_sha256') != Z_PROTOCOL
            or budget.get('status') != 'complete' or budget.get('running') or budget.get('queued')
            or budget.get('cleanup_error') or budget.get('exit_code') != 0):
        raise ValueError('Z must be completely analyzed and cleanly terminal')
    return item, summary, audit


def prepare():
    forbidden = ('protocol.json', 'inputs', 'configs', 'initialization', 'generation_claim.json',
                 'ready.json', 'attempt.json', 'budget.json', 'runs', 'confirmation', 'logs', 'build-cache')
    if any((STUDY / name).exists() for name in forbidden):
        raise ValueError('first preparation refuses previous inputs, generation or runtime work')
    reg, summary, audit = registration()
    import numpy as np
    import torch
    from numerical import check
    from omegaconf import OmegaConf

    from src.evolve import fill, setup
    from src.genome import Layout
    from src.life import spec

    zp = read(Z / 'protocol.json')
    for key, base in (('file_pins', Z), ('production_pins', ROOT)):
        for name, digest in zp[key].items():
            if sha(base / name) != digest:
                raise ValueError('frozen Z source or input differs: ' + name)
    check(zp['numerical_identity'])  # Metadata only; never call numerical_identity in preparation.
    world = spec.world('catch_speck_blink20_20_l4', T=1024)
    if asdict(world) != zp['world']:
        raise ValueError('exact unchanged approved blink world required')
    endpoints = read(Z / 'confirmation/endpoints.json')
    if (endpoints['labels'] != Z_LABELS or endpoints['protocol_sha256'] != Z_PROTOCOL
            or endpoints['numerical_identity'] != zp['expected_numerical_identity']):
        raise ValueError('exact terminal six-role Z binding required')
    with np.load(Z / 'confirmation/genotypes.npz', allow_pickle=False) as table:
        genomes, labels = table['genomes'], table['labels']
    if (genomes.shape != (6, 875) or genomes.dtype != np.float32 or labels.tolist() != Z_LABELS
            or not np.isfinite(genomes).all()):
        raise ValueError('six exact terminal ABI4 genotypes required')
    raw_pins = {label: hashlib.sha256(g.tobytes()).hexdigest() for label, g in zip(Z_LABELS, genomes)}
    if raw_pins != endpoints['genotype_sha256']:
        raise ValueError('Z six-role array differs from endpoint binding')
    index, rates, cost_pins = read(Z / 'confirmation/row_index.json'), {}, {}
    for i, label in enumerate(Z_LABELS):
        relative = f'blink/row_{i:04d}.npz'
        path = Z / 'confirmation' / relative
        if sha(path) != index[relative]['sha256']:
            raise ValueError('terminal Z timing row changed')
        with np.load(path, allow_pickle=False) as row:
            identity = json.loads(str(row['identity']))
            if (row['ledger'].shape != (512, 58) or int(row['genome_index']) != i
                    or identity['role'] != label or identity['genome_sha256'] != raw_pins[label]
                    or identity['endpoints_sha256'] != sha(Z / 'confirmation/endpoints.json')
                    or row['seeds'].tolist() != zp['confirmation']['seeds']
                    or float(row['cpu_seconds']) != index[relative]['cpu_seconds']):
                raise ValueError('actual Z confirmation timing identity differs')
            rates[label] = float(row['cpu_seconds']) / 512
        cost_pins['confirmation/' + relative] = sha(path)
    projection = cost_projection(rates)
    if not projection['feasible']:
        raise ValueError('unchanged scope fails conservative lineage-max cost projection')
    lists = {run: planned_search_seeds(run, reg['paired_native_seeds'][run.split('_')[0]]) for run in RUNS}
    overlap = {p: sorted(set(lists[p + '_depth']) & set(lists[p + '_precision'])) for p in PARENTS}
    if audit['run_life_seeds'] != lists or audit['intentional_overlap'] != overlap:
        raise ValueError('native life IDs or intentional policy overlap differs')
    unions = {p: set(lists[p + '_depth']) | set(lists[p + '_precision']) for p in PARENTS}
    if (any(len(lists[run]) != len(set(lists[run])) for run in RUNS)
            or unions['D90'] & unions['L92'] or (unions['D90'] | unions['L92']) & set(reg['confirmation_seeds'])
            or 11 in unions['D90'] | unions['L92']):
        raise ValueError('unintended research namespace overlap')
    reference = zp['reference_files'][0]
    layout, original = Layout.load(Z / reference)
    if original.numpy().tobytes() != genomes[0].tobytes():
        raise ValueError('retained genome layout reference differs')
    copied = {name: name for name in ('protocol.json', 'budget.json', 'confirmation/endpoints.json',
                                     'confirmation/genotypes.npz', 'confirmation/row_index.json', 'confirmation/report.json')}
    copied.update({name: name for name in cost_pins})
    copied[reference] = 'layout_reference.json'
    copied[str(TEMPLATE.relative_to(Z))] = 'template.yaml'
    for source, target in copied.items():
        freeze(STUDY / 'inputs/Z' / target, (Z / source).read_bytes())
    freeze_json(STUDY / 'inputs/Z_summary.json', summary)
    freeze_json(STUDY / 'inputs/Z_cost_rows.json', {'rates': rates, 'source_pins': cost_pins, 'projection': projection})
    mapping, starts = {}, {}
    for parent, i in zip(PARENTS, (4, 5)):
        raw = torch.from_numpy(genomes[i].copy())
        name = f'inputs/Z_{parent}.json'
        freeze_json(STUDY / name, {'dims': layout.dims.__dict__, 'params': layout.to_dict(raw)})
        if Layout.load(STUDY / name)[1].numpy().tobytes() != raw.numpy().tobytes():
            raise ValueError('fixed Z start JSON roundtrip differs')
        mapping[parent] = {'start_file': name, 'raw_sha256': raw_pins['Z_' + parent], 'Z_role_index': i,
                           'Z_endpoint': endpoints['endpoints'][str(zp['runs'][i - 4])]}
        starts[parent] = raw
    with (STUDY / 'generation_claim.json').open('x') as stream:
        json.dump({'registration_sha256': sha(STUDY / 'registration.json'),
                   'paired_native_seeds': reg['paired_native_seeds'], 'populations_to_generate': 2}, stream)
        stream.flush()
        os.fsync(stream.fileno())
    configs, initializations = {}, {}
    for parent in PARENTS:
        seed = reg['paired_native_seeds'][parent]
        cfg = search_config(parent + '_depth', seed, mapping[parent]['start_file'])
        _, current_layout, _, evaluator = setup(cfg)
        if (current_layout.dims != layout.dims or evaluator.abi.version != 4
                or asdict(evaluator.world()) != asdict(world) or not evaluator.extinct_charge or not evaluator.fast
                or evaluator.has_envelope or cfg.life.heldout or cfg.life.size_curve
                or cfg.clones.conditions or cfg.clones.every):
            raise ValueError('native ABI4 initialization/scoring scope differs')
        generator = torch.Generator().manual_seed(seed)
        before = hashlib.sha256(generator.get_state().numpy().tobytes()).hexdigest()
        operations = []
        population = fill(starts[parent][None], 32, layout, generator, cfg.evolve, ops=operations).numpy()
        if (population.shape != (32, 875) or population[0].tobytes() != starts[parent].numpy().tobytes()
                or len(operations) != 31 or any(set(op) != {'mut'} or len(op['mut']) != 2 for op in operations)):
            raise ValueError('ordinary 31-mutant initialization differs')
        data = io.BytesIO()
        np.save(data, population, allow_pickle=False)
        path = STUDY / f'initialization/{parent}.npy'
        freeze(path, data.getvalue())
        initializations[parent] = {'population_file': str(path.relative_to(STUDY)), 'file_sha256': sha(path),
            'population_raw_sha256': hashlib.sha256(population.tobytes()).hexdigest(),
            'generator_before_sha256': before,
            'generator_after_sha256': hashlib.sha256(generator.get_state().numpy().tobytes()).hexdigest(),
            'copies': [{'id': j + 1, 'parent': 0, 'ops': op} for j, op in enumerate(operations)]}
        for policy in ('depth', 'precision'):
            run = parent + '_' + policy
            current = search_config(run, seed, mapping[parent]['start_file'])
            path = STUDY / f'configs/{run}.yaml'
            freeze(path, OmegaConf.to_yaml(current, resolve=True).encode())
            configs[run] = {'path': str(path.relative_to(STUDY)), 'sha256': sha(path)}
    freeze_json(STUDY / 'initialization.json', {'status': 'pure_genetic_preparation', 'simulation_calls': 0,
        'backgrounds': initializations, 'runs': {run: run.split('_')[0] for run in RUNS}})
    pinned = [p for folder in ('inputs', 'configs', 'initialization') for p in (STUDY / folder).rglob('*') if p.is_file()]
    pinned += list(STUDY.glob('*.py')) + [STUDY / n for n in ('README.md', 'PREREG.md', 'SCHEMA.md',
        'registration.json', 'seed_audit.json', 'initialization.json', 'generation_claim.json')]
    protocol = {'study': 'AB blink precision versus depth', 'runs': list(RUNS),
        'paired_native_seeds': reg['paired_native_seeds'],
        'run_settings': {run: settings(run, reg['paired_native_seeds'][run.split('_')[0]]) for run in RUNS},
        'configs': configs, 'founder_mapping': mapping,
        'reference_files': [mapping[p]['start_file'] for p in PARENTS], 'world': asdict(world),
        'expected_numerical_identity': zp['expected_numerical_identity'], 'numerical_identity': zp['numerical_identity'],
        'production_pins': zp['production_pins'], 'cost_projection': projection,
        'search_genome_lives': 16504, 'confirmation_genome_lives': 3072, 'planned_genome_lives': 19576,
        'startup_validation_genome_lives': 10, 'max_cpu_seconds': 9000, 'search_cpu_seconds': 7200,
        'max_simulation_threads': 4, 'confirmation': {'labels': LABELS, 'seeds': reg['confirmation_seeds'], 'threads': 2,
            'primary_pairs': [[3, 2], [5, 4]], 'gain_pairs': [[2, 0], [3, 0], [4, 1], [5, 1]]},
        'file_pins': {str(path.relative_to(STUDY)): sha(path) for path in sorted(pinned)}}
    freeze_json(STUDY / 'protocol.json', protocol)
    print(json.dumps({'status': 'prepared_unreleased', 'simulation_calls': 0, 'compiled_libraries': 0,
                      'initial_populations': 2, 'native_jobs': 4, 'protocol_sha256': sha(STUDY / 'protocol.json')}))


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--prepare', action='store_true')
    args = parser.parse_args()
    if not args.prepare:
        print(json.dumps({'status': 'source_only_unregistered', 'research_lives': 19576, 'startup_validation_lives': 10,
                          'simulation_calls': 0, 'generated_populations': 0,
                          'requires': 'reviewed terminal Z, paired namespace audit and root registration'}))
        return
    prepare()


if __name__ == '__main__':
    main()
