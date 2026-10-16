"""Independent saved-data audit. No study/engine imports, builds, simulations or random draws.

Scalar accounting/reducer copied from accepted baseline independent audit source63b3aebd...44d427e4;
duration arithmetic admits the declared T256 engineering cases as well as T1024 science.
"""
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

BASE_PROTOCOL = 'b1b4cbdb2c1d2d7f2e1eeac05d28a8944dc4ed8e0fc3fdd3efc5190d9ded55cc'
PROTOCOL = '435d8439a33cc160ecdc4150e22fd845fb2ff8e31fdc532b570c4c2a568209c1'
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
METRICS += ('rec_cand rec_accept rec_events rec_gain births deaths n_peak '
           'total_patch_stock_open total_patch_stock_end').split()
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
    require(world['t0'] == world['t_open'] == 0 and world['T'] in (256, 1024), 'unexpected full-life world')
    end, duration = row['t_end'], world['T']
    guarded, extinct = bool(status & 6), bool(status & 1)
    require(0 <= end <= duration and (guarded or end == duration), 'invalid endpoint')
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
    guard = world['c_live'] * world['n_max'] * (duration - end) if guarded else 0.
    net = income - physical - guard
    for name, value in [('income', income), ('cost', physical), ('guard_charge', guard), ('net', net),
                        ('F', net / duration)]:
        close(row[name], value, 'native ' + name, 1e-9)
    if extinct:
        require(0 <= row['t_ext'] <= end, 'extinction time')
    extinction_energy = world['c_live'] * (duration - max(row['t_ext'], 0)) if extinct else 0.
    return dict(physical_cost=physical, reconstructed_guard_charge=guard, reconstructed_native_F=net / duration,
                extinction_charge=extinction_energy, production_F=row['F'] - extinction_energy / duration,
                **costs, **{'total_patch_' + name: value for name, value in patch.items()},
                initial_income=world['R_cap'] * patch['initial_harvest'],
                refill_income=world['R_cap'] * patch['refill_harvest'], guard=int(guarded), extinct=int(extinct))


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


def schedule(engineering):
    rows = []

    def add(group, role, mode, world, seed, backend, pair, comparison=None):
        index = len(rows)
        rows.append(dict(index=index, group=group, role=role, row=0 if role == 'AO_rank0' else 1,
                         mode=mode, world=world, seed=seed, backend=backend, pair=pair, comparison=comparison,
                         path=f'raw/{index:03d}_{group}_{mode}_{role}_{seed}_{backend}.npz'))

    for item in engineering:
        add('native_equivalence', item['role'], 'native', item['world'], item['seed'],
            'C_fast' if item['fast'] else 'C_full', item['pair'], item['copied_path'])
    for mode in ('constant1', 'constant055'):
        for role, seed in [('AO_rank0', 42000000), ('AM_reference', 42000001)]:
            for backend in ('C_full', 'C_fast', 'Python'):
                add('constant_parity', role, mode, 'patch256', seed, backend, mode + '_' + role)
    for mode in ('constant1', 'constant055'):
        for role in ('AO_rank0', 'AM_reference'):
            for seed in range(52480000, 52480032):
                add('science', role, mode, 'patch', seed, 'C_fast', None)
    return rows


def load_raw(path, seed_value, protocol_pin, fast):
    import numpy as np

    with np.load(path, allow_pickle=False) as data:
        require(set(data.files) == {'ledger', 'hashes', 'seed', 'protocol_sha256'}, 'raw schema: ' + str(path))
        ledger, hashes, seed = data['ledger'].copy(), data['hashes'].copy(), data['seed']
        require(ledger.shape == (1, 107) and ledger.dtype == np.float64, 'ledger shape/type')
        require(hashes.shape == (1, 5) and hashes.dtype == np.uint64, 'hash shape/type')
        require(seed.shape == (1,) and seed.dtype == np.uint64 and int(seed[0]) == seed_value, 'seed binding')
        require(data['protocol_sha256'].shape == () and data['protocol_sha256'].item() == protocol_pin,
                'raw protocol binding')
    if fast:
        require(all(int(value) == HASH_INIT for value in hashes[0]), 'fast hashes not constants')
    return ledger, hashes


def checked_baseline(protocol):
    import numpy as np

    reuse = read(STUDY / 'inputs/reuse.json')
    require(reuse['status'] == 'deliberate_development_reuse' and not reuse['confirmation_eligible']
            and reuse['newly_reserved_blocks'] == [], 'reuse scope')
    require(reuse['baseline_protocol_sha256'] == BASE_PROTOCOL, 'baseline protocol identity')
    require(sha(STUDY / 'inputs/baseline_protocol.json') == BASE_PROTOCOL, 'copied baseline protocol hash')
    baseline = read(STUDY / 'inputs/baseline_protocol.json')
    complete = read(STUDY / 'inputs/baseline_measurement_complete.json')
    budget = read(STUDY / 'inputs/baseline_budget.json')
    require(complete['status'] == budget['status'] == 'complete', 'incomplete baseline')
    require(complete['protocol_sha256'] == budget['protocol_sha256'] == BASE_PROTOCOL, 'baseline bindings')
    require(complete['backend_calls'] == 456, 'baseline inventory')
    for name in ('row_index', 'summary'):
        require(sha(STUDY / f'inputs/baseline_{name}.json') == complete[name + '_sha256'], 'baseline ' + name)
    baseline_index = read(STUDY / 'inputs/baseline_row_index.json')
    archive = ROOT / 'results/resource_patch_baseline_20261015'
    require(sha(archive / 'manifest.json') == reuse['baseline_manifest_sha256'], 'published baseline manifest')
    manifest = read(archive / 'manifest.json')['artifacts']
    for name in ('protocol', 'measurement_complete', 'budget', 'row_index', 'summary'):
        copied = STUDY / f'inputs/baseline_{name}.json'
        require(sha(copied) == manifest[name + '.json']['sha256'], 'baseline archive linkage: ' + name)
    selected = [item for item in baseline['schedule'] if item['group'] == 'engineering' or
                (item['group'] == 'reference' and item['world'] == 'patch')]
    declared = reuse['engineering_rows'] + reuse['native_rows']
    require(len(selected) == len(declared) == 72, 'reuse72-row inventory')
    native = {}
    for item, copied in zip(selected, declared, strict=True):
        require(all(copied[key] == value for key, value in item.items()), 'reuse schedule linkage')
        expected_copy = 'inputs/baseline_rows/' + Path(item['path']).name
        expected_public = 'results/resource_patch_baseline_20261015/' + item['path']
        require(copied['copied_path'] == expected_copy and copied['baseline_public_path'] == expected_public,
                'reuse copied/original path')
        path = STUDY / expected_copy
        digest = sha(path)
        require(digest == copied['sha256'] == baseline_index[item['path']]['sha256']
                == manifest[item['path']]['sha256'], 'reused native hash')
        ledger, hashes = load_raw(path, item['seed'], BASE_PROTOCOL, item['fast'])
        account(dict(zip(COLUMNS, map(float, ledger[0]), strict=True)), baseline['worlds'][item['world']]['world'])
        native[expected_copy] = (ledger, hashes)
    require({str(path.relative_to(STUDY)) for path in (STUDY / 'inputs/baseline_rows').glob('*.npz')}
            == set(native), 'copied baseline file inventory')
    require(len(reuse['native_rows']) == 64 and len(reuse['engineering_rows']) == 8, 'reuse split')
    require(protocol['seeds'] == reuse['seeds'] == list(range(52480000, 52480032)), 'development seed identities')
    for name in ('patch', 'pool', 'persistent'):
        require(protocol['worlds'][name] == baseline['worlds'][name], 'native world changed')
    shorter = json.loads(json.dumps(protocol['worlds']['patch']))
    shorter['world']['T'] = shorter['vector'][0] = 256
    require(protocol['worlds']['patch256'] == shorter, 'engineering duration-only world')
    require(protocol['production_pins'] == baseline['production_pins'], 'production changed since baseline')
    for name, dtype in [('raw_genomes.npy', np.float32), ('packed_genomes.npy', np.float64)]:
        prior_path = archive / 'inputs' / name
        require(sha(prior_path) == baseline['input_pins']['inputs/' + name]
                == manifest['inputs/' + name]['sha256'], 'baseline genotype file')
        original = np.load(prior_path, allow_pickle=False)
        current = np.load(STUDY / 'inputs' / name, allow_pickle=False)
        require(current.dtype == dtype and current.shape == (2, 875), 'new fixed genotype table')
        require(current.tobytes() == original[[0, 32]].tobytes(), 'fixed AO/AM genotype bytes')
    return reuse, native


def record(item, ledger, origin, protocol):
    native = dict(zip(COLUMNS, map(float, ledger[0]), strict=True))
    computed = account(native, protocol['worlds'][item['world']]['world'])
    metadata = {key: item[key] for key in ('group', 'role', 'mode', 'world', 'seed', 'backend', 'path')}
    # Native 'path' is traveled distance; the raw filename remains in the index rather than this CSV column.
    return metadata | dict(origin=origin) | native | computed


def audit():
    require(PROTOCOL is not None and sha(STUDY / 'protocol.json') == PROTOCOL, 'final reviewed protocol required')
    require(len(COLUMNS) == 107 and len(METRICS) == 43, 'independent schema')
    protocol = read(STUDY / 'protocol.json')
    complete, budget = read(STUDY / 'measurement_complete.json'), read(STUDY / 'budget.json')
    require(complete['status'] == budget['status'] == 'complete', 'terminal data not ready')
    require(complete['protocol_sha256'] == budget['protocol_sha256'] == PROTOCOL, 'terminal protocol linkage')
    require(complete['backend_calls'] == 148 and complete['scientific_lives'] == 128
            and complete['engineering_lives'] == 20 and complete['startup_lives'] == 0
            and complete['reused_native_scientific_lives'] == 64, 'complete call inventory')
    require(not budget['running'] and not budget['queued'], 'owned work remains')
    cleanup = budget['terminal_cleanup']
    require(cleanup['all_owned_groups_exited'] and cleanup['all_worker_identities_exited']
            and not cleanup['remaining_descendants'], 'cleanup incomplete')
    for category, base in [('source_pins', STUDY), ('input_pins', STUDY), ('production_pins', ROOT)]:
        for name, digest in protocol[category].items():
            archived = STUDY / 'production' / name if category == 'production_pins' else base / name
            path = archived if archived.is_file() else base / name
            require(sha(path) == digest, 'pinned input differs: ' + name)
    for name, key in [('row_index.json', 'row_index_sha256'), ('summary.json', 'summary_sha256'),
                      ('per_life.csv', 'per_life_sha256')]:
        require(sha(STUDY / name) == complete[key], 'complete artifact linkage: ' + name)
    reuse, old = checked_baseline(protocol)
    rows = schedule(reuse['engineering_rows'])
    require(rows == protocol['schedule'] and len(rows) == 148, 'independent new-call schedule')
    require(dict(Counter(row['backend'] for row in rows)) == {'C_full': 8, 'C_fast': 136, 'Python': 4},
            'backend inventory')
    index = read(STUDY / 'row_index.json')
    require(set(index) == {r['path'] for r in rows}, 'new raw index coverage')
    require({str(p.relative_to(STUDY)) for p in (STUDY / 'raw').rglob('*.npz')} == set(index), 'new raw files')
    records, parity, native_checks = [], {}, []
    for item in rows:
        path, pin = STUDY / item['path'], index[item['path']]
        require(sha(path) == pin['sha256'] and all(pin[key] == value for key, value in item.items()),
                'new raw row linkage: ' + item['path'])
        ledger, hashes = load_raw(path, item['seed'], PROTOCOL, item['backend'] == 'C_fast')
        records.append(record(item, ledger, 'new', protocol))
        if item['group'] == 'native_equivalence':
            before_ledger, before_hashes = old[item['comparison']]
            require(ledger.tobytes() == before_ledger.tobytes() and hashes.tobytes() == before_hashes.tobytes(),
                    'native hook is not byte-identical')
            native_checks.append(dict(index=item['index'], identical=True))
        elif item['group'] == 'constant_parity':
            parity.setdefault(item['pair'], {})[item['backend']] = (ledger.tobytes(), hashes.tobytes())
    parity_checks = []
    for pair, values in parity.items():
        require(set(values) == {'C_full', 'C_fast', 'Python'}, 'three parity backends required')
        require(values['C_full'][0] == values['C_fast'][0] == values['Python'][0], 'constant ledger parity')
        require(values['C_full'][1] == values['Python'][1], 'constant full hash parity')
        parity_checks.append(dict(pair=pair, identical=True))
    require(len(native_checks) == 8 and len(parity_checks) == 4, 'engineering check inventory')
    for item in reuse['native_rows']:
        fields = dict(group='science', role=item['role'], mode='native', world='patch', seed=item['seed'],
                      backend='C_fast', path=item['copied_path'])
        records.append(record(fields, old[item['copied_path']][0], 'reused_baseline', protocol))
    require(len(records) == 212, 'combined CSV rows')
    with (STUDY / 'per_life.csv').open(newline='') as stream:
        reader = csv.DictReader(stream)
        require(set(reader.fieldnames) == set(records[0]), 'CSV column coverage')
        csv_rows = list(reader)
    require(len(csv_rows) == 212, 'CSV row count')
    csv_numbers = 0
    for saved, expected in zip(csv_rows, records, strict=True):
        for key, value in expected.items():
            if key in COLUMNS:
                require(struct.pack('<d', float(saved[key])) == struct.pack('<d', value), 'CSV native bits: ' + key)
                csv_numbers += 1
            elif isinstance(value, str):
                require(saved[key] == value, 'CSV metadata: ' + key)
            else:
                close(float(saved[key]), value, 'CSV ' + key)
                csv_numbers += 1
    science = [row for row in records if row['group'] == 'science']
    require(len(science) == 192, 'combined scientific rows')
    groups, paired = {}, {}
    for role in ('AO_rank0', 'AM_reference'):
        groups[role], paired[role], selected = {}, {}, {}
        for mode in ('native', 'constant1', 'constant055'):
            group = [row for row in science if row['role'] == role and row['mode'] == mode]
            require(sorted(row['seed'] for row in group) == list(range(52480000, 52480032)), 'paired32-row panel')
            selected[mode] = {row['seed']: row for row in group}
            groups[role][mode] = {name: moments(row[name] for row in group) for name in METRICS}
        for mode in ('constant1', 'constant055'):
            paired[role]['native_minus_' + mode] = {
                name: moments(selected['native'][seed][name] - selected[mode][seed][name]
                              for seed in range(52480000, 52480032)) for name in METRICS}
    expected = dict(status='complete', valid=True, protocol_sha256=PROTOCOL,
        row_index_sha256=sha(STUDY / 'row_index.json'), new_backend_calls=148, new_scientific_lives=128,
        new_engineering_lives=20, reused_scientific_lives=64, combined_scientific_rows=192,
        new_native_ledger_values=148 * 107, new_native_hash_values=148 * 5,
        status_counts=dict(Counter(str(int(row['status'])) for row in records)), engineering_checks_passed=True,
        native_equivalence=native_checks, constant_parity=parity_checks, groups=groups,
        paired_native_minus_constant=paired, interpretation=protocol['interpretation'])
    numeric = compare_tree(expected, read(STUDY / 'summary.json'))
    return dict(status='passed', protocol_sha256=PROTOCOL, baseline_protocol_sha256=BASE_PROTOCOL,
                new_rows=148, reused_scientific_rows=64, reused_engineering_rows=8, unique_raw_rows_audited=220,
                csv_rows=212, scientific_rows=192, new_native_ledger_values=148 * 107,
                combined_csv_native_ledger_values=212 * 107, raw_native_hash_words=220 * 5,
                native_hook_identical_checks=8, full_fast_Python_triples=4,
                csv_numeric_values_checked=csv_numbers, summary_numeric_values_checked=numeric,
                groups=6, paired_groups=4, metrics_per_group=len(METRICS),
                source_stock_FIFO_cost_extinction_accounting=True, csv_native_float_bits_exact=True,
                reducer='Independent math.fsum scalar mean and centered second moment; paired whole-life SE.',
                reconciliation=dict(native_relative_tolerance=1e-9, derived_summary_relative_tolerance=2e-12),
                limitations=['Full hashes are compared/integrity-checked, not regenerated without simulation.',
                             'Explicit baseline seed reuse is development evidence, not fresh confirmation.',
                             'Whole-life modulation changes can affect development and signal strength.'],
                artifacts={name: sha(STUDY / name) for name in ('protocol.json', 'inputs/reuse.json',
                           'row_index.json', 'summary.json', 'per_life.csv',
                           'measurement_complete.json', 'budget.json')})


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

