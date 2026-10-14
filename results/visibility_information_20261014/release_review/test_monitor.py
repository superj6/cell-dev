"""Synthetic lifecycle checks only: no scientific modules, compilers, or workers are run."""
from __future__ import annotations

import importlib.util
import json
import signal
import subprocess
import sys
from pathlib import Path
from types import SimpleNamespace

import pytest

MONITOR = Path(__file__).resolve().parents[1] / "autonomous_visibility_information_20261014/monitor.py"


@pytest.fixture
def m(monkeypatch, tmp_path):
    loader = importlib.util.spec_from_file_location("visibility_monitor_review", MONITOR)
    mod = importlib.util.module_from_spec(loader)
    loader.loader.exec_module(mod)
    mod.ROOT, mod.STUDY = tmp_path, tmp_path / "study"
    mod.STUDY.mkdir()

    def source(path, value="pinned synthetic source"):
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(value)
        return mod.sha(path)

    mod.protocol = {
        "monitor_scope": mod.SCOPE,
        "seeds": list(range(52_130_000, 52_130_512)),
        "worlds": {world: {"candidates": [{"role": role, "identity": world + ":" + role}
                                          for role in mod.ROLES]} for world in mod.WORLDS},
        "file_pins": {"bundle/input.json": source(mod.STUDY / "bundle/input.json")},
        "production_pins": {"src/kernel.c": source(mod.ROOT / "src/kernel.c")},
        "production_binding": {"status": "complete"},
    }
    mod.save(mod.STUDY / "protocol.json", mod.protocol)
    mod.save(mod.ROOT / "prior/budget.json", {"status": "complete", "running": {}, "queued": []})
    mod.clearance = {"status": "cleared", "all_processes_exited": True,
                     "budget_pins": {"prior/budget.json": mod.sha(mod.ROOT / "prior/budget.json")},
                     "processes": [{"pid": 50, "start_ticks": 123}], "process_groups": [50]}
    mod.save(mod.STUDY / "resource_clearance.json", mod.clearance)
    pins = {name: source(mod.STUDY / name) for name in ("monitor.py", "validate.py", "measure.py")}
    pins.update({name: mod.sha(mod.STUDY / name) for name in ("protocol.json", "resource_clearance.json")})
    pins.update(mod.protocol["file_pins"])
    mod.ready = {"status": "released", "source_pins": pins, "production_pins": mod.protocol["production_pins"]}
    mod.save(mod.STUDY / "ready.json", mod.ready)
    mod.cpu = [0.0]
    monkeypatch.setattr(mod, "own_cpu", lambda: 1.0)
    monkeypatch.setattr(mod, "child_cpu", lambda: mod.cpu[0])
    monkeypatch.setattr(mod, "active_cpu", lambda group: 0.0)
    monkeypatch.setattr(mod, "proc_table", lambda: {})
    monkeypatch.setattr(mod, "process_identity", lambda pid: {"pid": pid, "ppid": 1, "pgid": pid, "start_ticks": 42})
    monkeypatch.setattr(mod, "enable_subreaper", lambda: None)
    monkeypatch.setattr(mod.os, "killpg", lambda *args: None)
    monkeypatch.setattr(mod.os, "waitpid", lambda *args: (_ for _ in ()).throw(ChildProcessError()))
    monkeypatch.setattr(mod.os, "sched_getaffinity", lambda pid: {0, 1, 12})
    monkeypatch.setattr(mod.os, "sched_setaffinity", lambda *args: None)
    monkeypatch.setattr(mod.signal, "signal", lambda *args: None)
    monkeypatch.setattr(mod.time, "sleep", lambda seconds: None)
    monkeypatch.setattr(sys, "argv", ["monitor.py", "--run"])
    return mod


def validation(m, **changes):
    report = {"status": "complete", "simulation_calls": 82,
              "protocol_sha256": m.sha(m.STUDY / "protocol.json"),
              "source_pins": m.protocol["file_pins"], "production_pins": m.protocol["production_pins"], **changes}
    m.save(m.STUDY / "validation/report.json", report)


def world_result(m, world):
    folder = m.STUDY / "rows" / world
    pins = {}
    for candidate in m.protocol["worlds"][world]["candidates"]:
        row = folder / candidate["role"]
        row.mkdir(parents=True)
        (row / "row.npz").write_bytes(b"synthetic output; not a real numerical archive")
        m.save(row / "checkpoint.json", {
            "identity": {"protocol_sha256": m.sha(m.STUDY / "protocol.json"), "world": world,
                         "candidate": candidate, "seeds": m.protocol["seeds"]},
            "row_sha256": m.sha(row / "row.npz")})
        pins[candidate["role"] + "/checkpoint.json"] = m.sha(row / "checkpoint.json")
    m.save(folder / "complete.json", {"status": "complete", "world": world,
        "protocol_sha256": m.sha(m.STUDY / "protocol.json"), "roles": list(m.ROLES),
        "simulation_calls": 6656, "checkpoint_pins": pins})


class Process:
    def __init__(self, pid, code=0):
        self.pid, self.returncode = pid, code

    def poll(self):
        return self.returncode

    def wait(self, timeout=None):
        if self.returncode is None:
            raise subprocess.TimeoutExpired("mock", timeout)
        return self.returncode


def launch_mock(m, monkeypatch, codes=(0, 0, 0), make_validation=True, make_worlds=True):
    calls, processes = [], []

    def spawn(command, **kwargs):
        budget = m.read(m.STUDY / "budget.json")
        assert budget["ready"] == m.ready
        assert (m.STUDY / "attempt.json").exists()
        assert kwargs["start_new_session"] is True
        assert all(kwargs["env"][key] == "1" for key in
                   ("OMP_NUM_THREADS", "OMP_THREAD_LIMIT", "MKL_NUM_THREADS", "OPENBLAS_NUM_THREADS"))
        assert "CELLDEV_THREADS_FILE" not in kwargs["env"]
        assert command[-2:] == ["--expected-parent", str(m.os.getpid())]
        if "--world" not in command:
            assert not calls
            if make_validation:
                validation(m)
            m.cpu[0] += 30
        else:
            assert calls and processes[0].returncode == 0
            assert m.read(m.STUDY / "validation_budget.json")["cpu_seconds"] == 31
            if make_worlds:
                world_result(m, command[command.index("--world") + 1])
            m.cpu[0] += 100
        process = Process(100 + len(calls), codes[len(calls)])
        calls.append((command, kwargs))
        processes.append(process)
        return process

    monkeypatch.setattr(m.subprocess, "Popen", spawn)
    return calls, processes


def run(m, expected=0):
    with pytest.raises(SystemExit) as exc:
        m.main()
    assert exc.value.code == expected
    return m.read(m.STUDY / "budget.json")


def test_dryrun_needs_no_release_and_never_claims_attempt(m, monkeypatch, capsys):
    (m.STUDY / "protocol.json").unlink()
    (m.STUDY / "ready.json").unlink()
    monkeypatch.setattr(sys, "argv", ["monitor.py"])
    monkeypatch.setattr(m.subprocess, "Popen", lambda *args, **kwargs: pytest.fail("launched"))
    m.main()
    result = json.loads(capsys.readouterr().out)
    assert result["simulated_lives"] == 0 and result["planned_simulation_calls"] == 13394
    assert not (m.STUDY / "attempt.json").exists()


def test_validation_then_two_worlds_share_cpu_without_reset(m, monkeypatch):
    calls, _ = launch_mock(m, monkeypatch)
    result = run(m)
    assert len(calls) == 3
    assert result["status"] == "complete" and result["cpu_seconds"] == 231
    assert result["validation_cpu_seconds"] == 31
    assert result["running"] == {} and result["queued"] == []
    assert [item["name"] for item in result["completed"]] == ["validation", *m.WORLDS]
    assert result["owned_process_groups"] == [100, 101, 102]
    limits = []
    monkeypatch.setattr(m, "child_limit", lambda seconds, parent: limits.append((seconds, parent)))
    for _, kwargs in calls:
        kwargs["preexec_fn"]()
    assert [value[0] for value in limits] == [179, 3569, 3469]
    assert all(parent == m.os.getpid() for _, parent in limits)


@pytest.mark.parametrize("artifact", ["attempt.json", "budget.json", "validation_budget.json", "validation", "rows", "logs", "build-cache"])
def test_prior_artifacts_forbid_any_restart(m, monkeypatch, artifact):
    (m.STUDY / artifact).mkdir()
    monkeypatch.setattr(m.subprocess, "Popen", lambda *args, **kwargs: pytest.fail("launched"))
    with pytest.raises(ValueError, match="prior attempt"):
        m.main()


@pytest.mark.parametrize("path", ["protocol.json", "monitor.py", "measure.py", "validate.py", "resource_clearance.json", "bundle/input.json"])
def test_changed_release_or_input_pin_rejected(m, path):
    (m.STUDY / path).write_text("{}")
    with pytest.raises((ValueError, KeyError)):
        m.main()
    assert not (m.STUDY / "attempt.json").exists()


def test_production_and_dependency_pins_rejected(m):
    (m.ROOT / "src/kernel.c").write_text("changed")
    with pytest.raises(ValueError, match="source pin differs"):
        m.main()


@pytest.mark.parametrize("field,value", [("status", "pending"), ("all_processes_exited", False), ("processes", []), ("process_groups", ["50"])])
def test_invalid_clearance_rejected(m, field, value):
    m.clearance[field] = value
    m.save(m.STUDY / "resource_clearance.json", m.clearance)
    with pytest.raises(ValueError):
        m.resource_clearance()


@pytest.mark.parametrize("table", [{50: {"start_ticks": 123, "pgrp": 99}}, {51: {"start_ticks": 456, "pgrp": 50}}])
def test_live_dependency_identity_or_group_rejected(m, monkeypatch, table):
    monkeypatch.setattr(m, "proc_table", lambda: table)
    with pytest.raises(ValueError, match="remains alive"):
        m.resource_clearance()


def test_reused_pid_with_new_start_is_not_original_process(m, monkeypatch):
    monkeypatch.setattr(m, "proc_table", lambda: {50: {"start_ticks": 999, "pgrp": 99}})
    assert m.resource_clearance() == m.clearance


def test_failed_validation_never_starts_research(m, monkeypatch):
    calls, _ = launch_mock(m, monkeypatch, codes=(1,))
    result = run(m, 1)
    assert len(calls) == 1 and result["reason"] == "job_failed"
    assert not (m.STUDY / "validation_budget.json").exists()


def test_missing_validation_receipt_never_starts_research(m, monkeypatch):
    calls, _ = launch_mock(m, monkeypatch, make_validation=False)
    with pytest.raises(FileNotFoundError):
        m.main()
    assert len(calls) == 1 and m.read(m.STUDY / "budget.json")["status"] == "monitor_failed"


@pytest.mark.parametrize("change", [{"status": "incomplete"}, {"simulation_calls": 81}, {"source_pins": {}}, {"production_pins": {}}])
def test_validation_must_complete_exact_pinned_package(m, change):
    validation(m, **change)
    with pytest.raises(ValueError, match="incomplete or unpinned"):
        m.check_validation(m.protocol)


def test_validation_cpu_at_stop_threshold_cannot_launch_research(m, monkeypatch):
    calls, _ = launch_mock(m, monkeypatch)
    monkeypatch.setattr(m, "child_cpu", lambda: 169 if calls else 0)
    result = run(m, 1)
    assert len(calls) == 1 and result["reason"] == "validation_cpu_budget_exhausted"
    assert result["cpu_seconds"] == 170


def test_own_cpu_counts_before_first_worker(m, monkeypatch):
    calls, _ = launch_mock(m, monkeypatch)
    monkeypatch.setattr(m, "own_cpu", lambda: 170)
    result = run(m, 1)
    assert not calls and result["cpu_seconds"] == 170


def test_total_cpu_race_at_final_exit_is_not_complete(m, monkeypatch):
    calls, _ = launch_mock(m, monkeypatch)
    monkeypatch.setattr(m, "child_cpu", lambda: 3599 if len(calls) == 3 else m.cpu[0])
    result = run(m, 1)
    assert result["reason"] == "cpu_budget_exhausted" and result["cpu_seconds"] == 3600


def test_missing_world_rows_cannot_mark_complete(m, monkeypatch):
    launch_mock(m, monkeypatch, make_worlds=False)
    with pytest.raises(FileNotFoundError):
        m.main()
    assert m.read(m.STUDY / "budget.json")["status"] == "monitor_failed"


def test_changed_raw_row_is_rejected(m):
    world_result(m, m.WORLDS[0])
    (m.STUDY / "rows" / m.WORLDS[0] / "I/row.npz").write_bytes(b"changed")
    with pytest.raises(ValueError, match="raw output pin"):
        m.check_world(m.WORLDS[0], m.protocol)


def test_source_changed_during_run_fails_closed(m, monkeypatch):
    calls, _ = launch_mock(m, monkeypatch)
    spawn = m.subprocess.Popen

    def changed(*args, **kwargs):
        process = spawn(*args, **kwargs)
        if len(calls) == 3:
            (m.ROOT / "src/kernel.c").write_text("changed")
        return process

    monkeypatch.setattr(m.subprocess, "Popen", changed)
    with pytest.raises(ValueError, match="source pin differs"):
        m.main()
    assert m.read(m.STUDY / "budget.json")["status"] == "monitor_failed"


def test_spawn_failure_reaps_existing_world_worker(m, monkeypatch):
    calls, processes = launch_mock(m, monkeypatch, codes=(0, None))
    spawn = m.subprocess.Popen

    def fail_third(*args, **kwargs):
        if len(calls) == 2:
            raise OSError("synthetic spawn failure")
        return spawn(*args, **kwargs)

    monkeypatch.setattr(m.subprocess, "Popen", fail_third)
    def send(pid, sig):
        process = next(p for p in processes if p.pid == pid)
        if process.returncode is None:
            process.returncode = -sig

    monkeypatch.setattr(m.os, "killpg", send)
    with pytest.raises(OSError, match="spawn failure"):
        m.main()
    result = m.read(m.STUDY / "budget.json")
    assert result["running"] == {} and result["queued"] == [] and result["cpu_seconds"] == 131


def test_failed_cleanup_retains_owned_group_and_cpu(m, monkeypatch):
    calls, _ = launch_mock(m, monkeypatch)
    monkeypatch.setattr(m, "cleanup_group", lambda process: (_ for _ in ()).throw(RuntimeError("descendant remains")))
    monkeypatch.setattr(m, "active_cpu", lambda group: 7)
    with pytest.raises(RuntimeError, match="descendant remains"):
        m.main()
    result = m.read(m.STUDY / "budget.json")
    assert len(calls) == 1 and result["cleanup_error"]
    assert result["running"] == {"100": "validation"} and result["cpu_seconds"] == 38


def test_exited_leader_descendant_group_is_killed_and_reaped(m, monkeypatch):
    process = Process(100, 0)
    table = {101: {"pgrp": 100, "ppid": m.os.getpid(), "cpu_ticks": 22}}
    signals, reaps = [], []
    monkeypatch.setattr(m, "proc_table", lambda: table.copy())
    monkeypatch.setattr(m.os, "killpg", lambda pid, sig: signals.append((pid, sig)))

    def wait(pid, flags):
        reaps.append(pid)
        if table:
            table.clear()
            m.cpu[0] += 22
            return 101, 0
        raise ChildProcessError()

    monkeypatch.setattr(m.os, "waitpid", wait)
    m.cleanup_group(process)
    assert signals == [(100, signal.SIGKILL)] and reaps == [-100, -100]
    assert m.consumed_cpu({}) == 23


def test_group_cpu_includes_adopted_descendants_after_leader_exit(m, monkeypatch):
    monkeypatch.setattr(m, "proc_table", lambda: {101: {"pgrp": 100, "cpu_ticks": 42}, 200: {"pgrp": 200, "cpu_ticks": 999}})
    monkeypatch.setattr(m.os, "sysconf", lambda name: 100)
    loader = importlib.util.spec_from_file_location("visibility_cpu_original", MONITOR)
    original = importlib.util.module_from_spec(loader)
    loader.loader.exec_module(original)
    monkeypatch.setattr(original, "proc_table", m.proc_table)
    assert original.active_cpu(100) == 0.42


def test_exact_parent_death_and_cpu_limit(m, monkeypatch):
    calls, limits = [], []
    monkeypatch.setattr(m.ctypes, "CDLL", lambda *args: SimpleNamespace(prctl=lambda *args: calls.append(args) or 0))
    monkeypatch.setattr(m.os, "getppid", lambda: 321)
    monkeypatch.setattr(m.resource, "setrlimit", lambda *args: limits.append(args))
    m.child_limit(123.75, 321)
    assert calls == [(1, signal.SIGKILL, 0, 0, 0)]
    assert limits == [(m.resource.RLIMIT_CPU, (122, 123))]


def test_lost_parent_exits_before_setting_cpu_limit(m, monkeypatch):
    monkeypatch.setattr(m.ctypes, "CDLL", lambda *args: SimpleNamespace(prctl=lambda *args: 0))
    monkeypatch.setattr(m.os, "getppid", lambda: 999)
    monkeypatch.setattr(m.os, "_exit", lambda code: (_ for _ in ()).throw(SystemExit(code)))
    monkeypatch.setattr(m.resource, "setrlimit", lambda *args: pytest.fail("continued without parent"))
    with pytest.raises(SystemExit) as exc:
        m.child_limit(100, 321)
    assert exc.value.code == 1


def test_pin_paths_cannot_escape_declared_root(m):
    with pytest.raises(ValueError, match="within its declared source root"):
        m.pinned_path(m.STUDY, "../src/kernel.c")


def test_both_live_worlds_stopped_at_total_cap(m, monkeypatch):
    calls, processes = launch_mock(m, monkeypatch, codes=(0, None, None))
    monkeypatch.setattr(m, "active_cpu", lambda group: 1800 if len(calls) == 3 else 0)
    clock, signals = [0.0], []
    monkeypatch.setattr(m.time, "monotonic", lambda: clock[0])
    monkeypatch.setattr(m.time, "sleep", lambda seconds: clock.__setitem__(0, clock[0] + seconds))

    def send(pid, sig):
        signals.append((pid, sig))
        process = next(p for p in processes if p.pid == pid)
        if sig == signal.SIGKILL and process.returncode is None:
            process.returncode = -sig

    monkeypatch.setattr(m.os, "killpg", send)
    result = run(m, 1)
    assert result["reason"] == "cpu_budget_exhausted" and not result["running"]
    assert all((pid, signal.SIGTERM) in signals and (pid, signal.SIGKILL) in signals for pid in (101, 102))


def test_cleanup_cpu_is_counted_before_validation_gate(m, monkeypatch):
    calls, _ = launch_mock(m, monkeypatch)
    original = m.cleanup_group

    def clean(process):
        original(process)
        m.cpu[0] += 150

    monkeypatch.setattr(m, "cleanup_group", clean)
    result = run(m, 1)
    assert len(calls) == 1 and result["cpu_seconds"] == 181
    assert result["reason"] == "validation_cpu_budget_exhausted"


def test_exclusive_attempt_claim_rejects_concurrent_claim(m, monkeypatch):
    real_open = Path.open

    def raced_open(path, mode="r", *args, **kwargs):
        if path == m.STUDY / "attempt.json" and mode == "x":
            with real_open(path, "w") as stream:
                stream.write("another monitor claimed the first attempt")
        return real_open(path, mode, *args, **kwargs)

    monkeypatch.setattr(Path, "open", raced_open)
    monkeypatch.setattr(m.subprocess, "Popen", lambda *args, **kwargs: pytest.fail("launched"))
    with pytest.raises(FileExistsError):
        m.main()


def test_changed_validation_budget_blocks_first_research_worker(m, monkeypatch):
    calls, _ = launch_mock(m, monkeypatch)
    original = m.save

    def changed(path, value):
        if path == m.STUDY / "validation_budget.json":
            value = dict(value, cpu_seconds=0)
        original(path, value)

    monkeypatch.setattr(m, "save", changed)
    with pytest.raises(ValueError, match="validation receipt changed"):
        m.main()
    assert len(calls) == 1


def test_incomplete_production_binding_is_rejected(m):
    m.protocol["production_binding"]["status"] = "awaiting_integration"
    m.save(m.STUDY / "protocol.json", m.protocol)
    with pytest.raises(ValueError, match="production ABI4 binding is incomplete"):
        m.check_protocol()


def test_unresolved_dependency_cleanup_is_rejected(m):
    m.save(m.ROOT / "prior/budget.json", {"status": "monitor_failed", "cleanup_error": "owned group alive"})
    m.clearance["budget_pins"]["prior/budget.json"] = m.sha(m.ROOT / "prior/budget.json")
    m.save(m.STUDY / "resource_clearance.json", m.clearance)
    with pytest.raises(ValueError, match="unresolved cleanup"):
        m.resource_clearance()
