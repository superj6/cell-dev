"""Preserve Q's zero-measurement dependency failure; no simulation or endpoint analysis."""
from __future__ import annotations

import argparse
import hashlib
import json
import math
import shutil
import subprocess
from pathlib import Path

ROOT = next((p for p in Path(__file__).resolve().parents if (p / "src/genome.py").exists()), None)


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def read(path):
    return json.loads(Path(path).read_text())


def save(path, value):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, indent=2, allow_nan=False) + "\n")


def verify(folder, records):
    for relative, record in records.items():
        path = folder / relative
        if sha(path) != record["sha256"] or path.stat().st_size != record["bytes"]:
            raise ValueError("preserved artifact differs: " + str(path))


def check(folder):
    manifest = read(folder / "provenance.json")
    assert manifest["status"] == "dependency_failed_before_measurement"
    verify(folder, manifest["artifacts"])
    verify(folder.parent, read(folder / "preserved_files.json")["artifacts"])
    assert read(folder / "summary.json")["research_lives"] == 0
    return manifest


def archive():
    work = ROOT / "outputs/autonomous_s7_hidden_20261014"
    prior = ROOT / "outputs/autonomous_next_step_20261014"
    public = ROOT / "results/s7_hidden_20261014"
    target = public / "operational_status"
    budgets = {"Q": read(work / "budget.json"), "P": read(prior / "budget.json")}
    # Terminal resource receipts are the first reads. No scientific outcome is ever opened.
    for label, cap in (("Q", 3600), ("P", 14400)):
        value = budgets[label]
        assert value["status"] in ("monitor_failed", "incomplete")
        assert not value["running"] and not value["queued"]
        assert value["cap_cpu_seconds"] == cap and math.isfinite(value["cpu_seconds"])
        assert 0 <= value["cpu_seconds"] < cap
    assert budgets["Q"]["status"] == "monitor_failed" and budgets["Q"]["error"] == "ValueError"
    assert budgets["P"]["status"] == "incomplete" and budgets["P"]["reason"] == "cpu_budget_exhausted"
    assert budgets["P"]["exit_code"] == 1
    absent = {name: not (work / name).exists() for name in ("measurement", "run.log")}
    assert all(absent.values())
    assert not target.exists(), "operational archive cannot overwrite an existing bundle"
    host_dir = ROOT / "outputs/wrapup_review_20261014"
    host, exits = read(host_dir / "host_exit_review.json"), read(host_dir / "session_exits.json")
    assert host["status"] == "all_released_monitors_and_workers_exited"
    assert not host["remaining_owned_or_research_processes"]
    assert host["session_exits_sha256"] == sha(host_dir / "session_exits.json")
    assert exits["Q"]["exit_code"] == 1
    assert "dependency stopped abnormally; inspect before Q launch" in exits["Q"]["output"]
    for label, name, folder in (("Q", "s7_hidden", work), ("P", "next_step", prior)):
        assert host["budgets"][name]["sha256"] == sha(folder / "budget.json")
        assert host["budgets"][name]["record"] == budgets[label]
    ready, protocol = read(work / "ready.json"), read(work / "protocol.json")
    assert ready == budgets["Q"]["ready"] and ready["dependencies"] == protocol["dependencies"]
    assert set(ready["files"]) == {
        "protocol.json", "prepare.py", "measure.py", "run_budgeted.py", "test_measure.py", "PREREG.md"}
    for name, expected in ready["files"].items():
        assert sha(work / name) == expected
    for name, expected in ready["dependencies"]["outputs/autonomous_next_step_20261014"].items():
        assert sha(prior / name) == expected
    for name, expected in protocol["source_identity"].items():
        assert sha(ROOT / name) == expected
    old = read(public / "provenance.json")
    offline = public / "offline_analysis_preparation"
    old_offline = read(offline / "provenance.json")
    assert len(old["artifacts"]) == 103 and len(old_offline["artifacts"]) == 10
    assert old["status"] == "prospective_preparation_not_released"
    verify(public, old["artifacts"])
    verify(offline, old_offline["artifacts"])
    preserved = dict(old["artifacts"])
    preserved.update({"offline_analysis_preparation/" + name: value
                      for name, value in old_offline["artifacts"].items()})
    for path in (public / "provenance.json", offline / "provenance.json"):
        preserved[str(path.relative_to(public))] = {"sha256": sha(path), "bytes": path.stat().st_size}
    assert len(preserved) == 115
    for relative, record in preserved.items():
        name = str((public / relative).relative_to(ROOT))
        blob = subprocess.check_output(["git", "show", ":" + name], cwd=ROOT)
        assert hashlib.sha256(blob).hexdigest() == record["sha256"]
    files = {"Q/" + name: work / name for name in (*ready["files"], "ready.json", "budget.json")}
    files.update({"P/" + name: prior / name for name in ("protocol.json", "run_budgeted.py", "budget.json")})
    files.update({"host/" + name: host_dir / name for name in ("host_exit_review.json", "session_exits.json")})
    files["archive_operational.py"] = Path(__file__)
    files["review/analysis_review_structural.json"] = Path(__file__).with_name("analysis_review_structural.json")
    sources = {name: sha(path) for name, path in files.items()}
    for relative, original in files.items():
        destination = target / relative
        destination.parent.mkdir(parents=True, exist_ok=True)
        shutil.copyfile(original, destination)
        assert sha(destination) == sources[relative]
    save(target / "preserved_files.json", {"status": "passed", "git_index_blobs_verified": 115,
         "preparation_artifacts": 103, "offline_artifacts": 10, "artifacts": preserved})
    summary = {"status": "dependency_failed_before_measurement", "resource_status": "monitor_failed",
               "monitor_error": "ValueError", "cause": "P stopped incomplete at its fixed CPU budget",
               "planned_research_lives": 6144, "research_lives": 0, "validation_lives": 0,
               "measurement_worker_started": False, "absent_working_artifacts": absent,
               "Q_monitored_cpu_seconds": budgets["Q"]["cpu_seconds"],
               "Q_cap_cpu_seconds": 3600, "P_monitored_cpu_seconds": budgets["P"]["cpu_seconds"],
               "scientific_outcome": None, "archival_simulated_lives": 0,
               "interpretation": "Q produced no biological measurement. No message-dependence conclusion follows.",
               "limits": ["The planned 6,144 lives were not executed.",
                          "Waiting/monitor CPU is operational overhead, not research simulation CPU.",
                          "No restart, rescue, cap extension or new release was performed by archival."]}
    save(target / "summary.json", summary)
    (target / "README.md").write_text(
        "# Q stopped before measurement\n\n"
        "Q's registered dependency, P, stopped incomplete at its fixed CPU budget. Q's monitor then exited "
        "with `monitor_failed` / `ValueError`, before opening its worker log or starting measurement. "
        "**Q ran zero research or validation lives and has no scientific outcome.**\n\n"
        f"Q used {budgets['Q']['cpu_seconds']:.6f} CPU-seconds of waiting/monitor overhead under its "
        "3,600-second cap. The planned 6,144 research lives were not executed. P's terminal receipt records "
        f"{budgets['P']['cpu_seconds']:.6f} CPU-seconds and an incomplete confirmation. "
        "No partial P endpoint comparison is made here.\n\n"
        "Exact terminal budgets, release pins, monitor sources and root host/session exit evidence are retained. "
        "Both working `measurement/` and `run.log` were absent. The original 103 preparation artifacts, their "
        "manifest, and the ten-file offline-analysis bundle plus its manifest remain byte-for-byte unchanged. "
        "All 115 original files also matched Git index blobs at archival time.\n\n"
        "This directory has a separate manifest. It changes no prepared scientific source or readiness marker. "
        "No simulation, restart, rescue, budget extension or new release was performed.\n\n"
        "Verify from the repository root:\n\n```sh\n"
        ".venv/bin/python results/s7_hidden_20261014/operational_status/archive_operational.py "
        "--check results/s7_hidden_20261014/operational_status\n```\n")
    verify(public, preserved)
    assert all(not (work / name).exists() for name in absent)
    for name, original in files.items():
        assert sha(original) == sources[name]
    artifacts = {str(path.relative_to(target)): {"sha256": sha(path), "bytes": path.stat().st_size}
                 for path in sorted(target.rglob("*")) if path.is_file()}
    save(target / "provenance.json", {"status": "dependency_failed_before_measurement", "artifacts": artifacts,
         "research_lives": 0, "archival_simulated_lives": 0,
         "original_preparation_provenance_sha256": sha(public / "provenance.json"),
         "offline_analysis_provenance_sha256": sha(offline / "provenance.json")})
    check(target)
    return summary


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    group = parser.add_mutually_exclusive_group()
    group.add_argument("--archive", action="store_true")
    group.add_argument("--check", type=Path)
    args = parser.parse_args()
    if args.archive:
        print(json.dumps(archive(), indent=2))
    elif args.check:
        result = check(args.check)
        print(json.dumps({"status": result["status"], "artifacts_checked": len(result["artifacts"])}))
    else:
        print(json.dumps({"status": "dry_run", "simulated_lives": 0}))
