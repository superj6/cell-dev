"""Classify the AO candidate namespace; this never registers or consumes seeds."""
import ast
import hashlib
import json
from pathlib import Path

BASE = Path(__file__).resolve().parent
ROOT = BASE.parents[2]
LOW, HIGH = 52420000, 52430000


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def main():
    inventory = json.loads((BASE / 'candidate_seed_inventory.json').read_text())
    assert not inventory['NPZ_matches'] and not inventory['NPZ_errors'] and not inventory['JSON_errors']
    records = inventory['native_records']
    values = [row['seed'] for row in records]
    assert len(values) == len(set(values)) == 500
    assert not any(LOW <= value < HIGH for value in values)
    assert inventory['run_life_seeds'] == {arm: values for arm in ('unchanged', 'balanced')}
    for study in ('autonomous_population_depth_20261015', 'autonomous_retained_depth_20261015'):
        assert not any((ROOT / 'outputs' / study / name).exists()
                       for name in ('registration.json', 'protocol.json', 'release.json'))
    classifications = []
    for item in inventory['JSON_hits']:
        assert item['value'] == LOW
        assert item['field'] in ('whole_block_half_open.1', 'seed_blocks.0.1')
        assert 'occlusion_acquisition_20261015' in item['path']
        classifications.append(dict(item, classification='excluded upper endpoint of registered AN block 141'))

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
        if path in ('docs/HANDOFF.md', 'docs/TASK_VARIATION_PLAN.md') and '53232' in text:
            category = 'root explicitly unregistered own AO candidate declaration'
        elif 'openhr/switching/' in path:
            category = 'old switching block 142 at base 43 million, disjoint'
        elif 'occlusion_acquisition_20261015' in path and Path(path).name in ('audit_namespace.py', 'classify_namespace.py'):
            assert '52420000' in text
            category = 'AN block 141 excluded upper endpoint in prior audit code'
        elif 'occlusion_acquisition_20261015' in path and Path(path).suffix == '.yaml':
            assert '033a070ca9a78d424451fcd6b6ed4cc231f623464c03f9a7a10afbbac0052427' in text
            category = 'substring inside a 64-digit hexadecimal population hash, not a seed'
        elif path == 'outputs/autonomous_structural_20261013/RECOVERY_HANDOFF.md':
            assert '0.1588524299' in text
            category = 'decimal statistical standard error, not an integer seed'
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
        'status': 'passed', 'reserved': False, 'registered': False, 'native_seed': 53232,
        'confirmation_seeds': list(range(LOW, LOW + 512)), 'candidate_seeds': list(range(LOW, LOW + 512)),
        'whole_block_half_open': [LOW, HIGH], 'native_records': records,
        'run_life_seeds': inventory['run_life_seeds'], 'unique_native_ids': 500,
        'intentional_reuse': [
            'Two matched arms deliberately share all 500 native life IDs and the native genetic seed; each arm has 384 generation, 112 validation and 4 final unique IDs.',
            'The two final index 0 IDs are reused for full-duration and half-duration diagnostics.',
            'The 512 fresh confirmation IDs are shared across all six roles and five worlds at R_cap 500.',
            'Twelve separately counted startup lives use the existing pinned numerical truth IDs.'
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
        'producer_schedule_check': 'The final source test independently compares prepare.py planned_search_seeds to this production-hash derivation.',
        'simulation_calls': 0, 'engine_builds': 0, 'genetic_draws': 0
    }
    (BASE / 'seed_audit.json').write_text(json.dumps(result, indent=2) + '\n')
    print(json.dumps({'status': 'passed', 'sha256': sha(BASE / 'seed_audit.json'),
        'JSON_classified': len(classifications), 'text_classified': len(text_classes),
        'native_unique': 500, 'confirmation': 512}))


if __name__ == '__main__':
    main()
