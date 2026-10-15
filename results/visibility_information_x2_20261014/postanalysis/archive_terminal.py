"""Append completed X2 and its separately reviewed census correction; never simulate."""
from __future__ import annotations

import importlib.util
import json
import os
from pathlib import Path
import subprocess
import sys

import numpy as np

AUDIT = Path(__file__).resolve().parent
ROOT = AUDIT.parents[1]
STUDY = ROOT / "outputs/autonomous_visibility_information_x2_20261014"
ARCHIVE = ROOT / "results/visibility_information_x2_20261014"
spec = importlib.util.spec_from_file_location("x2_archive", AUDIT / "archive.py")
A = importlib.util.module_from_spec(spec)
spec.loader.exec_module(A)


def main():
    budget = A.read(STUDY / "budget.json")
    ready = A.read(STUDY / "ready.json")
    clearance = A.read(STUDY / "terminal_process_clearance.json")
    if (budget["status"] != "complete" or budget["exit_code"] != 0 or budget["running"]
            or budget["queued"] or budget.get("cleanup_error") or budget["cpu_seconds"] != 1348.464197):
        raise ValueError("X2 is not the reviewed settled complete run")
    if (clearance["status"] != "cleared" or clearance["all_processes_exited"] is not True
            or clearance["budget_sha256"] != A.sha(STUDY / "budget.json")):
        raise ValueError("terminal resource clearance differs")
    for name, digest in ready["source_pins"].items():
        if A.sha(STUDY / name) != digest:
            raise ValueError("released source changed: " + name)
    corrected_manifest = STUDY / "postanalysis/manifest.json"
    if A.sha(corrected_manifest) != "911ebdb39b339ed67c6422d65fef52f7898372f05998914436f62e2cd3d8c386":
        raise ValueError("corrected analysis is not the frozen reviewed revision")
    review = A.read(STUDY / "postanalysis/raw_analysis_review.json")
    if review["status"] != "complete" or review["complete_study_lives"] != 13394:
        raise ValueError("corrected full analysis is incomplete")
    prelaunch = ARCHIVE / "prelaunch/manifest.json"
    prior_sha = A.sha(prelaunch)
    if prior_sha != "191be8b197a4892e4b55ec97c07f9ded23072751fc4495fe6e7d07ba02bd6094":
        raise ValueError("published prelaunch manifest changed")
    prior = A.read(prelaunch)
    plan = A.make_plan(ROOT, STUDY, AUDIT, "terminal")
    plan.update(status="complete_with_separate_reviewed_postanalysis_correction",
                scientific_lives_completed=13394, simulation_calls=13394,
                research_lives=13312, validation_lives=82, compiled_libraries=4,
                cpu_seconds=1348.464197, prior_failed_X_cpu_seconds=0.716548,
                combined_X_X2_cpu_seconds=1349.180745,
                scientific_outcomes_claimed=True, prelaunch_manifest_sha256=prior_sha,
                scientific_scope="fixed external-controller information payoff; no evolved behavior claim")

    def add(source, relative):
        plan["artifacts"][relative] = {"source": str(source), "sha256": A.sha(source),
                                      "bytes": source.stat().st_size, "origin": str(source.relative_to(ROOT))}

    for source in sorted((STUDY / "postanalysis").rglob("*")):
        if source.is_file() and "__pycache__" not in source.parts:
            add(source, str(source.relative_to(STUDY)))
    for name in ("monitor_console.log", "reanalysis_console.json"):
        add(STUDY / name, "operations/" + name)
    add(Path(__file__).resolve(), "postanalysis/archive_terminal.py")
    status_path = AUDIT / "ARCHIVE.md"
    status_path.write_text(
        "# Completed X2 archive\n\n"
        "X2 completed 13,312 research lives and 82 validation lives using 1,348.464197 CPU-seconds, "
        "including compilation and teardown. Including the earlier X initialization failure, the total is "
        "1,349.180745 CPU-seconds. All owned processes have exited.\n\n"
        "The released analyzer incorrectly counted starting cells as births and rejected the completed data. "
        "Its original code and failure record remain unchanged. The separately reviewed correction in "
        "[postanalysis/ERRATUM.md](postanalysis/ERRATUM.md) fixes the initial-cell census and removes two "
        "unsupported comparisons between disjoint counters. It changes no data, physics, scoring, or scientific criteria. "
        "It uses existing records and runs no new lives.\n\n"
        "The corrected [summary](postanalysis/working_results/summary.json) and "
        "[paired vectors](postanalysis/working_results/paired_vectors.npz) reproduce from this archive using "
        "`python postanalysis/analyze.py --study . --out NEW_OUTPUT_DIRECTORY`. These are measurements of "
        "fixed external controllers; they do not establish evolved behavior or a specific memory mechanism.\n\n"
        "[prelaunch/manifest.json](prelaunch/manifest.json) preserves the published preparation. "
        "The original README, PREREG, analyzer and every released source pin remain byte-identical. "
        "[manifest.json](manifest.json) covers the appended complete raw rows, validation, generated C sources, "
        "four libraries, operational records, and the separate corrected audit.\n"
    )
    add(status_path, "ARCHIVE.md")
    A.write_archive(ARCHIVE, plan)
    output = AUDIT / "public_terminal_reanalysis"
    command = [sys.executable, str(ARCHIVE / "postanalysis/analyze.py"), "--study", str(ARCHIVE), "--out", str(output)]
    env = dict(os.environ, PYTHONDONTWRITEBYTECODE="1", OPENBLAS_NUM_THREADS="1", OMP_NUM_THREADS="1")
    result = subprocess.run(command, env=env, capture_output=True, text=True, check=True)
    if A.read(output / "summary.json")["status"] != "complete":
        raise ValueError("public corrected analysis is incomplete")
    reference = STUDY / "postanalysis/working_results"
    if (output / "summary.json").read_bytes() != (reference / "summary.json").read_bytes():
        raise ValueError("public corrected summary differs")
    with np.load(output / "paired_vectors.npz", allow_pickle=False) as left, np.load(reference / "paired_vectors.npz", allow_pickle=False) as right:
        if set(left.files) != set(right.files):
            raise ValueError("public paired-vector keys differ")
        for name in left.files:
            if left[name].shape != right[name].shape or left[name].dtype != right[name].dtype or left[name].tobytes() != right[name].tobytes():
                raise ValueError("public paired-vector bytes differ: " + name)
        vectors = len(left.files)
    for name, item in plan["artifacts"].items():
        if A.sha(ARCHIVE / name) != item["sha256"]:
            raise ValueError("terminal manifest differs: " + name)
    for name, item in prior["artifacts"].items():
        if A.sha(ARCHIVE / name) != item["sha256"]:
            raise ValueError("published prepared bytes changed: " + name)
    if A.sha(prelaunch) != prior_sha:
        raise ValueError("prelaunch manifest changed")
    actual = {str(p.relative_to(ARCHIVE)) for p in ARCHIVE.rglob("*") if p.is_file()}
    expected = set(plan["artifacts"]) | {"manifest.json", "prelaunch/manifest.json"}
    if actual != expected:
        raise ValueError("archive manifest coverage differs: " + repr(sorted(actual ^ expected)))
    files = {str((ARCHIVE / name).relative_to(ROOT)) for name in expected}
    tracked = set(subprocess.run(["git", "ls-files", "-z", "--", str(ARCHIVE.relative_to(ROOT))], cwd=ROOT, text=True, capture_output=True, check=True).stdout.split("\0")) - {""}
    visible = set(subprocess.run(["git", "ls-files", "--others", "--exclude-standard", "-z", "--", str(ARCHIVE.relative_to(ROOT))], cwd=ROOT, text=True, capture_output=True, check=True).stdout.split("\0")) - {""}
    receipt = {"status": "verified_complete_portable_corrected_analysis", "protocol_sha256": A.PROTOCOL_SHA,
               "scientific_lives": 13394, "new_lives_by_archival_or_analysis": 0,
               "recorded_libraries": 4, "new_compilations_by_archival_or_analysis": 0,
               "cpu_seconds": 1348.464197, "combined_X_X2_cpu_seconds": 1349.180745,
               "copied_artifacts": len(plan["artifacts"]), "total_files": len(actual),
               "prepared_artifacts_preserved": len(prior["artifacts"]),
               "prelaunch_manifest_sha256": prior_sha, "terminal_manifest_sha256": A.sha(ARCHIVE / "manifest.json"),
               "released_source_pins_unchanged": len(ready["source_pins"]),
               "corrected_summary_byte_identical": True, "paired_arrays_byte_identical": vectors,
               "public_summary_sha256": A.sha(output / "summary.json"),
               "public_paired_vectors_sha256": A.sha(output / "paired_vectors.npz"),
               "exact_manifest_coverage": True, "git_tracked": len(tracked), "git_visible_untracked": len(visible),
               "git_force_add_required": sorted(files - tracked - visible),
               "all_ignored_paths": A.ignored_paths(ROOT, ARCHIVE, plan)}
    (AUDIT / "terminal_archive_verification.json").write_text(json.dumps(receipt, indent=2) + "\n")
    print(json.dumps({k: v for k, v in receipt.items() if k != "all_ignored_paths"}, indent=2))


if __name__ == "__main__":
    main()
