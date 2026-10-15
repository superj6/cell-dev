"""Independently recount recorded AH ancestry backwards; no engine or RNG imports."""
import hashlib
import json
from pathlib import Path

A = Path(__file__).resolve().parent
ROOT = A.parents[1]
S = ROOT / 'outputs/autonomous_exploratory_reserve_20261014'
F = A / 'future_direction'


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def main():
    report = json.loads((F / 'posthoc_retention.json').read_text())
    assert report['status'] == 'complete_posthoc_descriptive_only'
    assert report['source_sha256'] == sha(F / 'posthoc_retention.py')
    for name, digest in report['input_pins'].items():
        assert sha(S / name) == digest
    lines = {}
    for mode in ('control', 'reserve'):
        lines[mode] = [json.loads(v) for v in (S / f'runs/{mode}/lineage.jsonl').read_text().splitlines()][1:]
    reserve = lines['reserve']
    parents = {}
    for row in reserve:
        for child in row['children']:
            assert child['id'] not in parents
            parents[child['id']] = (child['pa'], child['pb'])
    final = reserve[-1]['survivors']
    assert final[0] == report['final_endpoint_id'] == 895 and len(final) == 32
    ancestors = {}
    for final_id in final:
        seen, pending = set(), [final_id]
        while pending:
            child_id = pending.pop()
            if child_id in seen:
                continue
            seen.add(child_id)
            pending.extend(parents.get(child_id, ()))
        ancestors[final_id] = seen
    for item in report['genealogical_ancestry']:
        protected = item['protected_id']
        expected = [child for child in final if protected in ancestors[child]]
        assert expected == item['final_population_genealogical_descendants']
        assert len(expected) == item['final_population_descendant_count']
        assert (protected in ancestors[895]) == item['final_endpoint_genealogical_descendant'] is False
        for generation, row in enumerate(reserve):
            direct = [c['id'] for c in row['children'] if protected in (c['pa'], c['pb'])]
            assert direct == item['direct_children_by_generation'][generation]['children']
            assert len(direct) == item['direct_child_counts_by_generation'][generation]
    nonzero = {i['protected_id']: i['final_population_genealogical_descendants']
               for i in report['genealogical_ancestry'] if i['final_population_descendant_count']}
    assert nonzero == {329: [882, 668, 856]}
    for row, decision in zip(reserve, report['selection_decisions']):
        meta = row['exploratory_reserve']
        ids = meta['candidate_ids']
        initial = meta['ranking_calls'][1]['order']
        pooled = meta['ranking_calls'][2]['order']
        shortlist = meta['shortlist_indices']
        assert meta['reserve_ids'] == decision['protected_ids']
        assert [ids[i] for i in initial[:64] if ids[i] not in row['recheck']['ids']] == decision['ordinary_initial_shortlist_displaced']
        assert [ids[shortlist[i]] for i in pooled[:32] if ids[shortlist[i]] not in row['survivors']] == decision['treatment_pooled_top32_displaced']
        for item in decision['protected']:
            index = ids.index(item['id'])
            assert initial.index(index) + 1 == item['initial_rank_of_256'] > 64
            assert pooled.index(shortlist.index(index)) + 1 == item['pooled_rank_of_treatment64'] > 32
    comparison = report['generation0_same_cohort_control_comparison']
    assert [i for i in lines['control'][0]['survivors'] if i not in reserve[0]['survivors']] == comparison['ordinary_survivors_displaced'] == [234, 176]
    assert [i for i in reserve[0]['survivors'] if i not in lines['control'][0]['survivors']] == comparison['reserve_survivors_added'] == [144, 135]
    paths = [Path(__file__), F / 'posthoc_retention.py', F / 'posthoc_retention.json', F / 'posthoc_retention_report.md',
             *[S / name for name in report['input_pins']]]
    receipt = {'status': 'passed_independent_backward_parentage_recount',
               'pins': {str(p.relative_to(ROOT)): sha(p) for p in paths},
               'protected_ids_checked': 6, 'final_rows_checked': 32, 'endpoint_id': 895,
               'endpoint_has_protected_ancestor': False, 'nonempty_final_descendants': nonzero,
               'selection_ranks_and_displacements_match': True,
               'scope': 'Post hoc genealogy and recorded selection only; no functional contribution or necessary-step inference.',
               'simulation_calls': 0, 'compiled_libraries': 0, 'new_genetic_draws': 0}
    (A / 'posthoc_independent_review.json').write_text(json.dumps(receipt, indent=2) + '\n')
    print(json.dumps({'status': receipt['status'], 'sha256': sha(A / 'posthoc_independent_review.json')}))


if __name__ == '__main__':
    main()
