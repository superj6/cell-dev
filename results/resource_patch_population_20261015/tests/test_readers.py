"""Literal/supplied arrays only: no organism, build, imported scorer or random draw."""
import hashlib
import importlib.util
import json
from pathlib import Path
from types import SimpleNamespace

import numpy as np
import pytest

PATH = Path(__file__).resolve().parents[1] / 'analyze.py'
SPEC = importlib.util.spec_from_file_location('population_reader_under_test', PATH)
A = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(A)


def same(a, b):
    a, b = np.asarray(a), np.asarray(b)
    return a.shape == b.shape and a.dtype == b.dtype and a.tobytes() == b.tobytes()


def describe(values):
    return dict(mean=float(np.mean(values)), se=float(np.std(values, ddof=1)/np.sqrt(len(values))), n=len(values))


def supplied_batch():
    ledger = np.zeros((96, 107), dtype=np.float64)
    ledger[:, 15] = np.arange(96, dtype=np.float64)
    native = dict(ledger=ledger, hashes=np.zeros((96, 5), dtype=np.uint64),
                  row_indices=np.asarray([7, 8, 9], dtype=np.int64), seeds=np.arange(32, dtype=np.uint64),
                  cpu_seconds=np.asarray(1.), wall_seconds=np.asarray(1.))
    observed = []

    def reconstruct(row, definition, seeds):
        assert definition == {'supplied': True} and seeds == list(range(32))
        assert row['ledger'].shape == (32, 107) and row['hashes'].shape == (32, 5)
        observed.append(row['ledger'][:, 15].copy())
        f = row['ledger'][:, 15].copy()
        return dict(F=f-.5, native_F=f, extinct_charge=np.full(32, .5)), {'retained': 32}

    scored = dict(production_F=ledger[:, 15].reshape(3, 32)-.5,
                  native_F=ledger[:, 15].reshape(3, 32), extinct_charge=np.full((3, 32), .5))
    helper = SimpleNamespace(identical=same, reconstruct=reconstruct)
    return native, scored, helper, observed


def test_cohort_split_is_genotype_major_and_scores_keep_all32_rows():
    native, scored, helper, observed = supplied_batch()
    metrics, health = A.reconstruct_batch(native, {'supplied': True}, list(range(32)), [7, 8, 9], helper, scored)
    assert len(metrics) == 3 and health == [{'retained': 32}] * 3
    assert same(np.stack(observed), np.arange(96, dtype=np.float64).reshape(3, 32))


def test_wrong_explicit_cohort_row_order_rejected():
    native, scored, helper, _ = supplied_batch()
    with pytest.raises(ValueError, match='row order'):
        A.reconstruct_batch(native, {'supplied': True}, list(range(32)), [8, 7, 9], helper, scored)


def test_wrong_scored_native_column_rejected():
    native, scored, helper, _ = supplied_batch()
    scored['native_F'] = scored['native_F'].copy()
    scored['native_F'][1, 5] += 1.
    with pytest.raises(ValueError, match='scoring'):
        A.reconstruct_batch(native, {'supplied': True}, list(range(32)), [7, 8, 9], helper, scored)


def cached_fixture(tmp_path):
    rows, values = [], {w: {} for w in A.WORLDS}
    matrices = {}
    for group, (start, stop) in A.RANGES.items():
        genome = np.zeros((256, 875), dtype=np.float32)
        for local, i in enumerate(range(start, stop)):
            genome[local, 0] = float(i)
            rows.append(dict(index=i, group=group, row=local, label=f'{group}_{local}', native_id=1000+local,
                             raw_sha256=A.raw_sha(genome[local]), reported_endpoint=local == 0))
            for w in A.WORLDS:
                # Literal algebra: first two tie on minimum acquisition; training weights must favor row0.
                capture = dict(patch=19., pool=16., persistent=6., blink80_20=2., transfer=3.)[w]
                f = (dict(patch=10., pool=0., persistent=0., blink80_20=-100., transfer=-100.)[w]
                     if local == 0 else
                     dict(patch=0., pool=8., persistent=8., blink80_20=100., transfer=100.)[w])
                values[w][i] = dict(F=np.full(32, f), captures=np.full(32, capture if local < 2 else 0.))
        if group not in ('mean4', 'pareto4'):
            continue
        folder = tmp_path / 'inputs' / 'cached' / group
        folder.mkdir(parents=True)
        cap = np.tile(np.asarray([19., 16., 19., 6.] * 2), (256, 1))
        fit = np.broadcast_to((32-np.arange(256, dtype=np.float64))[:, None], (256, 8)).copy()
        arrays = dict(base_captures=cap, base_production_F=fit, recheck_captures=cap[:64],
                      recheck_production_F=fit[:64], shortlist=np.arange(64, dtype=np.int64),
                      pick=np.arange(32, dtype=np.int64), candidate_ids=np.arange(1000, 1256, dtype=np.int64),
                      base_genomes=genome)
        path = folder / 'g003.npz'
        np.savez_compressed(path, **arrays)
        pin = hashlib.sha256(path.read_bytes()).hexdigest()
        cached = [[19., 16., 6., float(32-i)] for i in range(32)]
        (folder / 'lineage.jsonl').write_text(json.dumps(dict(gen=3, survivors=list(range(1000, 1032)),
            selection=dict(sha256=pin)))+'\n')
        (folder / 'endpoint_selection.json').write_text(json.dumps(dict(rank=0, selection_sha256=pin,
            selection=dict(objectives=cached, order=list(range(32)))))+'\n')
        matrices[group] = arrays
    return rows, values, matrices


def test_training_weights_and_fixed_reported_endpoint_annotation(tmp_path):
    rows, values, _ = cached_fixture(tmp_path)
    result = A.descriptive_orders(tmp_path, rows, values, SimpleNamespace(describe=describe))
    for group in A.GROUPS:
        assert result[group]['fresh_order_local_rows'][0] == 0
        assert result[group]['rows'][0]['training_weighted_F']['mean'] == 5.
        assert result[group]['rows'][0]['reported_endpoint']
        assert result[group]['replaces_reporting_endpoint'] is False
    assert result['mean4']['rows'][1]['training_weighted_F']['mean'] == 4.
    assert result['mean4']['cached16_order_local_rows'] == list(range(32))
    assert result['G8']['cached_capture_table_available'] is False


def test_cached_survivor_id_mismatch_rejected(tmp_path):
    rows, values, _ = cached_fixture(tmp_path)
    rows[32]['native_id'] += 100
    with pytest.raises(ValueError, match='survivor IDs'):
        A.descriptive_orders(tmp_path, rows, values, SimpleNamespace(describe=describe))


def test_cached_genotype_mismatch_rejected(tmp_path):
    rows, values, _ = cached_fixture(tmp_path)
    rows[32]['raw_sha256'] = '0' * 64
    with pytest.raises(ValueError, match='genotype row bytes'):
        A.descriptive_orders(tmp_path, rows, values, SimpleNamespace(describe=describe))


def test_descriptive_order_has_no_genome_export_or_other_write(tmp_path):
    rows, values, _ = cached_fixture(tmp_path)
    before = {str(p): p.read_bytes() for p in tmp_path.rglob('*') if p.is_file()}
    A.descriptive_orders(tmp_path, rows, values, SimpleNamespace(describe=describe))
    assert {str(p): p.read_bytes() for p in tmp_path.rglob('*') if p.is_file()} == before
