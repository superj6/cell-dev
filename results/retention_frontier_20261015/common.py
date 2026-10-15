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
    return protocol


def checked_release():
    protocol = checked_protocol()
    release = read(STUDY / "release.json")
    if release.get("status") != "released" or release.get("protocol_sha256") != sha(STUDY / "protocol.json"):
        raise ValueError("explicit release of the exact protocol is required")
    return protocol
