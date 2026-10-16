"""Independent saved-data audit. No study/engine imports, builds, simulations or random draws."""
from __future__ import annotations

import argparse
import csv
import hashlib
import json
import math
import resource
import struct
import time
from collections import Counter
from pathlib import Path

PROTOCOL = 'b1b4cbdb2c1d2d7f2e1eeac05d28a8944dc4ed8e0fc3fdd3efc5190d9ded55cc'
HERE = Path(__file__).resolve().parent
STUDY = HERE.parent
ROOT = STUDY.parents[1]
BASE = (
    'income live_time sec_int spikes kappa_sum contact_events claims births rejects rejects_wall deaths kills '
    'cost guard_charge net F n_end n_peak t_end status events beats P_int arrivals arrivals_dropped packets '
    'morph_secreted morph_decayed morph_lost morph_content_end morph_inflight_end chem_clamps last_birth ticks t_ext '
    'captures misses clicks b2_clicks respawns nudges rec_cand rec_accept rec_events rec_gain samples dist_sum '
    'zone_samples path X_end Y_end n_S_end n_M_end n_H_end live_S live_M live_H low_light_captures'
).split()
TASK = [f'{name}_{kind}' for name in ('choice_opportunities', 'choice_carry_in', 'correct_choices',
        'wrong_choices', 'choice_timeouts', 'unfinished_choices') for kind in ('narrow', 'broad')]
PATCH = ('stock_open', 'source', 'supply', 'spill', 'harvest', 'empty', 'stock_end',
         'initial_harvest', 'refill_harvest')
PATCH_COLUMNS = [f'patch_{name}_{i}' for name in PATCH[:7] for i in range(4)]
PATCH_COLUMNS += ['patch_geometric_misses'] + [f'patch_{name}_{i}' for name in PATCH[7:] for i in range(4)]
COLUMNS = BASE + TASK + PATCH_COLUMNS
METRICS = (
    'production_F F captures misses clicks income physical_cost guard_charge extinction_charge initial_income '
    'refill_income total_patch_initial_harvest total_patch_refill_harvest total_patch_source total_patch_supply '
    'total_patch_spill total_patch_empty patch_geometric_misses path live_time n_end n_S_end n_M_end n_H_end '
    'cost_maintenance cost_spikes cost_motor cost_messages cost_division_claims cost_secretion cost_misses '
    'cost_receptors guard extinct'
).split()
COUNTS = (
    'spikes contact_events claims births rejects rejects_wall deaths kills n_end n_peak status events beats '
    'arrivals arrivals_dropped packets chem_clamps ticks captures misses clicks b2_clicks respawns nudges '
    'rec_cand rec_accept rec_events samples zone_samples n_S_end n_M_end n_H_end low_light_captures'
).split() + TASK + PATCH_COLUMNS
HASH_INIT = 0x243F6A8885A308D3


def read(path):
    return json.loads(path.read_text())


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def require(condition, message):
    if not condition:
        raise ValueError(message)


def close(actual, expected, label, tolerance=2e-12):
    require(math.isfinite(actual) and math.isfinite(expected), 'nonfinite ' + label)
    require(abs(actual - expected) <= tolerance * max(1., abs(expected)), 'numerical mismatch: ' + label)


def moments(values):
    # Independent scalar, compensated reducer; no producer or NumPy statistics code.
    values = [float(value) for value in values]
    count = len(values)
    require(count > 0, 'empty moment group')
    mean = math.fsum(values) / count
    squared = math.fsum((value - mean) ** 2 for value in values)
    return dict(n=count, mean=mean, se=math.sqrt(squared / (count * (count - 1))) if count > 1 else None,
                minimum=min(values), maximum=max(values))


def account(row, world):
    require(all(math.isfinite(value) for value in row.values()), 'nonfinite native ledger')
    for name in COUNTS:
        require(row[name] >= 0 and row[name].is_integer(), 'invalid event count: ' + name)
    status = int(row['status'])
    require(status & ~511 == 0, 'unknown status bits')
    require(status & (8 | 16 | 64 | 128) == 0, 'corrupt native return')
    require(row['b2_clicks'] == 0 and all(row[name] == 0 for name in TASK), 'unexpected other-task counts')
    require(row['clicks'] == row['captures'] + row['misses'], 'click conservation')
    require(row['n_S_end'] + row['n_M_end'] + row['n_H_end'] == row['n_end'], 'plane counts')
    require(world['t0'] == world['t_open'] == 0 and world['T'] == 1024, 'unexpected full-life world')
    end = row['t_end']
    guarded, extinct = bool(status & 6), bool(status & 1)
    require(0 <= end <= 1024 and (guarded or end == 1024), 'invalid endpoint')
    patch = {name: 0. for name in PATCH}
    if world['patch_count'] and end > 0:
        for i in range(4):
            values = {name: row[f'patch_{name}_{i}'] for name in PATCH}
            if i >= world['patch_count']:
                require(not any(values.values()), 'inactive patch nonzero')
                continue
            capacity = world['patch_capacity']
            require(values['stock_open'] == capacity, 'full-life opening stock')
            require(0 <= values['stock_end'] <= capacity, 'closing stock bound')
            require(values['source'] == values['supply'] + values['spill'], 'source conservation')
            require(capacity + values['supply'] == values['harvest'] + values['stock_end'], 'stock conservation')
            require(capacity + values['source'] == values['harvest'] + values['spill'] + values['stock_end'],
                    'offered-resource conservation')
            require(values['harvest'] == values['initial_harvest'] + values['refill_harvest'], 'origin sum')
            require(values['initial_harvest'] == min(capacity, values['harvest']), 'FIFO initial provenance')
            require(values['refill_harvest'] <= values['supply'], 'refill cannot exceed admitted supply')
            for name in PATCH:
                patch[name] += values[name]
        require(row['captures'] == patch['harvest'], 'patch/native harvest mismatch')
        require(row['misses'] == patch['empty'] + row['patch_geometric_misses'], 'patch/native miss mismatch')
        require(row['respawns'] == row['low_light_captures'] == 0, 'inapplicable patch count')
    else:
        require(all(row[name] == 0 for name in PATCH_COLUMNS), 'neutral/empty-window patch ledger')
    costs = {}
    for name, price, count in (
        ('maintenance', 'c_live', 'live_time'), ('spikes', 'c_spike', 'spikes'),
        ('motor', 'c_tw', 'kappa_sum'), ('messages', 'c_msg', 'contact_events'),
        ('division_claims', 'c_div', 'claims'), ('secretion', 'c_sec', 'sec_int'),
        ('misses', 'c_miss', 'misses'), ('receptors', 'c_rec', 'rec_gain'),
    ):
        costs['cost_' + name] = world[price] * row[count]
    physical = math.fsum(costs.values())
    income = world['R_cap'] * row['captures']
    guard = world['c_live'] * world['n_max'] * (1024 - end) if guarded else 0.
    net = income - physical - guard
    for name, value in [('income', income), ('cost', physical), ('guard_charge', guard), ('net', net),
                        ('F', net / 1024)]:
        close(row[name], value, 'native ' + name, 1e-9)
    if extinct:
        require(0 <= row['t_ext'] <= end, 'extinction time')
    extinction_energy = world['c_live'] * (1024 - max(row['t_ext'], 0)) if extinct else 0.
    return dict(physical_cost=physical, reconstructed_guard_charge=guard, reconstructed_native_F=net / 1024,
                extinction_charge=extinction_energy, production_F=row['F'] - extinction_energy / 1024,
                **costs, **{'total_patch_' + name: value for name, value in patch.items()},
                initial_income=world['R_cap'] * patch['initial_harvest'],
                refill_income=world['R_cap'] * patch['refill_harvest'], guard=int(guarded), extinct=int(extinct))


def schedule():
    rows = []

    def add(group, role, row, world, seed, fast, pair=None):
        index = len(rows)
        rows.append(dict(index=index, group=group, role=role, row=row, world=world, seed=seed, fast=fast,
                         pair=pair, path=f'raw/{index:04d}_{group}_{world}_{role}_{seed}.npz'))

    for pair, (role, row, world, seed) in enumerate([
        ('AO_rank0', 0, 'patch', 42000000), ('AM_reference', 32, 'patch', 42000001),
        ('AO_rank0', 0, 'pool', 42000002), ('AM_reference', 32, 'persistent', 42000003),
    ]):
        for fast in (False, True):
            add('engineering', role, row, world, seed, fast, pair)
    for row in range(32):
        for seed in range(52470000, 52470008):
            add('population', f'row{row:02d}', row, 'patch', seed, True)
    for world in ('patch', 'pool', 'persistent'):
        for role, row in [('AO_rank0', 0), ('AM_reference', 32)]:
            for seed in range(52480000, 52480032):
                add('reference', role, row, world, seed, True)
    return rows


def compare_tree(expected, actual, path='summary'):
    if isinstance(expected, dict):
        require(isinstance(actual, dict) and set(expected) == set(actual), 'keys differ: ' + path)
        return sum(compare_tree(value, actual[key], path + '/' + str(key)) for key, value in expected.items())
    if isinstance(expected, list):
        require(isinstance(actual, list) and len(expected) == len(actual), 'list differs: ' + path)
        return sum(compare_tree(value, actual[i], path + '/' + str(i)) for i, value in enumerate(expected))
    if isinstance(expected, bool) or expected is None or isinstance(expected, str):
        require(type(expected) is type(actual) and actual == expected, 'value differs: ' + path)
        return 0
    if isinstance(expected, int):
        require(type(actual) is int and actual == expected, 'integer differs: ' + path)
    else:
        close(actual, expected, path)
    return 1


def audit():
    import numpy as np

    require(len(COLUMNS) == 107 and len(set(COLUMNS)) == 107, 'independent ABI schema')
    require(sha(STUDY / 'protocol.json') == PROTOCOL, 'frozen protocol hash')
    protocol = read(STUDY / 'protocol.json')
    complete, budget = read(STUDY / 'measurement_complete.json'), read(STUDY / 'budget.json')
    require(complete['status'] == budget['status'] == 'complete', 'terminal data not ready')
    require(complete['protocol_sha256'] == budget['protocol_sha256'] == PROTOCOL, 'terminal protocol binding')
    require(complete['backend_calls'] == 456 and complete['scientific_lives'] == 448
            and complete['engineering_lives'] == 8 and complete['startup_lives'] == 0, 'complete call inventory')
    require(not budget['running'] and not budget['queued'], 'owned work remains')
    cleanup = budget['terminal_cleanup']
    require(cleanup['all_owned_groups_exited'] and cleanup['all_worker_identities_exited']
            and not cleanup['remaining_descendants'], 'cleanup incomplete')
    for category, base in [('source_pins', STUDY), ('input_pins', STUDY), ('production_pins', ROOT)]:
        for name, digest in protocol[category].items():
            local = STUDY / 'production' / name if category == 'production_pins' else base / name
            path = local if local.is_file() else base / name
            require(sha(path) == digest, 'pinned input differs: ' + name)
    for name, key in [('row_index.json', 'row_index_sha256'), ('summary.json', 'summary_sha256'),
                      ('per_life.csv', 'per_life_sha256')]:
        require(sha(STUDY / name) == complete[key], 'complete artifact binding: ' + name)
    rows = schedule()
    require(rows == protocol['schedule'] == read(STUDY / 'inputs/schedule.json'), 'declared456-call schedule')
    index = read(STUDY / 'row_index.json')
    require(set(index) == {r['path'] for r in rows}, 'raw index coverage')
    require({str(p.relative_to(STUDY)) for p in (STUDY / 'raw').rglob('*.npz')} == set(index), 'raw files coverage')
    records, pairs = [], {}
    for item in rows:
        path = STUDY / item['path']
        require(sha(path) == index[item['path']]['sha256'], 'raw digest: ' + item['path'])
        require(all(index[item['path']][key] == value for key, value in item.items()), 'index row binding')
        with np.load(path, allow_pickle=False) as data:
            require(set(data.files) == {'ledger', 'hashes', 'seed', 'protocol_sha256'}, 'raw schema')
            ledger, hashes, seed = data['ledger'], data['hashes'], data['seed']
            require(ledger.shape == (1, 107) and ledger.dtype == np.float64, 'ledger shape/type')
            require(hashes.shape == (1, 5) and hashes.dtype == np.uint64, 'hash shape/type')
            require(seed.shape == (1,) and seed.dtype == np.uint64 and int(seed[0]) == item['seed'], 'seed binding')
            require(data['protocol_sha256'].shape == () and data['protocol_sha256'].item() == PROTOCOL,
                    'raw protocol binding')
            if item['fast']:
                require(all(int(value) == HASH_INIT for value in hashes[0]), 'fast hashes not constants')
            native = dict(zip(COLUMNS, map(float, ledger[0]), strict=True))
            computed = account(native, protocol['worlds'][item['world']]['world'])
            records.append(item | native | computed)
            if item['group'] == 'engineering':
                pairs.setdefault(item['pair'], {})[item['fast']] = ledger.tobytes()
    require(len(pairs) == 4 and all(pair[False] == pair[True] for pair in pairs.values()), 'full/fast ledger parity')
    with (STUDY / 'per_life.csv').open(newline='') as stream:
        reader = csv.DictReader(stream)
        require(set(reader.fieldnames) == set(records[0]), 'CSV column coverage')
        csv_rows = list(reader)
    require(len(csv_rows) == 456, 'CSV row count')
    csv_numbers = 0
    for saved, record in zip(csv_rows, records, strict=True):
        for key, value in record.items():
            if key in COLUMNS:
                require(struct.pack('<d', float(saved[key])) == struct.pack('<d', value), 'CSV native bits: ' + key)
                csv_numbers += 1
            elif isinstance(value, bool) or value is None or isinstance(value, str):
                require(saved[key] == ('' if value is None else str(value)), 'CSV metadata: ' + key)
            else:
                close(float(saved[key]), value, 'CSV ' + key)
                csv_numbers += 1
    population = []
    for row in range(32):
        group = [r for r in records if r['group'] == 'population' and r['row'] == row]
        require(len(group) == 8, 'population coverage')
        population.append(dict(row=row, ancestral_id=protocol['population_ids'][row],
                               metrics={name: moments(r[name] for r in group) for name in METRICS}))
    references, contrasts = {}, {}
    for world in ('patch', 'pool', 'persistent'):
        references[world], selected = {}, {}
        for role in ('AO_rank0', 'AM_reference'):
            group = [r for r in records if r['group'] == 'reference' and r['role'] == role and r['world'] == world]
            require(len(group) == 32, 'reference coverage')
            selected[role] = {r['seed']: r for r in group}
            references[world][role] = {name: moments(r[name] for r in group) for name in METRICS}
        require(set(selected['AO_rank0']) == set(selected['AM_reference']), 'pairing mismatch')
        contrasts[world] = {name: moments(selected['AO_rank0'][seed][name] - selected['AM_reference'][seed][name]
                                        for seed in sorted(selected['AO_rank0'])) for name in METRICS}
    expected = dict(status='complete', valid=True, protocol_sha256=PROTOCOL,
        row_index_sha256=sha(STUDY / 'row_index.json'), native_rows=456, native_ledger_values=456 * 107,
        native_hash_values=456 * 5, scientific_lives=448, engineering_lives=8, full_fast_ledgers_identical=True,
        status_counts=dict(Counter(str(int(row['status'])) for row in records)), population_rows=population,
        population_row_mean_distribution={name: moments(row['metrics'][name]['mean'] for row in population)
                                          for name in METRICS}, references=references, paired_AO_minus_AM=contrasts,
        interpretation=protocol['interpretation'],
        population_uncertainty=('Eight shared seeds per row; row distribution is descriptive, '
                                'not32 independent search replicates.'),
        source_contribution=('Initial/refill FIFO income is observed-trajectory accounting, '
                             'not a source-off experiment.'))
    numeric = compare_tree(expected, read(STUDY / 'summary.json'))
    return dict(status='passed', protocol_sha256=PROTOCOL, audited_rows=456, scientific_rows=448,
                engineering_rows=8, full_fast_pairs=4, native_ledger_values=456 * 107, native_hash_values=456 * 5,
                csv_numeric_values_checked=csv_numbers, summary_numeric_values_checked=numeric,
                population_rows=32, metrics_per_group=len(METRICS), reference_groups=6, paired_groups=3,
                source_stock_FIFO_cost_extinction_accounting=True, csv_native_float_bits_exact=True,
                reducer='Independent math.fsum scalar mean and centered second moment; SE clusters by whole life.',
                reconciliation=dict(native_relative_tolerance=1e-9, derived_summary_relative_tolerance=2e-12),
                limitations=['Full native hashes are integrity-checked, not regenerated without simulation.',
                             'FIFO origin accounting cannot establish switching, revisits or memory.'],
                artifacts={name: sha(STUDY / name) for name in ('protocol.json', 'row_index.json', 'summary.json',
                           'per_life.csv', 'measurement_complete.json', 'budget.json')})


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--saved-data-only', action='store_true')
    args = parser.parse_args()
    if not args.saved_data_only:
        parser.print_help()
        return
    output = HERE / 'independent_accounting.json'
    require(not output.exists(), 'preserve existing audit receipt; no silent overwrite')
    started, cpu = time.monotonic(), time.process_time()
    error = None
    try:
        result = audit()
    except Exception as failure:
        error = failure
        result = dict(status='failed', error=f'{type(failure).__name__}: {failure}', protocol_sha256=PROTOCOL)
    result.update(audit_source_sha256=sha(Path(__file__)), simulations=0, builds=0, random_draws=0,
                  resources=dict(cpu_seconds=time.process_time() - cpu, wall_seconds=time.monotonic() - started,
                                 max_rss_kib=resource.getrusage(resource.RUSAGE_SELF).ru_maxrss))
    with output.open('x') as stream:
        json.dump(result, stream, indent=2, allow_nan=False)
        stream.write('\n')
    print(json.dumps(result, indent=2))
    if error is not None:
        raise SystemExit(1)


if __name__ == '__main__':
    main()
