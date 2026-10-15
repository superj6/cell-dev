"""AA post-Z namespace delta. Read only actual seed members; never reserve or simulate."""
from __future__ import annotations

import hashlib
import importlib.util
import io
import json
import os
from pathlib import Path
import subprocess
import zipfile

import numpy as np

ROOT = Path(__file__).resolve().parents[2]
OUT = Path(__file__).resolve().parent
Z = ROOT / 'outputs/autonomous_visibility_continuation_20261014'
LOW, HIGH = 52_210_000, 52_220_000


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def read(path):
    return json.loads(path.read_text())


def main():
    baseline_path = OUT / 'npz_seed_baseline.json'
    assert sha(baseline_path) == 'b5fbb637071e0bebae670b532742c4e8dec33cf05c7d6399419f06bb3daffb58'
    prior = read(baseline_path)['records']
    classification = read(OUT / 'npz_seed_classification.json')
    assert classification['unexplained_nonfixture_errors'] == 0 and classification['numeric_seed_matches'] == 0
    budget, clearance = read(Z / 'budget.json'), read(Z / 'terminal_process_clearance.json')
    assert budget['status'] == 'complete' and not budget['running'] and not budget['queued'] and not budget.get('cleanup_error')
    assert clearance['all_processes_exited'] and clearance['budget_sha256'] == sha(Z / 'budget.json')
    spec = importlib.util.spec_from_file_location('AA_seed_only', OUT / 'npz_seed_inventory.py')
    helper = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(helper)
    seen, changed, matches, errors = set(), {}, [], []
    unchanged = arrays = 0
    for top in (ROOT / 'results', ROOT / 'outputs'):
        for folder, dirs, names in os.walk(top, followlinks=False):
            base = Path(folder)
            dirs[:] = sorted(n for n in dirs if n not in helper.SKIP
                              and not (base / n).is_relative_to(OUT)
                              and not (base / n).is_relative_to(ROOT / 'outputs/autonomous_visibility_lateral_20261014'))
            for name in sorted(names):
                if not name.endswith('.npz'):
                    continue
                path = base / name
                relative = str(path.relative_to(ROOT))
                seen.add(relative)
                stat = helper.stat_record(path)
                if relative in prior and prior[relative].get('stat') == stat:
                    unchanged += 1
                    continue
                record = {'change': 'modified' if relative in prior else 'added', 'stat': stat,
                          'synthetic_fixture': any(p.startswith('test_') for p in path.parts), 'seed_members': {}}
                changed[relative] = record
                try:
                    with zipfile.ZipFile(path) as archive:
                        for info in archive.infolist():
                            if not helper.seed_member(info.filename.lower()):
                                continue
                            if info.filename in record['seed_members']:
                                raise ValueError('duplicate seed member')
                            payload = archive.read(info)
                            value = np.load(io.BytesIO(payload), allow_pickle=False)
                            if not np.issubdtype(value.dtype, np.number) or not np.isfinite(value).all():
                                raise ValueError('invalid seed member')
                            if not np.issubdtype(value.dtype, np.integer) and np.any(value != np.floor(value)):
                                raise ValueError('non-integral seed member')
                            arrays += 1
                            record['seed_members'][info.filename] = {'sha256': hashlib.sha256(payload).hexdigest(),
                                'dtype': str(value.dtype), 'shape': list(value.shape)}
                            for item in value[(value >= LOW) & (value < HIGH)].flat:
                                matches.append({'path': relative, 'member': info.filename, 'value': int(item)})
                    if helper.stat_record(path) != stat:
                        raise ValueError('changed while scanning')
                except (OSError, ValueError, zipfile.BadZipFile, EOFError) as error:
                    errors.append({'path': relative, 'error': type(error).__name__ + ': ' + str(error),
                                   'synthetic_fixture': record['synthetic_fixture']})
    # Literal JSON range check, including the proposed upper endpoint for explicit classification.
    command = ['rg', '-l', '-0', '-P', '--glob', '*.json', '--glob', '!**/test_*/**',
               r'(?<![0-9.])522[12][0-9]{4}(?![0-9.])', 'results', 'outputs']
    result = subprocess.run(command, cwd=ROOT, capture_output=True, check=False)
    assert result.returncode in (0, 1)
    json_matches, json_pins = [], {}
    def visit(value, trail, path):
        if isinstance(value, dict):
            for key, item in value.items():
                visit(item, trail + [str(key)], path)
        elif isinstance(value, list):
            for i, item in enumerate(value):
                visit(item, trail + [str(i)], path)
        elif isinstance(value, int) and not isinstance(value, bool) and LOW <= value <= HIGH:
            json_matches.append({'path': path, 'field': '.'.join(trail), 'value': value})
    for name in sorted(set(x.decode() for x in result.stdout.split(b'\0') if x)):
        path = ROOT / name
        if path.is_relative_to(OUT) or path.is_relative_to(ROOT / 'outputs/autonomous_visibility_lateral_20261014'):
            continue
        value = read(path)
        json_pins[name] = sha(path)
        visit(value, [], name)
    assert not matches and not [x for x in errors if not x['synthetic_fixture']]
    for match in json_matches:
        assert match['value'] == LOW and match['field'] in (
            'whole_block_checked_half_open.1', 'proposed_whole_block.1', 'candidate_whole_blocks_half_open.0.1')
    delta = {'status': 'passed', 'prior_baseline_sha256': sha(baseline_path),
             'Z_terminal_budget_sha256': sha(Z / 'budget.json'), 'Z_terminal_clearance_sha256': sha(Z / 'terminal_process_clearance.json'),
             'whole_block_half_open': [LOW, HIGH], 'current_npz_paths': len(seen), 'unchanged_npz_paths': unchanged,
             'changed_npz_records': changed, 'removed_npz_paths': sorted(set(prior) - seen),
             'changed_seed_members_checked': arrays, 'numeric_matches': matches, 'errors': errors,
             'JSON_literal_source_pins': json_pins, 'JSON_numeric_matches': json_matches,
             'JSON_match_classification': 'All matches are the exclusive upper endpoint of prior block120.',
             'text_match_classification': 'Three copies of block120 exclusive upper endpoint; one historical block121 uses base43M, yielding44,210,000..44,210,095, disjoint from proposed base51M block121.',
             'limits': 'Unchanged NPZ reuse is based on recorded filesystem identity/stat tuple and immutable published evidence, not full-NPZ content hashes. Exact seed payload hashes are retained. AA own audit/source preparation and synthetic JSON test trees are excluded. No scientific outcome members are opened by this delta.',
             'simulation_calls': 0, 'compilation_calls': 0, 'reserved': False}
    (OUT / 'final_namespace_delta.json').write_text(json.dumps(delta, indent=2) + '\n')
    print(json.dumps({'status': 'passed', 'current_npz_paths': len(seen), 'unchanged': unchanged,
                      'added_or_changed': len(changed), 'changed_seed_members': arrays,
                      'removed': len(set(prior) - seen), 'matches': 0, 'JSON_endpoint_matches': len(json_matches),
                      'delta_sha256': sha(OUT / 'final_namespace_delta.json')}, indent=2))


if __name__ == '__main__':
    main()
