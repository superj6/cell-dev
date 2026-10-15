"""Focused source-only regressions; no genetic generation, kernel build or life."""
import ast
import importlib.util
import json
import sys
from pathlib import Path

import pytest

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[1]
sys.path.insert(0, str(HERE))


def load(name, file):
    specification = importlib.util.spec_from_file_location(name, HERE / file)
    module = importlib.util.module_from_spec(specification)
    sys.modules[name] = module
    specification.loader.exec_module(module)
    return module


P = load('z_prepare', 'prepare.py')
B = load('run_budgeted', 'run_budgeted.py')
M = load('z_measure', 'measure.py')


def test_exact_reviewed_helpers():
    y = ROOT / 'outputs/autonomous_visibility_gradient_20261014'
    for name in ('scoring.py', 'numerical.py'):
        assert (HERE / name).read_bytes() == (y / name).read_bytes()


def test_config_clears_decoy_and_suppresses_extra_diagnostics():
    cfg = P.search_config(0, 'synthetic-unused.json')
    assert cfg.life.abi == 4
    assert cfg.life.world == 'catch_speck_blink20_20_l4'
    assert cfg.life.T == 1024 and cfg.life.T_choices is None
    assert dict(cfg.world) == {} and dict(cfg.costs_life) == {}
    assert cfg.life.flags == [] and cfg.life.freeze_frac is None and cfg.life.t_open == 0
    assert not cfg.envelope.enabled
    assert cfg.life.heldout == [] and cfg.life.size_curve == []
    assert cfg.clones.every == 0 and cfg.clones.conditions == []
    assert (cfg.life.final_top, cfg.life.final_lives, cfg.life.final_fork_lives) == (1, 2, 0)
    assert (cfg.evolve.mu, cfg.evolve.lam, cfg.life.lives, cfg.evolve.recheck_k, cfg.evolve.recheck_lives) == (32, 224, 3, 64, 4)
    assert cfg.evolve.recheck_key == 'all' and cfg.evolve.random_ties
    assert (cfg.evolve.n_mut, cfg.evolve.p_cell, cfg.evolve.n_mut_scale) == (2, .5, True)
    assert (cfg.evolve.dup_rate, cfg.evolve.del_rate, cfg.evolve.dup_split) == (0, 0, False)
    assert cfg.evolve.breeding == 'sex' and cfg.evolve.generations == 4
    assert cfg.logging.lineage == 'all' and cfg.logging.checkpoint_every == 1
    assert cfg.threads == 2 and cfg.life.extinct_charge and cfg.life.fast_kernel
    selection = 2 * cfg.evolve.generations * ((cfg.evolve.mu + cfg.evolve.lam) * cfg.life.lives
                                            + cfg.evolve.recheck_k * cfg.evolve.recheck_lives)
    periodic = 2 * 2 * cfg.life.valid_lives
    final = 2 * 3 * cfg.life.final_lives
    assert (selection, periodic, final, selection + periodic + final + 6 * 512 + 6) == (8192, 64, 12, 11346)


def test_prepare_guard_precedes_runtime_access_or_generation(monkeypatch, tmp_path):
    monkeypatch.setattr(P, 'STUDY', tmp_path)
    monkeypatch.setattr(P, 'Y', tmp_path / 'forbidden_Y')
    with pytest.raises(FileNotFoundError, match='registration.json'):
        P.prepare()
    assert list(tmp_path.iterdir()) == []


def test_prepare_rejects_prior_population_claim(monkeypatch, tmp_path):
    monkeypatch.setattr(P, 'STUDY', tmp_path)
    (tmp_path / 'generation_claim.json').write_text('{}')
    with pytest.raises(ValueError, match='first preparation'):
        P.prepare()


def test_cost_projection_uses_worse_developed_start():
    rates = {'D90': {'founder': .2, 'Y_start': .1}, 'L92': {'founder': .1, 'Y_start': .3}}
    result = P.cost_projection(rates)
    assert result['startup_search_projection'] == 180 + 1.5 * 4134 * .5
    assert result['confirmation_projection'] == pytest.approx(180 + 1.5 * 512 * 1.7)
    assert result['feasible']
    assert not P.cost_projection({p: {'founder': 1., 'Y_start': 1.} for p in P.PARENTS})['feasible']


@pytest.mark.parametrize('bad', [0., -1., float('inf'), float('nan')])
def test_invalid_cost_evidence(bad):
    rates = {p: {'founder': .1, 'Y_start': .1} for p in P.PARENTS}
    rates['D90']['founder'] = bad
    with pytest.raises(ValueError, match='positive measured'):
        P.cost_projection(rates)


def state():
    return {'generation': 4, 'curves': [{'gen': g, 'pop_invalid': 0., 'pop_mismatch': 0.,
                                        'recheck_invalid': 0.} for g in range(4)]}


def test_complete_search_health():
    assert M.validate_search_state(state()) == {'pop_invalid': 0., 'pop_mismatch': 0., 'recheck_invalid': 0.}


@pytest.mark.parametrize('field', ['pop_invalid', 'pop_mismatch', 'recheck_invalid'])
@pytest.mark.parametrize('bad', [1., float('nan')])
def test_failed_search_health(field, bad):
    value = state()
    value['curves'][2][field] = bad
    with pytest.raises(ValueError, match='invalid or mismatched'):
        M.validate_search_state(value)


def test_incomplete_or_unordered_search():
    value = state()
    value['generation'] = 3
    with pytest.raises(ValueError, match='incomplete'):
        M.validate_search_state(value)
    value = state()
    value['curves'].reverse()
    with pytest.raises(ValueError, match='ordered'):
        M.validate_search_state(value)


@pytest.mark.parametrize('phase,threshold,reason', [('search', 3590, 'search_reserve_limit'),
                                                  ('confirmation', 7190, 'cpu_budget_exhausted')])
def test_reserved_budget_thresholds(phase, threshold, reason):
    assert B.budget_reason(phase, threshold - .001) is None
    assert B.budget_reason(phase, threshold) == reason


def test_owned_group_lifecycle_is_unchanged_U():
    def functions(path):
        return {node.name: ast.dump(node, include_attributes=False) for node in ast.parse(path.read_text()).body
                if isinstance(node, ast.FunctionDef)}
    old = functions(ROOT / 'results/decoy_evolution_20261014/run_budgeted.py')
    new = functions(HERE / 'run_budgeted.py')
    for name in ('own_cpu', 'child_cpu', 'proc_table', 'active_cpu', 'consumed_cpu', 'child_limit',
                 'send_signal', 'enable_subreaper', 'cleanup_group', 'cleanup', 'interrupt', 'process_identity'):
        assert new[name] == old[name], name


def test_exactly_one_confirmation_identity_call_and_no_prepass():
    def calls(path):
        return [node for node in ast.walk(ast.parse(path.read_text())) if isinstance(node, ast.Call)
                and isinstance(node.func, ast.Attribute) and node.func.attr == 'numerical_identity']
    assert len(calls(HERE / 'measure.py')) == 1
    assert not calls(HERE / 'prepare.py') and not calls(HERE / 'run_budgeted.py')


def ownership(monkeypatch, tmp_path):
    monkeypatch.setattr(M, 'STUDY', tmp_path)
    monkeypatch.setenv('CELLDEV_CONTINUATION_MONITOR_PID', '42')
    monkeypatch.delenv('CELLDEV_THREADS_FILE', raising=False)
    monkeypatch.setattr(M.os, 'getppid', lambda: 42)
    monkeypatch.setattr(M.os, 'getpid', lambda: 43)
    monkeypatch.setattr(M.os, 'getpgrp', lambda: 43)
    monkeypatch.setattr(M.os, 'getsid', lambda _: 43)
    monkeypatch.setattr(B, 'process_identity', lambda _: {'pid': 42, 'start_ticks': 90})
    (tmp_path / 'ready.json').write_text('{}')
    (tmp_path / 'attempt.json').write_text(json.dumps({'monitor': {'pid': 42, 'start_ticks': 90},
                                                      'ready_sha256': B.sha(tmp_path / 'ready.json')}))
    (tmp_path / 'budget.json').write_text(json.dumps({'status': 'running', 'phase': 'confirmation', 'running': {}}))


def test_confirmation_allows_startup_before_pid_publication(monkeypatch, tmp_path):
    ownership(monkeypatch, tmp_path)
    M.parent_check()


@pytest.mark.parametrize('corruption', ['parent', 'start_ticks', 'phase', 'group', 'elastic'])
def test_direct_or_changed_confirmation_ownership_rejected(monkeypatch, tmp_path, corruption):
    ownership(monkeypatch, tmp_path)
    if corruption == 'parent':
        monkeypatch.setattr(M.os, 'getppid', lambda: 99)
    elif corruption == 'start_ticks':
        monkeypatch.setattr(B, 'process_identity', lambda _: {'pid': 42, 'start_ticks': 91})
    elif corruption == 'phase':
        (tmp_path / 'budget.json').write_text(json.dumps({'status': 'running', 'phase': 'search'}))
    elif corruption == 'group':
        monkeypatch.setattr(M.os, 'getpgrp', lambda: 99)
    else:
        monkeypatch.setenv('CELLDEV_THREADS_FILE', 'unexpected')
    with pytest.raises(ValueError):
        M.parent_check()
