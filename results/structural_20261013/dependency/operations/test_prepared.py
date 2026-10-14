"""Prepared-study checks use config inspection, synthetic scores and mocked processes; no life runs."""
import importlib.util
import json
from pathlib import Path

import numpy as np
import pytest


def module():
    path = Path(__file__).with_name("run_budgeted.py")
    spec = importlib.util.spec_from_file_location("continuation_budget", path)
    obj = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(obj)
    return obj


def test_prepared_protocol_and_default_dry_run(capsys, monkeypatch):
    run = module()
    protocol = run.check_protocol()
    assert protocol["runs"] == [51089, 51090]
    assert protocol["planned_genome_lives"] == 36012
    assert protocol["selection_T1024_equivalent_lives"] == 34304
    assert protocol["max_cpu_seconds"] == 10800
    monkeypatch.setattr("sys.argv", ["run_budgeted"])
    monkeypatch.setattr(run.subprocess, "Popen", lambda *a, **kw: pytest.fail("dry run launched a process"))
    run.main()
    assert json.loads(capsys.readouterr().out)["status"] == "dry_run"


def test_duration_mixture_pairs_seed_clusters_before_se():
    run = module()
    common = np.array([1, 50, 100.0])
    rows = {name: {1: {"F": common}, 2: {"F": common + delta}} for name, delta in
            (("768", [1, 2, 3]), ("1024", [3, 2, 1]), ("1536", [2, 2, 2]))}
    result = run.duration_mixture(rows, 2, 1)
    assert result.tolist() == [2, 2, 2] and result.std(ddof=1) == 0
    with pytest.raises(ValueError, match="three registered"):
        run.duration_mixture({"1024": rows["1024"]}, 2, 1)


def fake_protocol(tmp_path):
    return {"runs": [51089, 51090], "configs": {str(seed): {"path": f"s{seed}.yaml"}
                                                for seed in (51089, 51090)},
            "max_cpu_seconds": 10800, "planned_genome_lives": 36012}


def mock_monitor(monkeypatch, tmp_path):
    run = module()
    monkeypatch.setattr(run, "ROOT", tmp_path)
    monkeypatch.setattr(run, "STUDY", tmp_path)
    monkeypatch.setattr(run, "check_protocol", lambda: fake_protocol(tmp_path))
    monkeypatch.setattr(run, "check_ready", lambda: {})
    monkeypatch.setattr(run.os, "sched_getaffinity", lambda _: set(range(12)))
    monkeypatch.setattr(run.os, "sched_setaffinity", lambda *args: None)
    monkeypatch.setattr(run.time, "sleep", lambda _: None)
    monkeypatch.setattr(run, "child_cpu", lambda: 0)
    monkeypatch.setattr(run, "active_cpu", lambda _: 0)
    monkeypatch.setattr("sys.argv", ["run_budgeted", "--run"])
    return run


def test_monitor_waits_for_both_evolution_jobs_before_confirmation(tmp_path, monkeypatch):
    run = mock_monitor(monkeypatch, tmp_path)
    commands, finished = [], []

    class Process:
        def __init__(self, command, **kwargs):
            if "--confirm-child" in command:
                assert len(finished) == 2
            assert kwargs["env"]["OMP_NUM_THREADS"] == "2"
            assert "CELLDEV_THREADS_FILE" not in kwargs["env"]
            self.pid = 200 + len(commands)
            commands.append(command)

        def poll(self):
            finished.append(self.pid)
            return 0

    monkeypatch.setattr(run.subprocess, "Popen", Process)
    with pytest.raises(SystemExit) as stopped:
        run.main()
    assert stopped.value.code == 0 and len(commands) == 3
    assert all("src.run" in command for command in commands[:2])
    assert "--confirm-child" in commands[2]
    assert json.loads((tmp_path / "budget.json").read_text())["status"] == "complete"


def test_monitor_does_not_start_jobs_after_cpu_budget_is_spent(tmp_path, monkeypatch):
    run = mock_monitor(monkeypatch, tmp_path)
    monkeypatch.setattr(run, "child_cpu", lambda: 10791)
    monkeypatch.setattr(run.subprocess, "Popen", lambda *a, **kw: pytest.fail("launched after budget"))
    with pytest.raises(SystemExit) as stopped:
        run.main()
    assert stopped.value.code == 1
    report = json.loads((tmp_path / "budget.json").read_text())
    assert report["status"] == "cpu_budget_exhausted" and report["completed"] == []


def test_source_readiness_is_required_before_launch(tmp_path, monkeypatch):
    run = module()
    monkeypatch.setattr(run, "STUDY", tmp_path)
    with pytest.raises(ValueError, match="not released"):
        run.check_ready()
