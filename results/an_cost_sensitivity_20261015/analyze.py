"""Post hoc AN price sensitivity; fixed trajectories only, no engines or AO observations."""
from __future__ import annotations

import argparse
import hashlib
import importlib.util
import json
import math
import sys
from pathlib import Path

import numpy as np

ROOT = next(p for p in Path(__file__).resolve().parents if (p / 'src/life/spec.py').is_file())
ARCHIVE = ROOT / 'results/occlusion_acquisition_20261015'
PROTOCOL = 'ca277b17294bbce52a4fd6bde77e5847b6b5230c00d285ba8492538f7508b26b'
SUMMARY = '1ce6412d0f063a429911ca80a5bc95c48cde08c087030a11def1abe46ac64512'
LITERAL = '8f90a044e21843d57cd3951bb882a8fe09c5a5df722ed63962c9fda0a0eed374'
ROLES = ('AM_current_start', 'generation4', 'generation8')
WEIGHTS = {'pool': .25, 'persistent': .25, 'blink80_20': .5}
GRIDS = {'c_live': (0., .25, .5, 1., 2.), 'c_miss': (.5, 1., 2., 4.)}
PAIRS = ((1, 0), (2, 0), (2, 1))


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def read(path):
    return json.loads(path.read_text())


def stats(x):
    mean = float(np.mean(x))
    se = float(np.std(x, ddof=1) / math.sqrt(len(x)))
    return {'mean': mean, 'se': se, 'n': len(x), 'lower_3se': mean - 3 * se, 'upper_3se': mean + 3 * se}


def reprice(row, price, multiplier):
    # Maintenance also scales the existing guard and extinction prices.
    return row['F'] + (1. - multiplier) * row[price]


def comparisons(values):
    return {ROLES[a] + '_minus_' + ROLES[b]: stats(values[ROLES[a]] - values[ROLES[b]]) for a, b in PAIRS}


def analyze(archive):
    if sha(archive / 'protocol.json') != PROTOCOL or sha(archive / 'analysis_result/summary.json') != SUMMARY:
        raise ValueError('completed AN protocol/summary differ')
    protocol = read(archive / 'protocol.json')
    summary = read(archive / 'analysis_result/summary.json')
    prior_review = read(archive / 'terminal_review/independent/independent_raw_review.json')
    if (summary['status'] != 'complete' or prior_review['status'] != 'passed'
            or prior_review['canonical_summary_sha256'] != SUMMARY or prior_review['literal_vectors_checked'] != 2933):
        raise ValueError('complete independently verified AN required')
    helper = archive / 'terminal_review/independent/verify_terminal_raw.py'
    if sha(helper) != LITERAL:
        raise ValueError('reviewed literal accountant changed')
    spec = importlib.util.spec_from_file_location('retained_AN_literal', helper)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    pins = {str(p.relative_to(archive)): sha(p) for p in (
        archive / 'protocol.json', archive / 'analysis_result/summary.json', archive / 'row_index.json',
        archive / 'endpoints.json', archive / 'terminal_review/independent/independent_raw_review.json', helper)}
    for name in ('src/life/kernel.c', 'src/life/evaluate.py', 'src/life/spec.py'):
        path = archive / 'production' / name
        if sha(path) != protocol['production_pins'][name]:
            raise ValueError('pinned physical/scoring source differs')
        pins[str(path.relative_to(archive))] = sha(path)
    index, endpoints = read(archive / 'row_index.json'), read(archive / 'endpoints.json')
    rows, health, prices = {}, {}, {}
    for world in WEIGHTS:
        definition = protocol['worlds'][world]
        w = definition['world']
        if w['R_cap'] != 500 or w['t_open'] != 0 or w['T'] != 1024 or w['b2_value'] != 0:
            raise ValueError('retained fixed-world accounting contract differs')
        prices[world] = {key: w[key] for key in ('c_live', 'c_miss', 'R_cap')}
        rows[world], health[world] = {}, {}
        for i, role in enumerate(ROLES):
            name = f'raw/{world}/row_{i:02d}.npz'
            path = archive / name
            if sha(path) != index[name]['sha256'] or sha(path) != summary['input_pins'][name]:
                raise ValueError('raw trajectory pin differs')
            pins[name] = sha(path)
            with np.load(path, allow_pickle=False) as z:
                raw = {k: z[k].copy() for k in z.files}
            if (raw['seeds'].dtype != np.uint64 or raw['seeds'].tolist() != protocol['seeds']
                    or str(raw['role']) != role or str(raw['world_name']) != world
                    or str(raw['protocol_sha256']) != PROTOCOL
                    or str(raw['endpoints_sha256']) != sha(archive / 'endpoints.json')
                    or str(raw['genome_raw_sha256']) != endpoints['genomes'][i]['raw_sha256']):
                raise ValueError('raw identity/pairing differs')
            v, health[world][role] = module.literal_row(raw, w, definition['abi'])
            row = {k: v[k] for k in ('F', 'captures', 'misses', 'clicks', 'capture_income')}
            row.update(ordinary_cost=-v['ordinary_cost'], maintenance=-v['cost__living'],
                       guard=-v['guard_cost'], extinction=-v['extinction_cost'],
                       c_live=-v['cost__living'] - v['guard_cost'] - v['extinction_cost'],
                       c_miss=-v['cost__missed_clicks'])
            for key in ('F', 'captures'):
                np.testing.assert_allclose(stats(row[key])['mean'], summary['absolute'][world][role][key]['mean'], rtol=0, atol=1e-12)
            for price in GRIDS:
                np.testing.assert_array_equal(reprice(row, price, 1.), row['F'])
            rows[world][role] = row
    rows['mixed_25_25_50'] = {
        role: {key: sum(WEIGHTS[w] * rows[w][role][key] for w in WEIGHTS)
               for key in rows['pool'][role]} for role in ROLES}
    baseline = {world: {
        'roles': {role: {k: stats(v) for k, v in row.items()} for role, row in by_role.items()},
        'paired_F': comparisons({r: by_role[r]['F'] for r in ROLES}),
        'paired_captures': comparisons({r: by_role[r]['captures'] for r in ROLES})}
        for world, by_role in rows.items()}
    grid = {}
    for price, multipliers in GRIDS.items():
        grid[price] = []
        for multiplier in multipliers:
            contexts = {}
            for world, by_role in rows.items():
                values = {r: reprice(by_role[r], price, multiplier) for r in ROLES}
                contexts[world] = {'absolute_F': {r: stats(v) for r, v in values.items()},
                    'paired_F': comparisons(values),
                    'mean_rank_descending': sorted(ROLES, key=lambda r: -float(values[r].mean()))}
            grid[price].append({'multiplier': multiplier, 'other_price_multiplier': 1., 'contexts': contexts})
    break_even = {}
    mixed = rows['mixed_25_25_50']
    base = mixed['generation8']['F'] - mixed['generation4']['F']
    for price in GRIDS:
        # Delta(m) = Delta(1) + (m-1) * (charge_g4 - charge_g8).
        slope = mixed['generation4'][price] - mixed['generation8'][price]
        intercept = base - slope
        root = None if float(slope.mean()) == 0 else -float(intercept.mean()) / float(slope.mean())
        if root is not None:
            np.testing.assert_allclose((intercept + root * slope).mean(), 0., rtol=0, atol=1e-12)
        break_even[price] = {'equation': 'mean_delta_F(m) = intercept + m * slope',
            'baseline_delta_F': stats(base), 'intercept_at_zero': stats(intercept), 'slope': stats(slope),
            'point_break_even_multiplier': root, 'nonnegative_price_domain': root is not None and root >= 0,
            'paired_effect_at_point_break_even': None if root is None else stats(intercept + root * slope),
            'g8_higher_mean_above_break_even': bool(slope.mean() > 0),
            'limit': 'Descriptive ratio of sample means; no confidence interval for the estimated crossing.'}
    if any(name == 'torch' or name.startswith('src.') for name in sys.modules):
        raise ValueError('engine/production import is forbidden')
    if any(sha(archive / path) != digest for path, digest in pins.items()):
        raise ValueError('analyzed input changed')
    return {'status': 'complete', 'planning': 'Post hoc, directed after AN completion and before inspecting any AO outcomes; grids fixed in this source before execution.',
        'script_sha256': sha(Path(__file__)), 'archive': str(archive.relative_to(ROOT)), 'input_pins': pins,
        'roles': ROLES, 'training_world_weights': WEIGHTS, 'prices': prices,
        'raw_rows': 9, 'retained_lives': 4608, 'paired_seed_count': 512, 'status_counts': health,
        'baseline_original_prices': baseline, 'separate_price_grids': grid, 'g8_minus_g4_mixed_break_even': break_even,
        'formula': 'F_live(m)=F+(1-m)*(maintenance+guard+extinction); F_miss(m)=F+(1-m)*miss_charge. All quantities are per unit time.',
        'source_conclusion': 'Both prices enter accounting only. Neither feeds cell state, development, actuation, capture geometry, scheduling, or death. c_live also sets guard/extinction scoring; numeric ledger/hash values may change.',
        'source_locations': {'production/src/life/kernel.c': [1261, 1475, 1913, 1920, 1925, 1933],
                             'production/src/life/evaluate.py': [261, 267, 269, 270]},
        'limits': ['Exact mathematical repricing of these saved trajectories, within floating-point tolerance; not a replay of an altered evolutionary search.',
                   'Mean rankings are descriptive; paired SE uses 512 seeds, not independent evolutionary replicates.',
                   'Cross-world weights are applied per shared seed before SE, preserving measured covariance; this does not estimate native 8+8 selection error.',
                   'No optimum price, acquisition improvement, retained capability, or richer algorithm follows from changing accounting.',
                   'Original production prices, frozen AO sources, and selection remain unchanged.'],
        'new_lives': 0, 'builds': 0, 'genetic_draws': 0, 'AO_outcomes_read': False}


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--archive', type=Path, default=ARCHIVE)
    parser.add_argument('--out', type=Path, default=Path(__file__).with_name('summary.json'))
    args = parser.parse_args()
    result = analyze(args.archive.resolve())
    with args.out.open('x') as stream:
        stream.write(json.dumps(result, indent=2, allow_nan=False) + '\n')
    print(json.dumps({'status': result['status'], 'raw_rows': result['raw_rows'],
                     'summary_sha256': sha(args.out), 'break_even': result['g8_minus_g4_mixed_break_even']}))
