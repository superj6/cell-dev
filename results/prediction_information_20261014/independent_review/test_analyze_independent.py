"""Independent V analyzer checks using synthetic completed archives; never simulate."""
from __future__ import annotations

import importlib.util
import math
import shutil
from pathlib import Path

import numpy as np
import pytest

HERE = Path(__file__).resolve().parent


def author_module():
    loader = importlib.util.spec_from_file_location("V_author_fixture_for_independent_review", HERE / "test_analyze.py")
    module = importlib.util.module_from_spec(loader)
    loader.loader.exec_module(module)
    return module


@pytest.fixture
def completed(tmp_path):
    # Reuse only the saved-artifact construction; expectations below are independently calculated.
    return author_module().completed.__wrapped__(tmp_path)


def stats(x):
    x = np.asarray(x, dtype=float)
    mean = float(sum(x) / len(x))
    se = math.sqrt(float(sum((v - mean) ** 2 for v in x)) / (len(x) - 1) / len(x))
    return {"mean": mean, "se": se, "n": len(x)}


def rewrite_row(run, base, name, update):
    directory = base / "rows" / name
    with np.load(directory / "row.npz", allow_pickle=False) as saved:
        arrays = {key: saved[key].copy() for key in saved.files}
    update(arrays)
    np.savez_compressed(directory / "row.npz", **arrays)
    receipt = run.read(directory / "checkpoint.json")
    receipt["row_sha256"] = run.sha(directory / "row.npz")
    run.save(directory / "checkpoint.json", receipt)
    return arrays


def set_captures(run, base, name, captures):
    p = run.read(base / "protocol.json")["world"]

    def update(arrays):
        led = arrays["ledger"]
        led[:, run.L["captures"]] = captures
        led[:, run.L["clicks"]] = captures + led[:, run.L["misses"]]
        led[:, run.L["income"]] = p["R_cap"] * captures
        led[:, run.L["net"]] = led[:, run.L["income"]] - led[:, run.L["cost"]]
        led[:, run.L["F"]] = led[:, run.L["net"]] / p["T"]

    return rewrite_row(run, base, name, update)


def recompute_worker_reports_independently(run, base):
    """These fixtures have only living/missed-click costs; use closed-form worker reports."""
    p = run.read(base / "protocol.json")["world"]
    rows = {}
    for name in run.NAMES:
        with np.load(base / "rows" / name / "row.npz", allow_pickle=False) as saved:
            rows[name] = saved["ledger"].copy()
    scores = run.read(base / "scores.json")
    for name, led in rows.items():
        for key in ("F", "captures", "clicks", "status", "t_end"):
            scores["runs"][name][key] = led[:, run.L[key]].tolist()
    run.save(base / "scores.json", scores)
    best_ref = sorted(run.NAMES[:2], key=lambda name: -float(rows[name][:, run.L["F"]].mean()))[0]
    best_less = sorted(run.NAMES[2:5], key=lambda name: -float(rows[name][:, run.L["F"]].mean()))[0]
    refs = {"full_vs_reflex": best_ref, "full_vs_frozen_reflex": "frozen",
            "full_vs_retuned_reflex": "retuned", "full_vs_ablated": "ablated"}
    report = run.read(base / "report.json")
    for label, ref in refs.items():
        left, right = rows["full"], rows[ref]
        result = {key: stats(left[:, run.L[key]] - right[:, run.L[key]]) for key in
                  ("F", "captures", "clicks", "b2_clicks", "misses", "spikes", "path", "zone_samples", "samples")}
        result["fitness_pieces"] = {
            "capture_income": stats(p["R_cap"] * (left[:, run.L["captures"]] - right[:, run.L["captures"]]) / p["T"]),
            "poison_cost_saving": stats(np.zeros(512)),
            "miss_cost_saving": stats(p["c_miss"] * (right[:, run.L["misses"]] - left[:, run.L["misses"]]) / p["T"]),
            "other_cost_saving": stats(p["c_live"] * (right[:, run.L["live_time"]] - left[:, run.L["live_time"]]) / p["T"])}
        report[label] = result
    gap = report["full_vs_reflex"]["F"]
    quiet = stats(rows[best_less][:, run.L["F"]] - rows[best_ref][:, run.L["F"]])
    gate = run.read(base / "admission.json")
    gate.update(best_reflex=best_ref, best_do_less=best_less, information_gap=gap,
                ablation_gap=report["full_vs_ablated"]["F"], do_less_gap=quiet,
                checks={"information_gap": gap["mean"] >= 1 and gap["mean"] > 3 * gap["se"],
                        "do_less": quiet["mean"] < gap["mean"] / 4})
    report["admission"] = gate
    run.save(base / "admission.json", gate)
    run.save(base / "report.json", report)
    return rows


def test_whole_reference_selection_with_crossing_per_life_winners(completed):
    run, base = completed
    set_captures(run, base, "frozen", np.r_[np.full(256, 12.), np.zeros(256)])
    rows = recompute_worker_reports_independently(run, base)
    summary, vectors = run.analyze(base)
    assert summary["best_reflex"] == "retuned"
    expected = rows["full"][:, run.L["F"]] - rows["retuned"][:, run.L["F"]]
    impossible_reference = np.maximum(rows["frozen"][:, run.L["F"]], rows["retuned"][:, run.L["F"]])
    assert not np.allclose(expected, rows["full"][:, run.L["F"]] - impossible_reference)
    np.testing.assert_array_equal(vectors["full_vs_reflex"], expected)
    assert summary["contrasts"]["full_vs_reflex"]["F"]["mean"] == pytest.approx(stats(expected)["mean"])
    assert summary["contrasts"]["full_vs_reflex"]["F"]["se"] == pytest.approx(stats(expected)["se"], abs=1e-12)


def test_exact_reference_tie_keeps_registered_first_reference(completed):
    run, base = completed
    with np.load(base / "rows/retuned/row.npz", allow_pickle=False) as saved:
        captures = saved["ledger"][:, run.L["captures"]].copy()
    set_captures(run, base, "frozen", captures)
    recompute_worker_reports_independently(run, base)
    summary, _ = run.analyze(base)
    assert summary["best_reflex"] == "frozen"
    assert summary["contrasts"]["full_vs_frozen_reflex"] == summary["contrasts"]["full_vs_retuned_reflex"]


def test_negative_broad_model_effect_and_failed_gap_are_retained(completed):
    run, base = completed
    set_captures(run, base, "full", np.arange(512) % 3 + 1.)
    recompute_worker_reports_independently(run, base)
    summary, vectors = run.analyze(base)
    assert summary["status"] == "complete"
    assert summary["broad_moving_target_model_effect"]["mean"] < 0
    assert np.all(vectors["full_vs_ablated"] < 0)
    assert summary["descriptive_checks"]["information_gap"] is False
    assert summary["descriptive_verdict"] == "incomplete"
    assert summary["prediction_specific_effect"] == "unmeasured"


@pytest.mark.parametrize("change", [{"sigma": 9.}, {"flags": 1}, {"c_live": .5}, {"lam_s": 20.}])
def test_modified_protocol_cannot_redefine_registered_world(completed, change):
    run, base = completed
    protocol = run.read(base / "protocol.json")
    protocol["world"].update(change)
    run.save(base / "protocol.json", protocol)
    with pytest.raises(ValueError, match="registered|prepared|protocol"):
        run.analyze(base)


def test_impossible_candidate_cpu_exceeds_monitored_research_cpu(completed):
    run, base = completed
    rewrite_row(run, base, "full", lambda row: row.update(cpu_seconds=np.asarray(1_000_000.)))
    with pytest.raises(ValueError, match="CPU|cpu|timing"):
        run.analyze(base)


@pytest.mark.parametrize("column", ["live_H", "ticks", "morph_inflight_end"])
def test_nonfinite_nonscore_ledger_column_rejects_whole_study(completed, column):
    run, base = completed
    rewrite_row(run, base, "quieter", lambda row: row["ledger"].__setitem__((15, run.L[column]), np.nan))
    with pytest.raises(ValueError, match="ledger"):
        run.analyze(base)


def test_portable_archive_without_repository_fallback(completed, monkeypatch):
    run, base = completed
    monkeypatch.setattr(run, "ROOT", None)
    summary, vectors = run.analyze(base)
    assert summary["status"] == "complete" and len(vectors["full_vs_ablated"]) == 512
    assert summary["audit"]["generated_source_reconstruction"] is True


def test_missing_archived_source_cannot_fall_back_when_portable(completed, monkeypatch):
    run, base = completed
    monkeypatch.setattr(run, "ROOT", None)
    shutil.rmtree(base / "original/results/open_headroom/harness")
    with pytest.raises((ValueError, FileNotFoundError)):
        run.analyze(base)


def test_analysis_writes_no_research_artifacts(completed, monkeypatch):
    run, base = completed
    monkeypatch.setattr(run, "ROOT", None)
    before = {str(path.relative_to(base)): run.sha(path) for path in base.rglob("*") if path.is_file()}
    run.analyze(base)
    after = {str(path.relative_to(base)): run.sha(path) for path in base.rglob("*") if path.is_file()}
    assert before == after
