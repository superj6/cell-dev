"""Freeze recovered inputs and the prospective duration protocol without compiling or simulating."""
from __future__ import annotations

import argparse
import importlib.util

import measure as M

SOURCES = {
    "inputs/headline.json": "results/open_headroom/data/headline.json",
    "inputs/reflex_knobs_verify.json": "outputs/openhr/verify_headline/reflex_knobs_verify.json",
    "inputs/c4_tuned_retained_not_used.json": "outputs/openhr/verify_headline/c4_tuned.json",
    "inputs/historical_identity.json": "outputs/openhr/verify_headline/test_v4_identity.json",
    "inputs/historical_replay.json": "outputs/openhr/verify_headline/test_replay_leak.json",
    "inputs/historical_job_c4.py": "outputs/openhr/verify_headline/job_c4.py",
    "inputs/historical_job_tissue.py": "outputs/openhr/verify_headline/job_tissue.py",
    "inputs/namespace_audit.json": "outputs/prospective_g5_20261014/namespace_audit.json",
    "inputs/feasibility.json": "outputs/prospective_g5_20261014/feasibility.json",
    "sources/F_measure.py": "results/discrimination_20261013/operations/measure.py",
    "sources/vctl.c": "outputs/openhr/verify_headline/vctl.c",
    "sources/make_vctl.py": "results/open_headroom/controllers/make_vctl.py",
}


def freeze_bytes(path, content):
    path.parent.mkdir(parents=True, exist_ok=True)
    if path.exists():
        if path.read_bytes() != content:
            raise ValueError("prepared input changed: " + str(path))
    else:
        path.write_bytes(content)


def main():
    argparse.ArgumentParser(description=__doc__).parse_args()
    if (M.STUDY / "ready.json").exists() or (M.STUDY / "budget.json").exists():
        raise ValueError("cannot prepare a released study")
    for target, original in SOURCES.items():
        freeze_bytes(M.STUDY / target, (M.ROOT / original).read_bytes())
    if M.read(M.STUDY / "inputs/headline.json")["reflex_knobs_verify"] != M.read(
            M.STUDY / "inputs/reflex_knobs_verify.json"):
        raise ValueError("retained reflex source copies differ")
    helper = M.ROOT / "outputs/autonomous_s7_20261014/sources/D_prepare.py"
    loader = importlib.util.spec_from_file_location("N_pure_seed_helper", helper)
    module = importlib.util.module_from_spec(loader)
    loader.loader.exec_module(module)
    old = module.pilot_life_seeds() | set().union(*(set(module.run_life_seeds(seed))
                                                 for seed in (51089, 51090, 51891, 51892)))
    validation = list(range(51_099_000, 51_099_004))
    scoring = [list(range(51_000_000 + block * 10_000, 51_000_000 + block * 10_000 + 512))
               for block in (40, 41)]
    if set(validation) & (old | set(scoring[0]) | set(scoring[1])):
        raise ValueError("validation overlaps training or research")
    M.freeze(M.STUDY / "inputs/validation_seed_audit.json", {
        "status": "passed", "seeds": validation, "block": 9, "offset": 9000,
        "old_hashed_unique_seeds_checked": len(old), "overlap": 0,
        "earlier_G_block9_validation": [51_090_000, 51_090_001],
        "pure_seed_helper_sha256": M.sha(helper), "simulated_lives": 0})
    M.freeze(M.STUDY / "input_sources.json", {target: {"source": original, "sha256": M.sha(M.ROOT / original)}
                                            for target, original in SOURCES.items()})
    M.freeze(M.STUDY / "protocol.json", M.expected_protocol())
    print("Prepared N: 12,288 research lives plus40 validation lives; no compile, simulation, readiness or launch.")


if __name__ == "__main__":
    main()
