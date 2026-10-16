"""Supplied arrays only: new endpoint weighting/order and genotype-major batch splitting."""
import importlib.util
from pathlib import Path
from types import SimpleNamespace

import numpy as np
import pytest

STUDY = Path(__file__).resolve().parents[1]
SPEC = importlib.util.spec_from_file_location('depth_reader_under_test', STUDY / 'analyze.py')
reader = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(reader)


def describe(values):
    return dict(mean=float(np.mean(values)), se=float(np.std(values, ddof=1)/np.sqrt(len(values))))


def supplied():
    values = {w: [{k: np.zeros(32) for k in reader.ENDPOINT_METRICS} for _ in range(32)]
              for w in reader.TRAIN}
    for w, scale in zip(reader.TRAIN, reader.SCALES, strict=True):
        for row in values[w]:
            row['captures'][:] = scale
    return values, np.arange(100, 132, dtype=np.int64), [f'row{i}' for i in range(32)]


def choose(values, ids, hashes):
    return reader.endpoint_statistics(values, ids, hashes, SimpleNamespace(describe=describe))


def test_weighted_f_is_not_unweighted_equal_world_mean():
    values, ids, hashes = supplied()
    values['patch'][0]['F'][:] = 4
    values['pool'][1]['F'][:] = values['persistent'][1]['F'][:] = 3
    result = choose(values, ids, hashes)
    assert result['selected_row'] == 0
    assert result['rows'][0]['objectives'][3] == 2
    assert result['rows'][1]['objectives'][3] == 1.5
    assert result['minimum_has_no_linear_SE'] and result['development_only']


def test_weakest_capture_fraction_precedes_arbitrarily_high_f():
    values, ids, hashes = supplied()
    values['persistent'][1]['captures'][:] *= .99
    for w in reader.TRAIN:
        values[w][1]['F'][:] = 1000
    result = choose(values, ids, hashes)
    assert result['selected_row'] == 0 and result['order'][-1] == 1


def test_exact_ties_use_native_id_without_row_or_random_preference():
    values, ids, hashes = supplied()
    ids[31] = 1
    result = choose(values, ids, hashes)
    assert result['selected_row'] == 31 and result['selected_id'] == 1
    assert result['random_draws'] == 0 and result['endpoint_lives'] == 3072


def test_endpoint_rejects_incomplete_life_vector():
    values, ids, hashes = supplied()
    values['patch'][0]['captures'] = np.zeros(31)
    with pytest.raises(ValueError, match='32 whole lives'):
        choose(values, ids, hashes)


def test_endpoint_rejects_nonfinite_fitness():
    values, ids, hashes = supplied()
    values['patch'][0]['F'][4] = np.nan
    with pytest.raises(ValueError, match='nonfinite'):
        choose(values, ids, hashes)


def batch_fixture():
    def reconstruct(row, definition, seeds):
        assert row['seeds'].tolist() == seeds
        score = row['ledger'][:, 0]
        return dict(F=score, native_F=score+1, extinct_charge=np.ones(32)), dict(n=32)

    def identical(a, b):
        return a.shape == b.shape and a.dtype == b.dtype and a.tobytes() == b.tobytes()

    native = dict(ledger=np.zeros((64, 107)), hashes=np.zeros((64, 5), dtype=np.uint64),
                  row_ids=np.asarray([19, 3], dtype=np.int64), seeds=np.arange(32, dtype=np.uint64),
                  cpu_seconds=np.asarray(0.), wall_seconds=np.asarray(0.))
    native['ledger'][:, 0] = np.arange(64)
    scored = dict(production_F=np.arange(64, dtype=np.float64).reshape(2, 32),
                  native_F=np.arange(1, 65, dtype=np.float64).reshape(2, 32), extinct_charge=np.ones((2, 32)))
    return native, scored, SimpleNamespace(reconstruct=reconstruct, identical=identical)


def test_genotype_major_cohort_splits_and_keeps_original_native_ids():
    native, scored, helper = batch_fixture()
    values, health = reader.reconstruct_batch(native, {}, list(range(32)), [19, 3], helper, scored)
    assert values[0]['F'].tolist() == list(range(32))
    assert values[1]['F'].tolist() == list(range(32, 64))
    assert health == [dict(n=32), dict(n=32)]


def test_batch_rejects_reordered_ids_and_misaligned_native_score():
    native, scored, helper = batch_fixture()
    with pytest.raises(ValueError, match='identities'):
        reader.reconstruct_batch(native, {}, list(range(32)), [3, 19], helper, scored)
    scored['native_F'][1, 0] += 1
    with pytest.raises(ValueError, match='scoring differs'):
        reader.reconstruct_batch(native, {}, list(range(32)), [19, 3], helper, scored)
