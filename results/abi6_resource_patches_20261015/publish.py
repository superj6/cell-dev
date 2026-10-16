"""Plan an immutable ABI6 engineering archive; explicit --publish creates it after finalization.

Only root notes/text sources, filtered validation evidence, declared preview files and pinned source snapshots
are retained. No production code is imported, no simulator is run and no binary is built.
"""
from __future__ import annotations

import argparse
import json
import os
import shutil
import sys
import tempfile
from pathlib import Path

sys.dont_write_bytecode = True
from verify import CONTRACT_SHA, SCHEMA, check_truth, relative, sha, verify_archive  # noqa: E402

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[1]
DEFAULT_PUBLIC = ROOT / "results/abi6_resource_patches_20261015"
EXCLUDED_DIRS = {"__pycache__", ".pytest_cache", ".ruff_cache", "cache", "build-cache", "tmp", "node_modules"}
EXCLUDED_FILES = {"heartbeat.json", "monitor_heartbeat.json", "monitor_status.json"}
TEXT_SUFFIXES = {".py", ".js", ".cjs", ".json", ".jsonl", ".log", ".md", ".txt", ".before_fix"}
EVIDENCE_SUFFIXES = TEXT_SUFFIXES | {".npz", ".html", ".css", ".svg", ".png"}


def evidence_files(folder: Path):
    """Prune temporary/cache trees before descent; never traverse a symlink."""
    for directory, names, filenames in os.walk(folder, followlinks=False):
        base = Path(directory)
        names[:] = sorted(name for name in names if name not in EXCLUDED_DIRS and
                          not name.startswith(("pytest", "patch-fixture-")) and not name.endswith("_tmp"))
        for name in names:
            if (base / name).is_symlink():
                raise ValueError(f"evidence directory is a symlink: {base / name}")
        for name in sorted(filenames):
            path = base / name
            if name in EXCLUDED_FILES or path.suffix not in EVIDENCE_SUFFIXES:
                continue
            if path.is_symlink():
                raise ValueError(f"evidence file is a symlink: {path}")
            yield path


def archive_plan(study: Path) -> tuple[dict[str, Path], dict]:
    final = json.loads((study / "finalization.json").read_text())
    if not final.get("status") or final["status"] in ("running", "incomplete", "source_prepared_unexecuted"):
        raise ValueError("a terminal finalization record is required")
    if sha(study / "DRAFT_CONTRACT.md") != CONTRACT_SHA:
        raise ValueError("approved contract changed")
    selected = {path.name: path for path in sorted(study.iterdir())
                if path.is_file() and path.suffix in {".md", ".json", ".py"}}
    for required in ("README.md", "finalization.json", "publish.py", "verify.py", "DRAFT_CONTRACT.md"):
        if required not in selected:
            raise ValueError(f"required root artifact absent: {required}")
    for path in evidence_files(study / "validation"):
        selected[path.relative_to(study).as_posix()] = path
    truth_name = final.get("archive_truth_path", "validation/truth")
    truth_path = relative(truth_name)
    if truth_path.parts[0] != "validation":
        raise ValueError("truth evidence must live beneath validation/")
    check_truth(study, truth_name)
    for name in final.get("archive_preview_paths", ["resource_patches_preview.html"]):
        path = study / relative(name)
        if not path.is_file():
            raise ValueError(f"declared preview absent: {name}")
        selected[name] = path
    if not final.get("source_pins"):
        raise ValueError("finalization source_pins are required")
    for name, digest in final["source_pins"].items():
        source = ROOT / relative(name)
        if source.is_symlink() or sha(source) != digest:
            raise ValueError(f"installed source changed before archival: {name}")
        selected[(Path("source") / relative(name)).as_posix()] = source
    for name, path in selected.items():
        relative(name)
        if path.is_symlink():
            raise ValueError(f"archive source is a symlink: {path}")
    return selected, final


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--publish", action="store_true")
    parser.add_argument("--target", type=Path, default=DEFAULT_PUBLIC)
    args = parser.parse_args()
    selected, final = archive_plan(HERE)
    records = {name: {"sha256": sha(path), "bytes": path.stat().st_size}
               for name, path in sorted(selected.items())}
    manifest = {"schema": SCHEMA, "status": "complete", "contract_sha256": CONTRACT_SHA,
                "finalization_sha256": records["finalization.json"]["sha256"],
                "truth_path": final.get("archive_truth_path", "validation/truth"), "artifacts": records}
    manifest_bytes = (json.dumps(manifest, indent=2, sort_keys=True) + "\n").encode()
    target = args.target.resolve()
    summary = {"status": "planned", "target": str(target), "artifacts": len(records),
               "bytes": sum(row["bytes"] for row in records.values()), "simulations": 0, "builds": 0}
    if not args.publish:
        print(json.dumps(summary, sort_keys=True))
        return
    if target.exists():
        if not target.is_dir() or (target / "manifest.json").read_bytes() != manifest_bytes:
            raise ValueError("refuse to alter an existing archive; use a fresh reviewed destination")
        print(json.dumps(verify_archive(target, archive_only=False, repo_root=ROOT), sort_keys=True))
        return
    target.parent.mkdir(parents=True, exist_ok=True)
    with tempfile.TemporaryDirectory(prefix="." + target.name + "-", dir=target.parent) as temporary:
        stage = Path(temporary) / "archive"
        stage.mkdir()
        for name, source in selected.items():
            destination = stage / relative(name)
            destination.parent.mkdir(parents=True, exist_ok=True)
            shutil.copyfile(source, destination)
        (stage / "manifest.json").write_bytes(manifest_bytes)
        report = verify_archive(stage, archive_only=False, repo_root=ROOT)
        # Verification catches source or evidence mutation between planning and copying.
        if target.exists():
            raise ValueError("archive destination appeared during staging; refusing replacement")
        stage.rename(target)
    print(json.dumps(report | {"target": str(target)}, sort_keys=True))


if __name__ == "__main__":
    main()
