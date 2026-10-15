"""Classify the AM candidate namespace; this never registers or consumes seeds."""
import ast
import hashlib
import json
from pathlib import Path

BASE = Path(__file__).resolve().parent
ROOT = BASE.parents[2]
LOW, HIGH = 52400000, 52410000


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def main():
    inventory = json.loads((BASE / 'candidate_seed_inventory.json').read_text())
    assert not inventory['NPZ_matches'] and not inventory['NPZ_errors'] and not inventory['JSON_errors']
    records = inventory['native_records']
    values = [row['seed'] for row in records]
    assert len(values) == len(set(values)) == 100
    assert not any(LOW <= value < HIGH for value in values)
    assert inventory['run_life_seeds'] == {arm: values for arm in ('current_value', 'high_value')}
    for study in ('autonomous_population_depth_20261015', 'autonomous_capture_value_selection_20261015'):
        assert not any((ROOT / 'outputs' / study / name).exists()
                       for name in ('registration.json', 'protocol.json', 'release.json'))
    classifications = []
    for item in inventory['JSON_hits']:
        assert item['value'] == LOW
        assert item['field'] in ('whole_block_half_open.1', 'seed_blocks.0.1')
        assert 'retention_selection_20261015' in item['path']
        classifications.append(dict(item, classification='excluded upper endpoint of registered AL block 139'))

    # Switching's block numbers belong to its older 43-million namespace.
    # Check the actual retained declarations rather than interpreting a bare block number.
    switching_pins = {}
    for name in ('outputs/openhr/harness/harness.py', 'results/open_headroom/harness/harness.py'):
        path = ROOT / name
        tree = ast.parse(path.read_text())
        base = next(ast.literal_eval(n.value) for n in tree.body if isinstance(n, ast.Assign)
                    and any(isinstance(t, ast.Name) and t.id == 'SEED_BASE' for t in n.targets))
        assert base == 43000000
        text = path.read_text()
        assert 'seed0=SEED_BASE + 10_000 * block, first=first' in text
        assert base + 10000 * 160 < LOW
        switching_pins[name] = sha(path)
    text_classes = []
    for line in (BASE / 'candidate_text_matches.txt').read_text().splitlines():
        path, number, text = line.split(':', 2)
        if path.endswith('/src/life/handbuilt.py') and 'hill_F=7.652403658548988' in text:
            category = 'decimal historical fitness literal, not a seed'
        elif path.endswith('/ALTERNATIVES.md') and 'arxiv.org/abs/2106.15240' in text:
            category = 'article identifier, not a seed'
        elif ('openhr/switching/' in path or path.endswith('/open_headroom/controllers/swlib.py')):
            category = 'old switching blocks 140 to 159 at base 43 million, disjoint'
        elif 'retention_selection_20261015' in path and Path(path).name in ('audit_namespace.py', 'classify_namespace.py'):
            assert '52400000' in text
            category = 'AL block 139 excluded upper endpoint in prior audit code'
        else:
            raise ValueError('unclassified source literal: ' + line)
        text_classes.append({'path': path, 'line': int(number), 'classification': category})

    registrations = []
    for folder in sorted((ROOT / 'outputs').glob('autonomous_*')):
        path = folder / 'registration.json'
        if not path.exists():
            continue
        item = json.loads(path.read_text())
        ranges = item.get('seed_blocks') or []
        if isinstance(ranges, dict):
            assert item['study'] == 'Y ordinary visibility gradient'
            ranges = [[51000000 + 10000 * b, 51000000 + 10000 * (b + 1)] for b in ranges.values()]
        if len(ranges) == 2 and all(isinstance(value, int) for value in ranges):
            ranges = [ranges]
        for lo, hi in ranges:
            assert max(lo, LOW) >= min(hi, HIGH)
        registrations.append({'path': str(path.relative_to(ROOT)), 'sha256': sha(path), 'seed_blocks': ranges})

    result = {
        'status': 'passed', 'reserved': False, 'registered': False, 'native_seed': 53230,
        'confirmation_seeds': list(range(LOW, LOW + 512)), 'candidate_seeds': list(range(LOW, LOW + 512)),
        'whole_block_half_open': [LOW, HIGH], 'native_records': records,
        'run_life_seeds': inventory['run_life_seeds'], 'unique_native_ids': 100,
        'intentional_reuse': [
            'Both search arms share the same 100 native IDs and genetic seed.',
            'The two final index 0 IDs are reused for full-duration and half-duration diagnostics.',
            'The 512 fresh confirmation IDs are shared across all four roles and four worlds at R_cap 500.',
            'Eight separately counted startup lives use the existing pinned numerical truth IDs.'
        ],
        'AJ_status': 'Native 53228 and block 137 remain held, source-only, unregistered and unreserved; no overlap.',
        'NPZ_coverage': {k: inventory[k] for k in ('current_npz_paths', 'unchanged_npz_paths',
            'unchanged_seed_members_covered', 'distinct_unchanged_payloads_reopened')},
        'changed_npz_count': len(inventory['changed_npz_records']), 'numeric_overlap_count': 0,
        'JSON_classification': classifications, 'text_classification': text_classes,
        'registration_pins': registrations, 'switching_namespace_source_pins': switching_pins,
        'historical_inventory_references': inventory['prior_inventory_pins'],
        'native_source_pins': inventory['native_source_pins'],
        'held_AJ_audit_sha256': inventory['held_AJ_seed_audit_sha256'],
        'evidence_pins': {n: sha(BASE / n) for n in ('audit_namespace.py', 'candidate_seed_inventory.json',
            'candidate_text_matches.txt', 'namespace_stdout.json', 'namespace_stderr.txt')},
        'classification_source_sha256': sha(Path(__file__)), 'limitations': inventory['limitations'],
        'producer_schedule_check': 'Pending final prepare.py planned_search_seeds; pure production life_seed derivation is complete.',
        'simulation_calls': 0, 'engine_builds': 0, 'genetic_draws': 0
    }
    (BASE / 'seed_audit.json').write_text(json.dumps(result, indent=2) + '\n')
    print(json.dumps({'status': 'passed', 'sha256': sha(BASE / 'seed_audit.json'),
        'JSON_classified': len(classifications), 'text_classified': len(text_classes),
        'native_unique': 100, 'confirmation': 512}))


if __name__ == '__main__':
    main()
