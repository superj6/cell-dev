"""AK source-only plan and one-time preparation. No preparation path runs a life."""
from __future__ import annotations

import argparse
import os
import shutil
import sys
from dataclasses import asdict, replace

os.environ.setdefault("ATEN_CPU_CAPABILITY", "avx2")
sys.dont_write_bytecode = True
from common import ROOT, STUDY, raw_sha, read, save, sha  # noqa: E402

sys.path.insert(0, str(ROOT))

ROLES = ["L92", "AE_L92", "AI_control"]
SOURCE_GENOMES = [
    "results/visibility_gradient_20261014/inputs/L92/parent.json",
    "results/exploratory_reserve_replication_20261014/inputs/AE_L92.json",
    "results/exploratory_reserve_replication_20261014/runs/control/best_genome.json",
]
SOURCE_CONFIG = "results/exploratory_reserve_replication_20261014/runs/control/config.yaml"
POOL_CONFIG = "results/s7_continuation_20261014/runs/s51892/config.yaml"
PERSISTENT_PROTOCOL = "results/exploratory_reserve_replication_20261014/protocol.json"
STARTUP = "results/visibility_dark_tail_gradient_20261014/startup_identity.json"
TRUTH = "results/abi4_visibility_20261014/final_truth/truth.json"
SOURCE_FILES = ["common.py", "prepare.py", "measure.py", "monitor.py", "analyze.py"]


def plan():
    from omegaconf import OmegaConf

    from src.genome import Layout
    from src.life import spec
    from src.life.evaluate import LifeEvaluator

    layout, _ = Layout.load(ROOT / SOURCE_GENOMES[0])
    cfg = OmegaConf.load(ROOT / POOL_CONFIG)
    pool = LifeEvaluator(cfg, layout).world(T=1024)
    persistent = spec.World(**read(ROOT / PERSISTENT_PROTOCOL)["world"])
    worlds = {"pool": (spec.V3, pool), "persistent": (spec.V3, persistent),
              "turn100": (spec.V3, replace(persistent, tau_turn=100.)),
              "blink80_5": (spec.V4, replace(persistent, visibility_mode=2, visibility_on=80.,
                                            visibility_off=5., visibility_low=0.))}
    result = {}
    for name, (abi, world) in worlds.items():
        abi.validate_world(world)
        result[name] = {"abi": abi.version, "world": asdict(world),
                        "world_vector": abi.pack_world(world).tolist(), "ledger_columns": list(abi.LEDGER)}
    return {"study": "AK fixed-genome retention and nearby edge cases", "roles": ROLES, "worlds": result,
            "research_lives": 3072, "startup_lives": 4, "seeds": list(range(52380000, 52380256)),
            "extinct_charge": True, "status_bits": spec.STATUS, "hash_names": list(spec.V3.HASHES),
            "budget": {"cpu_seconds": 2400, "wall_seconds": 1800, "threads": 2, "workers": 1,
                       "cleanup_margin_seconds": 10},
            "primary": [{"world": "pool", "new": "AI_control", "old": "L92", "metric": "captures"},
                        {"world": "persistent", "new": "AI_control", "old": "AE_L92", "metric": "captures"}],
            "retention_margin_fraction": 0.1,
            "retention_rule": "Conventional diagnostic: mean(new - 0.9 * old) minus 3 paired SE > 0. "
                              "Also report unthresholded losses and bounds; no null-as-retention inference.",
            "selection": "No selection, mutation, winner replacement, search, or discarded role.",
            "limitations": ["Outcome-informed choice of one lineage, not evolutionary replication.",
                "All revealed cases become development data; future final holdouts must be separate.",
                "POOL changes several physical parameters; only the two edges isolate one change from persistent.",
                "Renewal dark intervals have mean five, no upper bound; success does not establish memory.",
                "Fresh seeds test these fixed genomes; no broad generalization or circuit mechanism follows.",
                "Three-SE intervals are descriptive; all contrasts and physical costs remain visible.",
                "A cap failure leaves an incomplete study; no automatic retry, extension or partial inference."]}


def prepare():
    if any((STUDY / name).exists() for name in ("protocol.json", "inputs", "release.json", "attempt.json", "raw")):
        raise ValueError("one-time preparation refuses preexisting inputs or execution")
    acceptance = read(STUDY / "preparation_acceptance.json")
    if acceptance.get("status") != "accepted_by_root":
        raise ValueError("source, cost and namespace reviews must be accepted first")
    for path, digest in acceptance["review_pins"].items():
        if sha(ROOT / path) != digest:
            raise ValueError("review pin changed: " + path)
    protocol = plan()
    source_pins = {name: sha(STUDY / name) for name in SOURCE_FILES}
    if source_pins != acceptance["source_pins"]:
        raise ValueError("reviewed source set changed")
    audit = read(ROOT / acceptance["seed_audit_path"])
    if audit["status"] != "passed" or audit["candidate_seeds"] != protocol["seeds"]:
        raise ValueError("fresh candidate namespace audit required")
    from src.genome import Layout

    inputs = STUDY / "inputs"
    inputs.mkdir()
    source_paths = SOURCE_GENOMES + [SOURCE_CONFIG, POOL_CONFIG, PERSISTENT_PROTOCOL, STARTUP, TRUTH]
    protocol["original_input_pins"] = {name: sha(ROOT / name) for name in source_paths}
    protocol["genomes"] = []
    for role, source in zip(ROLES, SOURCE_GENOMES):
        target = inputs / f"{role}.json"
        shutil.copyfile(ROOT / source, target)
        _, genome = Layout.load(target)
        protocol["genomes"].append({"role": role, "path": str(target.relative_to(STUDY)),
            "source": source, "raw_sha256": raw_sha(genome.numpy()), "file_sha256": sha(target)})
    for name, source in (("config.yaml", SOURCE_CONFIG), ("pool_config.yaml", POOL_CONFIG),
                         ("persistent_protocol.json", PERSISTENT_PROTOCOL), ("startup_identity.json", STARTUP)):
        shutil.copyfile(ROOT / source, inputs / name)
    fixture = next(c for c in read(ROOT / TRUTH)["cases"] if c["name"] == "body0_renewal_55040000")
    save(inputs / "visibility_truth.json", fixture, exclusive=True)
    shutil.copyfile(ROOT / acceptance["seed_audit_path"], inputs / "seed_audit.json")
    protocol["input_pins"] = {str(p.relative_to(STUDY)): sha(p) for p in sorted(inputs.iterdir())}
    protocol["source_pins"] = source_pins
    production = sorted((ROOT / "src").rglob("*.py")) + [ROOT / "src/life/kernel.c",
                                                          ROOT / "scripts/taskvar_gates.py"]
    protocol["production_pins"] = {str(p.relative_to(ROOT)): sha(p) for p in production}
    protocol["review_pins"] = acceptance["review_pins"]
    protocol["prior_commit"] = acceptance["prior_commit"]
    save(STUDY / "protocol.json", protocol, exclusive=True)
    print("prepared exact fixed inputs; zero genetic draws, builds or simulation calls")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--prepare", action="store_true")
    args = parser.parse_args()
    if args.prepare:
        prepare()
    else:
        import json
        print(json.dumps(plan(), indent=2))
