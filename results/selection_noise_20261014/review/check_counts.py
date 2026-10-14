"""Independent raw shortlist/survivor count audit of completed D/G/L; no simulator imports."""
import hashlib
import json
from pathlib import Path

import numpy as np

ROOT = Path(__file__).resolve().parents[2]
OUT = Path(__file__).resolve().parent
DIAG = ROOT / 'outputs/selection_noise_20261014'
STUDIES = {'D': ('continuation_20261013', (51089, 51090)),
           'G': ('structural_20261013', (51089, 51090)), 'L': ('s7_continuation_20261014', (51891, 51892))}


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def read(path):
    return json.loads(path.read_text())


saved = read(DIAG / 'generations.json')
if isinstance(saved, dict):
    print('generation wrapper keys', list(saved))
    raise ValueError('inspect generation schema')
index = {(r['study'], r['run'], r['gen']): r for r in saved}
rows, spot = [], []
for study, (directory, runs) in STUDIES.items():
    base = ROOT / 'results' / directory
    budget = read(base / 'operations/budget.json')
    assert budget['status'] == 'complete' and not budget['running'] and not budget['queued']
    manifest = read(base / 'provenance.json')
    for seed in runs:
        path = base / 'runs' / ('s' + str(seed)) / 'lineage.jsonl'
        assert sha(path) == manifest['artifacts'][str(path.relative_to(base))]['sha256']
        records = [json.loads(line) for line in path.read_text().splitlines()]
        for row in [r for r in records if 'gen' in r]:
            r = index[(study, seed, row['gen'])]
            ids, survivors = row['recheck']['ids'], row['survivors']
            replaced = len(set(ids[:32]) - set(survivors))
            assert replaced == r['changed_parents'] == row['recheck']['changed']
            base_scores = np.asarray(row['recheck']['F_base'])
            fresh_scores = np.asarray(row['recheck']['F_recheck'])
            actual = np.asarray(row['fitness'])
            top_base = {ids[i] for i, f in enumerate(base_scores) if f == max(base_scores)}
            top_final = {survivors[i] for i, f in enumerate(actual) if f == max(actual)}
            assert set(r['base_top_ids']) == top_base and set(r['recorded_pooled_top_ids']) == top_final
            complete_top = actual[-1] < actual[0]
            strict = bool(not (top_base & top_final) and complete_top)
            assert strict == (r['top_relation'] == 'strict_displacement')
            if strict:
                upper = [actual[survivors.index(i)] if i in survivors else actual[-1] for i in top_base]
                margin = float(actual[0] - max(upper))
                assert margin > 0 and margin == r['strict_displacement_recorded_margin_lower_bound']
            record = {'study': study, 'run': seed, 'gen': row['gen'], 'replaced': replaced,
                      'strict_top_displacement': strict, 'leader_identity_changed': ids[0] != survivors[0]}
            rows.append(record)
            if row['gen'] in (0, 15):
                spot.append({**record, 'initial_top_ids': sorted(top_base), 'recorded_final_top_ids': sorted(top_final),
                             'survivor_set_sha256': hashlib.sha256(json.dumps(survivors).encode()).hexdigest()})
assert len(rows) == 96
assert sum(r['replaced'] for r in rows) == 1120
assert sum(r['strict_top_displacement'] for r in rows) == 76
receipt = {'status': 'passed', 'reviewer': 'audit_de independent raw count audit', 'simulated_lives': 0,
           'active_P_outcomes_read': False, 'generations_checked': len(rows), 'parent_slots': 32 * len(rows),
           'replaced_parent_slots': sum(r['replaced'] for r in rows),
           'strict_top_displacements': sum(r['strict_top_displacement'] for r in rows),
           'leader_identity_changes': sum(r['leader_identity_changed'] for r in rows), 'spot_records': spot,
           'diagnostic_sha256': {name: sha(DIAG / name) for name in
                                  ('analyze.py', 'test_analyze.py', 'summary.json', 'generations.json')},
           'review_script_sha256': sha(Path(__file__)),
           'limits': ['Original shortlist order and survivor sets define replacement; earlier tie draw not reconstructed.',
                      'Strict displacement uses exact recorded top sets and complete maximum/cutoff ordering, not reconstructed means.',
                      'These conditional descriptive counts do not establish independent variance or scoring-policy value.']}
(OUT / 'count_review.json').write_text(json.dumps(receipt, indent=2) + '\n')
print(json.dumps({k: receipt[k] for k in ('status', 'generations_checked', 'replaced_parent_slots',
                                       'strict_top_displacements', 'leader_identity_changes')}))
