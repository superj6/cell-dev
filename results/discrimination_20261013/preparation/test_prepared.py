"""Preparation, atomic resume and accounting tests use synthetic arrays/mocked processes; no life simulations."""
import importlib.util
import json
from pathlib import Path
from types import SimpleNamespace

import numpy as np
import pytest


def module(name):
    path = Path(__file__).with_name(name + ".py")
    spec = importlib.util.spec_from_file_location("discrimination_" + name, path)
    result = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(result)
    return result


def synthetic(run, world, *, captures=(3, 4), poison=(0, 1), controller=False):
    n = len(captures)
    ledger = np.zeros((n, run.spec.V3.LEDGER_SIZE), dtype=np.float64)
    for key, value in {"captures": captures, "b2_clicks": poison, "clicks": np.array(captures) + poison,
                       "live_time": 56 * world.T, "n_end": 56, "t_end": world.T,
                       "income": world.R_cap * np.array(captures)}.items():
        ledger[:, run.spec.V3.L[key]] = value
    ledger[:, run.spec.V3.L["cost"]] = run.spec.V3.column_cost(ledger, world)
    ledger[:, run.spec.V3.L["F"]] = run.spec.V3.fitness(ledger, world)
    result = run.build.Lives(ledger, np.zeros((n, run.spec.V3.HASH_SIZE), dtype=np.uint64), abi=run.spec.V3)
    if controller:
        result.diag, result.latency = np.zeros((n, 16)), np.full(n, world.d0)
    return result


def row_identity(run, *, controller=False):
    return {"manifest": {"test_only": True}, "seeds": [51_040_100, 51_040_101],
            "candidate": {"name": "synthetic", "kind": "information" if controller else "frozen_reflex"}}


def test_prepared_dry_run_stays_out_of_simulator(capsys, monkeypatch):
    run = module("measure")
    monkeypatch.setattr(run.build, "run", lambda *a, **k: pytest.fail("dry run simulated a life"))
    monkeypatch.setattr("sys.argv", ["measure"])
    run.main()
    result = json.loads(capsys.readouterr().out)
    assert (result["status"], result["candidate_lives"], result["threads"]) == ("dry_run", 3584, 2)


def test_candidate_set_exactly_matches_audited_runner(tmp_path, monkeypatch):
    run = module("measure")
    from scripts import taskvar_measure as audited

    seen = []
    world = run.spec.world("catch_speck_l4", T=1024)

    def tissue(body, ws, seeds, **kwargs):
        seen.append({"footprint": body[0], "knobs": body[1]})
        return synthetic(run, world)

    def controller(cid, params, fp, ws, seeds, **kwargs):
        seen.append({"footprint": fp, "params": params, "controller_id": cid})
        return synthetic(run, world, controller=True)

    fake = SimpleNamespace(
        WorldSpec=lambda name, over: SimpleNamespace(preset="catch_speck_l4", over=over, x={}),
        spec=run.spec, reflex=lambda shape, params: (shape, params), footprint=lambda shape: shape,
        tissue_run=tissue, ctl_run=controller)

    def compile_fake(library, source, fast):
        library.write_bytes(b"synthetic test library")
        return fake

    monkeypatch.setattr(audited, "compile_measurement", compile_fake)
    audited.measurement(run.CONFIG, tmp_path, 2, 1024, 4, 2, run.AUDIT)
    config = json.loads(run.CONFIG.read_text())
    expected = run.candidates(config)
    assert len(seen) == len(expected) == 7
    for received, candidate in zip(seen, expected):
        assert all(candidate[key] == value for key, value in received.items())
    assert expected[-1]["params"][25] == 0 and expected[-2]["params"][25] == 1
    assert [i for i, (a, b) in enumerate(zip(expected[-1]["params"], expected[-2]["params"])) if a != b] == [25]


def test_atomic_checkpoint_resumes_without_repeating_candidate(tmp_path):
    run = module("measure")
    world = run.spec.world("catch_speck_l4", T=1024, b2_value=-50)
    identity = row_identity(run, controller=True)
    path = tmp_path / "full"
    first = run.checkpoint_row(path, identity, world, lambda: synthetic(run, world, controller=True))
    second = run.checkpoint_row(path, identity, world, lambda: pytest.fail("repeated committed candidate"))
    assert first["ledger"].tobytes() == second["ledger"].tobytes()
    assert not (tmp_path / "full.pending").exists()
    changed = dict(identity, seeds=list(reversed(identity["seeds"])))
    with pytest.raises(ValueError, match="bytes or identity"):
        run.load_row(path, changed, world)


def test_row_corruption_is_rejected_even_when_timing_remains_finite(tmp_path):
    run = module("measure")
    world = run.spec.world("catch_speck_l4", T=1024, b2_value=-50)
    identity, path = row_identity(run), tmp_path / "frozen"
    arrays = run.checkpoint_row(path, identity, world, lambda: synthetic(run, world))
    arrays["cpu_seconds"] = np.asarray(0.01)
    np.savez_compressed(path / "row.npz", **arrays)
    with pytest.raises(ValueError, match="checkpoint bytes"):
        run.load_row(path, identity, world)


def test_full_ledger_validation_and_income_cost_decomposition(tmp_path):
    run = module("measure")
    world = run.spec.world("catch_speck_l4", T=1024, b2_value=-50)
    identity = row_identity(run)
    full = run.checkpoint_row(tmp_path / "a", identity, world,
                              lambda: synthetic(run, world, captures=(5, 6), poison=(0, 0)))
    ref = run.checkpoint_row(tmp_path / "b", identity, world,
                             lambda: synthetic(run, world, captures=(3, 4), poison=(1, 1)))
    report = run.comparison(full, ref, world)
    assert report["F"] == {"mean": 1050 / 1024, "se": 0, "n": 2}
    assert sum(piece["mean"] for piece in report["fitness_pieces"].values()) == report["F"]["mean"]
    full["ledger"][0, run.spec.V3.L["cost"]] += 1
    with pytest.raises(ValueError, match="cost differs"):
        run.validate_arrays(full, identity, world)


def test_invalid_candidate_never_becomes_a_committed_checkpoint(tmp_path):
    run = module("measure")
    world = run.spec.world("catch_speck_l4", T=1024)
    result = synthetic(run, world)
    result.ledger[0, run.spec.V3.L["status"]] = run.spec.STATUS["guard_events"]
    path = tmp_path / "bad"
    with pytest.raises(ValueError, match="compute guard"):
        run.checkpoint_row(path, row_identity(run), world, lambda: result)
    assert not path.exists()
    assert (tmp_path / "bad.pending/failure.json").exists()
    assert (tmp_path / "bad.pending/row.npz").exists()
    with pytest.raises(ValueError, match="previously failed"):
        run.checkpoint_row(path, row_identity(run), world, lambda: pytest.fail("replaced a rejected candidate"))


def test_both_fixed_reflex_comparisons_survive_best_reference_selection(tmp_path, monkeypatch):
    run = module("measure")
    world = run.spec.world("catch_speck_l4", T=1024, b2_value=-50)
    identity = row_identity(run)
    rows = {name: run.checkpoint_row(tmp_path / name, identity, world,
                                    lambda captures=captures: synthetic(run, world, captures=captures, poison=(0, 0)))
            for name, captures in {"full": (5, 6), "frozen": (2, 3), "retuned": (3, 4), "ablated": (4, 5)}.items()}
    monkeypatch.setattr(run, "admission", lambda _: {"best_reflex": "retuned", "verdict": "pass"})
    report = run.final_report({}, rows, world)
    assert report["full_vs_reflex"] == report["full_vs_retuned_reflex"]
    assert report["full_vs_frozen_reflex"]["F"]["mean"] == 1500 / 1024
    assert report["full_vs_retuned_reflex"]["F"]["mean"] == 1000 / 1024
    assert report["full_vs_ablated"]["F"]["mean"] == 500 / 1024


def test_budget_resume_preserves_total_and_rejects_unfinalized_prior_run(tmp_path, monkeypatch):
    run = module("run_budgeted")
    monkeypatch.setattr(run, "readiness", lambda: {"test": True})
    path = tmp_path / "budget.json"
    saved = {"status": "interrupted", "ready": {"test": True}, "cap_cpu_seconds": 1800,
             "cpu_seconds": 731.5, "attempts": [{"number": 1}]}
    path.write_text(json.dumps(saved))
    assert run.prior_usage(path, True) == (731.5, [{"number": 1}])
    with pytest.raises(ValueError, match="explicit --resume"):
        run.prior_usage(path, False)
    saved["status"] = "running"
    path.write_text(json.dumps(saved))
    with pytest.raises(ValueError, match="unfinalized"):
        run.prior_usage(path, True)


def test_monitor_dry_run_does_not_spawn(capsys, monkeypatch):
    run = module("run_budgeted")
    monkeypatch.setattr(run.subprocess, "Popen", lambda *a, **kw: pytest.fail("dry run spawned a process"))
    monkeypatch.setattr("sys.argv", ["run_budgeted"])
    run.main()
    assert json.loads(capsys.readouterr().out)["status"] == "dry_run"


def test_monitor_never_resets_spent_budget(tmp_path, monkeypatch):
    run = module("run_budgeted")
    monkeypatch.setattr(run, "STUDY", tmp_path)
    (tmp_path / "protocol.json").write_text(json.dumps({"candidate_lives": 3584}))
    monkeypatch.setattr(run, "readiness", lambda: {})
    monkeypatch.setattr(run, "prior_usage", lambda *a: (1791, []))
    monkeypatch.setattr(run.subprocess, "Popen", lambda *a, **kw: pytest.fail("spent budget launched a worker"))
    monkeypatch.setattr("sys.argv", ["run_budgeted", "--run", "--resume"])
    with pytest.raises(ValueError, match="budget is exhausted"):
        run.main()


def test_monitor_completes_and_carries_prior_cpu_forward(tmp_path, monkeypatch):
    run = module("run_budgeted")
    monkeypatch.setattr(run, "STUDY", tmp_path)
    (tmp_path / "protocol.json").write_text(json.dumps({"candidate_lives": 3584}))
    monkeypatch.setattr(run, "readiness", lambda: {})
    monkeypatch.setattr(run, "prior_usage", lambda *a: (100, [{"number": 1}]))
    monkeypatch.setattr(run.os, "sched_getaffinity", lambda _: set(range(12)))
    monkeypatch.setattr(run.os, "sched_setaffinity", lambda *a: None)
    monkeypatch.setattr(run.signal, "signal", lambda *a: None)
    monkeypatch.setattr(run.time, "process_time", lambda: 0)
    use = iter([0, 7])
    monkeypatch.setattr(run, "child_usage", lambda: next(use))

    class Process:
        pid = 999999

        def __init__(self, command, **kwargs):
            assert kwargs["env"]["OMP_NUM_THREADS"] == "2"
            assert "CELLDEV_THREADS_FILE" not in kwargs["env"]

        def poll(self):
            return 0

    monkeypatch.setattr(run.subprocess, "Popen", Process)
    monkeypatch.setattr("sys.argv", ["run_budgeted", "--run", "--resume"])
    with pytest.raises(SystemExit) as stopped:
        run.main()
    assert stopped.value.code == 0
    result = json.loads((tmp_path / "budget.json").read_text())
    assert result["status"] == "complete" and result["cpu_seconds"] == 107
    assert result["attempts"][-1]["cpu_seconds"] == 7
