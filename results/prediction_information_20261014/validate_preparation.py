"""Verify the V preparation archive without compilation, simulator imports or new lives."""
from __future__ import annotations
import hashlib
import json
from pathlib import Path
import numpy as np

STUDY = Path(__file__).resolve().parent


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def main():
    manifest = json.loads((STUDY / "provenance.json").read_text())
    assert manifest["status"] == "prepared_not_launched" and manifest["scientific_candidate_lives"] == 0
    for name, item in manifest["artifacts"].items():
        path = STUDY / name
        assert path.stat().st_size == item["bytes"] and sha(path) == item["sha256"], name
    protocol = json.loads((STUDY / "protocol.json").read_text())
    assert protocol["candidate_lives"] == 3584 and protocol["seeds"] == list(range(52_080_000, 52_080_512))
    assert protocol["max_cpu_seconds"] == 3600 and protocol["threads"] == 2
    for relative, digest in protocol["source_pins"].items():
        assert sha(STUDY / manifest["original_files"][relative]) == digest
    world = protocol["world"]
    assert (world["T"], world["v_t"], world["tau_turn"], world["d0"], world["d_min"]) == (1024, .3, 200, 1, .5)
    config_path = STUDY / manifest["original_files"]["results/taskvar/measurement/prediction.json"]
    config = json.loads(config_path.read_text())
    assert sha(config_path) == protocol["config_sha256"]
    controller = STUDY / manifest["original_files"]["results/taskvar/measurement/prediction_ctl.c"]
    assert sha(controller) == config["source_sha256"] == "8bfff9f02653c93f22f6d86df7b2c47e1167191fe9448ad26ec194f695689c58"
    assert config["ablation_isolates_capability"] is False
    candidates = protocol["candidates"]
    assert candidates[-2]["params"] == config["params"]
    assert [i for i, (a, b) in enumerate(zip(candidates[-2]["params"], candidates[-1]["params"])) if a != b] == [3, 4]
    assert candidates[-1]["params"][3:5] == [0, 0]
    assert candidates[3]["name"] == "smaller_tuned" and candidates[3]["knobs"] == config["smaller_reflex_knobs"]
    budget = json.loads((STUDY / "calibration_budget.json").read_text())
    assert budget["status"] == "complete" and budget["cpu_seconds"] == protocol["calibration_cpu_seconds"] <= 30
    assert sha(STUDY / "calibration_budget.json") == protocol["calibration_budget_sha256"]
    for name, digest in json.loads((STUDY / "library.json").read_text()).items():
        assert sha(STUDY / name) == digest
    calibration = json.loads((STUDY / "calibration_plan.json").read_text())
    assert calibration["seeds"] == [52_090_000, 52_090_001]
    for relative, digest in calibration["source_pins"].items():
        assert sha(STUDY / manifest["calibration_original_files"][relative]) == digest
    for name in ("full", "ablated"):
        directory = STUDY / "calibration" / name
        receipt = json.loads((directory / "checkpoint.json").read_text())
        assert sha(directory / "row.npz") == receipt["row_sha256"]
        with np.load(directory / "row.npz", allow_pickle=False) as row:
            assert json.loads(row["identity"].item()) == receipt["identity"]
            assert row["ledger"].shape == (2, 57) and np.isfinite(row["ledger"]).all()
            assert row["diag"].shape == (2, 16) and np.isfinite(row["diag"]).all()
            assert np.all(row["latency"] == 1)
    replay_count = 0
    for relative, destination in manifest["original_files"].items():
        if relative.endswith("_replay.npz"):
            with np.load(STUDY / destination, allow_pickle=False) as logs:
                for key in ("same_life", "other_life", "other_world"):
                    assert logs[key].dtype == logs["actions"].dtype
                    assert logs[key].shape == logs["actions"].shape
                    assert logs[key].tobytes() == logs["actions"].tobytes()
                    replay_count += 1
                assert logs["control"].tobytes() != logs["actions"].tobytes()
    assert replay_count == 12
    assert not any((STUDY / name).exists() for name in ("ready.json", "budget.json", "rows"))
    print(json.dumps({"status": "passed", "artifacts": len(manifest["artifacts"]),
                      "calibration_lives": 4, "exact_action_replays": replay_count, "new_simulations": 0}))


if __name__ == "__main__":
    main()
