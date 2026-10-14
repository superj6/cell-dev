"""Independent V archive/calibration review. Reads saved arrays; no simulation or compilation."""
from __future__ import annotations

import hashlib
import json
import sys
from pathlib import Path

import numpy as np

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[1]
sys.path.insert(0, str(ROOT))
from src.life import spec  # noqa: E402


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def read(path):
    return json.loads(Path(path).read_text())


def integers(value):
    if isinstance(value, dict):
        for v in value.values():
            yield from integers(v)
    elif isinstance(value, list):
        for v in value:
            yield from integers(v)
    elif isinstance(value, int) and not isinstance(value, bool):
        yield value


def main():
    public = ROOT / "results/prediction_information_20261014"
    work = ROOT / "outputs/autonomous_prediction_information_20261014"
    manifest = read(public / "provenance.json")
    protocol = read(public / "protocol.json")
    assert protocol == read(work / "protocol.json")
    assert manifest["status"] == "prepared_not_launched"
    for name, meta in manifest["artifacts"].items():
        assert (public / name).stat().st_size == meta["bytes"]
        assert sha(public / name) == meta["sha256"], name
    for name, digest in {**protocol["source_pins"], **protocol["harness_identity"]}.items():
        assert sha(ROOT / name) == digest, name
        assert sha(public / manifest["original_files"][name]) == digest, name
    assert not any((work / name).exists() for name in ("ready.json", "budget.json", "rows", "manifest.json"))
    p = protocol["world"]
    expected_world = spec.world("catch_speck_l4", v_t=.3, tau_turn=200, T=1024)
    assert spec.World(**p) == expected_world
    assert p["b2_amp"] == 0 and p["flags"] == p["fork_flags"] == p["t_open"] == 0
    assert protocol["candidate_lives"] == 7 * 512 == 3584
    assert protocol["max_cpu_seconds"] == 3600 and protocol["threads"] == 2
    candidates = protocol["candidates"]
    assert [x["name"] for x in candidates] == ["frozen", "retuned", "smaller_frozen", "smaller_tuned",
                                               "quieter", "full", "ablated"]
    cfg = read(ROOT / "results/taskvar/measurement/prediction.json")
    assert candidates[-2]["params"] == cfg["params"]
    changes = [i for i, (x, y) in enumerate(zip(candidates[-2]["params"], candidates[-1]["params"])) if x != y]
    assert changes == [3, 4] and candidates[-1]["params"][3:5] == [0, 0]
    assert candidates[-2]["params"][3:5] == [.3, 200]
    assert cfg["ablation_isolates_capability"] is False
    assert candidates[-2]["footprint"] == candidates[-1]["footprint"] == "hollow3"
    assert candidates[3]["knobs"] == cfg["smaller_reflex_knobs"]
    assert candidates[4]["knobs"] == dict(cfg["reflex_knobs"], **{"K.t_ref": 8.0})
    action = {"latency": "d0", "charge": "relay", "t_ref_min": .5,
              "privileged": False, "quant": False, "fast": True}
    assert candidates[-1]["action"] == candidates[-2]["action"] == action
    calibration = read(work / "calibration_plan.json")
    assert calibration["candidate_lives"] == 4 and calibration["max_cpu_seconds"] == 30
    assert calibration["seeds"] == [52_090_000, 52_090_001]
    budget = read(work / "calibration_budget.json")
    assert budget["status"] == "complete" and budget["cpu_seconds"] == 11.558130849
    assert protocol["calibration_cpu_seconds"] == budget["cpu_seconds"]
    assert protocol["calibration_budget_sha256"] == sha(work / "calibration_budget.json")
    assert len(budget["attempts"]) == 1 and budget["attempts"][0]["exit_code"] == 0
    for name, digest in calibration["source_pins"].items():
        assert sha(public / manifest["calibration_original_files"][name]) == digest, name
    library = read(public / "library.json")
    assert set(library) == {"measurement.c", "measurement.so"}
    for name, digest in library.items():
        assert sha(public / name) == sha(work / name) == digest
        assert protocol["source_pins"][str((work / name).relative_to(ROOT))] == digest
    assert protocol["source_pins"][str((work / "library.json").relative_to(ROOT))] == sha(work / "library.json")
    calibration_checks = {}
    for name in ("full", "ablated"):
        prefix = public / "calibration" / name
        receipt = read(prefix / "checkpoint.json")
        assert receipt["row_sha256"] == sha(prefix / "row.npz")
        assert receipt["identity"]["library"] == library
        assert receipt["identity"]["seeds"] == calibration["seeds"]
        assert receipt["identity"]["candidate"] == next(x for x in candidates if x["name"] == name)
        with np.load(prefix / "row.npz", allow_pickle=False) as saved:
            assert read_identity(saved["identity"].item()) == receipt["identity"]
            led = saved["ledger"]
            assert led.dtype == np.float64 and led.shape == (2, 57) and np.isfinite(led).all()
            assert saved["hashes"].dtype == np.uint64 and saved["hashes"].shape == (2, 5)
            assert saved["diag"].shape == (2, 16) and np.isfinite(saved["diag"]).all()
            assert np.array_equal(saved["latency"], np.ones(2))
            for field in ("wall_seconds", "cpu_seconds"):
                assert np.isfinite(saved[field]) and float(saved[field]) >= 0
            col = {key: led[:, i] for i, key in enumerate(spec.V3.LEDGER)}
            assert np.array_equal(col["status"], np.zeros(2))
            assert np.array_equal(col["t_end"], np.full(2, 1024.))
            assert np.array_equal(col["n_end"], np.full(2, 56.))
            # Independent left-to-right reconstruction; do not call column_cost or fitness.
            pairs = [("c_live", "live_time"), ("c_spike", "spikes"), ("c_tw", "kappa_sum"),
                     ("c_msg", "contact_events"), ("c_div", "claims"), ("c_sec", "sec_int"),
                     ("c_miss", "misses"), ("c_rec", "rec_gain")]
            cost = p[pairs[0][0]] * col[pairs[0][1]]
            for price, field in pairs[1:]:
                cost = cost + p[price] * col[field]
            cost = cost + max(0, -p["b2_value"]) * col["b2_clicks"]
            income = p["R_cap"] * col["captures"]
            assert np.array_equal(income, col["income"])
            assert np.allclose(cost, col["cost"], atol=1e-9, rtol=1e-9)
            fitness = (income - cost) / (p["T"] - p["t_open"])
            assert np.array_equal(fitness, col["F"])
            calibration_checks[name] = {"all57_finite": True, "cost_residual_max": float(np.max(abs(cost-col["cost"]))),
                                       "fitness_bit_exact": True, "completed_unguarded_lives": 2}
    seeds = protocol["seeds"]
    assert seeds == list(range(52_080_000, 52_080_512))
    used = set(integers(read(ROOT / "outputs/audit_decoy_evolution_20261014/namespace_lists.json")))
    target = set(seeds) | set(calibration["seeds"])
    # namespace_lists retains U's reserved block107 only, and no exclusive upper boundary.
    assert not target & used
    assert not target & set(protocol["tuning_seeds"])
    namespace = read(work / "namespace_audit.json")
    inventory = read(work / "namespace_inventory.json")
    assert sha(work / "namespace_inventory.json") == namespace["inventory_sha256"]
    assert namespace["passed"] and not namespace["unexpected_matches"] and not namespace["unexpected_unreadable"]
    assert len(inventory["matches"]) == 1 and inventory["matches"][0]["value"] == 52_080_000
    assert inventory["matches"][0]["field"] == "validation_reserved_half_open.1"
    assert all(any(part.startswith("test_") for part in Path(path).parts) for path in inventory["unreadable"])
    replays = 0
    for original, destination in manifest["original_files"].items():
        if not original.endswith("_replay.npz"):
            continue
        with np.load(public / destination, allow_pickle=False) as saved:
            for key in ("same_life", "other_life", "other_world"):
                assert saved[key].dtype == saved["actions"].dtype
                assert saved[key].shape == saved["actions"].shape
                assert saved[key].tobytes() == saved["actions"].tobytes()
                replays += 1
            assert saved["control"].tobytes() != saved["actions"].tobytes()
    assert replays == 12
    receipt = {"status": "passed_scientific_preparation_review_monitor_review_separate", "new_simulations": 0,
        "protocol_sha256": sha(work / "protocol.json"), "measure_sha256": sha(work / "measure.py"),
        "monitor_sha256": sha(work / "run_budgeted.py"), "archive_provenance_sha256": sha(public / "provenance.json"),
        "artifacts_verified": len(manifest["artifacts"]), "research_lives": 3584, "calibration_lives": 4,
        "calibration_cpu_seconds_carried_forward": budget["cpu_seconds"], "cap_cpu_seconds": 3600,
        "calibration_checks": calibration_checks, "source_pins_verified": len(protocol["source_pins"]),
        "harness_pins_verified": len(protocol["harness_identity"]), "exact_action_replays": replays,
        "fresh_research_and_calibration_seed_count": len(target), "prior_numeric_namespace_values_checked": len(used),
        "all_seed_overlaps": 0, "only_controller_parameter_changes": changes,
        "interpretation": "The full-minus-ablated contrast measures the broad moving-target model. "
                          "Prediction-specific admission remains incomplete; external free computation is not "
                          "a demonstrated evolved algorithm or local-tissue ceiling.",
        "review_script_sha256": sha(Path(__file__))}
    (HERE / "preparation_review.json").write_text(json.dumps(receipt, indent=2) + "\n")
    print(json.dumps(receipt, indent=2))


def read_identity(value):
    return json.loads(value)


if __name__ == "__main__":
    main()
