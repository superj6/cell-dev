"""Candidate-only block151 audit using the accepted inventory cache; no reservation or engine import."""
from __future__ import annotations

import argparse
import hashlib
import io
import json
import os
import re
import resource
import signal
import subprocess
import time
import zipfile
from pathlib import Path

import numpy as np

ROOT = Path(__file__).resolve().parents[3]
OUT = Path(__file__).resolve().parent
STUDY = OUT.parent
PRIOR = ROOT / 'results/resource_patch_selection_20261015/namespace/candidate_seed_inventory.json'
REVISION = '5d556443e91d558de8de27ab2e5dc7ae11a51415'
LOW, HIGH = 52510000, 52520000
SKIP = {'.git', '.venv', '__pycache__', 'node_modules', '.pytest_cache'}


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def read(path):
    return json.loads(Path(path).read_text())


def stat(path):
    value = Path(path).stat()
    return {key: getattr(value, 'st_' + key) for key in ('size', 'mtime_ns', 'ctime_ns', 'dev', 'ino')}


def seed_member(name):
    return name.endswith('.npy') and re.search(r'(^|[^A-Za-z0-9])seeds?(?=$|[^A-Za-z0-9])', name[:-4], re.I)


def excluded(path):
    return path.is_relative_to(STUDY)


def save(path, value):
    with path.open('x') as stream:
        json.dump(value, stream, indent=2)
        stream.write('\n')


def main():
    started, cpu = time.monotonic(), time.process_time()
    if any((STUDY / name).exists() for name in ('inputs', 'protocol.json', 'reservation.json', 'release.json', 'raw')):
        raise ValueError('candidate audit must precede input materialization/reservation/release')
    if any((OUT / name).exists() for name in ('candidate_seed_inventory.json', 'candidate_text_matches.txt')):
        raise ValueError('first audit requires absent output artifacts')
    head = subprocess.check_output(['git', 'rev-parse', 'HEAD'], cwd=ROOT, text=True).strip()
    if head != REVISION:
        raise ValueError('completed comparison/viewer milestone revision differs')
    accepted = read(PRIOR)
    prior, sources = {}, dict(accepted['prior_inventory_pins'])
    sources[str(PRIOR.relative_to(ROOT))] = sha(PRIOR)
    # Reuse only stat-to-payload membership. Reopen every distinct payload for the NEW block.
    for name, digest in sources.items():
        path = ROOT / name
        if sha(path) != digest:
            raise ValueError('historical inventory bytes differ: ' + name)
        value = read(path)
        records = value.get('changed_npz_records', value.get('new_or_modified_npz_records', value.get('records', {})))
        if not isinstance(records, dict) or any(not isinstance(row, dict) or 'stat' not in row
                                                for row in records.values()):
            raise ValueError('historical membership schema differs: ' + name)
        prior.update(records)
    current = {}
    for top in (ROOT / 'results', ROOT / 'outputs'):
        for folder, dirs, names in os.walk(top, followlinks=False):
            base = Path(folder)
            dirs[:] = sorted(n for n in dirs if n not in SKIP and not excluded(base / n))
            for name in sorted(names):
                path = base / name
                if name.endswith('.npz'):
                    current[str(path.relative_to(ROOT))] = stat(path)
    unchanged = {p for p, s in current.items()
                 if p in prior and prior[p].get('stat') == s and not prior[p].get('error')}
    groups = {}
    for path in unchanged:
        for name, value in prior[path].get('seed_members', {}).items():
            digest = value if isinstance(value, str) else value.get('npy_sha256', value.get('sha256'))
            if seed_member(name) and digest:
                groups.setdefault(digest, []).append((path, name))
    payloads, matches, errors, delta = {}, [], [], {}

    def inspect(raw, path, name, expected=None):
        digest = hashlib.sha256(raw).hexdigest()
        if expected is not None and digest != expected:
            raise ValueError('historical representative payload changed')
        if digest not in payloads:
            array = np.load(io.BytesIO(raw), allow_pickle=False)
            if (not isinstance(array, np.ndarray) or not np.issubdtype(array.dtype, np.number)
                    or not np.isfinite(array).all() or np.any(array != np.floor(array))):
                raise ValueError('invalid numeric integer seed payload')
            hits = sorted({int(x) for x in array.flat if LOW <= int(x) < HIGH})
            payloads[digest] = dict(representative_path=path, member=name, dtype=str(array.dtype),
                                    shape=list(array.shape), count=int(array.size), matches=hits)
        if payloads[digest]['matches']:
            matches.append(dict(path=path, member=name, values=payloads[digest]['matches']))
        return digest

    for digest, members in sorted(groups.items()):
        path, name = sorted(members)[0]
        with zipfile.ZipFile(ROOT / path) as archive:
            inspect(archive.read(name), path, name, digest)
        if stat(ROOT / path) != current[path]:
            raise ValueError('representative changed during audit')
    for path in sorted(set(current) - unchanged):
        item = dict(stat=current[path], seed_members={},
                    synthetic_fixture=any(x.startswith('test_') for x in Path(path).parts))
        delta[path] = item
        try:
            with zipfile.ZipFile(ROOT / path) as archive:
                for info in archive.infolist():
                    if seed_member(info.filename):
                        if info.filename in item['seed_members']:
                            raise ValueError('duplicate seed member')
                        item['seed_members'][info.filename] = inspect(archive.read(info), path, info.filename)
            if stat(ROOT / path) != current[path]:
                raise ValueError('NPZ changed during audit')
        except (OSError, ValueError, zipfile.BadZipFile, EOFError) as error:
            item['error'] = type(error).__name__ + ': ' + str(error)
            errors.append(dict(path=path, error=item['error'], synthetic_fixture=item['synthetic_fixture']))
    pattern = r'(?<![0-9.])(?:5251[0-9]{4}|52520000)(?![0-9.])'
    found = subprocess.run(['rg', '--no-ignore', '-l', '-0', '-P', '--glob', '*.json',
        '--glob', '!**/test_*/**', '--glob', '!**/__pycache__/**', pattern, 'results', 'outputs'],
        cwd=ROOT, capture_output=True)
    if found.returncode not in (0, 1):
        raise ValueError(found.stderr.decode())
    json_pins, json_hits, json_errors = {}, [], []

    def walk(value, trail, path):
        if isinstance(value, dict):
            for key, item in value.items():
                if str(key).isdecimal() and LOW <= int(key) <= HIGH:
                    json_hits.append(dict(path=path, field='.'.join(trail), kind='key', value=int(key)))
                walk(item, trail + [str(key)], path)
        elif isinstance(value, list):
            for i, item in enumerate(value):
                walk(item, trail + [str(i)], path)
        elif ((isinstance(value, int) and not isinstance(value, bool))
              or isinstance(value, str) and value.isdecimal()):
            if LOW <= int(value) <= HIGH:
                json_hits.append(dict(path=path, field='.'.join(trail), value=int(value)))

    for raw in sorted(set(found.stdout.split(b'\0')) - {b''}):
        path = raw.decode()
        if excluded(ROOT / path):
            continue
        try:
            json_pins[path] = sha(ROOT / path)
            walk(read(ROOT / path), [], path)
        except (OSError, ValueError) as error:
            json_errors.append(dict(path=path, error=str(error)))
    text = subprocess.run(['rg', '--no-ignore', '-n', '-P', '--glob', '*.py', '--glob', '*.md',
        '--glob', '*.yaml', '--glob', '*.html', '--glob', '*.js', '--glob', '!**/test_*/**',
        r'(?<![0-9.])52[_,]?(?:51[0-9_,]*|520[0-9_,]*)(?![0-9.])|(?:block|fresh_seeds|reserve).{0,35}\b151\b',
        'results', 'outputs', 'docs'], cwd=ROOT, capture_output=True)
    if text.returncode not in (0, 1):
        raise ValueError(text.stderr.decode())
    lines = [line for line in text.stdout.decode().splitlines() if not excluded(ROOT / line.split(':', 1)[0])]
    with (OUT / 'candidate_text_matches.txt').open('x') as stream:
        stream.write('\n'.join(lines) + '\n')
    result = dict(status='pending_literal_classification', reserved=False, registered=False,
        source_revision=REVISION, candidate_seeds=list(range(LOW, LOW + 32)), whole_block_half_open=[LOW, HIGH],
        prior_inventory_pins=sources, current_npz_paths=len(current), unchanged_npz_paths=len(unchanged),
        unchanged_seed_members_covered=sum(map(len, groups.values())), distinct_unchanged_payloads_reopened=len(groups),
        payload_reviews=payloads, changed_npz_records=delta, NPZ_matches=matches, NPZ_errors=errors,
        JSON_source_pins=json_pins, JSON_hits=json_hits, JSON_errors=json_errors,
        text_matches_sha256=sha(OUT / 'candidate_text_matches.txt'), text_match_count=len(lines),
        script_sha256=sha(Path(__file__)), simulation_calls=0, engine_builds=0, genetic_draws=0,
        resources=dict(cpu_seconds=time.process_time()-cpu, wall_seconds=time.monotonic()-started,
                       peak_rss_bytes=resource.getrusage(resource.RUSAGE_SELF).ru_maxrss*1024),
        limitations=[
            'Stat cache reuses membership, not earlier no-collision conclusions; distinct payloads are reopened.',
            'Every new or changed NPZ is examined, including completed comparison and viewer exports.',
            'Only seed payloads are loaded; label text and JSON declarations require separate literal review.',
            'This own unexecuted study directory is excluded; no seed block is reserved by this audit.',
            'Candidate IDs are development only; no genetic seed is used.'])
    save(OUT / 'candidate_seed_inventory.json', result)
    print(json.dumps({key: result[key] for key in ('status', 'current_npz_paths', 'unchanged_npz_paths',
        'distinct_unchanged_payloads_reopened', 'text_match_count', 'resources')}))
    print(json.dumps(dict(NPZ_matches=len(matches), NPZ_errors=errors, JSON_hits=len(json_hits), JSON_errors=json_errors)))


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--run', action='store_true')
    args = parser.parse_args()
    if args.run:
        os.sched_setaffinity(0, {min(os.sched_getaffinity(0))})
        resource.setrlimit(resource.RLIMIT_CPU, (40, 40))
        resource.setrlimit(resource.RLIMIT_AS, (2*1024**3, 2*1024**3))
        signal.alarm(60)
        available = next(int(line.split()[1])*1024 for line in Path('/proc/meminfo').read_text().splitlines()
                         if line.startswith('MemAvailable:'))
        if available < 4*1024**3:
            raise ValueError('4GiB host headroom required')
        main()
    else:
        print('Source only: block151 not scanned or reserved.')
