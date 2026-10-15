"""Check AE terminal headline arithmetic and reviewed documentation; no engine calls."""
from pathlib import Path
import hashlib
import json
import numpy as np
ROOT=Path(__file__).resolve().parents[3]
OUT=Path(__file__).resolve().parent
STUDY=ROOT/'outputs/autonomous_prediction_gradient_20261014'
def sha(path):return hashlib.sha256(path.read_bytes()).hexdigest()
def read(path):return json.loads(path.read_text())
def main():
 d=read(STUDY/'analysis_result/summary.json');b=read(STUDY/'budget.json');raw=read(STUDY/'terminal_review/independent_terminal_raw_review.json')
 assert sha(STUDY/'analysis_result/summary.json')=='e269cab21b720053fcb0ae14febfd62b76a86c7a91bb49cc0a7cedc536721628'
 assert d['total_lives']==6218 and d['research_lives']==6208 and d['validation_lives']==10
 assert b['cpu_seconds']==1226.079103 and round(b['wall_seconds'],6)==540.565354
 assert round(b['phase_receipts']['calibration_complete']['cpu_seconds'],6)==13.689933
 assert round(d['resources']['startup_screen_cpu_seconds'],6)==874.767044
 assert round(d['resources']['confirmation_cpu_seconds'],6)==351.312059
 assert raw['raw_lives']==6216 and raw['numerical_goldens']==2 and raw['raw_rows']==138
 assert all(set(x['status_histogram'])=={'0'} for x in raw['raw_health'].values())
 checks={}
 with np.load(STUDY/'analysis_result/paired_vectors.npz',allow_pickle=False) as vectors:
  assert len(vectors.files)==128
  for contrast,terms in d['contrasts'].items():
   for metric,item in terms.items():
    v=vectors[contrast+'__'+metric];assert v.shape==(512,)
    assert float(v.mean())==item['mean'] and float(v.std(ddof=1)/np.sqrt(v.size))==item['se']
   pieces=sum(vectors[contrast+'__'+k] for k in ('capture_income','ordinary_cost','guard_cost','extinction_cost'))
   assert np.allclose(vectors[contrast+'__F'],pieces,atol=1e-9,rtol=0)
   assert not np.any(vectors[contrast+'__guard_cost']) and not np.any(vectors[contrast+'__extinction_cost'])
   checks[contrast]={k:terms[k] for k in ('F','captures','capture_income','ordinary_cost','n_end','spikes','misses')}
 x=d['contrasts']['H_D90_minus_P_D90'];y=d['contrasts']['H_L92_minus_P_L92']
 assert x['F']['mean']>3*x['F']['se'] and abs(x['captures']['mean'])<3*x['captures']['se']
 assert y['F']['mean']>3*y['F']['se'] and y['captures']['mean']>3*y['captures']['se']
 assert y['ordinary_cost']['mean']>y['capture_income']['mean']>0
 assert d['roles']['panel_rows']=={'P_D90':0,'H_D90':54,'P_L92':0,'H_L92':31}
 prior={n:read(ROOT/'results'/n/'selection.json') for n in ('visibility_gradient_20261014','visibility_flash_gradient_20261014')}
 assert prior['visibility_flash_gradient_20261014']['D90']['raw_sha256']==d['roles']['genotype_sha256']['H_D90']
 assert all(v['L92']['genome_row']!=31 for v in prior.values())
 mutations={}
 for p,i in [('D90',54),('L92',31)]:mutations[p]=read(STUDY/f'inputs/Y/inputs/{p}/mutation_ops.json')[i-1]
 assert mutations['D90']['mut']==[['W',[0,23],-0.7830668687820435],['W',[7,24],-0.6494652032852173]]
 assert mutations['L92']['mut']==[['W',[7,7],-0.6144153475761414],['W',[5,0],0.3049311637878418]]
 evidence=[OUT/'TERMINAL_README.md',OUT/'terminal_results_text.md',OUT/'update_terminal_docs.py',ROOT/'RESULTS.md',ROOT/'docs/HANDOFF.md',ROOT/'docs/TASK_VARIATION_PLAN.md',Path(__file__)]
 result={'status':'passed','summary_sha256':sha(STUDY/'analysis_result/summary.json'),'paired_vectors_sha256':sha(STUDY/'analysis_result/paired_vectors.npz'),'all128_summary_statistics_recomputed':True,'both_physical_decompositions_reconciled':True,'headlines':checks,'absolute_means':d['absolute_means'],'recorded_selected_mutations':mutations,'historical_selection_pins':{str((ROOT/'results'/n/'selection.json').relative_to(ROOT)):sha(ROOT/'results'/n/'selection.json') for n in prior},'documentation_pins':{str(p.relative_to(ROOT)):sha(p) for p in evidence},'manual_document_review':['The latest RESULTS entry and AE-complete HANDOFF/plan paragraphs match the full mean/SE, absolute fitness/capture, size/activity, timing, scope and selected-allele records.','D90 capture decrease is unresolved at the fixed three-SE criterion.','L92 has a small resolved capture-income gain, smaller than its positive cost savings. Both contributions have the same sign.','No tracking, prediction, memory, learning, isolated-allele or general search-reliability claim is made.','Historical preparation entries remain explicitly chronological; future AF notes are unreleased.'],'new_lives':0,'new_compilations':0}
 (OUT/'doc_claim_review.json').write_text(json.dumps(result,indent=2)+'\n');print(json.dumps({'status':'passed','receipt_sha256':sha(OUT/'doc_claim_review.json'),'arrays':128}))
if __name__=='__main__':main()
