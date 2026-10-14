"""Archive the failed X first attempt, without importing any simulation code.

This post-failure wrapper leaves all released sources and preparation bytes intact.
It uses the previously reviewed archive helper, adding exact zero-work evidence.
"""
from __future__ import annotations

from datetime import datetime, timezone
import importlib.util
import json
import os
from pathlib import Path
import subprocess
import sys

AUDIT = Path(__file__).resolve().parent
ROOT = AUDIT.parents[1]
STUDY = ROOT / "outputs/autonomous_visibility_information_20261014"
ARCHIVE = ROOT / "results/visibility_information_20261014"
spec = importlib.util.spec_from_file_location("x_archiver", AUDIT / "archive.py")
helper = importlib.util.module_from_spec(spec)
spec.loader.exec_module(helper)


def save_once(path, value):
    text = json.dumps(value, indent=2, allow_nan=False) + "\n"
    if path.exists():
        if path.read_text() != text:
            raise ValueError("immutable terminal receipt changed: " + str(path))
    else:
        path.write_text(text)


def identity(pid):
    try:
        text = Path(f"/proc/{pid}/stat").read_text()
    except FileNotFoundError:
        return None
    fields = text[text.rindex(")") + 2:].split()
    return dict(pid=pid, ppid=int(fields[1]), pgid=int(fields[2]),
                start_ticks=int(fields[19]), state=fields[0])


def main():
    budget = helper.read(STUDY / "budget.json")
    ready = helper.read(STUDY / "ready.json")
    if (budget["status"] != "incomplete" or budget["reason"] != "job_failed"
            or budget["phase"] != "validation" or budget["cpu_seconds"] != 0.716548
            or budget.get("running") or budget.get("queued") or budget.get("cleanup_error")):
        raise ValueError("unexpected terminal failure")
    identities = budget["process_identities"]
    if {(r["pid"], r["start_ticks"]) for r in identities} != {(790102, 2546567), (790104, 2546597)}:
        raise ValueError("unexpected process identities")
    current = [identity(row["pid"]) for row in identities]
    members = []
    for entry in Path("/proc").iterdir():
        if entry.name.isdigit():
            row = identity(int(entry.name))
            if row and row["pgid"] in budget["owned_process_groups"]:
                members.append(row)
    if any(current) or members:
        raise ValueError("recorded process or owned process group remains")
    absent = ["validation", "validation_budget.json", "rows", "build-cache", "kernel-cache"]
    if any((STUDY / name).exists() for name in absent) or list(STUDY.rglob("*.so")) or list(STUDY.rglob("*.npz")):
        raise ValueError("unexpected compiled or simulation evidence")
    log = (STUDY / "logs/validation.log").read_text()
    if "value=require_release()" not in log or "ValueError: numerical/compiler/runtime identity changed" not in log:
        raise ValueError("unexpected failure order")
    for name, digest in ready["source_pins"].items():
        if helper.sha(STUDY / name) != digest:
            raise ValueError("frozen release input changed: " + name)
    review = AUDIT / "x_failure_review.json"
    if helper.sha(review) != "19dc91f37cd802da106ab8961d05ee778902695ace64334a6547103f462024c3":
        raise ValueError("independent failure review changed")
    clearance_path = STUDY / "terminal_process_clearance.json"
    if not clearance_path.exists():
        save_once(clearance_path, {
            "status": "cleared", "checked_at_utc": datetime.now(timezone.utc).isoformat(),
            "method": "read-only Linux /proc identity and full process-group scan",
            "budget_sha256": helper.sha(STUDY / "budget.json"),
            "recorded_process_identities": identities, "current_identities": current,
            "owned_process_groups": budget["owned_process_groups"], "group_members": members,
            "all_recorded_processes_exited": True, "all_owned_groups_empty": True,
            "compilation_calls_by_review": 0, "simulation_calls_by_review": 0,
        })
    failure = {
        "status": "terminal_incomplete_before_compilation_or_simulation",
        "reason": "numerical/compiler/runtime identity changed",
        "cpu_seconds": budget["cpu_seconds"], "simulation_calls": 0,
        "validation_lives": 0, "research_lives": 0, "kernel_libraries_compiled": 0,
        "scientific_outcomes_available": False,
        "planned_validation_lives": 82, "planned_research_lives": 13312,
        "failure_order": "require_release numerical identity check raised before validation directory creation, compilation, and any life call",
        "absent_paths": absent,
        "evidence_pins": {name: helper.sha(STUDY / name) for name in (
            "protocol.json", "ready.json", "attempt.json", "budget.json", "logs/validation.log",
            "validate.py", "common.py", "numerical.py", "terminal_process_clearance.json")},
        "independent_failure_review_sha256": helper.sha(review),
        "historical_preparation_counts_remain_zero": True,
        "retry_or_source_change_performed_by_archival": False,
    }
    save_once(STUDY / "terminal_failure.json", failure)
    prospective = ARCHIVE / "prelaunch/manifest.json"
    prior_sha = helper.sha(prospective)
    prior = helper.read(prospective)
    if prior_sha != "3fd09095e9023abdc3a06cd24133f503f288a50c55ab63d6d69734f186709cc7":
        raise ValueError("published preparation manifest changed")
    plan = helper.make_plan(ROOT, STUDY, AUDIT, "terminal")
    plan.update(status=failure["status"], scientific_lives_completed=0,
                simulation_calls=0, validation_lives=0, research_lives=0,
                compiled_libraries=0, cpu_seconds=budget["cpu_seconds"],
                prelaunch_manifest_sha256=prior_sha)

    def add(source, relative):
        plan["artifacts"][relative] = {"source": str(source), "sha256": helper.sha(source),
                                      "bytes": source.stat().st_size, "origin": str(source.relative_to(ROOT))}

    add(STUDY / "terminal_failure.json", "operations/terminal_failure.json")
    add(STUDY / "monitor_console.log", "operations/monitor_console.log")
    add(review, "postfailure/x_failure_review.json")
    add(Path(__file__).resolve(), "postfailure/archive_terminal.py")
    helper.write_archive(ARCHIVE, plan)
    env = dict(os.environ, PYTHONDONTWRITEBYTECODE="1", OMP_NUM_THREADS="1", OPENBLAS_NUM_THREADS="1")
    command = [sys.executable, str(ARCHIVE / "analysis/analyze.py"), "--study", str(ARCHIVE)]
    result = subprocess.run(command, env=env, capture_output=True, text=True, check=True)
    analysis = json.loads(result.stdout)
    if analysis["status"] != "incomplete" or analysis["scientific_outcomes_emitted"] is not False:
        raise ValueError("public analysis did not fail closed")
    save_once(STUDY / "terminal_reanalysis.json", analysis)
    add(STUDY / "terminal_reanalysis.json", "operations/terminal_reanalysis.json")
    helper.write_archive(ARCHIVE, plan)
    if helper.sha(prospective) != prior_sha:
        raise ValueError("preparation manifest changed during archival")
    for name, item in prior["artifacts"].items():
        if helper.sha(ARCHIVE / name) != item["sha256"]:
            raise ValueError("prepared bytes changed: " + name)
    for name, item in plan["artifacts"].items():
        if helper.sha(ARCHIVE / name) != item["sha256"]:
            raise ValueError("terminal manifest pin differs: " + name)
    actual = {str(path.relative_to(ARCHIVE)) for path in ARCHIVE.rglob("*") if path.is_file()}
    expected = set(plan["artifacts"]) | {"manifest.json", "prelaunch/manifest.json"}
    if actual != expected:
        raise ValueError("archive manifest coverage differs: " + repr(sorted(actual ^ expected)))
    verification = {
        "status": "verified", "phase": "terminal", "scientific_status": "incomplete",
        "actual_simulation_calls": 0, "actual_compiled_libraries": 0,
        "attempt_cpu_seconds": budget["cpu_seconds"],
        "copied_artifacts": len(plan["artifacts"]), "total_files": len(actual),
        "prepared_artifacts_preserved": len(prior["artifacts"]),
        "prelaunch_manifest_sha256": prior_sha, "terminal_manifest_sha256": helper.sha(ARCHIVE / "manifest.json"),
        "ready_sha256_unchanged": helper.sha(STUDY / "ready.json"),
        "process_clearance_sha256": helper.sha(clearance_path),
        "public_analysis": analysis, "exact_manifest_coverage": True,
        "force_add_paths": helper.ignored_paths(ROOT, ARCHIVE, plan),
    }
    save_once(AUDIT / "terminal_archive_verification.json", verification)
    print(json.dumps(verification, indent=2))


if __name__ == "__main__":
    main()
