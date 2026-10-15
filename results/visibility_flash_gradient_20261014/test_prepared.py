"""Focused source-only AC checks; no simulation, compilation or genotype generation."""
from __future__ import annotations

import ast
import importlib.util
import json
import os
import subprocess
import sys
from pathlib import Path

import numpy as np
import pytest

STUDY = Path(__file__).resolve().parent
ROOT = STUDY.parents[1]
sys.path[:0] = [str(STUDY), str(ROOT)]
import prepare  # noqa: E402

import measure  # noqa: E402

loader = importlib.util.spec_from_file_location('ac_monitor_tests', STUDY / 'monitor.py')
monitor = importlib.util.module_from_spec(loader)
loader.loader.exec_module(monitor)


def function(path, name):
    return next(x for x in ast.parse(path.read_text()).body if isinstance(x, ast.FunctionDef) and x.name == name)


def test_unchanged_numerical_and_production_scorer():
    original = ROOT / 'outputs/autonomous_visibility_gradient_20261014'
    for name in ('scoring.py', 'numerical.py'):
        assert (STUDY / name).read_bytes() == (original / name).read_bytes()


@pytest.mark.parametrize('name', ['proc_table', 'resource_clearance', 'own_cpu', 'child_cpu', 'active_cpu',
                                  'consumed_cpu', 'child_limit', 'send_signal', 'enable_subreaper',
                                  'cleanup_group', 'cleanup', 'process_identity'])
def test_reviewed_lifecycle_functions_unchanged(name):
    original = ROOT / 'outputs/autonomous_visibility_gradient_20261014/monitor.py'
    assert ast.dump(function(original, name)) == ast.dump(function(STUDY / 'monitor.py', name))


def test_one_golden_call_no_preparation_generation_or_build():
    tree = ast.parse((STUDY / 'measure.py').read_text())
    calls = [x for x in ast.walk(tree) if isinstance(x, ast.Call)
             and isinstance(x.func, ast.Name) and x.func.id == 'numerical_identity']
    assert len(calls) == 1
    for path in (STUDY / 'prepare.py', STUDY / 'monitor.py'):
        for node in ast.walk(ast.parse(path.read_text())):
            if isinstance(node, ast.Call):
                assert not (isinstance(node.func, ast.Name) and node.func.id in
                            ('numerical_identity', 'fill', 'setup', 'make_mutants'))
                assert not (isinstance(node.func, ast.Attribute) and isinstance(node.func.value, ast.Name)
                            and node.func.value.id == 'build' and node.func.attr in ('run', 'build'))


def test_retained_mutant_selection_all_rows_negative_tie():
    rows = {i: {'F': np.full(32, 100.0 if i == 0 else -3.0)} for i in range(65)}
    assert measure.select_winner(rows) == 1
    rows[64]['F'][:] = -2
    assert measure.select_winner(rows) == 64
    rows[3]['F'][0] = np.nan
    with pytest.raises(ValueError):
        measure.select_winner(rows)


@pytest.mark.parametrize('fault', ['missing', 'overlap', 'golden', 'overflow', 'boolean'])
def test_stage_seed_contract(fault):
    seeds = {'screen': list(range(100, 132)), 'confirm': list(range(1000, 1512)), 'calibration': [2000, 2001]}
    assert measure.stage_seeds({'seeds': seeds}) == seeds
    if fault == 'missing':
        seeds['screen'].pop()
    else:
        seeds['calibration'][0] = {'overlap': 100, 'golden': 11, 'overflow': 2**64, 'boolean': True}[fault]
    with pytest.raises(ValueError):
        measure.stage_seeds({'seeds': seeds})


def fixtures():
    historical = {p: [0.1] * 65 for p in measure.PARENTS}
    historical['D90'][45] = 1.0
    rows = {p: {0: {'cpu_seconds': 0.3}, 1: {'cpu_seconds': 0.4}} for p in measure.PARENTS}
    snapshot = {f'screen/{p}': {f'calibration/row_{i:04d}.npz': rows[p][i] for i in (0, 1)}
                for p in measure.PARENTS}
    return historical, rows, snapshot


def test_initial_projection_includes_12_roles_worst_blink_and_fixed_overhead():
    historical, rows, snapshot = fixtures()
    result = measure.calibration_projection(rows, 20, historical)
    expected = monitor.initial_projection_values({'historical_blink_cpu_per_life': historical},
                                                {'row_snapshot': snapshot, 'cpu_seconds': 20})
    assert all(result[k] == v for k, v in expected.items())
    assert len(result['confirmation_role_rates']['flash']) == len(result['confirmation_role_rates']['blink']) == 6
    assert result['confirmation_role_rates']['blink']['H_D90'] == 1
    assert result['screen_projection_cpu_seconds'] == 1268
    assert result['confirmation_projection_cpu_seconds'] == pytest.approx(2253.6)


def test_initial_cost_gate_stops_before_screen_when_infeasible():
    historical, rows, snapshot = fixtures()
    historical['D90'][45] = 4
    assert not measure.calibration_projection(rows, 20, historical)['feasible']
    with pytest.raises(ValueError, match='initial cost'):
        monitor.initial_projection_values({'historical_blink_cpu_per_life': historical},
                                          {'row_snapshot': snapshot, 'cpu_seconds': 20})
    main = ast.unparse(function(STUDY / 'monitor.py', 'main'))
    assert main.index('initial_projection_values(protocol,') < main.index("save(STUDY / 'monitor_receipts'")


def test_frozen_selected_projection_retains_duplicate_roles():
    historical, _, _ = fixtures()
    screens = {p: {i: {'cpu_seconds': 3.2} for i in range(65)} for p in measure.PARENTS}
    winners = {p: {'genome_row': measure.BLINK_ROWS[p]} for p in measure.PARENTS}
    result = measure.selected_projection(screens, winners, historical)
    assert sum(map(len, result['confirmation_role_rates'].values())) == 12
    assert result['confirmation_role_rates']['flash']['H_D90'] == result['confirmation_role_rates']['flash']['B_D90']
    assert result['confirmation_projection_cpu_seconds'] == pytest.approx(1101.6)
    screens['D90'][58]['cpu_seconds'] = 200
    assert not measure.selected_projection(screens, winners, historical)['feasible']


@pytest.mark.parametrize('phase,edge', [('startup_calibration', 170), ('startup_screen', 3390), ('confirmation', 7190)])
def test_three_cumulative_phase_limits(phase, edge):
    assert monitor.SCOPE == measure.SCOPE
    assert monitor.budget_reason(phase, edge - .01) is None
    assert monitor.budget_reason(phase, edge)


def test_startup_transition_persistent_worker_total_rlimit():
    assert monitor.phase_transition('calibration_complete', 'startup_calibration') == 'startup_screen'
    assert monitor.phase_transition('screens_complete', 'startup_screen') == 'confirmation'
    with pytest.raises(ValueError):
        monitor.phase_transition('screens_complete', 'startup_calibration')
    with pytest.raises(ValueError):
        monitor.phase_transition('calibration_complete', 'confirmation')
    main = ast.unparse(function(STUDY / 'monitor.py', 'main'))
    assert 'remaining = CAP - consumed' in main
    assert 'limit=remaining' in main
    assert 'child_limit(limit, parent)' in main
    assert main.count('subprocess.Popen(') == 1


def test_exact_row_and_life_counts():
    assert len(monitor.expected_rows('calibration_complete', 'screen/D90')) == 2
    assert len(monitor.expected_rows('screens_complete', 'screen/D90')) == 67
    assert len(monitor.expected_rows('complete', 'confirm/flash')) == 6
    assert 2 * 67 + 2 * 6 == 146
    assert 2 * 65 * 32 + 2 * 6 * 512 == 10304
    assert 10304 + 2 * 2 * 2 + 2 == 10314


@pytest.mark.parametrize('changed', ['startup_identity.json', 'selection.json', 'calibration_projection.json',
                                    'confirmation_projection.json', 'confirmation_roles.json',
                                    'confirmation_genotypes.npz', 'request', 'receipt'])
def test_acknowledged_artifact_tamper_rejected(tmp_path, monkeypatch, changed):
    monkeypatch.setattr(monitor, 'STUDY', tmp_path)
    request = tmp_path / 'requests/screens_complete.json'
    receipt_path = tmp_path / 'monitor_receipts/screens_complete.json'
    monitor.save(request, {'selection_sha256': 'known'})
    files = ['startup_identity.json', 'selection.json', 'calibration_projection.json',
             'confirmation_projection.json', 'confirmation_roles.json', 'confirmation_genotypes.npz']
    for name in files:
        monitor.save(tmp_path / name, {'frozen': name})
    receipt = {'request_sha256': monitor.sha(request),
               'artifact_pins': {name: monitor.sha(tmp_path / name) for name in files}}
    monitor.save(receipt_path, receipt)
    monitor.check_acknowledged({'screens_complete': receipt})
    target = request if changed == 'request' else receipt_path if changed == 'receipt' else tmp_path / changed
    monitor.save(target, {'altered': True})
    with pytest.raises(ValueError):
        monitor.check_acknowledged({'screens_complete': receipt})


@pytest.mark.parametrize('status', ['complete', 'incomplete', 'monitor_failed'])
def test_ab_dependency_is_clean_terminal_not_success(tmp_path, monkeypatch, status):
    monkeypatch.setattr(prepare, 'STUDY', tmp_path)
    monkeypatch.setattr(prepare, 'ROOT', tmp_path)
    budget_name = 'outputs/autonomous_visibility_precision_20261014/budget.json'
    monitor.save(tmp_path / budget_name, {'status': status, 'running': {}, 'queued': [], 'cleanup_error': None})
    seeds = {'screen': list(range(100, 132)), 'confirm': list(range(1000, 1512)), 'calibration': [2000, 2001]}
    monitor.save(tmp_path / 'seed_audit.json', {'status': 'passed', 'seeds': seeds})
    reg = {'status': 'registered', 'roles': measure.ROLES,
           'panel_policy': 'entire_Y_panels_unchanged_regardless_of_AB_outcomes', 'seeds': seeds,
           'seed_audit_sha256': monitor.sha(tmp_path / 'seed_audit.json'),
           'AB_terminal': {'file_pins': {budget_name: monitor.sha(tmp_path / budget_name)}}}
    monitor.save(tmp_path / 'registration.json', reg)
    assert prepare.registration()[0] == reg
    monitor.save(tmp_path / budget_name, {'status': status, 'running': {'123': 'worker'}})
    reg['AB_terminal']['file_pins'][budget_name] = monitor.sha(tmp_path / budget_name)
    monitor.save(tmp_path / 'registration.json', reg)
    with pytest.raises(ValueError, match='clean terminal'):
        prepare.registration()


@pytest.mark.parametrize('script', ['prepare.py', 'measure.py', 'monitor.py'])
def test_default_dry_run_has_no_inputs_or_runtime(script):
    result = subprocess.run([sys.executable, str(STUDY / script)], capture_output=True, text=True, check=True,
                            env={**os.environ, 'PYTHONDONTWRITEBYTECODE': '1'})
    value = json.loads(result.stdout)
    assert value['status'] in ('source_only_unregistered', 'dry_run')
    assert not any((STUDY / name).exists() for name in
                   ('inputs', 'protocol.json', 'attempt.json', 'measurement', 'build-cache', 'startup_identity.json'))


def test_preparation_refuses_before_registration_without_creating_inputs(tmp_path, monkeypatch):
    monkeypatch.setattr(prepare, 'STUDY', tmp_path)
    with pytest.raises(FileNotFoundError):
        prepare.prepare()
    assert list(tmp_path.iterdir()) == []


def test_actual_public_Y_metadata_paths_and_budget_mapping():
    # Metadata only: do not load or copy genotype arrays.
    assert prepare.historical_source('budget.json') == prepare.Y / 'operations/budget.json'
    assert prepare.read(prepare.historical_source('budget.json'))['status'] == 'complete'
    for name in ('protocol.json', 'selection.json', 'startup_identity.json', 'analysis_result/summary.json',
                 'analysis/genetic_replay.py', 'analysis/genetic_replay.json'):
        assert prepare.historical_source(name).is_file()
    protocol = prepare.read(prepare.Y / 'protocol.json')
    assert all((prepare.Y / name).is_file() for name in protocol['file_pins'])
    assert not (STUDY / 'inputs').exists()
