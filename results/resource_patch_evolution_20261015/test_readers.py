"""Saved-native and supplied-array reader checks only; no simulator imports, calls, builds or draws."""
import csv
import json
from pathlib import Path

import analyze
import numpy as np
import pytest

from measure import atomic_npz

ROOT = Path(__file__).resolve().parents[2]
BASE = ROOT / 'results/resource_patch_baseline_20261015'
BASE_PROTOCOL = analyze.read(BASE / 'protocol.json')


def definition(world):
    return dict(abi=6, world=world, ledger_columns=list(analyze.LEDGER))


def native(ledger, seeds):
    return dict(ledger=ledger, seeds=np.asarray(seeds, dtype=np.uint64),
                hashes=np.full((len(seeds), 5), 0x243F6A8885A308D3, dtype=np.uint64),
                cpu_seconds=np.asarray(0.), wall_seconds=np.asarray(0.))


@pytest.mark.parametrize('world', ['patch', 'pool', 'persistent'])
@pytest.mark.parametrize('role', ['AO_rank0', 'AM_reference'])
def test_saved_reference_food_costs_and_production(world, role):
    cases = [row for row in BASE_PROTOCOL['schedule'] if row['group'] == 'reference'
             and row['world'] == world and row['role'] == role]
    values = []
    for case in cases:
        with np.load(BASE / case['path'], allow_pickle=False) as raw:
            values.append(raw['ledger'][0])
    row = native(np.stack(values), [case['seed'] for case in cases])
    metrics, health = analyze.reconstruct(row, definition(BASE_PROTOCOL['worlds'][world]['world']), row['seeds'])
    with (BASE / 'per_life.csv').open(newline='') as stream:
        records = [r for r in csv.DictReader(stream) if r['group'] == 'reference'
                   and r['world'] == world and r['role'] == role]
    assert len(records) == 32 and health['status_counts'] == {'0': 32}
    for new, old in [('F', 'production_F'), ('native_F', 'F'), ('physical_cost', 'physical_cost'),
                     ('initial_income', 'initial_income'), ('refill_income', 'refill_income'),
                     ('total_patch_initial_harvest', 'total_patch_initial_harvest'),
                     ('total_patch_refill_harvest', 'total_patch_refill_harvest')]:
        np.testing.assert_allclose(metrics[new], [float(r[old]) for r in records], rtol=1e-12, atol=1e-12)
    expected = analyze.read(BASE / 'summary.json')['references'][world][role]['production_F']
    result = analyze.describe(metrics['F'])
    assert result['mean'] == pytest.approx(expected['mean'], rel=1e-12)
    assert result['se'] == pytest.approx(expected['se'], rel=1e-12)


def supplied(world, count=2):
    # Algebraic fixture: a surviving, stationary single cell, no actions, and full patches spilling ten packets.
    ledger = np.zeros((count, 107), dtype=np.float64)
    for key, value in dict(live_time=world['T'], live_S=world['T'], n_end=1, n_peak=1, n_S_end=1,
                           t_end=world['T'], t_ext=-1, cost=world['c_live'] * world['T'],
                           net=-world['c_live'] * world['T'], F=-world['c_live']).items():
        ledger[:, analyze.L[key]] = value
    for slot in range(world['patch_count']):
        for key, value in dict(stock_open=world['patch_capacity'], stock_end=world['patch_capacity'],
                               source=10, spill=10).items():
            ledger[:, analyze.L[f'patch_{key}_{slot}']] = value
    return ledger


def test_supplied_guard_and_extinction_remain_charged():
    world = BASE_PROTOCOL['worlds']['pool']['world']
    ledger = supplied(world)
    first = {'status': 4, 't_end': 10., 'live_time': 10., 'live_S': 10., 'cost': world['c_live'] * 10,
             'guard_charge': world['c_live'] * world['n_max'] * (world['T'] - 10)}
    first['net'] = -first['cost'] - first['guard_charge']
    first['F'] = first['net'] / world['T']
    second = {'status': 1, 'n_end': 0, 'n_S_end': 0, 'deaths': 1, 't_ext': 20., 'live_time': 20., 'live_S': 20.,
              'cost': world['c_live'] * 20, 'net': -world['c_live'] * 20,
              'F': -world['c_live'] * 20 / world['T']}
    for index, updates in enumerate([first, second]):
        for key, value in updates.items():
            ledger[index, analyze.L[key]] = value
    metrics, health = analyze.reconstruct(native(ledger, [1, 2]), definition(world), [1, 2])
    assert health['guarded'] == health['extinct'] == 1
    assert metrics['F'][0] == first['F']
    assert metrics['F'][1] == pytest.approx(-world['c_live'])
    assert metrics['extinction_energy'][1] == world['c_live'] * (world['T'] - 20)


@pytest.mark.parametrize('corruption', ['source', 'FIFO', 'inactive', 'task', 'fast_hash'])
def test_supplied_corruption_is_rejected(corruption):
    world = BASE_PROTOCOL['worlds']['patch']['world']
    row = native(supplied(world), [1, 2])
    if corruption == 'source':
        row['ledger'][0, analyze.L['patch_source_0']] += 1
        row['ledger'][0, analyze.L['patch_source_1']] -= 1  # Aggregate still matches; per-slot conservation fails.
    elif corruption == 'FIFO':
        for key, value in dict(patch_harvest_0=1, patch_refill_harvest_0=1, patch_supply_0=1,
                               patch_spill_0=9, captures=1, clicks=1).items():
            row['ledger'][0, analyze.L[key]] = value
    elif corruption == 'inactive':
        row['ledger'][0, analyze.L['patch_stock_end_3']] = 1
    elif corruption == 'task':
        row['ledger'][0, analyze.L['choice_opportunities_narrow']] = 1
    else:
        row['hashes'][0, 0] = 0
    with pytest.raises(ValueError):
        analyze.reconstruct(row, definition(world), [1, 2])


def test_complete_supplied_matrix_and_raw_path_metadata(tmp_path):
    worlds = {name: dict(BASE_PROTOCOL['worlds']['patch' if name == 'transfer' else
                        'persistent' if name == 'blink80_20' else name]['world']) for name in analyze.WORLDS}
    worlds['transfer'].update(patch_count=4, R_min=3., R_max=5., patch_refill_fast=100., patch_refill_slow=200.)
    worlds['blink80_20'].update(visibility_mode=2, visibility_on=80., visibility_off=20., visibility_low=0.)
    seeds = list(range(512))  # Supplied labels only: no seed generator or simulator.
    protocol = dict(roles=list(analyze.ROLES), worlds={name: definition(world) for name, world in worlds.items()},
                    seeds=seeds, extinct_charge=True)
    def write(path, value):
        path.write_text(json.dumps(value) + '\n')

    write(tmp_path / 'protocol.json', protocol)
    protocol_pin = analyze.sha(tmp_path / 'protocol.json')
    endpoints = dict(roles=list(analyze.ROLES), protocol_sha256=protocol_pin,
                     genomes=[dict(role=role, raw_sha256='synthetic_' + role) for role in analyze.ROLES])
    write(tmp_path / 'endpoints.json', endpoints)
    endpoint_pin = analyze.sha(tmp_path / 'endpoints.json')
    index = {}
    for world, fields in worlds.items():
        for i, role in enumerate(analyze.ROLES):
            raw_path = f'raw/{world}/row_{i:02d}.npz'
            value = native(supplied(fields, 512), seeds)
            value.update(raw_path=np.asarray(raw_path), world_name=np.asarray(world), role=np.asarray(role),
                         protocol_sha256=np.asarray(protocol_pin), endpoints_sha256=np.asarray(endpoint_pin),
                         genome_raw_sha256=np.asarray('synthetic_' + role))
            atomic_npz(tmp_path / raw_path, **value)
            metrics, health = analyze.reconstruct(value, definition(fields), seeds)
            scored = f'scored/{world}/row_{i:02d}.npz'
            atomic_npz(tmp_path / scored, raw_sha256=np.asarray(analyze.sha(tmp_path / raw_path)),
                       production_F=metrics['F'], native_F=metrics['native_F'],
                       extinct_charge=metrics['extinct_charge'])
            index[raw_path] = dict(status='validated', lives=512, abi=6, role=role, world=world,
                                   sha256=analyze.sha(tmp_path / raw_path), scored_path=scored,
                                   scored_sha256=analyze.sha(tmp_path / scored), health=health)
    write(tmp_path / 'row_index.json', index)
    write(tmp_path / 'measurement_complete.json', dict(status='complete', research_lives=7680, startup_lives=4,
        rows=15, protocol_sha256=protocol_pin, row_index_sha256=analyze.sha(tmp_path / 'row_index.json'),
        endpoints_sha256=endpoint_pin))
    result = analyze.analyze(tmp_path)
    assert result['research_lives'] == 7680 and len(result['absolute']) == 5
    for world in analyze.WORLDS:
        for difference in result['paired'][world].values():
            assert difference['F']['mean'] == difference['F']['se'] == 0
    for world in result['old_world_retention'].values():
        assert world['mixed8_vs_AO_start']['mean_capture_ratio'] is None
    assert result['absolute']['transfer']['mixed8']['total_patch_stock_open']['mean'] == 8
