"""File and owned-worker checks; imports never build or run a life."""
from __future__ import annotations

import hashlib
import json
import os
from pathlib import Path

STUDY = Path(__file__).resolve().parent
ROOT = STUDY.parents[1]
ROLES = ('AM_reference', 'AN_start', 'unchanged8', 'unchanged24', 'balanced8', 'balanced24')


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def read(path):
    return json.loads(Path(path).read_text())


def save(path, value, *, exclusive=False):
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    data = (json.dumps(value, indent=2, allow_nan=False) + '\n').encode()
    target = path if exclusive else path.with_suffix(path.suffix + '.tmp')
    with target.open('xb' if exclusive else 'wb') as stream:
        stream.write(data)
        stream.flush()
        os.fsync(stream.fileno())
    if not exclusive:
        target.replace(path)


def checked_protocol():
    protocol = read(STUDY / 'protocol.json')
    for key, base in (('production_pins', ROOT), ('input_pins', STUDY), ('source_pins', STUDY)):
        for name, digest in protocol[key].items():
            path = (base / name).resolve()
            if not path.is_relative_to(base.resolve()) or sha(path) != digest:
                raise ValueError('changed pinned file: ' + name)
    for name in ('seed_audit', 'reservation'):
        if sha(STUDY / (name + '.json')) != protocol[name + '_sha256']:
            raise ValueError('changed pinned namespace evidence: ' + name)
    return protocol


def checked_release():
    protocol = checked_protocol()
    release = read(STUDY / 'release.json')
    if release.get('status') != 'released' or release.get('protocol_sha256') != sha(STUDY / 'protocol.json'):
        raise ValueError('root release must bind this exact prepared protocol')
    return protocol


def parent_check():
    monitor = int(os.environ.get('CELLDEV_MONITOR_PID', '0'))
    if monitor <= 1 or os.getppid() != monitor or os.getpgrp() != os.getpid():
        raise ValueError('worker must belong to its live monitor session')
    attempt_path = STUDY / 'attempt.json'
    if os.environ.get('CELLDEV_ATTEMPT_PATH') != str(attempt_path):
        raise ValueError('unexpected owned attempt path')
    if os.environ.get('CELLDEV_ATTEMPT_SHA256') != sha(attempt_path):
        raise ValueError('attempt binding differs')
    attempt = read(attempt_path)
    fields = Path(f'/proc/{monitor}/stat').read_text().rsplit(')', 1)[1].split()
    identity = dict(pid=monitor, ppid=int(fields[1]), pgid=int(fields[2]), start_ticks=int(fields[19]))
    namespace = os.readlink('/proc/self/ns/pid')
    if (attempt['monitor'] != identity or int(os.environ['CELLDEV_MONITOR_START_TICKS']) != identity['start_ticks']
            or attempt['pid_namespace'] != namespace or os.environ['CELLDEV_PID_NAMESPACE'] != namespace
            or os.readlink(f'/proc/{monitor}/ns/pid') != namespace
            or attempt['protocol_sha256'] != sha(STUDY / 'protocol.json')
            or os.environ['CELLDEV_PROTOCOL_SHA256'] != sha(STUDY / 'protocol.json')
            or attempt['release_sha256'] != sha(STUDY / 'release.json')):
        raise ValueError('monitor identity, namespace, or release differs')
    if 'CELLDEV_THREADS_FILE' in os.environ:
        raise ValueError('elastic thread overrides forbidden')
