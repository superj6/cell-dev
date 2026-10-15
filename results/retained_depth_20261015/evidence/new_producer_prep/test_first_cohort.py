"""Only synthetic recorded operations; no genetic RNG, engine or scientific inputs."""
import copy
import importlib.util
import json
from pathlib import Path

import pytest
import torch

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[2]
STUDY = ROOT / 'outputs/autonomous_retained_depth_20261015'
spec = importlib.util.spec_from_file_location('AO_cohort_test', STUDY / 'native_replay.py')
R = importlib.util.module_from_spec(spec)
spec.loader.exec_module(R)


class Layout:
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


def fixture():
    initial = torch.arange(128, dtype=torch.float32).reshape(32, 4)
    initial[1] = initial[0]  # Duplicates remain separate ordered parents.
    children = [{'id': 32 + j, 'pa': j % 32, 'pb': (j + 1) % 32, 'mask': j % 2,
                 'ops': {'mut': [['b', [0], .25], ['b', [1], -.125]]}}
                for j in range(224)]
    lines = [{'event': 'founders', 'sampled': 0, 'ids': list(range(32)), 'copies': []},
             {'gen': 0, 'children': children}]
    return initial, lines


def test_exact_recorded_cohort_without_rng_or_outcome_dependence():
    initial, lines = fixture()
    before = torch.get_rng_state().clone()
    result = R.replay_first(Layout(), initial, lines)
    expected = [row.clone() for row in initial]
    for child in lines[1]['children']:
        row = initial[child['pa'] if child['mask'] else child['pb']].clone()
        row[0] += .25
        row[1] -= .125
        expected.append(row)
    assert result['candidate_raw_sha256'] == R.raw_sha(torch.stack(expected).numpy())
    assert len(result['candidate_row_sha256']) == 256
    assert result['candidate_row_sha256'][0] == result['candidate_row_sha256'][1]
    changed = copy.deepcopy(lines)
    changed[1]['children'][0].update(fitness=-99999., kept=False)
    assert R.replay_first(Layout(), initial, changed) == result
    assert torch.equal(before, torch.get_rng_state())


@pytest.mark.parametrize('kind', ['ids', 'parent', 'mask', 'structural', 'points'])
def test_corrupt_first_cohort_rejected(kind):
    initial, lines = fixture()
    child = lines[1]['children'][0]
    if kind == 'ids':
        child['id'] = 0
    elif kind == 'parent':
        child['pa'] = 32
    elif kind == 'mask':
        child['mask'] = -1
    elif kind == 'structural':
        child['ops']['dup'] = [0, 1]
    else:
        child['ops']['mut'] = []
    with pytest.raises(ValueError):
        R.replay_first(Layout(), initial, lines)


def synthetic_pair(base, monkeypatch):
    initial, lines = fixture()
    protocol = {'source_pins': {n: R.sha(STUDY / n) for n in ('native_replay.py', 'replay_ops.py')}}
    (base / 'protocol.json').write_text(json.dumps(protocol))
    for arm in ('unchanged', 'balanced'):
        out = base / 'runs' / arm
        out.mkdir(parents=True)
        (out / 'lineage.jsonl').write_text('\n'.join(json.dumps(x) for x in lines) + '\n')
        (out / 'search_complete.json').write_text(json.dumps({
            'status': 'complete', 'arm': arm, 'protocol_sha256': R.sha(base / 'protocol.json'),
            'output_pins': {'lineage.jsonl': R.sha(out / 'lineage.jsonl')}}))
    monkeypatch.setattr(R, 'initial_population', lambda *_: (Layout(), initial))
    return protocol


def test_paired_first_cohort_receipt(tmp_path, monkeypatch):
    protocol = synthetic_pair(tmp_path, monkeypatch)
    result = R.first_cohort(tmp_path, protocol)
    assert set(result['runs']) == {'unchanged', 'balanced'}
    assert result['all_256_candidate_bytes_equal'] and result['recorded_genetic_signatures_equal']
    assert result['simulated_lives'] == result['random_draws'] == 0


def test_distinct_recorded_operation_rejected_even_with_updated_log_pin(tmp_path, monkeypatch):
    protocol = synthetic_pair(tmp_path, monkeypatch)
    out = tmp_path / 'runs/balanced'
    lines = [json.loads(s) for s in (out / 'lineage.jsonl').read_text().splitlines()]
    lines[1]['children'][0]['ops']['mut'][0][2] = .5
    (out / 'lineage.jsonl').write_text('\n'.join(json.dumps(x) for x in lines) + '\n')
    marker = json.loads((out / 'search_complete.json').read_text())
    marker['output_pins']['lineage.jsonl'] = R.sha(out / 'lineage.jsonl')
    (out / 'search_complete.json').write_text(json.dumps(marker))
    with pytest.raises(ValueError, match='paired first cohorts differ'):
        R.first_cohort(tmp_path, protocol)


def test_operations_source_exact_previously_reviewed_AM():
    previous = ROOT / 'outputs/autonomous_capture_value_selection_20261015/replay_ops.py'
    assert (STUDY / 'replay_ops.py').read_bytes() == previous.read_bytes()
