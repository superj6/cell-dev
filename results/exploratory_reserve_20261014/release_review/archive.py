"""Package AH without running it. Default dry run; copied scientific evidence is immutable.

Preparation contains zero compiled libraries/lives. Terminal packaging only appends
operational/raw artifacts; prelaunch/manifest.json preserves the published preparation.
"""
from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path
import shutil
import subprocess

ROOT = Path(__file__).resolve().parents[2]
STUDY = ROOT / "outputs/autonomous_exploratory_reserve_20261014"
AUDIT = Path(__file__).resolve().parent
ARCHIVE = ROOT / "results/exploratory_reserve_20261014"
PROTOCOL_SHA = "0a9e505969ed11cd8f240f9404bbff2adf9a91d91d5387252fd9595874c61be4"
SKIP = {"__pycache__", ".pytest_cache", ".git"}
OPERATIONS = ("ready.json", "attempt.json", "budget.json", "validation_budget.json", "resource_clearance.json",
              "terminal_process_clearance.json", "seed_registration.json")


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def read(path):
    return json.loads(Path(path).read_text())


def inside(base, name):
    if not isinstance(name, str) or Path(name).is_absolute() or ".." in Path(name).parts:
        raise ValueError("unsafe archive path")
    path = (base / name).resolve()
    if not path.is_relative_to(base.resolve()):
        raise ValueError("archive path escapes declared root")
    return path


def make_plan(root, study, audit, phase):
    protocol = read(study / "protocol.json")
    if sha(study / "protocol.json") != PROTOCOL_SHA:
        raise ValueError("protocol is not the reviewed AH registration")
    if phase not in ("preparation", "terminal"):
        raise ValueError("invalid archive phase")
    artifacts = {}

    def add(source, relative, digest=None, origin=None):
        inside(Path("/archive"), relative)
        if not source.is_file():
            raise FileNotFoundError(source)
        actual = sha(source)
        if digest is not None and actual != digest:
            raise ValueError("source pin changed: " + str(source))
        item = {"source": str(source), "sha256": actual, "bytes": source.stat().st_size,
                "origin": origin or str(source.relative_to(root))}
        if relative in artifacts and artifacts[relative]["sha256"] != actual:
            raise ValueError("archive destination collision: " + relative)
        artifacts[relative] = item

    def tree(folder, prefix):
        if not folder.exists():
            return
        for path in sorted(folder.rglob("*")):
            parts = path.relative_to(folder).parts
            if path.is_file() and not any(p in SKIP or p.startswith("test_") for p in parts[:-1]):
                add(path, str(Path(prefix) / path.relative_to(folder)))

    for name, digest in protocol["file_pins"].items():
        add(inside(study, name), name, digest)
    for name in ("protocol.json", "registration.json", "analysis_pins.json", "PREPARED_STATUS.json"):
        add(study / name, name)
    for name, digest in protocol["production_pins"].items():
        add(inside(root, name), "production/" + name, digest)
    # Current namespace proof is bundled; immutable older proof is content-addressed.
    registration = read(study / "registration.json")
    external = dict(registration["AG_terminal"]["file_pins"])
    external.update(registration["review_pins"])
    for name, digest in registration["AE_complete"]["file_pins"].items():
        external["results/prediction_gradient_20261014/" + name] = digest
    external.update(read(audit / "independent_source_design_review.json")["source_pins"])
    namespace = audit / "namespace"
    candidate = read(namespace / "candidate_namespace_review.json")
    external.update(candidate["source_pins"])
    external.update(read(namespace / "final_namespace_delta.json")["JSON_source_pins"])
    external.update(read(namespace / "final_namespace_delta.json")["source_pins"])
    for path in sorted(namespace.rglob("*")):
        if path.is_file() and not any(part in SKIP for part in path.relative_to(namespace).parts):
            external[str(path.relative_to(root))] = sha(path)
    refs = read(namespace / "history_references.json")
    for digest, item in refs["content_by_sha256"].items():
        source = inside(root, item["repository_path"])
        if sha(source) != digest or source.stat().st_size != item["bytes"]:
            raise ValueError("historical public namespace content differs")
        recorded = subprocess.run(["git", "show", item["containing_public_commit"] + ":" + item["repository_path"]],
                                  cwd=root, capture_output=True, check=True).stdout
        if hashlib.sha256(recorded).hexdigest() != digest:
            raise ValueError("historical committed namespace content differs")
    history = read(study / "seed_audit.json").get("source_revision_history_resolution", {})
    for folder in ("visibility_gradient_20261014", "visibility_flash_gradient_20261014", "visibility_dark_tail_information_20261014", "prediction_continuation_20261014", "prediction_gradient_20261014", "visibility_dark_tail_gradient_20261014"):
        for name in ("manifest.json", "prelaunch/manifest.json"):
            path = root / "results" / folder / name
            if path.is_file():
                external[str(path.relative_to(root))] = sha(path)
    for name, digest in external.items():
        if digest in refs["content_by_sha256"] or protocol["production_pins"].get(name) == digest:
            continue
        source = inside(root, name)
        if name in history and history[name]["sha256"] == digest:
            source = inside(root, history[name]["preserved_path"])
        add(source, "original/" + name, digest)
    add(audit / "NAMESPACE_PROVENANCE.md", "NAMESPACE_PROVENANCE.md")
    add(audit / "ARCHIVE.md", "ARCHIVE.md")
    for name in ("analyze.py", "offline_accounting.py", "native_audit.py", "initialization_replay.json", "analysis_review.json"):
        if not (study / "analysis" / name).is_file():
            raise ValueError("final independent analysis files have not been installed: " + name)
    tree(study / "analysis", "analysis")
    tree(study / "release_review", "release_review")
    if not (study / "release_review/archive.py").is_file():
        add(audit / "archive.py", "release_review/archive.py")
    for name in OPERATIONS:
        path = study / name
        if path.exists():
            add(path, "operations/" + name)
    clearance = study / "resource_clearance.json"
    dependency_pins = read(clearance)["budget_pins"] if clearance.exists() else {}
    for name, digest in dependency_pins.items():
        add(inside(root, name), "original/" + name, digest)
    if phase == "preparation":
        for name in ("ready.json", "attempt.json", "budget.json", "runs", "confirmation", "logs", "build-cache"):
            if (study / name).exists():
                raise ValueError("prospective packaging requires a zero-run unreleased study: " + name)
        if list(study.rglob("*.so")):
            raise ValueError("prospective study unexpectedly contains compiled libraries")
        if not (study / "preparation_claim.json").is_file():
            raise ValueError("retained inputs have not been copied and pinned")
    else:
        budget = read(study / "budget.json")
        if (budget.get("status") not in ("complete", "incomplete", "monitor_failed")
                or budget.get("running") or budget.get("queued") or budget.get("cleanup_error")):
            raise ValueError("terminal packaging requires settled worker groups and queues")
        ready = read(study / "ready.json")
        for name, digest in ready["source_pins"].items():
            relative = "operations/" + name if name in OPERATIONS else name
            add(inside(study, name), relative, digest)
        for folder in ("measurement", "logs", "requests", "monitor_receipts", "analysis_result", "build-cache", "terminal_review", "figures"):
            tree(study / folder, folder)
        for name in ("startup_identity.json", "report.json", "selection.json", "calibration_projection.json",
                     "confirmation_projection.json", "confirmation_roles.json", "confirmation_genotypes.npz"):
            if (study / name).exists():
                add(study / name, name)
    for path in sorted(study.rglob("*")):
        if not path.is_file() or any(part in SKIP for part in path.relative_to(study).parts):
            continue
        name = str(path.relative_to(study))
        relative = "operations/" + name if name in OPERATIONS else name
        add(path, relative)
    return {"format": 1, "phase": phase, "protocol_sha256": PROTOCOL_SHA,
            "status": "prepared_not_launched" if phase == "preparation" else "terminal_artifacts_archived",
            "scientific_lives_completed": 0 if phase == "preparation" else None,
            "compiled_libraries": 0 if phase == "preparation" else None,
            "release": False if phase == "preparation" else True,
            "planned_research_lives": 9804, "planned_validation_lives": 6,
            "scientific_outcomes_claimed": False,
            "working_directory": str(study.relative_to(root)),
            "scientific_inputs_portable_inside_folder": True,
            "historical_namespace_provenance_requires_repository_artifacts": True,
            "namespace_history_references_sha256": sha(audit / "namespace/history_references.json"),
            "historical_namespace_objects_not_recopied": refs["content_by_sha256"],
            "previously_compiled_provenance_libraries": [name for name in artifacts if name.endswith(".so") and name.startswith("production/")],
            "dependency_budget_pins": dependency_pins,
            "dependency_clearance_status": "copied" if clearance.exists() else "root_clearance_pending_before_release",
            "artifacts": artifacts}


def manifest(plan):
    value = {key: item for key, item in plan.items() if key != "artifacts"}
    value["artifacts"] = {name: {key: item[key] for key in ("sha256", "bytes", "origin")}
                          for name, item in sorted(plan["artifacts"].items())}
    return value


def ignored_paths(root, archive, plan):
    names = [str((archive / name).relative_to(root)) for name in sorted(plan["artifacts"])]
    names += [str((archive / name).relative_to(root)) for name in ("manifest.json", "prelaunch/manifest.json")]
    result = subprocess.run(["git", "check-ignore", "--no-index", "-z", "--stdin"],
                            input=("\0".join(names) + "\0").encode(), capture_output=True, cwd=root)
    if result.returncode not in (0, 1):
        raise RuntimeError("cannot audit force-add requirements: " + result.stderr.decode())
    return [name for name in result.stdout.decode().split("\0") if name]


def write_archive(archive, plan):
    prospective = archive / "prelaunch/manifest.json"
    current = archive / "manifest.json"
    if plan["phase"] == "terminal" and not prospective.is_file():
        raise ValueError("terminal update requires an existing published prospective snapshot")
    expected = manifest(plan)
    # Preflight every existing destination before copying anything. Prepared evidence
    # is never silently replaced, even when a source file has been deliberately edited.
    for name, item in plan["artifacts"].items():
        destination = inside(archive, name)
        if destination.exists() and sha(destination) != item["sha256"]:
            raise ValueError("immutable archived artifact differs: " + name)
    if plan["phase"] == "preparation" and prospective.exists() and read(prospective) != expected:
        raise ValueError("prospective archive is immutable; use a distinct reviewed revision")
    if current.exists() and read(current).get("protocol_sha256") != PROTOCOL_SHA:
        raise ValueError("archive belongs to another protocol")
    for name, item in sorted(plan["artifacts"].items()):
        source = Path(item["source"])
        if sha(source) != item["sha256"]:
            raise ValueError("source changed after planning: " + name)
        destination = inside(archive, name)
        destination.parent.mkdir(parents=True, exist_ok=True)
        if not destination.exists():
            shutil.copyfile(source, destination)
        if sha(destination) != item["sha256"]:
            raise ValueError("copied artifact hash differs: " + name)
    archive.mkdir(parents=True, exist_ok=True)
    if plan["phase"] == "preparation" and not prospective.exists():
        prospective.parent.mkdir(parents=True, exist_ok=True)
        prospective.write_text(json.dumps(expected, indent=2, allow_nan=False) + "\n")
    current.write_text(json.dumps(expected, indent=2, allow_nan=False) + "\n")
    return expected


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--write", action="store_true")
    parser.add_argument("--phase", choices=("preparation", "terminal"), default="preparation")
    args = parser.parse_args()
    plan = make_plan(ROOT, STUDY, AUDIT, args.phase)
    force = ignored_paths(ROOT, ARCHIVE, plan)
    if args.write:
        write_archive(ARCHIVE, plan)
    print(json.dumps({"status": "archived" if args.write else "dry_run", "phase": args.phase,
        "archive": str(ARCHIVE.relative_to(ROOT)), "protocol_sha256": PROTOCOL_SHA,
        "artifact_count": len(plan["artifacts"]), "bytes": sum(x["bytes"] for x in plan["artifacts"].values()),
        "compiled_libraries_by_helper": 0, "simulated_lives_by_helper": 0,
        "force_add_required": force}, indent=2))


if __name__ == "__main__":
    main()
