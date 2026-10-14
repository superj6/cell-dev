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
    loader = importlib.util.spec_from_file_location("scoring_budget_monitor_test", HERE / "run_budgeted.py")
    mod = importlib.util.module_from_spec(loader)
    loader.loader.exec_module(mod)
    mod.ROOT, mod.STUDY, mod.DEPENDENCIES = tmp_path, tmp_path / "S", ("R",)
    mod.STUDY.mkdir()

    def source(relative):
        path = tmp_path / relative
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text("synthetic pinned source " + relative + "\n")
        return mod.sha(path)

    protocol = {"max_cpu_seconds": 14400, "max_simulation_threads": 4, "runs": [52091, 52092], "generations": 8,
                "planned_genome_lives": 37484, "confirmation_genome_lives": 4608, "selection_genome_lives": 32768,
                "periodic_valid_genome_lives": 96, "tiny_final_genome_lives": 12,
                "reference_labels": ["D51089", "D51090", "P52091", "P52092"],
                "wait_for_studies": ["R"],
                "seed_audit_sha256": source("S/seed_audit.json"), "prepare_sha256": source("S/prepare.py"),
                "initialization_audit_sha256": source("S/initialization.json"),
                "configs": {str(seed): {"path": f"S/configs/s{seed}.yaml",
                                        "sha256": source(f"S/configs/s{seed}.yaml")} for seed in mod.RUNS},
                "source_identity": {"src/engine.py": source("src/engine.py")},
                "inputs": {"inputs/provenance.json": source("S/inputs/provenance.json")},
                "reference_sources": {"sources/D.py": source("S/sources/D.py")},
                "template_pins": {"D/config.yaml": source("D/config.yaml")},
                "helpers": {name: source("scripts/" + name) for name in mod.HELPERS}}
    for name in ("founder", "pilot"):
        protocol[name + "_file"] = "S/inputs/" + name + ".json"
        protocol[name + "_sha256"] = source(protocol[name + "_file"])
        protocol["inputs"]["inputs/" + name + ".json"] = protocol[name + "_sha256"]
    initial = {str(seed): {"population_file": f"initialization/s{seed}.npy",
                          "file_sha256": source(f"S/initialization/s{seed}.npy")} for seed in mod.RUNS}
    mod.save(mod.STUDY / "initialization.json", {"runs": initial})
    protocol["initialization_audit_sha256"] = mod.sha(mod.STUDY / "initialization.json")
    protocol["dependencies"] = {name: {file: source(name + "/" + file)
                                       for file in ("protocol.json", "run_budgeted.py")}
                                for name in mod.DEPENDENCIES}
    mod.save(mod.STUDY / "protocol.json", protocol)
    ready = {"runner_sha256": source("S/run_budgeted.py"), "measurement_sha256": source("S/measure.py"),
             "protocol_sha256": mod.sha(mod.STUDY / "protocol.json"), "helpers": protocol["helpers"],
             "dependencies": {name: {file: source(name + "/" + file)
                                      for file in ("protocol.json", "run_budgeted.py")} for name in mod.DEPENDENCIES}}
    mod.save(mod.STUDY / "ready.json", ready)
    for name in mod.DEPENDENCIES:
        mod.save(tmp_path / name / "budget.json", {"status": "complete", "running": {}, "queued": []})
    mod.protocol, mod.ready = protocol, ready
    monkeypatch.setattr(mod, "own_cpu", lambda: 0)
    monkeypatch.setattr(mod.os, "killpg", lambda *args: None)
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


def launch_mock(m, monkeypatch, codes=(0, 0, 0, 0), report="complete", lives=4608, references="complete"):
    calls, processes = [], []

    def spawn(command, **kwargs):
        record = json.loads((m.STUDY / "budget.json").read_text())
        assert record["ready"] == m.ready
        assert kwargs["env"]["OMP_NUM_THREADS"] == kwargs["env"]["MKL_NUM_THREADS"] == "2"
        assert kwargs["env"]["OPENBLAS_NUM_THREADS"] == "2" and "CELLDEV_THREADS_FILE" not in kwargs["env"]
        assert kwargs["start_new_session"]
        assert kwargs["env"]["CELLDEV_SCORING_BUDGET_MONITOR_PID"] == str(m.os.getpid())
        if "--freeze-references" in command:
            assert not processes
            if references is not None:
                files = {}
                for label in m.protocol["reference_labels"]:
                    path = m.STUDY / "references" / (label + ".json")
                    path.parent.mkdir(parents=True, exist_ok=True)
                    path.write_text(label + " fixed reference bytes")
                    files[path.name] = m.sha(path)
                m.save(m.STUDY / "references/report.json", {"status": references,
                    "runs": list(m.RUNS), "mapping": {"52091": 51089, "52092": 51090},
                    "labels": m.protocol["reference_labels"], "files": files})
        elif "src.run" in command:
            assert record["frozen_references"] and len(processes) in (1, 2)
        if "--confirm-child" in command:
            assert len(processes) == 3 and all(p.returncode is not None for p in processes)
            if report is not None:
                m.save(m.STUDY / "confirmation/report.json", {"status": report, "genome_lives": lives,
                    "planned_genome_lives": 4608, "completed_genome_lives": lives})
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
    assert result["simulated_lives"] == 0 and result["planned_genome_lives"] == 37484
    assert not (m.STUDY / "budget.json").exists()


def test_reference_freeze_precedes_both_searches_and_single_confirmation(m, monkeypatch):
    calls, _ = launch_mock(m, monkeypatch)
    record = run(m)
    assert len(calls) == 4 and "--freeze-references" in calls[0][0] and "--confirm-child" in calls[3][0]
    assert record["status"] == "complete" and record["phase"] == "confirmation"
    assert record["running"] == {} and record["queued"] == []
    assert record["completed"] == [{"name": name, "exit_code": 0} for name in
                                    ("freeze_references", "evolve_s52091", "evolve_s52092", "confirmation")]
    assert record["ready"] == m.ready and record["cpu_seconds"] == 10


@pytest.mark.parametrize("name", ["R"])
def test_dependency_must_be_complete_and_empty(m, name):
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


def test_abnormal_dependency_is_terminal_without_launch(m):
    m.save(m.ROOT / "R/budget.json", {"status": "incomplete"})
    with pytest.raises(ValueError, match="abnormally"):
        m.main()
    record = json.loads((m.STUDY / "budget.json").read_text())
    assert record["status"] == "monitor_failed" and not record["queued"] and not record["running"]


@pytest.mark.parametrize("paths", [[], ["unregistered"], ["R", "R"], ["R", "unregistered"]])
def test_exact_dependency_set_is_required(m, paths):
    with pytest.raises(ValueError, match="dependency set"):
        m.dependencies({"wait_for_studies": paths})


@pytest.mark.parametrize("relative", ["seed_audit.json", "prepare.py", "initialization.json", "configs/s52091.yaml",
                                      "inputs/founder.json", "inputs/pilot.json", "inputs/provenance.json",
                                      "sources/D.py", "initialization/s52091.npy", "initialization/s52092.npy"])
def test_changed_preparation_or_fixed_input_is_rejected(m, relative):
    (m.STUDY / relative).write_text("changed")
    with pytest.raises(ValueError, match="differs"):
        m.check_protocol()


@pytest.mark.parametrize("relative", ["src/engine.py", "D/config.yaml", "scripts/taskvar_confirm.py"])
def test_changed_engine_template_or_helper_is_rejected(m, relative):
    (m.ROOT / relative).write_text("changed")
    with pytest.raises(ValueError, match="differs"):
        m.check_protocol()


@pytest.mark.parametrize("relative", ["S/run_budgeted.py", "S/measure.py", "R/protocol.json", "R/run_budgeted.py"])
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
        del ready["dependencies"]["R"]
    else:
        del ready["dependencies"]["R"]["run_budgeted.py"]
    m.save(m.STUDY / "ready.json", ready)
    with pytest.raises(ValueError, match="pin set|differs from registration"):
        m.check_ready()


def test_waiting_release_change_is_terminal_and_launches_nothing(m, monkeypatch):
    m.save(m.ROOT / "R/budget.json", {"status": "running"})
    monkeypatch.setattr(m.subprocess, "Popen", lambda *a, **kw: pytest.fail("launched"))

    def wait(_):
        value = json.loads((m.STUDY / "budget.json").read_text())
        assert value["status"] == "waiting_for_workers" and value["ready"] == m.ready
        m.save(m.ROOT / "R/budget.json", {"status": "complete", "running": {}, "queued": []})
        m.save(m.STUDY / "ready.json", {**m.ready, "release": "changed"})

    monkeypatch.setattr(m.time, "sleep", wait)
    with pytest.raises(ValueError, match="readiness or protocol changed"):
        m.main()
    value = json.loads((m.STUDY / "budget.json").read_text())
    assert value["status"] == "monitor_failed" and value["running"] == {} and value["queued"] == []


@pytest.mark.parametrize("report,lives", [(None, 4608), ("incomplete", 4608), ("complete", 4607)])
def test_successful_exit_requires_exact_completed_science(m, monkeypatch, report, lives):
    launch_mock(m, monkeypatch, report=report, lives=lives)
    with pytest.raises((ValueError, FileNotFoundError)):
        m.main()
    assert json.loads((m.STUDY / "budget.json").read_text())["status"] == "monitor_failed"


def test_failed_search_never_launches_confirmation(m, monkeypatch):
    calls, _ = launch_mock(m, monkeypatch, codes=(0, 1, 0))
    record = run(m, 1)
    assert len(calls) == 3 and record["status"] == "incomplete" and record["reason"] == "job_failed"


def test_final_confirmation_cpu_race_cannot_report_complete(m, monkeypatch):
    calls, _ = launch_mock(m, monkeypatch)
    monkeypatch.setattr(m, "child_cpu", lambda: m.CAP + 1 if len(calls) == 4 else 10)
    record = run(m, 1)
    assert record["status"] == "incomplete" and record["reason"] == "cpu_budget_exhausted"


def test_search_consumption_is_not_reset_before_confirmation(m, monkeypatch):
    calls, _ = launch_mock(m, monkeypatch)
    monkeypatch.setattr(m, "child_cpu", lambda: m.CAP - 10 if len(calls) == 3 else 10)
    record = run(m, 1)
    assert len(calls) == 3 and record["reason"] == "cpu_budget_exhausted"
    assert record["cpu_seconds"] == m.CAP - 10


def test_changed_source_before_final_report_cannot_be_complete(m, monkeypatch):
    calls, _ = launch_mock(m, monkeypatch)
    original = m.subprocess.Popen

    def change_on_confirmation(*args, **kwargs):
        process = original(*args, **kwargs)
        if len(calls) == 4:
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
    assert [value[0] for value in limits] == [14390, 14390, 14290, 14390]
    assert all(parent == m.os.getpid() for _, parent in limits)


def test_cap_terminates_both_workers_then_kills_after_two_seconds(m, monkeypatch):
    calls, processes = launch_mock(m, monkeypatch, codes=(0, None, None))
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
    assert len(calls) == 3 and record["reason"] == "cpu_budget_exhausted"
    assert signals[0][1] == signal.SIGKILL  # completed phase0 group cleanup
    signals = signals[1:]
    assert [item[1] for item in signals[:4]] == [signal.SIGTERM, signal.SIGTERM, signal.SIGKILL, signal.SIGKILL]
    assert all(item[1] == signal.SIGKILL for item in signals[4:])
    assert signals[2][2] - signals[0][2] == 2
    assert not record["running"] and not record["queued"]


def test_spawn_failure_cleans_up_first_worker_and_records_budget(m, monkeypatch):
    calls, processes = launch_mock(m, monkeypatch, codes=(0, None, None))
    original = m.subprocess.Popen

    def fail_second(*args, **kwargs):
        if len(calls) == 2:
            raise OSError("synthetic spawn failure")
        return original(*args, **kwargs)

    monkeypatch.setattr(m.subprocess, "Popen", fail_second)
    signals = []

    def send(pid, signum):
        signals.append(signum)
        next(process for process in processes if process.pid == pid).returncode = -signum

    monkeypatch.setattr(m.os, "killpg", send)
    with pytest.raises(OSError, match="spawn failure"):
        m.main()
    value = json.loads((m.STUDY / "budget.json").read_text())
    assert value["status"] == "monitor_failed" and value["cpu_seconds"] == 10
    assert not value["queued"] and not value["running"] and signals == [signal.SIGKILL, signal.SIGTERM, signal.SIGKILL]


@pytest.mark.parametrize("folder", ["runs", "confirmation", "logs", "references", "references.pending"])
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


def test_waiting_monitor_cpu_can_exhaust_allocation_without_launch(m, monkeypatch):
    m.save(m.ROOT / "R/budget.json", {"status": "running"})
    monkeypatch.setattr(m, "own_cpu", lambda: m.CAP - m.RESERVE)
    monkeypatch.setattr(m.subprocess, "Popen", lambda *a, **kw: pytest.fail("launched"))
    with pytest.raises(RuntimeError, match="exhausted while waiting"):
        m.main()
    value = json.loads((m.STUDY / "budget.json").read_text())
    assert value["status"] == "monitor_failed" and value["reason"] == "cpu_budget_exhausted"
    assert value["cpu_seconds"] == m.CAP - m.RESERVE + 10
    assert not value["queued"] and not value["running"]


def test_cpu_includes_monitor_reaped_children_and_both_live_trees(m, monkeypatch):
    monkeypatch.setattr(m, "own_cpu", lambda: 17.5)
    monkeypatch.setattr(m, "active_cpu", lambda pid: {100: 3.5, 101: 5.0}[pid])
    assert m.consumed_cpu({100: None, 101: None}) == 36


def test_reaped_workers_receive_final_group_cleanup(m, monkeypatch):
    calls, processes = launch_mock(m, monkeypatch)
    signals = []
    monkeypatch.setattr(m.os, "killpg", lambda pid, signum: signals.append((pid, signum)))
    run(m)
    assert len(calls) == 4
    assert signals == [(p.pid, signal.SIGKILL) for p in processes]


def test_cleanup_kills_group_after_direct_child_exits_on_term(m, monkeypatch):
    from io import StringIO

    process, log, calls = Process(100), StringIO(), []
    monkeypatch.setattr(m.os, "killpg", lambda pid, signum: calls.append((pid, signum)))
    running = {100: (process, log, "test")}
    m.cleanup(running)
    assert calls == [(100, signal.SIGTERM), (100, signal.SIGKILL)]
    assert log.closed and not running


def test_insufficient_remaining_rlimit_is_rejected(m, monkeypatch):
    monkeypatch.setattr(m.ctypes, "CDLL", lambda *a: SimpleNamespace(prctl=lambda *args: 0))
    monkeypatch.setattr(m.os, "getppid", lambda: 321)
    monkeypatch.setattr(m.resource, "setrlimit", lambda *a: pytest.fail("set insufficient limit"))
    with pytest.raises(ValueError, match="not enough CPU"):
        m.child_limit(1.9, 321)


@pytest.mark.parametrize("status", [None, "incomplete", "failed"])
def test_phase0_must_freeze_both_references_before_any_search(m, monkeypatch, status):
    calls, _ = launch_mock(m, monkeypatch, references=status)
    with pytest.raises((ValueError, FileNotFoundError)):
        m.main()
    assert len(calls) == 1 and "--freeze-references" in calls[0][0]
    record = json.loads((m.STUDY / "budget.json").read_text())
    assert record["status"] == "monitor_failed" and record["phase"] == "references"
    assert record["frozen_references"] is None and not record["running"] and not record["queued"]


def test_failed_reference_audit_never_starts_searches(m, monkeypatch):
    calls, _ = launch_mock(m, monkeypatch, codes=(1,))
    record = run(m, 1)
    assert len(calls) == 1 and record["reason"] == "job_failed"
    assert record["phase"] == "references" and record["frozen_references"] is None


@pytest.mark.parametrize("change", ["mapping", "runs", "labels", "empty_files", "missing_file", "bytes",
                                    "absolute", "parent_path", "self_pin", "bad_digest", "pending"])
def test_invalid_reference_freeze_receipt_blocks_all_searches(m, monkeypatch, change):
    calls, _ = launch_mock(m, monkeypatch)
    original = m.subprocess.Popen

    def corrupt(*args, **kwargs):
        process = original(*args, **kwargs)
        if len(calls) != 1:
            pytest.fail("search launched with invalid phase0")
        path = m.STUDY / "references/report.json"
        report = json.loads(path.read_text())
        if change == "mapping":
            report["mapping"]["52091"] = 51090
        elif change in ("runs", "labels"):
            report[change].reverse()
        elif change == "empty_files":
            report["files"] = {}
        elif change == "missing_file":
            (m.STUDY / "references/D51089.json").unlink()
        elif change == "bytes":
            (m.STUDY / "references/D51089.json").write_text("changed input")
        elif change in ("absolute", "parent_path", "self_pin"):
            invalid = {"absolute": "/outside.json", "parent_path": "../outside.json",
                       "self_pin": "report.json"}[change]
            report["files"][invalid] = "a" * 64
        elif change == "bad_digest":
            report["files"]["D51089.json"] = "z" * 64
        else:
            (m.STUDY / "references.pending").mkdir()
        m.save(path, report)
        return process

    monkeypatch.setattr(m.subprocess, "Popen", corrupt)
    with pytest.raises((ValueError, FileNotFoundError)):
        m.main()
    assert len(calls) == 1


@pytest.mark.parametrize("stage", [2, 3, 4])
def test_frozen_references_cannot_change_after_phase0(m, monkeypatch, stage):
    calls, _ = launch_mock(m, monkeypatch)
    original = m.subprocess.Popen

    def tamper(*args, **kwargs):
        process = original(*args, **kwargs)
        if len(calls) == stage:
            path = m.STUDY / "references/D51089.json"
            path.write_text("a substituted reference")
            # Updating the report too still cannot alter the original phase0 snapshot.
            report = json.loads((m.STUDY / "references/report.json").read_text())
            report["files"][path.name] = m.sha(path)
            m.save(m.STUDY / "references/report.json", report)
        return process

    monkeypatch.setattr(m.subprocess, "Popen", tamper)
    with pytest.raises(ValueError, match="receipt changed after phase0"):
        m.main()
    assert len(calls) == stage
    assert json.loads((m.STUDY / "budget.json").read_text())["status"] == "monitor_failed"


def test_phase0_cpu_is_not_reset_before_search(m, monkeypatch):
    calls, _ = launch_mock(m, monkeypatch)
    monkeypatch.setattr(m, "child_cpu", lambda: m.CAP - 10 if calls else 10)
    record = run(m, 1)
    assert len(calls) == 1 and record["reason"] == "cpu_budget_exhausted"
    assert record["cpu_seconds"] == m.CAP - 10


@pytest.mark.parametrize("field", ["planned_genome_lives", "genome_lives", "completed_genome_lives"])
def test_every_final_count_requires_all4608_lives(m, monkeypatch, field):
    calls, _ = launch_mock(m, monkeypatch)
    original = m.subprocess.Popen

    def partial(*args, **kwargs):
        process = original(*args, **kwargs)
        if len(calls) == 4:
            path = m.STUDY / "confirmation/report.json"
            report = json.loads(path.read_text())
            report[field] = 4096
            m.save(path, report)
        return process

    monkeypatch.setattr(m.subprocess, "Popen", partial)
    with pytest.raises(ValueError, match="all prescribed lives"):
        m.main()


def test_dependency_readiness_cannot_rebind_away_from_registration(m):
    path = m.ROOT / "R/protocol.json"
    path.write_text("changed resource registration")
    m.ready["dependencies"]["R"]["protocol.json"] = m.sha(path)
    m.save(m.STUDY / "ready.json", m.ready)
    with pytest.raises(ValueError, match="differs from registration"):
        m.check_ready()


@pytest.mark.parametrize("field,value", [("generations", 16), ("planned_genome_lives", 37548),
    ("selection_genome_lives", 32769), ("periodic_valid_genome_lives", 160), ("tiny_final_genome_lives", 0),
    ("max_simulation_threads", 5), ("max_cpu_seconds", 14401)])
def test_study_scope_cannot_drift(m, field, value):
    m.protocol[field] = value
    m.save(m.STUDY / "protocol.json", m.protocol)
    with pytest.raises(ValueError, match="scope differs"):
        m.check_protocol()


def test_prctl_failure_never_sets_worker_cpu_limit(m, monkeypatch):
    monkeypatch.setattr(m.ctypes, "CDLL", lambda *a: SimpleNamespace(prctl=lambda *args: -1))
    monkeypatch.setattr(m.resource, "setrlimit", lambda *a: pytest.fail("continued without parent binding"))
    with pytest.raises(OSError, match="bind worker lifetime"):
        m.child_limit(100, 321)


def test_active_cpu_counts_descendants_once_and_excludes_unrelated_processes(m, monkeypatch):
    loader = importlib.util.spec_from_file_location("scoring_budget_cpu_test", HERE / "run_budgeted.py")
    mod = importlib.util.module_from_spec(loader)
    loader.loader.exec_module(mod)
    monkeypatch.setattr(mod.os, "sysconf", lambda name: 100)

    class Entry:
        def __init__(self, pid, parent, ticks):
            self.name, self.parent, self.ticks = str(pid), parent, ticks

        def __truediv__(self, name):
            assert name == "stat"
            return self

        def read_text(self):
            fields = ["0"] * 20
            fields[1] = str(self.parent)
            fields[11:15] = map(str, self.ticks)
            return self.name + " (a child with ) spaces) " + " ".join(fields)

    entries = [Entry(100, 99, [10, 20, 30, 40]), Entry(101, 100, [10, 15, 20, 5]),
               Entry(102, 101, [10, 5, 5, 5]), Entry(888, 99, [10000, 0, 0, 0])]
    monkeypatch.setattr(mod, "Path", lambda name: SimpleNamespace(iterdir=lambda: iter(entries)))
    assert mod.active_cpu(100) == 1.75


def test_cpu_used_by_final_reference_audit_cannot_cross_cap_and_report_complete(m, monkeypatch):
    calls, _ = launch_mock(m, monkeypatch)
    original = m.check_references
    used = [10]
    monkeypatch.setattr(m, "child_cpu", lambda: used[0])

    def audit(protocol, previous=None):
        result = original(protocol, previous)
        if len(calls) == 4:
            used[0] = m.CAP + 1
        return result

    monkeypatch.setattr(m, "check_references", audit)
    record = run(m, 1)
    assert record["status"] == "incomplete" and record["reason"] == "cpu_budget_exhausted"
    assert record["cpu_seconds"] == m.CAP + 1


@pytest.mark.parametrize("excess", [0, 1])
def test_authoritative_final_record_cpu_sample_rejects_cap_crossing(m, monkeypatch, excess):
    calls, _ = launch_mock(m, monkeypatch)
    original = m.check_references
    final_samples = []

    def audit(protocol, previous=None):
        result = original(protocol, previous)
        if len(calls) == 4:
            final_samples.extend([m.CAP - 1, m.CAP + excess])
        return result

    def sample():
        return final_samples.pop(0) if final_samples else 10

    monkeypatch.setattr(m, "check_references", audit)
    monkeypatch.setattr(m, "child_cpu", sample)
    record = run(m, 1)
    assert len(calls) == 4 and not final_samples
    assert record["status"] == "incomplete" and record["reason"] == "cpu_budget_exhausted"
    assert record["exit_code"] == 1 and record["cpu_seconds"] == m.CAP + excess
