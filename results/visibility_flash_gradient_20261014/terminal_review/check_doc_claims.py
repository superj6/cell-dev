"""No-life cross-check of AC terminal prose against the frozen summary."""
import hashlib
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
AUDIT = Path(__file__).resolve().parent
STUDY = ROOT / 'outputs/autonomous_visibility_flash_gradient_20261014'
sha = lambda p: hashlib.sha256(p.read_bytes()).hexdigest()
s = json.loads((STUDY / 'analysis_result/summary.json').read_text())
docs = {n: ROOT / n for n in ('RESULTS.md', 'docs/HANDOFF.md', 'docs/TASK_VARIATION_PLAN.md')}
text = docs['RESULTS.md'].read_text().split('## 2026-10-14 — Flash selects different mutations, with economy and a tentative capture lead\n', 1)[1]
rows = []
for suffix, heading in (('P', '| H minus own parent'), ('B', '| H minus prior blink selection B')):
    table = text.split(heading, 1)[1].split('\n\n', 1)[0]
    lines = [line for line in table.splitlines() if line.startswith('| D90') or line.startswith('| L92')]
    assert len(lines) == 4
    for line, (world, lineage) in zip(lines, [('flash','D90'),('flash','L92'),('blink','D90'),('blink','L92')], strict=True):
        c = s['contrasts']['within'][world][f'H_{lineage}_minus_{suffix}_{lineage}']
        expected = [c['columns']['F'], c['columns']['captures'], c['fitness_pieces']['capture_income'], c['total_cost_saving']]
        values = line.split('|')[2:-1]
        for printed, actual in zip(values, expected, strict=True):
            mean, se = [float(t.strip().replace('−','-')) for t in printed.split('±')]
            assert abs(mean - actual['mean']) <= .00000501
            assert abs(se - actual['se']) <= .00000501
        rows.append({'world':world,'contrast':f'H_{lineage}_minus_{suffix}_{lineage}', 'metrics':expected})
interactions = []
for c, d in s['contrasts']['interactions'].items():
    interactions.append({'contrast':c, 'F':d['F'], 'captures':d['captures']})
    assert d['F']['positive_above_3se'] == (d['F']['mean'] > 3*d['F']['se'])
    assert d['captures']['positive_above_3se'] == (d['captures']['mean'] > 3*d['captures']['se'])
for world in ('flash','blink'):
    for lineage in ('D90','L92'):
        d=s['contrasts']['within'][world][f'B_{lineage}_minus_P_{lineage}']['columns']
        assert d['F']['positive_above_3se'] == (world=='blink' and lineage=='D90')
        assert d['captures']['positive_above_3se'] == (world=='blink' and lineage=='D90')
near = {}
for name, d in (
    ('L92_primary_capture', s['contrasts']['within']['flash']['H_L92_minus_P_L92']['columns']['captures']),
    ('L92_H_minus_B_F_interaction', s['contrasts']['interactions']['H_L92_minus_B_L92']['F']),
    ('L92_H_minus_B_capture_interaction', s['contrasts']['interactions']['H_L92_minus_B_L92']['captures'])):
    near[name] = {'mean':d['mean'],'three_se':3*d['se'],'margin':d['mean']-3*d['se'],'strict_positive':d['mean']>3*d['se']}
assert [d['strict_positive'] for d in near.values()] == [False, False, True]
assert s['research_lives']==10304 and s['validation_lives']==10 and s['total_lives']==10314
assert s['resources']['total_cpu_seconds']==2044.626301
assert s['resources']['startup_screen_cpu_seconds']==879.179945
assert s['resources']['confirmation_cpu_seconds']==1165.446356
assert len(set(s['roles']['genotype_sha256'].values()))==6
for name in ('H_D90_minus_P_D90','H_L92_minus_P_L92'):
    assert s['contrasts']['within']['flash'][name]['columns']['F']['positive_above_3se']
    assert not s['contrasts']['interactions'][name]['F']['positive_above_3se']
receipt = {'status':'passed','summary_sha256':sha(STUDY/'analysis_result/summary.json'),
 'documents':{n:sha(p) for n,p in docs.items()},'review_source_sha256':sha(Path(__file__)),
 'table_rows_checked':rows,'interactions':interactions,'strict_near_threshold_checks':near,
 'other_claims_reviewed':['All role rows and six distinct genomes match.','D90 gains through ordinary cost savings while losing captures in both worlds.','L92 secondary H-B capture gain does not replace the primary outcome.','No reciprocal specialization, isolated memory, prediction or independent-search reliability claim is supported.','Resource, life, release-pin and raw health counts agree with terminal receipts.'],
 'corrections_required':[],'new_simulations':0,'new_compilations':0}
(AUDIT/'doc_claim_review.json').write_text(json.dumps(receipt,indent=2)+'\n')
print(json.dumps({'status':'passed','review_sha256':sha(AUDIT/'doc_claim_review.json'),'near_threshold_checks':near}))
