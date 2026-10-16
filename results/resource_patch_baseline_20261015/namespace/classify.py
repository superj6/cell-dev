"""Classify the completed seed-only scan, then reserve development blocks147/148; no draws."""
import hashlib
import json
import re
from pathlib import Path

HERE = Path(__file__).resolve().parent


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def main():
    data = json.loads((HERE / 'candidate_seed_inventory.json').read_text())
    assert not data['NPZ_matches'] and not data['NPZ_errors'] and not data['JSON_errors']
    assert data['whole_blocks_half_open'] == [[52470000, 52480000], [52480000, 52490000]]
    numeric, irrelevant = [], 0
    allowed_fields = {'whole_block_half_open.1', 'seed_blocks.0.1', 'seed_checks.reserved_half_open.1',
                      'whole_reserved_block_half_open.1'}
    for item in data['JSON_hits']:
        if item['value'] == -1:
            # The reused scanner's disabled native-ID sentinel also collected -1 metadata.
            # It is outside both candidate blocks and is neither a candidate nor a collision.
            irrelevant += 1
            continue
        assert item['value'] == 52470000 and item['field'] in allowed_fields
        assert 'delayed_match_evolution' in item['path']
        numeric.append(dict(item, classification='Excluded upper endpoint of previous block146'))
    text = []
    for line in (HERE / 'candidate_text_matches.txt').read_text().splitlines():
        path, lineno, value = line.split(':', 2)
        residual = re.sub(r'(?<![0-9a-f])[0-9a-f]{64}(?![0-9a-f])', 'HASH', value)
        if 'delayed_match_evolution' in path and '52470000' in residual:
            kind = 'Previous block146 excluded upper endpoint; not a used seed'
        elif 'delayed_match_evolution' in path and re.fullmatch(r'\s*- (?:old_id: )?5248', residual):
            kind = 'Ancestral individual ID5248; outside both blocks'
        elif path.endswith('RESULTS.md') and '0.045247' in residual:
            kind = 'Substring of decimal statistic, not a seed'
        elif not re.search(r'52[_,]?(?:4[78][0-9_,]*|490[0-9_,]*)|(?:block|fresh_seeds|reserve).{0,35}\b14[78]\b', residual):
            kind = 'Substring of pinned hexadecimal hash, not a seed'
        else:
            raise ValueError('unclassified source declaration: ' + line)
        text.append(dict(path=path, line=int(lineno), classification=kind))
    audit = dict(status='passed', scope='recorded seed-member payloads plus exact numeric JSON and source declarations',
        blocks=[147, 148], whole_blocks_half_open=data['whole_blocks_half_open'],
        population_seeds=list(range(52470000, 52470008)), reference_seeds=list(range(52480000, 52480032)),
        NPZ_matches=0, numeric_classifications=numeric, text_classifications=text,
        ignored_negative_sentinel_values=irrelevant,
        coverage={key: data[key] for key in ('current_npz_paths', 'unchanged_npz_paths',
            'unchanged_seed_members_covered', 'distinct_unchanged_payloads_reopened')},
        inventory_sha256=sha(HERE / 'candidate_seed_inventory.json'),
        source_sha256=sha(HERE / 'audit_namespace.py'), classifier_sha256=sha(Path(__file__)),
        historical_inventory_references=data['prior_inventory_pins'],
        resources_sha256=sha(HERE / 'resources.txt'), simulation_calls=0, builds=0, random_draws=0,
        limitations=data['limitations'])
    (HERE / 'seed_audit.json').write_text(json.dumps(audit, indent=2) + '\n')
    reservation = dict(status='reserved_development_only', study='Inherited pursuit in resource patches',
        seed_blocks=data['whole_blocks_half_open'], population_seeds=audit['population_seeds'],
        reference_seeds=audit['reference_seeds'], confirmation_eligible=False, scientific_lives=448,
        engineering_seed_reuse=[42000000, 42000001, 42000002, 42000003], engineering_lives=8,
        actual_executed_calls=0, seed_audit_sha256=sha(HERE / 'seed_audit.json'),
        intentional_reuse='All32 rows share8 population seeds; AO/AM and all3 worlds share32 separate reference seeds.')
    (HERE / 'reservation.json').write_text(json.dumps(reservation, indent=2) + '\n')
    print(json.dumps(dict(status='passed', candidate_numeric=len(numeric), text=len(text),
                         ignored_negative_sentinels=irrelevant, reserved_blocks=[147, 148], calls=0)))


if __name__ == '__main__':
    main()
