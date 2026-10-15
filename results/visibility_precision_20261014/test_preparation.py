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


P = load('ab_prepare', 'prepare.py')
B = load('run_budgeted', 'run_budgeted.py')
M = load('ab_measure', 'measure.py')


def test_exact_reviewed_helpers():
    y = ROOT / 'outputs/autonomous_visibility_continuation_20261014'
    for name in ('scoring.py', 'numerical.py'):
        assert (HERE / name).read_bytes() == (y / name).read_bytes()


@pytest.mark.parametrize('policy,generations,initial,recheck', [('depth', 4, 3, 4), ('precision', 1, 12, 16)])
def test_config_keeps_physics_and_exact_policy(policy, generations, initial, recheck):
    from omegaconf import OmegaConf
    cfg = P.search_config('D90_' + policy, 0, 'synthetic-unused.json')
    baseline = OmegaConf.to_container(OmegaConf.load(P.TEMPLATE), resolve=True)
    actual = OmegaConf.to_container(cfg, resolve=True)
    expected_changes = {('seed',): 0, ('threads',): 2,
        ('evolve', 'generations'): generations, ('evolve', 'recheck_lives'): recheck,
        ('evolve', 'seed_genome'): str(P.STUDY / 'synthetic-unused.json'), ('life', 'lives'): initial,
        ('life', 'control'): 'blink_precision_allocation_' + policy,
        ('logging', 'output_dir'): str(P.STUDY / 'runs' / ('D90_' + policy))}
    for keys, value in expected_changes.items():
        cursor = baseline
        for key in keys[:-1]:
            cursor = cursor[key]
        cursor[keys[-1]] = value
    assert actual == baseline
    assert cfg.life.abi == 4 and cfg.life.T == 1024 and cfg.life.T_choices is None
    assert (cfg.evolve.mu, cfg.evolve.lam, cfg.evolve.recheck_k) == (32, 224, 64)
    assert cfg.evolve.recheck_key == 'all' and cfg.evolve.random_ties
    assert cfg.life.heldout == [] and cfg.life.size_curve == []
    assert cfg.clones.every == 0 and cfg.clones.conditions == [] and not cfg.envelope.enabled
    assert (cfg.life.final_top, cfg.life.final_lives, cfg.life.final_fork_lives, cfg.life.valid_lives) == (1, 2, 0, 16)
    selection = generations * (256 * initial + 64 * recheck)
    periodic = sum(g % 4 == 0 or g == generations - 1 for g in range(generations)) * 16
    assert selection == 4096
    assert periodic == (32 if policy == 'depth' else 16)
    assert 2 * ((4096 + 32 + 6) + (4096 + 16 + 6)) + 6 * 512 + 10 == 19586


def test_prepare_guard_precedes_runtime_access_or_generation(monkeypatch, tmp_path):
    monkeypatch.setattr(P, 'STUDY', tmp_path)
    monkeypatch.setattr(P, 'Z', tmp_path / 'forbidden_Z')
    with pytest.raises(FileNotFoundError, match='registration.json'):
        P.prepare()
    assert list(tmp_path.iterdir()) == []


def test_prepare_rejects_prior_population_claim(monkeypatch, tmp_path):
    monkeypatch.setattr(P, 'STUDY', tmp_path)
    (tmp_path / 'generation_claim.json').write_text('{}')
    with pytest.raises(ValueError, match='first preparation'):
        P.prepare()


def test_cost_projection_uses_all_six_lineage_costs():
    rates = dict(zip(P.Z_LABELS, (.2, .1, .1, .3, .05, .1)))
    result = P.cost_projection(rates)
    assert result['lineage_maxima'] == {'D90': .2, 'L92': .3}
    assert result['startup_search_projection'] == 180 + 1.5 * 8252 * .5
    assert result['confirmation_projection'] == pytest.approx(180 + 1.5 * 512 * 1.15)
    assert result['feasible']
    assert not P.cost_projection({p: 1. for p in P.Z_LABELS})['feasible']


@pytest.mark.parametrize('bad', [0., -1., float('inf'), float('nan')])
def test_invalid_cost_evidence(bad):
    rates = {p: .1 for p in P.Z_LABELS}
    rates['D90'] = bad
    with pytest.raises(ValueError, match='positive actual'):
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


@pytest.mark.parametrize('phase,threshold,reason', [('search', 7190, 'search_reserve_limit'),
                                                  ('confirmation', 8990, 'cpu_budget_exhausted')])
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
    monkeypatch.setenv('CELLDEV_PRECISION_MONITOR_PID', '42')
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


def test_planned_namespace_shape_and_intentional_overlap(monkeypatch):
    import types
    fake = types.ModuleType('src.life.evaluate')
    fake.life_seed = lambda seed, purpose, g, j: (seed, purpose, g, j)
    monkeypatch.setitem(sys.modules, 'src.life.evaluate', fake)
    a = P.planned_search_seeds('D90_depth', 0)
    b = P.planned_search_seeds('D90_precision', 0)
    assert (len(a), len(b), len(set(a) & set(b)), len(set(a) | set(b))) == (64, 48, 27, 85)
    assert {g for _, purpose, g, _ in a if purpose == 'valid'} == {0, 3}
    assert {g for _, purpose, g, _ in b if purpose == 'valid'} == {0}
    assert not (set(a) | set(b)) & set(P.planned_search_seeds('L92_depth', 1))


def test_precise_endpoint_requires_one_complete_generation():
    value = state()
    value['generation'], value['curves'] = 1, value['curves'][:1]
    assert M.validate_search_state(value, 1)['pop_invalid'] == 0
    with pytest.raises(ValueError, match='incomplete'):
        M.validate_search_state(value, 4)


def synthetic_cohort():
    copies = [{'id': i, 'parent': 0, 'ops': {'mut': []}} for i in range(1, 32)]
    children = [{'id': i, 'pa': i % 32, 'pb': (i + 1) % 32, 'mask': '0', 'ops': {'mut': []},
                 'fitness': float(i), 'kept': False} for i in range(32, 256)]
    return [{'event': 'founders', 'ids': [0], 'copies': copies}, {'gen': 0, 'children': children}]


def cohort_fixture(monkeypatch, tmp_path):
    monkeypatch.setattr(M, 'STUDY', tmp_path)
    rows = synthetic_cohort()
    initial = {'backgrounds': {p: {'copies': rows[0]['copies'], 'population_raw_sha256': p} for p in P.PARENTS},
               'runs': {run: run.split('_')[0] for run in P.RUNS}}
    (tmp_path / 'initialization.json').write_text(json.dumps(initial))
    protocol = {'paired_native_seeds': {'D90': 0, 'L92': 1},
                'run_settings': {run: P.settings(run, int(run.startswith('L92'))) for run in P.RUNS}}
    for run in P.RUNS:
        path = tmp_path / 'runs' / run / 'lineage.jsonl'
        path.parent.mkdir(parents=True)
        path.write_text('\n'.join(json.dumps(row) for row in rows) + '\n')
    return protocol


def test_matched_cohort_ignores_selection_outcomes(monkeypatch, tmp_path):
    protocol = cohort_fixture(monkeypatch, tmp_path)
    path = tmp_path / 'runs/D90_precision/lineage.jsonl'
    rows = [json.loads(line) for line in path.read_text().splitlines()]
    rows[1]['children'][0].update(fitness=-999., kept=True)
    path.write_text('\n'.join(json.dumps(row) for row in rows))
    proof = M.check_matched_first_cohorts(protocol)
    assert set(proof) == {'D90', 'L92'} and proof['D90']['offspring_count'] == 224


@pytest.mark.parametrize('field,value', [('pa', 31), ('mask', '1'), ('ops', {'mut': [1]}), ('id', 900)])
def test_changed_first_genetics_rejected(monkeypatch, tmp_path, field, value):
    protocol = cohort_fixture(monkeypatch, tmp_path)
    path = tmp_path / 'runs/D90_precision/lineage.jsonl'
    rows = [json.loads(line) for line in path.read_text().splitlines()]
    rows[1]['children'][0][field] = value
    path.write_text('\n'.join(json.dumps(row) for row in rows))
    with pytest.raises(ValueError):
        M.check_matched_first_cohorts(protocol)


def test_changed_initial_fill_rejected(monkeypatch, tmp_path):
    protocol = cohort_fixture(monkeypatch, tmp_path)
    path = tmp_path / 'initialization.json'
    item = json.loads(path.read_text())
    item['backgrounds']['D90']['copies'][0]['parent'] = 20
    path.write_text(json.dumps(item))
    with pytest.raises(ValueError, match='prepared matched'):
        M.check_matched_first_cohorts(protocol)
