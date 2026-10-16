"""Verify immutable ABI6 engineering evidence; --archive-only needs no installed production source.

This reader hashes retained files only. It performs no imports of production code, builds, or simulations.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import re
from pathlib import Path, PurePosixPath

SCHEMA = "abi6-resource-engineering-archive-v1"
CONTRACT_SHA = "15c3f7d7006bd274c2e7c9c06d6a89bd264dd8128be8579286dda70c1d740d77"


def sha(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def relative(name: str) -> Path:
    path = PurePosixPath(name)
    if not name or name == "." or path.is_absolute() or ".." in path.parts or path.as_posix() != name or "\\" in name:
        raise ValueError(f"unsafe archive path: {name!r}")
    return Path(*path.parts)


def files(root: Path) -> dict[str, Path]:
    result = {}
    for path in sorted(root.rglob("*")):
        if path.is_symlink():
            raise ValueError(f"symlinks are not archive artifacts: {path}")
        if path.is_file():
            result[path.relative_to(root).as_posix()] = path
    return result


def check_truth(root: Path, truth_name: str) -> dict:
    truth_dir = root / relative(truth_name)
    truth = json.loads((truth_dir / "truth.json").read_text())
    progress = json.loads((truth_dir / "progress.json").read_text())
    calls = json.loads((truth_dir / "calls.json").read_text())
    if truth.get("status") != "complete" or truth.get("abi") != 6 or len(truth.get("cases", [])) != 8:
        raise ValueError("eight completed ABI6 truth cases required")
    if (progress.get("status"), progress.get("complete_cases"), progress.get("calls")) != ("complete", 8, 24):
        raise ValueError("truth progress does not attest 24 returned calls")
    if len(calls) != 24 or any(row.get("status") != "validated" for row in calls):
        raise ValueError("all 24 truth calls must have validated raw output")
    if [row.get("index") for row in calls] != list(range(24)):
        raise ValueError("truth call indices are not complete and ordered")
    expected = set()
    for row in calls:
        raw = relative(row["raw"])
        if len(raw.parts) != 1 or raw.suffix != ".npz" or raw.name in expected:
            raise ValueError("truth raw files must be distinct immediate NPZ artifacts")
        expected.add(raw.name)
        if sha(truth_dir / raw) != row["raw_sha256"]:
            raise ValueError(f"truth call/raw digest differs: {raw}")
    if {path.name for path in truth_dir.glob("*.npz")} != expected:
        raise ValueError("truth directory must contain exactly its 24 declared NPZ files")
    names = [case["name"] for case in truth["cases"]]
    if len(set(names)) != 8:
        raise ValueError("truth case names must be unique")
    for name in names:
        if sorted(row["backend"] for row in calls if row["case"] == name) != ["C_fast", "C_full", "Python"]:
            raise ValueError(f"truth case needs one full, fast and Python call: {name}")
    return {"cases": 8, "raw_npz": 24}


def verify_archive(root: Path, *, archive_only: bool, repo_root: Path | None = None) -> dict:
    manifest = json.loads((root / "manifest.json").read_text())
    if manifest.get("schema") != SCHEMA or manifest.get("status") != "complete":
        raise ValueError("not a complete ABI6 engineering manifest")
    actual = files(root)
    expected = set(manifest["artifacts"]) | {"manifest.json"}
    if set(actual) != expected:
        raise ValueError(f"archive file set differs; extra={sorted(set(actual)-expected)}, "
                         f"missing={sorted(expected-set(actual))}")
    for name, record in manifest["artifacts"].items():
        path = root / relative(name)
        if path.stat().st_size != record["bytes"] or sha(path) != record["sha256"]:
            raise ValueError(f"archive bytes differ: {name}")
    if sha(root / "DRAFT_CONTRACT.md") != CONTRACT_SHA or manifest["contract_sha256"] != CONTRACT_SHA:
        raise ValueError("approved contract differs")
    if sha(root / "finalization.json") != manifest["finalization_sha256"]:
        raise ValueError("finalization differs from manifest")
    final = json.loads((root / "finalization.json").read_text())
    if not final.get("source_pins"):
        raise ValueError("finalization must pin production and test source snapshots")
    for name, digest in final["source_pins"].items():
        source = relative(name)
        if not re.fullmatch(r"[0-9a-f]{64}", digest) or sha(root / "source" / source) != digest:
            raise ValueError(f"final source snapshot differs: {name}")
        if not archive_only and (repo_root is None or sha(repo_root / source) != digest):
            raise ValueError(f"installed source differs: {name}")
    truth_name = final.get("archive_truth_path", "validation/truth")
    if manifest["truth_path"] != truth_name:
        raise ValueError("manifest and finalization name different truth directories")
    truth_counts = check_truth(root, truth_name)
    for name in final.get("archive_preview_paths", ["resource_patches_preview.html"]):
        if name not in manifest["artifacts"] or not (root / relative(name)).is_file():
            raise ValueError(f"declared preview absent: {name}")
    failures = (
        ("python_initial", 6, ("test_abi6_legacy.py.before_fix",)),
        ("python_full", 2, ("before_fix/src/life/probe.py", "before_fix/tests/test_abi5_kernel_boundaries.py",
                            "before_fix/tests/test_life_kernel_smoke.py")),
    )
    for label, count, originals in failures:
        folder = root / "validation" / label
        output = (folder / "worker.stdout.log").read_text().splitlines()
        budget = json.loads((folder / "budget.json").read_text())
        if sum(line.startswith("FAILED tests/") for line in output) != count or budget.get("worker_exit_code") != 1:
            raise ValueError(f"original {label} failure output and exit status must be retained")
        if any(not (folder / name).is_file() for name in originals):
            raise ValueError(f"original {label} source files must be retained")
    for command in (root / "validation").glob("*/command.json"):
        budget = json.loads((command.parent / "budget.json").read_text())
        cleanup = budget.get("terminal_cleanup", {})
        if (budget.get("status") not in ("complete", "incomplete") or budget.get("running") or
                budget.get("queued") or not cleanup.get("all_owned_groups_exited") or
                not cleanup.get("all_worker_identities_exited") or cleanup.get("remaining_descendants")):
            raise ValueError(f"validation worker lacks terminal cleanup: {command.parent.name}")
    return {"status": "passed", "artifacts": len(manifest["artifacts"]),
            "bytes": sum(row["bytes"] for row in manifest["artifacts"].values()),
            "installed_sources_checked": not archive_only, "truth": truth_counts,
            "manifest_sha256": sha(root / "manifest.json"), "simulations": 0, "builds": 0}


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--archive", type=Path, default=Path(__file__).resolve().parent)
    parser.add_argument("--repo-root", type=Path)
    parser.add_argument("--archive-only", action="store_true")
    args = parser.parse_args()
    root = args.archive.resolve()
    repo = args.repo_root.resolve() if args.repo_root else root.parents[1]
    print(json.dumps(verify_archive(root, archive_only=args.archive_only, repo_root=repo), sort_keys=True))


if __name__ == "__main__":
    main()
