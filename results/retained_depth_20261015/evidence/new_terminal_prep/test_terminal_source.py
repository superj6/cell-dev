"""Focused AO coverage/accuracy checks using synthetic arrays and source-only imports."""
import ast
import importlib.util
import sys
from pathlib import Path

import numpy as np
import pytest

ROOT = next(p for p in Path(__file__).resolve().parents if (p / 'src/life/spec.py').is_file())
HERE = Path(__file__).resolve().parent


def load(name, path):
    spec = importlib.util.spec_from_file_location(name, path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


M = load('ao_terminal_literal', HERE / 'verify_terminal_raw.py')
A = load('ao_frozen_reader', ROOT / 'outputs/autonomous_retained_depth_20261015/analyze.py')


def synthetic_rows():
    world = {k: 0. for k in ('c_spike', 'c_tw', 'c_msg', 'c_div', 'c_sec', 'c_miss', 'c_rec', 'b2_value')}
    world.update(c_live=.01, R_cap=500., n_max=128, t0=0., T=1024., t_open=0.)
    ledger = np.zeros((512, 58), dtype=np.float64)
    ledger[:, 1] = 1024.
    ledger[:, 16:18] = 1.
    ledger[:, 18] = 1024.
    ledger[:, 34] = -1.
    ledger[:, 35] = np.arange(512) % 3
    ledger[:, 37] = ledger[:, 35]
    ledger[:, 0] = 500. * ledger[:, 35]
    ledger[:, 12] = .01 * 1024.
    ledger[:, 14] = ledger[:, 0] - ledger[:, 12]
    ledger[:, 15] = ledger[:, 14] / 1024.
    values, _ = M.literal_row({'ledger': ledger, 'production_F': ledger[:, 15]}, world, 4)
    assert len(values) == 75
    return {w: {r: {k: v.copy() for k, v in values.items()} for r in M.ROLES} for w in M.WORLDS}


def test_literal_math_recount_and_frozen_identity_unchanged():
    def functions(path):
        return {n.name: ast.dump(n) for n in ast.parse(path.read_text()).body if isinstance(n, ast.FunctionDef)}
    prior = ROOT / 'outputs/audit_occlusion_acquisition_20261015/new_terminal_prep/verify_terminal_raw.py'
    a, b = functions(prior), functions(HERE / 'verify_terminal_raw.py')
    assert all(a[k] == b[k] for k in ('read', 'sha', 'stat', 'literal_row', 'recount'))
    assert M.PROTOCOL_SHA == '2cfc3ac9a6d41e2d3c49e630a7bc611ff9737962175def3d1eb89e6d8de6d68d'
    assert M.ANALYZER_SHA == M.sha(ROOT / 'outputs/autonomous_retained_depth_20261015/analyze.py')
    assert M.ROLES == A.ROLES and M.WORLDS == A.WORLDS and M.ARMS == ('unchanged', 'balanced')


def test_all_11967_vectors_21_retention_entries_and_covariance():
    rows = synthetic_rows()
    noise = np.arange(512, dtype=np.float64)
    rows['persistent']['balanced24']['captures'] += noise
    rows['turn100_blink80_20']['balanced24']['captures'] += noise + 2
    literal = M.all_vectors(rows)
    _, canonical = A.contrasts(rows)
    _, retention = A.retention_diagnostics(rows)
    canonical.update(retention)
    assert len(literal) == len(canonical) == 11967 and set(literal) == set(canonical)
    assert all(np.array_equal(literal[k], canonical[k]) for k in literal)
    key = 'interaction__turn100_blink80_20_minus_persistent__balanced24_minus_unchanged24__captures'
    np.testing.assert_array_equal(literal[key], np.full(512, 2.))
    assert sum(k.startswith('retention__') for k in literal) == 42
    assert len({k.rsplit('__', 1)[0] for k in literal if k.startswith('retention__')}) == 21


@pytest.mark.parametrize('mode', ['mixed_clicks', 'all_clickless', 'invalid_census'])
def test_accuracy_all30_rows_and_edge_cases(mode):
    rows = synthetic_rows()
    chosen = rows['pool']['AM_reference']
    if mode == 'all_clickless':
        for key in ('captures', 'misses', 'clicks'):
            chosen[key][:] = 0
    elif mode == 'invalid_census':
        chosen['clicks'][0] += 1
        with pytest.raises(ValueError, match='captures \\+ misses = clicks'):
            M.accuracy_counts(rows)
        return
    actual = M.accuracy_counts(rows)
    expected = {w: {r: A.describe_counts(*(rows[w][r][k] for k in ('captures', 'misses', 'clicks')))
                    for r in M.ROLES} for w in M.WORLDS}
    assert actual == expected and sum(len(v) for v in actual.values()) == 30
    assert actual['pool']['AM_reference']['aggregate_capture_fraction'] == (None if mode == 'all_clickless' else 1.)
    if mode == 'all_clickless':
        assert actual['pool']['AM_reference']['clickless_lives'] == 512
    rows['pool'].pop('balanced24')
    with pytest.raises(ValueError, match='30-row accuracy matrix'):
        M.accuracy_counts(rows)


def test_terminal_gate_precedes_scientific_reads(monkeypatch):
    monkeypatch.setattr(sys, 'argv', ['verify_terminal_raw.py', '--study', '/synthetic_AO',
        '--protocol-sha256', M.PROTOCOL_SHA, '--budget-sha256', 'budget', '--clearance-sha256', 'clearance'])
    monkeypatch.setattr(M, 'sha', lambda p: 'budget' if p.name == 'budget.json' else 'clearance')
    seen = []

    def read(path):
        seen.append(path.name)
        assert path.name in ('budget.json', 'host_clearance.json')
        return {'status': 'running'}

    monkeypatch.setattr(M, 'read', read)
    with pytest.raises(ValueError, match='root-cleared complete'):
        M.main()
    assert seen == ['budget.json', 'host_clearance.json']
