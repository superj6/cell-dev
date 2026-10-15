"""AH registration-time seed-only delta; never execute producer or root helpers."""
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
CURRENT = ROOT / 'outputs/autonomous_exploratory_reserve_20261014'
AG = ROOT / 'outputs/autonomous_visibility_dark_tail_gradient_20261014'
LOW, HIGH = 52_350_000, 52_360_000


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def read(path):
    return json.loads(path.read_text())


def helper_candidates(path):
    """Read only two asserted literals from the unexecuted root draft."""
    values = {}
    for node in ast.walk(ast.parse(path.read_text())):
        if not isinstance(node, ast.Compare) or len(node.ops) != 1 or not isinstance(node.ops[0], ast.Eq):
            continue
        left = node.left
        if not (isinstance(left, ast.Subscript) and isinstance(left.value, ast.Name)
                and left.value.id == 'seed' and isinstance(left.slice, ast.Constant)
                and left.slice.value in ('paired_native_seed', 'confirmation_seeds')):
            continue
        expression = node.comparators[0]
        for part in ast.walk(expression):
            assert isinstance(part, (ast.Constant, ast.Call, ast.Name, ast.Load)), ast.dump(part)
            if isinstance(part, ast.Name):
                assert part.id in ('list', 'range')
        values[left.slice.value] = eval(compile(ast.Expression(expression), str(path), 'eval'),
                                       {'__builtins__': {}, 'list': list, 'range': range})
    return values


def main():
    candidate = read(OUT / 'candidate_namespace_review.json')
    inventory = read(OUT / 'candidate_namespace_inventory.json')
    assert candidate['status'] == 'passed_candidate_pending_final_delta'
    assert sha(OUT / 'candidate_namespace_inventory.json') == candidate['inventory_sha256']
    assert not any((CURRENT / name).exists() for name in
                   ('registration.json', 'seed_audit.json', 'inputs', 'configs', 'initialization',
                    'protocol.json', 'ready.json', 'attempt.json', 'budget.json'))
    for name, digest in candidate['source_pins'].items():
        assert sha(ROOT / name) == digest, name
    for name, digest in candidate['AG_terminal_pins'].items():
        assert sha(ROOT / name) == digest, name
    budget, clearance = read(AG / 'budget.json'), read(AG / 'terminal_process_clearance.json')
    assert budget['status'] == 'complete' and not budget['running'] and not budget['queued']
    assert not budget.get('cleanup_error')
    assert clearance['status'] == 'cleared' and clearance['all_processes_exited']
    assert clearance['budget_sha256'] == sha(AG / 'budget.json')
    module = importlib.util.spec_from_file_location('ah_seed_predicates', OUT / 'namespace_audit.py')
    h = importlib.util.module_from_spec(module)
    module.loader.exec_module(h)
    lists, records, overlap, native = h.derive()
    assert lists == candidate['run_life_seeds'] and overlap == candidate['intentional_overlap']
    # Bind the current producer's pure schedule definition to the reviewed snapshot.
    def plan_ast(path):
        return ast.dump(next(node for node in ast.parse(path.read_text()).body
                             if isinstance(node, ast.FunctionDef) and node.name == 'planned_search_seeds'),
                        include_attributes=False)
    assert plan_ast(CURRENT / 'prepare.py') == plan_ast(OUT / 'AH_prepare_candidate.py.txt')
    root_register = OUT.parent / 'register_study.py'
    assert helper_candidates(root_register) == {
        'paired_native_seed': 53226, 'confirmation_seeds': candidate['confirmation_seeds']}
    # The calling root separately accepts the producer/reader reviews. These files
    # must exist before this final scan, but no review schema is invented here.
    reviews = [OUT.parent / name for name in (
        'producer_source_review.json', 'reader_source_review.json', 'analyzer_peer_review.json',
        'independent_source_design_review.json')]
    expected_statuses = ('passed_source_only_unregistered', 'source_only_reviewed_unregistered',
                         'approved_source_only_unbound', 'approved_source_only_unregistered')
    for path, status in zip(reviews, expected_statuses):
        assert read(path)['status'] == status, path
    peer = read(OUT.parent / 'analyzer_peer_review.json')
    assert peer['reader_source_review_sha256'] == sha(OUT.parent / 'reader_source_review.json')
    assert peer['reader_source_pins'] == read(OUT.parent / 'reader_source_review.json')['reader_sources']
    producer = read(OUT.parent / 'producer_source_review.json')
    assert peer['producer_source_pins'] == producer['producer_source_pins']
    for base, mapping in ((CURRENT, peer['producer_source_pins']),
                          (OUT.parent / 'analysis', peer['reader_source_pins'])):
        for name, digest in mapping.items():
            assert sha(base / name) == digest, name
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
            dirs[:] = sorted(name for name in dirs if name not in h.SKIP and not h.excluded(base / name))
            for name in sorted(names):
                if not name.endswith('.npz'):
                    continue
                path = base / name
                relative, state = str(path.relative_to(ROOT)), h.stat(path)
                seen.add(relative)
                if relative in prior and prior[relative].get('stat') == state:
                    unchanged += 1
                    continue
                record = {'stat': state, 'synthetic_fixture': any(p.startswith('test_') for p in path.parts),
                          'seed_members': {}}
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
                                    or (not np.issubdtype(values.dtype, np.integer)
                                        and np.any(values != np.floor(values)))):
                                raise ValueError('invalid seed member')
                            arrays += 1
                            record['seed_members'][item.filename] = {'sha256': hashlib.sha256(raw).hexdigest(),
                                'shape': list(values.shape), 'dtype': str(values.dtype)}
                            hits = sorted({int(x) for x in values.flat if LOW <= int(x) < HIGH or int(x) in native})
                            if hits:
                                matches.append({'path': relative, 'member': item.filename, 'values': hits})
                    if h.stat(path) != state:
                        raise ValueError('file changed during final delta')
                except (OSError, ValueError, zipfile.BadZipFile, EOFError) as error:
                    errors.append({'path': relative, 'error': type(error).__name__ + ': ' + str(error)})
    pattern = r'(?<![0-9.])(?:523[56][0-9]{4}|53226|' + '|'.join(str(x) for x in sorted(native)) + r')(?![0-9.])'
    found = subprocess.run(['rg', '--no-ignore', '-l', '-0', '-P', '--glob', '*.json',
                            '--glob', '!**/test_*/**', pattern, 'results', 'outputs'], cwd=ROOT, capture_output=True)
    assert found.returncode in (0, 1)
    pins, hits, string_hits, json_errors = {}, [], [], []

    def wanted(value):
        return LOW <= value <= HIGH or value in native or value == 53226

    def visit(value, trail, path):
        if isinstance(value, dict):
            for key, item in value.items():
                if key.isdecimal() and wanted(int(key)):
                    string_hits.append({'path': path, 'field': '.'.join(trail), 'kind': 'key', 'value': key})
                visit(item, trail + [key], path)
        elif isinstance(value, list):
            for i, item in enumerate(value):
                visit(item, trail + [str(i)], path)
        elif type(value) is int and wanted(value):
            hits.append({'path': path, 'field': '.'.join(trail), 'value': value})
        elif isinstance(value, str) and value.isdecimal() and wanted(int(value)):
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
    allowed = {'whole_blocks_half_open.2.1', 'whole_block_half_open.1', 'same_whole_blocks_half_open.2.1'}
    assert all(item['value'] == LOW and item['field'] in allowed
               and 'visibility_dark_tail_gradient_20261014' in item['path'] for item in hits), hits
    assert not matches and not errors and not json_errors and not string_hits
    text = subprocess.run(['rg', '--no-ignore', '-n', '-P', '--glob', '*.py', '--glob', '*.md',
        '--glob', '*.yaml', '--glob', '!**/test_*/**',
        r'52[_,]?3[56][0-9_,]*|53[_,]?226|(?:block|fresh_seeds|reserve).{0,35}\b135\b',
        'results', 'outputs', 'docs'], cwd=ROOT, capture_output=True)
    assert text.returncode in (0, 1)
    textlines = [line for line in text.stdout.decode().splitlines() if not h.excluded(ROOT / line.split(':', 1)[0])]
    previous_text = set((OUT / 'candidate_text_matches.txt').read_text().splitlines())
    new_text = sorted(set(textlines) - previous_text)
    assert all(line.startswith(str(root_register.relative_to(ROOT)) + ':') for line in new_text), new_text
    (OUT / 'final_text_matches.txt').write_text('\n'.join(textlines) + '\n')
    sources = [Path(__file__), *reviews, CURRENT / 'prepare.py', AG / 'budget.json',
               AG / 'terminal_process_clearance.json', AG / 'seed_audit.json',
               ROOT / 'results/visibility_dark_tail_gradient_20261014/manifest.json', root_register]
    result = {'status': 'passed', 'registered': False, 'reserved': False,
        'candidate_review_sha256': sha(OUT / 'candidate_namespace_review.json'),
        'candidate_inventory_sha256': sha(OUT / 'candidate_namespace_inventory.json'),
        'same_whole_blocks_half_open': candidate['whole_blocks_half_open'],
        'paired_native_seed': 53226, 'run_life_seeds': lists, 'confirmation_seeds': candidate['confirmation_seeds'],
        'source_pins': {str(path.relative_to(ROOT)): sha(path) for path in sources},
        'AG_terminal_public_commit': candidate['AG_terminal_public_commit'],
        'current_npz_paths': len(seen), 'unchanged_npz_paths': unchanged,
        'new_or_modified_npz_records': changed, 'removed_prior_paths': sorted(set(prior) - seen),
        'seed_members_read': arrays, 'actual_overlaps': matches, 'NPZ_errors': errors,
        'JSON_source_pins': pins, 'JSON_numeric_matches': hits, 'JSON_numeric_string_or_key_matches': string_hits,
        'JSON_errors': json_errors,
        'classification': 'Prior AG block134 upper endpoint is excluded; root draft names the same unexecuted AH candidates.',
        'known_synthetic_placeholders_unchanged': candidate['inherited_fixture_scope'],
        'root_candidate_source': {'path': str(root_register.relative_to(ROOT)), 'sha256': sha(root_register),
            'exact_stage_literals_verified_without_executing_helper': True, 'new_text_matches': new_text,
            'classification': 'Unexecuted draft; canonical registration, seed audit and inputs are absent.'},
        'final_text_match_sha256': sha(OUT / 'final_text_matches.txt'),
        'reviewer_execution_history': {'initial_error': 'Reader receipt used source_only_reviewed_unregistered; initial checker rejected its unrecognized status before scanning. Corrected to exact current receipt schemas; no source/study changes.',
            'source_sha256': sha(OUT / 'history/final_namespace_delta_initial.py.txt'),
            'stderr_sha256': sha(OUT / 'history/final_delta_initial_error.txt')},
        'limits': ['Same-candidate delta reuses unchanged file stat identity and the initial reopened seed-payload proof.',
            'Current reader fixtures and completed AG canonical/public copies are covered; future additions need a new compact delta.',
            'Only seed metadata inspected; no outcomes, genotypes, simulations, compilations, genetic draws or copied scientific inputs.'],
        'simulation_calls': 0, 'compilation_calls': 0, 'genetic_draws': 0, 'genotype_copies': 0}
    (OUT / 'final_namespace_delta.json').write_text(json.dumps(result, indent=2) + '\n')
    proof_paths = [OUT / name for name in ('namespace_audit.py', 'classify_candidate.py', 'final_namespace_delta.py',
        'candidate_namespace_inventory.json', 'candidate_namespace_review.json', 'final_namespace_delta.json',
        'history_references.json', 'README.md')]
    audit = {'status': 'passed', 'registered': False, 'reserved': False,
        'paired_native_seed': 53226, 'confirmation_seeds': candidate['confirmation_seeds'],
        'run_life_seeds': lists, 'intentional_overlap': overlap,
        'base': 51000000, 'block': 135, 'whole_blocks_half_open': candidate['whole_blocks_half_open'],
        'unique_candidate_ids': 576, 'unique_native_ids': 64, 'new_genetic_draws': 0,
        'intentional_reuse': candidate['intentional_reuse'], 'records_by_run': records,
        'candidate_review_sha256': sha(OUT / 'candidate_namespace_review.json'),
        'final_delta_sha256': sha(OUT / 'final_namespace_delta.json'),
        'historical_reference_sha256': sha(OUT / 'history_references.json'),
        'source_pins': {str(path.relative_to(ROOT)): sha(path) for path in proof_paths},
        'scope': 'Candidate-only audit: 64 native IDs shared by both arms; 512 fresh confirmation IDs shared by three roles. Root registration/release is separate.',
        'simulation_calls': 0, 'compilation_calls': 0, 'genotype_copies': 0}
    (OUT / 'seed_audit.json').write_text(json.dumps(audit, indent=2) + '\n')
    print(json.dumps({'status': 'passed', 'seed_audit_sha256': sha(OUT / 'seed_audit.json'),
        'delta_sha256': sha(OUT / 'final_namespace_delta.json'), 'current_npz_paths': len(seen),
        'new_or_modified_npz': len(changed), 'seed_members_read': arrays, 'overlaps': len(matches), 'errors': 0}))


if __name__ == '__main__':
    main()
