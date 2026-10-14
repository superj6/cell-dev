"""Independent S preparation audit; no active outcomes, compilation, or simulated lives."""
import hashlib
import json
from pathlib import Path

import numpy as np
from omegaconf import OmegaConf

ROOT = Path(__file__).resolve().parents[2]
STUDY = ROOT / "outputs/autonomous_scoring_budget_20261014"
OUT = Path(__file__).resolve().parent


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def read(path):
    return json.loads(path.read_text())


def differences(left, right, path=""):
    if isinstance(left, dict) and isinstance(right, dict):
        result = set()
        for key in left.keys() | right.keys():
            name = path + "." + key if path else key
            if key not in left or key not in right:
                result.add(name)
            else:
                result |= differences(left[key], right[key], name)
        return result
    return set() if left == right else {path}


def main():
    protocol = read(STUDY / "protocol.json")
    assert sha(STUDY / "protocol.json") == "a935a20d3e9dff962c79bb65e9586076484a595b157e6fa186133a86dba212cd"
    initial = read(STUDY / "initialization.json")["runs"]
    previous = read(STUDY / "inputs/P_preparation/initialization.json")["runs"]
    independent = read(OUT / "source_seed_review.json")
    allowed = {"logging.output_dir", "life.control", "life.lives", "evolve.recheck_lives",
               "evolve.seed_genome", "evolve.generations"}
    actual = {}
    for seed, founder in ((52091, 51089), (52092, 51090)):
        key = str(seed)
        current_cfg = OmegaConf.to_container(OmegaConf.load(STUDY / f"configs/s{seed}.yaml"), resolve=True)
        previous_cfg = OmegaConf.to_container(
            OmegaConf.load(STUDY / f"inputs/P_preparation/configs/s{seed}.yaml"), resolve=True)
        assert differences(previous_cfg, current_cfg) == allowed
        assert current_cfg["seed"] == seed
        assert current_cfg["life"]["lives"] == 6 and current_cfg["evolve"]["recheck_lives"] == 8
        assert current_cfg["evolve"]["generations"] == 8
        assert initial[key] == previous[key]
        relative = initial[key]["population_file"]
        new_file, old_file = STUDY / relative, STUDY / "inputs/P_preparation" / relative
        assert new_file.read_bytes() == old_file.read_bytes()
        raw = np.load(new_file, allow_pickle=False)
        assert raw.shape == (32, 875) and raw.dtype == np.float32
        assert sha(new_file) == initial[key]["file_sha256"]
        assert hashlib.sha256(raw.tobytes()).hexdigest() == initial[key]["population_raw_sha256"]
        assert [hashlib.sha256(row.tobytes()).hexdigest() for row in raw] == initial[key]["row_raw_sha256"]
        for field in ("population_raw_sha256", "generator_before_sha256", "generator_after_sha256"):
            assert initial[key][field] == independent["initialization_audits"][key][field]
        assert len(initial[key]["copies"]) == 31
        assert sum(len(row["ops"]["mut"]) for row in initial[key]["copies"]) == 62
        assert (ROOT / current_cfg["evolve"]["seed_genome"]).read_bytes() == (
            ROOT / previous_cfg["evolve"]["seed_genome"]).read_bytes()
        actual[key] = {"D_founder": founder, "population_file_sha256": sha(new_file),
                       "allowed_changed_keys": sorted(allowed), "all_32_rows_and_RNG_receipt_equal_to_P": True,
                       "duration_schedule": protocol["selection_durations"][key]}
    assert protocol["planned_genome_lives"] == 32768 + 96 + 12 + 4608 == 37484
    assert protocol["confirmation"]["primary_pairs"] == [[4, 2], [5, 3]]
    assert protocol["confirmation"]["secondary_pairs"] == [[4, 0], [5, 1], [2, 0], [3, 1]]
    assert protocol["confirmation"]["seeds"] == list(range(52_050_000, 52_050_256))
    assert all(not (STUDY / name).exists() for name in ("ready.json", "budget.json", "references", "runs"))
    report = {"status": "passed", "reviewer": "audit_de independent final preparation review",
              "simulated_lives": 0, "active_outcomes_read": False, "protocol_sha256": sha(STUDY / "protocol.json"),
              "source_sha256": sha(Path(__file__)), "runs": actual,
              "prospective_namespace_receipt_sha256": sha(OUT / "source_seed_review.json"),
              "research_genome_lives": 37484, "release_state": "held; no readiness or simulation"}
    (OUT / "actual_initialization_review.json").write_text(json.dumps(report, indent=2) + "\n")


if __name__ == "__main__":
    main()
