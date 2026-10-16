"""Bounded replay of the frozen saved-data reader; never builds or simulates a life."""
import argparse
import hashlib
import importlib
import json
import os
from pathlib import Path
import resource
import shutil
import signal
import subprocess
import sys
import time

import verify


def save(path, value):
    with path.open('x') as stream:
        json.dump(value, stream, indent=2, allow_nan=False)
        stream.write('\n')


def run(out):
    started = time.monotonic()
    available = next(int(line.split()[1]) * 1024 for line in Path('/proc/meminfo').read_text().splitlines()
                     if line.startswith('MemAvailable:'))
    verify.require(available >= 4 * 1024**3, 'replay requires 4 GiB available host memory')
    requested = Path(out)
    requested = requested if requested.is_absolute() else Path.cwd() / requested
    outputs = verify.ROOT / 'outputs'
    verify.require(not requested.is_symlink() and not requested.exists(), '--out must not exist')
    out = requested.resolve()
    verify.require(out.parent == outputs.resolve() and out.name not in ('', '.', '..'),
                   '--out must be one new directory directly under this repository outputs/')
    verify.require(not outputs.is_symlink(), 'outputs must not be a symlink')
    out.mkdir(exist_ok=False)
    receipt = {'status': 'started', 'simulator_calls': 0, 'builds': 0, 'random_draws': 0,
               'replay_source_sha256': verify.sha(Path(__file__)), 'output': str(out.relative_to(verify.ROOT))}
    save(out / 'replay_started.json', receipt)
    try:
        checked = verify.verify()
        verify.require(shutil.disk_usage(out).free >= checked['raw_uncompressed_bytes'] + 64 * 1024**2,
                       'insufficient disk space for replay')
        # Frozen common/raw modules infer ROOT from a study three directories below it.
        checkout = out / 'checkout'
        study_parent = checkout / 'outputs' / 'saved_information'
        study = study_parent / 'prelaunch'
        shutil.copytree(verify.HERE / 'prelaunch', study, ignore=shutil.ignore_patterns('__pycache__'))
        shutil.copy2(verify.HERE / 'seed_audit.json', study_parent / 'seed_audit.json')
        protocol = verify.read(study / 'protocol.json')
        for name, pin in protocol['production_pins'].items():
            data = subprocess.check_output(['git', 'show', protocol['source_revision'] + ':' + name], cwd=verify.ROOT)
            verify.require(hashlib.sha256(data).hexdigest() == pin, 'replay source pin: ' + name)
            destination = verify.checked_path(checkout, name)
            destination.parent.mkdir(parents=True, exist_ok=True)
            with destination.open('xb') as stream:
                stream.write(data)
        verify.require(not (study / 'raw').exists(), 'public archive unexpectedly contains unpacked raw')
        rows = verify.scheduled_rows(study, protocol)
        extracted = verify.verify_raw(rows, destination=study_parent)
        # No native library is loaded: analyze imports raw solely for ABI ledger constants.
        sys.path.insert(0, str(study))
        for name in ('common', 'analyze', 'raw'):
            verify.require(name not in sys.modules, 'unexpected preloaded module: ' + name)
        common = importlib.import_module('common')
        common.checked_protocol()
        analyzer = importlib.import_module('analyze')
        reproduced = analyzer.analyze(protocol, rows)
        target = out / 'summary.json'
        common.save(target, reproduced, exclusive=True)
        verify.require(target.read_bytes() == (verify.HERE / 'prelaunch/summary.json').read_bytes(),
                       'replayed summary is not byte-identical')
        receipt.update(status='passed', protocol_sha256=checked['protocol_sha256'],
                       native_summary_sha256=checked['summary_sha256'], replay_summary_sha256=verify.sha(target),
                       raw_tar_sha256=checked['raw_tar_sha256'], row_index_sha256=checked['row_index_sha256'],
                       source_revision=protocol['source_revision'], **extracted)
    except BaseException as error:
        receipt.update(status='failed', error=repr(error))
        raise
    finally:
        usage = resource.getrusage(resource.RUSAGE_SELF)
        children = resource.getrusage(resource.RUSAGE_CHILDREN)
        receipt.update(cpu_seconds=usage.ru_utime + usage.ru_stime + children.ru_utime + children.ru_stime,
                       wall_seconds=time.monotonic() - started, peak_rss_kib=usage.ru_maxrss)
        save(out / 'replay_receipt.json', receipt)
    return receipt


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--out', required=True, help='new outputs/<name>; existing destinations are rejected')
    args = parser.parse_args()
    for name in ('OPENBLAS_NUM_THREADS', 'OMP_NUM_THREADS', 'MKL_NUM_THREADS', 'NUMEXPR_NUM_THREADS'):
        os.environ[name] = '1'
    sys.dont_write_bytecode = True
    resource.setrlimit(resource.RLIMIT_CPU, (60, 60))
    resource.setrlimit(resource.RLIMIT_AS, (2 * 1024**3, 2 * 1024**3))
    signal.signal(signal.SIGALRM, lambda *_: (_ for _ in ()).throw(TimeoutError('120-second replay wall limit')))
    signal.alarm(120)
    try:
        print(json.dumps(run(args.out), indent=2))
    finally:
        signal.alarm(0)


if __name__ == '__main__':
    main()
