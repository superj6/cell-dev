"""Check AH terminal prose against complete reviewed summary; no engine calls."""
from pathlib import Path
import hashlib
import json
import math
import re

ROOT = Path(__file__).resolve().parents[2]
A = Path(__file__).resolve().parent
S = ROOT / 'outputs/autonomous_exploratory_reserve_20261014'


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def read(path):
    return json.loads(path.read_text())


def main():
    assert sha(S / 'analysis_result/summary.json') == 'fc097ab9a104d0211351ab77bc88cce351dee8cba05f0f597c369de6d132aa26'
    s = read(S / 'analysis_result/summary.json')
    text = (A / 'terminal_text.md').read_text()
    assert text.strip() in (ROOT / 'RESULTS.md').read_text()
    rows = [s['contrasts']['primary']['AH_reserve'], s['contrasts']['gain']['AH_control'], s['contrasts']['gain']['AH_reserve']]
    lines = [line for line in text.splitlines() if line.startswith('| Reserve') or line.startswith('| Control')]
    assert len(lines) == 3
    for line, row in zip(lines, rows):
        cells = line.split('|')[2:6]
        values = [row['columns']['captures'], row['columns']['F'], row['fitness_pieces']['capture_income'], row['total_cost_saving']]
        for cell, value in zip(cells, values):
            numbers = re.findall(r'[+−-]?\d+\.\d+', cell)
            assert len(numbers) == 2
            assert all(math.isclose(float(number.replace('−', '-')), value[key], rel_tol=0, abs_tol=5.1e-7)
                       for number, key in zip(numbers, ('mean', 'se'))), (cell, value)
    primary, control, reserve = rows
    for key in ('captures', 'F'):
        value = primary['columns'][key]
        assert value['mean'] > 3 * value['se'] and value['positive_above_3se']
    for row in (control, reserve):
        value = row['columns']['captures']
        assert abs(value['mean']) < 3 * value['se'] and not value['positive_above_3se']
        assert row['total_cost_saving']['mean'] > row['columns']['F']['mean'] / 2
    assert primary['fitness_pieces']['capture_income']['mean'] > primary['columns']['F']['mean'] > 0
    cost = primary['total_cost_saving']
    assert cost['mean'] < 0 and abs(cost['mean']) < 3 * cost['se']
    assert '3 SE = 0.347902' in text and abs(3 * reserve['columns']['captures']['se'] - .347902) < 5.1e-7
    for row in rows:
        assert row['fitness_pieces']['guard_charge_saving']['mean'] == row['fitness_pieces']['extinction_charge_saving']['mean'] == 0
        assert abs(row['columns']['F']['mean'] - row['fitness_pieces']['capture_income']['mean'] - row['total_cost_saving']['mean']) < 1e-12
    for role in ('AE_L92', 'AH_control', 'AH_reserve'):
        assert all(value == 0 for value in s['confirmation_health'][role].values())
        for key in ('F', 'captures', 'n_end'):
            number = s['absolute_means'][role][key]['mean']
            tokens = [float(v.replace('−', '-')) for v in re.findall(r'[+−-]?\d+\.\d+', text)]
            assert any(abs(v - number) <= 5.1e-7 for v in tokens), (role, key)
    native = s['native_audit']
    assert native['first_base_F_bitwise_equal'] and native['matched_first_cohort']['candidate_shape'] == [256, 875]
    for role, rank0, guards in (('control', 870, 12), ('reserve', 895, 18)):
        run = native['runs'][role]
        assert run['final_rank_zero_id'] == rank0
        assert sum(run['initial_evaluation_guard_lives_by_generation']) == guards
        assert run['selection']['sexual_offspring'] == 896
        assert run['selection']['logged_point_mutations_including_initial_copies'] == 1854
        assert run['selection']['tie_ranking_calls_replayed'] == 12
        assert run['genetic_replay']['raw_population_replay_bitwise']
        assert run['genetic_replay']['duplication_events'] == run['genetic_replay']['deletion_events'] == 0
        assert all(item['mean_active_genes'] == item['min_active_genes'] == item['max_active_genes'] == 8 for item in run['genetic_replay']['trajectory'])
        decisions = run['selection']['policy_decisions']
        assert not decisions[3]['active'] and not decisions[3]['protected_ids']
        if role == 'reserve':
            for item in decisions[:3]:
                assert len(item['protected_ids']) == 2 and item['active']
                assert item['protected_ids'] == item['protected_outside_ordinary_initial_top64'] == item['protected_outside_treatment_pooled_top32']
    assert math.isclose(primary['columns']['spikes']['mean'], 192.001953, abs_tol=5.1e-7, rel_tol=0)
    assert math.isclose(primary['columns']['spikes']['se'], 15.684410, abs_tol=5.1e-7, rel_tol=0)
    b = read(S / 'budget.json')
    assert (s['research_lives'], s['startup_validation_lives'], s['total_lives']) == (9804, 6, 9810)
    assert b['cpu_seconds'] == s['resources']['total_cpu_seconds'] == 862.767205
    assert abs(b['wall_seconds'] - 257.302628) < 5.1e-7
    assert b['search_stage_cpu_seconds'] == 720.896357
    assert abs(s['resources']['confirmation_cpu_seconds'] - 141.870848) < 1e-10
    assert len(b['process_identities']) == 4 and len(b['owned_process_groups']) == 3
    for name in ('docs/HANDOFF.md', 'docs/TASK_VARIATION_PLAN.md'):
        document = (ROOT / name).read_text()
        assert '0.556641' in document and '0.254917' in document
    overview = (ROOT / 'README.md').read_text()
    for key in ('captures', 'F'):
        value = primary['columns'][key]
        assert f"+{value['mean']:.3f} ± {value['se']:.3f}" in overview
    figure = (A / 'figures/generate.py').read_text()
    assert "xerr=[3 * r['se'] for r in values]" in figure
    assert "[('primary', 'AH_reserve'), ('gain', 'AH_control'), ('gain', 'AH_reserve')]" in figure
    posthoc = read(A / 'posthoc_independent_review.json')
    assert posthoc['status'] == 'passed_independent_backward_parentage_recount'
    assert not posthoc['endpoint_has_protected_ancestor'] and posthoc['nonempty_final_descendants'] == {'329': [882, 668, 856]}
    assert 'Post hoc lineage check' in text and 'three of the final 32' in text
    paths = [Path(__file__), A / 'terminal_text.md', A / 'update_terminal_docs.py', A / 'TERMINAL_README.md',
             S / 'analysis_result/summary.json', S / 'analysis_result/paired_vectors.npz',
             A / 'independent_terminal_raw_review.json', A / 'terminal_execution_review.json',
             A / 'posthoc_independent_review.json', A / 'future_direction/curated_manifest.json',
             *[A / 'figures' / n for n in ('generate.py', 'capture_and_economy.png', 'capture_and_economy.svg')],
             *[ROOT / n for n in ('README.md', 'RESULTS.md', 'docs/HANDOFF.md', 'docs/TASK_VARIATION_PLAN.md')]]
    receipt = {'status': 'passed', 'source_pins': {str(path.relative_to(ROOT)): sha(path) for path in paths},
        'table_contrasts_checked': 3, 'numeric_table_mean_se_pairs_checked': 12,
        'strict_thresholds': {'primary_captures_positive': True, 'primary_F_positive': True,
            'reserve_minus_start_captures_positive': False, 'control_minus_start_captures_resolved': False,
            'relative_ordinary_cost_difference_resolved': False},
        'native_guard_summary': {'control': 12, 'reserve': 18, 'paid': True,
            'limit': 'Initial-search summaries only; no complete per-life native raw ledger claim.'},
        'policy_replay': '24rank calls,6protectedIDs and both final populations match. Actual treatment pooled ranks do not reveal later unobserved ordinary counterfactuals.',
        'figure_review': 'Viewed PNG directly: readable four panels, all three contrasts, explicit three-SE bars and single-pair limit; no clipping. Generator uses pinned summary means and3*SE.',
        'narrative_scope': 'Relative endpoint capture advantage supported by income; own-start capture change unresolved; one deliberately selected background/pair, no reliability or memory claim.',
        'posthoc_scope': 'Independent backward ancestry recount confirms no protected ancestry for endpoint895; only329 has3/32 final descendants. No functional contribution or necessary-step claim.',
        'corrections': ['Checker initially required six decimals in the three-decimal README overview; corrected only checker formatting, with source/error preserved in history. No numerical or narrative correction was needed.'], 'simulation_calls': 0, 'compiled_libraries': 0, 'new_genetic_draws': 0}
    (A / 'doc_claim_review.json').write_text(json.dumps(receipt, indent=2) + '\n')
    print(json.dumps({'status': 'passed', 'sha256': sha(A / 'doc_claim_review.json')}))


if __name__ == '__main__':
    main()
