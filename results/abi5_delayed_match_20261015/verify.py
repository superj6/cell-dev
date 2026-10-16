"""Verify the ABI5 archive and installed port source bytes without running simulations."""
from pathlib import Path
import hashlib
import json
import sys

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[1]
manifest = json.loads((HERE / "manifest.json").read_text())
for name, record in manifest["artifacts"].items():
    path = HERE / name
    assert path.stat().st_size == record["bytes"], name
    assert hashlib.sha256(path.read_bytes()).hexdigest() == record["sha256"], name
final = json.loads((HERE / "finalization.json").read_text())
if "--archive-only" not in sys.argv:
    for name, digest in final["source_pins"].items():
        assert hashlib.sha256((ROOT / name).read_bytes()).hexdigest() == digest, name
print(json.dumps({"status": "passed", "artifacts": len(manifest["artifacts"]),
                  "installed_sources_checked": "--archive-only" not in sys.argv, "simulations": 0}))
