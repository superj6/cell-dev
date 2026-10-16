"""Classify the 144/145 seed audit; no reservation, engine import, build, or life."""
from __future__ import annotations

import ast
import hashlib
import json
from pathlib import Path

OUT = Path(__file__).resolve().parent
ROOT = OUT.parents[1]
LOW, HIGH = 52440000, 52460000


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def read(path):
    return json.loads(path.read_text())


def main():
    inventory = read(OUT / 'candidate_seed_inventory.json')
    if inventory['NPZ_matches'] or inventory['NPZ_errors'] or inventory['JSON_errors']:
        raise ValueError('unresolved seed overlap or audit error')
    json_classes = []
    for row in inventory['JSON_hits']:
        if (row['value'] != LOW or row['field'] not in ('whole_block_half_open.1', 'seed_blocks.0.1')
                or not row['path'].startswith('results/delayed_match_baseline_20261015/')):
            raise ValueError('unclassified JSON integer: ' + str(row))
        json_classes.append(dict(row, classification='Excluded upper endpoint of baseline block143'))
    text_classes = []
    for line in (OUT / 'candidate_text_matches.txt').read_text().splitlines():
        path, number, text = line.split(':', 2)
        if 'be37b466524494bbc514e110349f75c9bd64b19af95e9e91e0c2130db160df68' in text:
            category = 'Substring of raw genome SHA256, not an integer seed'
        elif 'delayed_match_baseline_20261015' in path and '52440000' in text:
            category = 'Excluded upper endpoint of baseline block143 in audit source'
        elif 'openhr/switching/' in path:
            category = 'Old block numbering at base43million, disjoint'
        elif '68.524434' in text or '.52442' in text or '-1.845244' in text:
            category = 'Substring of decimal cost/statistic, not an integer seed'
        elif '6,144' in text or 'all 144 raw checkpoints' in text:
            category = 'Count of lives/candidates/checkpoints, not a seed namespace'
        elif 'reserve_survivors_added' in text and '[144, 135]' in text:
            category = 'Lineage survivor identifier, not life seed'
        elif '0x46575244' in text:
            assert not LOW <= int('46575244', 16) < HIGH
            category = 'Hexadecimal stream constant, outside candidate namespace'
        else:
            raise ValueError('unclassified text literal: ' + line)
        text_classes.append(dict(path=path, line=int(number), classification=category))
    switching = ROOT / 'outputs/openhr/harness/harness.py'
    tree = ast.parse(switching.read_text())
    old_base = next(ast.literal_eval(node.value) for node in tree.body if isinstance(node, ast.Assign)
                   and any(isinstance(t, ast.Name) and t.id == 'SEED_BASE' for t in node.targets))
    assert old_base == 43000000 and old_base + 10000*160 < LOW
    assert 'seed0=SEED_BASE + 10_000 * block, first=first' in switching.read_text()
    registrations = []
    paths = [folder / 'registration.json' for folder in sorted((ROOT / 'outputs').glob('autonomous_*'))]
    paths.append(ROOT / 'outputs/delayed_match_baseline_20261015/reservation.json')
    for path in paths:
        if not path.exists():
            continue
        record = read(path)
        ranges = record.get('seed_blocks') or []
        if isinstance(ranges, dict):
            assert record['study'] == 'Y ordinary visibility gradient'
            ranges = [[51000000+10000*b, 51000000+10000*(b+1)] for b in ranges.values()]
        if len(ranges) == 2 and all(isinstance(v, int) for v in ranges):
            ranges = [ranges]
        assert all(max(lo, LOW) >= min(hi, HIGH) for lo, hi in ranges)
        registrations.append(dict(path=str(path.relative_to(ROOT)), sha256=sha(path), seed_blocks=ranges))
    # The candidate folder was excluded from history scanning, so explicitly check its existing
    # engineering schedules/call receipts. These used old fixture IDs, not scientific candidate IDs.
    engineering_seeds = set()
    plan = read(OUT / 'engineering_retry/plan.json')
    engineering_seeds.update(row['seed'] for row in plan['pairs'])
    # plan['script'] contains actuator events (time, actuator, amplitude), not seeds;
    # every script replay's seed is already declared in plan['pairs'].
    calls = read(OUT / 'policy_engineering/calls.json')
    engineering_seeds.update(row['seed'] for row in calls)
    assert len(read(OUT / 'engineering_retry/calls.json')) == 32 and len(calls) == 8
    assert engineering_seeds == {42000000, 42000001, 42000002, 42000004, 42000006, 42000007}
    assert not any(LOW <= seed < HIGH for seed in engineering_seeds)
    result = dict(status='passed', reserved=False, registered=False,
        candidate_blocks={'development': 144, 'confirmation': 145},
        whole_blocks_half_open=[[52440000, 52450000], [52450000, 52460000]],
        development_seeds=list(range(52440000, 52440064)),
        confirmation_seeds=list(range(52450000, 52450512)), numeric_overlap_count=0,
        coverage={key: inventory[key] for key in ('current_npz_paths', 'unchanged_npz_paths',
            'unchanged_seed_members_covered', 'distinct_unchanged_payloads_reopened')},
        JSON_classification=json_classes, text_classification=text_classes,
        registration_pins=registrations, switching_source_sha256=sha(switching),
        engineering_fixture_seeds=sorted(engineering_seeds), prior_engineering_calls=40,
        engineering_source_pins={name: sha(OUT / name) for name in
            ('engineering_retry/plan.json', 'engineering_retry/calls.json',
             'policy_engineering/plan.json', 'policy_engineering/calls.json')},
        baseline_running_directory_skipped=inventory['excluded_running_baseline'],
        baseline_reservation_sha256=inventory['baseline_reservation_sha256'],
        limitations=inventory['limitations'],
        evidence_pins={name: sha(OUT / name) for name in ('audit_namespace.py', 'candidate_seed_inventory.json',
            'candidate_text_matches.txt', 'namespace_stdout.json', 'namespace_resources.txt', 'classify_namespace.py')},
        audit_simulation_calls=0, audit_engine_builds=0, audit_random_draws=0)
    (OUT / 'seed_audit.json').write_text(json.dumps(result, indent=2) + '\n')
    print(json.dumps(dict(status='passed', seed_audit_sha256=sha(OUT / 'seed_audit.json'),
                         reserved=False, registered=False, audited_ids=576, numeric_overlap_count=0)))


if __name__ == '__main__':
    main()
