"""Offline validation of the prepared discrimination archive; never imports a simulator."""
from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path

import numpy as np


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def validate_archive(base):
    base = base.resolve()
    provenance = json.loads((base / "provenance.json").read_text())
    if provenance["status"] != "prepared_not_launched" or provenance["scientific_candidate_lives"] != 0:
        raise ValueError("this checker expects preparation evidence, not completed scientific results")
    for relative, record in provenance["artifacts"].items():
        path = (base / relative).resolve()
        if not path.is_relative_to(base) or sha(path) != record["sha256"] or path.stat().st_size != record["bytes"]:
            raise ValueError(f"archive artifact differs: {relative}")
    protocol = json.loads((base / "protocol.json").read_text())
    original = provenance["original_files"]

    def recovered(path):
        if path not in original:
            raise ValueError(f"missing original source/input: {path}")
        return base / original[path]

    for path, digest in {**protocol["source_pins"], **protocol["harness_identity"]}.items():
        if sha(recovered(path)) != digest:
            raise ValueError(f"frozen original source/input differs: {path}")
    config_path = recovered("results/taskvar/measurement/discrimination.json")
    audit_path = recovered("results/taskvar/validation/discrimination_audit.json")
    config, audit = json.loads(config_path.read_text()), json.loads(audit_path.read_text())
    if sha(config_path) != protocol["config_sha256"] or sha(audit_path) != protocol["audit_sha256"]:
        raise ValueError("protocol config/audit binding differs")
    controller = recovered("results/taskvar/measurement/" + config["controller_source"])
    if sha(controller) != config["source_sha256"] or config["source_sha256"] != protocol["controller_sha256"]:
        raise ValueError("recovered controller differs")
    if (not audit["passed"] or not audit["world_parity_audit"]["passed"]
            or audit["source_sha256"] != config["source_sha256"]
            or audit["harness_identity"] != protocol["harness_identity"]
            or audit["config_sha256"] != sha(config_path)):
        raise ValueError("replay/parity audit does not bind the prepared inputs")
    checks = 0
    if len(audit["rows"]) != 4 or audit["T"] != 64:
        raise ValueError("unexpected bounded audit scope")
    for variant in ("full", "ablated"):
        for i in range(2):
            relative = str(Path(audit["artifact"]).parent / f"{variant}_{i}_replay.npz")
            with np.load(recovered(relative), allow_pickle=False) as logs:
                for key in ("same_life", "other_life", "other_world"):
                    if logs[key].shape != logs["actions"].shape or logs[key].tobytes() != logs["actions"].tobytes():
                        raise ValueError("saved replay action records differ")
                    checks += 1
                if logs["control"].tobytes() == logs["actions"].tobytes():
                    raise ValueError("saved closed-loop replay control fails to differ")
    seeds = protocol["seeds"]
    if seeds != list(range(51_300_000, 51_300_512)) or set(seeds) & set(protocol["tuning_seeds"]):
        raise ValueError("fresh ordered scoring seeds or tuning separation differ")
    if (protocol["candidate_lives"], protocol["seed_block"], protocol["threads"], protocol["max_cpu_seconds"]) != (
            3584, 30, 2, 1800):
        raise ValueError("registered study dimensions or budget differ")
    expected_world = dict(T=1024, d0=1, d_min=0.5, t_open=0, t_fork=0, fork_flags=0,
                          b2_amp=1, b2_sigma=1.2, b2_value=-50, b2_p=1, b2_mode=1)
    if any(protocol["world"][key] != value for key, value in expected_world.items()):
        raise ValueError("registered world differs")
    candidates = protocol["candidates"]
    if [row["name"] for row in candidates] != ["frozen", "retuned", "smaller_frozen", "smaller_transferred",
                                                "quieter", "full", "ablated"]:
        raise ValueError("registered seven-candidate order differs")
    full, ablated = candidates[-2:]
    if full["params"] != config["params"] or full["footprint"] != "hollow3" or ablated["footprint"] != "hollow3":
        raise ValueError("full controller or matched footprint differs")
    changed = [i for i, (a, b) in enumerate(zip(full["params"], ablated["params"])) if a != b]
    if changed != [25] or (full["params"][25], ablated["params"][25]) != (1, 0):
        raise ValueError("ablation changes more than the registered decoy-model flag")
    action = dict(latency="d0", charge="relay", t_ref_min=0.5, privileged=False, quant=False, fast=True)
    if full["action"] != action or ablated["action"] != action:
        raise ValueError("controller action/sensing defaults differ")
    if protocol["fixed_reference_reports"] != ["full minus frozen", "full minus retuned"]:
        raise ValueError("fixed-reflex comparison reports are missing")
    if "never censor individual lives" not in protocol["failure_policy"]:
        raise ValueError("whole-study invalid-life policy is missing")
    return {"status": "prepared_archive_valid", "scientific_candidate_lives": 0,
            "planned_candidate_lives": 3584, "artifact_hashes_checked": len(provenance["artifacts"]),
            "source_input_pins_checked": len(set(protocol["source_pins"]) | set(protocol["harness_identity"])),
            "saved_replay_comparisons_checked": checks, "simulation_executed": False}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--archive", type=Path, default=Path(__file__).resolve().parent)
    args = parser.parse_args()
    print(json.dumps(validate_archive(args.archive), indent=2))


if __name__ == "__main__":
    main()
