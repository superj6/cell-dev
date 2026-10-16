"""Stage terminal evidence into a fresh outputs folder; never publish or run a simulator."""
from __future__ import annotations

import argparse
import hashlib
import json
import shutil
import subprocess
import time
from pathlib import Path

import verify

HERE = Path(__file__).resolve().parent
SKIP = {'__pycache__', '.pytest_cache', 'build-cache', 'reader_test_tmp', 'tmp'}
ROOT_SUFFIXES = {'.py', '.json', '.md', '.txt', '.log', '.csv'}


def save(path, value):
    with path.open('x') as stream:
        json.dump(value, stream, indent=2, allow_nan=False)
        stream.write('\n')


def copy(source, destination):
    verify.require(source.is_file() and not source.is_symlink(), 'regular evidence file required: ' + str(source))
    destination.parent.mkdir(parents=True, exist_ok=True)
    if destination.exists():
        verify.require(verify.sha(source) == verify.sha(destination), 'changed prospective file: ' + str(destination))
    else:
        shutil.copyfile(source, destination)


def tree(source, destination):
    for path in sorted(source.rglob('*')):
        relative = path.relative_to(source)
        if set(relative.parts) & SKIP:
            continue
        verify.require(not path.is_symlink(), 'symlink in evidence tree')
        if path.is_file():
            verify.require(path.suffix not in ('.so', '.pyc', '.tmp'), 'binary/cache/temp evidence')
            copy(path, destination / relative)


def pack(args):
    started = time.monotonic()
    study, out = args.study.resolve(), args.out.resolve()
    prospective = verify.ROOT / 'results/resource_patch_selection_20261015'
    verify.require(out.is_relative_to(verify.ROOT / 'outputs') and not out.exists()
                   and not out.is_relative_to(study) and not study.is_relative_to(out), 'fresh separate outputs folder')
    protocol, rows = verify.terminal_bindings(study)
    original = verify.read(prospective / 'manifest.json')
    verify.require(original['status'] == 'prospective' and original['protocol_sha256'] == verify.PROTOCOL,
                   'unchanged prospective archive required')
    verify.manifest_files(prospective, original)
    verify.require(verify.sha(prospective / 'protocol.json') == verify.PROTOCOL, 'prospective protocol')
    verify.require(args.readme.read_bytes() != (prospective / 'README.md').read_bytes(), 'terminal README required')
    out.mkdir(parents=True)
    try:
        for name in (*original['files'], 'manifest.json'):
            copy(verify.checked(prospective, name), verify.checked(out, name))
        history = out / 'registration_history'
        history.mkdir(exist_ok=False)
        for name in verify.VERSIONS:
            shutil.move(out / name, history / name)
        # Keep all top-level runtime logs/receipts and every native run/checkpoint/startup/raw file.
        for source in sorted(study.iterdir()):
            if source.is_file() and source.suffix in ROOT_SUFFIXES and source.name not in verify.VERSIONS:
                copy(source, out / source.name)
        for name in ('runs', 'execution', 'reviews', 'raw', 'scored'):
            verify.require((study / name).is_dir(), 'missing terminal evidence tree: ' + name)
            tree(study / name, out / name)
        for name in ('terminal_audit', 'terminal_selection_audit', 'terminal_tables'):
            if (study / name).is_dir():
                tree(study / name, out / name)
        for name in args.include:
            source = verify.checked(study, name)
            destination = verify.checked(out, name)
            tree(source, destination) if source.is_dir() else copy(source, destination)
        copy(args.readme.resolve(), out / 'README.md')
        copy(args.report.resolve(), out / 'REPORT.md')
        copy(HERE / 'verify.py', out / 'verify.py')
        tree(HERE, out / 'terminal_package')
        if args.snapshot_production:
            for name, digest in protocol['production_pins'].items():
                data = subprocess.check_output(['git', 'show', verify.REVISION + ':' + name], cwd=verify.ROOT)
                verify.require(hashlib.sha256(data).hexdigest() == digest, 'committed production pin: ' + name)
                destination = verify.checked(out / 'production', name)
                destination.parent.mkdir(parents=True, exist_ok=True)
                with destination.open('xb') as stream:
                    stream.write(data)
        save(out / 'packaging_receipt.json', dict(status='staged', protocol_sha256=verify.PROTOCOL,
            prospective_manifest_sha256=verify.sha(history / 'manifest.json'),
            summary_sha256=verify.sha(out / 'summary.json'), helper_sha256=verify.sha(__file__),
            source_revision=verify.REVISION, raw_scored_files=rows,
            wall_seconds_before_verification=time.monotonic() - started,
            simulator_calls=0, builds=0, random_draws=0))
        records = {name: dict(sha256=verify.sha(out / name), bytes=(out / name).stat().st_size)
                   for name in sorted(verify.files(out))}
        save(out / 'manifest.json', dict(status='complete', protocol_sha256=verify.PROTOCOL,
            research_lives=30796, startup_lives=12, total_calls=30808, files=records))
        return verify.verify(out)
    except BaseException as error:
        save(out / 'packaging_failure.json', dict(status='failed', error=repr(error),
             simulator_calls=0, builds=0, random_draws=0))
        raise


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--study', type=Path, default=HERE.parent)
    parser.add_argument('--out', type=Path, required=True)
    parser.add_argument('--readme', type=Path, required=True)
    parser.add_argument('--report', type=Path, required=True)
    parser.add_argument('--snapshot-production', action='store_true',
                        help='copy every pinned production source from git')
    parser.add_argument('--include', action='append', default=[], help='additional study-relative evidence')
    print(json.dumps(pack(parser.parse_args()), indent=2))
