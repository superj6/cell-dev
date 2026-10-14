"""Portable, simulation-free records and source checks for the fixed visibility pilot."""
from __future__ import annotations
import hashlib
import json
import os
from pathlib import Path

STUDY = Path(__file__).resolve().parent
ROOT = STUDY.parents[1]
ROLES = ['R0', 'R1', 'I', 'A', 'B', *[f'D{i}' for i in range(8)]]
WORLDS = ['flash5_dim25', 'blink20']
SIZES = [3, 875, 129, 66, 57, 5, 23, 1024, 7, 18]
ACTION = dict(latency='d0', charge='relay', t_ref_min=0.5, privileged=False, quant=False)


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def canonical(value):
    return json.dumps(value, sort_keys=True, separators=(',', ':'), allow_nan=False)


def read(path):
    return json.loads(Path(path).read_text())


def save(path, value):
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    temp = path.with_suffix(path.suffix + '.pending')
    with temp.open('w') as stream:
        stream.write(json.dumps(value, indent=2, allow_nan=False) + '\n')
        stream.flush()
        os.fsync(stream.fileno())
    temp.replace(path)


def verify_pins(pins, base=STUDY):
    for name, digest in pins.items():
        path = Path(base) / name
        if not path.resolve().is_relative_to(Path(base).resolve()) or not path.is_file() or sha(path) != digest:
            raise ValueError('source/config pin changed: ' + name)


def protocol():
    value = read(STUDY / 'protocol.json')
    verify_pins(value['file_pins'])
    verify_pins(value['production_pins'], ROOT)
    return value


def process_identity(pid):
    fields = Path(f'/proc/{pid}/stat').read_text().rsplit(')',1)[1].split()
    return {'pid':pid,'ppid':int(fields[1]),'pgid':int(fields[2]),'sid':int(fields[3]),'start_ticks':int(fields[19])}


def parent_check(expected, *, nested=False, phase=None):
    if expected is None or expected <= 1 or os.getppid() != expected:
        raise ValueError('worker must be owned by the recorded monitor parent')
    monitor_pid = int(os.environ.get('CELLDEV_VISIBILITY_MONITOR_PID','0'))
    attempt = read(STUDY/'attempt.json')
    actual = process_identity(monitor_pid)
    registered = attempt['monitor']
    if monitor_pid <= 1 or registered['pid'] != monitor_pid or actual['start_ticks'] != registered['start_ticks']:
        raise ValueError('monitor process identity changed')
    if attempt['ready_sha256'] != sha(STUDY/'ready.json'):
        raise ValueError('monitor attempt release changed')
    budget = read(STUDY/'budget.json')
    if budget.get('status') != 'running' or (phase is not None and budget.get('phase') != phase):
        raise ValueError('monitor budget is not actively running this phase')
    if nested:
        direct = process_identity(expected)
        if direct['ppid'] != monitor_pid or direct['pgid'] != expected or direct['sid'] != expected or os.getpgrp() != expected or os.getsid(0) != expected:
            raise ValueError('production bridge escaped owned validation process group')
    elif expected != monitor_pid or os.getpgrp() != os.getpid() or os.getsid(0) != os.getpid():
        raise ValueError('worker is not the owned monitor child process group')


def require_release():
    value = protocol()
    from numerical import check
    check(value['numerical_identity'])
    ready = read(STUDY / 'ready.json')
    if ready.get('status') != 'released' or value['production_binding']['status'] != 'complete':
        raise ValueError('root release and completed production binding required')
    if ready.get('production_pins') != value['production_pins'] or not value['production_pins']:
        raise ValueError('production release pins missing or changed')
    required = dict(value['file_pins'])
    for name in ('protocol.json', 'monitor.py', 'measure.py', 'validate.py', 'resource_clearance.json'):
        required[name] = sha(STUDY / name)
    if any(ready.get('source_pins', {}).get(name) != digest for name, digest in required.items()):
        raise ValueError('release pins missing or changed')
    verify_pins(ready['source_pins'])
    return value
