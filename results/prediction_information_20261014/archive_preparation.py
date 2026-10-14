"""Archive V preparation and fixed calibration without release or scientific simulation."""
from __future__ import annotations
import hashlib
import json
import shutil
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
STUDY = ROOT / "outputs/autonomous_prediction_information_20261014"
ARCHIVE = ROOT / "results/prediction_information_20261014"
PREVIOUS = {}


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def copy_checked(source, relative, digest=None):
    if digest is not None and sha(source) != digest:
        raise ValueError(f"source changed: {source}")
    destination = ARCHIVE / relative
    destination.parent.mkdir(parents=True, exist_ok=True)
    if destination.exists() and destination.read_bytes() != Path(source).read_bytes():
        previous = PREVIOUS.get("artifacts", {}).get(relative)
        if previous is None or sha(destination) != previous["sha256"]:
            raise ValueError(f"archive artifact already differs from its registered prior revision: {relative}")
    shutil.copyfile(source, destination)


def main():
    global PREVIOUS
    if (ARCHIVE / "provenance.json").exists():
        PREVIOUS = json.loads((ARCHIVE / "provenance.json").read_text())
    if any((STUDY / name).exists() for name in ("ready.json", "manifest.json", "budget.json", "rows")):
        raise ValueError("preparation packaging requires unreleased scientific study")
    protocol = json.loads((STUDY / "protocol.json").read_text())
    calibration = json.loads((STUDY / "calibration_budget.json").read_text())
    if calibration["status"] != "complete" or protocol["calibration_budget_sha256"] != sha(STUDY / "calibration_budget.json"):
        raise ValueError("calibration receipt changed")
    ARCHIVE.mkdir(parents=True, exist_ok=True)
    names = ("README.md", "PREREG.md", "protocol.json", "measure.py", "run_budgeted.py", "prepare.py", "test_prepared.py",
             "archive_preparation.py", "validate_preparation.py", "namespace_audit.json", "namespace_inventory.json",
             "calibration_plan.json", "calibration_budget.json", "calibration_complete.json", "library.json",
             "measurement.c", "measurement.so", "calibration.log", "preparation_validation.json", "preparation_tests.txt",
             "protocol_before_library_binding.json", "protocol_before_group_cleanup.json", "protocol_before_resume_cleanup_binding.json")
    for name in names:
        copy_checked(STUDY / name, name)
    for path in sorted((STUDY / "calibration").rglob("*")):
        if path.is_file():
            copy_checked(path, str(path.relative_to(STUDY)))
    originals = {}
    plan = json.loads((STUDY / "calibration_plan.json").read_text())
    pins = {**protocol["source_pins"], **protocol["harness_identity"]}
    boundary = json.loads((STUDY / "namespace_audit.json").read_text())["exclusive_upper_boundary"]
    pins[boundary["path"]] = boundary["sha256"]
    for relative, digest in pins.items():
        destination = "original/" + relative
        copy_checked(ROOT / relative, destination, digest)
        originals[relative] = destination
    calibration_originals = {}
    for relative, digest in plan["source_pins"].items():
        source = ROOT / relative
        if sha(source) != digest:
            source = STUDY / "calibration_sources" / source.name
        destination = "calibration_original/" + relative
        copy_checked(source, destination, digest)
        calibration_originals[relative] = destination
    files = {str(path.relative_to(ARCHIVE)): {"sha256": sha(path), "bytes": path.stat().st_size}
             for path in sorted(ARCHIVE.rglob("*")) if path.is_file() and path.name != "provenance.json"
             and "__pycache__" not in path.parts and ".pytest_cache" not in path.parts}
    report = {"format": 1, "status": "prepared_not_launched", "scientific_candidate_lives": 0,
              "planned_scientific_lives": 3584, "new_validation_lives": 4,
              "validation_cpu_seconds": calibration["cpu_seconds"], "cap_cpu_seconds_including_validation": 3600,
              "controller_source_changes": False, "audited_source_changes": False,
              "working_directory": str(STUDY.relative_to(ROOT)), "original_files": originals,
              "calibration_original_files": calibration_originals,
              "preparation_revision": "Bind calibrated evidence and harden whole-group cleanup, subreaper CPU accounting and exact parent identity. Exact calibration code retained; no new lives.",
              "interpretation": "Broad moving-target-model effect only; prediction-specific admission stays incomplete.",
              "artifacts": files}
    path = ARCHIVE / "provenance.json"
    raw = json.dumps(report, indent=2, allow_nan=False) + "\n"
    path.write_text(raw)
    print(json.dumps({"status": report["status"], "artifacts": len(files),
                      "bytes": sum(v["bytes"] for v in files.values()), "provenance_sha256": sha(path)}))


if __name__ == "__main__":
    main()
