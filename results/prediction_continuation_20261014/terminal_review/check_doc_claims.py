"""Check completed AF prose against the frozen independently reviewed summary."""
from pathlib import Path
import hashlib
import json

ROOT = Path(__file__).resolve().parents[2]
AUDIT = Path(__file__).resolve().parent
STUDY = ROOT / 'outputs/autonomous_prediction_continuation_20261014'


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def main():
    summary = json.loads((STUDY / 'analysis_result/summary.json').read_text())
    assert sha(STUDY / 'analysis_result/summary.json') == 'b544f4c337389566ed386df8d0453f7f6ca6e7ab6453a682599d844dc9d7be61'
    text = (AUDIT / 'terminal_result_text.md').read_text()
    primary = summary['contrasts']['primary']
    checked = []

    def check(label, actual, shown):
        assert shown in text, (label, shown)
        parsed = float(shown.replace(',', '').replace('−', '-'))
        assert abs(parsed - actual) <= .000005000001, (label, parsed, actual)
        checked.append({'claim': label, 'actual': actual, 'rendered': shown})

    rendered = {
        'AF_D90': [('F', '+.73529', '.06459'), ('captures', '−.34180', '.13345')],
        'AF_L92': [('F', '+1.43758', '.05065'), ('captures', '−1.92969', '.10146')],
    }
    for role, fields in rendered.items():
        for metric, mean, se in fields:
            check(f'{role}.{metric}.mean', primary[role]['columns'][metric]['mean'], mean)
            check(f'{role}.{metric}.se', primary[role]['columns'][metric]['se'], se)
    for role, income, income_se, cost, cost_se in (
            ('AF_D90', '−.16689', '.06516', '+.90218', '.01283'),
            ('AF_L92', '−.94223', '.04954', '+2.37981', '.01221')):
        value = primary[role]
        check(role + '.capture_income.mean', value['fitness_pieces']['capture_income']['mean'], income)
        check(role + '.capture_income.se', value['fitness_pieces']['capture_income']['se'], income_se)
        check(role + '.cost_saving.mean', value['total_cost_saving']['mean'], cost)
        check(role + '.cost_saving.se', value['total_cost_saving']['se'], cost_se)
        assert value['columns']['F']['positive_above_3se']
        assert not value['columns']['captures']['positive_above_3se']
        assert value['fitness_pieces']['guard_charge_saving']['mean'] == 0
        assert value['fitness_pieces']['extinction_charge_saving']['mean'] == 0
        costs = {k: v['mean'] for k, v in value['fitness_pieces'].items() if k.endswith('_cost_saving')}
        assert max(costs, key=costs.get) == 'living_cost_saving'
    assert not primary['AF_D90']['columns']['captures']['negative_below_minus_3se']
    assert primary['AF_L92']['columns']['captures']['negative_below_minus_3se']
    absolute = summary['absolute_means']
    for role, metric, shown in (
            ('AE_L92', 'captures', '3.85938'), ('AF_L92', 'captures', '1.92969'),
            ('AE_L92', 'F', '−.83237'), ('AF_L92', 'F', '+.60520'),
            ('AE_L92', 'n_end', '108.96094'), ('AF_L92', 'n_end', '13.06250'),
            ('AE_L92', 'spikes', '2,517.89063'), ('AF_L92', 'spikes', '84.01563'),
            ('AE_D90', 'captures', '5.81445'), ('AF_D90', 'captures', '5.47266'),
            ('AE_D90', 'F', '+.12332'), ('AF_D90', 'F', '+.85861')):
        check(f'{role}.{metric}', absolute[role][metric]['mean'], shown)
    assert absolute['AE_L92']['captures']['mean'] == 2 * absolute['AF_L92']['captures']['mean']
    for role, metric, mean, se in (
            ('AF_L92', 'misses', '28.83789', '.51566'), ('AF_L92', 'path', '150.59793', '1.97385'),
            ('AF_D90', 'n_end', '39.26758', '.52442'), ('AF_D90', 'spikes', '2,582.44727', '52.52066')):
        check(f'{role}.fewer_{metric}.mean', -primary[role]['columns'][metric]['mean'], mean)
        check(f'{role}.fewer_{metric}.se', primary[role]['columns'][metric]['se'], se)
    assert (summary['research_lives'], summary['startup_validation_lives'], summary['total_lives']) == (10316, 6, 10322)
    budget = json.loads((STUDY / 'budget.json').read_text())
    check('total_CPU', budget['cpu_seconds'], '1,191.290362')
    check('search_CPU', budget['search_stage_cpu_seconds'], '1,012.253396')
    check('confirmation_CPU', summary['resources']['confirmation_cpu_seconds'], '179.036966')
    check('wall_seconds', budget['wall_seconds'], '372.726189')
    runs = summary['native_audit']['runs']
    assert [sum(runs[str(seed)]['initial_evaluation_guard_lives_by_generation']) for seed in (53224, 53225)] == [18, 9]
    assert all(not any(row.values()) for row in summary['confirmation_health'].values())
    assert all(row['genetic_replay']['raw_population_replay_bitwise'] and row['all_final_population_rows_bound']
               for row in runs.values())
    files = [ROOT / p for p in ('README.md', 'RESULTS.md', 'docs/HANDOFF.md', 'docs/TASK_VARIATION_PLAN.md')]
    files += [AUDIT / p for p in ('terminal_result_text.md', 'update_terminal_docs.py', 'TERMINAL_README.md')]
    receipt = {'status': 'passed_terminal_claim_review', 'summary_sha256': sha(STUDY / 'analysis_result/summary.json'),
               'raw_review_sha256': sha(STUDY / 'terminal_review/independent_terminal_raw_review.json'),
               'source_pins': {str(path.relative_to(ROOT)): sha(path) for path in files},
               'numeric_claims': checked, 'classification': 'Both F gains are cost savings; D90 capture change unresolved, L92 capture loss resolved.',
               'scope_limits_checked': ['No original-parent confirmation arms in AF.',
                   'Two fixed runs do not measure evolutionary reliability or identify a memory/prediction mechanism.',
                   '27 guarded initial search evaluations are distinguished from2048 clean raw confirmations.',
                   'All146 paired vectors and both native populations independently reproduced; startup goldens are recorded identity receipts.',
                   'AG remains source-only; no registration, inputs, draws, builds or lives authorized by AF results.'],
               'simulation_calls': 0, 'compilation_calls': 0}
    (AUDIT / 'doc_claim_review.json').write_text(json.dumps(receipt, indent=2) + '\n')
    print(json.dumps({'status': receipt['status'], 'numeric_claims_checked': len(checked),
                      'receipt_sha256': sha(AUDIT / 'doc_claim_review.json')}))


if __name__ == '__main__':
    main()
