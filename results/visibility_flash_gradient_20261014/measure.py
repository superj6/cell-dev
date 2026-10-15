"""AC: retained ordinary-mutant panels in flash, followed by paired flash/blink confirmation.

Dry run is the default. Actual work requires a registered protocol, root release,
and the reviewed monitor's live ownership and accounted phase acknowledgments.
"""
from __future__ import annotations

import argparse
import json
import math
import os
import sys
import time
from dataclasses import asdict
from pathlib import Path

os.environ.setdefault('ATEN_CPU_CAPABILITY', 'avx2')
sys.dont_write_bytecode = True
STUDY = Path(__file__).resolve().parent
ROOT = STUDY.parents[1]
sys.path.insert(0, str(ROOT))

from common import parent_check, read, require_release, save, sha  # noqa: E402

PARENTS = ('D90', 'L92')
WORLDS = {'flash': 'catch_speck_flash5_dim25_l4', 'blink': 'catch_speck_blink20_20_l4'}
ROLES = ['P_D90', 'P_L92', 'B_D90', 'B_L92', 'H_D90', 'H_L92']
BLINK_ROWS = {'D90': 58, 'L92': 24}
CAP, SCREEN_CAP, RESERVE, STARTUP_CAP, MARGIN = 7200, 3400, 3800, 180, 10
SCOPE = {'total_cpu_seconds': CAP, 'startup_screen_cpu_seconds': SCREEN_CAP,
         'confirmation_reserve_cpu_seconds': RESERVE, 'startup_calibration_cpu_seconds': STARTUP_CAP,
         'max_workers': 1, 'threads_per_worker': 2, 'research_lives': 10304, 'validation_lives': 10}


def stage_seeds(protocol):
    expected = {'screen': 32, 'confirm': 512, 'calibration': 2}
    seeds = protocol['seeds']
    if set(seeds) != set(expected):
        raise ValueError('fixed stage seed set changed')
    flat = []
    for key, count in expected.items():
        row = seeds[key]
        if len(row) != count or any(type(x) is not int or not 0 <= x < 2**64 for x in row):
            raise ValueError('fixed unsigned stage seeds changed')
        flat.extend(row)
    if len(set(flat)) != len(flat) or 11 in flat:
        raise ValueError('fresh stages or retained numerical golden overlap')
    return seeds


def select_winner(rows):
    """Y's whole-mean, then lowest-row rule; the parent cannot win selection."""
    import numpy as np
    if set(rows) != set(range(65)):
        raise ValueError('selection requires all 65 parent/mutant rows')
    for row in rows.values():
        if np.asarray(row['F']).shape != (32,) or not np.isfinite(row['F']).all():
            raise ValueError('selection requires complete finite 32-life rows')
    return min(range(1, 65), key=lambda i: (-float(rows[i]['F'].mean()), i))


def historical_rates(protocol):
    rates = protocol['historical_blink_cpu_per_life']
    if (set(rates) != set(PARENTS) or any(len(rates[p]) != 65 for p in PARENTS)
            or any(not isinstance(x, (int, float)) or not math.isfinite(x) or x <= 0
                   for p in PARENTS for x in rates[p])):
        raise ValueError('all 130 retained positive blink screen costs required')
    return rates


def calibration_projection(rows, startup_cpu, historical):
    rates = {p: max(float(rows[p][i]['cpu_seconds']) / 2 for i in (0, 1)) for p in PARENTS}
    screen = startup_cpu + 1.5 * 2080 * sum(rates.values())
    # Every role stays in the sum, even when two roles share a genome.
    role_rates = {'flash': {r: rates[r.split('_')[1]] for r in ROLES}, 'blink': {}}
    for p in PARENTS:
        role_rates['blink'].update({f'P_{p}': historical[p][0], f'B_{p}': historical[p][BLINK_ROWS[p]],
                                   f'H_{p}': max(historical[p])})
    confirm = 180 + 1.5 * 512 * sum(v for world in role_rates.values() for v in world.values())
    return {'flash_batch_max_cpu_per_life': rates, 'startup_cpu_seconds': startup_cpu,
            'confirmation_role_rates': role_rates, 'screen_projection_cpu_seconds': screen,
            'confirmation_projection_cpu_seconds': confirm,
            'screen_threshold': 3390, 'confirmation_threshold': 3790,
            'feasible': screen <= 3390 and confirm <= 3790,
            'limitation': 'Four two-seed batches do not bound slow mutants or changes in developed bodies.'}


def selected_projection(screens, winners, historical):
    rates = {'flash': {}, 'blink': {}}
    for p in PARENTS:
        for prefix, index in (('P', 0), ('B', BLINK_ROWS[p]), ('H', winners[p]['genome_row'])):
            rates['flash'][f'{prefix}_{p}'] = float(screens[p][index]['cpu_seconds']) / 32
            rates['blink'][f'{prefix}_{p}'] = historical[p][index]
    estimate = 180 + 1.5 * 512 * sum(v for world in rates.values() for v in world.values())
    return {'confirmation_role_rates': rates, 'confirmation_projection_cpu_seconds': estimate,
            'confirmation_threshold': 3790, 'feasible': estimate <= 3790,
            'limitation': 'Observed 32-life costs and fixed margins do not bound future 512-life costs.'}


def monitor_ack(name, payload, parent_pid):
    parent_check(parent_pid)
    request = STUDY / 'requests' / (name + '.json')
    response = STUDY / 'monitor_receipts' / (name + '.json')
    if request.exists() or response.exists():
        raise ValueError('first attempt refuses an existing phase handshake')
    save(request, {'protocol_sha256': sha(STUDY / 'protocol.json'), **payload})
    deadline = time.monotonic() + 60
    while not response.exists():
        parent_check(parent_pid)
        if time.monotonic() >= deadline:
            raise RuntimeError('monitor phase acknowledgment timed out')
        time.sleep(0.1)
    receipt = read(response)
    limit = 170 if name == 'calibration_complete' else 3390
    cpu = receipt.get('cpu_seconds')
    if (receipt.get('status') != 'allowed' or receipt.get('request_sha256') != sha(request)
            or receipt.get('protocol_sha256') != sha(STUDY / 'protocol.json')
            or receipt.get('attempt_sha256') != sha(STUDY / 'attempt.json')
            or not isinstance(cpu, (int, float)) or not 0 <= cpu <= limit):
        raise ValueError('monitor phase receipt changed or exceeded its ceiling')
    parent_check(parent_pid)
    return receipt


def load_panels(protocol):
    import numpy as np
    from omegaconf import OmegaConf
    from scoring import raw_sha

    from src.genome import Layout
    from src.life import spec
    from src.life.evaluate import LifeEvaluator

    if (protocol['monitor_scope'] != SCOPE or protocol['roles'] != ROLES
            or protocol['blink_selected_rows'] != BLINK_ROWS):
        raise ValueError('fixed scope or six-role mapping changed')
    worlds = {key: spec.world(preset, T=1024) for key, preset in WORLDS.items()}
    if {key: asdict(value) for key, value in worlds.items()} != protocol['worlds']:
        raise ValueError('approved production worlds changed')
    panels, evaluators = {}, {key: {} for key in WORLDS}
    for p in PARENTS:
        prefix = STUDY / 'inputs/Y/inputs' / p
        manifest = read(prefix / 'panel_manifest.json')
        table = np.load(prefix / 'genomes.npy', allow_pickle=False)
        layout, founder = Layout.load(str(prefix / 'parent.json'))
        if (table.dtype != np.float32 or table.shape != (65, 875) or not np.isfinite(table).all()
                or table[0].tobytes() != founder.reshape(-1).float().numpy().tobytes()
                or [raw_sha(row) for row in table] != protocol['panel_genotype_sha256'][p]
                or manifest['genomes_sha256'] != raw_sha(table)):
            raise ValueError('retained complete Y panel changed')
        for key, world in worlds.items():
            cfg = OmegaConf.load(STUDY / f'configs/{key}_{p}.yaml')
            evaluator = LifeEvaluator(cfg, layout)
            if (evaluator.abi.version != 4 or not evaluator.extinct_charge or evaluator.threads != 2
                    or not evaluator.fast or evaluator.T_choices or evaluator.has_envelope
                    or asdict(evaluator.world()) != asdict(world)):
                raise ValueError('derived configuration differs from fixed production scoring')
            evaluators[key][p] = evaluator
        panels[p] = table
    historical_rates(protocol)
    return panels, evaluators, worlds


def contrast_reports(rows, worlds):
    """Paired flash-minus-blink differences are formed before any summary statistic."""
    import numpy as np
    from scoring import ABI, COLS

    from scripts.taskvar_gates import paired

    def metrics(row, world):
        value = {name: row[name] for name in COLS}
        ledger = np.stack([row[name] for name in ABI.LEDGER], axis=1)
        value.update(bright_captures=row['captures'] - row['low_light_captures'],
                     capture_income=row['income'] / world.T,
                     ordinary_cost=-ABI.column_cost(ledger, world) / world.T,
                     guard_cost=-row['guard_charge'] / world.T,
                     extinction_cost=-row['extinct_charge'])
        if not np.allclose(value['F'], sum(value[k] for k in
                           ('capture_income', 'ordinary_cost', 'guard_cost', 'extinction_cost')), atol=1e-9, rtol=0):
            raise ValueError('production fitness decomposition changed')
        return value

    values = {w: {r: metrics(rows[w][i], worlds[w]) for i, r in enumerate(ROLES)} for w in WORLDS}
    contrasts = {}
    for p in PARENTS:
        for a, b in ((f'H_{p}', f'P_{p}'), (f'B_{p}', f'P_{p}'), (f'H_{p}', f'B_{p}')):
            delta = {w: {k: values[w][a][k] - values[w][b][k] for k in values[w][a]} for w in WORLDS}
            for w in WORLDS:
                contrasts[f'within__{w}__{a}_minus_{b}'] = {
                    k: paired(v, np.zeros_like(v)) for k, v in delta[w].items()}
            if a.startswith('H_'):
                contrasts[f'interaction__{a}_minus_{b}'] = {
                    k: paired(delta['flash'][k] - delta['blink'][k], np.zeros_like(delta['flash'][k]))
                    for k in delta['flash']}
    return contrasts


def run(parent_pid):
    parent_check(parent_pid)
    protocol = require_release()
    for name in ('measurement', 'startup_identity.json', 'report.json', 'selection.json', 'requests',
                 'monitor_receipts', 'confirmation_genotypes.npz', 'confirmation_roles.json'):
        if (STUDY / name).exists():
            raise ValueError('first attempt refuses existing generated work: ' + name)
    if os.environ.get('CELLDEV_THREADS_FILE'):
        raise ValueError('elastic thread override is forbidden')
    from numerical import check
    check(protocol['numerical_identity'])
    panels, evaluators, worlds = load_panels(protocol)
    seeds, historical = stage_seeds(protocol), historical_rates(protocol)
    import numpy as np
    from scoring import RowStore, atomic_npz, raw_sha

    from src.checkpoint import numerical_identity

    # The only identity invocation: exactly two ABI3 seed11 T200 compatibility lives.
    identity = numerical_identity()
    metadata = {k: v for k, v in identity.items() if k not in ('kernels', 'golden')}
    if identity != protocol['expected_numerical_identity'] or metadata != protocol['expected_startup_metadata']:
        raise ValueError('retained startup numerical/source/golden identity changed')
    save(STUDY / 'startup_identity.json', {'identity': identity, 'preexpected_fields': sorted(identity),
        'newly_captured_fields': [], 'numerical_identity_invocations': 1,
        'golden_lives': {'abi': 3, 'seed': 11, 'T': 200, 'full': 1, 'fast': 1}})
    stores = {f'screen/{p}': RowStore(STUDY / f'measurement/screen/{p}', panels[p], worlds['flash'],
        evaluators['flash'][p], {'protocol_sha256': sha(STUDY / 'protocol.json'), 'background': p, 'world': 'flash'})
        for p in PARENTS}
    report = {'status': 'incomplete', 'scope': SCOPE, 'screen': {}, 'confirmation': {}}
    save(STUDY / 'report.json', report)
    calibration = {p: stores[f'screen/{p}'].stage('calibration', [0, 1], seeds['calibration']) for p in PARENTS}
    receipt = monitor_ack('calibration_complete', {'validation_lives': 10,
        'startup_identity_sha256': sha(STUDY / 'startup_identity.json'),
        'row_index_sha256': {key: sha(store.out / 'row_index.json') for key, store in stores.items()}}, parent_pid)
    projection = calibration_projection(calibration, receipt['cpu_seconds'], historical)
    save(STUDY / 'calibration_projection.json', projection)
    if not projection['feasible']:
        raise RuntimeError('initial_fixed_scope_cost_projection_does_not_fit')
    screens, winners = {}, {}
    for p in PARENTS:
        parent_check(parent_pid)
        screens[p] = stores[f'screen/{p}'].stage('screen', list(range(65)), seeds['screen'])
        chosen = select_winner(screens[p])
        winners[p] = {'genome_row': chosen, 'raw_sha256': raw_sha(panels[p][chosen])}
        report['screen'][p] = {'selected': winners[p], 'complete_rows': 65,
            'row_index_sha256': sha(stores[f'screen/{p}'].out / 'row_index.json')}
        save(STUDY / 'report.json', report)
    save(STUDY / 'selection.json', winners)
    rows = {f'{prefix}_{p}': index for p in PARENTS
            for prefix, index in (('P', 0), ('B', BLINK_ROWS[p]), ('H', winners[p]['genome_row']))}
    table = np.stack([panels[role.split('_')[1]][rows[role]] for role in ROLES])
    atomic_npz(STUDY / 'confirmation_genotypes.npz', genomes=table, roles=np.asarray(ROLES))
    save(STUDY / 'confirmation_roles.json', {'roles': ROLES, 'panel_rows': rows,
        'genotype_sha256': {role: raw_sha(table[i]) for i, role in enumerate(ROLES)},
        'selection_sha256': sha(STUDY / 'selection.json'), 'protocol_sha256': sha(STUDY / 'protocol.json'),
        'genotypes_sha256': sha(STUDY / 'confirmation_genotypes.npz')})
    projection = selected_projection(screens, winners, historical)
    save(STUDY / 'confirmation_projection.json', projection)
    if not projection['feasible']:
        raise RuntimeError('frozen_selected_role_cost_projection_does_not_fit')
    monitor_ack('screens_complete', {'scientific_genome_lives': 4160,
        'selection_sha256': sha(STUDY / 'selection.json'),
        'row_index_sha256': {key: sha(store.out / 'row_index.json') for key, store in stores.items()},
        'confirmation_roles_sha256': sha(STUDY / 'confirmation_roles.json'),
        'confirmation_genotypes_sha256': sha(STUDY / 'confirmation_genotypes.npz')}, parent_pid)
    confirmed = {}
    for w in WORLDS:
        parent_check(parent_pid)
        key = f'confirm/{w}'
        stores[key] = RowStore(STUDY / 'measurement' / key, table, worlds[w], evaluators[w]['D90'],
            {'protocol_sha256': sha(STUDY / 'protocol.json'), 'world': w, 'roles': ROLES,
             'confirmation_roles_sha256': sha(STUDY / 'confirmation_roles.json')})
        confirmed[w] = stores[key].stage('confirm', list(range(6)), seeds['confirm'])
        report['confirmation'][w] = {'complete_roles': ROLES, 'row_index_sha256': sha(stores[key].out / 'row_index.json')}
        save(STUDY / 'report.json', report)
    report.update(status='complete', research_genome_lives=10304, validation_lives=10,
                  total_genome_lives=10314, row_cpu_seconds=sum(store.cpu_seconds for store in stores.values()),
                  row_index_sha256={key: sha(store.out / 'row_index.json') for key, store in stores.items()},
                  contrasts=contrast_reports(confirmed, worlds),
                  limitations=['The two backgrounds are fixed, not independent evolutionary replicates.',
                               'Flash and blink differ in residual cue strength, scheduling and placement resets.',
                               'Capture or world-specific gains do not isolate retained information or memory.'])
    save(STUDY / 'report.json', report)
    return report


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--run', action='store_true')
    parser.add_argument('--monitor-pid', type=int)
    args = parser.parse_args()
    if not args.run:
        print(json.dumps({'status': 'source_only_unregistered', 'scope': SCOPE,
                          'total_genome_lives': 10314, 'simulation_calls': 0, 'genetic_draws': 0,
                          'requires': 'clean AB terminal clearance, root registration, retained inputs and release'}))
        return
    result = run(args.monitor_pid)
    print(json.dumps({'status': result['status'], 'total_genome_lives': result['total_genome_lives']}))


if __name__ == '__main__':
    main()
