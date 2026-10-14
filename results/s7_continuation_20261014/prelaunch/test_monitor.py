"""Synthetic scheduling, pinning and resource-monitor tests. No scientific subprocess is launched."""
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
    loader = importlib.util.spec_from_file_location("s7_monitor_review", HERE / "run_budgeted.py")
    mod = importlib.util.module_from_spec(loader)
    loader.loader.exec_module(mod)
    mod.ROOT, mod.STUDY, mod.DEPENDENCIES = tmp_path, tmp_path / "L", ("J", "K")
    mod.STUDY.mkdir()

    def source(relative):
        path = tmp_path / relative
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text("synthetic pinned source " + relative + "\n")
        return mod.sha(path)

    protocol = {"max_cpu_seconds": 14400, "max_simulation_threads": 4, "runs": [51891, 51892], "generations": 16,
                "planned_genome_lives": 36012, "confirmation_genome_lives": 3072, "wait_for_studies": ["J", "K"],
                "seed_audit_sha256": source("L/seed_audit.json"), "prepare_sha256": source("L/prepare.py"),
                "initialization_audit_sha256": source("L/initialization.json"),
                "configs": {str(seed): {"path": f"L/configs/s{seed}.yaml",
                                        "sha256": source(f"L/configs/s{seed}.yaml")} for seed in mod.RUNS},
                "source_identity": {"src/engine.py": source("src/engine.py")},
                "inputs": {"inputs/provenance.json": source("L/inputs/provenance.json")},
                "reference_sources": {"sources/D.py": source("L/sources/D.py")},
                "template_pins": {"D/config.yaml": source("D/config.yaml")},
                "helpers": {name: source("scripts/" + name) for name in mod.HELPERS}}
    for name in ("founder", "pilot"):
        protocol[name + "_file"] = "L/inputs/" + name + ".json"
        protocol[name + "_sha256"] = source(protocol[name + "_file"])
    initial = {str(seed): {"population_file": f"initialization/s{seed}.npy",
                          "file_sha256": source(f"L/initialization/s{seed}.npy")} for seed in mod.RUNS}
    mod.save(mod.STUDY / "initialization.json", {"runs": initial})
    protocol["initialization_audit_sha256"] = mod.sha(mod.STUDY / "initialization.json")
    mod.save(mod.STUDY / "protocol.json", protocol)
    ready = {"runner_sha256": source("L/run_budgeted.py"), "measurement_sha256": source("L/measure.py"),
             "protocol_sha256": mod.sha(mod.STUDY / "protocol.json"), "helpers": protocol["helpers"],
             "dependencies": {name: {file: source(name + "/" + file)
                                      for file in ("protocol.json", "run_budgeted.py")} for name in mod.DEPENDENCIES}}
    mod.save(mod.STUDY / "ready.json", ready)
    for name in mod.DEPENDENCIES:
        mod.save(tmp_path / name / "budget.json", {"status": "complete", "running": {}, "queued": []})
    mod.protocol, mod.ready = protocol, ready
    monkeypatch.setattr(mod, "child_cpu", lambda: 10)
    monkeypatch.setattr(mod, "active_cpu", lambda pid: 0)
    monkeypatch.setattr(mod.os, "sched_getaffinity", lambda pid: {0, 1, 12})
    monkeypatch.setattr(mod.os, "sched_setaffinity", lambda pid, values: None)
    monkeypatch.setattr(mod.signal, "signal", lambda *args: None)
    monkeypatch.setattr(mod.time, "sleep", lambda seconds: None)
    monkeypatch.setattr(sys, "argv", ["run_budgeted.py", "--run"])
    return mod


class Process:
    def __init__(self, pid, code=0):
        self.pid, self.returncode = pid, code

    def poll(self):
        return self.returncode

    def wait(self, timeout=None):
        if self.returncode is None:
            raise subprocess.TimeoutExpired("mock", timeout)
        return self.returncode


def launch_mock(m, monkeypatch, codes=(0, 0, 0), report="complete", lives=3072):
    calls, processes = [], []

    def spawn(command, **kwargs):
        record = json.loads((m.STUDY / "budget.json").read_text())
        assert record["ready"] == m.ready
        assert kwargs["env"]["OMP_NUM_THREADS"] == kwargs["env"]["MKL_NUM_THREADS"] == "2"
        assert kwargs["env"]["OPENBLAS_NUM_THREADS"] == "2" and "CELLDEV_THREADS_FILE" not in kwargs["env"]
        assert kwargs["start_new_session"]
        if "--confirm-child" in command:
            assert len(processes) == 2 and all(p.returncode is not None for p in processes)
            if report is not None:
                m.save(m.STUDY / "confirmation/report.json", {"status": report, "genome_lives": lives})
        process = Process(100 + len(calls), codes[len(calls)])
        calls.append((command, kwargs))
        processes.append(process)
        return process

    monkeypatch.setattr(m.subprocess, "Popen", spawn)
    return calls, processes


def run(m, expected=0):
    with pytest.raises(SystemExit) as error:
        m.main()
    assert error.value.code == expected
    return json.loads((m.STUDY / "budget.json").read_text())


def test_dryrun_has_no_worker_or_resource_record(m, monkeypatch, capsys):
    monkeypatch.setattr(sys, "argv", ["run_budgeted.py"])
    monkeypatch.setattr(m.subprocess, "Popen", lambda *a, **kw: pytest.fail("launched"))
    m.main()
    result = json.loads(capsys.readouterr().out)
    assert result["simulated_lives"] == 0 and result["planned_genome_lives"] == 36012
    assert not (m.STUDY / "budget.json").exists()


def test_two_searches_precede_the_single_confirmation(m, monkeypatch):
    calls, _ = launch_mock(m, monkeypatch)
    record = run(m)
    assert len(calls) == 3 and "--confirm-child" in calls[2][0]
    assert record["status"] == "complete" and record["phase"] == "confirmation"
    assert record["running"] == {} and record["queued"] == []
    assert record["completed"] == [{"name": name, "exit_code": 0} for name in
                                    ("evolve_s51891", "evolve_s51892", "confirmation")]
    assert record["ready"] == m.ready and record["cpu_seconds"] == 10


@pytest.mark.parametrize("name", ["J", "K"])
def test_both_dependencies_must_be_complete_and_empty(m, name):
    path = m.ROOT / name / "budget.json"
    path.unlink()
    assert not m.prerequisites(m.protocol)
    for status in ("running", "waiting_for_workers"):
        m.save(path, {"status": status})
        assert not m.prerequisites(m.protocol)
    for field in ("running", "queued"):
        m.save(path, {"status": "complete", field: ["leftover"]})
        with pytest.raises(ValueError, match="active work"):
            m.prerequisites(m.protocol)


def test_second_abnormal_dependency_is_detected_while_first_runs(m):
    m.save(m.ROOT / "J/budget.json", {"status": "running"})
    m.save(m.ROOT / "K/budget.json", {"status": "incomplete"})
    with pytest.raises(ValueError, match="abnormally"):
        m.main()
    record = json.loads((m.STUDY / "budget.json").read_text())
    assert record["status"] == "monitor_failed" and not record["queued"] and not record["running"]


@pytest.mark.parametrize("paths", [[], ["J"], ["J", "J"], ["J", "unregistered"]])
def test_exact_dependency_set_is_required(m, paths):
    with pytest.raises(ValueError, match="dependency set"):
        m.dependencies({"wait_for_studies": paths})


@pytest.mark.parametrize("relative", ["seed_audit.json", "prepare.py", "initialization.json", "configs/s51891.yaml",
                                      "inputs/founder.json", "inputs/pilot.json", "inputs/provenance.json",
                                      "sources/D.py", "initialization/s51891.npy", "initialization/s51892.npy"])
def test_changed_preparation_or_fixed_input_is_rejected(m, relative):
    (m.STUDY / relative).write_text("changed")
    with pytest.raises(ValueError, match="differs"):
        m.check_protocol()


@pytest.mark.parametrize("relative", ["src/engine.py", "D/config.yaml", "scripts/taskvar_confirm.py"])
def test_changed_engine_template_or_helper_is_rejected(m, relative):
    (m.ROOT / relative).write_text("changed")
    with pytest.raises(ValueError, match="differs"):
        m.check_protocol()


@pytest.mark.parametrize("relative", ["L/run_budgeted.py", "L/measure.py", "J/protocol.json", "K/run_budgeted.py"])
def test_changed_release_or_dependency_source_is_rejected(m, relative):
    (m.ROOT / relative).write_text("changed")
    with pytest.raises(ValueError, match="differs"):
        m.check_ready()


@pytest.mark.parametrize("change", ["helper", "dependency", "dependency_source"])
def test_partial_readiness_pin_sets_are_rejected(m, change):
    ready = m.ready
    if change == "helper":
        ready["helpers"] = {}
    elif change == "dependency":
        del ready["dependencies"]["K"]
    else:
        del ready["dependencies"]["J"]["run_budgeted.py"]
    m.save(m.STUDY / "ready.json", ready)
    with pytest.raises(ValueError, match="pin set"):
        m.check_ready()


def test_waiting_release_change_is_terminal_and_launches_nothing(m, monkeypatch):
    m.save(m.ROOT / "J/budget.json", {"status": "running"})
    monkeypatch.setattr(m.subprocess, "Popen", lambda *a, **kw: pytest.fail("launched"))

    def wait(_):
        value = json.loads((m.STUDY / "budget.json").read_text())
        assert value["status"] == "waiting_for_workers" and value["ready"] == m.ready
        m.save(m.ROOT / "J/budget.json", {"status": "complete", "running": {}, "queued": []})
        m.save(m.STUDY / "ready.json", {**m.ready, "release": "changed"})

    monkeypatch.setattr(m.time, "sleep", wait)
    with pytest.raises(ValueError, match="readiness or protocol changed"):
        m.main()
    value = json.loads((m.STUDY / "budget.json").read_text())
    assert value["status"] == "monitor_failed" and value["running"] == {} and value["queued"] == []


@pytest.mark.parametrize("report,lives", [(None, 3072), ("incomplete", 3072), ("complete", 3071)])
def test_successful_exit_requires_exact_completed_science(m, monkeypatch, report, lives):
    launch_mock(m, monkeypatch, report=report, lives=lives)
    with pytest.raises((ValueError, FileNotFoundError)):
        m.main()
    assert json.loads((m.STUDY / "budget.json").read_text())["status"] == "monitor_failed"


def test_failed_search_never_launches_confirmation(m, monkeypatch):
    calls, _ = launch_mock(m, monkeypatch, codes=(1, 0))
    record = run(m, 1)
    assert len(calls) == 2 and record["status"] == "incomplete" and record["reason"] == "job_failed"


def test_final_confirmation_cpu_race_cannot_report_complete(m, monkeypatch):
    calls, _ = launch_mock(m, monkeypatch)
    monkeypatch.setattr(m, "child_cpu", lambda: m.CAP + 1 if len(calls) == 3 else 10)
    record = run(m, 1)
    assert record["status"] == "incomplete" and record["reason"] == "cpu_budget_exhausted"


def test_search_consumption_is_not_reset_before_confirmation(m, monkeypatch):
    calls, _ = launch_mock(m, monkeypatch)
    monkeypatch.setattr(m, "child_cpu", lambda: m.CAP - 10 if len(calls) == 2 else 10)
    record = run(m, 1)
    assert len(calls) == 2 and record["reason"] == "cpu_budget_exhausted"
    assert record["cpu_seconds"] == m.CAP - 10


def test_changed_source_before_final_report_cannot_be_complete(m, monkeypatch):
    calls, _ = launch_mock(m, monkeypatch)
    original = m.subprocess.Popen

    def change_on_confirmation(*args, **kwargs):
        process = original(*args, **kwargs)
        if len(calls) == 3:
            (m.ROOT / "src/engine.py").write_text("changed while scoring")
        return process

    monkeypatch.setattr(m.subprocess, "Popen", change_on_confirmation)
    with pytest.raises(ValueError, match="source differs"):
        m.main()
    assert json.loads((m.STUDY / "budget.json").read_text())["status"] == "monitor_failed"


def test_parent_computes_remaining_limit_before_fork(m, monkeypatch):
    calls, _ = launch_mock(m, monkeypatch)
    monkeypatch.setattr(m, "active_cpu", lambda pid: 100)
    run(m)
    limits = []
    monkeypatch.setattr(m, "child_cpu", lambda: pytest.fail("child sampled parent CPU"))
    monkeypatch.setattr(m, "child_limit", lambda remaining, parent: limits.append((remaining, parent)))
    for _, kwargs in calls:
        kwargs["preexec_fn"]()
    assert [value[0] for value in limits] == [14390, 14290, 14390]
    assert all(parent == m.os.getpid() for _, parent in limits)


def test_cap_terminates_both_workers_then_kills_after_two_seconds(m, monkeypatch):
    calls, processes = launch_mock(m, monkeypatch, codes=(None, None))
    monkeypatch.setattr(m, "active_cpu", lambda pid: (m.CAP - m.RESERVE) / 2)
    clock = [0.0]
    monkeypatch.setattr(m.time, "monotonic", lambda: clock[0])
    monkeypatch.setattr(m.time, "sleep", lambda seconds: clock.__setitem__(0, clock[0] + seconds))
    signals = []

    def send(pid, signum):
        signals.append((pid, signum, clock[0]))
        if signum == signal.SIGKILL:
            next(p for p in processes if p.pid == pid).returncode = -signum

    monkeypatch.setattr(m.os, "killpg", send)
    record = run(m, 1)
    assert len(calls) == 2 and record["reason"] == "cpu_budget_exhausted"
    assert [item[1] for item in signals] == [signal.SIGTERM, signal.SIGTERM, signal.SIGKILL, signal.SIGKILL]
    assert signals[2][2] - signals[0][2] == 2
    assert not record["running"] and not record["queued"]


def test_spawn_failure_cleans_up_first_worker_and_records_budget(m, monkeypatch):
    calls, processes = launch_mock(m, monkeypatch, codes=(None, None))
    original = m.subprocess.Popen

    def fail_second(*args, **kwargs):
        if calls:
            raise OSError("synthetic spawn failure")
        return original(*args, **kwargs)

    monkeypatch.setattr(m.subprocess, "Popen", fail_second)
    signals = []

    def send(pid, signum):
        signals.append(signum)
        processes[0].returncode = -signum

    monkeypatch.setattr(m.os, "killpg", send)
    with pytest.raises(OSError, match="spawn failure"):
        m.main()
    value = json.loads((m.STUDY / "budget.json").read_text())
    assert value["status"] == "monitor_failed" and value["cpu_seconds"] == 10
    assert not value["queued"] and not value["running"] and signals == [signal.SIGTERM]


@pytest.mark.parametrize("folder", ["runs", "confirmation", "logs"])
def test_unaccounted_artifacts_prevent_restart(m, monkeypatch, folder):
    (m.STUDY / folder).mkdir()
    monkeypatch.setattr(m.subprocess, "Popen", lambda *a, **kw: pytest.fail("launched"))
    with pytest.raises(ValueError, match="artifacts"):
        m.main()


def test_existing_budget_is_never_reset(m, monkeypatch):
    previous = {"status": "incomplete", "cpu_seconds": 123}
    m.save(m.STUDY / "budget.json", previous)
    monkeypatch.setattr(m.subprocess, "Popen", lambda *a, **kw: pytest.fail("launched"))
    with pytest.raises(ValueError, match="budget record"):
        m.main()
    assert json.loads((m.STUDY / "budget.json").read_text()) == previous


def test_rlimit_and_exact_parent_death_binding(m, monkeypatch):
    calls, limits = [], []
    monkeypatch.setattr(m.ctypes, "CDLL", lambda *a: SimpleNamespace(prctl=lambda *args: calls.append(args) or 0))
    monkeypatch.setattr(m.os, "getppid", lambda: 321)
    monkeypatch.setattr(m.resource, "setrlimit", lambda *args: limits.append(args))
    m.child_limit(123.75, 321)
    assert calls == [(1, signal.SIGKILL, 0, 0, 0)]
    assert limits == [(m.resource.RLIMIT_CPU, (122, 123))]


def test_lost_parent_exits_before_setting_resource_limit(m, monkeypatch):
    monkeypatch.setattr(m.ctypes, "CDLL", lambda *a: SimpleNamespace(prctl=lambda *args: 0))
    monkeypatch.setattr(m.os, "getppid", lambda: 999)
    monkeypatch.setattr(m.os, "_exit", lambda code: (_ for _ in ()).throw(SystemExit(code)))
    monkeypatch.setattr(m.resource, "setrlimit", lambda *a: pytest.fail("lost parent continued"))
    with pytest.raises(SystemExit) as error:
        m.child_limit(100, 321)
    assert error.value.code == 1
