"""Mock-only resource and scheduling checks; no worker subprocess or simulation."""
import importlib.util
import json
import signal
import subprocess
import sys
from pathlib import Path
from types import SimpleNamespace

import pytest

HERE = Path(__file__).resolve().parent


@pytest.fixture
def m(monkeypatch, tmp_path):
    loader = importlib.util.spec_from_file_location("trace_monitor_review", HERE / "run_budgeted.py")
    mod = importlib.util.module_from_spec(loader)
    loader.loader.exec_module(mod)
    mod.ROOT, mod.STUDY = tmp_path, tmp_path / "K"
    mod.DEPENDENCIES = ("H", "I")
    mod.original_check_ready = mod.check_ready
    mod.STUDY.mkdir()
    mod.save(mod.STUDY / "protocol.json", {"wait_for_studies": ["H", "I"]})
    mod.save(tmp_path / "H/budget.json", {"status": "complete", "running": {}, "queued": []})
    mod.save(tmp_path / "I/budget.json", {"status": "complete", "running": {}, "queued": []})
    monkeypatch.setattr(mod, "check_ready", lambda: {})
    monkeypatch.setattr(mod, "cpu", lambda pid=None: 0)
    monkeypatch.setattr(mod.os, "sched_getaffinity", lambda pid: {0, 1, 12})
    monkeypatch.setattr(mod.os, "sched_setaffinity", lambda pid, values: None)
    monkeypatch.setattr(mod.signal, "signal", lambda *args: None)
    monkeypatch.setattr(mod.time, "sleep", lambda seconds: None)
    monkeypatch.setattr(sys, "argv", ["run_budgeted.py", "--run"])
    return mod


class Process:
    pid = 123

    def __init__(self, code=0):
        self.returncode = code

    def poll(self):
        return self.returncode

    def wait(self, timeout=None):
        if self.returncode is None:
            raise subprocess.TimeoutExpired("mock", timeout)
        return self.returncode


def popen(m, monkeypatch, process, report=True):
    calls = []

    def spawn(command, **kwargs):
        calls.append(command)
        assert kwargs["env"]["OMP_NUM_THREADS"] == kwargs["env"]["MKL_NUM_THREADS"] == "1"
        assert kwargs["env"]["OPENBLAS_NUM_THREADS"] == "1" and "CELLDEV_THREADS_FILE" not in kwargs["env"]
        assert kwargs["start_new_session"]
        if report:
            m.save(m.STUDY / "measurement/report.json", {"status": "complete"})
        return process
    monkeypatch.setattr(m.subprocess, "Popen", spawn)
    return calls


def test_dryrun_never_launches(m, monkeypatch, capsys):
    monkeypatch.setattr(sys, "argv", ["run_budgeted.py"])
    monkeypatch.setattr(m.subprocess, "Popen", lambda *a, **kw: pytest.fail("launched"))
    m.main()
    assert json.loads(capsys.readouterr().out)["simulated_lives"] == 0


def test_dependency_requires_completion_not_fitness(m):
    assert m.dependency_available()
    for status in ("running", "waiting_for_workers"):
        m.save(m.ROOT / "H/budget.json", {"status": status})
        assert not m.dependency_available()
    m.save(m.ROOT / "H/budget.json", {"status": "cpu_budget_exhausted"})
    with pytest.raises(ValueError, match="abnormally"):
        m.dependency_available()
    m.save(m.ROOT / "H/budget.json", {"status": "complete", "running": {"1": "leftover"}})
    with pytest.raises(ValueError, match="active work"):
        m.dependency_available()


@pytest.mark.parametrize("name", ["H", "I"])
def test_either_dependency_blocks_launch_until_complete_and_empty(m, name):
    path = m.ROOT / name / "budget.json"
    path.unlink()
    assert not m.dependency_available()
    m.save(path, {"status": "running", "running": {"123": "measurement"}, "queued": []})
    assert not m.dependency_available()
    m.save(path, {"status": "complete", "running": {}, "queued": ["leftover"]})
    with pytest.raises(ValueError, match="active work"):
        m.dependency_available()
    m.save(path, {"status": "complete", "running": {}, "queued": []})
    assert m.dependency_available()


def test_failed_second_dependency_is_not_hidden_by_running_first(m):
    m.save(m.ROOT / "H/budget.json", {"status": "running"})
    m.save(m.ROOT / "I/budget.json", {"status": "incomplete"})
    with pytest.raises(ValueError, match="abnormally"):
        m.dependency_available()


@pytest.mark.parametrize("paths", [[], ["H"], ["H", "H"], ["H", "unregistered"]])
def test_exact_two_registered_dependencies_are_required(m, paths):
    m.save(m.STUDY / "protocol.json", {"wait_for_studies": paths})
    with pytest.raises(ValueError, match="dependency set differs"):
        m.dependency_available()


def readiness_fixture(m, monkeypatch):
    for name in ("measure.py", "run_budgeted.py"):
        (m.STUDY / name).write_text("synthetic fixture source\n")
    for dependency in m.DEPENDENCIES:
        for name in ("protocol.json", "run_budgeted.py"):
            (m.ROOT / dependency / name).write_text("synthetic dependency\n")
    ready = {"files": {name: m.sha(m.STUDY / name) for name in
                       ("measure.py", "run_budgeted.py", "protocol.json")},
             "dependencies": {path: {name: m.sha(m.ROOT / path / name) for name in
                                     ("protocol.json", "run_budgeted.py")} for path in m.DEPENDENCIES}}
    m.save(m.STUDY / "ready.json", ready)
    monkeypatch.setitem(sys.modules, "measure", SimpleNamespace(
        check_protocol=lambda: json.loads((m.STUDY / "protocol.json").read_text())))
    return ready


def test_ready_binds_all_own_and_dependency_source_bytes(m, monkeypatch):
    ready = readiness_fixture(m, monkeypatch)
    assert m.original_check_ready() == ready
    (m.STUDY / "measure.py").write_text("changed")
    with pytest.raises(ValueError, match="readiness pin differs"):
        m.original_check_ready()


@pytest.mark.parametrize("dependency,name", [("H", "protocol.json"), ("I", "run_budgeted.py")])
def test_changed_dependency_source_is_rejected(m, monkeypatch, dependency, name):
    readiness_fixture(m, monkeypatch)
    (m.ROOT / dependency / name).write_text("changed dependency")
    with pytest.raises(ValueError, match="dependency source differs"):
        m.original_check_ready()


@pytest.mark.parametrize("change,message", [
    ("own_extra", "readiness file pin set"), ("missing_dependency", "dependency readiness pin set"),
    ("missing_source", "dependency source pin set")])
def test_readiness_pin_sets_cannot_be_partial_or_expanded(m, monkeypatch, change, message):
    ready = readiness_fixture(m, monkeypatch)
    if change == "own_extra":
        ready["files"]["other.py"] = "unexpected"
    elif change == "missing_dependency":
        del ready["dependencies"]["I"]
    else:
        del ready["dependencies"]["H"]["run_budgeted.py"]
    m.save(m.STUDY / "ready.json", ready)
    with pytest.raises(ValueError, match=message):
        m.original_check_ready()


def test_complete_requires_success_and_completed_report(m, monkeypatch):
    calls = popen(m, monkeypatch, Process())
    with pytest.raises(SystemExit) as error:
        m.main()
    assert error.value.code == 0 and len(calls) == 1
    assert json.loads((m.STUDY / "budget.json").read_text())["status"] == "complete"


def test_waiting_rechecks_readiness_before_launch_and_persists_its_identity(m, monkeypatch):
    availability = iter([False, True])
    monkeypatch.setattr(m, "dependency_available", lambda: next(availability))
    checks = []
    monkeypatch.setattr(m, "check_ready", lambda: checks.append("checked") or {"fixed": "release"})
    calls = popen(m, monkeypatch, Process())

    def wait(_):
        assert not calls
        assert json.loads((m.STUDY / "budget.json").read_text())["status"] == "waiting_for_workers"

    monkeypatch.setattr(m.time, "sleep", wait)
    with pytest.raises(SystemExit) as error:
        m.main()
    assert error.value.code == 0 and len(checks) == 2 and len(calls) == 1
    assert json.loads((m.STUDY / "budget.json").read_text())["ready"] == {"fixed": "release"}


def test_changed_readiness_while_waiting_never_launches(m, monkeypatch):
    checks = iter([{"release": 1}, {"release": 2}])
    monkeypatch.setattr(m, "check_ready", lambda: next(checks))
    monkeypatch.setattr(m.subprocess, "Popen", lambda *a, **kw: pytest.fail("changed release launched"))
    with pytest.raises(ValueError, match="readiness changed"):
        m.main()


@pytest.mark.parametrize("code,report", [(2, True), (0, False), (-signal.SIGKILL, True)])
def test_failed_or_missing_science_is_not_complete(m, monkeypatch, code, report):
    popen(m, monkeypatch, Process(code), report=report)
    with pytest.raises(SystemExit) as error:
        m.main()
    assert error.value.code == 1
    assert json.loads((m.STUDY / "budget.json").read_text())["status"] == "incomplete"


def test_cpu_cap_terms_and_kills_and_records_consumed_cpu(m, monkeypatch):
    process = Process(None)
    popen(m, monkeypatch, process)
    monkeypatch.setattr(m, "cpu", lambda pid=None: 1789)
    signals = []

    def killpg(pid, sig):
        signals.append(sig)
        if sig == signal.SIGKILL:
            process.returncode = -sig
    monkeypatch.setattr(m.os, "killpg", killpg)
    with pytest.raises(SystemExit) as error:
        m.main()
    assert error.value.code == 1 and signals == [signal.SIGTERM, signal.SIGKILL]
    record = json.loads((m.STUDY / "budget.json").read_text())
    assert record["cpu_seconds"] == 1789 and record["cpu_budget_exhausted"]


def test_final_cpu_race_cannot_report_success(m, monkeypatch):
    popen(m, monkeypatch, Process())
    monkeypatch.setattr(m, "cpu", lambda pid=None: 1801)
    with pytest.raises(SystemExit) as error:
        m.main()
    assert error.value.code == 1


def test_termination_tolerates_process_exiting_before_signal(m, monkeypatch):
    def already_gone(*args):
        raise ProcessLookupError
    monkeypatch.setattr(m.os, "killpg", already_gone)
    assert m.terminate(Process(0)) == 0


def test_monitor_failure_terminates_owned_worker_and_preserves_budget(m, monkeypatch):
    process = Process(None)
    popen(m, monkeypatch, process)
    signals = []

    def fail_cpu(pid=None):
        if pid is not None:
            raise RuntimeError("synthetic resource-read failure")
        return 17

    def kill(pid, sig):
        assert pid == process.pid
        signals.append(sig)
        process.returncode = -sig

    monkeypatch.setattr(m, "cpu", fail_cpu)
    monkeypatch.setattr(m.os, "killpg", kill)
    with pytest.raises(RuntimeError, match="resource-read failure"):
        m.main()
    saved = json.loads((m.STUDY / "budget.json").read_text())
    assert saved["status"] == "monitor_failed" and saved["cpu_seconds"] == 17
    assert saved["running"] == {} and saved["queued"] == [] and signals == [signal.SIGTERM]


def test_restart_refuses_budget_or_unaccounted_measurement(m, monkeypatch):
    monkeypatch.setattr(m.subprocess, "Popen", lambda *a, **kw: pytest.fail("launched"))
    m.save(m.STUDY / "budget.json", {"cpu_seconds": 100})
    with pytest.raises(ValueError, match="budget record"):
        m.main()
    (m.STUDY / "budget.json").unlink()
    (m.STUDY / "measurement").mkdir()
    with pytest.raises(ValueError, match="artifacts"):
        m.main()


def test_rlimit_and_parent_death_binding(m, monkeypatch):
    signals, limits = [], []
    monkeypatch.setattr(m.ctypes, "CDLL", lambda *a: SimpleNamespace(prctl=lambda *args: signals.append(args) or 0))
    monkeypatch.setattr(m.os, "getppid", lambda: 123)
    monkeypatch.setattr(m.resource, "setrlimit", lambda *args: limits.append(args))
    m.child_limit(1800)
    assert signals == [(1, signal.SIGKILL, 0, 0, 0)]
    assert limits == [(m.resource.RLIMIT_CPU, (1799, 1800))]


def test_remaining_limit_is_captured_before_entering_child(m, monkeypatch):
    consumed, limits = [17], []
    monkeypatch.setattr(m, "cpu", lambda pid=None: consumed[0])
    monkeypatch.setattr(m, "child_limit", limits.append)

    def spawn(command, **kwargs):
        # After fork getrusage(RUSAGE_CHILDREN) no longer describes the parent's consumed budget.
        consumed[0] = 1000
        kwargs["preexec_fn"]()
        m.save(m.STUDY / "measurement/report.json", {"status": "complete"})
        return Process(0)

    monkeypatch.setattr(m.subprocess, "Popen", spawn)
    with pytest.raises(SystemExit) as error:
        m.main()
    assert error.value.code == 0 and limits == [1783]
