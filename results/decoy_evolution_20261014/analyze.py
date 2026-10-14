"""Independent NumPy-only U analysis. Never score an incomplete study or import its runner."""
from __future__ import annotations

import argparse
import hashlib
import importlib.util
import json
from pathlib import Path

import numpy as np

HERE = Path(__file__).resolve().parent
HELPER_SHA = '4e6800a092455649357cbd411b1352afcd3e4f82f6119ce7b597f068edd8df6c'
if hashlib.sha256((HERE / 'offline_accounting.py').read_bytes()).hexdigest() != HELPER_SHA:
    raise ValueError('independent accounting helper differs')
loader = importlib.util.spec_from_file_location('U_independent_accounting', HERE / 'offline_accounting.py')
A = importlib.util.module_from_spec(loader)
loader.loader.exec_module(A)
LABELS = ['I_s5_row32', 'I_s7_row1', 's53091_final_rank0', 's53092_final_rank0']
CONDITIONS = ['trained', 'width_swapped', 'frozen', 'frozen_lateral_off']
SEEDS = np.arange(52_060_000, 52_060_512, dtype=np.uint64)
COUNTS = ('F', 'captures', 'b2_clicks', 'clicks', 'misses', 'n_end', 'n_H_end', 'live_time', 'spikes', 'path')


def worlds(base):
    expected = {'T': 1024, 't0': 0, 't_open': 0, 't_fork': 0, 'flags': 0, 'fork_flags': 0,
                'd0': 1, 'd_min': .5, 'sigma': .6, 'lam_s': 2, 'b2_amp': 1,
                'b2_sigma': 1.2, 'b2_value': -50, 'b2_p': 1, 'b2_mode': 1}
    if any(base.get(k) != v for k, v in expected.items()):
        raise ValueError('fixed F/I world differs')
    return {'trained': base, 'width_swapped': dict(base, sigma=1.2, b2_sigma=.6),
            'frozen': dict(base, t_fork=512., t_open=544., fork_flags=16),
            'frozen_lateral_off': dict(base, t_fork=512., t_open=544., fork_flags=2064)}


def contrasts(rows, candidates=(2, 3)):
    result = {}
    for i in candidates:
        parent = i - 2
        gain = {condition: rows[condition][i]['F'] - rows[condition][parent]['F'] for condition in CONDITIONS}
        result[LABELS[i]] = {'trained_gain': A.stats(gain['trained'], flags=True),
                            'width_cue_interaction': A.stats(gain['trained'] - gain['width_swapped'], flags=True),
                            'added_frozen_lateral_dependence': A.stats(
                                gain['frozen'] - gain['frozen_lateral_off'], flags=True)}
    return result


def components(candidate, reference, world):
    span = world['T'] - world['t_open']
    terms = {'capture_income': world['R_cap'] * (candidate['captures'] - reference['captures']) / span,
             'poison_cost_saving': -world['b2_value'] * (reference['b2_clicks'] - candidate['b2_clicks']) / span,
             'miss_cost_saving': world['c_miss'] * (reference['misses'] - candidate['misses']) / span,
             'guard_charge_saving': (reference['guard_charge'] - candidate['guard_charge']) / span,
             'extinction_charge_saving': reference['extinct_charge'] - candidate['extinct_charge']}
    terms['other_cost_saving'] = ((reference['cost'] - candidate['cost']) / span -
                                 terms['poison_cost_saving'] - terms['miss_cost_saving'])
    residual = candidate['F'] - reference['F'] - sum(terms.values())
    if not np.allclose(residual, 0, rtol=0, atol=1e-9):
        raise ValueError('fitness decomposition does not reconcile')
    return {name: A.stats(value) for name, value in terms.items()}


def frozen_structure(rows):
    checked = []
    for i in range(4):
        arms = [rows[condition][i] for condition in CONDITIONS[2:]]
        complete = np.logical_and.reduce([(row['status'].astype(np.int64) & 7) == 0 for row in arms])
        for row in arms:
            if np.any(row['births'] != 0) or np.any(row['deaths'] != 0) or np.any(row['last_birth'] >= 544):
                raise ValueError('frozen tissue changed during accounting')
            for key in ('n_end', 'n_S_end', 'n_M_end', 'n_H_end'):
                if not A.identical(row[key][complete], arms[0][key][complete]):
                    raise ValueError('frozen pair has different composition')
            if not np.allclose(row['live_time'][complete], 480 * row['n_end'][complete], rtol=1e-10, atol=1e-8):
                raise ValueError('frozen cell-time differs')
        checked.append({'label': LABELS[i], 'complete_pairs': int(complete.sum()),
                        'guard_or_extinct_pairs': int((~complete).sum()), 'all_fitness_rows_retained': True})
    return checked


def analyze(base):
    if not (base / 'budget.json').exists():
        return {'status': 'not_started', 'confirmation': None, 'partial_outcomes_compared': False}
    budget = A.read(base / 'budget.json')
    if budget['status'] != 'complete':
        return {'status': budget['status'], 'confirmation': None, 'partial_outcomes_compared': False}
    if budget['running'] or budget['queued'] or budget['cpu_seconds'] >= 7200 or budget['exit_code'] != 0:
        raise ValueError('resource completion differs')
    expected_jobs = [('evolve_s53091', 0), ('evolve_s53092', 0), ('confirmation', 0)]
    A.equal(sorted((x['name'], x['exit_code']) for x in budget['completed']), sorted(expected_jobs), 'worker exits')
    protocol, ready = A.read(base / 'protocol.json'), A.read(base / 'ready.json')
    A.equal(ready, budget['ready'], 'released resource identity')
    for name, key in [('protocol.json', 'protocol_sha256'), ('run_budgeted.py', 'runner_sha256'),
                      ('measure.py', 'measurement_sha256')]:
        A.equal(A.sha(base / name), ready[key], 'release source ' + name)
    A.equal(protocol['planned_genome_lives'], 16460, 'planned research lives')
    A.equal(protocol['confirmation']['labels'], LABELS, 'role order')
    A.equal(protocol['confirmation']['conditions'], CONDITIONS, 'condition order')
    A.equal(protocol['confirmation']['seeds'], SEEDS.tolist(), 'registered seeds')
    conditions = worlds(protocol['world'])
    manifest = A.read(base / 'confirmation/endpoints.json')
    A.equal(manifest['protocol_sha256'], A.sha(base / 'protocol.json'), 'measurement protocol')
    A.equal(manifest['worlds'], conditions, 'all measurement world keys')
    A.equal(manifest['labels'], LABELS, 'frozen role order')
    A.equal(manifest['seeds'], SEEDS.tolist(), 'frozen seed order')
    A.equal(manifest['ready'], ready, 'frozen release')
    A.equal(manifest['numerical_identity'], protocol['expected_numerical_identity'], 'numerical identity')
    genomes = A.arrays(base / 'confirmation/genotypes.npz')
    A.equal(genomes['labels'].tolist(), LABELS, 'packed role order')
    for i, label in enumerate(LABELS):
        A.equal(hashlib.sha256(genomes['genomes'][i].tobytes()).hexdigest(),
                manifest['genotype_sha256'][label], 'frozen genome')
    for i, seed in enumerate((53091, 53092)):
        record = manifest['endpoints'][str(seed)]
        A.equal(record['generation'], 4, 'endpoint generation')
        A.equal(record['rank'], 0, 'endpoint rank')
        A.equal(A.sha(base / f'runs/s{seed}/checkpoint.pt'), record['checkpoint_sha256'], 'checkpoint bytes')
        A.equal(A.sha(base / f'runs/s{seed}/best_genome.json'), record['genome_file_sha256'], 'endpoint file')
        A.equal(manifest['genotype_sha256'][LABELS[i+2]], record['genome_raw_sha256'], 'endpoint genome')
        A.equal(manifest['genotype_sha256'][LABELS[i]], protocol['founder_mapping'][str(seed)]['raw_sha256'],
                'I founder genome')
        if any(value != 0 for value in record['search_health'].values()):
            raise ValueError('unhealthy search cannot establish an endpoint result')
    for relative, digest in protocol['inputs'].items():
        A.equal(A.sha(base / relative), digest, 'fixed input bytes')
    index = A.read(base / 'confirmation/row_index.json')
    expected_paths = {f'{c}/row_{i:04d}.npz' for c in CONDITIONS for i in range(4)}
    A.equal(set(index), expected_paths, 'complete raw row index')
    rows, health, cpu = {}, {}, 0.
    for condition, world in conditions.items():
        rows[condition], health[condition] = {}, {}
        for i in range(4):
            relative = f'{condition}/row_{i:04d}.npz'
            path = base / 'confirmation' / relative
            A.equal(A.sha(path), index[relative], 'indexed raw row')
            row = A.arrays(path)
            if not A.identical(row['seeds'], SEEDS) or int(row['genome_index']) != i:
                raise ValueError('raw seed or role order differs')
            health[condition][LABELS[i]] = A.validate_row(row, world)
            rows[condition][i] = row
            cpu += float(row['cpu_seconds'])
        aggregate = A.arrays(base / f'confirmation/{condition}/scores.npz')
        if not A.identical(aggregate['seeds'], SEEDS):
            raise ValueError('aggregate seed order differs')
        for key in A.COLS:
            if not A.identical(aggregate[key], np.stack([rows[condition][i][key] for i in range(4)])):
                raise ValueError('aggregate differs from raw rows: ' + key)
    if cpu > budget['cpu_seconds'] + 1e-6:
        raise ValueError('row CPU exceeds complete monitored study')
    report = A.read(base / 'confirmation/report.json')
    A.equal(report['status'], 'complete', 'measurement completion')
    A.equal(report['genome_lives'], 8192, 'measured life count')
    estimates = contrasts(rows)
    for label, values in estimates.items():
        A.check_stats({k: values['trained_gain'][k] for k in ('mean', 'se', 'n')},
                      report['primary'][label], 'primary ' + label)
        estimate = values['trained_gain']
        A.equal(report['primary'][label]['above_3se'], estimate['mean'] > 3 * estimate['se'], 'primary flag')
        A.equal(report['primary'][label]['at_least_0p5'], estimate['mean'] >= .5, 'practical flag')
        for ours, saved in [('width_cue_interaction', 'width_association_gain'),
                            ('added_frozen_lateral_dependence', 'added_lateral_dependence')]:
            A.check_stats({k: values[ours][k] for k in ('mean', 'se', 'n')},
                          report['secondary'][label][saved]['F'], ours + ' ' + label)
    descriptions = {condition: {LABELS[i]: {
        'absolute_means': {key: float(rows[condition][i][key].mean()) for key in COUNTS},
        'vs_own_founder': {key: A.stats(rows[condition][i][key] - rows[condition][i-2][key]) for key in COUNTS},
        'fitness_contributions': components(rows[condition][i], rows[condition][i-2], world)}
        for i in (2, 3)} for condition, world in conditions.items()}
    for condition, results in descriptions.items():
        for label, result in results.items():
            saved = report['conditions'][condition]['own_founder_contrasts'][label]
            for key, estimate in result['vs_own_founder'].items():
                A.check_stats(estimate, saved[key], condition + ' ' + label + ' ' + key)
            for name, estimate in result['fitness_contributions'].items():
                A.check_stats(estimate, saved['decoy_fitness_contributions'][name], name + ' ' + label)
    return {'status': 'complete', 'research_genome_lives': 16460, 'confirmation_genome_lives': 8192,
            'monitored_cpu_seconds': budget['cpu_seconds'], 'raw_confirmation_cpu_seconds': cpu,
            'confirmation': estimates, 'conditions': descriptions, 'health': health,
            'frozen_structure': frozen_structure(rows),
            'limits': ['Two fixed founders with one search each do not estimate general search reliability.',
                       'Width reversal changes spatial signal geometry as well as cue identity.',
                       'Frozen lateral dependence does not identify a discrimination algorithm.',
                       'Freeze stops gene, phenotype and effective-weight updates as well as growth.',
                       'Higher fitness, larger bodies and message dependence alone do not establish sophistication.']}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--study', type=Path, default=HERE)
    parser.add_argument('--out', type=Path)
    args = parser.parse_args()
    result = analyze(args.study)
    if args.out:
        A.save(args.out, result)
    print(json.dumps(result if result['status'] != 'complete' else
                     {key: result[key] for key in ('status', 'confirmation', 'monitored_cpu_seconds')}, indent=2))


if __name__ == '__main__':
    main()
