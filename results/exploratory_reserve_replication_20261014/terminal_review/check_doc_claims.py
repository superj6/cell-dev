"""Check final AI prose/figure data against the frozen complete result; no engines."""
from pathlib import Path
import hashlib
import json
import math
import re

ROOT = Path(__file__).resolve().parents[2]
A = Path(__file__).resolve().parent
S = ROOT / 'outputs/autonomous_exploratory_reserve_replication_20261014'


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def read(path):
    return json.loads(path.read_text())


def main():
    assert sha(S / 'analysis_result/summary.json') == 'a070f5b95edd37d95fc8d6cc9a5a87203cac3edc65baf6f18105dc36ccc3f2f9'
    s = read(S / 'analysis_result/summary.json')
    text = (A / 'terminal_text.md').read_text()
    assert text.strip() in (ROOT / 'RESULTS.md').read_text()
    rows = [s['contrasts']['primary']['AI_reserve'], s['contrasts']['gain']['AI_control'], s['contrasts']['gain']['AI_reserve']]
    lines = [line for line in text.splitlines() if line.startswith('| Reserve') or line.startswith('| Control')]
    assert len(lines) == 3
    for line, row in zip(lines, rows):
        values = [row['columns']['captures'], row['columns']['F'], row['fitness_pieces']['capture_income'], row['total_cost_saving']]
        for cell, value in zip(line.split('|')[2:6], values):
            numbers = re.findall(r'[+−-]?\d+\.\d+', cell)
            assert len(numbers) == 2
            assert all(math.isclose(float(n.replace('−', '-')), value[key], abs_tol=5.1e-7, rel_tol=0)
                       for n, key in zip(numbers, ('mean', 'se'))), (cell, value)
    primary, control, reserve = rows
    for key in ('captures', 'F'):
        value = primary['columns'][key]
        assert value['mean'] < -3 * value['se'] and value['negative_below_minus_3se']
    assert control['columns']['captures']['mean'] > 3 * control['columns']['captures']['se']
    assert abs(reserve['columns']['captures']['mean']) < 3 * reserve['columns']['captures']['se']
    assert primary['total_cost_saving']['mean'] < -3 * primary['total_cost_saving']['se']
    for row in (control, reserve):
        assert row['total_cost_saving']['mean'] > row['columns']['F']['mean'] / 2
    for row in rows:
        assert abs(row['columns']['F']['mean'] - row['fitness_pieces']['capture_income']['mean'] - row['total_cost_saving']['mean']) < 1e-12
        assert row['fitness_pieces']['guard_charge_saving']['mean'] == row['fitness_pieces']['extinction_charge_saving']['mean'] == 0
    assert all(v == 0 for row in s['confirmation_health'].values() for v in row.values())
    native = s['native_audit']
    assert native['first_base_F_bitwise_equal'] and native['matched_first_cohort']['candidate_shape'] == [256, 875]
    for mode, endpoint in (('control', 668), ('reserve', 887)):
        run = native['runs'][mode]
        assert run['final_rank_zero_id'] == endpoint
        assert sum(run['initial_evaluation_guard_lives_by_generation']) == 3
        assert run['selection']['sexual_offspring'] == 896
        assert run['selection']['logged_point_mutations_including_initial_copies'] == 1854
        assert run['selection']['tie_ranking_calls_replayed'] == 12
        assert run['genetic_replay']['raw_population_replay_bitwise']
        assert run['genetic_replay']['duplication_events'] == run['genetic_replay']['deletion_events'] == 0
        assert all(t['mean_active_genes'] == t['min_active_genes'] == t['max_active_genes'] == 8 for t in run['genetic_replay']['trajectory'])
        decisions = run['selection']['policy_decisions']
        assert not decisions[3]['active'] and not decisions[3]['protected_ids']
        if mode == 'reserve':
            assert sum(len(d['protected_ids']) for d in decisions) == 6
            assert sum(len(d['protected_outside_ordinary_initial_top64']) for d in decisions) == 5
            assert sum(len(d['protected_outside_treatment_pooled_top32']) for d in decisions) == 6
    b = read(S / 'budget.json')
    assert (s['research_lives'], s['startup_validation_lives'], s['total_lives']) == (9804, 6, 9810)
    assert b['cpu_seconds'] == s['resources']['total_cpu_seconds'] == 1068.361098
    assert b['search_stage_cpu_seconds'] == 923.782077
    assert abs(b['wall_seconds'] - 305.364878) < 5.1e-7
    assert len(b['process_identities']) == 4 and len(b['owned_process_groups']) == 3
    ah = read(ROOT / 'results/exploratory_reserve_20261014/analysis_result/summary.json')
    assert ah['primary_behavioral_estimate']['mean'] > 0 > s['primary_behavioral_estimate']['mean']
    figure = (A / 'figures/generate.py').read_text()
    assert "xerr=[3 * r['se'] for r in values]" in figure
    assert "[('primary', 'AI_reserve'), ('gain', 'AI_control'), ('gain', 'AI_reserve')]" in figure
    paths = [Path(__file__), A / 'terminal_text.md', A / 'update_terminal_docs.py', A / 'TERMINAL_README.md',
             S / 'analysis_result/summary.json', S / 'analysis_result/paired_vectors.npz',
             A / 'independent_terminal_raw_review.json', A / 'terminal_execution_review.json',
             *[A / 'figures' / n for n in ('generate.py', 'capture_and_economy.png', 'capture_and_economy.svg')],
             *[ROOT / n for n in ('README.md', 'RESULTS.md', 'docs/HANDOFF.md', 'docs/TASK_VARIATION_PLAN.md')]]
    receipt = {'status': 'passed', 'source_pins': {str(p.relative_to(ROOT)): sha(p) for p in paths},
        'table_contrasts_checked': 3, 'numeric_table_mean_se_pairs_checked': 12,
        'strict_thresholds': {'primary_captures_negative': True, 'primary_F_negative': True,
            'control_minus_start_captures_positive': True, 'reserve_minus_start_captures_resolved': False,
            'primary_ordinary_cost_increase_resolved': True},
        'native_initial_guard_summary': {'control': 3, 'reserve': 3, 'paid': True},
        'protected_counts': {'total': 6, 'outside_initial_top64': 5, 'outside_treatment_pooled_top32': 6},
        'interpretation': 'AH and AI have opposite relative endpoint effects and are reported separately; no general reserve advantage or algorithm/memory claim. Ordinary AI control has resolved own-start captures, with most F gain from economy.',
        'figure_review': 'Generator reads exact pinned summary and uses three paired SE, three contrasts and four panels; PNG visual inspection recorded before packaging.',
        'native_scope': 'Full recorded-operation populations/ranks reproduced; search guard summaries are not complete per-life raw ledgers.',
        'simulation_calls': 0, 'compiled_libraries': 0, 'new_genetic_draws': 0}
    target = A / 'doc_claim_review.json'
    target.write_text(json.dumps(receipt, indent=2) + '\n')
    print(json.dumps({'status': 'passed', 'sha256': sha(target)}))


if __name__ == '__main__':
    main()
