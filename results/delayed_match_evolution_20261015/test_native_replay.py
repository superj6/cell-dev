"""Synthetic recorded operations only: no genetic draws, builds or scientific lives."""
from __future__ import annotations

import copy
import hashlib
import importlib.util
import json
from pathlib import Path
from types import SimpleNamespace

import numpy as np
import pytest
import torch

HERE = Path(__file__).resolve().parent
found = importlib.util.spec_from_file_location('matching_replay_test', HERE / 'native_replay.py')
R = importlib.util.module_from_spec(found)
found.loader.exec_module(R)


class Layout:
    size = 4
    dims = SimpleNamespace(genes_max=1)
    n_units = 1
    unit_of = torch.zeros(4, dtype=torch.long)
    block_of = torch.zeros(4, dtype=torch.long)
    slices = {'b': (0, 4, (4,))}

    def mutable(self, value):
        return torch.ones_like(value, dtype=torch.bool)

    def n_mut_of(self, value, n):
        return torch.full((len(value),), n, dtype=torch.long)

    def silence(self, value):
        return value.clone()

    def active(self, value):
        return torch.ones(1, dtype=torch.bool)


def recorded_fixture(generations):
    """Independent arithmetic for retained child rows; no use of the replay primitive."""
    initial = torch.arange(128, dtype=torch.float32).reshape(32, 4) / 128
    initial[1] = initial[0]
    population = {i: row.clone() for i, row in enumerate(initial)}
    origins = {i: i for i in range(32)}
    lines = [{'event': 'founders', 'sampled': 0, 'ids': list(range(32)), 'copies': []}]
    for g in range(generations):
        parents = list(population)
        all_rows, all_origins, children = dict(population), dict(origins), []
        for j in range(224):
            cid = 32 + 224*g + j
            pa, pb, mask = parents[j % 32], parents[(j+1) % 32], j % 2
            source = pa if mask else pb
            row = population[source].clone()
            row[0] += .25
            row[1] -= .125
            all_rows[cid], all_origins[cid] = row, origins[source]
            children.append({'id': cid, 'pa': pa, 'pb': pb, 'mask': mask,
                             'ops': {'mut': [['b', [0], .25], ['b', [1], -.125]]}})
        survivors = [children[0]['id']] + parents[:31]
        for child in children:
            child['kept'] = child['id'] in survivors
        population = {i: all_rows[i] for i in survivors}
        origins = {i: all_origins[i] for i in survivors}
        matrix = np.asarray(list(origins.values()), dtype=np.int64)[:, None]
        registry = {'0': {str(int(i)): int(np.count_nonzero(matrix == i)) for i in np.unique(matrix)}}
        lines.append({'gen': g, 'children': children, 'survivors': survivors,
                      'registry': registry, 'n_active': 1.})
    state = {'ids': torch.tensor(list(population)), 'population': torch.stack(list(population.values())),
             'origins': torch.tensor(list(origins.values()))[:, None],
             'next_innov': 32, 'next_id': 32 + 224*generations}
    return initial, lines, state


@pytest.mark.parametrize('generations', (8, 24))
def test_all_retained_rows_and_operation_counts_without_rng(generations):
    initial, lines, state = recorded_fixture(generations)
    before = torch.get_rng_state().clone()
    initial_before = initial.numpy().tobytes()
    result = R.recorded_population(Layout(), initial, lines, state, generations)
    assert result['offspring_replayed'] == generations*224
    assert result['point_mutations_including_initial_copies'] == generations*224*2
    assert result['all_32_rows_bound'] and len(result['row_sha256']) == 32
    assert torch.equal(before, torch.get_rng_state())
    assert initial.numpy().tobytes() == initial_before


@pytest.mark.parametrize('kind', ('ids', 'parent', 'mask', 'structural', 'points', 'kept', 'survivors', 'raw', 'origin'))
def test_corrupt_recorded_population_rejected(kind):
    initial, lines, state = recorded_fixture(1)
    child = lines[1]['children'][0]
    if kind == 'ids':
        child['id'] = 0
    elif kind == 'parent':
        child['pa'] = 10000
    elif kind == 'mask':
        child['mask'] = -1
    elif kind == 'structural':
        child['ops']['dup'] = [0, 1]
    elif kind == 'points':
        child['ops']['mut'][1][1] = [0]
    elif kind == 'kept':
        child['kept'] = False
    elif kind == 'survivors':
        lines[1]['survivors'][1] = lines[1]['survivors'][0]
    elif kind == 'raw':
        state['population'][0, 0] += 1
    else:
        state['origins'][0, 0] += 1
    with pytest.raises(ValueError):
        R.recorded_population(Layout(), initial, lines, state, 1)


def test_first_cohort_preserves_duplicate_rows_and_recorded_commands():
    initial, lines, _ = recorded_fixture(1)
    result = R.replay_first(Layout(), initial, lines)
    assert len(result['candidate_row_sha256']) == 256
    assert result['candidate_row_sha256'][0] == result['candidate_row_sha256'][1]
    changed = copy.deepcopy(lines)
    changed[1]['children'][0]['fitness'] = -9999
    assert R.replay_first(Layout(), initial, changed) == result
    changed[1]['children'][0]['ops']['mut'][0][2] = .5
    assert R.replay_first(Layout(), initial, changed) != result


def test_log_prefix_bindings_allow_later_suffix_but_reject_prefix_change(tmp_path):
    names = ('curves.jsonl', 'lineage.jsonl', 'clones.jsonl')
    saved = {'logs': {}}
    for name in names:
        data = b'' if name == 'clones.jsonl' else b'{"gen":0}\n'
        (tmp_path / name).write_bytes(data)
        saved['logs'][name] = {'bytes': len(data), 'sha256': hashlib.sha256(data).hexdigest()}
    expected = R.bound_logs(tmp_path, saved)
    (tmp_path / 'lineage.jsonl').write_bytes(b'{"gen":0}\n{"gen":1}\n')
    assert R.bound_logs(tmp_path, saved, prefix=True) == expected
    with pytest.raises(ValueError):
        R.bound_logs(tmp_path, saved)
    (tmp_path / 'lineage.jsonl').write_bytes(b'{"gen":9}\n{"gen":1}\n')
    with pytest.raises(ValueError):
        R.bound_logs(tmp_path, saved, prefix=True)


def test_single_run_first_cohort_receipt(tmp_path, monkeypatch):
    initial, lines, _ = recorded_fixture(1)
    protocol = {'source_pins': {n: R.sha(HERE / n) for n in ('native_replay.py', 'replay_ops.py')}}
    (tmp_path / 'protocol.json').write_text(json.dumps(protocol))
    folder = tmp_path / 'runs/mixed'
    folder.mkdir(parents=True)
    (folder / 'lineage.jsonl').write_text('\n'.join(json.dumps(x) for x in lines) + '\n')
    (folder / 'search_complete.json').write_text(json.dumps({
        'status': 'complete', 'arm': 'mixed', 'protocol_sha256': R.sha(tmp_path / 'protocol.json'),
        'output_pins': {'lineage.jsonl': R.sha(folder / 'lineage.jsonl')}}))
    monkeypatch.setattr(R, 'initial_population', lambda *_: (Layout(), initial))
    result = R.first_cohort(tmp_path, protocol)
    assert set(result['runs']) == {'mixed'}
    assert result['simulated_lives'] == result['random_draws'] == 0


def test_replay_primitive_preserves_reviewed_AO_bytes():
    old = HERE.parents[1] / 'outputs/autonomous_retained_depth_20261015/replay_ops.py'
    assert (HERE / 'replay_ops.py').read_bytes() == old.read_bytes()
