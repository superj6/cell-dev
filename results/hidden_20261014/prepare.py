"""Freeze H's existing endpoint inputs, source identity and block94 protocol; no simulations."""
from __future__ import annotations

import hashlib
import json
import os
import sys
from pathlib import Path

os.environ.setdefault("ATEN_CPU_CAPABILITY", "avx2")
ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))
from measure import CONDITIONS, HELPERS, LABELS, STUDY, sha  # noqa: E402


def freeze(path, data):
    path.parent.mkdir(parents=True, exist_ok=True)
    if path.exists() and path.read_bytes() != data:
        raise ValueError("prepared file differs: " + str(path))
    path.write_bytes(data)


def main():
    from omegaconf import OmegaConf

    from src import checkpoint
    from src.genome import Layout

    archive = ROOT / "results/continuation_20261013"
    d = json.loads((archive / "protocol.json").read_text())
    manifest = json.loads((archive / "confirmation/manifest.json").read_text())
    budget = json.loads((archive / "operations/budget.json").read_text())
    if budget["status"] != "complete" or budget.get("running") or budget.get("queued"):
        raise ValueError("D is not complete")
    if manifest["numerical_identity"] != d["expected_numerical_identity"]:
        raise ValueError("D numerical identity differs")
    inputs, genome_hashes = {}, []
    sources = [archive / "inputs/founder_row38.json"] + [archive / f"runs/s{s}/best_genome.json"
                                                          for s in (51089, 51090)]
    for label, source in zip(LABELS, sources):
        _, genome = Layout.load(source)
        digest = hashlib.sha256(genome.numpy().tobytes()).hexdigest()
        prior_label = label.removeprefix("d_")
        if digest != manifest["genotype_sha256"][prior_label]:
            raise ValueError("fixed input differs from D confirmation")
        relative = "inputs/" + label + ".json"
        freeze(STUDY / relative, source.read_bytes())
        inputs[relative] = {"sha256": sha(source), "source": str(source.relative_to(ROOT))}
        genome_hashes.append(digest)
    endpoints = {}
    for seed in (51089, 51090):
        folder = archive / f"runs/s{seed}"
        saved = checkpoint.load(folder / "checkpoint.pt")
        cfg = OmegaConf.load(folder / "config.yaml")
        checkpoint.validate(saved, cfg, d["expected_numerical_identity"])
        _, genome = Layout.load(folder / "best_genome.json")
        if saved["state"]["generation"] != 16 or genome.numpy().tobytes() != (
                saved["state"]["population"][0].numpy().tobytes()):
            raise ValueError("D input is not exact generation16 final population rank0")
        if sha(folder / "checkpoint.pt") != manifest["checkpoint_sha256"][str(seed)]:
            raise ValueError("D checkpoint differs from frozen confirmation")
        endpoints[str(seed)] = {"checkpoint_sha256": sha(folder / "checkpoint.pt"), "generation": 16,
                                "endpoint_rule": "exact final population rank0"}
    for name, source in (("evaluator.yaml", archive / "configs/s51089.yaml"),
                         ("D_protocol.json", archive / "protocol.json"),
                         ("D_manifest.json", archive / "confirmation/manifest.json"),
                         ("D_budget.json", archive / "operations/budget.json")):
        relative = "inputs/" + name
        freeze(STUDY / relative, source.read_bytes())
        inputs[relative] = {"sha256": sha(source), "source": str(source.relative_to(ROOT))}
    g = ROOT / "outputs/autonomous_structural_20261013"
    seeds = list(range(51_940_000, 51_940_512))
    used = set(manifest["seeds"])
    for values in json.loads((archive / "seed_audit.json").read_text())["run_life_seeds"].values():
        used.update(values)
    if used.intersection(seeds):
        raise ValueError("H overlaps D discovery/confirmation seeds")
    for relative, digest in d["source_identity"].items():
        if sha(ROOT / relative) != digest:
            raise ValueError("current numerical source differs")
    protocol = {"status": "prepared_not_released", "labels": list(LABELS), "conditions": list(CONDITIONS),
                "seed_block": 94, "seeds": seeds, "genome_lives": 6144, "threads": 2,
                "max_cpu_seconds": 3600, "T": 1536, "t_fork": 768, "t_open": 800,
                "source_identity": d["source_identity"], "numerical_identity": d["expected_numerical_identity"],
                "helpers": {name: sha(ROOT / "scripts" / name) for name in HELPERS},
                "inputs": inputs, "genome_raw_sha256": genome_hashes, "fixed_endpoint_audits": endpoints,
                "G_study": str(g.relative_to(ROOT)),
                "G_dependency_pins": {name: sha(g / name) for name in ("protocol.json", "run_budgeted.py")},
                "primary": [label + "__added_hidden_dependence" for label in LABELS[1:]],
                "formula": "(D-row38)freeze - (D-row38)freeze+hidden_off, paired within each fresh seed",
                "secondary": "Added lateral dependence, normal/frozen gains and gain lost under freeze; "
                             "both endpoints",
                "validation": "No new simulated lives in preparation; E supplies existing "
                              "frozen-window validation",
                "limitations": [
                    "This is conditional spike-message dependence, not proof of a new algorithm or adult maturity.",
                    "Frozen genotypes may have different bodies and states; footprints are not matched.",
                    "Freeze also suppresses GRN/phenotype updates; normal-minus-freeze is not development alone.",
                    "Hidden sends can act indirectly through other cells; "
                    "hidden_off does not silence cells or chemistry.",
                    "New hidden/lateral sends are suppressed with their normal charge; "
                    "in-flight messages still arrive.",
                    "The settling interval removes bounded pending deliveries, not past membrane or world history.",
                    "Three-SE flags are descriptive; unresolved effects are not zero, and no endpoint is selected.",
                    "Life-level SE concerns two fixed descendants, not uncertainty over evolutionary searches."]}
    freeze(STUDY / "protocol.json", (json.dumps(protocol, indent=2, allow_nan=False) + "\n").encode())
    print(json.dumps({"status": protocol["status"], "genome_lives": 6144, "simulated_lives": 0}))


if __name__ == "__main__":
    main()
