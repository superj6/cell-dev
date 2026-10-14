"""Preparation, atomic resume and accounting tests use synthetic arrays/mocked processes; no life simulations."""
import importlib.util
import json
from pathlib import Path
from types import SimpleNamespace

import numpy as np
import pytest


def module(name):
    path = Path(__file__).with_name(name + ".py")
    spec = importlib.util.spec_from_file_location("prediction_information_" + name, path)
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
    monkeypatch.setattr(run, "check_protocol", lambda: {"candidate_lives": 3584})
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
    assert expected[-1]["params"][3:5] == [0, 0] and expected[-2]["params"][3:5] == [.3, 200]
    assert [i for i, (a, b) in enumerate(zip(expected[-1]["params"], expected[-2]["params"])) if a != b] == [3, 4]


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



def test_controller_and_candidates_are_fixed_recovered_inputs():
    run = module("measure")
    config = json.loads(run.CONFIG.read_text())
    assert run.sha(run.INPUTS / config["controller_source"]) == "8bfff9f02653c93f22f6d86df7b2c47e1167191fe9448ad26ec194f695689c58"
    items = run.candidates(config)
    assert [x["name"] for x in items] == ["frozen", "retuned", "smaller_frozen", "smaller_tuned", "quieter", "full", "ablated"]
    assert items[3]["knobs"] == config["smaller_reflex_knobs"]
    assert config["ablation_isolates_capability"] is False
    assert run.ACTION == dict(latency="d0", charge="relay", t_ref_min=.5, privileged=False, quant=False, fast=True)


def test_monitor_dry_run_does_not_spawn(capsys, monkeypatch):
    run = module("run_budgeted")
    monkeypatch.setattr(run.subprocess, "Popen", lambda *a, **kw: pytest.fail("dry run spawned a process"))
    monkeypatch.setattr("sys.argv", ["run_budgeted"])
    run.main()
    assert json.loads(capsys.readouterr().out)["status"] == "dry_run"


def test_prior_usage_includes_calibration_and_never_resets(tmp_path, monkeypatch):
    run = module("run_budgeted")
    monkeypatch.setattr(run, "calibration_prior", lambda: 12.5)
    monkeypatch.setattr(run, "readiness", lambda: {"test": True})
    monkeypatch.setattr(run, "proc_table", lambda: {})
    path = tmp_path / "budget.json"
    assert run.prior_usage(path, False) == (12.5, [])
    saved = {"status": "interrupted", "ready": {"test": True}, "cap_cpu_seconds": 3600,
             "cpu_seconds": 731.5, "owned_process_groups": [95002],
             "attempts": [{"number": 1, "monitor_pid": 95001, "monitor_start_ticks": 1,
                           "worker_pid": 95002, "worker_start_ticks": 2}]}
    path.write_text(json.dumps(saved))
    assert run.prior_usage(path, True) == (731.5, saved["attempts"])
    with pytest.raises(ValueError, match="explicit --resume"):
        run.prior_usage(path, False)
    for status, message in [("running", "unfinalized"), ("complete", "already complete")]:
        saved["status"] = status
        path.write_text(json.dumps(saved))
        with pytest.raises(ValueError, match=message):
            run.prior_usage(path, True)
    saved.update(status="interrupted", cpu_seconds=0)
    path.write_text(json.dumps(saved))
    with pytest.raises(ValueError, match="cumulative CPU"):
        run.prior_usage(path, True)


def test_clearance_accepts_failed_science_only_after_every_process_exits(tmp_path, monkeypatch):
    run = module("run_budgeted")
    monkeypatch.setattr(run, "ROOT", tmp_path)
    monkeypatch.setattr(run, "STUDY", tmp_path)
    dependency = tmp_path / "u_budget.json"
    monkeypatch.setattr(run, "DEPENDENCY", dependency)
    dependency.write_text(json.dumps({"status": "incomplete"}))
    receipt = {"all_processes_exited": True, "dependency_budget": "u_budget.json",
               "dependency_budget_sha256": run.sha(dependency), "processes": [{"pid": 123, "start_ticks": 999}],
               "process_groups": [123]}
    (tmp_path / "resource_clearance.json").write_text(json.dumps(receipt))
    monkeypatch.setattr(run, "proc_table", lambda: {})
    assert run.resource_clearance() == receipt
    monkeypatch.setattr(run, "proc_table", lambda: {123: {"start_ticks": 999, "pgrp": 123}})
    with pytest.raises(ValueError, match="remains alive"):
        run.resource_clearance()
    monkeypatch.setattr(run, "proc_table", lambda: {124: {"start_ticks": 1000, "pgrp": 123}})
    with pytest.raises(ValueError, match="process group"):
        run.resource_clearance()
    monkeypatch.setattr(run, "proc_table", lambda: {})
    dependency.write_text(json.dumps({"status": "running"}))
    receipt["dependency_budget_sha256"] = run.sha(dependency)
    (tmp_path / "resource_clearance.json").write_text(json.dumps(receipt))
    with pytest.raises(ValueError, match="has not finalized"):
        run.resource_clearance()


def test_calibration_budget_and_source_requirements(tmp_path, monkeypatch):
    run = module("run_budgeted")
    monkeypatch.setattr(run, "STUDY", tmp_path)
    path = tmp_path / "calibration_budget.json"
    for status, cpu in [("incomplete", 12), ("complete", 31)]:
        path.write_text(json.dumps({"status": status, "cpu_seconds": cpu, "cap_cpu_seconds": 30}))
        with pytest.raises(ValueError, match="calibration incomplete"):
            run.calibration_prior()
    path.write_text(json.dumps({"status": "complete", "cpu_seconds": 12, "cap_cpu_seconds": 30}))
    assert run.calibration_prior() == 12
    monkeypatch.setattr("sys.argv", ["run_budgeted", "--calibrate", "--resume"])
    with pytest.raises(ValueError, match="cannot be repeated"):
        run.main()


def test_process_tree_cpu_includes_compiler_descendants(monkeypatch):
    run = module("run_budgeted")
    monkeypatch.setattr(run, "proc_table", lambda: {
        1: {"ppid": 0, "cpu_ticks": 100}, 2: {"ppid": 1, "cpu_ticks": 200},
        3: {"ppid": 2, "cpu_ticks": 300}, 4: {"ppid": 0, "cpu_ticks": 900}})
    monkeypatch.setattr(run.os, "sysconf", lambda _: 100)
    assert run.process_tree_cpu(1) == 6


@pytest.mark.parametrize("exit_code,expected", [(0, "complete"), (1, "job_failed")])
def test_monitor_closes_budget_and_carries_calibration(tmp_path, monkeypatch, exit_code, expected):
    run = module("run_budgeted")
    monkeypatch.setattr(run, "STUDY", tmp_path)
    monkeypatch.setattr(run, "readiness", lambda: {})
    monkeypatch.setattr(run, "prior_usage", lambda *a: (12.5, []))
    monkeypatch.setattr(run.os, "sched_getaffinity", lambda _: set(range(12)))
    monkeypatch.setattr(run.os, "sched_setaffinity", lambda *a: None)
    monkeypatch.setattr(run.signal, "signal", lambda *a: None)
    monkeypatch.setattr(run.time, "process_time", lambda: .5)
    monkeypatch.setattr(run, "proc_table", lambda: {run.os.getpid(): {"start_ticks": 99}})
    monkeypatch.setattr(run, "enable_subreaper", lambda: None)
    monkeypatch.setattr(run, "process_group_cpu", lambda _: 0)
    monkeypatch.setattr(run, "cleanup_group", lambda _: None)
    usage = iter([0, 7, 7])
    monkeypatch.setattr(run, "child_usage", lambda: next(usage))

    class Process:
        pid = 999999
        def __init__(self, command, **kwargs):
            assert kwargs["env"]["OMP_NUM_THREADS"] == "2"
            assert "CELLDEV_THREADS_FILE" not in kwargs["env"]
        def poll(self):
            return exit_code

    monkeypatch.setattr(run.subprocess, "Popen", Process)
    monkeypatch.setattr("sys.argv", ["run_budgeted", "--run"])
    with pytest.raises(SystemExit) as stopped:
        run.main()
    assert stopped.value.code == (0 if exit_code == 0 else 1)
    record = json.loads((tmp_path / "budget.json").read_text())
    assert record["status"] == expected
    assert record["cpu_seconds"] == 20
    assert record["worker_pid"] is None


def test_monitor_terminates_whole_group_at_fixed_cap(tmp_path, monkeypatch):
    run = module("run_budgeted")
    monkeypatch.setattr(run, "STUDY", tmp_path)
    monkeypatch.setattr(run, "readiness", lambda: {})
    monkeypatch.setattr(run, "prior_usage", lambda *a: (3500, []))
    monkeypatch.setattr(run.os, "sched_getaffinity", lambda _: set(range(12)))
    monkeypatch.setattr(run.os, "sched_setaffinity", lambda *a: None)
    monkeypatch.setattr(run.signal, "signal", lambda *a: None)
    monkeypatch.setattr(run.time, "process_time", lambda: .5)
    monkeypatch.setattr(run.time, "sleep", lambda _: None)
    monkeypatch.setattr(run, "proc_table", lambda: {run.os.getpid(): {"start_ticks": 99}})
    monkeypatch.setattr(run, "enable_subreaper", lambda: None)
    usage = iter([0, 0, 95, 95])
    monkeypatch.setattr(run, "child_usage", lambda: next(usage))
    group_usage = iter([91, 0, 0])
    monkeypatch.setattr(run, "process_group_cpu", lambda _: next(group_usage))
    signals = []
    monkeypatch.setattr(run.os, "killpg", lambda pid, sig: signals.append((pid, sig)))
    monkeypatch.setattr(run, "cleanup_group", lambda process: run.os.killpg(process.pid, run.signal.SIGKILL))

    class Process:
        pid = 999999
        def __init__(self, *a, **kw):
            self.codes = iter([None, -15])
        def poll(self):
            return next(self.codes)

    monkeypatch.setattr(run.subprocess, "Popen", Process)
    monkeypatch.setattr("sys.argv", ["run_budgeted", "--run"])
    with pytest.raises(SystemExit) as stopped:
        run.main()
    assert stopped.value.code == 1
    record = json.loads((tmp_path / "budget.json").read_text())
    assert record["status"] == "cpu_budget_exhausted"
    assert record["cpu_seconds"] == 3595.5
    assert signals == [(999999, run.signal.SIGTERM), (999999, run.signal.SIGKILL)]


def test_calibrated_library_and_receipts_are_bound_to_protocol(monkeypatch):
    run = module("measure")
    protocol = run.check_protocol()
    required = ["library.json", "measurement.so", "measurement.c", "calibration_plan.json", "calibration_complete.json",
                "calibration/full/row.npz", "calibration/full/checkpoint.json", "calibration/ablated/row.npz",
                "calibration/ablated/checkpoint.json"]
    for name in required:
        key = str((run.STUDY / name).relative_to(run.ROOT))
        assert protocol["source_pins"][key] == run.sha(run.STUDY / name)
    original_sha = run.sha
    monkeypatch.setattr(run, "sha", lambda path: "modified" if Path(path) == run.STUDY / "library.json" else original_sha(path))
    with pytest.raises(ValueError, match="protocol/source/numerical identity changed"):
        run.check_protocol()


def test_cleanup_reaps_descendants_when_leader_has_already_exited(monkeypatch):
    run = module("run_budgeted")
    signals, waited = [], []
    monkeypatch.setattr(run.os, "killpg", lambda pid, sig: signals.append((pid, sig)))
    state = iter([{501: {"pgrp": 500}}, {}])
    monkeypatch.setattr(run, "proc_table", lambda: next(state))
    monkeypatch.setattr(run.time, "sleep", lambda _: None)
    waits = iter([(501, 0), (0, 0), (0, 0)])
    def waitpid(pid, flags):
        waited.append(pid)
        return next(waits)
    monkeypatch.setattr(run.os, "waitpid", waitpid)
    process = SimpleNamespace(pid=500, poll=lambda: 0)
    run.cleanup_group(process)
    assert signals == [(500, run.signal.SIGKILL), (500, run.signal.SIGKILL)]
    assert waited == [-500, -500, -500]


def test_child_limits_rejects_adoption_by_noninit_subreaper(monkeypatch):
    run = module("run_budgeted")
    monkeypatch.setattr(run.ctypes, "CDLL", lambda _: SimpleNamespace(prctl=lambda *args: 0))
    monkeypatch.setattr(run.os, "getppid", lambda: 654)
    def exited(code):
        raise SystemExit(code)
    monkeypatch.setattr(run.os, "_exit", exited)
    monkeypatch.setattr(run.resource, "setrlimit", lambda *args: pytest.fail("adopted child received budget"))
    with pytest.raises(SystemExit) as stopped:
        run.child_limits(30, 2, 123)
    assert stopped.value.code == 1


def test_subreaper_setup_failure_cannot_launch_child(monkeypatch):
    run = module("run_budgeted")
    monkeypatch.setattr(run.ctypes, "CDLL", lambda _: SimpleNamespace(prctl=lambda *args: -1))
    with pytest.raises(OSError, match="descendant CPU"):
        run.enable_subreaper()


@pytest.mark.parametrize("case", ["cleanup_error", "monitor_alive", "worker_alive", "group_alive", "missing_identity"])
def test_resume_rejects_unreconciled_prior_v_processes(tmp_path, monkeypatch, case):
    run = module("run_budgeted")
    monkeypatch.setattr(run, "calibration_prior", lambda: 12.5)
    monkeypatch.setattr(run, "readiness", lambda: {})
    record = {"status": "monitor_failed", "ready": {}, "cap_cpu_seconds": 3600, "cpu_seconds": 50,
              "owned_process_groups": [95002], "attempts": [{"number": 1, "monitor_pid": 95001,
              "monitor_start_ticks": 10, "worker_pid": 95002, "worker_start_ticks": 20}]}
    table = {}
    if case == "cleanup_error":
        record["cleanup_error"] = "group still alive"
    elif case == "monitor_alive":
        table[95001] = {"start_ticks": 10, "pgrp": 95000}
    elif case == "worker_alive":
        table[95002] = {"start_ticks": 20, "pgrp": 95002}
    elif case == "group_alive":
        table[95003] = {"start_ticks": 30, "pgrp": 95002}
    else:
        del record["attempts"][0]["worker_start_ticks"]
    path = tmp_path / "budget.json"
    path.write_text(json.dumps(record))
    monkeypatch.setattr(run, "proc_table", lambda: table)
    with pytest.raises(ValueError, match="prior"):
        run.prior_usage(path, True)
