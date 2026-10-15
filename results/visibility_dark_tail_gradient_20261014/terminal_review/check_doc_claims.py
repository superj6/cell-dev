"""Check AG terminal headline arithmetic and reviewed documentation; no engine calls."""
from pathlib import Path
import hashlib,json
import numpy as np
ROOT=Path(__file__).resolve().parents[2]
OUT=Path(__file__).resolve().parent
S=ROOT/'outputs/autonomous_visibility_dark_tail_gradient_20261014'
sha=lambda p:hashlib.sha256(p.read_bytes()).hexdigest()
read=lambda p:json.loads(p.read_text())
d=read(S/'analysis_result/summary.json');b=read(S/'budget.json');raw=read(S/'terminal_review/independent_terminal_raw_review.json')
assert sha(S/'analysis_result/summary.json')=='0395a7f2e8f182b656b64298071d363252b1abc8d59c437a12d7e7740ce7db57'
assert (d['research_lives'],d['validation_lives'],d['total_lives'])==(6208,10,6218)
assert round(b['cpu_seconds'],6)==1204.022071 and round(b['wall_seconds'],6)==529.776304
assert round(d['resources']['startup_screen_cpu_seconds'],6)==858.650131 and round(d['resources']['confirmation_cpu_seconds'],6)==345.371940
assert raw['raw_lives']==6216 and raw['numerical_goldens']==2 and raw['raw_rows']==138
assert all(set(x['status_histogram'])=={'0'} for x in raw['raw_health'].values())
checks={}
with np.load(S/'analysis_result/paired_vectors.npz',allow_pickle=False) as vectors:
 assert len(vectors.files)==132
 for contrast,terms in d['contrasts'].items():
  for metric,item in terms.items():
   v=vectors[contrast+'__'+metric];assert v.shape==(512,)
   assert float(v.mean())==item['mean'] and float(v.std(ddof=1)/np.sqrt(v.size))==item['se']
   assert item['positive_above_3se']==(item['mean']>3*item['se'])
  pieces=sum(vectors[contrast+'__'+k] for k in ('capture_income','ordinary_cost','guard_cost','extinction_cost'))
  assert np.allclose(vectors[contrast+'__F'],pieces,atol=1e-9,rtol=0)
  assert not np.any(vectors[contrast+'__guard_cost']) and not np.any(vectors[contrast+'__extinction_cost'])
  assert np.array_equal(vectors[contrast+'__captures'],vectors[contrast+'__low_light_captures']+vectors[contrast+'__bright_captures'])
  checks[contrast]={k:terms[k] for k in ('F','captures','low_light_captures','bright_captures','capture_income','ordinary_cost','n_end','spikes')}
x=d['contrasts']['H_D90_minus_P_D90'];y=d['contrasts']['H_L92_minus_P_L92']
assert x['F']['mean']>3*x['F']['se'] and abs(x['captures']['mean'])<3*x['captures']['se']
assert y['F']['mean']>3*y['F']['se'] and y['captures']['mean']>3*y['captures']['se']
assert y['low_light_captures']['mean']<3*y['low_light_captures']['se']
assert y['ordinary_cost']['mean']>y['capture_income']['mean']>0
assert d['roles']['panel_rows']=={'P_D90':0,'H_D90':54,'P_L92':0,'H_L92':61}
mutations={p:read(S/f'inputs/Y/inputs/{p}/mutation_ops.json')[i-1] for p,i in [('D90',54),('L92',61)]}
assert mutations['L92']['mut']==[['A',[18,7],0.15874287486076355],['A',[10,7],-1.2523930072784424]]
evidence=[OUT/'TERMINAL_README.md',OUT/'terminal_text.md',OUT/'update_terminal_docs.py',ROOT/'README.md',ROOT/'RESULTS.md',ROOT/'docs/HANDOFF.md',ROOT/'docs/TASK_VARIATION_PLAN.md',OUT/'figures/generate.py',Path(__file__)]
r={'status':'passed','summary_sha256':sha(S/'analysis_result/summary.json'),'paired_vectors_sha256':sha(S/'analysis_result/paired_vectors.npz'),'all132_summary_statistics_recomputed':True,'both_physical_decompositions_reconciled':True,'headlines':checks,'absolute_means':d['absolute_means'],'recorded_selected_mutations':mutations,'documentation_pins':{str(p.relative_to(ROOT)):sha(p) for p in evidence},'manual_document_review':['The latest RESULTS entry, README and AG-complete HANDOFF/plan paragraphs match mean/SE, absolute means, resource counts and selected row records.','L92 total captures strictly exceed three SE; dark captures remain below three SE using unrounded values.','Most L92 F gain is cost saving; its mean F remains negative. D90 capture change is unresolved.','Five bright time units follow every target placement, including replacements; background activity continues.','No memory, prediction, mechanism, general evolutionary reliability or controlled dark-versus-dim claim is made.','Historical preparation prose stays chronological; AH remains source-only and unreleased.'],'new_lives':0,'new_compilations':0}
(OUT/'doc_claim_review.json').write_text(json.dumps(r,indent=2)+'\n')
print(json.dumps({'status':'passed','receipt_sha256':sha(OUT/'doc_claim_review.json'),'arrays':132}))
