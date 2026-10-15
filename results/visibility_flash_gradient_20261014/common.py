"""Small record/release helpers reused from the reviewed visibility monitor."""
from __future__ import annotations

import hashlib
import json
import os
from pathlib import Path

STUDY = Path(__file__).resolve().parent
ROOT = STUDY.parents[1]


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def read(path):
    return json.loads(Path(path).read_text())


def save(path, value):
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_suffix(path.suffix + ".pending")
    with temporary.open("w") as stream:
        stream.write(json.dumps(value, indent=2, allow_nan=False) + "\n")
        stream.flush()
        os.fsync(stream.fileno())
    temporary.replace(path)


def verify_pins(pins, base):
    for relative, expected in pins.items():
        path = Path(base) / relative
        if not path.resolve().is_relative_to(Path(base).resolve()) or not path.is_file() or sha(path) != expected:
            raise ValueError("source/config pin changed: " + relative)


def process_identity(pid):
    fields = Path(f"/proc/{pid}/stat").read_text().rsplit(")", 1)[1].split()
    return {"pid": pid, "ppid": int(fields[1]), "pgid": int(fields[2]), "sid": int(fields[3]),
            "start_ticks": int(fields[19])}


def parent_check(expected):
    if expected is None or expected <= 1 or os.getppid() != expected:
        raise ValueError("worker must be owned by the recorded monitor parent")
    monitor_pid = int(os.environ.get("CELLDEV_FLASH_GRADIENT_MONITOR_PID", "0"))
    attempt = read(STUDY / "attempt.json")
    actual = process_identity(monitor_pid)
    registered = attempt["monitor"]
    if monitor_pid != expected or registered["pid"] != monitor_pid or actual["start_ticks"] != registered["start_ticks"]:
        raise ValueError("monitor process identity changed")
    if attempt["ready_sha256"] != sha(STUDY / "ready.json"):
        raise ValueError("monitor attempt release changed")
    if (os.getpgrp() != os.getpid() or os.getsid(0) != os.getpid()
            or read(STUDY / "budget.json").get("status") != "running"):
        raise ValueError("worker is outside its active owned monitor group")


def require_release():
    protocol = read(STUDY / "protocol.json")
    ready = read(STUDY / "ready.json")
    if ready.get("status") != "released" or protocol.get("world_decision") != "complete":
        raise ValueError("complete world decision and root release required")
    required_local = {"measure.py", "scoring.py", "common.py", "numerical.py"}
    required_production = {str(p.relative_to(ROOT)) for p in (ROOT / "src").rglob("*.py")}
    required_production.update({"src/life/kernel.c", "scripts/taskvar_confirm.py",
                                "scripts/taskvar_gradient.py", "scripts/taskvar_gates.py"})
    if (not required_local.issubset(protocol["file_pins"])
            or not required_production.issubset(protocol["production_pins"])):
        raise ValueError("required worker and reference-import source closure is not pinned")
    verify_pins(protocol["file_pins"], STUDY)
    verify_pins(protocol["production_pins"], ROOT)
    required = dict(protocol["file_pins"])
    required.update({name: sha(STUDY / name) for name in
                     ("protocol.json", "monitor.py", "resource_clearance.json")})
    if any(ready.get("source_pins", {}).get(k) != v for k, v in required.items()):
        raise ValueError("release pins missing or changed")
    if ready.get("production_pins") != protocol["production_pins"] or not protocol["production_pins"]:
        raise ValueError("production release pins missing or changed")
    verify_pins(ready["source_pins"], STUDY)
    return protocol
