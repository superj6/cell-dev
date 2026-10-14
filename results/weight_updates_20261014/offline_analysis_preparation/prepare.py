"""Freeze R's fixed s5 inputs and source/dependency pins; no compilation or life simulation."""
from __future__ import annotations

import hashlib
import importlib.util
import json
import os
import sys
from dataclasses import asdict
from pathlib import Path

os.environ.setdefault("ATEN_CPU_CAPABILITY", "avx2")
ROOT = next(path for path in Path(__file__).resolve().parents if (path / "src/genome.py").exists())
sys.path.insert(0, str(ROOT))
from measure import BLOCK, CAP, CONDITIONS, DEPENDENCY, HELPERS, LABELS, STUDY, sha, worlds  # noqa: E402

RUNS = (51089, 51090)
GENETICS_SHA = "8fd717bdecb5f0e073e04838bbf286a4a968924bc9848b55c5a8d2b2055f4139"
Q_PINS = {"protocol.json": "9645eb61c343905bd870b5f7ef5329ef77c54fd2205fa739511e1798466b6545",
          "run_budgeted.py": "6d27bda12f049c946471ee8e7d8f4222558268b1d2bc05d043145890a1a2b919"}


def read(path):
    return json.loads(Path(path).read_text())


def freeze(path, data):
    path.parent.mkdir(parents=True, exist_ok=True)
    if path.exists() and path.read_bytes() != data:
        raise ValueError("frozen input differs: " + str(path))
    path.write_bytes(data)


def main():
    from omegaconf import OmegaConf

    from src import checkpoint
    from src.genome import Layout

    if (STUDY / "ready.json").exists() or (STUDY / "budget.json").exists():
        raise ValueError("preparation cannot rewrite a released study")
    archive = ROOT / "results/continuation_20261013"
    provenance = read(archive / "provenance.json")
    for name, record in provenance["artifacts"].items():
        if sha(archive / name) != record["sha256"] or (archive / name).stat().st_size != record["bytes"]:
            raise ValueError("D sealed artifact differs: " + name)
    previous = read(archive / "protocol.json")
    if (provenance["protocol_sha256"] != sha(archive / "protocol.json")
            or provenance["numerical_identity"] != previous["expected_numerical_identity"]):
        raise ValueError("D provenance identity differs")
    manifest = read(archive / "confirmation/manifest.json")
    budget = read(archive / "operations/budget.json")
    if budget["status"] != "complete" or budget.get("running") or budget.get("queued"):
        raise ValueError("D resource receipt is incomplete")
    if manifest["numerical_identity"] != previous["expected_numerical_identity"]:
        raise ValueError("D numerical identity differs")
    for relative, digest in previous["source_identity"].items():
        if sha(ROOT / relative) != digest:
            raise ValueError("current numerical source differs: " + relative)
    for name, digest in Q_PINS.items():
        if sha(ROOT / DEPENDENCY / name) != digest:
            raise ValueError("Q source pin differs: " + name)
    audit_source = STUDY / "sources/G_audit_search.py"
    if sha(audit_source) != GENETICS_SHA:
        raise ValueError("reviewed genetic replay helper differs")
    loader = importlib.util.spec_from_file_location("R_existing_genetic_replay", audit_source)
    helper = importlib.util.module_from_spec(loader)
    loader.loader.exec_module(helper)
    inputs = {}

    def keep(source, relative):
        freeze(STUDY / relative, source.read_bytes())
        inputs[relative] = {"sha256": sha(source), "source": str(source.relative_to(ROOT))}

    raw_hashes = []
    sources = [archive / "inputs/founder_row38.json"] + [archive / f"runs/s{run}/best_genome.json" for run in RUNS]
    for label, source in zip(LABELS, sources):
        _, genome = Layout.load(source)
        digest = hashlib.sha256(genome.numpy().tobytes()).hexdigest()
        if digest != manifest["genotype_sha256"][label.removeprefix("d_")]:
            raise ValueError("fixed genotype differs from D confirmation")
        keep(source, "inputs/" + label + ".json")
        raw_hashes.append(digest)
    layout, founder = Layout.load(sources[0])
    endpoints = {}
    for run in RUNS:
        folder = archive / f"runs/s{run}"
        saved = checkpoint.load(folder / "checkpoint.pt")
        checkpoint.validate(saved, OmegaConf.load(archive / f"configs/s{run}.yaml"),
                            previous["expected_numerical_identity"])
        state = saved["state"]
        _, genome = Layout.load(folder / "best_genome.json")
        if state["generation"] != 16 or genome.numpy().tobytes() != state["population"][0].numpy().tobytes():
            raise ValueError("D input differs from exact generation16 final population rank0")
        if sha(folder / "checkpoint.pt") != manifest["checkpoint_sha256"][str(run)]:
            raise ValueError("D checkpoint differs from fixed confirmation")
        if [row["gen"] for row in state["curves"]] != list(range(16)):
            raise ValueError("D search history is incomplete")
        health = {key: max(row[key] for row in state["curves"])
                  for key in ("pop_invalid", "pop_mismatch", "recheck_invalid")}
        if any(health.values()):
            raise ValueError("D contains invalid or mismatched search lives")
        lines = [json.loads(line) for line in (folder / "lineage.jsonl").read_text().splitlines() if line.strip()]
        replay = helper.replay_genetics(lines, state, layout, founder, structural=False)
        endpoints[str(run)] = {"checkpoint_sha256": sha(folder / "checkpoint.pt"), "generation": 16,
                              "endpoint_rule": "exact final population rank0", "health": health,
                              "genetic_replay": replay}
        for name in ("checkpoint.pt", "best_genome.json", "lineage.jsonl"):
            keep(folder / name, f"inputs/D/runs/s{run}/" + name)
        keep(archive / f"configs/s{run}.yaml", f"inputs/D/configs/s{run}.yaml")
    keep(archive / "configs/s51089.yaml", "inputs/evaluator.yaml")
    for name in ("provenance.json", "protocol.json", "confirmation/manifest.json", "operations/budget.json",
                 "seed_audit.json", "inputs/founder_row38.json"):
        keep(archive / name, "inputs/D/" + name)
    seed_audit = read(STUDY / "seed_audit.json")
    seeds = list(range(52_040_000, 52_040_512))
    if seed_audit["status"] != "passed" or seed_audit["candidate_seeds"] != seeds:
        raise ValueError("fresh seed namespace audit differs")
    protocol = {
        "status": "prepared_not_released", "labels": list(LABELS), "conditions": list(CONDITIONS),
        "seed_block": BLOCK, "seeds": seeds, "genome_lives": 4608, "threads": 2, "max_cpu_seconds": CAP,
        "T": 1536, "t_fork": 768, "t_open": 800,
        "worlds": {key: asdict(world) for key, world in worlds().items()},
        "source_identity": previous["source_identity"], "numerical_identity": previous["expected_numerical_identity"],
        "helpers": {name: sha(ROOT / "scripts" / name) for name in HELPERS}, "inputs": inputs,
        "genome_raw_sha256": raw_hashes, "fixed_endpoint_audits": endpoints,
        "wait_for_studies": [DEPENDENCY], "dependencies": {DEPENDENCY: Q_PINS},
        "preparation_pins": {name: sha(STUDY / name) for name in
                             ("prepare.py", "PREREG.md", "seed_audit.json", "sources/seed_review.py",
                              "sources/G_audit_search.py", "sources/H_measure.py",
                              "semantic_proof/COMBINED_CLAMP_SOURCE_AUDIT.md",
                              "semantic_proof/source_proof.json", "semantic_proof/independent_review.json",
                              "semantic_proof/independent_review.py")},
        "D_scientific_provenance_sha256": sha(archive / "provenance.json"),
        "primary": [label + "__added_C_minus_F" for label in LABELS[1:]],
        "formula": "(D-row38)C - (D-row38)F, paired within each fresh seed",
        "secondary": "Added S-minus-C, gains in all three conditions, each genotype's C-minus-F and S-minus-C",
        "contrast_count": 16,
        "arm_meanings": {
            "S": "Structure held fixed by division_off and apoptosis_off",
            "C": "S plus identity_clamp and pheno_fixed; local effective receive weights still update",
            "F": "Existing freeze; gene state, phenotype and effective receive weights held fixed"},
        "validation": "No preparation lives. Existing fixed-window validation and two standard numerical-identity "
                      "startup goldens after release; all CPU included in the cap.",
        "limitations": [
            "C-minus-F is a conditional ongoing effective receive-weight update effect from local chemical/contact "
            "state, including early transient carryover and closed-loop changes in spikes, movement, captures "
            "and costs.",
            "S-minus-C includes continuing GRN/phenotype updates and any readout catch-up from pre-fork partition.",
            "Neither contrast isolates pure memory, learning, adult maturity or a new algorithm.",
            "derive does not directly read activity/receptor traces; chemical relaxation alone can drive weights. "
            "A positive C-minus-F does not establish sensory adaptation or use of changing evidence.",
            "Genotypes may have different bodies and states; footprints are not matched.",
            "Settling removes bounded pending deliveries, not prior membrane states, chemical state or world history.",
            "Chemistry continues in all arms. There is no modeled charge per GRN/readout/derive operation.",
            "All guards/extinction penalties remain in fitness; structural invariants use complete matched triplets.",
            "Three-SE flags are descriptive; unresolved effects are not zero, and both endpoint signs remain.",
            "Life-level SE concerns fixed descendants, not uncertainty over evolutionary searches.",
            "Q is solely a resource dependency; its result never changes R candidates or contrasts.",
            "The R motivation and fixed design precede O outcome inspection."]}
    (STUDY / "protocol.json").write_text(json.dumps(protocol, indent=2, allow_nan=False) + "\n")
    print(json.dumps({"status": protocol["status"], "genome_lives": 4608, "simulated_lives": 0}))


if __name__ == "__main__":
    main()
