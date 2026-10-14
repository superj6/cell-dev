"""Hash and archive G preparation without creating readiness or launching a process."""
from __future__ import annotations

import json
import shutil
from pathlib import Path

from run_budgeted import HELPERS, ROOT, STUDY, check_protocol, save, sha

OUT = ROOT / "results/structural_20261013"


def main():
    protocol = check_protocol()
    ready = {
        "monitor_sha256": sha(STUDY / "run_budgeted.py"),
        "measurement_sha256": sha(STUDY / "measure.py"),
        "protocol_sha256": sha(STUDY / "protocol.json"),
        "helpers": {name: sha(ROOT / "scripts" / name) for name in HELPERS},
        "status": "template_not_released",
    }
    save(STUDY / "ready.template.json", ready)
    files = {}

    def keep(source, relative):
        path = OUT / relative
        path.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(source, path)
        files[str(relative)] = {"sha256": sha(path), "bytes": path.stat().st_size}

    for name in (
        "README.md", "PREREG.md", "prepare.py", "run_budgeted.py", "measure.py", "prepare_archive.py",
        "test_prepared.py", "test_monitor_measure.py", "protocol.json", "seed_audit.json",
        "ready.template.json", "validation.json",
    ):
        keep(STUDY / name, name)
    for folder in ("configs", "inputs"):
        for path in sorted((STUDY / folder).iterdir()):
            if path.is_file():
                keep(path, path.relative_to(STUDY))
    for name in HELPERS:
        keep(ROOT / "scripts" / name, Path("sources") / name)
    for name in ("analyze.py", "audit_search.py", "test_analyze.py", "test_audit_search.py", "analysis_validation.json"):
        if (STUDY / name).exists():
            keep(STUDY / name, name)
    analysis_helper = STUDY / "sources/continuation_analyze.py"
    if analysis_helper.exists():
        keep(analysis_helper, "sources/continuation_analyze.py")
    dependency = ROOT / protocol["D_study"]
    for name in protocol["D_pins"]:
        keep(dependency / name, Path("dependency") / name)
    baseline = json.loads((dependency / "protocol.json").read_text())
    for value in baseline["configs"].values():
        keep(ROOT / value["path"], Path("dependency/configs") / Path(value["path"]).name)
    save(OUT / "provenance.json", {
        "status": "prepared_not_released", "simulated_lives_by_preparation": 0,
        "numerical_identity": protocol["expected_numerical_identity"],
        "artifacts": files,
    })
    print(json.dumps({"status": "prepared_not_released", "out": str(OUT), "hashed_artifacts": len(files),
                      "ready_json_created": False, "simulated_lives": 0}, indent=2))


if __name__ == "__main__":
    main()
