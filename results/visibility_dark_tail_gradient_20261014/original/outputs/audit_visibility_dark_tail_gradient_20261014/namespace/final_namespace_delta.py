"""Final AG same-candidate delta after source/fixture freeze; seed metadata only."""
from pathlib import Path
import ast
import hashlib
import importlib.util
import io
import json
import os
import subprocess
import zipfile
import numpy as np

ROOT = Path(__file__).resolve().parents[3]
OUT = Path(__file__).resolve().parent
CURRENT = ROOT / 'outputs/autonomous_visibility_dark_tail_gradient_20261014'
AF = ROOT / 'outputs/autonomous_prediction_continuation_20261014'
LOW, HIGH = 52_320_000, 52_350_000


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def read(path):
    return json.loads(path.read_text())


def main():
    candidate = read(OUT / 'candidate_namespace_review.json')
    inventory = read(OUT / 'candidate_namespace_inventory.json')
    assert candidate['status'] == 'passed_candidate_pending_final_delta'
    assert sha(OUT / 'candidate_namespace_inventory.json') == candidate['inventory_sha256']
    assert not any((CURRENT / name).exists() for name in ('registration.json', 'seed_audit.json', 'inputs', 'protocol.json', 'ready.json'))
    for item in candidate['synthetic_errors_classified']:
        assert sha(ROOT / item['path']) == item['sha256']
    reader = OUT.parent / 'reader_source_review.json'
    peer = OUT.parent / 'analyzer_peer_review.json'
    assert sha(reader) == 'da57360bd062724060a2a42f524953454c7d80619669461ffd64fb8fa19c09e7'
    peer_record = read(peer)
    assert any(word in peer_record['status'] for word in ('passed', 'approved'))
    budget, clearance = read(AF / 'budget.json'), read(AF / 'terminal_process_clearance.json')
    assert budget['status'] == 'complete' and not budget['running'] and not budget['queued'] and not budget.get('cleanup_error')
    assert clearance['status'] == 'cleared' and clearance['all_processes_exited'] and clearance['budget_sha256'] == sha(AF / 'budget.json')
    module = importlib.util.spec_from_file_location('ag_seed_predicates', OUT / 'namespace_audit.py')
    h = importlib.util.module_from_spec(module)
    module.loader.exec_module(h)
    prior = {}
    for relative, digest in inventory['baseline_sources'].items():
        path = ROOT / relative
        assert sha(path) == digest
        value = read(path)
        prior.update(value.get('records', value.get('changed_npz_records', value.get('new_or_modified_npz_records'))))
    prior.update(inventory['changed_npz_records'])
    changed, seen, matches, errors = {}, set(), [], []
    unchanged = arrays = 0
    for top in (ROOT / 'results', ROOT / 'outputs'):
        for folder, dirs, names in os.walk(top, followlinks=False):
            base = Path(folder)
            dirs[:] = sorted(n for n in dirs if n not in h.SKIP and not h.excluded(base / n))
            for name in sorted(names):
                if not name.endswith('.npz'):
                    continue
                path = base / name
                relative, state = str(path.relative_to(ROOT)), h.stat(path)
                seen.add(relative)
                if relative in prior and prior[relative].get('stat') == state:
                    unchanged += 1
                    continue
                record = {'stat': state, 'synthetic_fixture': any(p.startswith('test_') for p in path.parts), 'seed_members': {}}
                changed[relative] = record
                try:
                    with zipfile.ZipFile(path) as archive:
                        for item in archive.infolist():
                            if not h.seed_member(item.filename):
                                continue
                            assert item.filename not in record['seed_members']
                            raw = archive.read(item)
                            values = np.load(io.BytesIO(raw), allow_pickle=False)
                            if (not np.issubdtype(values.dtype, np.number) or not np.isfinite(values).all()
                                    or (not np.issubdtype(values.dtype, np.integer) and np.any(values != np.floor(values)))):
                                raise ValueError('invalid seed member')
                            arrays += 1
                            record['seed_members'][item.filename] = {'sha256': hashlib.sha256(raw).hexdigest(),
                                'shape': list(values.shape), 'dtype': str(values.dtype)}
                            hits = sorted({int(x) for x in values.flat if LOW <= int(x) < HIGH})
                            if hits:
                                matches.append({'path': relative, 'member': item.filename, 'values': hits})
                    if h.stat(path) != state:
                        raise ValueError('file changed during final delta')
                except (OSError, ValueError, zipfile.BadZipFile, EOFError) as error:
                    errors.append({'path': relative, 'error': type(error).__name__ + ': ' + str(error)})
    found = subprocess.run(['rg', '--no-ignore', '-l', '-0', '-P', '--glob', '*.json', '--glob', '!**/test_*/**',
        r'(?<![0-9.])523[2345][0-9]{4}(?![0-9.])', 'results', 'outputs'], cwd=ROOT, capture_output=True)
    assert found.returncode in (0, 1)
    pins, hits, string_hits, json_errors = {}, [], [], []

    def visit(value, trail, path):
        if isinstance(value, dict):
            for key, item in value.items():
                if key.isdecimal() and LOW <= int(key) <= HIGH:
                    string_hits.append({'path': path, 'field': '.'.join(trail), 'kind': 'key', 'value': key})
                visit(item, trail + [key], path)
        elif isinstance(value, list):
            for i, item in enumerate(value):
                visit(item, trail + [str(i)], path)
        elif type(value) is int and LOW <= value <= HIGH:
            hits.append({'path': path, 'field': '.'.join(trail), 'value': value})
        elif isinstance(value, str) and value.isdecimal() and LOW <= int(value) <= HIGH:
            string_hits.append({'path': path, 'field': '.'.join(trail), 'kind': 'value', 'value': value})

    for raw in sorted(set(found.stdout.split(b'\0')) - {b''}):
        relative = raw.decode()
        path = ROOT / relative
        if h.excluded(path):
            continue
        try:
            pins[relative] = sha(path)
            visit(read(path), [], relative)
        except (OSError, ValueError) as error:
            json_errors.append({'path': relative, 'error': str(error)})
    allowed = {'whole_blocks_half_open.0.1', 'whole_block_half_open.1', 'same_whole_blocks_half_open.0.1'}
    assert all(item['value'] == LOW and item['field'] in allowed and 'prediction_continuation_20261014' in item['path'] for item in hits)
    assert not matches and not errors and not json_errors and not string_hits
    root_register = OUT.parent / 'register_study.py'
    expression = next(node.value for node in ast.parse(root_register.read_text()).body
                      if isinstance(node, ast.Assign)
                      and any(isinstance(target, ast.Name) and target.id == 'expected' for target in node.targets))
    expected = eval(compile(ast.Expression(expression), str(root_register), 'eval'),
                    {'__builtins__': {}, 'list': list, 'range': range})
    assert expected == candidate['seeds']
    # The root draft exists now but has not registered anything. Its literal
    # candidates are explicitly classified rather than treated as prior use.
    text = subprocess.run(['rg', '--no-ignore', '-n', '-P', '--glob', '*.py', '--glob', '*.md', '--glob', '*.yaml',
        '--glob', '!**/test_*/**', r'52[_,]?3[2345][0-9_,]*|(?:block|fresh_seeds|reserve).{0,35}\b13[234]\b',
        'results', 'outputs', 'docs'], cwd=ROOT, capture_output=True)
    assert text.returncode in (0, 1)
    textlines = [line for line in text.stdout.decode().splitlines() if not h.excluded(ROOT / line.split(':', 1)[0])]
    previous_text = set((OUT / 'candidate_text_matches.txt').read_text().splitlines())
    new_text = sorted(set(textlines) - previous_text)
    assert all(line.startswith(str(root_register.relative_to(ROOT)) + ':') for line in new_text), new_text
    (OUT / 'final_text_matches.txt').write_text('\n'.join(textlines) + '\n')
    result = {'status': 'passed', 'registered': False, 'reserved': False,
        'candidate_review_sha256': sha(OUT / 'candidate_namespace_review.json'),
        'candidate_inventory_sha256': sha(OUT / 'candidate_namespace_inventory.json'),
        'same_whole_blocks_half_open': candidate['whole_blocks_half_open'], 'seeds': candidate['seeds'],
        'source_pins': {str(path.relative_to(ROOT)): sha(path) for path in
            (Path(__file__), reader, peer, OUT.parent / 'source_preparation_review.json', OUT.parent / 'independent_source_design_review.json',
             AF / 'budget.json', AF / 'terminal_process_clearance.json', AF / 'seed_audit.json',
             ROOT / 'results/prediction_continuation_20261014/manifest.json', root_register)},
        'AF_terminal_public_commit': candidate['AF_terminal_public_commit'],
        'current_npz_paths': len(seen), 'unchanged_npz_paths': unchanged,
        'new_or_modified_npz_records': changed, 'removed_prior_paths': sorted(set(prior) - seen),
        'seed_members_read': arrays, 'actual_overlaps': matches, 'NPZ_errors': errors,
        'JSON_source_pins': pins, 'JSON_numeric_matches': hits, 'JSON_numeric_string_or_key_matches': string_hits,
        'JSON_errors': json_errors, 'classification': 'Only prior AF block131 exclusive upper endpoint52320000 appears; no candidate member use or reservation.',
        'known_synthetic_placeholders_unchanged': len(candidate['synthetic_errors_classified']),
        'root_candidate_source': {'path': str(root_register.relative_to(ROOT)), 'sha256': sha(root_register),
            'exact_stage_literals_verified_without_executing_helper': True, 'new_text_matches': new_text,
            'classification': 'Unexecuted root registration draft names these same proposed candidates; canonical registration and inputs are absent.'},
        'final_text_match_sha256': sha(OUT / 'final_text_matches.txt'),
        'limits': ['Same-candidate delta reuses unchanged file stat identity and the initial reopened payload proof; only changed/new seed members are reread.',
            'All current AG source/test fixtures and completed AF canonical/public copies are covered; future additions require a new compact delta before registration.',
            'No scientific outcome or genotype arrays loaded; no new simulations, compilations, genetic draws or copied scientific inputs.'],
        'simulation_calls': 0, 'compilation_calls': 0, 'genetic_draws': 0, 'genotype_copies': 0}
    (OUT / 'final_namespace_delta.json').write_text(json.dumps(result, indent=2) + '\n')
    proof_paths = [OUT / name for name in ('namespace_audit.py', 'classify_candidate.py', 'final_namespace_delta.py',
        'candidate_namespace_inventory.json', 'candidate_namespace_review.json', 'final_namespace_delta.json', 'history_references.json')]
    audit = {'status': 'passed', 'registered': False, 'reserved': False, 'seeds': candidate['seeds'],
        'base': 51000000, 'blocks': [132, 133, 134], 'whole_blocks_half_open': candidate['whole_blocks_half_open'],
        'unique_candidate_ids': 546, 'native_run_seeds': [], 'new_genetic_draws': 0,
        'intentional_reuse': candidate['intentional_reuse'],
        'candidate_review_sha256': sha(OUT / 'candidate_namespace_review.json'),
        'final_delta_sha256': sha(OUT / 'final_namespace_delta.json'),
        'historical_reference_sha256': sha(OUT / 'history_references.json'),
        'source_pins': {str(path.relative_to(ROOT)): sha(path) for path in proof_paths},
        'scope': 'Candidate-only namespace review for two calibration,32screen and512confirmation IDs. Existing seed11 identity pair is explicit reuse. Root registration/release remains separate.',
        'simulation_calls': 0, 'compilation_calls': 0, 'genotype_copies': 0}
    (OUT / 'seed_audit.json').write_text(json.dumps(audit, indent=2) + '\n')
    print(json.dumps({'status': 'passed', 'seed_audit_sha256': sha(OUT / 'seed_audit.json'),
        'delta_sha256': sha(OUT / 'final_namespace_delta.json'), 'current_npz_paths': len(seen),
        'new_or_modified_npz': len(changed), 'seed_members_read': arrays, 'overlaps': len(matches), 'errors': 0}))


if __name__ == '__main__':
    main()
