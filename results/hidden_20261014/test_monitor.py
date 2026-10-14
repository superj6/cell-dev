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
    loader = importlib.util.spec_from_file_location("hidden_monitor_test", HERE / "run_budgeted.py")
    mod = importlib.util.module_from_spec(loader)
    loader.loader.exec_module(mod)
    mod.ROOT, mod.STUDY = tmp_path, tmp_path / "H"
    mod.STUDY.mkdir()
    mod.save(mod.STUDY / "protocol.json", {"G_study": "G"})
    mod.save(tmp_path / "G/budget.json", {"status": "complete", "running": {}, "queued": []})
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
        assert kwargs["env"]["OMP_NUM_THREADS"] == kwargs["env"]["MKL_NUM_THREADS"] == "2"
        assert kwargs["env"]["OPENBLAS_NUM_THREADS"] == "2" and "CELLDEV_THREADS_FILE" not in kwargs["env"]
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
        m.save(m.ROOT / "G/budget.json", {"status": status})
        assert not m.dependency_available()
    m.save(m.ROOT / "G/budget.json", {"status": "cpu_budget_exhausted"})
    with pytest.raises(ValueError, match="abnormally"):
        m.dependency_available()
    m.save(m.ROOT / "G/budget.json", {"status": "complete", "running": {"1": "leftover"}})
    with pytest.raises(ValueError, match="active work"):
        m.dependency_available()


def test_complete_requires_success_and_completed_report(m, monkeypatch):
    calls = popen(m, monkeypatch, Process())
    with pytest.raises(SystemExit) as error:
        m.main()
    assert error.value.code == 0 and len(calls) == 1
    assert json.loads((m.STUDY / "budget.json").read_text())["status"] == "complete"


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
    monkeypatch.setattr(m, "cpu", lambda pid=None: 3589)
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
    assert record["cpu_seconds"] == 3589 and record["cpu_budget_exhausted"]


def test_final_cpu_race_cannot_report_success(m, monkeypatch):
    popen(m, monkeypatch, Process())
    monkeypatch.setattr(m, "cpu", lambda pid=None: 3601)
    with pytest.raises(SystemExit) as error:
        m.main()
    assert error.value.code == 1


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
    m.child_limit(3600)
    assert signals == [(1, signal.SIGKILL, 0, 0, 0)]
    assert limits == [(m.resource.RLIMIT_CPU, (3599, 3600))]
