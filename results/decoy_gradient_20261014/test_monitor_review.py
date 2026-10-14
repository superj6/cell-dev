"""Independent mocked review of I monitor main-loop accounting; never execute a worker."""
import importlib.util
import json
import signal
import sys
from pathlib import Path

import pytest


@pytest.fixture
def m(tmp_path, monkeypatch):
    path = Path(__file__).with_name("run_budgeted.py")
    spec = importlib.util.spec_from_file_location("independent_I_monitor", path)
    run = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(run)
    run.STUDY, run.ROOT = tmp_path / "I", tmp_path
    run.STUDY.mkdir()
    monkeypatch.setattr(run, "check_ready", lambda: {})
    monkeypatch.setattr(run, "dependencies_complete", lambda _: True)
    monkeypatch.setattr(run, "cpu", lambda pid=None: 1)
    monkeypatch.setattr(run.signal, "signal", lambda *args: None)
    monkeypatch.setattr(run.os, "sched_getaffinity", lambda _: {0, 1, 12})
    monkeypatch.setattr(run.os, "sched_setaffinity", lambda *args: None)
    monkeypatch.setattr(run.time, "sleep", lambda _: None)
    monkeypatch.setattr(sys, "argv", ["monitor", "--run"])
    return run


def process(m, monkeypatch, *, code=0, report=True):
    class Fake:
        pid, returncode = 123, code

        def poll(self):
            return self.returncode

        def wait(self, timeout=None):
            return self.returncode

    instance = Fake()

    def popen(command, **kwargs):
        assert kwargs["env"]["OMP_NUM_THREADS"] == kwargs["env"]["OPENBLAS_NUM_THREADS"] == "2"
        assert "CELLDEV_THREADS_FILE" not in kwargs["env"]
        if report:
            path = m.STUDY / "measurement/report.json"
            path.parent.mkdir()
            path.write_text('{"status":"complete"}')
        return instance

    monkeypatch.setattr(m.subprocess, "Popen", popen)
    return instance


@pytest.mark.parametrize("code,report,expected", [(0, True, 0), (0, False, 1), (2, True, 1)])
def test_success_needs_both_zero_exit_and_complete_scientific_report(m, monkeypatch, code, report, expected):
    process(m, monkeypatch, code=code, report=report)
    with pytest.raises(SystemExit) as result:
        m.main()
    assert result.value.code == expected
    budget = json.loads((m.STUDY / "budget.json").read_text())
    assert budget["status"] == ("complete" if expected == 0 else "incomplete")
    assert budget["running"] == {} and budget["queued"] == []


def test_budget_threshold_stops_worker_and_preserves_incomplete_record(m, monkeypatch):
    worker = process(m, monkeypatch, code=None)
    monkeypatch.setattr(m, "cpu", lambda pid=None: 3589 if pid is not None else 12)
    calls = []

    def stop(worker):
        calls.append(worker.pid)
        worker.returncode = -signal.SIGTERM

    monkeypatch.setattr(m, "terminate", stop)
    with pytest.raises(SystemExit) as result:
        m.main()
    assert result.value.code == 1 and calls == [worker.pid]
    budget = json.loads((m.STUDY / "budget.json").read_text())
    assert budget["status"] == "incomplete" and budget["cpu_budget_exhausted"]


def test_final_cpu_race_cannot_mark_complete(m, monkeypatch):
    process(m, monkeypatch)
    calls = iter([10, 3600])
    monkeypatch.setattr(m, "cpu", lambda pid=None: next(calls))
    with pytest.raises(SystemExit) as result:
        m.main()
    assert result.value.code == 1


@pytest.mark.parametrize("artifact", ["budget.json", "measurement/s5/screen/row_0000.npz"])
def test_prior_resource_or_science_record_cannot_automatically_restart(m, monkeypatch, artifact):
    path = m.STUDY / artifact
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("saved work")
    monkeypatch.setattr(m.subprocess, "Popen", lambda *a, **k: pytest.fail("automatic restart"))
    with pytest.raises(ValueError, match="no automatic restart"):
        m.main()


def test_monitor_exception_cleans_worker_before_recording_failure(m, monkeypatch):
    worker = process(m, monkeypatch, code=None)
    calls = []

    def cpu(pid=None):
        if pid is not None:
            raise RuntimeError("synthetic read failure")
        return 10

    def stop(value):
        calls.append(value.pid)
        value.returncode = -signal.SIGTERM

    monkeypatch.setattr(m, "cpu", cpu)
    monkeypatch.setattr(m, "terminate", stop)
    with pytest.raises(RuntimeError, match="synthetic read failure"):
        m.main()
    assert calls == [worker.pid]
    budget = json.loads((m.STUDY / "budget.json").read_text())
    assert budget["status"] == "monitor_failed" and budget["cpu_seconds"] == 10
