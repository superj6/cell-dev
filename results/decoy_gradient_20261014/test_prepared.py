"""Preparation tests: synthetic arrays, temporary files and mocked scoring only."""
from __future__ import annotations

import importlib.util
import json
from pathlib import Path
from types import SimpleNamespace

import numpy as np
import pytest

HERE = Path(__file__).resolve().parent


def load(name):
    spec = importlib.util.spec_from_file_location("decoy_test_" + name, HERE / (name + ".py"))
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


measure, monitor = load("measure"), load("run_budgeted")


def synthetic_row(n=8, captures=0, poison=0, misses=0, other=0):
    world = measure.spec.world("catch_speck_l4", **measure.WORLD_OVERRIDES)
    row = {key: np.zeros(n) for key in (*measure.spec.V3.LEDGER, "F_kernel", "extinct_charge", "window")}
    row["captures"][:] = captures
    row["b2_clicks"][:] = poison
    row["misses"][:] = misses
    row["income"][:] = captures * world.R_cap
    row["cost"][:] = poison * 50 + misses * world.c_miss + other
    row["F"] = row["F_kernel"] = (row["income"] - row["cost"]) / world.T
    row["window"][:] = world.T
    row["t_end"][:] = world.T
    return row


def test_seed_partition():
    values = measure.stage_seeds()
    assert {key: len(value) for key, value in values.items()} == measure.LIVES
    assert [values[key][0] for key in ("screen", "rescore", "confirm")] == [51950000, 51960000, 51970000]
    assert len(set(sum(values.values(), []))) == 1056


def test_exact_f_world():
    world = measure.spec.world("catch_speck_l4", **measure.WORLD_OVERRIDES)
    assert (world.d0, world.d_min, world.sigma, world.lam_s) == (1, 0.5, 0.6, 2)
    assert (world.b2_value, world.b2_mode, world.b2_p, world.b2_sigma) == (-50, 1, 1, 1.2)


def test_shortlist_uses_mutants_even_when_parent_is_best():
    values = np.full((65, 32), -5.0)
    values[0] = 100
    assert measure.select_top(values) == [1, 2, 3, 4]


def test_rescore_ties_use_original_row_not_input_order():
    rows = {i: {"F": np.full(8, -1.0)} for i in (40, 5, 12, 3)}
    assert measure.select_winner(rows, [40, 5, 12, 3]) == 3


@pytest.mark.parametrize("selection", ([0, 1, 2, 3], [1, 1, 2, 3], [1, 2, 3]))
def test_rescore_rejects_wrong_panel(selection):
    with pytest.raises(ValueError):
        measure.select_winner({}, selection)


def test_pairing_and_cost_decomposition():
    world = measure.spec.world("catch_speck_l4", **measure.WORLD_OVERRIDES)
    parent = synthetic_row(captures=10, poison=4, misses=8, other=400)
    winner = synthetic_row(captures=12, poison=1, misses=5, other=500)
    report = measure.comparison(winner, parent, world)
    values = report["decoy_fitness_contributions"]
    assert values["capture_income"]["mean"] == 1000 / 1024
    assert values["poison_cost_saving"]["mean"] == 150 / 1024
    assert values["miss_cost_saving"]["mean"] == 30 / 1024
    assert values["other_cost_saving"]["mean"] == -100 / 1024
    assert report["primary"]["mean"] == 1080 / 1024
    assert report["primary"]["se"] == 0
    assert values["residual"]["mean"] == 0


def test_accounting_rejects_unexplained_gain():
    parent, winner = synthetic_row(), synthetic_row()
    winner["F"] += 1
    with pytest.raises(ValueError, match="reconstruct"):
        measure.comparison(winner, parent, measure.spec.world("catch_speck_l4", **measure.WORLD_OVERRIDES))


def test_workflow_freezes_both_winners_before_confirmation(tmp_path, monkeypatch):
    protocol = {"source_identity": {}, "helpers": {}, "expected_numerical_identity": {},
                "input_sha256": {}, "max_cpu_seconds": 3600, "simulation_workers": 2}
    (tmp_path / "protocol.json").write_text(json.dumps(protocol))
    genomes = {p: np.repeat(np.arange(65, dtype=np.float32)[:, None], 5, axis=1) for p in measure.PARENTS}
    configs = {p: (None, tmp_path / "dummy.yaml") for p in measure.PARENTS}
    (tmp_path / "dummy.yaml").write_text("{}")
    world = measure.spec.world("catch_speck_l4", **measure.WORLD_OVERRIDES)
    events = []

    class FakeStore:
        def __init__(self, out, genomes, world, evaluator, threads, cap):
            self.out, self.index, self.cpu_seconds = out, {}, 0
            self.parent = out.name

        def stage(self, stage, indices, seeds):
            if stage == "confirm":
                frozen = json.loads((self.out.parent / "selection.json").read_text())
                assert set(frozen) == set(measure.PARENTS)
                assert all(value["genome_row"] == 64 for value in frozen.values())
            events.append((self.parent, stage, list(indices), len(seeds)))
            return {i: synthetic_row(n=len(seeds), captures=i if stage != "confirm" else -i) for i in indices}

    monkeypatch.setattr(measure, "load_inputs", lambda _: (protocol, genomes, configs, world))
    monkeypatch.setattr(measure, "numerical_identity", lambda: {})
    monkeypatch.setattr(measure, "LifeEvaluator", lambda *args: None)
    monkeypatch.setattr(measure, "RowStore", FakeStore)
    report = measure.run(tmp_path)
    assert report["status"] == "complete"
    assert [(p, stage) for p, stage, *_ in events] == [
        ("s5", "screen"), ("s7", "screen"), ("s5", "rescore"), ("s7", "rescore"),
        ("s5", "confirm"), ("s7", "confirm")]
    assert sum(len(indices) * lives for _, _, indices, lives in events) == 11328
    assert all(x["primary"]["mean"] < 0 for x in report["confirmation"].values())


def test_dependency_waits_for_G_and_rejects_failures(tmp_path, monkeypatch):
    monkeypatch.setattr(monitor, "ROOT", tmp_path)
    protocol = {"dependencies": {"G": {}}}
    (tmp_path / "G").mkdir()
    (tmp_path / "G/budget.json").write_text(json.dumps({"status": "running"}))
    assert not monitor.dependencies_complete(protocol)
    (tmp_path / "G/budget.json").write_text(json.dumps({"status": "complete", "running": {}, "queued": []}))
    assert monitor.dependencies_complete(protocol)
    (tmp_path / "G/budget.json").write_text(json.dumps({"status": "incomplete"}))
    with pytest.raises(ValueError, match="normally"):
        monitor.dependencies_complete(protocol)


def test_completed_dependency_cannot_have_work(tmp_path, monkeypatch):
    monkeypatch.setattr(monitor, "ROOT", tmp_path)
    (tmp_path / "G").mkdir()
    (tmp_path / "G/budget.json").write_text(json.dumps({"status": "complete", "running": {"123": "job"}}))
    with pytest.raises(ValueError, match="still contains"):
        monitor.dependencies_complete({"dependencies": {"G": {}}})


def test_ready_rejects_changed_released_file(tmp_path, monkeypatch):
    monkeypatch.setattr(monitor, "STUDY", tmp_path)
    names = ("protocol.json", "measure.py", "run_budgeted.py", "prepare.py", "prereg_draft.md", "test_prepared.py")
    for name in names:
        (tmp_path / name).write_text("original")
    (tmp_path / "ready.json").write_text(json.dumps({"files": {name: monitor.sha(tmp_path / name) for name in names}}))
    (tmp_path / "measure.py").write_text("changed")
    with pytest.raises(ValueError, match="released study file"):
        monitor.check_ready()


def test_termination_escalates_when_term_is_ignored(monkeypatch):
    signals = []
    monkeypatch.setattr(monitor.os, "killpg", lambda pid, signum: signals.append((pid, signum)))

    class Process:
        pid = 99

        def wait(self, timeout=None):
            if timeout is not None:
                raise monitor.subprocess.TimeoutExpired("mock", timeout)
            return -9

    assert monitor.terminate(Process()) == -9
    assert signals == [(99, monitor.signal.SIGTERM), (99, monitor.signal.SIGKILL)]


def test_cpu_counts_live_descendants_and_reaped_children(tmp_path, monkeypatch):
    proc = tmp_path / "proc"
    proc.mkdir()
    for pid, parent, ticks in ((100, 50, 100), (101, 100, 200), (102, 101, 300), (999, 50, 900)):
        folder = proc / str(pid)
        folder.mkdir()
        fields = ["0"] * 15
        fields[0], fields[1], fields[11], fields[13] = "S", str(parent), str(ticks), "10"
        (folder / "stat").write_text(str(pid) + " (mock process) " + " ".join(fields))
    monkeypatch.setattr(monitor, "Path", lambda value: proc if value == "/proc" else Path(value))
    monkeypatch.setattr(monitor.os, "sysconf", lambda _: 100)
    monkeypatch.setattr(monitor.resource, "getrusage", lambda _: SimpleNamespace(ru_utime=1.0, ru_stime=0.5))
    assert monitor.cpu() == 3.0
    assert monitor.cpu(100) == 9.3


def test_child_limit_uses_remaining_cpu_and_parent_death_signal(monkeypatch):
    calls = []
    fake = SimpleNamespace(prctl=lambda *args: calls.append(("prctl", args)) or 0)
    monkeypatch.setattr(monitor.ctypes, "CDLL", lambda _: fake)
    monkeypatch.setattr(monitor.os, "getppid", lambda: 123)
    monkeypatch.setattr(monitor.resource, "setrlimit", lambda resource, limits: calls.append(("limits", limits)))
    monitor.child_limit(3500.75)
    assert calls == [("prctl", (1, monitor.signal.SIGKILL, 0, 0, 0)), ("limits", (3499, 3500))]


def test_child_limit_fails_if_monitor_is_already_gone(monkeypatch):
    monkeypatch.setattr(monitor.ctypes, "CDLL", lambda _: SimpleNamespace(prctl=lambda *args: 0))
    monkeypatch.setattr(monitor.os, "getppid", lambda: 1)

    def exited(code):
        raise SystemExit(code)

    monkeypatch.setattr(monitor.os, "_exit", exited)
    with pytest.raises(SystemExit):
        monitor.child_limit(3599)
