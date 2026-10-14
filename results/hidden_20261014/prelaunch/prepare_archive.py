"""Publish H preparation with hashes only; no readiness marker and no simulation."""
from __future__ import annotations

import json
import shutil
from pathlib import Path

from run_budgeted import save

from measure import HELPERS, ROOT, STUDY, check_protocol, sha

OUT = ROOT / "results/hidden_20261014"


def main():
    protocol = check_protocol()
    ready = {"status": "template_not_released", "files": {
        name: sha(STUDY / name) for name in ("run_budgeted.py", "measure.py", "protocol.json")}}
    save(STUDY / "ready.template.json", ready)
    artifacts = {}

    def keep(source, relative):
        target = OUT / relative
        target.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(source, target)
        artifacts[str(relative)] = {"sha256": sha(target), "bytes": target.stat().st_size}

    for name in ("README.md", "PREREG.md", "prepare.py", "prepare_archive.py", "protocol.json", "measure.py",
                 "run_budgeted.py", "test_measure.py", "test_monitor.py", "validation.json", "ready.template.json"):
        keep(STUDY / name, name)
    for relative in protocol["inputs"]:
        keep(STUDY / relative, relative)
    for name in HELPERS:
        keep(ROOT / "scripts" / name, Path("sources") / name)
    for relative in protocol["source_identity"]:
        keep(ROOT / relative, Path("sources") / relative)
    for relative in protocol["G_dependency_pins"]:
        keep(ROOT / protocol["G_study"] / relative, Path("dependency") / relative)
    save(OUT / "provenance.json", {"status": "prepared_not_released", "artifacts": artifacts,
                                  "simulated_lives": 0, "numerical_identity": protocol["numerical_identity"]})
    print(json.dumps({"status": "prepared_not_released", "hashed_artifacts": len(artifacts),
                      "simulated_lives": 0, "ready_json_created": False}))


if __name__ == "__main__":
    main()
