"""Small file/provenance helpers; importing this module never runs a life."""
from __future__ import annotations

import hashlib
import json
import os
from pathlib import Path

STUDY = Path(__file__).resolve().parent
ROOT = STUDY.parents[1]


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def raw_sha(value):
    return hashlib.sha256(value.tobytes()).hexdigest()


def read(path):
    return json.loads(Path(path).read_text())


def save(path, value, *, exclusive=False):
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    data = (json.dumps(value, indent=2, allow_nan=False) + "\n").encode()
    if exclusive:
        with path.open("xb") as stream:
            stream.write(data)
            stream.flush()
            os.fsync(stream.fileno())
        return
    tmp = path.with_suffix(path.suffix + ".tmp")
    with tmp.open("wb") as stream:
        stream.write(data)
        stream.flush()
        os.fsync(stream.fileno())
    tmp.replace(path)


def checked_protocol():
    protocol = read(STUDY / "protocol.json")
    for key, base in (("production_pins", ROOT), ("input_pins", STUDY), ("source_pins", STUDY)):
        for name, digest in protocol[key].items():
            path = (base / name).resolve()
            if not path.is_relative_to(base.resolve()) or sha(path) != digest:
                raise ValueError("changed pinned file: " + name)
    for field, name in (('seed_audit_sha256', 'namespace/seed_audit.json'),
                        ('reservation_sha256', 'reservation.json')):
        if sha(STUDY / name) != protocol[field]:
            raise ValueError('changed namespace evidence: ' + name)
    return protocol


def checked_release():
    protocol = checked_protocol()
    release = read(STUDY / "release.json")
    if release.get("status") != "released" or release.get("protocol_sha256") != sha(STUDY / "protocol.json"):
        raise ValueError("explicit release of the exact protocol is required")
    return protocol


def parent_check():
    monitor = int(os.environ.get("CELLDEV_MONITOR_PID", "0"))
    if monitor <= 1 or os.getppid() != monitor or os.getpgrp() != os.getpid():
        raise ValueError("measurement must run in the monitor's owned child session")
    if os.environ.get("CELLDEV_PROTOCOL_SHA256") != sha(STUDY / "protocol.json"):
        raise ValueError("monitor protocol binding differs")
    attempt_path = Path(os.environ.get("CELLDEV_ATTEMPT_PATH", ""))
    if attempt_path not in (STUDY / 'execution' / phase / 'attempt.json'
                            for phase in ('pareto', 'measurement')):
        raise ValueError("unexpected owned phase attempt")
    if os.environ.get("CELLDEV_ATTEMPT_SHA256") != sha(attempt_path):
        raise ValueError("monitor attempt binding differs")
    attempt = read(attempt_path)
    fields = Path(f"/proc/{monitor}/stat").read_text().rsplit(")", 1)[1].split()
    identity = {"pid": monitor, "ppid": int(fields[1]), "pgid": int(fields[2]),
                "start_ticks": int(fields[19])}
    namespace = os.readlink("/proc/self/ns/pid")
    if (attempt["monitor"] != identity
            or int(os.environ.get("CELLDEV_MONITOR_START_TICKS", "0")) != identity["start_ticks"]
            or attempt["pid_namespace"] != namespace
            or os.environ.get("CELLDEV_PID_NAMESPACE") != namespace
            or os.readlink(f"/proc/{monitor}/ns/pid") != namespace
            or attempt["protocol_sha256"] != sha(STUDY / "protocol.json")
            or attempt["release_sha256"] != sha(STUDY / "release.json")):
        raise ValueError("monitor identity, namespace or release binding differs")
    if "CELLDEV_THREADS_FILE" in os.environ:
        raise ValueError("fixed two-thread budget forbids elastic thread override")

