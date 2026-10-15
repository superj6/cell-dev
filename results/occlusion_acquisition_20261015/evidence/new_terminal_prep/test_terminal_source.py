"""Bounded AN terminal-helper checks, using only synthetic in-memory observations."""
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


M = load('an_terminal_literal', HERE / 'verify_terminal_raw.py')
A = load('an_frozen_reader', ROOT / 'outputs/autonomous_occlusion_acquisition_20261015/analyze.py')


def test_literal_math_and_recount_are_exact_am():
    old = ROOT / 'outputs/audit_capture_value_selection_20261015/terminal_review/verify_terminal_raw.py'
    def functions(path):
        return {n.name: ast.dump(n) for n in ast.parse(path.read_text()).body if isinstance(n, ast.FunctionDef)}
    a, b = functions(old), functions(HERE / 'verify_terminal_raw.py')
    assert all(a[k] == b[k] for k in ('read', 'sha', 'stat', 'literal_row', 'recount'))
    assert M.PROTOCOL_SHA == 'ca277b17294bbce52a4fd6bde77e5847b6b5230c00d285ba8492538f7508b26b'
    assert M.ROLES == A.ROLES and M.WORLDS == A.WORLDS and M.ARMS == ('acquisition',)


def test_exact_2933_literal_vectors_and_fixed_checkpoint_covariance():
    fixture = load('retained_synthetic_row', ROOT / 'outputs/cumulative_capability_20261015/design/test_retention_analyze.py')
    raw, definition, _ = fixture.row(abi=4, n=512)
    values, _ = M.literal_row(raw, definition['world'], 4)
    rows = {world: {role: {k: value.copy() for k, value in values.items()} for role in M.ROLES} for world in M.WORLDS}
    noise = np.arange(512, dtype=np.float64)
    rows['persistent']['generation8']['captures'] += noise
    rows['turn100_blink80_20']['generation8']['captures'] += noise + 2
    literal = M.all_vectors(rows)
    _, canonical = A.contrasts(rows)
    _, retention = A.retention_diagnostics(rows)
    canonical.update(retention)
    assert len(literal) == len(canonical) == 2933 and set(literal) == set(canonical)
    assert all(np.array_equal(literal[k], canonical[k]) for k in literal)
    key = 'interaction__turn100_blink80_20_minus_persistent__generation8_minus_AM_current_start__captures'
    np.testing.assert_array_equal(literal[key], np.full(512, 2.))
    assert sum(k.startswith('retention__') for k in literal) == 8


def test_terminal_gate_precedes_scientific_reads(monkeypatch):
    monkeypatch.setattr(sys, 'argv', ['verify_terminal_raw.py', '--study', '/synthetic_AN',
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
