"""Copy fixed F preparation/source inputs to the public archive; never simulate or release a run."""
from __future__ import annotations

import hashlib
import json
import shutil
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
STUDY = Path(__file__).resolve().parent
ARCHIVE = ROOT / "results/discrimination_20261013"


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def main():
    if any((STUDY / name).exists() for name in ("ready.json", "manifest.json", "measurement.so", "budget.json")):
        raise ValueError("this packaging step is restricted to unlaunched, unreleased preparation")
    protocol = json.loads((STUDY / "protocol.json").read_text())
    ARCHIVE.mkdir(parents=True, exist_ok=True)
    shutil.copyfile(STUDY / "protocol.json", ARCHIVE / "protocol.json")
    shutil.copyfile(STUDY / "prereg_draft.txt", ARCHIVE / "prereg.txt")
    (ARCHIVE / "preparation").mkdir(exist_ok=True)
    for name in ("measure.py", "run_budgeted.py", "test_prepared.py", "README.txt", "archive_preparation.py"):
        shutil.copyfile(STUDY / name, ARCHIVE / "preparation" / name)
    originals = {}
    for relative, digest in {**protocol["source_pins"], **protocol["harness_identity"]}.items():
        source = ROOT / relative
        if sha(source) != digest:
            raise ValueError(f"prepared source/input changed: {relative}")
        destination = ARCHIVE / "original" / relative
        destination.parent.mkdir(parents=True, exist_ok=True)
        shutil.copyfile(source, destination)
        originals[relative] = str(destination.relative_to(ARCHIVE))
    files = {str(path.relative_to(ARCHIVE)): {"sha256": sha(path), "bytes": path.stat().st_size}
             for path in sorted(ARCHIVE.rglob("*")) if path.is_file() and path.name != "provenance.json"
             and "__pycache__" not in path.parts and ".pytest_cache" not in path.parts}
    report = {"format": 1, "status": "prepared_not_launched", "scientific_candidate_lives": 0,
              "new_validation_lives": 0, "controller_source_changes": False, "audited_source_changes": False,
              "working_directory": str(STUDY.relative_to(ROOT)), "original_files": originals,
              "artifacts": files}
    (ARCHIVE / "provenance.json").write_text(json.dumps(report, indent=2) + "\n")
    print(json.dumps({"status": report["status"], "artifacts": len(files),
                      "bytes": sum(value["bytes"] for value in files.values())}))


if __name__ == "__main__":
    main()
