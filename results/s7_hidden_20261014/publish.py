"""Copy Q's prospective preparation and audited sources; never release or simulate."""
from __future__ import annotations

import json
import shutil
from pathlib import Path

from run_budgeted import READY_FILES, save

from measure import ROOT, STUDY, check_protocol, sha

OUT = ROOT / "results/s7_hidden_20261014"


def main():
    if (STUDY / "ready.json").exists() or (STUDY / "budget.json").exists():
        raise ValueError("cannot republish preparation after release")
    protocol = check_protocol()
    ready = {"status": "template_not_released", "files": {name: sha(STUDY / name) for name in READY_FILES},
             "dependencies": protocol["dependencies"]}
    save(STUDY / "ready.template.json", ready)
    artifacts = {}

    def keep(source, relative):
        target = OUT / relative
        target.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(source, target)
        artifacts[str(relative)] = {"sha256": sha(target), "bytes": target.stat().st_size}

    for name in ("README.md", "PREREG.md", "prepare.py", "publish.py", "protocol.json", "measure.py",
                 "run_budgeted.py", "test_measure.py", "test_monitor.py", "validation.json", "ready.template.json"):
        keep(STUDY / name, name)
    for relative in set(protocol["inputs"]) | set(protocol["preparation_pins"]):
        keep(STUDY / relative, relative)
    for relative in protocol["source_identity"]:
        keep(ROOT / relative, Path("sources") / relative)
    for name in protocol["helpers"]:
        keep(ROOT / "scripts" / name, Path("sources/scripts") / name)
    for name in protocol["dependencies"]["outputs/autonomous_next_step_20261014"]:
        keep(ROOT / "outputs/autonomous_next_step_20261014" / name, Path("dependency/P") / name)
    audit = json.loads((STUDY / "seed_audit.json").read_text())
    for relative, digest in audit["source_sha256"].items():
        if sha(ROOT / relative) != digest:
            raise ValueError("namespace audit source changed: " + relative)
        keep(ROOT / relative, Path("namespace_sources") / relative)
    for name in ("science_review.json", "monitor_review.json"):
        keep(ROOT / "outputs/audit_q_20261014" / name, Path("review") / name)
    save(OUT / "provenance.json", {"status": "prospective_preparation_not_released", "artifacts": artifacts,
                                  "simulated_lives": 0, "ready_json_created": False})
    print(json.dumps({"status": "prospective_preparation_not_released", "artifacts": len(artifacts),
                      "simulated_lives": 0, "ready_json_created": False}))


if __name__ == "__main__":
    main()
