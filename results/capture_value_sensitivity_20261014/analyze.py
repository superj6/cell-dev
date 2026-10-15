"""Exploratory repricing of fixed, already-observed AC contrasts; no new lives."""
from pathlib import Path
import hashlib,json
import numpy as np
ROOT=Path(__file__).resolve().parents[2]
OUT=Path(__file__).resolve().parent
AC=ROOT/'outputs/autonomous_visibility_flash_gradient_20261014'
def sha(p):return hashlib.sha256(p.read_bytes()).hexdigest()
def read(p):return json.loads(p.read_text())
EXPECTED={'protocol.json':'672ac123ca9283cd004e699cb6be1b0ac4203b468f75f03546140560cd58fda2',
 'analysis_result/summary.json':'f70691e072f070d0dee8e3bdf55e1c78c409e6d3dd4e746118c651ba499b10ed',
 'analysis_result/paired_vectors.npz':'6509e8ab4c9ddeb10655090d612608ec4de56d0ba4c34db2ecdde21f653f51ff',
 'terminal_process_clearance.json':'5af01429104cae73b5982ec5aa9d94ca58126d46ef5c0891dd6883f225368ce3'}
assert not (OUT/'summary.json').exists() and not (OUT/'paired_vectors.npz').exists()
for name,digest in EXPECTED.items():assert sha(AC/name)==digest,name
summary=read(AC/'analysis_result/summary.json');assert summary['status']=='complete'
assert all(w['R_cap']==500 and w['T']==1024 for w in summary['worlds'].values())
source=read(AC/'ready.json')['production_pins']
for name,digest in source.items():assert sha(ROOT/name)==digest,name
stored=np.load(AC/'analysis_result/paired_vectors.npz',allow_pickle=False)
results={};vectors={}
for world,contrasts in summary['contrasts']['within'].items():
 for key,item in contrasts.items():
  prefix=f'within__{world}__{key}'
  baseline=stored[prefix+'__F'];income=stored[prefix+'__F__capture_income']
  assert baseline.shape==income.shape==(512,)
  for value in [500,1000,2000]:
   v=baseline+(value/500-1)*income
   mean=float(v.mean());se=float(v.std(ddof=1)/np.sqrt(len(v)))
   label=f'R{value}__{prefix}'
   vectors[label]=v
   results[label]={'capture_value':value,'world':world,'comparison':key,'mean_F_change':mean,
      'paired_se':se,'n':len(v),'above_3se':mean>3*se,'below_minus_3se':mean < -3*se}
np.savez_compressed(OUT/'paired_vectors.npz',**vectors)
record={'status':'complete_exploratory_repricing','capture_values':[500,1000,2000],
 'new_simulated_lives':0,'new_genetic_draws':0,'new_compilations':0,'new_independent_evidence':False,
 'source_study':'AC','fixed_paired_lives':512,'comparisons':results,
 'input_pins':{str((AC/k).relative_to(ROOT)):v for k,v in EXPECTED.items()},
 'source_pins':{k:source[k] for k in ['src/life/kernel.c','src/life/evaluate.py','src/life/spec.py']},
 'analysis_sha256':sha(Path(__file__)),'plan_sha256':sha(OUT/'PLAN.md'),
 'paired_vectors_sha256':sha(OUT/'paired_vectors.npz'),
 'limitations':['Post hoc grid motivated by the observed economy/capture tradeoff.',
 'All uncertainty reuses AC observations; this is not fresh confirmation.',
 'Fixed genomes were selected under the original capture value, not the repriced objective.',
 'No claim about future evolved behavior, memory, or algorithmic sophistication.',
 'No production price, world, policy or AC primary finding has changed.']}
(OUT/'summary.json').write_text(json.dumps(record,indent=2)+'\n')
for key,item in results.items():
 if item['comparison']=='H_D90_minus_B_D90':print(key,item['mean_F_change'],item['paired_se'])
print(json.dumps({'status':record['status'],'vectors':len(vectors),'new_lives':0,'summary_sha256':sha(OUT/'summary.json')}))
