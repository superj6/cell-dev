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
    loader = importlib.util.spec_from_file_location("weight_updates_monitor_test", HERE / "run_budgeted.py")
    mod = importlib.util.module_from_spec(loader)
    loader.loader.exec_module(mod)
    mod.ROOT, mod.STUDY = tmp_path, tmp_path / "R"
    mod.DEPENDENCIES = ("Q",)
    mod.original_check_ready = mod.check_ready
    mod.original_cpu = mod.cpu
    mod.STUDY.mkdir()
    mod.save(mod.STUDY / "protocol.json", {"wait_for_studies": ["Q"], "genome_lives": 4608,
                                            "planned_genome_lives": 4608, "max_cpu_seconds": 3600,
                                            "threads": 2})
    mod.save(tmp_path / "Q/budget.json", {"status": "complete", "running": {}, "queued": []})
    monkeypatch.setattr(mod, "check_ready", lambda: {})
    monkeypatch.setattr(mod, "cpu", lambda pid=None: 0)
    monkeypatch.setattr(mod.os, "killpg", lambda *args: None)
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
        assert command == [str(m.ROOT / ".venv/bin/python"), str(m.STUDY / "measure.py"), "--run"]
        assert kwargs["cwd"] == m.ROOT
        assert kwargs["env"]["CELLDEV_WEIGHT_UPDATES_MONITOR_PID"] == str(m.os.getpid())
        assert kwargs["env"]["ATEN_CPU_CAPABILITY"] == "avx2"
        assert kwargs["env"]["CELL_DEV_CACHE"] == str(m.ROOT / "outputs/e1_resume/kernel-cache")
        assert kwargs["env"]["OMP_NUM_THREADS"] == kwargs["env"]["MKL_NUM_THREADS"] == "2"
        assert kwargs["env"]["OPENBLAS_NUM_THREADS"] == "2" and "CELLDEV_THREADS_FILE" not in kwargs["env"]
        assert kwargs["start_new_session"]
        if report:
            m.save(m.STUDY / "measurement/report.json",
               {"status": "complete", "genome_lives": 4608, "planned_genome_lives": 4608,
                "completed_genome_lives": 4608})
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
        m.save(m.ROOT / "Q/budget.json", {"status": status})
        assert not m.dependency_available()
    m.save(m.ROOT / "Q/budget.json", {"status": "cpu_budget_exhausted"})
    with pytest.raises(ValueError, match="abnormally"):
        m.dependency_available()
    m.save(m.ROOT / "Q/budget.json", {"status": "complete", "running": {"1": "leftover"}})
    with pytest.raises(ValueError, match="active work"):
        m.dependency_available()


@pytest.mark.parametrize("name", ["Q"])
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


@pytest.mark.parametrize("paths", [[], ["Q", "Q"], ["Q", "unregistered"], ["unregistered"]])
def test_exact_registered_dependency_is_required(m, paths):
    m.save(m.STUDY / "protocol.json", {"wait_for_studies": paths})
    with pytest.raises(ValueError, match="dependency set differs"):
        m.dependency_available()


def readiness_fixture(m, monkeypatch):
    for name in m.READY_FILES:
        if name == "protocol.json":
            continue
        (m.STUDY / name).write_text("synthetic fixture source\n")
    for dependency in m.DEPENDENCIES:
        for name in ("protocol.json", "run_budgeted.py"):
            (m.ROOT / dependency / name).write_text("synthetic dependency\n")
    dependencies = {path: {name: m.sha(m.ROOT / path / name) for name in
                           ("protocol.json", "run_budgeted.py")} for path in m.DEPENDENCIES}
    protocol = json.loads((m.STUDY / "protocol.json").read_text())
    protocol["dependencies"] = dependencies
    m.save(m.STUDY / "protocol.json", protocol)
    ready = {"files": {name: m.sha(m.STUDY / name) for name in m.READY_FILES}, "dependencies": dependencies}
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


@pytest.mark.parametrize("dependency,name", [("Q", "protocol.json"), ("Q", "run_budgeted.py")])
def test_changed_dependency_source_is_rejected(m, monkeypatch, dependency, name):
    readiness_fixture(m, monkeypatch)
    (m.ROOT / dependency / name).write_text("changed dependency")
    with pytest.raises(ValueError, match="dependency source differs"):
        m.original_check_ready()


@pytest.mark.parametrize("change,message", [
    ("own_extra", "readiness file pin set"), ("missing_dependency", "dependency readiness pin set"),
    ("missing_source", "dependency readiness differs")])
def test_readiness_pin_sets_cannot_be_partial_or_expanded(m, monkeypatch, change, message):
    ready = readiness_fixture(m, monkeypatch)
    if change == "own_extra":
        ready["files"]["other.py"] = "unexpected"
    elif change == "missing_dependency":
        del ready["dependencies"]["Q"]
    else:
        del ready["dependencies"]["Q"]["run_budgeted.py"]
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
    assert error.value.code == 0 and len(checks) == 3 and len(calls) == 1
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
    monkeypatch.setattr(m, "cpu", lambda pid=None: 3589 if pid is not None else 0)
    signals = []

    def killpg(pid, sig):
        signals.append(sig)
        if sig == signal.SIGKILL:
            process.returncode = -sig
    monkeypatch.setattr(m.os, "killpg", killpg)
    with pytest.raises(SystemExit) as error:
        m.main()
    assert error.value.code == 1 and signals[:2] == [signal.SIGTERM, signal.SIGKILL]
    assert all(sig == signal.SIGKILL for sig in signals[2:])
    record = json.loads((m.STUDY / "budget.json").read_text())
    assert record["cpu_seconds"] == 0 and record["cpu_budget_exhausted"]


def test_final_cpu_race_cannot_report_success(m, monkeypatch):
    popen(m, monkeypatch, Process())
    calls = iter([0, 0, 3601])
    monkeypatch.setattr(m, "cpu", lambda pid=None: next(calls))
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
    assert saved["running"] == {} and saved["queued"] == [] and signals[:2] == [signal.SIGTERM, signal.SIGKILL]
    assert all(sig == signal.SIGKILL for sig in signals[2:])


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
    m.child_limit(3600, 123)
    assert signals == [(1, signal.SIGKILL, 0, 0, 0)]
    assert limits == [(m.resource.RLIMIT_CPU, (3599, 3600))]


def test_wrong_life_count_does_not_mark_complete(m, monkeypatch):
    def spawn(*args, **kwargs):
        m.save(m.STUDY / "measurement/report.json",
               {"status": "complete", "genome_lives": 4607, "planned_genome_lives": 4608,
                "completed_genome_lives": 4608})
        return Process()

    monkeypatch.setattr(m.subprocess, "Popen", spawn)
    with pytest.raises(SystemExit) as error:
        m.main()
    assert error.value.code == 1


def test_abnormal_wait_writes_terminal_receipt_without_launch(m, monkeypatch):
    m.save(m.ROOT / "Q/budget.json", {"status": "incomplete"})
    monkeypatch.setattr(m.subprocess, "Popen", lambda *a, **kw: pytest.fail("launched"))
    with pytest.raises(ValueError, match="abnormally"):
        m.main()
    saved = json.loads((m.STUDY / "budget.json").read_text())
    assert saved["status"] == "monitor_failed" and not saved["running"] and not saved["queued"]


def test_remaining_limit_is_captured_in_parent_and_budget_precedes_spawn(m, monkeypatch):
    captured = []
    monkeypatch.setattr(m, "cpu", lambda pid=None: 23)
    monkeypatch.setattr(m.os, "getpid", lambda: 456)
    monkeypatch.setattr(m, "child_limit", lambda seconds, parent: captured.append((seconds, parent)))

    def spawn(*args, **kwargs):
        assert (m.STUDY / "budget.json").exists()
        kwargs["preexec_fn"]()
        m.save(m.STUDY / "measurement/report.json",
               {"status": "complete", "genome_lives": 4608, "planned_genome_lives": 4608,
                "completed_genome_lives": 4608})
        return Process()

    monkeypatch.setattr(m.subprocess, "Popen", spawn)
    with pytest.raises(SystemExit) as error:
        m.main()
    assert error.value.code == 0 and captured == [(3577, 456)]


def test_prelaunch_consumed_budget_prevents_worker(m, monkeypatch):
    monkeypatch.setattr(m, "cpu", lambda pid=None: 3590)
    monkeypatch.setattr(m.subprocess, "Popen", lambda *a, **kw: pytest.fail("launched"))
    with pytest.raises(ValueError, match="cumulative CPU"):
        m.main()


def test_exact_parent_death_race_fails_closed(m, monkeypatch):
    monkeypatch.setattr(m.ctypes, "CDLL", lambda *a: SimpleNamespace(prctl=lambda *args: 0))
    monkeypatch.setattr(m.os, "getppid", lambda: 999)
    monkeypatch.setattr(m.os, "_exit", lambda code: (_ for _ in ()).throw(SystemExit(code)))
    monkeypatch.setattr(m.resource, "setrlimit", lambda *args: pytest.fail("wrong parent received limit"))
    with pytest.raises(SystemExit) as error:
        m.child_limit(3600, 123)
    assert error.value.code == 1


def test_failed_parent_death_binding_fails_closed(m, monkeypatch):
    monkeypatch.setattr(m.ctypes, "CDLL", lambda *a: SimpleNamespace(prctl=lambda *args: -1))
    with pytest.raises(OSError):
        m.child_limit(3600, 123)


def test_group_kill_follows_even_when_direct_child_exits_on_term(m, monkeypatch):
    process, signals = Process(None), []

    def killpg(pid, sig):
        signals.append(sig)
        if sig == signal.SIGTERM:
            process.returncode = -sig

    monkeypatch.setattr(m.os, "killpg", killpg)
    assert m.terminate(process) == -signal.SIGTERM
    assert signals == [signal.SIGTERM, signal.SIGKILL]


def test_final_release_pin_change_prevents_success(m, monkeypatch):
    releases = iter([{"fixed": 1}, {"fixed": 1}, {"fixed": 2}])
    monkeypatch.setattr(m, "check_ready", lambda: next(releases))
    popen(m, monkeypatch, Process())
    with pytest.raises(ValueError, match="during measurement"):
        m.main()
    saved = json.loads((m.STUDY / "budget.json").read_text())
    assert saved["status"] == "monitor_failed" and not saved["running"]


def test_cpu_includes_monitor_reaped_children_and_live_descendants(m, monkeypatch):
    usage = {m.resource.RUSAGE_SELF: SimpleNamespace(ru_utime=1, ru_stime=2),
             m.resource.RUSAGE_CHILDREN: SimpleNamespace(ru_utime=3, ru_stime=4)}
    monkeypatch.setattr(m.resource, "getrusage", lambda who: usage[who])
    monkeypatch.setattr(m.os, "sysconf", lambda name: 100)

    class Entry:
        def __init__(self, pid, parent, counters):
            self.name, self.parent, self.counters = str(pid), parent, counters

        def __truediv__(self, name):
            assert name == "stat"
            return self

        def read_text(self):
            fields = ["0"] * 20
            fields[1] = str(self.parent)
            for index, value in zip((11, 12, 13, 14), self.counters):
                fields[index] = str(value)
            return f"{self.name} (mock process) " + " ".join(fields)

    entries = [Entry(100, 9, (10, 20, 5, 5)), Entry(101, 100, (30, 10, 0, 0)),
               Entry(102, 9, (1000, 1000, 1000, 1000))]
    monkeypatch.setattr(m, "Path", lambda name: SimpleNamespace(iterdir=lambda: iter(entries)))
    assert m.original_cpu() == 10
    assert m.original_cpu(100) == pytest.approx(10.8)


@pytest.mark.parametrize("key,value", [
    ("genome_lives", 4609),
    ("max_cpu_seconds", 3601), ("threads", 3)])
def test_registered_scope_cannot_drift(m, monkeypatch, key, value):
    readiness_fixture(m, monkeypatch)
    protocol = json.loads((m.STUDY / "protocol.json").read_text())
    protocol[key] = value
    m.save(m.STUDY / "protocol.json", protocol)
    with pytest.raises(ValueError, match="scope or resource"):
        m.original_check_ready()


def test_dependency_digest_must_match_registration_even_if_file_matches(m, monkeypatch):
    ready = readiness_fixture(m, monkeypatch)
    path = m.ROOT / "Q/protocol.json"
    path.write_text("new dependency protocol")
    ready["dependencies"]["Q"]["protocol.json"] = m.sha(path)
    m.save(m.STUDY / "ready.json", ready)
    with pytest.raises(ValueError, match="differs from registration"):
        m.original_check_ready()


@pytest.mark.parametrize("name", ["prepare.py", "test_measure.py", "PREREG.md"])
def test_release_binds_preparation_validation_and_registration(m, monkeypatch, name):
    readiness_fixture(m, monkeypatch)
    (m.STUDY / name).write_text("changed")
    with pytest.raises(ValueError, match="readiness pin differs"):
        m.original_check_ready()


def test_wrong_planned_count_does_not_mark_complete(m, monkeypatch):
    def spawn(*args, **kwargs):
        m.save(m.STUDY / "measurement/report.json", {
            "status": "complete", "genome_lives": 4608, "planned_genome_lives": 4607,
            "completed_genome_lives": 4608})
        return Process()

    monkeypatch.setattr(m.subprocess, "Popen", spawn)
    with pytest.raises(SystemExit) as error:
        m.main()
    assert error.value.code == 1
    assert json.loads((m.STUDY / "budget.json").read_text())["status"] == "incomplete"


def test_final_pin_change_cannot_mark_complete(m, monkeypatch):
    calls = iter([{"fixed": "before"}, {"fixed": "before"}, {"fixed": "after"}])
    monkeypatch.setattr(m, "check_ready", lambda: next(calls))
    popen(m, monkeypatch, Process())
    with pytest.raises(ValueError, match="readiness changed during"):
        m.main()
    record = json.loads((m.STUDY / "budget.json").read_text())
    assert record["status"] == "monitor_failed"
    assert record["ready"] == {"fixed": "before"} and not record["running"] and not record["queued"]


def test_termination_kills_group_even_when_leader_exits_after_term(m, monkeypatch):
    signals = []
    monkeypatch.setattr(m.os, "killpg", lambda pid, sig: signals.append((pid, sig)))
    assert m.terminate(Process(0)) == 0
    assert signals == [(123, signal.SIGTERM), (123, signal.SIGKILL)]


def test_cpu_counts_monitor_reaped_and_every_live_descendant_once(m, monkeypatch):
    loader = importlib.util.spec_from_file_location("weight_updates_cpu_test", HERE / "run_budgeted.py")
    mod = importlib.util.module_from_spec(loader)
    loader.loader.exec_module(mod)
    usage = {mod.resource.RUSAGE_SELF: SimpleNamespace(ru_utime=2, ru_stime=3),
             mod.resource.RUSAGE_CHILDREN: SimpleNamespace(ru_utime=7, ru_stime=11)}
    monkeypatch.setattr(mod.resource, "getrusage", lambda who: usage[who])
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
    assert mod.cpu() == 23
    assert mod.cpu(100) == 24.75


def test_waiting_cpu_exhaustion_is_terminal_without_spawn(m, monkeypatch):
    monkeypatch.setattr(m, "dependency_available", lambda: False)
    monkeypatch.setattr(m, "cpu", lambda pid=None: 3588)
    monkeypatch.setattr(m.subprocess, "Popen", lambda *a, **kw: pytest.fail("waiting cap launched"))
    with pytest.raises(ValueError, match="waiting exhausted"):
        m.main()
    record = json.loads((m.STUDY / "budget.json").read_text())
    assert record["cpu_seconds"] == 3588 and record["status"] == "monitor_failed"
    assert not record["running"] and not record["queued"]


def test_failed_spawn_leaves_budget_receipt_and_refuses_restart(m, monkeypatch):
    def failed_spawn(*args, **kwargs):
        assert json.loads((m.STUDY / "budget.json").read_text())["status"] == "running"
        raise OSError("synthetic spawn failure")

    monkeypatch.setattr(m.subprocess, "Popen", failed_spawn)
    with pytest.raises(OSError, match="spawn failure"):
        m.main()
    assert json.loads((m.STUDY / "budget.json").read_text())["status"] == "monitor_failed"
    with pytest.raises(ValueError, match="budget record"):
        m.main()


@pytest.mark.parametrize("actual", [None, 4607, 4609])
def test_planned_count_never_substitutes_for_actual_completed_lives(m, monkeypatch, actual):
    def spawn(*args, **kwargs):
        report = {"status": "complete", "genome_lives": 4608, "planned_genome_lives": 4608}
        if actual is not None:
            report["completed_genome_lives"] = actual
        m.save(m.STUDY / "measurement/report.json", report)
        return Process()

    monkeypatch.setattr(m.subprocess, "Popen", spawn)
    with pytest.raises(SystemExit) as error:
        m.main()
    assert error.value.code == 1
    assert json.loads((m.STUDY / "budget.json").read_text())["status"] == "incomplete"


def test_normal_worker_exit_cleans_descendant_group(m, monkeypatch):
    signals = []
    monkeypatch.setattr(m.os, "killpg", lambda pid, sig: signals.append((pid, sig)))
    popen(m, monkeypatch, Process())
    with pytest.raises(SystemExit) as error:
        m.main()
    assert error.value.code == 0 and signals
    assert all(item == (123, signal.SIGKILL) for item in signals)


def test_final_error_after_leader_exit_still_cleans_group(m, monkeypatch):
    signals = []
    monkeypatch.setattr(m.os, "killpg", lambda pid, sig: signals.append((pid, sig)))
    popen(m, monkeypatch, Process())
    calls = iter([{}, {}, {"changed": True}])
    monkeypatch.setattr(m, "check_ready", lambda: next(calls))
    with pytest.raises(ValueError, match="during measurement"):
        m.main()
    assert signals and all(item == (123, signal.SIGKILL) for item in signals)
