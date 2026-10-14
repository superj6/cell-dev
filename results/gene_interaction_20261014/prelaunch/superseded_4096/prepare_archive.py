"""Publish prospective M source/genome receipts without releasing or simulating the study."""
from __future__ import annotations

import json
import shutil
from pathlib import Path

from run_budgeted import save

from measure import HELPERS, ROOT, STUDY, check_protocol, sha

OUT = ROOT / "results/gene_interaction_20261014"


def main():
    if (STUDY / "ready.json").exists() or (STUDY / "budget.json").exists():
        raise ValueError("cannot refresh released preparation")
    protocol = check_protocol()
    dependencies = {name: {file: sha(ROOT / name / file) for file in ("protocol.json", "run_budgeted.py")}
                    for name in protocol["wait_for_studies"]}
    ready = {"status": "template_not_released", "files": {
        name: sha(STUDY / name) for name in ("run_budgeted.py", "measure.py", "protocol.json")},
        "dependencies": dependencies}
    save(STUDY / "ready.template.json", ready)
    artifacts = {}

    def keep(source, relative):
        target = OUT / relative
        target.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(source, target)
        artifacts[str(relative)] = {"sha256": sha(target), "bytes": target.stat().st_size}

    for name in ("README.md", "PREREG.md", "prepare.py", "prepare_archive.py", "protocol.json", "measure.py",
                 "run_budgeted.py", "test_measure.py", "test_monitor.py", "validation.json", "independent_review.json",
                 "ready.template.json", "seed_audit.json", "genomes.json", "genotypes.npy",
                 "sources/G_audit_search.py"):
        keep(STUDY / name, name)
    for relative in protocol["inputs"]:
        keep(STUDY / relative, relative)
    for name in HELPERS:
        keep(ROOT / "scripts" / name, Path("sources/scripts") / name)
    for relative in protocol["source_identity"]:
        keep(ROOT / relative, Path("sources") / relative)
    for folder, files in dependencies.items():
        for relative in files:
            keep(ROOT / folder / relative, Path("dependency/L") / relative)
    save(OUT / "provenance.json", {"status": "prospective_preparation_not_released", "artifacts": artifacts,
                                  "simulated_lives": 0, "numerical_identity": protocol["numerical_identity"],
                                  "total_artifact_bytes": sum(value["bytes"] for value in artifacts.values())})
    print(json.dumps({"status": "prospective_preparation_not_released", "hashed_artifacts": len(artifacts),
                      "simulated_lives": 0, "ready_json_created": False}))


if __name__ == "__main__":
    main()
