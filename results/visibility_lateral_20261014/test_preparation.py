"""Focused source/synthetic AA checks. No compiler, kernel, mutation or real endpoint calls."""
import ast
import hashlib
import json
from dataclasses import asdict
from pathlib import Path
from types import SimpleNamespace

import numpy as np
import prepare as P
import pytest
import run_budgeted as B
import scoring as S

import measure as M
from src.life import build, spec
from src.life.evaluate import LifeEvaluator


def ledger(n=128):
    data = np.zeros((n, 58), np.float64)
    for key, value in {'n_end': 5, 'n_peak': 5, 'n_S_end': 2, 'n_M_end': 2, 'n_H_end': 1,
                       'live_time': 2400, 'live_S': 960, 'live_M': 960, 'live_H': 480,
                       'cost': 48, 'net': -48, 'F': -.1, 'last_birth': 500, 't_end': 1024,
                       't_ext': -1, 'path': 100}.items():
        data[:, spec.V4.L[key]] = value
    return data


def evaluator():
    obj = SimpleNamespace(abi=spec.V4, extinct_charge=True, has_envelope=False)
    obj.columns = lambda *args: LifeEvaluator.columns(obj, *args)
    return obj


def rows(n=128):
    row = S.columns_from_ledger(ledger(n), P.worlds()['freeze'], list(range(n)), evaluator())
    return {c: [{k: v.copy() for k, v in row.items()} for _ in M.LABELS] for c in M.CONDITIONS}


def test_late_window_scoring_keeps_terminal_five_without_initial_census():
    r = rows()
    assert M.validate_frozen(r)['coverage'][0]['complete_paired_lives'] == 128
    assert np.all(r['freeze'][0]['births'] == 0)
    assert np.all(r['freeze'][0]['n_end'] == 5)
    assert np.all(r['freeze'][0]['window'] == 480)


@pytest.mark.parametrize('key', ['births', 'deaths', 'kills', 'claims', 'rejects', 'rejects_wall'])
def test_frozen_structural_changes_fail(key):
    r = rows(2)
    r['freeze'][0][key][0] = 1
    with pytest.raises(ValueError, match='structure'):
        M.validate_frozen(r)


def test_matching_sizes_and_plane_integrals_required():
    r = rows(2)
    r['freeze+lateral_off'][0]['live_H'][0] -= 1
    with pytest.raises(ValueError, match='cell-time'):
        M.validate_frozen(r)


def test_guarded_rows_excluded_only_from_structural_equality():
    r = rows(2)
    r['freeze+lateral_off'][0]['status'][0] = spec.STATUS['guard_events']
    r['freeze+lateral_off'][0]['live_H'][0] = 0
    assert M.validate_frozen(r)['coverage'][0]['complete_paired_lives'] == 1
    assert len(M.contrasts({c: np.stack([x['F'] for x in r[c]]) for c in M.CONDITIONS})) == 36


def test_interaction_direction_and_whole_seed_subtraction():
    values = {c: np.zeros((6, 2)) for c in M.CONDITIONS}
    values['freeze'][4] = [5, 7]
    values['freeze'][2] = [2, 1]
    values['freeze+lateral_off'][4] = [1, 2]
    values['freeze+lateral_off'][2] = [0, 1]
    out = M.contrasts(values)
    np.testing.assert_array_equal(out['primary__Z_D90_minus_Y_D90__added_lateral_dependence'], [2, 5])
    assert len(out) == 36


@pytest.mark.parametrize('value', [-1, 0, float('nan'), float('inf')])
def test_invalid_cost_is_not_feasibility(value):
    rates = dict.fromkeys(P.LABELS, .2)
    rates['Z_L92'] = value
    with pytest.raises(ValueError):
        P.cost_projection(rates)


def test_cost_gate_and_stop_margin():
    rate = (1190 - 180) / (1.5 * 3 * 128 * 6)
    assert P.cost_projection(dict.fromkeys(P.LABELS, rate))['feasible']
    assert not P.cost_projection(dict.fromkeys(P.LABELS, rate + .001))['feasible']
    assert B.budget_reason(1189.9) is None
    assert B.budget_reason(1190) == 'cpu_budget_exhausted'


def test_world_changes_are_only_existing_measurement_fields():
    original = asdict(spec.world('catch_speck_blink20_20_l4', T=1024))
    for condition, world in P.worlds().items():
        delta = {k: v for k, v in asdict(world).items() if v != original[k]}
        expected = {'t_fork': 512, 't_open': 544}
        if condition != 'normal':
            expected['fork_flags'] = 16 if condition == 'freeze' else 2064
        assert delta == expected


def test_exactly_one_standard_identity_call_and_no_prepare_generation():
    calls = []
    for name in ('prepare.py', 'measure.py', 'run_budgeted.py'):
        tree = ast.parse((Path(__file__).parent / name).read_text())
        calls += [(name, n.func.id) for n in ast.walk(tree) if isinstance(n, ast.Call)
                  and isinstance(n.func, ast.Name) and n.func.id in ('numerical_identity', 'setup', 'fill')]
    assert calls == [('measure.py', 'numerical_identity')]


def test_prepare_requires_registration_before_any_endpoint_read(tmp_path, monkeypatch):
    monkeypatch.setattr(P, 'STUDY', tmp_path)
    monkeypatch.setattr(P, 'Z', tmp_path / 'absent_Z')
    with pytest.raises(FileNotFoundError, match='registration.json'):
        P.prepare()
    assert not (tmp_path / 'inputs').exists()


def test_parent_guard_accepts_owned_startup_before_running_map_publication(tmp_path, monkeypatch):
    monkeypatch.setattr(M, 'STUDY', tmp_path)
    monkeypatch.setenv('CELLDEV_LATERAL_MONITOR_PID', '900')
    monkeypatch.delenv('CELLDEV_THREADS_FILE', raising=False)
    monkeypatch.setattr(M.os, 'getppid', lambda: 900)
    monkeypatch.setattr(M.os, 'getpid', lambda: 901)
    monkeypatch.setattr(M.os, 'getpgrp', lambda: 901)
    monkeypatch.setattr(M.os, 'getsid', lambda x: 901)
    monkeypatch.setattr(B, 'process_identity', lambda pid: {'pid': pid, 'ppid': 1, 'pgid': 900, 'start_ticks': 55})
    (tmp_path / 'ready.json').write_text('{}')
    (tmp_path / 'attempt.json').write_text(json.dumps({'monitor': {'pid': 900, 'start_ticks': 55},
                                                     'ready_sha256': B.sha(tmp_path / 'ready.json')}))
    (tmp_path / 'budget.json').write_text(json.dumps({'status': 'running', 'phase': 'measurement', 'running': {}}))
    M.parent_check()
    monkeypatch.setattr(M.os, 'getppid', lambda: 902)
    with pytest.raises(ValueError, match='direct child'):
        M.parent_check()


def test_all_eighteen_rows_serialize_with_mocked_kernel_only(tmp_path, monkeypatch):
    """Exercise the actual row writer/report with synthetic ledgers, never the engine."""
    import numerical
    from omegaconf import OmegaConf

    import src.life.evaluate as E
    from src import checkpoint
    from src.genome import Layout

    identities, raw_calls = [], []
    genomes = np.zeros((6, 875), np.float32)  # Synthetic serialization fixture, no organism generation.
    raw = {label: hashlib.sha256(g.tobytes()).hexdigest() for label, g in zip(M.LABELS, genomes)}
    (tmp_path / 'protocol.json').write_text('{}')
    np.savez(tmp_path / 'genotypes.npz', genomes=genomes, labels=np.asarray(M.LABELS))
    protocol = {'numerical_identity': {}, 'expected_numerical_identity': {'synthetic': True},
        'genotypes_file': 'genotypes.npz', 'genotype_sha256': raw, 'layout_file': 'unused', 'config_file': 'unused',
        'unmodified_world': asdict(spec.world('catch_speck_blink20_20_l4', T=1024)),
        'worlds': {k: asdict(v) for k, v in P.worlds().items()}, 'seeds': list(range(9000, 9128))}
    monkeypatch.setattr(M, 'STUDY', tmp_path)
    monkeypatch.setattr(B, 'check_protocol', lambda: protocol)
    monkeypatch.setattr(B, 'check_ready', lambda: {})
    monkeypatch.setattr(M, 'parent_check', lambda: None)
    monkeypatch.setattr(numerical, 'check', lambda x: None)
    monkeypatch.setattr(checkpoint, 'numerical_identity', lambda: identities.append('golden-pair') or {'synthetic': True})
    monkeypatch.setattr(Layout, 'load', lambda p: (None, None))
    monkeypatch.setattr(OmegaConf, 'load', lambda p: None)
    ev = evaluator()
    ev.world = lambda: spec.world('catch_speck_blink20_20_l4', T=1024)
    monkeypatch.setattr(E, 'LifeEvaluator', lambda *args: ev)

    def fake_run(world, seeds, **kwargs):
        raw_calls.append((world.fork_flags, world.t_open, len(seeds), kwargs['threads']))
        return build.Lives(ledger(), np.zeros((128, 5), np.uint64), abi=spec.V4)

    monkeypatch.setattr(S.build, 'run', fake_run)
    M.measure()
    assert identities == ['golden-pair']
    assert raw_calls == [(flags, 544, 128, 2) for flags in (0, 16, 2064) for _ in range(6)]
    report = json.loads((tmp_path / 'measurement/report.json').read_text())
    assert report['genome_lives'] == 2304 and report['startup_validation_genome_lives'] == 2
    assert len(report['contrasts']['F']) == 36
    index = json.loads((tmp_path / 'measurement/row_index.json').read_text())
    assert len(index) == 18
    with np.load(tmp_path / 'measurement/freeze/row_0000.npz') as row:
        assert row['ledger'].shape == (128, 58)
        assert json.loads(str(row['identity']))['condition'] == 'freeze'
        assert row['window'].tolist() == [480.] * 128
