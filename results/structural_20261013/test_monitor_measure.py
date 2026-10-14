"""Mock-only resource/stage and arithmetic checks: no scientific life is simulated."""

import importlib.util
import json
import signal
import subprocess
import sys
from copy import deepcopy
from pathlib import Path
from types import SimpleNamespace

import numpy as np
import pytest

HERE = Path(__file__).resolve().parent


def module(name, filename):
    spec = importlib.util.spec_from_file_location(name, HERE / filename)
    value = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(value)
    return value


@pytest.fixture
def monitor(monkeypatch, tmp_path):
    mod = module("structural_monitor_test", "run_budgeted.py")
    root = tmp_path / "repo"
    study = root / "outputs/autonomous_structural_20261013"
    study.mkdir(parents=True)
    monkeypatch.setattr(mod, "ROOT", root)
    monkeypatch.setattr(mod, "STUDY", study)
    monkeypatch.setattr(sys, "argv", ["run_budgeted.py", "--run"])
    files = ["prepare.py", "seed_audit.json", "run_budgeted.py", "measure.py"]
    for name in files:
        (study / name).write_text(name)
    for name in mod.HELPERS:
        path = root / "scripts" / name
        path.parent.mkdir(exist_ok=True)
        path.write_text(name)
    (root / "src").mkdir()
    (root / "src/kernel.c").write_text("fixed source")
    configs = {}
    for seed in [51089, 51090]:
        path = study / f"s{seed}.yaml"
        path.write_text(str(seed))
        configs[str(seed)] = {"path": str(path.relative_to(root)), "sha256": mod.sha(path)}
    for name in ["founder", "pilot"]:
        (study / f"{name}.json").write_text(name)
    dependency = root / "outputs/autonomous_continuation_20261013"
    dependency.mkdir()
    (dependency / "protocol.json").write_text("fixed D protocol")
    protocol = {
        "max_cpu_seconds": 14400,
        "max_simulation_threads": 4,
        "runs": [51089, 51090],
        "generations": 16,
        "structural_operators": {
            "dup_rate": 0.02,
            "del_rate": 0.01,
            "dup_split": False,
            "n_mut_scale": True,
            "existing_production_operators": True,
        },
        "configs": configs,
        "planned_genome_lives": 37548,
        "seed_audit_sha256": mod.sha(study / "seed_audit.json"),
        "prepare_sha256": mod.sha(study / "prepare.py"),
        "source_identity": {"src/kernel.c": mod.sha(root / "src/kernel.c")},
        "D_study": str(dependency.relative_to(root)),
        "D_pins": {"protocol.json": mod.sha(dependency / "protocol.json")},
    }
    for name in ["founder", "pilot"]:
        protocol[name + "_file"] = str((study / f"{name}.json").relative_to(root))
        protocol[name + "_sha256"] = mod.sha(study / f"{name}.json")
    mod.save(study / "protocol.json", protocol)
    mod.save(
        study / "ready.json",
        {
            "protocol_sha256": mod.sha(study / "protocol.json"),
            "monitor_sha256": mod.sha(study / "run_budgeted.py"),
            "measurement_sha256": mod.sha(study / "measure.py"),
            "helpers": {name: mod.sha(root / "scripts" / name) for name in mod.HELPERS},
        },
    )
    for folder in [dependency, root / "outputs/autonomous_frozen_20261013"]:
        mod.save(folder / "budget.json", {"status": "complete", "running": {}, "queued": []})
    monkeypatch.setattr(mod.os, "sched_getaffinity", lambda pid: {0, 1, 15})
    monkeypatch.setattr(mod.os, "sched_setaffinity", lambda pid, values: None)
    monkeypatch.setattr(mod.signal, "signal", lambda *args: None)
    monkeypatch.setattr(mod, "child_cpu", lambda: 0.0)
    monkeypatch.setattr(mod, "active_cpu", lambda pid: 0.0)
    clock = [0.0]
    monkeypatch.setattr(mod.time, "monotonic", lambda: clock[0])
    monkeypatch.setattr(mod.time, "sleep", lambda seconds: clock.__setitem__(0, clock[0] + seconds))
    mod.test_clock = clock
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


def successful_popen(monitor, monkeypatch, *, failure=None, live=None):
    calls, processes = [], []

    def popen(command, **kwargs):
        name = command[-1] if "--mode" in command else "search"
        assert kwargs["env"]["OMP_NUM_THREADS"] == kwargs["env"]["MKL_NUM_THREADS"] == "2"
        assert kwargs["start_new_session"] is True
        assert "CELLDEV_THREADS_FILE" not in kwargs["env"]
        if name == "neutrality":
            monitor.save(
                monitor.STUDY / "neutrality/report.json", {"status": "complete", "genome_lives": 18, "cpu_seconds": 2.0}
            )
        if name == "confirm":
            monitor.save(monitor.STUDY / "confirmation/report.json", {"status": "complete"})
        process = Process(1000 + len(calls), None if live == name else 3 if failure == name else 0)
        processes.append(process)
        calls.append(name)
        return process

    monkeypatch.setattr(monitor.subprocess, "Popen", popen)
    return calls, processes


def test_dryrun_has_no_readiness_or_process_requirement(monitor, monkeypatch, capsys):
    (monitor.STUDY / "ready.json").unlink()
    monkeypatch.setattr(sys, "argv", ["run_budgeted.py"])
    monkeypatch.setattr(monitor.subprocess, "Popen", lambda *a, **k: pytest.fail("dry run launched"))
    monitor.main()
    result = json.loads(capsys.readouterr().out)
    assert result["simulated_lives"] == 0 and result["max_cpu_seconds"] == 14400
    assert not (monitor.STUDY / "budget.json").exists()


@pytest.mark.parametrize(
    "relative",
    [
        "src/kernel.c",
        "scripts/taskvar_confirm.py",
        "outputs/autonomous_structural_20261013/measure.py",
        "outputs/autonomous_structural_20261013/s51089.yaml",
        "outputs/autonomous_structural_20261013/founder.json",
        "outputs/autonomous_continuation_20261013/protocol.json",
    ],
)
def test_changed_source_config_input_or_control_refuses_before_process(monitor, monkeypatch, relative):
    (monitor.ROOT / relative).write_text("altered")
    monkeypatch.setattr(monitor.subprocess, "Popen", lambda *a, **k: pytest.fail("changed pin launched"))
    with pytest.raises(ValueError, match="differs"):
        monitor.main()


def test_all_predecessors_must_complete_and_failed_predecessor_stops(monitor):
    protocol = monitor.check_protocol()
    dependency = monitor.ROOT / protocol["D_study"]
    assert monitor.prerequisites(protocol)
    monitor.save(dependency / "budget.json", {"status": "running", "running": {"1": "confirm"}, "queued": []})
    assert not monitor.prerequisites(protocol)
    monitor.save(dependency / "budget.json", {"status": "complete", "running": {}, "queued": []})
    optional = monitor.ROOT / "outputs/autonomous_discrimination_20261013"
    monitor.save(optional / "ready.json", {})
    assert not monitor.prerequisites(protocol)
    monitor.save(optional / "budget.json", {"status": "job_failed", "running": {}, "queued": []})
    with pytest.raises(ValueError, match="abnormally"):
        monitor.prerequisites(protocol)
    monitor.save(optional / "budget.json", {"status": "complete", "running": {"1": "stale"}, "queued": []})
    with pytest.raises(ValueError, match="active work"):
        monitor.prerequisites(protocol)


def test_stages_and_two_search_limit(monitor, monkeypatch):
    calls, _ = successful_popen(monitor, monkeypatch)
    snapshots = []
    real_save = monitor.save

    def save(path, value):
        snapshots.append(deepcopy(value))
        real_save(path, value)

    monkeypatch.setattr(monitor, "save", save)
    with pytest.raises(SystemExit) as error:
        monitor.main()
    assert error.value.code == 0
    assert calls == ["neutrality", "search", "search", "confirm"]
    assert all(len(value.get("running", {})) <= 2 for value in snapshots)
    result = json.loads((monitor.STUDY / "budget.json").read_text())
    assert result["status"] == "complete" and len(result["completed"]) == 4


def test_failed_neutrality_does_not_launch_search(monitor, monkeypatch):
    calls, _ = successful_popen(monitor, monkeypatch, failure="neutrality")
    with pytest.raises(SystemExit) as error:
        monitor.main()
    assert error.value.code == 1 and calls == ["neutrality"]
    assert json.loads((monitor.STUDY / "budget.json").read_text())["status"] == "job_failed"


@pytest.mark.parametrize(
    "stage,expected", [("neutrality", "neutrality_budget_exhausted"), ("search", "cpu_budget_exhausted")]
)
def test_cpu_stop_terms_then_kills_with_no_confirmation(monitor, monkeypatch, stage, expected):
    calls, processes = successful_popen(monitor, monkeypatch, live=stage)
    monkeypatch.setattr(monitor, "active_cpu", lambda pid: 27.0 if stage == "neutrality" else 7191.0)
    signals = []

    def killpg(pid, sig):
        signals.append((pid, sig))
        if sig == signal.SIGKILL:
            next(p for p in processes if p.pid == pid).returncode = -sig

    monkeypatch.setattr(monitor.os, "killpg", killpg)
    with pytest.raises(SystemExit) as error:
        monitor.main()
    assert error.value.code == 1 and "confirm" not in calls
    for process in processes:
        if process.returncode < 0:
            assert [sig for pid, sig in signals if pid == process.pid] == [signal.SIGTERM, signal.SIGKILL]
    result = json.loads((monitor.STUDY / "budget.json").read_text())
    assert result["status"] == expected
    assert result["queued"] == [] and result["running"] == {}


def test_final_exit_race_cannot_report_completion_above_cap(monitor, monkeypatch):
    calls, _ = successful_popen(monitor, monkeypatch)
    monkeypatch.setattr(monitor, "child_cpu", lambda: 14401.0 if calls[-1:] == ["confirm"] else 0.0)
    with pytest.raises(SystemExit) as error:
        monitor.main()
    assert error.value.code == 1
    assert json.loads((monitor.STUDY / "budget.json").read_text())["status"] == "cpu_budget_exhausted"


def test_existing_budget_and_artifacts_block_unaccounted_restart(monitor, monkeypatch):
    monkeypatch.setattr(monitor.subprocess, "Popen", lambda *a, **k: pytest.fail("restarted"))
    monitor.save(monitor.STUDY / "budget.json", {"cpu_seconds": 2})
    with pytest.raises(ValueError, match="budget record"):
        monitor.main()
    (monitor.STUDY / "budget.json").unlink()
    (monitor.STUDY / "neutrality").mkdir()
    with pytest.raises(ValueError, match="unaccounted"):
        monitor.main()


def test_child_cpu_limit_and_monitor_lifetime_binding(monitor, monkeypatch):
    calls, limits = [], []
    monkeypatch.setattr(
        monitor.ctypes, "CDLL", lambda arg: SimpleNamespace(prctl=lambda *args: calls.append(args) or 0)
    )
    monkeypatch.setattr(monitor.os, "getppid", lambda: 123)
    monkeypatch.setattr(monitor.resource, "setrlimit", lambda key, value: limits.append((key, value)))
    monitor.child_limit(30)
    monitor.child_limit(14000.9)
    assert calls == [(1, signal.SIGKILL, 0, 0, 0)] * 2
    assert limits == [(monitor.resource.RLIMIT_CPU, (29, 30)), (monitor.resource.RLIMIT_CPU, (13999, 14000))]


@pytest.fixture
def measure():
    return module("structural_measure_test", "measure.py")


class Lives:
    def __init__(self):
        self.ledger = np.zeros((2, 57), dtype=np.float64)
        self.hashes = np.zeros((2, 5), dtype=np.uint64)
        self.raster_n = np.array([2, 2], dtype=np.int64)
        self.fate_n = np.array([2, 2], dtype=np.int64)
        self.times = np.array([1.0, 2.0])
        self.uids = np.array([10, 11], dtype=np.int64)
        self.integers = np.arange(14, dtype=np.int64).reshape(2, 7)
        self.floats = np.arange(36, dtype=np.float64).reshape(2, 18)
        self.status = np.zeros(2)
        self.t_end = np.full(2, 1024.0)

    def spikes(self, i):
        return self.times, self.uids

    def fates(self, i):
        return self.integers, self.floats

    def __getitem__(self, name):
        return getattr(self, name)


def duplicate_lives():
    base = Lives()
    duplicate = deepcopy(base)
    duplicate.floats[:, 10] = duplicate.floats[:, 4]
    return base, duplicate


def test_neutrality_allows_only_new_gene_state_matching_source(measure):
    base, duplicate = duplicate_lives()
    measure.neutral_equal(base, duplicate, 2, 8)
    duplicate.floats[0, 10] += 1
    with pytest.raises(ValueError, match="source gene"):
        measure.neutral_equal(base, duplicate, 2, 8)


@pytest.mark.parametrize("field", ["ledger", "hashes", "raster_n", "fate_n", "times", "uids", "integers", "floats"])
def test_neutrality_rejects_each_observable_difference(measure, field):
    base, duplicate = duplicate_lives()
    getattr(duplicate, field).flat[0] += 1
    with pytest.raises(ValueError, match="changed"):
        measure.neutral_equal(base, duplicate, 2, 8)


def test_log_validation_allows_benign_equal_flags_but_rejects_stopping_and_overflow(measure):
    from src.life import spec

    value = Lives()
    plan = {"raster_cap": 2, "fate_cap": 2}
    world = SimpleNamespace(T=1024.0)
    value.status[:] = spec.STATUS["wall"] | spec.STATUS["chem_clamp"]
    measure.validate_neutral_logs(value, world, plan)
    for bit in (
        "extinct",
        "guard_cells",
        "guard_events",
        "raster_overflow",
        "fate_overflow",
        "ledger_mismatch",
        "capacity",
    ):
        value.status[:] = spec.STATUS[bit]
        with pytest.raises(ValueError, match="without guards"):
            measure.validate_neutral_logs(value, world, plan)
    value.status[:] = 0
    value.raster_n[0] = 3
    with pytest.raises(ValueError, match="capacity"):
        measure.validate_neutral_logs(value, world, plan)


def test_duration_mixture_preserves_covariance_and_negative_effects(measure):
    sequence = np.arange(256, dtype=float)
    rows = {}
    for duration, contrast in zip((768, 1024, 1536), (sequence, -sequence, np.full(256, -3.0))):
        rows[str(duration)] = {0: {"F": contrast}, 1: {"F": np.zeros(256)}}
    result = measure.mixture(rows, 0, 1)
    assert np.array_equal(result, np.full(256, -1.0))
    assert result.std(ddof=1) == 0
    assert sum((rows[str(t)][0]["F"].std(ddof=1) ** 2 for t in (768, 1024, 1536))) > 0
    with pytest.raises(ValueError, match="all three"):
        measure.mixture({"768": rows["768"]}, 0, 1)


def test_frozen_manifest_refuses_changed_identity(measure, tmp_path):
    path = tmp_path / "manifest.json"
    value = {"seeds": list(range(256)), "genotypes": ["fixed"] * 6}
    measure.frozen(path, value)
    before = path.read_bytes()
    measure.frozen(path, value)
    assert path.read_bytes() == before
    with pytest.raises(ValueError, match="frozen"):
        measure.frozen(path, {**value, "genotypes": ["changed"] * 6})
    assert path.read_bytes() == before


@pytest.mark.parametrize("change", [None, "generation", "history", "health", "best"])
def test_endpoint_is_fixed_final_rank0_with_full_clean_history(measure, monkeypatch, tmp_path, change):
    import torch

    from src import checkpoint
    from src.genome import Layout

    layout, genome = Layout.load(HERE / "inputs/founder_row38.json")
    saved = {
        "state": {
            "generation": 16,
            "curves": [{"gen": i, "pop_invalid": 0, "pop_mismatch": 0, "recheck_invalid": 0} for i in range(16)],
            "population": genome[None].clone(),
            "origins": torch.arange(16)[None],
        }
    }
    saved["state"]["origins"][0, 3] = 19
    if change == "generation":
        saved["state"]["generation"] = 15
    elif change == "history":
        saved["state"]["curves"].pop(5)
    elif change == "health":
        saved["state"]["curves"][3]["pop_invalid"] = 1
    elif change == "best":
        saved["state"]["population"][0, 0] += 1
    (tmp_path / "checkpoint.pt").write_bytes(b"fixed checkpoint")
    checked = []
    monkeypatch.setattr(checkpoint, "load", lambda path: saved)
    monkeypatch.setattr(checkpoint, "validate", lambda state, cfg, identity: checked.append((cfg, identity)))
    monkeypatch.setattr(Layout, "load", lambda path: (layout, genome))
    monkeypatch.setitem(sys.modules, "run_budgeted", SimpleNamespace(sha=lambda path: "checkpoint-sha"))
    if change is not None:
        with pytest.raises(ValueError):
            measure.endpoint(tmp_path, {"fixed": "config"}, {"fixed": "identity"})
    else:
        selected, audit = measure.endpoint(tmp_path, {"fixed": "config"}, {"fixed": "identity"})
        assert torch.equal(selected, genome)
        assert audit["active_genes"] == 8 and audit["duplicate_origin_ids"] == [19]
    assert checked == [({"fixed": "config"}, {"fixed": "identity"})]


def test_failed_neutrality_preserves_raw_failing_row_and_never_retries(measure, monkeypatch, tmp_path):
    from src.life import build

    monitor = module("structural_measure_monitor_test", "run_budgeted.py")
    protocol = json.loads((HERE / "protocol.json").read_text())
    monkeypatch.setitem(
        sys.modules,
        "run_budgeted",
        SimpleNamespace(
            check_protocol=lambda: protocol,
            check_ready=lambda: {"test": "readiness"},
            save=monitor.save,
            sha=monitor.sha,
        ),
    )
    monkeypatch.setattr(measure, "STUDY", tmp_path)
    (tmp_path / "protocol.json").write_text(json.dumps(protocol))
    calls = []

    def synthetic_run(*args, **kwargs):
        value = Lives()
        if calls:
            value.floats[:, 10] = value.floats[:, 2]
            value.ledger[0, 0] += 1
        calls.append(True)
        return value

    monkeypatch.setattr(build, "run", synthetic_run)
    with pytest.raises(ValueError, match="ledger or event hashes"):
        measure.neutrality()
    report = json.loads((tmp_path / "neutrality/report.json").read_text())
    assert report["status"] == "failed" and report["genome_lives"] == 4 and len(calls) == 2
    assert (tmp_path / "neutrality/row_01.npz").exists()
    with pytest.raises(ValueError, match="already has artifacts"):
        measure.neutrality()
    assert len(calls) == 2
