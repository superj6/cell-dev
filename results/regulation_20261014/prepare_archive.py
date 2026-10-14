"""Publish O's fixed preparation without readiness or simulation."""
from __future__ import annotations

import json
from pathlib import Path

from prepare import freeze, freeze_json

from measure import ROOT, STUDY, check_protocol, sha

OUT = ROOT / "results/regulation_20261014"


def main():
    if any((STUDY / name).exists() for name in ("ready.json", "budget.json", "measurement")):
        raise ValueError("cannot publish a new preparation after release")
    protocol = check_protocol()
    ready = json.loads((STUDY / "ready.template.json").read_text())
    for name, digest in ready["files"].items():
        if sha(STUDY / name) != digest:
            raise ValueError("release template changed: " + name)
    artifacts = {}

    def keep(source, relative):
        target = OUT / relative
        freeze(target, Path(source).read_bytes())
        artifacts[str(relative)] = {"sha256": sha(target), "bytes": target.stat().st_size}

    for name in ("README.md", "PREREG.md", "prepare.py", "prepare_archive.py", "measure.py", "run_budgeted.py",
                 "protocol.json", "ready.template.json", "seed_review.json", "test_measure.py", "test_monitor.py",
                 "analyze.py", "test_analysis.py", "test_monitor_review.py", "independent_review.json"):
        keep(STUDY / name, name)
    for relative in protocol["inputs"]:
        keep(STUDY / relative, relative)
    for relative in protocol["source_identity"]:
        keep(ROOT / relative, Path("sources") / relative)
    for name in protocol["helpers"]:
        keep(ROOT / "scripts" / name, Path("sources") / name)
    for relative in ("protocol.json", "summary.json", "provenance.json", "inputs/D_protocol.json",
                     "inputs/D_manifest.json", "inputs/D_budget.json"):
        keep(ROOT / "results/hidden_20261014" / relative, Path("motivation_H") / relative)
    for folder, files in ready["dependencies"].items():
        for name, digest in files.items():
            source = ROOT / folder / name
            if sha(source) != digest:
                raise ValueError("prepared dependency changed: " + folder + "/" + name)
            keep(source, Path("dependencies") / Path(folder).name / name)
    for name, source in {
        "source_seed_review.py.txt": ROOT / "outputs/audit_m_20261014/check_sources.py",
        "D_seed_prepare.py.txt": ROOT / "outputs/autonomous_s7_20261014/sources/D_prepare.py",
    }.items():
        keep(source, Path("namespace_sources") / name)
    seed_review = json.loads((STUDY / "seed_review.json").read_text())
    if sha(OUT / "namespace_sources/D_seed_prepare.py.txt") != seed_review["seed_audit"]["helper_sha256"]:
        raise ValueError("archived namespace enumerator differs")
    freeze_json(OUT / "provenance.json", {
        "status": "prospective_preparation_not_released", "artifacts": artifacts,
        "simulated_lives": 0, "research_genome_lives": 4608, "cap_cpu_seconds": 3600,
        "total_artifact_bytes": sum(record["bytes"] for record in artifacts.values()),
    })
    print(json.dumps({"status": "prepared_not_released", "artifacts": len(artifacts), "simulated_lives": 0}))


if __name__ == "__main__":
    main()
