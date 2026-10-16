"""Prospective delayed-match information blocks 144/145 audit; seed payloads only, no engine imports."""
from __future__ import annotations

import hashlib
import io
import json
import os
from pathlib import Path
import re
import subprocess
import zipfile

import numpy as np

ROOT = Path(__file__).resolve().parents[2]
OUT = Path(__file__).resolve().parent
AJ = ROOT / 'outputs/audit_population_depth_20261015/namespace'
STUDY = OUT
AK = ROOT / 'outputs/cumulative_capability_20261015/operations'
LOW, HIGH = 52440000, 52460000
BASELINE = ROOT / "outputs/delayed_match_baseline_20261015"
SKIP = {'.git', '.venv', '__pycache__', 'node_modules', '.pytest_cache'}


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def read(path):
    return json.loads(path.read_text())


def stat(path):
    value = path.stat()
    return {key: getattr(value, 'st_' + key) for key in ('size', 'mtime_ns', 'ctime_ns', 'dev', 'ino')}


def seed_member(name):
    return name.endswith('.npy') and re.search(r'(^|[^A-Za-z0-9])seeds?(?=$|[^A-Za-z0-9])', name[:-4], re.I)


def excluded(path):
    return path.is_relative_to(OUT) or path.is_relative_to(BASELINE)



def main():
    if any((STUDY / name).exists() for name in ('protocol.json', 'registration.json', 'release.json', 'raw')):
        raise ValueError('candidate audit must precede current-study preparation/release')
    reservation = read(BASELINE / "reservation.json")
    assert reservation["seed_blocks"] == [[52430000, 52440000]]
    assert reservation["status"] == "reserved_development_only"
    native_records, native = [], set()
    refs = read(AJ / 'history_references.json')['content_by_sha256']
    prior, sources = {}, {}
    # The exact accepted historical inventories remain at their committed paths.
    # Their earlier no-overlap conclusions are NOT reused for this different block.
    for digest, item in refs.items():
        path = ROOT / item['repository_path']
        if sha(path) != digest:
            raise ValueError('historical inventory bytes changed')
        value = read(path)
        records = value.get('records') if digest == 'b5fbb637071e0bebae670b532742c4e8dec33cf05c7d6399419f06bb3daffb58' else None
        records = records if records is not None else value.get('changed_npz_records', value.get('new_or_modified_npz_records'))
        if records is not None:
            prior.update(records)
            sources[str(path.relative_to(ROOT))] = digest
    for name in ('candidate_namespace_inventory.json', 'final_namespace_delta.json'):
        path = AJ / name
        value = read(path)
        prior.update(value.get('changed_npz_records', value.get('new_or_modified_npz_records', {})))
        sources[str(path.relative_to(ROOT))] = sha(path)
    latest = AK / 'candidate_seed_inventory.json'
    latest_data = read(latest)
    prior.update(latest_data['changed_npz_records'])
    sources[str(latest.relative_to(ROOT))] = sha(latest)
    prior_AL = ROOT / 'outputs/audit_retention_selection_20261015/operations/candidate_seed_inventory.json'
    prior.update(read(prior_AL)['changed_npz_records'])
    sources[str(prior_AL.relative_to(ROOT))] = sha(prior_AL)
    prior_AM = ROOT / 'outputs/audit_capture_value_selection_20261015/operations/candidate_seed_inventory.json'
    prior.update(read(prior_AM)['changed_npz_records'])
    sources[str(prior_AM.relative_to(ROOT))] = sha(prior_AM)
    prior_AN = ROOT / 'outputs/audit_occlusion_acquisition_20261015/operations/candidate_seed_inventory.json'
    prior.update(read(prior_AN)['changed_npz_records'])
    sources[str(prior_AN.relative_to(ROOT))] = sha(prior_AN)
    prior_AO = ROOT / 'outputs/audit_retained_depth_20261015/new_prepare_prep/candidate_seed_inventory.json'
    prior.update(read(prior_AO)['changed_npz_records'])
    sources[str(prior_AO.relative_to(ROOT))] = sha(prior_AO)
    prior_baseline = BASELINE / "candidate_seed_inventory.json"
    prior.update(read(prior_baseline)["changed_npz_records"])
    sources[str(prior_baseline.relative_to(ROOT))] = sha(prior_baseline)
    current = {}
    for top in (ROOT / 'results', ROOT / 'outputs'):
        for folder, dirs, names in os.walk(top, followlinks=False):
            base = Path(folder)
            dirs[:] = sorted(n for n in dirs if n not in SKIP and not excluded(base / n))
            for name in sorted(names):
                path = base / name
                if name.endswith('.npz'):
                    current[str(path.relative_to(ROOT))] = stat(path)
    unchanged = {p for p, s in current.items() if p in prior and prior[p].get('stat') == s}
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
            hits = sorted({int(x) for x in array.flat if LOW <= int(x) < HIGH or int(x) in native})
            payloads[digest] = {'representative_path': path, 'member': name, 'dtype': str(array.dtype),
                                'shape': list(array.shape), 'count': int(array.size), 'matches': hits}
        if payloads[digest]['matches']:
            matches.append({'path': path, 'member': name, 'values': payloads[digest]['matches']})
        return digest

    for digest, members in sorted(groups.items()):
        path, name = sorted(members)[0]
        with zipfile.ZipFile(ROOT / path) as archive:
            inspect(archive.read(name), path, name, digest)
        if stat(ROOT / path) != current[path]:
            raise ValueError('representative changed during audit')
    for path in sorted(set(current) - unchanged):
        item = {'stat': current[path], 'seed_members': {},
                'synthetic_fixture': any(x.startswith('test_') for x in Path(path).parts)}
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
            errors.append({'path': path, 'error': item['error'], 'synthetic_fixture': item['synthetic_fixture']})
    pattern = r'(?<![0-9.])(?:524[45][0-9]{4}|52460000)(?![0-9.])'
    found = subprocess.run(['rg', '--no-ignore', '-l', '-0', '-P', '--glob', '*.json',
        '--glob', '!**/test_*/**', '--glob', '!**/__pycache__/**', pattern, 'results', 'outputs'],
        cwd=ROOT, capture_output=True)
    if found.returncode not in (0, 1):
        raise ValueError(found.stderr.decode())
    json_pins, json_hits, json_errors = {}, [], []

    def walk(value, trail, path):
        if isinstance(value, dict):
            for key, item in value.items():
                if str(key).isdecimal() and (LOW <= int(key) <= HIGH or int(key) in native):
                    json_hits.append({'path': path, 'field': '.'.join(trail), 'kind': 'key', 'value': int(key)})
                walk(item, trail + [str(key)], path)
        elif isinstance(value, list):
            for i, item in enumerate(value):
                walk(item, trail + [str(i)], path)
        elif ((isinstance(value, int) and not isinstance(value, bool))
              or isinstance(value, str) and value.isdecimal()):
            if (LOW <= int(value) <= HIGH or int(value) in native):
                json_hits.append({'path': path, 'field': '.'.join(trail), 'value': int(value)})

    for raw in sorted(set(found.stdout.split(b'\0')) - {b''}):
        path = raw.decode()
        if excluded(ROOT / path):
            continue
        try:
            json_pins[path] = sha(ROOT / path)
            walk(read(ROOT / path), [], path)
        except (OSError, ValueError) as error:
            json_errors.append({'path': path, 'error': str(error)})
    text = subprocess.run(['rg', '--no-ignore', '-n', '-P', '--glob', '*.py', '--glob', '*.md',
        '--glob', '*.yaml', '--glob', '!**/test_*/**',
        r'52[_,]?4[45][0-9_,]*|(?:block|fresh_seeds|reserve).{0,35}\b(?:144|145)\b',
        'results', 'outputs', 'docs'], cwd=ROOT, capture_output=True)
    if text.returncode not in (0, 1):
        raise ValueError(text.stderr.decode())
    lines = [line for line in text.stdout.decode().splitlines() if not excluded(ROOT / line.split(':', 1)[0])]
    (OUT / 'candidate_text_matches.txt').write_text('\n'.join(lines) + '\n')
    result = {'status': 'pending_literal_classification', 'reserved': False, 'registered': False,
        'baseline_reservation_sha256': sha(BASELINE / 'reservation.json'), 'excluded_running_baseline': str(BASELINE.relative_to(ROOT)), 'native_seed': None, 'native_records': native_records, 'run_life_seeds': {},
        'candidate_seeds': list(range(LOW, LOW + 64)) + list(range(52450000, 52450512)), 'whole_block_half_open': [LOW, HIGH],
        'prior_inventory_pins': sources, 'current_npz_paths': len(current), 'unchanged_npz_paths': len(unchanged),
        'unchanged_seed_members_covered': sum(map(len, groups.values())),
        'distinct_unchanged_payloads_reopened': len(groups), 'payload_reviews': payloads,
        'changed_npz_records': delta, 'NPZ_matches': matches, 'NPZ_errors': errors,
        'JSON_source_pins': json_pins, 'JSON_hits': json_hits, 'JSON_errors': json_errors,
        'text_matches_sha256': sha(OUT / 'candidate_text_matches.txt'), 'text_match_count': len(lines),
        'script_sha256': sha(Path(__file__)), 'native_source_pins': {name: sha(ROOT / name) for name in ('src/life/spec.py', 'src/life/evaluate.py')}, 'held_AJ_seed_audit_sha256': sha(AJ / 'seed_audit.json'), 'simulation_calls': 0, 'genetic_draws': 0,
        'limitations': ['Recorded stat tuples permit reuse of payload membership, not earlier no-collision conclusions.',
            'Every distinct unchanged seed payload is reopened for blocks 144/145; new or changed NPZ seed members are read.',
            'Own candidate preparation is excluded; the running baseline directory is skipped because its explicit reserved block143 is disjoint. AJ is only a proposal, not a reservation.',
            'Full NPZ outcome/genotype arrays are not loaded. Whole-block and literal declarations are separately reviewed.']}
    (OUT / 'candidate_seed_inventory.json').write_text(json.dumps(result, indent=2) + '\n')
    print(json.dumps({key: result[key] for key in ('status', 'current_npz_paths', 'unchanged_npz_paths',
        'unchanged_seed_members_covered', 'distinct_unchanged_payloads_reopened', 'text_match_count')}, indent=2))
    print(json.dumps({'NPZ_matches': len(matches), 'NPZ_errors': errors, 'JSON_hits': len(json_hits),
                      'JSON_errors': json_errors, 'changed_npz': len(delta)}, indent=2))


if __name__ == '__main__':
    main()
