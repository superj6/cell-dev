"""Saved-native-row accounting and paired summaries; never build or simulate."""
from __future__ import annotations

import argparse
import csv
import sys

from common import ROOT, STUDY, checked_protocol, read, save, sha

sys.dont_write_bytecode = True
sys.path.insert(0, str(ROOT))


def moments(values):
    import numpy as np
    values = np.asarray(values, dtype=np.float64)
    return dict(n=len(values), mean=float(values.mean()),
        se=float(values.std(ddof=1) / len(values)**.5) if len(values) > 1 else None,
        minimum=float(values.min()), maximum=float(values.max()))


def validate_life(ledger, world):
    import numpy as np

    from src.life import spec

    abi = spec.V6
    if ledger.dtype != np.float64 or ledger.shape != (1, 107) or not np.isfinite(ledger).all():
        raise ValueError('native ledger shape/dtype/finiteness')
    row = ledger[0]
    def get(key):
        return float(row[abi.L[key]])
    known = sum(spec.STATUS.values())
    status = get('status')
    if status < 0 or status != int(status) or int(status) & ~known:
        raise ValueError('unknown or noninteger native status')
    status = int(status)
    forbidden = sum(spec.STATUS[x] for x in ('capacity', 'ledger_mismatch', 'raster_overflow', 'fate_overflow'))
    if status & forbidden:
        raise ValueError('capacity/accounting/log corruption; raw row retained')
    counts = ('captures', 'misses', 'clicks', 'b2_clicks', 'respawns', 'births', 'deaths', 'claims', 'spikes',
              'contact_events', 'n_end', 'n_peak', 'rec_cand', 'rec_accept', 'rec_events') + spec.PATCH_LEDGER
    if any(get(key) < 0 or get(key) != int(get(key)) for key in counts):
        raise ValueError('negative or fractional native event count')
    if get('clicks') != get('captures') + get('misses') + get('b2_clicks'):
        raise ValueError('click conservation')
    if get('b2_clicks') != 0 or any(get(k) != 0 for k in spec.TASK_LEDGER):
        raise ValueError('unexpected second-blob or matching event')
    patch = {metric: 0 for metric in (*spec.PATCH_METRICS, 'initial_harvest', 'refill_harvest')}
    if world.patch_count:
        for i in range(4):
            values = {name: get(f'patch_{name}_{i}') for name in patch}
            if i >= world.patch_count and any(values.values()):
                raise ValueError('inactive patch counters')
            if i < world.patch_count:
                if not 0 <= values['stock_open'] <= world.patch_capacity or not 0 <= values['stock_end'] <= world.patch_capacity:
                    raise ValueError('stock bounds')
                if values['source'] != values['supply'] + values['spill']:
                    raise ValueError('source conservation')
                if values['stock_open'] + values['supply'] != values['harvest'] + values['stock_end']:
                    raise ValueError('stock conservation')
                if values['harvest'] != values['initial_harvest'] + values['refill_harvest']:
                    raise ValueError('FIFO harvest decomposition')
                if values['initial_harvest'] > world.patch_capacity or values['refill_harvest'] > values['supply']:
                    raise ValueError('full-life origin bounds')
            for name in patch:
                patch[name] += values[name]
        if (patch['harvest'] != get('captures') or
                patch['empty'] + get('patch_geometric_misses') != get('misses') or
                get('respawns') != 0 or get('low_light_captures') != 0):
            raise ValueError('patch/native outcome disagreement')
    elif any(get(key) != 0 for key in spec.PATCH_LEDGER):
        raise ValueError('neutral worlds must have zero patch ledger')
    costs = dict(maintenance=world.c_live * get('live_time'), spikes=world.c_spike * get('spikes'),
        motor=world.c_tw * get('kappa_sum'), messages=world.c_msg * get('contact_events'),
        division_claims=world.c_div * get('claims'), secretion=world.c_sec * get('sec_int'),
        misses=world.c_miss * get('misses'), receptors=world.c_rec * get('rec_gain'))
    physical = sum(costs.values())
    income = world.R_cap * get('captures')
    guards = spec.STATUS['guard_cells'] | spec.STATUS['guard_events']
    endpoint = get('t_end')
    if not world.t0 <= endpoint <= world.t0 + world.T or (not status & guards and endpoint != world.t0 + world.T):
        raise ValueError('unexpected actual endpoint')
    guard = world.c_live * world.n_max * (world.t0 + world.T - endpoint) if status & guards else 0.0
    net = income - physical - guard
    native_F = net / (world.T - world.t_open)
    for key, expected in (('income', income), ('cost', physical), ('guard_charge', guard), ('net', net), ('F', native_F)):
        if abs(get(key) - expected) > 1e-9 * max(1., abs(expected)):
            raise ValueError('native numerical accounting mismatch: ' + key)
    extinct = bool(status & spec.STATUS['extinct'])
    if extinct and not world.t0 <= get('t_ext') <= endpoint:
        raise ValueError('extinction timestamp outside actual life')
    extinction_energy = (world.c_live * (world.t0 + world.T - max(get('t_ext'), world.t0 + world.t_open))
                         if extinct else 0.0)
    if extinction_energy < 0:
        raise ValueError('extinction timestamp after endpoint')
    production_F = get('F') - extinction_energy / (world.T - world.t_open)
    return dict(physical_cost=physical, reconstructed_guard_charge=guard, reconstructed_native_F=native_F,
        extinction_charge=extinction_energy, production_F=production_F,
        **{'cost_' + key: value for key, value in costs.items()},
        **{'total_patch_' + key: value for key, value in patch.items()},
        initial_income=world.R_cap * patch['initial_harvest'], refill_income=world.R_cap * patch['refill_harvest'],
        guard=int(bool(status & guards)), extinct=int(extinct))


METRICS = ('production_F', 'F', 'captures', 'misses', 'clicks', 'income', 'physical_cost', 'guard_charge',
    'extinction_charge', 'initial_income', 'refill_income', 'total_patch_initial_harvest',
    'total_patch_refill_harvest', 'total_patch_source', 'total_patch_supply', 'total_patch_spill',
    'total_patch_empty', 'patch_geometric_misses', 'path', 'live_time', 'n_end', 'n_S_end', 'n_M_end', 'n_H_end',
    'cost_maintenance', 'cost_spikes', 'cost_motor', 'cost_messages', 'cost_division_claims', 'cost_secretion',
    'cost_misses', 'cost_receptors', 'guard', 'extinct')


def analyze():
    import numpy as np

    from src.life import spec

    protocol = checked_protocol()
    index = read(STUDY / 'row_index.json')
    expected = {item['path']: item for item in protocol['schedule']}
    if set(index) != set(expected) or len(index) != 456:
        raise ValueError('exact456 saved rows required')
    records, pairs = [], {}
    for item in protocol['schedule']:
        path = STUDY / item['path']
        pin = index[item['path']]
        if any(pin[key] != value for key, value in item.items()) or sha(path) != pin['sha256']:
            raise ValueError('saved row/index binding differs')
        with np.load(path, allow_pickle=False) as data:
            if set(data.files) != {'ledger', 'hashes', 'seed', 'protocol_sha256'}:
                raise ValueError('native raw schema differs')
            if (data['seed'].dtype != np.uint64 or data['seed'].shape != (1,) or
                    int(data['seed'][0]) != item['seed'] or data['protocol_sha256'].item() != sha(STUDY / 'protocol.json')):
                raise ValueError('raw seed/protocol binding differs')
            ledger, hashes = data['ledger'], data['hashes']
            if hashes.shape != (1, 5) or hashes.dtype != np.uint64:
                raise ValueError('five native hash families required')
            if item['fast'] and not np.all(hashes == spec.HASH_INIT):
                raise ValueError('fast hash families are not constants')
            world = spec.World(**protocol['worlds'][item['world']]['world'])
            computed = validate_life(ledger, world)
            record = dict(item, **{key: float(ledger[0, column]) for key, column in spec.V6.L.items()}, **computed)
            records.append(record)
            if item['group'] == 'engineering':
                pairs.setdefault(item['pair'], {})[item['fast']] = ledger.tobytes()
    identical = len(pairs) == 4 and all(set(pair) == {False, True} and pair[False] == pair[True] for pair in pairs.values())
    if not identical:
        raise ValueError('engineering full/fast mismatch')
    scientific = [row for row in records if row['group'] != 'engineering']
    if len(scientific) != 448:
        raise ValueError('scientific row count differs')
    populations = []
    for i in range(32):
        rows = [r for r in scientific if r['group'] == 'population' and r['row'] == i]
        if len(rows) != 8:
            raise ValueError('population row incomplete')
        populations.append(dict(row=i, ancestral_id=protocol['population_ids'][i],
            metrics={key: moments([r[key] for r in rows]) for key in METRICS}))
    references, contrasts = {}, {}
    for world in ('patch', 'pool', 'persistent'):
        references[world] = {}
        selected = {}
        for role in ('AO_rank0', 'AM_reference'):
            rows = [r for r in scientific if r['group'] == 'reference' and r['role'] == role and r['world'] == world]
            if len(rows) != 32:
                raise ValueError('fixed reference incomplete')
            selected[role] = {r['seed']: r for r in rows}
            references[world][role] = {key: moments([r[key] for r in rows]) for key in METRICS}
        if selected['AO_rank0'].keys() != selected['AM_reference'].keys():
            raise ValueError('reference pairing differs')
        contrasts[world] = {key: moments([selected['AO_rank0'][seed][key] - selected['AM_reference'][seed][key]
                                        for seed in sorted(selected['AO_rank0'])]) for key in METRICS}
    status_counts = {}
    for row in records:
        key = str(int(row['status']))
        status_counts[key] = status_counts.get(key, 0) + 1
    summary = dict(status='complete', valid=True, protocol_sha256=sha(STUDY / 'protocol.json'),
        row_index_sha256=sha(STUDY / 'row_index.json'), native_rows=456, native_ledger_values=456*107,
        native_hash_values=456*5, scientific_lives=448, engineering_lives=8, full_fast_ledgers_identical=identical,
        status_counts=status_counts, population_rows=populations,
        population_row_mean_distribution={key: moments([r['metrics'][key]['mean'] for r in populations]) for key in METRICS},
        references=references, paired_AO_minus_AM=contrasts,
        interpretation=protocol['interpretation'],
        population_uncertainty='Eight shared seeds per row; row distribution is descriptive, not32 independent search replicates.',
        source_contribution='Initial/refill FIFO income is observed-trajectory accounting, not a source-off experiment.')
    with (STUDY / 'per_life.csv').open('w', newline='') as stream:
        writer = csv.DictWriter(stream, fieldnames=list(records[0]))
        writer.writeheader()
        writer.writerows(records)
    save(STUDY / 'summary.json', summary)
    return summary


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--saved-data-only', action='store_true')
    if parser.parse_args().saved_data_only:
        analyze()
