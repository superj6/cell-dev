"""Descriptive parentage/selection recount only; no genotype generation or engine imports."""
import argparse
import hashlib
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]
STUDY = ROOT / 'outputs/autonomous_exploratory_reserve_20261014'
OUT = Path(__file__).resolve().parent


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def read(path):
    return json.loads(path.read_text())


def main():
    global STUDY, OUT
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--study', type=Path, default=STUDY)
    parser.add_argument('--out', type=Path, default=OUT)
    args = parser.parse_args()
    STUDY, OUT = args.study.resolve(), args.out.resolve()
    OUT.mkdir(parents=True, exist_ok=True)
    if (OUT / 'posthoc_retention.json').exists():
        raise ValueError('refuse replacing a previous recount')
    summary = read(STUDY / 'analysis_result/summary.json')
    assert summary['status'] == 'complete'
    clearance = read(STUDY / 'terminal_process_clearance.json')
    assert clearance['all_processes_exited'] is True
    lines = {}
    for run in ('control', 'reserve'):
        path = STUDY / 'runs' / run / 'lineage.jsonl'
        assert sha(path) == summary['native_audit']['read_artifact_sha256'][f'runs/{run}/lineage.jsonl']
        lines[run] = [json.loads(line) for line in path.read_text().splitlines()][1:]
        assert [row['gen'] for row in lines[run]] == [0, 1, 2, 3]
    control, reserve = lines['control'], lines['reserve']
    assert control[0]['exploratory_reserve']['base_F'] == reserve[0]['exploratory_reserve']['base_F']
    descendants = {i: set() for i in range(32)}
    decisions, protected_all = [], []
    for row in reserve:
        meta = row['exploratory_reserve']
        ids = meta['candidate_ids']
        initial = meta['ranking_calls'][1]['order']
        pooled = meta['ranking_calls'][2]['order']
        short = meta['shortlist_indices']
        protected = meta['reserve_ids']
        for child in row['children']:
            descendants[child['id']] = descendants[child['pa']] | descendants[child['pb']]
            if child['id'] in protected:
                descendants[child['id']] = descendants[child['id']] | {child['id']}
        ordinary_initial = [ids[i] for i in initial[:64]]
        measured_pooled = [ids[short[j]] for j in pooled[:32]]
        chosen = row['survivors']
        record = {'generation': row['gen'], 'protected_ids': protected,
            'ordinary_initial_shortlist_displaced': [i for i in ordinary_initial if i not in row['recheck']['ids']],
            'treatment_pooled_top32_displaced': [i for i in measured_pooled if i not in chosen],
            'protected': []}
        for item in protected:
            index = ids.index(item)
            position = short.index(index)
            record['protected'].append({'id': item, 'initial_rank_of_256': initial.index(index) + 1,
                'pooled_rank_of_treatment64': pooled.index(position) + 1,
                'initial_F': meta['base_F'][index], 'pooled_F': meta['ranking_calls'][2]['fitness'][position]})
        protected_all.extend(protected)
        decisions.append(record)
    assert len(protected_all) == 6 and len(set(protected_all)) == 6
    final_ids = reserve[-1]['survivors']
    endpoint = final_ids[0]
    ancestry = []
    for item in protected_all:
        uses = [{ 'generation': row['gen'], 'children': [child['id'] for child in row['children']
                 if child['pa'] == item or child['pb'] == item]} for row in reserve]
        ancestry.append({'protected_id': item, 'direct_child_counts_by_generation':
            [len(x['children']) for x in uses], 'direct_children_by_generation': uses,
            'final_population_genealogical_descendants': [i for i in final_ids if item in descendants[i]],
            'final_population_descendant_count': sum(item in descendants[i] for i in final_ids),
            'final_endpoint_genealogical_descendant': item in descendants[endpoint]})
    paths = ['analysis_result/summary.json', 'terminal_process_clearance.json',
             'runs/control/lineage.jsonl', 'runs/reserve/lineage.jsonl']
    output = {'status': 'complete_posthoc_descriptive_only',
        'input_pins': {name: sha(STUDY / name) for name in paths},
        'source_sha256': sha(Path(__file__)), 'protected_opportunities': 6,
        'selection_decisions': decisions,
        'generation0_same_cohort_control_comparison': {
            'ordinary_survivors_displaced': [i for i in control[0]['survivors'] if i not in reserve[0]['survivors']],
            'reserve_survivors_added': [i for i in reserve[0]['survivors'] if i not in control[0]['survivors']],
            'scope': 'Same reconstructed first cohort; later generations do not have a common genotype population.'},
        'final_endpoint_id': endpoint, 'genealogical_ancestry': ancestry,
        'primary_frozen_result': summary['primary_behavioral_estimate'],
        'limitations': ['Post hoc description; not preregistered mechanism evidence.',
            'Parentage union ignores which units cross over, inactive units, later mutations and functional effects.',
            'A protected ancestor is not proven necessary or beneficial by descendant membership.',
            'Treatment-shortlist pooled displacement is not generally the full ordinary counterfactual.',
            'No new capture estimate or genotype selection is made by this report.'],
        'simulation_calls': 0, 'compiled_libraries': 0, 'genetic_draws': 0}
    with (OUT / 'posthoc_retention.json').open('x') as stream:
        stream.write(json.dumps(output, indent=2, allow_nan=False) + '\n')
    print(json.dumps({'endpoint': endpoint, 'decisions': decisions,
        'ancestry': [{k: v for k, v in x.items() if k != 'direct_children_by_generation'} for x in ancestry],
        'generation0': output['generation0_same_cohort_control_comparison']}, indent=2))


if __name__ == '__main__':
    main()
