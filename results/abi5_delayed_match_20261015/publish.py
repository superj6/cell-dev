"""Archive completed ABI5 engineering evidence; never copy worktree caches or transient test directories."""
from pathlib import Path
import hashlib
import json
import shutil

ROOT = Path(__file__).resolve().parents[2]
STUDY = Path(__file__).resolve().parent
WORKTREE = STUDY / "worktree"
PUBLIC = ROOT / "results/abi5_delayed_match_20261015"
EXCLUDED = {"__pycache__", "cache", "tmp", "pytest-of-jgon", ".pytest_cache", ".ruff_cache"}


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def copy(source, target):
    target.parent.mkdir(parents=True, exist_ok=True)
    if target.exists() and sha(source) != sha(target):
        raise ValueError("refuse changed archive: " + str(target))
    shutil.copyfile(source, target)


for directory in ("coordination", "validation"):
    for source in sorted((STUDY / directory).rglob("*")):
        if (source.is_file() and (directory != "coordination" or source.name in ("CONTRACT.md", "AUTHORIZED_PROPOSAL.md"))
                and not EXCLUDED.intersection(source.relative_to(STUDY).parts)
                and source.suffix not in (".pyc", ".so")):
            copy(source, PUBLIC / source.relative_to(STUDY))
for name in ("README.md", "finalization.json", "verify.py", "publish.py"):
    copy(STUDY / name, PUBLIC / name)
final = json.loads((STUDY / "finalization.json").read_text())
for name, digest in final["source_pins"].items():
    source = WORKTREE / name
    assert sha(source) == digest, name
    copy(source, PUBLIC / "source" / name)
artifacts = {str(path.relative_to(PUBLIC)): {"sha256": sha(path), "bytes": path.stat().st_size}
             for path in sorted(PUBLIC.rglob("*")) if path.is_file() and path.name != "manifest.json"}
(PUBLIC / "manifest.json").write_text(json.dumps({"status": "complete", "artifacts": artifacts}, indent=2) + "\n")
print(json.dumps({"files": len(artifacts), "bytes": sum(r["bytes"] for r in artifacts.values())}))
