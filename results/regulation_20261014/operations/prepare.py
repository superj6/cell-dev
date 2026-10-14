"""Pin O after the M/N scheduling dependencies are prepared; no simulated lives."""
from __future__ import annotations

import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))

from measure import BLOCK, CAP, CONDITIONS, HELPERS, LABELS, STUDY, sha  # noqa: E402


def freeze(path, data):
    path.parent.mkdir(parents=True, exist_ok=True)
    if path.exists():
        if path.read_bytes() != data:
            raise ValueError("prepared artifact changed: " + str(path))
        return
    path.write_bytes(data)


def freeze_json(path, value):
    freeze(path, (json.dumps(value, indent=2, allow_nan=False) + "\n").encode())


def main():
    from run_budgeted import DEPENDENCIES

    archive = ROOT / "results/hidden_20261014"
    prior = json.loads((archive / "provenance.json").read_text())
    h = json.loads((archive / "protocol.json").read_text())
    if json.loads((archive / "operations/budget.json").read_text())["status"] != "complete":
        raise ValueError("motivating H study not complete")
    inputs = {}
    for name in [label + ".json" for label in LABELS] + ["evaluator.yaml"]:
        relative = "inputs/" + name
        source = archive / relative
        if sha(source) != prior["artifacts"][relative]["sha256"]:
            raise ValueError("H fixed input changed")
        freeze(STUDY / relative, source.read_bytes())
        inputs[relative] = {"sha256": sha(source), "source": str(source.relative_to(ROOT))}
    seeds = list(range(52_010_000, 52_010_512))
    receipt = ROOT / "outputs/audit_m_20261014/source_seed_review.json"
    freeze(STUDY / "seed_review.json", receipt.read_bytes())
    review = json.loads(receipt.read_text())
    candidate = review["candidate_101"]
    if (review["status"] != "passed" or candidate["seeds"] != seeds
            or candidate["pilot_overlap"] or candidate["D_G_L_overlap"]):
        raise ValueError("O independent namespace receipt differs")
    for relative, digest in h["source_identity"].items():
        if sha(ROOT / relative) != digest:
            raise ValueError("source differs from H: " + relative)
    for relative in ("protocol.json", "summary.json", "provenance.json"):
        freeze(STUDY / "motivation_H" / relative, (archive / relative).read_bytes())
    dependencies = {folder: {name: sha(ROOT / folder / name)
                             for name in ("protocol.json", "run_budgeted.py")} for folder in DEPENDENCIES}
    protocol = {
        "status": "prepared_not_started", "labels": list(LABELS), "conditions": list(CONDITIONS),
        "seed_block": BLOCK, "seeds": seeds, "genome_lives": 4608, "threads": 2,
        "max_cpu_seconds": CAP, "T": 1536, "t_fork": 768, "t_open": 800,
        "source_identity": h["source_identity"], "numerical_identity": h["numerical_identity"],
        "helpers": {name: sha(ROOT / "scripts" / name) for name in HELPERS},
        "inputs": inputs, "genome_raw_sha256": h["genome_raw_sha256"],
        "fixed_endpoint_audits": h["fixed_endpoint_audits"],
        "seed_review_sha256": sha(STUDY / "seed_review.json"),
        "prereg_sha256": sha(STUDY / "PREREG.md"),
        "prepare_sha256": sha(Path(__file__)), "wait_for_studies": list(DEPENDENCIES),
        "primary": [label + "__added_input_dependence" for label in LABELS[1:]],
        "formula": "(D-row38)structure - (D-row38)structure+genes_blind within each fresh seed",
        "secondary": "Each arm's D-row38 gain, own input loss, structure-minus-freeze effects and accounting.",
        "structure_flags": ["division_off", "apoptosis_off"],
        "genes_blind_inputs": {"18": "own spike trace", "19": "incoming channel0 trace",
                               "20": "incoming channel1 trace", "21": "contact count fraction",
                               "22": "receptor trace"},
        "retained_GRN_inputs": "Current genes, both morphogens and sense/act plane cues.",
        "motivation": "H D51090 normal-minus-freeze gain loss +0.914342313962279 +/-0.21374879038851366F; "
                      "both fixed D endpoints retained despite their different H outcomes.",
        "validation": "No preparation simulation. Two startup T200 golden lives are inside the CPU cap "
                      "but outside the4608 research lives. Constant structure is checked in all scored arms.",
        "limitations": [
            "Masking five GRN inputs is not general blindness: morphogens and plane cues remain.",
            "Receptor events still reach neurons, and spike messaging continues.",
            "This tests ongoing dependence on specified local GRN inputs, not memory or a new algorithm.",
            "The structure-minus-freeze comparison includes phenotype and effective-weight updates.",
            "Genotypes retain different footprints and pre-fork state; no matched-footprint claim.",
            "Pending pre-fork events settle before800, but the interval does not erase their earlier effects.",
            "All guarded/extinct fitness rows remain; invalid implementation rows stop the study.",
            "Both signs and endpoints are retained; descriptive3SE flags do not estimate search reliability."]}
    freeze_json(STUDY / "protocol.json", protocol)
    freeze_json(STUDY / "ready.template.json", {
        "status": "template_not_released",
        "files": {name: sha(STUDY / name) for name in ("run_budgeted.py", "measure.py", "protocol.json")},
        "dependencies": dependencies})
    print(json.dumps({"status": "prepared_not_started", "simulated_lives": 0, "research_lives": 4608}))


if __name__ == "__main__":
    main()
