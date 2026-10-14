"""Lossless trace storage and strict validation tests; no life simulations."""
from dataclasses import fields
from types import SimpleNamespace

import numpy as np
import pandas as pd
import pytest

import measure as M
from src.life import probe, spec


def synthetic():
    tables = {field.name: pd.DataFrame() for field in fields(probe.Trace) if field.name not in ('ledger', 'meta')}
    tables['cells'] = pd.DataFrame(dict(uid=np.array([2**64-1, 7], dtype=np.uint64),
                                       x=np.array([-0., np.nan]), y=np.array([np.inf, -np.inf]),
                                       cls=['H', 'S']))
    tables['genes_birth'] = pd.DataFrame(dict(g0=np.array([0.1, -0.2], dtype=np.float64)))
    tables['steps'] = pd.DataFrame(dict(step=np.array([], dtype=np.int64), t=np.array([], dtype=np.float64)))
    ledger = {key: 0.0 for key in spec.V3.LEDGER}
    ledger['t_end'] = 1536.
    trace = probe.Trace(**tables, ledger=ledger,
                        meta=dict(seed=M.SEEDS[0], world=spec.world('catch_speck_l4', **M.WORLD), seconds=1.25))
    kernel = SimpleNamespace(ledger=np.asarray([list(ledger.values())], dtype=np.float64),
                             hashes=np.array([[0, 1, 2, 3, 2**64-1]], dtype=np.uint64))
    return trace, kernel


def test_all_table_roundtrip_without_pickle(tmp_path):
    trace, kernel = synthetic()
    path = tmp_path / 'trace.npz'
    M.store_trace(path, trace, kernel)
    with np.load(path, allow_pickle=False) as data:
        assert all(data[key].dtype.kind != 'O' for key in data.files)
        assert data['kernel_hashes'].tobytes() == kernel.hashes.tobytes()
    restored, ledger = M.load_trace(path)
    M.validate_roundtrip(trace, restored)
    assert ledger.tobytes() == kernel.ledger.tobytes()
    assert M.validate_match(restored, ledger) == {}


def test_roundtrip_checks_unused_gene_tables(tmp_path):
    trace, kernel = synthetic()
    path = tmp_path / 'trace.npz'
    M.store_trace(path, trace, kernel)
    restored, _ = M.load_trace(path)
    restored.genes_birth.loc[0, 'g0'] = np.nextafter(0.1, 1.)
    with pytest.raises(ValueError, match='genes_birth/g0'):
        M.validate_roundtrip(trace, restored)


def test_reference_ledger_validation_is_bitwise():
    trace, kernel = synthetic()
    kernel.ledger[0, spec.V3.L['F']] = -0.
    with pytest.raises(ValueError, match='ledger differs'):
        M.validate_match(trace, kernel.ledger)


def test_invalid_ledger_is_not_dropped():
    trace, kernel = synthetic()
    trace.ledger['status'] = float(spec.STATUS['guard_events'])
    kernel.ledger[0, spec.V3.L['status']] = trace.ledger['status']
    with pytest.raises(ValueError, match='invalid or incomplete'):
        M.validate_match(trace, kernel.ledger)


def test_missing_receptor_groups_compare_as_null(monkeypatch):
    trace, _ = synthetic()
    from src.life import readouts

    monkeypatch.setattr(probe, 'relabel', lambda _: None)
    monkeypatch.setattr(readouts, 'search_signature', lambda *a, **k: dict(ratio=None))
    monkeypatch.setattr(readouts, 'relay_chains', lambda *a, **k: dict(relayed=float('nan')))
    first, second = M.describe(trace), M.describe(trace)
    assert first == second and first['relay']['800']['relayed'] is None
