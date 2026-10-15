"""Focused synthetic checks only: no compilation, engine lives or mutant generation."""
# ruff: noqa: E402
from __future__ import annotations

import ast
import importlib.util
import json
import os
import subprocess
import sys
from dataclasses import asdict
from pathlib import Path

os.environ.setdefault("ATEN_CPU_CAPABILITY", "avx2")
ROOT = Path(__file__).resolve().parents[2]
STUDY = Path(__file__).resolve().parent
sys.path[:0] = [str(STUDY), str(ROOT)]

import numpy as np
import pytest
import scoring
from omegaconf import OmegaConf

import measure
from src.genome import Layout
from src.life import build, spec
from src.life.evaluate import LifeEvaluator

loader = importlib.util.spec_from_file_location("gradient_monitor_tests", STUDY / "monitor.py")
monitor = importlib.util.module_from_spec(loader)
loader.loader.exec_module(monitor)


@pytest.fixture(autouse=True)
def no_engine(monkeypatch):
    def forbidden(*args, **kwargs):
        raise AssertionError("preparation test attempted an engine call or compilation")
    monkeypatch.setattr(build, "run", forbidden)
    monkeypatch.setattr(build, "build", forbidden)


@pytest.fixture
def evaluator():
    prefix = ROOT / "outputs/audit_visibility_gradient_20261014/founders/D90"
    cfg = OmegaConf.load(prefix / "config.yaml")
    cfg.life.abi = 4
    cfg.life.world = "catch_speck_blink20_20_l4"
    cfg.life.T_choices = []
    cfg.world = {}
    cfg.costs_life = {}
    cfg.threads = 2
    layout, _ = Layout.load(prefix / "parent.json")
    return LifeEvaluator(cfg, layout)


def ledger(world, *, state="normal", n=2):
    v = spec.V4
    a = np.zeros((n, 58), dtype=np.float64)
    a[:, v.L["t_end"]] = world.T
    a[:, v.L["live_time"]] = 3000
    a[:, v.L["captures"]] = 3
    a[:, v.L["low_light_captures"]] = 1
    a[:, v.L["income"]] = world.R_cap * 3
    a[:, v.L["n_end"]] = 2
    if state == "extinct":
        a[:, v.L["status"]] = spec.STATUS["extinct"]
        a[:, v.L["t_end"]] = a[:, v.L["t_ext"]] = 200
        a[:, v.L["n_end"]] = 0
    elif state == "guard":
        a[:, v.L["status"]] = spec.STATUS["guard_cells"]
        a[:, v.L["t_end"]] = 200
    a[:, v.L["cost"]] = v.column_cost(a, world)
    a[:, v.L["guard_charge"]] = v.guard_charge(a, world)
    a[:, v.L["net"]] = a[:, v.L["income"]] - a[:, v.L["cost"]] - a[:, v.L["guard_charge"]]
    a[:, v.L["F"]] = v.fitness(a, world)
    return a


@pytest.mark.parametrize("parent", ["D90", "L92"])
def test_extracted_founder_exact_layout_roundtrip(parent):
    prefix = ROOT / "outputs/audit_visibility_gradient_20261014/founders" / parent
    layout, genome = Layout.load(prefix / "parent.json")
    raw = np.load(prefix / "genome.npy", allow_pickle=False)
    assert layout.size == 875
    assert raw.tobytes() == genome.reshape(-1).numpy().tobytes()
    assert scoring.raw_sha(raw) == measure.FOUNDER_SHA[parent]


@pytest.mark.parametrize("state", ["normal", "extinct", "guard"])
def test_production_penalties_and_capture_diagnostics(evaluator, state):
    world = evaluator.world()
    assert asdict(world) == asdict(spec.world("catch_speck_blink20_20_l4", T=1024))
    raw = ledger(world, state=state)
    col = scoring.columns_from_ledger(raw, world, [100, 101], evaluator)
    assert col["F_kernel"].tobytes() == raw[:, spec.V4.L["F"]].tobytes()
    assert np.array_equal(col["F"], col["F_kernel"] - col["extinct_charge"])
    assert np.all(col["extinct_charge"] > 0) == (state == "extinct")
    assert np.all(col["guard_charge"] > 0) == (state == "guard")
    assert np.all(col["low_light_captures"] == 1)


@pytest.mark.parametrize("fault", ["abi3", "low_over_total", "low_fraction", "capacity", "mismatch", "nonfinite", "short", "cost", "net", "F"])
def test_bad_raw_rows_are_rejected(evaluator, fault):
    world = evaluator.world()
    raw = ledger(world)
    if fault == "abi3":
        raw = raw[:, :57]
    elif fault == "low_over_total":
        raw[:, spec.V4.L["low_light_captures"]] = 4
    elif fault == "low_fraction":
        raw[:, spec.V4.L["low_light_captures"]] = .5
    elif fault in ("capacity", "mismatch"):
        raw[:, spec.V4.L["status"]] = spec.STATUS["capacity" if fault == "capacity" else "ledger_mismatch"]
    elif fault == "nonfinite":
        raw[0, 0] = np.nan
    elif fault == "short":
        raw[:, spec.V4.L["t_end"]] -= 1
    else:
        raw[:, spec.V4.L[fault]] += .1
    with pytest.raises(ValueError):
        scoring.columns_from_ledger(raw, world, [100, 101], evaluator)


def test_kernel_cost_tolerance_and_decomposition(evaluator):
    world = evaluator.world()
    raw = ledger(world)
    raw[:, spec.V4.L["cost"]] += 2e-8  # Valid accumulated rounding: kernel permits6e-8 here.
    col = scoring.columns_from_ledger(raw, world, [100, 101], evaluator)
    same = scoring.comparison(col, col, world)
    assert same["F"]["mean"] == 0 and same["capture_income"]["mean"] == 0
    assert same["bright_captures"]["mean"] == 0


def test_selection_keeps_negative_mutant_and_stable_tie():
    rows = {i: {"F": np.full(32, 10.0 if i == 0 else -3.0)} for i in range(65)}
    assert measure.select_winner(rows) == 1
    rows[64]["F"][:] = -2
    assert measure.select_winner(rows) == 64
    del rows[1]
    with pytest.raises(ValueError):
        measure.select_winner(rows)


def test_fixed_calibration_projection_uses_batch_mean_and_reserve():
    rows = {p: {0: {"cpu_seconds": 1.0}, 1: {"cpu_seconds": 2.0}} for p in measure.PARENTS}
    result = measure.calibration_projection(rows, 20)
    assert result["batch_max_cpu_per_life"] == {"D90": 1.0, "L92": 1.0}
    assert result["screen_projection_cpu_seconds"] == 6260
    assert not result["feasible"]


def test_seed_stages_reject_overlap_and_golden():
    seeds = {"screen": list(range(100, 132)), "confirm": list(range(1000, 1512)), "calibration": [2000, 2001]}
    assert measure.stage_seeds({"seeds": seeds}) == seeds
    seeds["calibration"][0] = 100
    with pytest.raises(ValueError):
        measure.stage_seeds({"seeds": seeds})
    seeds["calibration"][0] = 11
    with pytest.raises(ValueError):
        measure.stage_seeds({"seeds": seeds})


def test_exactly_one_numerical_identity_call_site():
    tree = ast.parse((STUDY / "measure.py").read_text())
    calls = [x for x in ast.walk(tree) if isinstance(x, ast.Call)
             and isinstance(x.func, ast.Name) and x.func.id == "numerical_identity"]
    assert len(calls) == 1


@pytest.mark.parametrize("name", ["proc_table", "resource_clearance", "own_cpu", "child_cpu", "active_cpu",
                                  "consumed_cpu", "child_limit", "send_signal", "enable_subreaper",
                                  "cleanup_group", "cleanup", "process_identity"])
def test_reviewed_lifecycle_functions_are_unchanged(name):
    def function(path):
        return next(x for x in ast.parse(path.read_text()).body if isinstance(x, ast.FunctionDef) and x.name == name)
    original = ROOT / "outputs/autonomous_visibility_information_x2_20261014/monitor.py"
    assert ast.dump(function(original)) == ast.dump(function(STUDY / "monitor.py"))


def test_distinct_phase_caps_and_exact_scope():
    assert monitor.SCOPE == measure.SCOPE
    assert monitor.budget_reason("startup_screen", 3389) is None
    assert monitor.budget_reason("startup_screen", 3390) == "startup_screen_cpu_budget_exhausted"
    assert monitor.budget_reason("confirmation", 3390) is None
    assert monitor.budget_reason("confirmation", 5390) == "cpu_budget_exhausted"
    assert len(monitor.expected_rows("calibration_complete")) == 2
    assert len(monitor.expected_rows("screens_complete")) == 67
    assert len(monitor.expected_rows("complete", {"genome_row": 13})) == 69


@pytest.mark.parametrize("changed", ["startup_identity.json", "selection.json", "calibration_projection.json", "request", "receipt"])
def test_acknowledged_artifact_tamper_is_rejected(tmp_path, monkeypatch, changed):
    monkeypatch.setattr(monitor, "STUDY", tmp_path)
    request = tmp_path / "requests/screens_complete.json"
    receipt_path = tmp_path / "monitor_receipts/screens_complete.json"
    monitor.save(request, {"selection_sha256": "known"})
    files = ["startup_identity.json", "selection.json", "calibration_projection.json"]
    for name in files:
        monitor.save(tmp_path / name, {"frozen": name})
    receipt = {"request_sha256": monitor.sha(request),
               "artifact_pins": {name: monitor.sha(tmp_path / name) for name in files}}
    monitor.save(receipt_path, receipt)
    monitor.check_acknowledged({"screens_complete": receipt})
    path = request if changed == "request" else receipt_path if changed == "receipt" else tmp_path / changed
    monitor.save(path, {"altered": True})
    with pytest.raises(ValueError):
        monitor.check_acknowledged({"screens_complete": receipt})


@pytest.mark.parametrize("script", ["measure.py", "monitor.py", "prepare.py"])
def test_default_is_no_import_or_simulation_dry_run(script):
    result = subprocess.run([sys.executable, str(STUDY / script)], capture_output=True, text=True, check=True,
                            env={**os.environ, "PYTHONDONTWRITEBYTECODE": "1"})
    value = json.loads(result.stdout)
    assert value["status"].startswith("dry_run")
    assert not any((STUDY / name).exists() for name in ("attempt.json", "measurement", "build-cache", "startup_identity.json"))


def test_preexpected_metadata_has_no_build_or_golden(evaluator):
    import prepare
    value = prepare.preexpected_metadata()
    assert set(value) == {"torch", "numpy", "python", "aten_cpu_capability", "torch_cpu_capability",
                          "torch_build", "torch_noise_sha256", "libm", "flags", "sources"}
    assert value["sources"]["src/life/kernel.c"] == monitor.sha(ROOT / "src/life/kernel.c")
    assert value["aten_cpu_capability"] == "avx2"


def test_preparation_refuses_before_root_registration(tmp_path, monkeypatch):
    import prepare
    monkeypatch.setattr(prepare, "STUDY", tmp_path)
    with pytest.raises(FileNotFoundError):
        prepare.prepare()
    assert list(tmp_path.iterdir()) == []


def test_cold_worker_environment_preserves_exact_runtime_identity(tmp_path):
    expected = json.loads((ROOT / "outputs/autonomous_visibility_information_x2_20261014/protocol.json").read_text())["numerical_identity"]
    env = dict(os.environ, ATEN_CPU_CAPABILITY="avx2", OMP_WAIT_POLICY="PASSIVE", OMP_NUM_THREADS="2",
               OMP_THREAD_LIMIT="2", MKL_NUM_THREADS="1", OPENBLAS_NUM_THREADS="1", NUMEXPR_NUM_THREADS="1",
               PYTHONUNBUFFERED="1", PYTHONDONTWRITEBYTECODE="1", CELL_DEV_CACHE=str(tmp_path / "unused_cache"))
    env.pop("CELLDEV_THREADS_FILE", None)
    code = "import sys,json;sys.path.insert(0,sys.argv[1]);import numerical;print(json.dumps(numerical.identity()))"
    result = subprocess.run([sys.executable, "-c", code, str(STUDY)], cwd=ROOT, env=env,
                            capture_output=True, text=True, check=True)
    assert json.loads(result.stdout) == expected
    assert not (tmp_path / "unused_cache").exists()
