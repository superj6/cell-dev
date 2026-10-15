"""Focused source-only AG checks; no simulation, compilation or genotype generation."""
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

loader = importlib.util.spec_from_file_location('ag_monitor_tests', STUDY / 'monitor.py')
monitor = importlib.util.module_from_spec(loader)
loader.loader.exec_module(monitor)


def function(path, name):
    return next(x for x in ast.parse(path.read_text()).body if isinstance(x, ast.FunctionDef) and x.name == name)


def test_retained_numerical_and_explicit_abi4_scorer():
    original = ROOT / 'outputs/autonomous_visibility_flash_gradient_20261014'
    assert (STUDY / 'numerical.py').read_bytes() == (original / 'numerical.py').read_bytes()
    source = (STUDY / 'scoring.py').read_text()
    assert 'ABI = spec.V4' in source and 'low_light_captures' in source
    assert 'evaluator.abi.version != 4' in source


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


def test_initial_projection_keeps_all130_floors_and_four_roles(tmp_path, monkeypatch):
    historical, rows, snapshot = fixtures()
    result = measure.calibration_projection(rows, 20, historical)
    expected = monitor.initial_projection_values({'historical_flash_cpu_per_life': historical},
                                                {'row_snapshot': snapshot, 'cpu_seconds': 20})
    assert all(result[k] == v for k, v in expected.items())
    assert len(result['confirmation_role_rates']) == 4
    assert result['confirmation_role_rates']['H_D90'] == 1
    assert result['confirmation_role_rates']['P_D90'] == .15
    assert sum(map(len, result['screen_row_rate_floors'].values())) == 130
    assert result['screen_projection_cpu_seconds'] == pytest.approx(1306.4)
    assert result['confirmation_projection_cpu_seconds'] == pytest.approx(1332.0)
    # Exercise the real persisted interface, where JSON object keys must stay strings.
    monkeypatch.setattr(monitor, 'STUDY', tmp_path)
    monitor.save(tmp_path / 'calibration_projection.json', result)
    monitor.check_initial_projection({'historical_flash_cpu_per_life': historical},
                                     {'row_snapshot': snapshot, 'cpu_seconds': 20})


def test_initial_cost_gate_stops_before_screen_when_infeasible():
    historical, rows, snapshot = fixtures()
    historical['D90'][45] = 4
    assert not measure.calibration_projection(rows, 20, historical)['feasible']
    with pytest.raises(ValueError, match='initial cost'):
        monitor.initial_projection_values({'historical_flash_cpu_per_life': historical},
                                          {'row_snapshot': snapshot, 'cpu_seconds': 20})
    main = ast.unparse(function(STUDY / 'monitor.py', 'main'))
    assert main.index('initial_projection_values(protocol,') < main.index("save(STUDY / 'monitor_receipts'")


def test_frozen_selected_projection_uses_both_actual_rows_and_historical_floors():
    historical, _, _ = fixtures()
    screens = {p: {i: {'cpu_seconds': 3.2} for i in range(65)} for p in measure.PARENTS}
    winners = {p: {'genome_row': 1} for p in measure.PARENTS}
    result = measure.selected_projection(screens, winners, historical)
    assert len(result['confirmation_role_rates']) == 4
    assert result['confirmation_projection_cpu_seconds'] == pytest.approx(487.2)
    winners['D90']['genome_row'] = 45
    result = measure.selected_projection(screens, winners, historical)
    assert result['confirmation_role_rates']['H_D90'] == 1
    assert result['confirmation_projection_cpu_seconds'] == pytest.approx(1178.4)
    screens['L92'][0]['cpu_seconds'] = 100
    assert not measure.selected_projection(screens, winners, historical)['feasible']


@pytest.mark.parametrize('phase,edge', [('startup_calibration', 170), ('startup_screen', 3390), ('confirmation', 5390)])
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
    assert len(monitor.expected_rows('complete', 'confirm/flash5_dark')) == 4
    assert 2 * 67 + 4 == 138
    assert 2 * 65 * 32 + 4 * 512 == 6208
    assert 6208 + 2 * 2 * 2 + 2 == 6218


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
def test_af_dependency_is_clean_terminal_not_success(tmp_path, monkeypatch, status):
    monkeypatch.setattr(prepare, 'STUDY', tmp_path)
    monkeypatch.setattr(prepare, 'ROOT', tmp_path)
    budget_name = 'outputs/autonomous_prediction_continuation_20261014/budget.json'
    monitor.save(tmp_path / budget_name, {'status': status, 'running': {}, 'queued': [], 'cleanup_error': None})
    seeds = {'screen': list(range(100, 132)), 'confirm': list(range(1000, 1512)), 'calibration': [2000, 2001]}
    monitor.save(tmp_path / 'seed_audit.json', {'status': 'passed', 'seeds': seeds})
    reg = {'status': 'registered', 'roles': measure.ROLES,
           'panel_policy': 'entire_Y_panels_unchanged_regardless_of_AF_outcomes', 'seeds': seeds,
           'seed_audit_sha256': monitor.sha(tmp_path / 'seed_audit.json'),
           'AF_terminal': {'file_pins': {budget_name: monitor.sha(tmp_path / budget_name)}}}
    monitor.save(tmp_path / 'registration.json', reg)
    assert prepare.registration()[0] == reg
    monitor.save(tmp_path / budget_name, {'status': status, 'running': {'123': 'worker'}})
    reg['AF_terminal']['file_pins'][budget_name] = monitor.sha(tmp_path / budget_name)
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
    for name in ('protocol.json', 'startup_identity.json', 'analysis_result/summary.json',
                 'analysis/genetic_replay.py', 'analysis/genetic_replay.json'):
        assert prepare.historical_source(name).is_file()
    protocol = prepare.read(prepare.Y / 'protocol.json')
    assert all((prepare.Y / name).is_file() for name in protocol['file_pins'])
    assert not (STUDY / 'inputs').exists()


def test_exact_AD_world_and_AC_single_coordinate_difference():
    from dataclasses import asdict

    from world_contract import AC_PROTOCOL_SHA256, AD_PROTOCOL_SHA256, check_world

    from src.life import spec
    assert prepare.sha(prepare.AD / 'protocol.json') == AD_PROTOCOL_SHA256
    assert prepare.sha(prepare.AC / 'protocol.json') == AC_PROTOCOL_SHA256
    dark = prepare.read(prepare.AD / 'protocol.json')['worlds']['flash5_dark']['production']['world']
    dim = prepare.read(prepare.AC / 'protocol.json')['worlds']['flash']
    assert {k for k in dark if dark[k] != dim[k]} == {'visibility_low'}
    assert (dim['visibility_low'], dark['visibility_low']) == (.25, 0.)
    world = spec.world('catch_speck_flash5_dim25_l4', T=1024, visibility_low=0.)
    check_world(asdict(world), dark)
    packed = spec.V4.pack_world(world)
    assert packed.dtype == np.float64 and packed.shape == (70,)
    assert packed.tobytes() == np.asarray([dark[k] for k in spec.V4.WORLD_KEYS], dtype=np.float64).tobytes()
    for field, value in [('visibility_low', .25), ('R_cap', 1000), ('v_t', .3)]:
        with pytest.raises(ValueError):
            check_world(dict(dark, **{field: value}), dark)


def test_synthetic_abi4_accounting_retains_extinction_and_guards():
    import scoring

    from src.life import spec
    from src.life.evaluate import LifeEvaluator
    world = spec.World(**prepare.read(prepare.AD / 'protocol.json')['worlds']['flash5_dark']['production']['world'])
    abi = spec.V4
    # Fabricated ledger values only; no genome, engine evaluation or actual seed namespace.
    ledger = np.zeros((3, 58), dtype=np.float64)
    ledger[:, abi.L['t_end']] = [1024, 600, 800]
    ledger[:, abi.L['status']] = [0, spec.STATUS['extinct'], spec.STATUS['guard_events']]
    ledger[1, abi.L['t_ext']] = 600
    ledger[:, abi.L['captures']] = [3, 2, 1]
    ledger[:, abi.L['low_light_captures']] = [2, 1, 1]
    ledger[:, abi.L['live_time']] = [1024, 600, 800]
    ledger[:, abi.L['income']] = world.R_cap * ledger[:, abi.L['captures']]
    ledger[:, abi.L['cost']] = abi.column_cost(ledger, world)
    ledger[:, abi.L['guard_charge']] = abi.guard_charge(ledger, world)
    ledger[:, abi.L['net']] = ledger[:, abi.L['income']] - ledger[:, abi.L['cost']] - ledger[:, abi.L['guard_charge']]
    ledger[:, abi.L['F']] = abi.fitness(ledger, world)
    evaluator = LifeEvaluator.__new__(LifeEvaluator)
    evaluator.abi, evaluator.extinct_charge = abi, True
    columns = scoring.columns_from_ledger(ledger, world, [1, 2, 3], evaluator)
    assert len(columns) == 61 and 'low_light_captures' in columns
    assert columns['F'][1] == columns['F_kernel'][1] - .02 * (1024 - 600) / 1024
    assert columns['guard_charge'][2] > 0
    broken = ledger.copy()
    broken[0, abi.L['net']] += 1
    with pytest.raises(ValueError, match='accountant mismatch'):
        scoring.columns_from_ledger(broken, world, [1, 2, 3], evaluator)


def test_actual_AC_timing_metadata_paths():
    assert prepare.cost_source('budget.json') == prepare.AC / 'operations/budget.json'
    assert prepare.read(prepare.cost_source('budget.json'))['status'] == 'complete'
    for bg in measure.PARENTS:
        index_path = prepare.AC / f'measurement/screen/{bg}/row_index.json'
        index = prepare.read(index_path)
        assert all(f'screen/row_{i:04d}.npz' in index for i in range(65))
        assert all((index_path.parent / f'screen/row_{i:04d}.npz').is_file() for i in range(65))


def test_exact_retained_Y_ABI4_scoring_bytes():
    assert (STUDY / 'scoring.py').read_bytes() == (ROOT / 'outputs/autonomous_visibility_gradient_20261014/scoring.py').read_bytes()
