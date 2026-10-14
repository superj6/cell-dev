"""Synthetic tests for independent H accounting, paired covariance and frozen-tissue audits; no lives."""
import importlib.util
import json
from pathlib import Path

import numpy as np
import pytest


def module():
    path = Path(__file__).with_name("analyze.py")
    spec = importlib.util.spec_from_file_location("hidden_independent", path)
    result = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(result)
    return result


def world():
    manifest = json.loads((Path(__file__).parent / "inputs/D_manifest.json").read_text())
    return dict(manifest["worlds"]["1536"], t_fork=768, t_open=800, fork_flags=16)


def synthetic(run, w, status=(0, 0, 0, 0), ends=(1536, 1536, 1536, 1536), extinct=(0, 0, 0, 0)):
    n = len(status)
    row = {key: np.zeros(n, dtype=np.float64) for key in run.COLS}
    row.update(cpu_seconds=np.asarray(1.25), wall_seconds=np.asarray(1.0))
    for name, value in dict(status=status, t_end=ends, t_ext=extinct, captures=5, income=2500,
                             n_end=100, n_S_end=30, n_M_end=40, n_H_end=30, live_time=73600,
                             window=736, last_birth=768.2, misses=2, spikes=500).items():
        row[name][:] = value
    costs = sum(price * row[column] for _, column, price in run.prices(w))
    status = np.asarray(status, dtype=np.int64)
    row["cost"] = costs
    row["guard_charge"] = np.where((status & 6) != 0, w["c_live"] * w["n_max"] * (1536 - row["t_end"]), 0)
    row["net"] = row["income"] - costs - row["guard_charge"]
    row["F_kernel"] = row["net"] / 736
    row["extinct_charge"] = w["c_live"] * np.where((status & 1) != 0,
                                                    1536 - np.maximum(row["t_ext"], 800), 0) / 736
    row["F"] = row["F_kernel"] - row["extinct_charge"]
    row["ledger"] = np.stack([row["F_kernel" if name == "F" else name] for name in run.LEDGER], axis=1)
    return row


def test_guard_and_extinction_penalties_are_retained_with_window_clamping():
    run = module()
    w = world()
    row = synthetic(run, w, status=(0, 4, 1, 1), ends=(1536, 1000, 500, 1000), extinct=(0, 0, 500, 1000))
    health = run.validate_row(row, w, n=4)
    assert health == {"guarded": 1, "extinct": 2, "valid_other_status": 0}
    assert row["guard_charge"][1] == .02 * 1024 * 536
    assert row["extinct_charge"][2] == .02
    assert row["extinct_charge"][3] == .02 * 536 / 736
    assert np.array_equal(row["F"], row["F_kernel"] - row["extinct_charge"])


@pytest.mark.parametrize("column,delta,message", [
    ("status", 64, "invalid implementation"), ("status", 128, "invalid implementation"),
    ("status", 0.1, "invalid implementation"), ("F", 0.01, "production fitness"),
    ("window", 1, "accounting window"), ("cost", 1, "independent accounting"),
    ("net", 1, "independent accounting"),
    ("t_end", -1, "incomplete life"), ("extinct_charge", 1, "independent accounting")])
def test_corrupted_or_invalid_row_rejected(column, delta, message):
    run = module()
    w = world()
    row = synthetic(run, w)
    row[column][1] += delta
    if column in run.LEDGER and column != "F":
        row["ledger"][1, run.L[column]] += delta
    with pytest.raises(ValueError, match=message):
        run.validate_row(row, w, n=4)


def test_raw_ledger_columns_cannot_disagree_with_saved_columns():
    run = module()
    w = world()
    row = synthetic(run, w)
    row["ledger"][0, run.L["path"]] += 1
    with pytest.raises(ValueError, match="saved production column"):
        run.validate_row(row, w, n=4)


def fixture_frozen(run):
    row = synthetic(run, world())
    return {condition: {key: np.stack([row[key]] * 3) for key in run.COLS} for condition in run.CONDITIONS}


def test_structure_accepts_benign_flags_and_counts_guard_exclusions_without_censoring():
    run = module()
    data = fixture_frozen(run)
    data["freeze"]["status"][0, 0] = 256
    data["freeze+hidden_off"]["status"][0, 1] = 4
    data["freeze+hidden_off"]["n_end"][0, 1] = 10
    data["freeze+hidden_off"]["live_time"][0, 1] = 10
    result = run.frozen_structure(data)
    assert result[0]["complete_triplets"] == 3 and result[0]["excluded_guard_or_extinct_triplets"] == 1
    assert all(row["all_fitness_rows_retained"] for row in result)
    assert data["freeze+hidden_off"]["F"].shape == (3, 4)


@pytest.mark.parametrize("key", ["births", "deaths", "last_birth", "n_end", "n_S_end", "n_M_end", "n_H_end",
                                "live_time", "t_end"])
def test_frozen_structure_detects_each_constraint(key):
    run = module()
    data = fixture_frozen(run)
    data["freeze+hidden_off"][key][2, 1] += 100
    with pytest.raises(ValueError):
        run.frozen_structure(data)


def test_four_arm_interactions_keep_seed_covariance_both_endpoints_and_signs():
    run = module()
    shared = np.asarray([100., -200., 300., -400.])
    data = {condition: np.stack([shared] * 3) for condition in run.CONDITIONS}
    data["freeze"][1] += [1, 2, 3, 4]
    data["freeze+hidden_off"][1] += [-1, 0, 1, 2]
    data["freeze+hidden_off"][2] += 3
    raw = run.effects(data)
    positive = run.stats(raw[run.LABELS[1] + "__added_hidden_dependence"], flags=True)
    negative = run.stats(raw[run.LABELS[2] + "__added_hidden_dependence"], flags=True)
    assert positive == {"mean": 2, "se": 0, "n": 4, "positive_above_3se": True, "negative_below_minus_3se": False}
    assert negative["mean"] == -3 and negative["negative_below_minus_3se"]
    assert len(raw) == 20


def test_income_cost_guard_extinction_terms_reconcile_per_seed():
    run = module()
    w = world()
    left = synthetic(run, w, status=(0, 4, 1, 0), ends=(1536, 1000, 500, 1536), extinct=(0, 0, 500, 0))
    right = synthetic(run, w)
    data = {key: np.stack([left[key], right[key]]) for key in run.COLS}
    terms = run.pair_terms(data, 1, w)
    assert np.allclose(terms["accounting_residual"], 0, atol=1e-12)
    assert terms["guard_charge_saving"][1] > 0 and terms["extinction_charge_saving"][2] == .02


def test_prelaunch_and_running_studies_cannot_be_reported_complete(tmp_path):
    run = module()
    assert run.analyze(tmp_path)[0]["budget_status"] == "not_started"
    (tmp_path / "budget.json").write_text('{"status":"waiting_for_workers"}')
    assert run.analyze(tmp_path)[0] == {"status": "incomplete", "budget_status": "waiting_for_workers"}


@pytest.mark.parametrize("cpu", [0, -1, 3600, 3601, float("nan"), float("inf")])
def test_claimed_completion_requires_finite_cpu_strictly_inside_cap(tmp_path, cpu):
    run = module()
    (tmp_path / "budget.json").write_text(json.dumps({"status": "complete", "exit_code": 0,
        "cpu_seconds": cpu, "running": {}, "queued": []}))
    with pytest.raises(ValueError, match="fixed worker budget"):
        run.analyze(tmp_path)
