"""Synthetic V accounting/completion tests and saved calibration replay; never run or import a simulator."""
import ast
import hashlib
import importlib.util
import json
import shutil
from pathlib import Path
import numpy as np
import pytest

ROOT = Path(__file__).resolve().parents[2]
PREP = ROOT / "results/prediction_information_20261014"


def module():
    path = Path(__file__).with_name("analyze.py")
    spec = importlib.util.spec_from_file_location("independent_prediction_information", path)
    result = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(result)
    return result


def world():
    return json.loads((PREP / "protocol.json").read_text())["world"]


def row(run, w, captures=5, misses=3, n=512, cells=56):
    ledger = np.zeros((n, 57), dtype=np.float64)
    for key, value in dict(captures=captures, misses=misses, clicks=captures + misses,
                          live_time=cells * w["T"], n_end=cells, t_end=w["T"], income=w["R_cap"] * captures).items():
        ledger[:, run.L[key]] = value
    # Independent closed form for this synthetic zero-spike/zero-receptor case.
    ledger[:, run.L["cost"]] = cells * w["T"] * w["c_live"] + w["c_miss"] * misses
    ledger[:, run.L["net"]] = ledger[:, run.L["income"]] - ledger[:, run.L["cost"]]
    ledger[:, run.L["F"]] = ledger[:, run.L["net"]] / w["T"]
    return {"ledger": ledger}


@pytest.fixture
def completed(tmp_path):
    run = module()
    base = tmp_path / "V"
    shutil.copytree(PREP, base)
    protocol = run.read(base / "protocol.json")
    w = protocol["world"]
    dependency = "outputs/autonomous_decoy_evolution_20261014/budget.json"
    dependency_path = base / "original" / dependency
    run.save(dependency_path, {"status": "incomplete", "note": "synthetic terminal U, no research performed"})
    run.save(base / "resource_clearance.json", {"all_processes_exited": True, "dependency_budget": dependency,
        "dependency_budget_sha256": run.sha(dependency_path), "processes": [{"pid": 123, "start_ticks": 456}],
        "process_groups": [123]})
    ready = {name: run.sha(base / name) for name in
             ("protocol.json", "measure.py", "run_budgeted.py", "resource_clearance.json")}
    run.save(base / "ready.json", ready)
    library = run.read(base / "library.json")
    manifest = {"protocol_sha256": run.sha(base / "protocol.json"), "ready": ready, "library": library}
    run.save(base / "manifest.json", manifest)
    calibration = protocol["calibration_cpu_seconds"]
    run.save(base / "budget.json", {"status": "complete", "ready": ready, "cap_cpu_seconds": 3600,
        "cpu_seconds": calibration + 14, "worker_pid": None,
        "attempts": [{"number": 1, "exit_code": 0, "prior_cpu_seconds": calibration, "cpu_seconds": 14}]})
    config = run.read(base / "original/results/taskvar/measurement/prediction.json")
    scores = {"world": "prediction", "T": 1024, "capability": "prediction", "seeds": protocol["seeds"],
        "harness_identity": protocol["harness_identity"], "library_sha256": library["measurement.so"],
        "config_sha256": protocol["config_sha256"], "scratch_slots": {}, "runs": {}}
    rows = {}
    for index, candidate in enumerate(protocol["candidates"]):
        name = candidate["name"]
        # Whole-mean retuned reference wins; shared variation preserves exact pairing.
        captures = np.full(512, [5, 6, 5, 5, 5, 12, 7][index], dtype=float)
        captures += np.arange(512) % 3
        cells = 26 if candidate["footprint"] == "hollow2" else 56
        value = row(run, w, captures=captures, cells=cells)
        identity = {"manifest": manifest, "candidate": candidate, "seeds": protocol["seeds"]}
        controller = name in ("full", "ablated")
        value.update(identity=np.asarray(json.dumps(identity, sort_keys=True, separators=(",", ":"))),
            hashes=np.full((512, 5), run.HASH_INIT, dtype=np.uint64), diag=np.zeros((512, 16 if controller else 0)),
            latency=np.ones(512) if controller else np.empty(0), cpu_seconds=np.asarray(1.), wall_seconds=np.asarray(.5))
        directory = base / "rows" / name
        directory.mkdir(parents=True)
        np.savez_compressed(directory / "row.npz", **value)
        run.save(directory / "checkpoint.json", {"identity": identity, "row_sha256": run.sha(directory / "row.npz")})
        rows[name] = value
        metadata = {k: v for k, v in candidate.items() if k != "name"}
        if controller:
            metadata.update(isolates_capability=False, disabled_parameters=[3, 4],
                            source_sha256=config["source_sha256"], privileged=False)
        scores["runs"][name] = dict(metadata, **{key: value["ledger"][:, run.L[key]].tolist()
            for key in ("F", "captures", "clicks", "status", "t_end")})
    run.save(base / "scores.json", scores)
    run.save(base / "progress.json", {"status": "complete", "completed_candidates": list(run.NAMES)})
    best_ref = "retuned"
    best_quiet = max(run.NAMES[2:5], key=lambda n: rows[n]["ledger"][:, run.L["F"]].mean())
    gap = run.stats(rows["full"]["ledger"][:, run.L["F"]] - rows[best_ref]["ledger"][:, run.L["F"]])
    ablation = run.stats(rows["full"]["ledger"][:, run.L["F"]] - rows["ablated"]["ledger"][:, run.L["F"]])
    quiet = run.stats(rows[best_quiet]["ledger"][:, run.L["F"]] - rows[best_ref]["ledger"][:, run.L["F"]])
    gate = {"world": "prediction", "T": 1024, "n": 512, "missing": ["ablation isolating the named capability"],
        "best_reflex": best_ref, "best_do_less": best_quiet, "verdict": "incomplete", "information_gap": gap,
        "ablation_gap": ablation, "do_less_gap": quiet,
        "checks": {"information_gap": gap["mean"] >= 1 and gap["mean"] > 3 * gap["se"],
                   "do_less": quiet["mean"] < gap["mean"] / 4}}
    run.save(base / "admission.json", gate)
    report = {"status": "complete", "candidate_lives": 3584, "admission": gate}
    for label, name in {"full_vs_reflex": best_ref, "full_vs_frozen_reflex": "frozen",
                        "full_vs_retuned_reflex": "retuned", "full_vs_ablated": "ablated"}.items():
        report[label] = run.contrast(rows["full"], rows[name], w)[0]
    run.save(base / "report.json", report)
    return run, base


def test_all_complete_rows_reanalyze_without_claiming_prediction(completed):
    run, base = completed
    summary, vectors = run.analyze(base)
    assert summary["status"] == "complete"
    assert summary["descriptive_verdict"] == "incomplete"
    assert summary["prediction_specific_effect"] == "unmeasured"
    assert summary["best_reflex"] == "retuned"
    assert np.isclose(summary["contrasts"]["full_vs_reflex"]["F"]["mean"], 6 * 500 / 1024)
    assert np.isclose(summary["broad_moving_target_model_effect"]["mean"], 5 * 500 / 1024)
    assert summary["audit"]["bounded_replay_comparisons"] == 12
    assert len(vectors["full_vs_reflex"]) == 512
    assert summary["budget"]["monitored_cpu_seconds"] == summary["budget"]["calibration_cpu_seconds_included"] + 14


@pytest.mark.parametrize("column,delta,message", [
    ("status", 2, "guarded or invalid"), ("status", 4, "guarded or invalid"),
    ("status", 64, "guarded or invalid"), ("status", 128, "guarded or invalid"),
    ("status", .1, "status encoding"), ("cost", 1, "total cost differs"),
    ("income", 1, "capture income differs"), ("net", 1, "net income/cost differs"),
    ("F", .001, "fitness differs"), ("t_end", -1, "incomplete life")])
def test_one_invalid_life_rejects_entire_ledger(column, delta, message):
    run = module()
    w = world()
    value = row(run, w)["ledger"]
    value[7, run.L[column]] += delta
    with pytest.raises(ValueError, match=message):
        run.validate_ledger(value, w)


def test_raw_calibration_full_ledgers_reconstruct_bitwise():
    run = module()
    for name in ("full", "ablated"):
        with np.load(PREP / "calibration" / name / "row.npz", allow_pickle=False) as arrays:
            run.validate_ledger(arrays["ledger"], world(), n=2)


def test_cost_and_paired_components_are_independent_closed_form():
    run = module()
    w = world()
    a, b = row(run, w, captures=6, misses=2), row(run, w)
    result, pieces = run.contrast(a, b, w)
    assert result["F"]["mean"] == 510 / 1024
    assert result["fitness_pieces"]["capture_income"]["mean"] == 500 / 1024
    assert result["fitness_pieces"]["miss_cost_saving"]["mean"] == 10 / 1024
    assert result["fitness_pieces"]["poison_cost_saving"]["mean"] == 0
    assert np.all(sum(pieces.values()) == 510 / 1024)


def test_paired_standard_error_retains_covariance():
    run = module()
    left = np.asarray([100., -100., 50., -50.])
    right = left - np.arange(1., 5.)
    actual = run.stats(left - right)
    assert actual["mean"] == 2.5
    assert np.isclose(actual["se"], np.sqrt(5 / 3) / 2)


def test_incomplete_never_reads_partial_rows(tmp_path, monkeypatch):
    run = module()
    monkeypatch.setattr(run, "audit_inputs", lambda *args: pytest.fail("read incomplete experiment"))
    assert run.analyze(tmp_path) == ({"status": "incomplete", "budget_status": "not_started"}, {})
    run.save(tmp_path / "budget.json", {"status": "cpu_budget_exhausted"})
    assert run.analyze(tmp_path)[0]["budget_status"] == "cpu_budget_exhausted"


@pytest.mark.parametrize("case", ["reset_cpu", "active_worker", "cleanup_error", "cap", "progress", "score_order",
                                  "raw_roundtrip", "specific_claim", "library", "missing_row", "changed_row", "candidate", "world_price", "candidate_cpu", "attempt_order", "empty_attempts", "second_attempt"])
def test_forged_or_incomplete_completion_is_rejected(completed, case):
    run, base = completed
    if case in ("candidate", "world_price"):
        x = run.read(base / "protocol.json")
        if case == "candidate": x["candidates"][0]["kind"] = "information"
        else: x["world"]["R_cap"] = 999
        run.save(base / "protocol.json", x)
    elif case in ("reset_cpu", "active_worker", "cleanup_error", "cap", "attempt_order", "empty_attempts", "second_attempt"):
        path = base / "budget.json"
        x = run.read(path)
        if case == "reset_cpu": x["attempts"][0]["prior_cpu_seconds"] = 0
        elif case == "active_worker": x["worker_pid"] = 12
        elif case == "cleanup_error": x["cleanup_error"] = "not gone"
        elif case == "attempt_order": x["attempts"][0]["number"] = 2
        elif case == "empty_attempts": x["attempts"] = []
        elif case == "second_attempt": x["attempts"].append(dict(x["attempts"][0], number=2))
        else: x["cpu_seconds"] = 3601
        run.save(path, x)
    elif case == "progress":
        run.save(base / "progress.json", {"status": "complete", "completed_candidates": ["full"]})
    elif case in ("score_order", "raw_roundtrip"):
        path = base / "scores.json"
        x = run.read(path)
        if case == "score_order": x["seeds"] = x["seeds"][::-1]
        else: x["runs"]["full"]["F"][0] += .01
        run.save(path, x)
    elif case == "specific_claim":
        x = run.read(base / "admission.json")
        x["specific_part"] = x["ablation_gap"]
        run.save(base / "admission.json", x)
        report = run.read(base / "report.json")
        report["admission"] = x
        run.save(base / "report.json", report)
    elif case == "library":
        with (base / "measurement.so").open("ab") as stream: stream.write(b"changed")
    elif case == "candidate_cpu":
        path = base / "rows/full/row.npz"
        with np.load(path, allow_pickle=False) as values:
            arrays = {key: values[key].copy() for key in values.files}
        arrays["cpu_seconds"] = np.asarray(1000.)
        np.savez_compressed(path, **arrays)
        receipt = run.read(path.with_name("checkpoint.json"))
        receipt["row_sha256"] = run.sha(path)
        run.save(path.with_name("checkpoint.json"), receipt)
    elif case == "missing_row":
        shutil.rmtree(base / "rows/ablated")
    else:
        with (base / "rows/full/row.npz").open("ab") as stream: stream.write(b"changed")
    with pytest.raises((ValueError, FileNotFoundError)):
        run.analyze(base)


def test_no_simulator_imports_or_compiler_calls():
    source = Path(__file__).with_name("analyze.py").read_text()
    tree = ast.parse(source)
    imports = {n.module for n in ast.walk(tree) if isinstance(n, ast.ImportFrom)}
    imports |= {alias.name for n in ast.walk(tree) if isinstance(n, ast.Import) for alias in n.names}
    assert not any(name and name.startswith(("src", "scripts", "torch", "subprocess", "ctypes")) for name in imports)
    assert "build.run" not in source and "ctl_run(" not in source
