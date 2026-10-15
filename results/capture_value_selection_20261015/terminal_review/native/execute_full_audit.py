"""Execute the prepared offline AM audit once, preserving exact sources and logs."""
from __future__ import annotations

import hashlib
import json
import os
import resource
import shutil
import subprocess
import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]
SOURCE = Path(__file__).resolve().parent
STUDY = ROOT / 'outputs/autonomous_capture_value_selection_20261015'
DEST = STUDY / 'terminal_review/native'


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def main():
    prepared = json.loads((SOURCE / 'full_audit_preparation.json').read_text())
    for name, digest in prepared['files'].items():
        if sha(SOURCE / name) != digest:
            raise ValueError('prepared helper changed: ' + name)
    for name, digest in prepared['producer_helpers'].items():
        if sha(STUDY / name) != digest:
            raise ValueError('producer helper changed: ' + name)
    for arm in ('current_value', 'high_value'):
        marker = STUDY / 'runs' / arm / 'search_complete.json'
        if json.loads(marker.read_text())['status'] != 'complete':
            raise ValueError('search is incomplete: ' + arm)
    DEST.mkdir(exist_ok=False)
    for name in dict.fromkeys([*prepared['files'], 'full_audit_preparation.json', 'README.md', Path(__file__).name]):
        shutil.copyfile(SOURCE / name, DEST / name)
    (DEST / 'producer_helpers').mkdir()
    for name in prepared['producer_helpers']:
        shutil.copyfile(STUDY / name, DEST / 'producer_helpers' / name)
    argv = [str(ROOT / '.venv/bin/python'), str(DEST / 'audit_native.py'),
            '--study', str(STUDY), '--out', str(DEST / 'complete_native_audit.json')]
    env = os.environ.copy()
    limits = {'PYTHONDONTWRITEBYTECODE': '1', 'OMP_NUM_THREADS': '1',
              'OPENBLAS_NUM_THREADS': '1', 'MKL_NUM_THREADS': '1',
              'NUMEXPR_NUM_THREADS': '1', 'ATEN_CPU_CAPABILITY': 'avx2'}
    env.update(limits)
    command = {'argv': argv, 'cwd': str(ROOT), 'environment_overrides': limits,
               'protocol_sha256': sha(STUDY / 'protocol.json'),
               'prepared_sources': prepared['files'],
               'producer_helpers': prepared['producer_helpers'],
               'execution_helper_sha256': sha(Path(__file__)),
               'simulation_calls': 0, 'compiled_libraries': 0, 'random_draws': 0}
    (DEST / 'execution_command.json').write_text(json.dumps(command, indent=2) + '\n')
    before = resource.getrusage(resource.RUSAGE_CHILDREN)
    start = time.monotonic()
    with (DEST / 'stdout.json').open('xb') as stdout, (DEST / 'stderr.txt').open('xb') as stderr:
        result = subprocess.run(argv, cwd=ROOT, env=env, stdout=stdout, stderr=stderr, check=False)
    after = resource.getrusage(resource.RUSAGE_CHILDREN)
    receipt = {'status': 'passed' if result.returncode == 0 else 'failed',
               'returncode': result.returncode, 'wall_seconds': time.monotonic() - start,
               'cpu_seconds': after.ru_utime + after.ru_stime - before.ru_utime - before.ru_stime,
               'command_sha256': sha(DEST / 'execution_command.json'),
               'stdout_sha256': sha(DEST / 'stdout.json'), 'stderr_sha256': sha(DEST / 'stderr.txt'),
               'simulation_calls': 0, 'compiled_libraries': 0, 'random_draws': 0}
    report = DEST / 'complete_native_audit.json'
    if report.exists():
        receipt['complete_native_audit_sha256'] = sha(report)
    (DEST / 'execution_review.json').write_text(json.dumps(receipt, indent=2) + '\n')
    print(json.dumps(receipt))
    return result.returncode


if __name__ == '__main__':
    sys.exit(main())
