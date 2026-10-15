"""Classify the candidate audit's exact literals; no seeds are allocated here."""
import hashlib
import json
from pathlib import Path

BASE = Path(__file__).resolve().parent
ROOT = BASE.parents[2]


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def main():
    inventory = json.loads((BASE / 'candidate_seed_inventory.json').read_text())
    assert not inventory['NPZ_matches'] and not inventory['NPZ_errors'] and not inventory['JSON_errors']
    aj = ROOT / 'outputs/autonomous_population_depth_20261015'
    study = ROOT / 'outputs/autonomous_retention_frontier_20261015'
    assert not any((folder / name).exists() for folder in (aj, study)
                   for name in ('registration.json', 'protocol.json', 'attempt.json', 'release.json'))
    json_classes = []
    for item in inventory['JSON_hits']:
        if item['path'].startswith('outputs/audit_population_depth_20261015/namespace/'):
            assert 'half_open' in item['field'] and item['field'].endswith('.1') and item['value'] == 52380000
            category = 'excluded_upper_endpoint_of_unreserved_AJ_candidate'
        else:
            assert item['path'] == 'outputs/cumulative_capability_20261015/design/root_plan.json'
            assert item['field'].startswith('seeds.')
            assert item['value'] == 52380000 + int(item['field'].split('.')[1])
            category = 'own_unexecuted_candidate_plan'
        json_classes.append(dict(item, classification=category))
    text_classes = []
    for line in (BASE / 'candidate_text_matches.txt').read_text().splitlines():
        path, number, text = line.split(':', 2)
        if path.startswith('outputs/audit_population_depth_20261015/namespace/'):
            category = 'unreserved_AJ_excluded_upper_endpoint_or_decimal_classifier'
        elif '.05238' in text or '-1.2523930072784424' in text:
            category = 'decimal_measurement_or_mutation_value_not_seed'
        elif path.endswith('/copy_terminal_review.py') and text.startswith('PINS = '):
            category = 'hexadecimal_artifact_hash_substring'
        elif path.endswith('/TERMINAL_README.md') and '138 raw' in text:
            category = 'historical_row_count_not_seed_block'
        else:
            raise ValueError('unclassified text: ' + line)
        text_classes.append({'path': path, 'line': int(number), 'classification': category})
    # Latest actually registered blocks remain disjoint; AJ is deliberately untouched.
    prior = json.loads((BASE / 'namespace_status.json').read_text())
    for record in prior['canonical_registrations']:
        blocks = record.get('seed_blocks') or []
        if len(blocks) == 2 and all(isinstance(value, int) for value in blocks):
            blocks = [blocks]
        for low, high in blocks:
            assert max(low, 52380000) >= min(high, 52390000)
    result = {'status': 'passed', 'reserved': False, 'registered': False,
        'candidate_seeds': list(range(52380000, 52380256)), 'whole_block_half_open': [52380000, 52390000],
        'intentional_reuse': 'The same 256 fresh IDs are shared across all three genomes and all four fixed worlds.',
        'startup_reuse': 'Four separately counted engineering lives reuse existing ABI3 and ABI4 truth IDs.',
        'AJ_status': 'Native 53228 and block 137 are source-only, never registered or reserved; left untouched.',
        'NPZ_coverage': {key: inventory[key] for key in ('current_npz_paths', 'unchanged_npz_paths',
            'unchanged_seed_members_covered', 'distinct_unchanged_payloads_reopened')},
        'changed_npz_count': len(inventory['changed_npz_records']), 'numeric_overlap_count': 0,
        'JSON_classification': json_classes, 'text_classification': text_classes,
        'evidence_pins': {name: sha(BASE / name) for name in ('candidate_seed_inventory.json',
            'candidate_text_matches.txt', 'audit_seed_block.py', 'namespace_status.json',
            'seed_audit_execution.log', 'seed_audit_execution.stderr.txt')},
        'historical_inventories': inventory['prior_inventory_pins'],
        'classification_source_sha256': sha(Path(__file__)),
        'new_lives': 0, 'engine_builds': 0, 'genetic_draws': 0,
        'limits': inventory['limitations']}
    (BASE / 'seed_audit.json').write_text(json.dumps(result, indent=2) + '\n')
    print(json.dumps({'status': result['status'], 'seed_audit_sha256': sha(BASE / 'seed_audit.json'),
                      'JSON_classified': len(json_classes), 'text_classified': len(text_classes)}, indent=2))


if __name__ == '__main__':
    main()
