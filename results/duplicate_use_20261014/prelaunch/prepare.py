"""Prospectively freeze J policy before G finishes; never inspect interim endpoints or scores."""
from __future__ import annotations

import json
import shutil

from measure import HELPERS, ROOT, RUNS, STUDY, sha


def main():
    g = ROOT / "outputs/autonomous_structural_20261013"
    source = json.loads((g / "protocol.json").read_text())
    inputs = {}
    for name, path in (("founder_row38.json", g / "inputs/founder_row38.json"),
                       ("evaluator.yaml", g / "configs/s51089.yaml"), ("G_protocol.json", g / "protocol.json")):
        target = STUDY / "inputs" / name
        target.parent.mkdir(parents=True, exist_ok=True)
        if target.exists() and target.read_bytes() != path.read_bytes():
            raise ValueError("prepared input changed")
        shutil.copy2(path, target)
        inputs[str(target.relative_to(STUDY))] = sha(target)
    protocol = {"status": "prospective_preparation_not_released", "runs": list(RUNS),
                "lives_per_stage": 512, "stage_blocks": {"screen": 98, "confirm": 99},
                "max_genome_lives": 19456, "max_cpu_seconds": 7200, "threads": 2, "T": 1024,
                "endpoint_rule": "exact final population rank0 at generation16",
                "candidate_rule": "every active slot with innovation origin >=16, no fitness or weight filter",
                "selection_rule": "largest paired intact-minus-KO mean per endpoint; smallest slot tie; any sign",
                "source_identity": source["source_identity"],
                "numerical_identity": source["expected_numerical_identity"],
                "helpers": {name: sha(ROOT / "scripts" / name) for name in HELPERS}, "inputs": inputs,
                "G_study": str(g.relative_to(ROOT)),
                "G_pins": {name: sha(g / name) for name in ("protocol.json", "run_budgeted.py", "audit_search.py")},
                "wait_for_studies": ["outputs/autonomous_hidden_20261014",
                                     "outputs/autonomous_decoy_gradient_20261014"],
                "world": {"preset": "catch_speck_l4", "d0": .5, "d_min": .25, "sigma": .4, "lam_s": 4},
                "count_bound": "At most16 duplicate-origin active slots per endpoint, 32KO+2intact screen rows; "
                               "then at most2selectedKO+2intact confirmation rows, all on512lives.",
                "no_candidates": "Report not applicable for each endpoint without active duplicate-origin genes; "
                                 "no substitute genotype, and no research lives if both are empty.",
                "deduplication": "none; all prescribed roles retained even if genotype bytes match",
                "validation": "No simulated preparation lives; numerical startup golden CPU is included in cap.",
                "limitations": [
                    "Confirmed loss measures one duplicated-origin gene's whole-life contribution, "
                    "including development.",
                    "A duplicate may replace an old gene or share a redundant role; "
                    "this does not prove expanded computation.",
                    "The knockout acts from birth in every cell; "
                    "it does not isolate an adult or fixed-tissue mechanism.",
                    "Individual null effects do not establish zero function or exclude redundancy and epistasis.",
                    "Initial strongest-gene selection is followed by fresh confirmation, retaining both signs.",
                    "Three-SE and greater-than0.5F confirmation flags are descriptive, not a20-run G-use criterion.",
                    "Two fixed endpoints do not establish general mutation-policy superiority."]}
    path = STUDY / "protocol.json"
    data = json.dumps(protocol, indent=2, allow_nan=False) + "\n"
    if path.exists() and path.read_text() != data:
        raise ValueError("prospective protocol changed")
    path.write_text(data)
    print(json.dumps({"status": protocol["status"], "max_genome_lives": 19456, "simulated_lives": 0}))


if __name__ == "__main__":
    main()
