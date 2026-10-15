"""Append settled Y evidence; default is a no-write, no-outcome-read description.

The published preparation and released source are immutable. --write requires
root terminal process clearance and, for a complete run, the full frozen analysis.
This helper performs no simulation, compilation, mutation, release or Git action.
"""
from __future__ import annotations

import argparse
import importlib.util
import json
import os
from pathlib import Path
import subprocess
import sys

AUDIT = Path(__file__).resolve().parent
ROOT = AUDIT.parents[1]
STUDY = ROOT / "outputs/autonomous_visibility_gradient_20261014"
ARCHIVE = ROOT / "results/visibility_gradient_20261014"
PRELAUNCH_SHA = "691aa4b84fa21203ae7271c12c033a53b9c7612218fa3c6b3ebb8040c94f4074"
READY_SHA = "8f04fdb3c1d41a2c5f68b89cc6b981e782ad7b3e1122ebd6e41d7e004755d62b"
HELPER_SHA = "c6f26517a16f508e2cb41e99bf5cf8c09ed4a29c4d5a8c849b4bd0bdcd41a56d"
CORRECTED_ANALYZER_SHA = "08b3bebe8f05a5d758bee3306ebaae6b6086a204e47ddbc556947b6bd32486b7"
CORRECTION_REVIEW_SHA = "915dee215115d3fb26d263d0ad90edd9df1c678e8f9ec992e4c0131c650c4f66"
POSTANALYSIS_MANIFEST_SHA = "f5eba1bc590ead918bae84dd9230b79f0571596159d0d40473c7bb34e1dd1306"
RAW_REVIEW_SHA = "a832a1edc3a4c134d7d38e7b51c86114b9c9e6c0f00003c755838a0ffed7cb5c"


def run():
    import numpy as np

    spec = importlib.util.spec_from_file_location("reviewed_y_archive", AUDIT / "archive.py")
    a = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(a)
    if a.sha(AUDIT / "archive.py") != HELPER_SHA:
        raise ValueError("published archive helper changed")
    if a.sha(ARCHIVE / "prelaunch/manifest.json") != PRELAUNCH_SHA or a.sha(STUDY / "ready.json") != READY_SHA:
        raise ValueError("published preparation or released identity changed")
    budget, ready = a.read(STUDY / "budget.json"), a.read(STUDY / "ready.json")
    clearance = a.read(STUDY / "terminal_process_clearance.json")
    if (budget.get("status") not in ("complete", "incomplete", "monitor_failed")
            or budget.get("running") or budget.get("queued") or budget.get("cleanup_error")):
        raise ValueError("run is not cleanly terminal")
    if (clearance.get("status") != "cleared" or clearance.get("all_processes_exited") is not True
            or clearance.get("budget_sha256") != a.sha(STUDY / "budget.json")):
        raise ValueError("root terminal clearance does not bind the settled budget")
    expected_processes = {(p["pid"], p["start_ticks"]) for p in budget["process_identities"]}
    if (expected_processes != {(p["pid"], p["start_ticks"]) for p in clearance["processes"]}
            or set(clearance["process_groups"]) != set(budget["owned_process_groups"])):
        raise ValueError("terminal clearance omits an owned process identity/group")
    for name, digest in ready["source_pins"].items():
        if a.sha(STUDY / name) != digest:
            raise ValueError("released source changed: " + name)
    complete = budget["status"] == "complete"
    if a.sha(STUDY / "postanalysis/manifest.json") != POSTANALYSIS_MANIFEST_SHA:
        raise ValueError("frozen postanalysis manifest changed")
    correction = a.read(STUDY / "postanalysis/manifest.json")
    for name, digest in correction["files"].items():
        if a.sha(a.inside(STUDY / "postanalysis", name)) != digest:
            raise ValueError("frozen postanalysis artifact changed: " + name)
    if (a.sha(STUDY / "postanalysis/analyze.py") != CORRECTED_ANALYZER_SHA
            or a.sha(STUDY / "postanalysis/independent_identity_review.json") != CORRECTION_REVIEW_SHA
            or a.sha(STUDY / "postanalysis/offline_accounting.py") != ready["source_pins"]["analysis/offline_accounting.py"]):
        raise ValueError("separate reviewed receipt-schema correction differs")
    if complete:
        if a.sha(STUDY / "terminal_review/raw_analysis_review.json") != RAW_REVIEW_SHA:
            raise ValueError("complete independent raw-analysis review changed")
        for name, digest in a.read(STUDY / "terminal_review/raw_analysis_review.json")["input_and_output_pins"].items():
            if a.sha(a.inside(STUDY, name)) != digest:
                raise ValueError("reviewed raw-analysis input/output changed: " + name)
        result = a.read(STUDY / "analysis_result/summary.json")
        if (budget.get("exit_code") != 0 or result.get("status") != "complete"
                or result.get("protocol_sha256") != a.PROTOCOL_SHA
                or (result.get("research_lives"), result.get("validation_lives"), result.get("total_lives")) != (6208, 10, 6218)
                or result["resources"]["total_cpu_seconds"] != budget["cpu_seconds"]):
            raise ValueError("full frozen analysis is absent or disagrees with terminal scope")
    prior = a.read(ARCHIVE / "prelaunch/manifest.json")
    plan = a.make_plan(ROOT, STUDY, AUDIT, "terminal")
    plan.update(status="complete_with_separate_reviewed_receipt_schema_correction" if complete else "incomplete_terminal_attempt",
                scientific_lives_completed=6218 if complete else None,
                research_lives=6208 if complete else None, validation_lives=10 if complete else None,
                compiled_libraries=len(list((STUDY / "build-cache").rglob("*.so"))),
                cpu_seconds=budget["cpu_seconds"], scientific_outcomes_claimed=complete,
                prelaunch_manifest_sha256=PRELAUNCH_SHA,
                corrected_analyzer_sha256=CORRECTED_ANALYZER_SHA,
                postanalysis_manifest_sha256=POSTANALYSIS_MANIFEST_SHA,
                scientific_scope="one-step ordinary-mutation diagnostic; no memory-mechanism or evolution-continuation claim")

    def add(path, relative):
        item = {"source": str(path), "sha256": a.sha(path), "bytes": path.stat().st_size,
                "origin": str(path.relative_to(ROOT))}
        if relative in plan["artifacts"] and plan["artifacts"][relative]["sha256"] != item["sha256"]:
            raise ValueError("terminal destination collision: " + relative)
        plan["artifacts"][relative] = item

    for folder in ("postanalysis", "terminal_review", "figures"):
        for path in sorted((STUDY / folder).rglob("*")):
            if path.is_file() and not any(x in a.SKIP for x in path.relative_to(STUDY).parts):
                add(path, str(path.relative_to(STUDY)))
    if (STUDY / "figures").is_dir() and (AUDIT / "plot_results.py").is_file():
        add(AUDIT / "plot_results.py", "figures/plot_results.py")
    for name in ("monitor_console.log", "reanalysis_console.json"):
        if (STUDY / name).is_file():
            add(STUDY / name, "operations/" + name)
    add(Path(__file__).resolve(), "terminal_review/archive_terminal.py")
    status = AUDIT / "ARCHIVE.md"
    status.write_text(
        "# Y terminal archive\n\n"
        + (f"Y completed 6,208 research lives and 10 validation lives using {budget['cpu_seconds']:.6f} CPU-seconds, "
           "including startup, compilation and cleanup. The eight calibration lives and two ABI3 compatibility goldens are included.\n\n"
           "The [full summary](analysis_result/summary.json) and [paired vectors](analysis_result/paired_vectors.npz) "
           "reproduce with `python postanalysis/analyze.py --study . --out NEW_DIRECTORY`. Each selected mutant is compared "
           "with its own evolved founder on 512 fresh paired seeds, after a separate 32-life screen.\n\n"
           if complete else
           f"This first attempt ended incomplete after {budget['cpu_seconds']:.6f} CPU-seconds. Preserved partial records "
           "do not establish a scientific outcome; the frozen analyzer must report incomplete. Exact total interrupted life calls are not inferred from saved rows.\n\n")
        + "The original frozen analyzer rejected the actual process receipt before producing outcomes: it required a session ID "
        "that the monitor never recorded. Its code and failure record remain intact. The separately reviewed reader in "
        "[postanalysis/](postanalysis/) checks the four recorded identity fields and retains parent/group, source, phase, resource "
        "and scientific checks. It makes no claim of archived session-ID evidence and changes no simulation or scientific criterion.\n\n"
        "All owned processes have exited. [prelaunch/manifest.json](prelaunch/manifest.json) preserves the published preparation. "
        "Every prepared artifact and released source pin remains unchanged. [manifest.json](manifest.json) covers the appended "
        "raw rows, binaries, phase handoffs, resource records, final analysis and reviews.\n\n"
        "This is a local mutation-gradient diagnostic in the approved irregular-blink world. Fitness and dark-capture effects "
        "do not by themselves identify memory, prediction or a new algorithm. Archiving and offline analysis run no new lives.\n")
    add(status, "ARCHIVE.md")
    for name, item in prior["artifacts"].items():
        if (plan["artifacts"].get(name, {}).get("sha256") != item["sha256"]
                or a.sha(ARCHIVE / name) != item["sha256"]):
            raise ValueError("published prepared artifact changed or omitted: " + name)
    a.write_archive(ARCHIVE, plan)
    output = AUDIT / "public_terminal_reanalysis"
    command = [sys.executable, str(ARCHIVE / "postanalysis/analyze.py"), "--study", str(ARCHIVE)]
    if complete:
        command += ["--out", str(output)]
    env = dict(os.environ, PYTHONDONTWRITEBYTECODE="1", OPENBLAS_NUM_THREADS="1", OMP_NUM_THREADS="1")
    execution = subprocess.run(command, cwd=ROOT.parent, env=env, capture_output=True, text=True, check=True)
    summary = json.loads(execution.stdout)
    original = subprocess.run([sys.executable, str(ARCHIVE / "analysis/analyze.py"), "--study", str(ARCHIVE)],
                              cwd=ROOT.parent, env=env, capture_output=True, text=True, check=True)
    original_status = json.loads(original.stdout)
    if (original_status.get("status") != "incomplete" or original_status.get("scientific_outcomes_emitted") is not False
            or original_status.get("error") != "ValueError: incomplete process identity"):
        raise ValueError("original frozen analyzer no longer reproduces the preserved failure")
    arrays = 0
    if complete:
        reference = STUDY / "analysis_result"
        if summary["status"] != "complete" or (output / "summary.json").read_bytes() != (reference / "summary.json").read_bytes():
            raise ValueError("portable full summary differs")
        with np.load(output / "paired_vectors.npz", allow_pickle=False) as left, np.load(reference / "paired_vectors.npz", allow_pickle=False) as right:
            if set(left.files) != set(right.files):
                raise ValueError("portable paired array names differ")
            for name in left.files:
                if left[name].shape != right[name].shape or left[name].dtype != right[name].dtype or left[name].tobytes() != right[name].tobytes():
                    raise ValueError("portable paired array bytes differ: " + name)
            arrays = len(left.files)
    elif summary.get("status") != "incomplete" or summary.get("scientific_outcomes_emitted") is not False:
        raise ValueError("incomplete run emitted scientific results")
    expected = set(plan["artifacts"]) | {"manifest.json", "prelaunch/manifest.json"}
    actual = {str(p.relative_to(ARCHIVE)) for p in ARCHIVE.rglob("*") if p.is_file()}
    if actual != expected or a.sha(ARCHIVE / "prelaunch/manifest.json") != PRELAUNCH_SHA:
        raise ValueError("manifest coverage or published preparation changed")
    for name, item in plan["artifacts"].items():
        if a.sha(ARCHIVE / name) != item["sha256"]:
            raise ValueError("terminal copied bytes differ: " + name)
    files = {str((ARCHIVE / name).relative_to(ROOT)) for name in expected}
    def git_paths(*args):
        r = subprocess.run(["git", "ls-files", *args, "-z", "--", str(ARCHIVE.relative_to(ROOT))],
                           cwd=ROOT, text=True, capture_output=True, check=True)
        return set(r.stdout.split("\0")) - {""}
    tracked, visible = git_paths(), git_paths("--others", "--exclude-standard")
    receipt = {"status": "verified_complete_portable_analysis" if complete else "verified_incomplete_terminal_archive",
               "protocol_sha256": a.PROTOCOL_SHA, "prelaunch_manifest_sha256": PRELAUNCH_SHA,
               "terminal_manifest_sha256": a.sha(ARCHIVE / "manifest.json"), "copied_artifacts": len(plan["artifacts"]),
               "total_files": len(actual), "prepared_artifacts_preserved": len(prior["artifacts"]),
               "released_source_pins_unchanged": len(ready["source_pins"]), "cpu_seconds": budget["cpu_seconds"],
               "new_lives": 0, "new_compilations": 0, "public_summary_byte_identical": complete,
               "corrected_analyzer_sha256": CORRECTED_ANALYZER_SHA, "original_frozen_failure_reproduced": True,
               "postanalysis_manifest_sha256": POSTANALYSIS_MANIFEST_SHA,
               "paired_arrays_byte_identical": arrays, "exact_manifest_coverage": True,
               "git_tracked": len(tracked), "git_visible_untracked": len(visible),
               "git_force_add_required": sorted(files - tracked - visible)}
    (AUDIT / "terminal_archive_verification.json").write_text(json.dumps(receipt, indent=2) + "\n")
    print(json.dumps(receipt, indent=2))


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--write", action="store_true")
    args = parser.parse_args()
    if not args.write:
        print(json.dumps({"status": "dry_run_no_outcomes_read", "prelaunch_manifest_sha256": PRELAUNCH_SHA,
                          "requires": "settled budget, root process clearance, unchanged release and complete frozen analysis if run completed",
                          "writes": False, "simulation_calls": 0, "compilation_calls": 0}))
        return
    run()


if __name__ == "__main__":
    main()
