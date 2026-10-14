"""Freeze Q's fixed s7 inputs and source/dependency pins; no compilation or life simulation."""
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

RUNS = (51891, 51892)
GENETICS_SHA = "8fd717bdecb5f0e073e04838bbf286a4a968924bc9848b55c5a8d2b2055f4139"
P_PINS = {"protocol.json": "2b4628a0ef6c2bef186641e5302eae9eaa1c41a98c1aa7218e9c95c378c70cfa",
          "run_budgeted.py": "7c30a8ca961df1483eefba08f6a0ba149f1ae0fbac1dd39cd98ec0283c31f101"}


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
    archive = ROOT / "results/s7_continuation_20261014"
    provenance = read(archive / "provenance.json")
    if provenance["status"] != "complete":
        raise ValueError("L scientific archive is incomplete")
    for name, record in provenance["artifacts"].items():
        if sha(archive / name) != record["sha256"] or (archive / name).stat().st_size != record["bytes"]:
            raise ValueError("L sealed artifact differs: " + name)
    previous = read(archive / "protocol.json")
    manifest = read(archive / "confirmation/manifest.json")
    budget = read(archive / "operations/budget.json")
    if budget["status"] != "complete" or budget.get("running") or budget.get("queued"):
        raise ValueError("L resource receipt is incomplete")
    if manifest["numerical_identity"] != previous["expected_numerical_identity"]:
        raise ValueError("L numerical identity differs")
    for relative, digest in previous["source_identity"].items():
        if sha(ROOT / relative) != digest:
            raise ValueError("current numerical source differs: " + relative)
    for name, digest in P_PINS.items():
        if sha(ROOT / DEPENDENCY / name) != digest:
            raise ValueError("P source pin differs: " + name)
    audit_source = STUDY / "sources/G_audit_search.py"
    if sha(audit_source) != GENETICS_SHA:
        raise ValueError("reviewed genetic replay helper differs")
    loader = importlib.util.spec_from_file_location("Q_existing_genetic_replay", audit_source)
    helper = importlib.util.module_from_spec(loader)
    loader.loader.exec_module(helper)
    inputs = {}

    def keep(source, relative):
        freeze(STUDY / relative, source.read_bytes())
        inputs[relative] = {"sha256": sha(source), "source": str(source.relative_to(ROOT))}

    raw_hashes = []
    sources = [archive / "inputs/founder_row29.json"] + [archive / f"runs/s{run}/best_genome.json" for run in RUNS]
    for label, source in zip(LABELS, sources):
        _, genome = Layout.load(source)
        digest = hashlib.sha256(genome.numpy().tobytes()).hexdigest()
        if digest != manifest["genotype_sha256"][label.removeprefix("l_")]:
            raise ValueError("fixed genotype differs from L confirmation")
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
            raise ValueError("L input differs from exact generation16 final population rank0")
        if sha(folder / "checkpoint.pt") != manifest["checkpoint_sha256"][str(run)]:
            raise ValueError("L checkpoint differs from fixed confirmation")
        if [row["gen"] for row in state["curves"]] != list(range(16)):
            raise ValueError("L search history is incomplete")
        health = {key: max(row[key] for row in state["curves"])
                  for key in ("pop_invalid", "pop_mismatch", "recheck_invalid")}
        if any(health.values()):
            raise ValueError("L contains invalid or mismatched search lives")
        lines = [json.loads(line) for line in (folder / "lineage.jsonl").read_text().splitlines() if line.strip()]
        replay = helper.replay_genetics(lines, state, layout, founder, structural=False)
        endpoints[str(run)] = {"checkpoint_sha256": sha(folder / "checkpoint.pt"), "generation": 16,
                              "endpoint_rule": "exact final population rank0", "health": health,
                              "genetic_replay": replay}
        for name in ("checkpoint.pt", "best_genome.json", "lineage.jsonl"):
            keep(folder / name, f"inputs/L/runs/s{run}/" + name)
        keep(archive / f"configs/s{run}.yaml", f"inputs/L/configs/s{run}.yaml")
    keep(archive / "configs/s51891.yaml", "inputs/evaluator.yaml")
    for name in ("provenance.json", "protocol.json", "confirmation/manifest.json", "operations/budget.json",
                 "seed_audit.json", "initialization.json", "inputs/founder_row29.json"):
        keep(archive / name, "inputs/L/" + name)
    seed_audit = read(STUDY / "seed_audit.json")
    seeds = list(range(52_030_000, 52_030_512))
    if seed_audit["status"] != "passed" or seed_audit["candidate_seeds"] != seeds:
        raise ValueError("fresh seed namespace audit differs")
    protocol = {
        "status": "prepared_not_released", "labels": list(LABELS), "conditions": list(CONDITIONS),
        "seed_block": BLOCK, "seeds": seeds, "genome_lives": 6144, "threads": 2, "max_cpu_seconds": CAP,
        "T": 1536, "t_fork": 768, "t_open": 800,
        "worlds": {key: asdict(world) for key, world in worlds().items()},
        "source_identity": previous["source_identity"], "numerical_identity": previous["expected_numerical_identity"],
        "helpers": {name: sha(ROOT / "scripts" / name) for name in HELPERS}, "inputs": inputs,
        "genome_raw_sha256": raw_hashes, "fixed_endpoint_audits": endpoints,
        "wait_for_studies": [DEPENDENCY], "dependencies": {DEPENDENCY: P_PINS},
        "preparation_pins": {name: sha(STUDY / name) for name in
                             ("prepare.py", "PREREG.md", "seed_audit.json", "sources/seed_review.py",
                              "sources/G_audit_search.py", "sources/H_measure.py")},
        "L_scientific_provenance_sha256": sha(archive / "provenance.json"),
        "primary": [label + "__added_hidden_dependence" for label in LABELS[1:]],
        "formula": "(L-row29)freeze - (L-row29)freeze+hidden_off, paired within each fresh seed",
        "secondary": "Added lateral dependence, normal/frozen gains, gain lost under freeze, each tissue lesion loss",
        "validation": "No preparation lives. Existing E/H frozen-window validation and two standard "
                      "numerical-identity startup goldens after release; all CPU included in the cap.",
        "limitations": [
            "Conditional spike-message dependence does not establish a new algorithm or adult maturity.",
            "Frozen genotypes may have different bodies and states; footprints are not matched.",
            "Freeze also suppresses GRN/phenotype updates; normal-minus-freeze is not development alone.",
            "Hidden sends can act indirectly; hidden_off does not silence cells or chemistry.",
            "New hidden/lateral sends are suppressed with normal charges; in-flight messages still arrive.",
            "Settling removes bounded pending deliveries, not prior membrane states or world history.",
            "Three-SE flags are descriptive; unresolved effects are not zero, and both endpoint signs remain.",
            "Life-level SE concerns fixed descendants, not uncertainty over evolutionary searches.",
            "Low hidden-cell counts in L motivate no prediction or selection; all fixed arms remain.",
            "P is solely a resource dependency; its result never changes Q candidates or contrasts."]}
    (STUDY / "protocol.json").write_text(json.dumps(protocol, indent=2, allow_nan=False) + "\n")
    print(json.dumps({"status": protocol["status"], "genome_lives": 6144, "simulated_lives": 0}))


if __name__ == "__main__":
    main()
