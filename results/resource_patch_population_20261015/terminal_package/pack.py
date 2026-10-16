"""Stage complete population evidence in a new outputs directory; no publication or simulation."""
from __future__ import annotations

import argparse
import json
import os
import resource
import shutil
import signal
import time
from pathlib import Path

import verify

HERE = Path(__file__).resolve().parent
STUDY = HERE.parent
SKIP = {'__pycache__', '.pytest_cache', '.ruff_cache', 'build-cache', 'fixtures', 'tmp',
        'reader_test_tmp', 'matplotlib_cache', 'terminal_package_logs'}


def save(path, value):
    with path.open('x') as stream:
        json.dump(value, stream, indent=2, allow_nan=False); stream.write('\n')


def copy(source, target):
    verify.require(source.is_file() and not source.is_symlink(), 'regular evidence file required')
    target.parent.mkdir(parents=True, exist_ok=True)
    if target.exists():
        verify.require(verify.sha(source) == verify.sha(target), 'changed prospective file: ' + str(target))
    else:
        shutil.copyfile(source, target)


def tree(source, target):
    for path in sorted(source.rglob('*')):
        relative = path.relative_to(source)
        if any(p in SKIP or p.startswith('test_') or p.endswith('_tmp') for p in relative.parts[:-1]):
            continue
        verify.require(not path.is_symlink(), 'symlink in evidence')
        if path.is_file() and path.suffix not in ('.pyc', '.so', '.tmp'):
            copy(path, target / relative)


def pack(args):
    start, cpu = time.monotonic(), time.process_time()
    study, out = args.study.resolve(), args.out.resolve()
    public = verify.ROOT / 'results/resource_patch_population_20261015'
    verify.require(out.is_relative_to(verify.ROOT/'outputs') and not out.exists()
                   and not out.is_relative_to(study) and not study.is_relative_to(out), 'fresh separate staging path')
    _, raw_pins = verify.terminal_bindings(study)
    original = verify.read(public / 'manifest.json')
    verify.require(original['status'] == 'prospective' and original['scientific_calls'] == 0
                   and original['planned_calls'] == 15524 and original['protocol_sha256'] == verify.PROTOCOL,
                   'unchanged prospective public archive required')
    verify.manifest_files(public, original)
    verify.require(args.readme.read_bytes() != (public/'README.md').read_bytes(), 'terminal README required')
    out.mkdir(parents=True)
    try:
        for name in (*original['files'], 'manifest.json'):
            target = 'registration/'+name if name in verify.REGISTRATION else name
            copy(verify.checked(public, name), verify.checked(out, target))
        for source in sorted(study.iterdir()):
            if (source.is_file() and source.suffix in ('.py', '.json', '.md', '.txt', '.log', '.csv', '.svg', '.png')
                    and source.name not in verify.REGISTRATION):
                copy(source, out/source.name)
        for name in ('raw', 'scored', 'startup_truth', 'execution', 'reviews', 'terminal_review', 'terminal_package'):
            verify.require((study/name).is_dir(), 'missing terminal evidence: ' + name)
            tree(study/name, out/name)
        if (study/'terminal_tables').is_dir():
            tree(study/'terminal_tables', out/'terminal_tables')
        for source in sorted((study/'publication_logs').glob('prospective_*')):
            copy(source, out/'publication_logs'/source.name)
        copy(args.readme.resolve(), out/'README.md')
        copy(args.report.resolve(), out/'REPORT.md')
        copy(HERE/'verify.py', out/'verify.py')
        save(out/'packaging_receipt.json', dict(status='staged', protocol_sha256=verify.PROTOCOL,
            prospective_manifest_sha256=verify.sha(out/'registration/manifest.json'),
            summary_sha256=verify.sha(out/'summary.json'), helper_sha256=verify.sha(__file__),
            raw_scored_files=raw_pins, cpu_seconds_before_verification=time.process_time()-cpu,
            wall_seconds_before_verification=time.monotonic()-start, simulator_calls=0, builds=0, random_draws=0))
        records = {name:dict(sha256=verify.sha(out/name), bytes=(out/name).stat().st_size)
                   for name in sorted(verify.files(out))}
        save(out/'manifest.json', dict(status='complete', protocol_sha256=verify.PROTOCOL,
            research_lives=15520, startup_lives=4, total_calls=15524, files=records))
        return verify.verify(out)
    except BaseException as error:
        save(out/'packaging_failure.json', dict(status='failed', error=repr(error), simulator_calls=0, builds=0))
        raise


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--study', type=Path, default=STUDY)
    parser.add_argument('--out', type=Path, default=verify.ROOT/'outputs/resource_patch_population_terminal_stage_20261015')
    parser.add_argument('--readme', type=Path, required=True)
    parser.add_argument('--report', type=Path, required=True)
    args = parser.parse_args()
    os.sched_setaffinity(0, {min(os.sched_getaffinity(0))})
    resource.setrlimit(resource.RLIMIT_CPU, (15,15))
    resource.setrlimit(resource.RLIMIT_AS, (2*1024**3,2*1024**3))
    signal.alarm(30)
    available = next(int(line.split()[1])*1024 for line in Path('/proc/meminfo').read_text().splitlines()
                     if line.startswith('MemAvailable:'))
    verify.require(available >= 4*1024**3, '4GiB host memory headroom required')
    print(json.dumps(pack(args), indent=2))
