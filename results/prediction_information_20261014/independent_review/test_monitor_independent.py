"""Independent V monitor fault-injection tests; subprocesses/signals are mocked, no lives execute."""
from __future__ import annotations

import importlib.util
import json
import os
from pathlib import Path

import pytest

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[1]
MONITOR = ROOT / "outputs/autonomous_prediction_information_20261014/run_budgeted.py"


def load_monitor():
    path = Path(os.environ.get("V_MONITOR_AUDIT_SOURCE", MONITOR))
    loader = importlib.util.spec_from_file_location("independent_V_monitor", path)
    mod = importlib.util.module_from_spec(loader)
    loader.loader.exec_module(mod)
    return mod


@pytest.mark.parametrize("exit_code", [0, 1, -15])
@pytest.mark.parametrize("inject_after_poll", [False, True])
def test_completed_leader_does_not_leave_owned_group_alive(tmp_path, monkeypatch, exit_code, inject_after_poll):
    mod = load_monitor()
    monkeypatch.setattr(mod, "STUDY", tmp_path)
    monkeypatch.setattr(mod, "readiness", lambda: {})
    monkeypatch.setattr(mod, "prior_usage", lambda *a: (12.5, []))
    monkeypatch.setattr(mod.os, "sched_getaffinity", lambda _: set(range(12)))
    monkeypatch.setattr(mod.os, "sched_setaffinity", lambda *a: None)
    monkeypatch.setattr(mod.signal, "signal", lambda *a: None)
    monkeypatch.setattr(mod.time, "process_time", lambda: .5)
    monkeypatch.setattr(mod.time, "sleep", lambda _: None)
    monkeypatch.setattr(mod, "child_usage", lambda: 7.)
    survivor = {"alive": True}
    signals = []

    def table():
        result = {mod.os.getpid(): {"ppid": 1, "pgrp": 3, "start_ticks": 99, "cpu_ticks": 0}}
        if survivor["alive"]:
            result[10001] = {"ppid": mod.os.getpid(), "pgrp": 999999, "start_ticks": 100, "cpu_ticks": 100}
        return result

    def killpg(pid, sig):
        signals.append((pid, sig))
        if pid == 999999 and sig == mod.signal.SIGKILL:
            survivor["alive"] = False

    monkeypatch.setattr(mod, "proc_table", table)
    monkeypatch.setattr(mod.os, "killpg", killpg)
    monkeypatch.setattr(mod.os, "waitpid", lambda *a: (0, 0))
    if hasattr(mod, "enable_subreaper"):
        monkeypatch.setattr(mod, "enable_subreaper", lambda: None)
    if inject_after_poll:
        original = mod.process_group_cpu
        called = []

        def once(pid):
            if not called:
                called.append(True)
                raise ValueError("injected accounting failure after leader exited")
            return original(pid)

        monkeypatch.setattr(mod, "process_group_cpu", once)

    class Process:
        pid = 999999
        def __init__(self, *a, **kw):
            pass
        def poll(self):
            return exit_code
        def wait(self, **kw):
            return exit_code

    monkeypatch.setattr(mod.subprocess, "Popen", Process)
    monkeypatch.setattr("sys.argv", ["run_budgeted", "--run"])
    with pytest.raises(ValueError if inject_after_poll else SystemExit):
        mod.main()
    assert not survivor["alive"], "owned descendant survives after direct worker exit"
    assert (999999, mod.signal.SIGKILL) in signals
    record = json.loads((tmp_path / "budget.json").read_text())
    assert record["worker_pid"] is None


def test_child_rejects_adoption_by_non_init_subreaper(monkeypatch):
    mod = load_monitor()
    calls = []

    class ExitIntercept(Exception):
        pass

    class Libc:
        def prctl(self, *args):
            calls.append(args)
            return 0

    def stopped(code):
        assert code == 1
        raise ExitIntercept

    monkeypatch.setattr(mod.ctypes, "CDLL", lambda *a: Libc())
    monkeypatch.setattr(mod.os, "getppid", lambda: 9988)
    monkeypatch.setattr(mod.os, "_exit", stopped)
    monkeypatch.setattr(mod.resource, "setrlimit", lambda *a: pytest.fail("adopted child proceeded"))
    with pytest.raises(ExitIntercept):
        mod.child_limits(100, 10, 8877)
    assert calls == [(1, mod.signal.SIGKILL, 0, 0, 0)]


@pytest.mark.parametrize("case", ["cleanup_error", "monitor_alive", "worker_alive", "group_alive"])
def test_resume_refuses_unresolved_previous_processes(tmp_path, monkeypatch, case):
    mod = load_monitor()
    monkeypatch.setattr(mod, "STUDY", tmp_path)
    monkeypatch.setattr(mod, "readiness", lambda: {})
    monkeypatch.setattr(mod, "calibration_prior", lambda: 11.5)
    record = {"status": "monitor_failed", "ready": {}, "cap_cpu_seconds": 3600, "cpu_seconds": 25.,
              "worker_pid": None, "owned_process_groups": [456], "attempts": [
                  {"number": 1, "monitor_pid": 123, "monitor_start_ticks": 900,
                   "worker_pid": 456, "worker_start_ticks": 901}]}
    table = {}
    if case == "cleanup_error":
        record["cleanup_error"] = "RuntimeError: owned process group did not exit"
    elif case == "monitor_alive":
        table[123] = {"ppid": 1, "pgrp": 122, "start_ticks": 900, "cpu_ticks": 10}
    elif case == "worker_alive":
        table[456] = {"ppid": 1, "pgrp": 999, "start_ticks": 901, "cpu_ticks": 10}
    else:
        table[789] = {"ppid": 1, "pgrp": 456, "start_ticks": 902, "cpu_ticks": 10}
    monkeypatch.setattr(mod, "proc_table", lambda: table)
    path = tmp_path / "budget.json"
    path.write_text(json.dumps(record))
    with pytest.raises(ValueError):
        mod.prior_usage(path, True)
