"""Freeze all M genomes and source-origin mappings using completed G; no life simulation."""
from __future__ import annotations

import json
import shutil
from dataclasses import asdict

from measure import HELPERS, ROLES, ROOT, RUNS, STUDY, candidates, load_endpoints, raw_sha, read_json, seeds, sha, world

LIMITATIONS = [
    "The paired four-arm contrast measures whole-life genetic interaction in each fixed endpoint.",
    "Every knockout acts from birth and may change development, morphology, physiology and later computation.",
    "Either interaction sign may arise from development or nonlinear task fitness; "
    "sign alone is not a redundancy label.",
    "The extant source-origin gene may have changed since duplication; "
    "ancestry does not imply identical current roles.",
    "No intervention isolates an adult gene-specific mechanism, expanded computation or a new algorithm.",
    "Both fixed endpoints and all effect signs remain; no selection or additional lives follow the result.",
    "Three-SE and absolute0.5F flags are descriptive; life-level SE does not describe variability across searches.",
    "These results do not establish that duplication was necessary for a function to evolve "
    "or that its policy is better.",
]


def save(path, value):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, indent=2, allow_nan=False) + "\n")


def main():
    import numpy as np

    if (STUDY / "ready.json").exists() or (STUDY / "budget.json").exists():
        raise ValueError("released preparation cannot be rewritten")
    g = ROOT / "results/structural_20261013"
    prior = read_json(g / "provenance.json")
    for relative, metadata in prior["artifacts"].items():
        path = g / relative
        if sha(path) != metadata["sha256"] or path.stat().st_size != metadata["bytes"]:
            raise ValueError("completed G archive changed: " + relative)
    files = ["protocol.json", "operations/budget.json", "provenance.json"]
    for seed in RUNS:
        files += [f"configs/s{seed}.yaml"]
        files += [f"runs/s{seed}/{name}" for name in ("checkpoint.pt", "best_genome.json", "lineage.jsonl")]
    copies = {"inputs/G/" + name: g / name for name in files}
    copies.update({"inputs/founder_row38.json": g / "inputs/founder_row38.json",
                   "inputs/evaluator.yaml": g / "configs/s51089.yaml",
                   "sources/seed_review.py.txt": ROOT / "outputs/audit_m_20261014/check_sources.py",
                   "sources/D_seed_prepare.py": ROOT / "outputs/autonomous_s7_20261014/sources/D_prepare.py"})
    for relative, source in copies.items():
        destination = STUDY / relative
        destination.parent.mkdir(parents=True, exist_ok=True)
        if destination.exists() and destination.read_bytes() != source.read_bytes():
            raise ValueError("fixed G input changed")
        shutil.copy2(source, destination)
    layout, records = load_endpoints()
    genomes, labels, branches = candidates(layout, records)
    manifest = {"labels": labels, "branches": branches,
                "endpoint_audits": {str(seed): record["audit"] for seed, record in records.items()},
                "genotypes_raw_sha256": raw_sha(genomes), "simulated_lives": 0}
    save(STUDY / "genomes.json", manifest)
    np.save(STUDY / "genotypes.npy", genomes, allow_pickle=False)
    seed_audit = read_json(STUDY / "seed_audit.json")
    if seed_audit["status"] != "passed" or seed_audit["candidate_seeds"] != seeds():
        raise ValueError("fresh seed namespace audit missing or inconsistent")
    if sha(STUDY / "sources/D_seed_prepare.py") != seed_audit["seed_audit"]["helper_sha256"]:
        raise ValueError("seed enumeration helper differs from independent receipt")
    source = read_json(g / "protocol.json")
    protocol = {"status": "prospective_preparation_not_released", "runs": list(RUNS), "lives": 512,
                "seed_block": 100, "seeds": seeds(), "genome_lives": 4096, "max_cpu_seconds": 3600,
                "threads": 2, "T": 1024, "roles": list(ROLES),
                "endpoint_rule": "exact final population rank0 at generation16",
                "pair_rule": "unique active copied-origin gene and its extant exact source origin from genetic replay",
                "scope_failure": "If the frozen one-pair-per-endpoint mapping fails, stop; "
                                 "never substitute another gene.",
                "source_identity": source["source_identity"],
                "numerical_identity": source["expected_numerical_identity"],
                "helpers": {name: sha(ROOT / "scripts" / name) for name in HELPERS},
                "inputs": {relative: sha(STUDY / relative) for relative in copies},
                "preparation_pins": {name: sha(STUDY / name)
                                     for name in ("prepare.py", "PREREG.md", "seed_audit.json",
                                                  "genomes.json", "genotypes.npy")},
                "wait_for_studies": ["outputs/autonomous_s7_20261014"], "world": asdict(world()),
                "primary": "intact minus copy_KO minus source_KO plus double_KO within each shared seed",
                "descriptive_flags": "abs(mean)>3SE and abs(mean)>=0.5F, retaining both signs and every endpoint",
                "secondary": "all three intact-minus-knockout losses, full income/cost and morphology accounting",
                "deduplication": "none; all eight roles receive the same512seeds explicitly",
                "validation": "Pure genome operations only during preparation; startup goldens are additional to4096 "
                              "research lives and their CPU is included in the cumulative cap.",
                "limitations": LIMITATIONS}
    save(STUDY / "protocol.json", protocol)
    print(json.dumps({"status": protocol["status"], "genome_lives": 4096, "simulated_lives": 0,
                      "pairs": {seed: {key: value[key] for key in
                                ("copy_slot", "copy_origin_id", "source_slot", "source_origin_id")}
                                for seed, value in branches.items()}}))


if __name__ == "__main__":
    main()
