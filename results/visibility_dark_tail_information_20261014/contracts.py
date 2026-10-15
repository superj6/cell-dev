"""Pure AD constants and transformations; no source-engine imports or random draws."""
from __future__ import annotations

import copy
import math

ROLES = ['R0', 'R1', 'I', 'A', 'B', *[f'D{i}' for i in range(8)]]
WORLD = 'flash5_dark'
SCOPE = {'total_cpu_seconds': 2400, 'validation_cpu_seconds': 180,
         'max_workers': 1, 'threads_per_worker': 2, 'research_lives': 6656,
         'validation_lives': 76, 'worlds': [WORLD], 'roles': ROLES}
VALIDATION_MATRIX = {'production_bridge': 8, 'full_fast': 12, 'callback_replay': 15,
                     'calibration': 39, 'identity': 2}


def transfer_candidates(original):
    """Match the declared physical amplitude; keep strategy, bodies and all other knobs."""
    if [row['role'] for row in original] != ROLES:
        raise ValueError('the exact thirteen retained candidates are required')
    result = copy.deepcopy(original)
    changes = {}
    for old, row in zip(original, result):
        role = row['role']
        if role in ('I', 'B'):
            if len(row['params']) != 30 or row['params'][21] != .25:
                raise ValueError('unexpected retained physical-description parameter')
            row['params'][21] = 0.
            changes[role] = {'original_parameters': old['params'], 'parameters': row['params'],
                             'changed_parameter_indices': [21],
                             'reason': 'match the declared target dark-rate multiplier'}
        elif role == 'A':
            if row['params'][21] != 0 or row['changed_parameter_indices'] != [9, 10, 21]:
                raise ValueError('unexpected retained broad ablation')
            row['changed_parameter_indices'] = [9, 10]
    return result, changes


def stage_seeds(registration):
    seeds = registration['seeds']
    if set(seeds) != {'validation', 'research'}:
        raise ValueError('exact validation/research seed groups required')
    for name, count in [('validation', 3), ('research', 512)]:
        values = seeds[name]
        if (len(values) != count or len(set(values)) != count
                or any(type(x) is not int or not 0 <= x < 2**64 for x in values)):
            raise ValueError('invalid fixed stage seeds')
    if set(seeds['validation']) & set(seeds['research']) or 11 in sum(seeds.values(), []):
        raise ValueError('scientific namespaces overlap; golden seed 11 is engineering-only')
    return seeds


def calibration_projection(calibration_cpu_seconds, historical_cpu_per_life):
    """Three-life batch CPU includes both worker threads; old roles provide a cost floor."""
    if set(calibration_cpu_seconds) != set(ROLES) or set(historical_cpu_per_life) != set(ROLES):
        raise ValueError('all thirteen roles must enter the fixed cost gate')
    rates = {}
    for role in ROLES:
        cpu, old = calibration_cpu_seconds[role], historical_cpu_per_life[role]
        if any(type(x) not in (int, float) or not math.isfinite(x) or x <= 0 for x in (cpu, old)):
            raise ValueError('finite positive calibration and historical CPU required')
        rates[role] = max(cpu / 3, old)
    projected = 180 + 1.5 * 512 * sum(rates.values())
    return {'cpu_per_life': rates, 'validation_allowance_cpu_seconds': 180,
            'multiplier': 1.5, 'projected_total_cpu_seconds': projected,
            'threshold_cpu_seconds': 2390, 'feasible': projected <= 2390,
            'interpretation': 'cost feasibility estimate; the monitor enforces the hard cap'}
