"""AE final same-candidate delta, executable only after clean terminal CURRENT clearance.
Reads seed-token arrays only. Does not register, copy genotypes, build or simulate.
"""
from __future__ import annotations
import hashlib
import importlib.util
import io
import json
import os
from pathlib import Path
import subprocess
import zipfile
import numpy as np
ROOT=Path(__file__).resolve().parents[4]
OUT=Path(__file__).resolve().parent
PREVIOUS=ROOT/'outputs/autonomous_visibility_dark_tail_information_20261014'
CURRENT=ROOT/'outputs/autonomous_prediction_gradient_20261014'
BASE=ROOT/'results/visibility_flash_gradient_20261014/original/outputs/audit_visibility_lateral_20261014/npz_seed_baseline.json'
LOW,HIGH=52_280_000,52_310_000

def sha(p):return hashlib.sha256(p.read_bytes()).hexdigest()
def read(p):return json.loads(p.read_text())
def main():
 candidate=read(OUT/'candidate_namespace_review.json')
 reader_review=OUT.parent/'reader_source_review.json'
 if sha(reader_review)!='38a6b377f6d583270f79da97e2d8e82ce64d8587c1f8818705679fd2f0672cee':raise ValueError('reader fixture source-freeze receipt changed')
 if sha(OUT/'candidate_namespace_review.json')!='17ad7b0d95670e9c54e5d0db9315b42efeac4ace034bf67635ac4f2051b387bc':raise ValueError('accepted candidate receipt changed')
 inventory=read(OUT/'candidate_namespace_inventory.json')
 assert sha(OUT/'candidate_namespace_inventory.json')==candidate['inventory_sha256']
 assert sha(BASE)=='b5fbb637071e0bebae670b532742c4e8dec33cf05c7d6399419f06bb3daffb58'
 budget=read(PREVIOUS/'budget.json');clear=read(PREVIOUS/'terminal_process_clearance.json')
 if budget.get('status') not in ('complete','incomplete') or budget.get('running') or budget.get('queued') or budget.get('cleanup_error'):raise ValueError('clean terminal AD required')
 if clear.get('status')!='cleared' or clear.get('all_processes_exited') is not True or clear.get('budget_sha256')!=sha(PREVIOUS/'budget.json'):raise ValueError('root AD clearance required')
 assert {(x['pid'],x['start_ticks']) for x in clear['processes']}=={(x['pid'],x['start_ticks']) for x in budget['process_identities']}
 assert set(clear['process_groups'])==set(budget['owned_process_groups'])
 source=OUT/'namespace_audit.py';assert sha(source)==candidate['source_pins'][str(source.relative_to(ROOT))]
 spec=importlib.util.spec_from_file_location('CURRENT_seed_predicate',source);h=importlib.util.module_from_spec(spec);spec.loader.exec_module(h)
 prior=read(BASE)['records']
 for relative,digest in inventory['baseline_sources'].items():
  if relative==str(BASE.relative_to(ROOT)):continue
  oldsource=ROOT/relative;assert sha(oldsource)==digest;old=read(oldsource)
  prior.update(old.get('changed_npz_records',old.get('new_or_modified_npz_records')))
 prior.update(inventory['changed_npz_records'])
 seen=set();changed={};matches=[];errors=[];unchanged=arrays=0
 for top in (ROOT/'results',ROOT/'outputs'):
  for folder,dirs,names in os.walk(top,followlinks=False):
   base=Path(folder);dirs[:]=sorted(n for n in dirs if n not in h.SKIP and not (base/n).is_relative_to(OUT) and not (base/n).is_relative_to(CURRENT))
   for name in sorted(names):
    if not name.endswith('.npz'):continue
    path=base/name;relative=str(path.relative_to(ROOT));seen.add(relative);st=h.stat(path)
    if relative in prior and prior[relative].get('stat')==st:unchanged+=1;continue
    item={'stat':st,'synthetic_fixture':any(p.startswith('test_') for p in path.parts),'seed_members':{}};changed[relative]=item
    try:
     with zipfile.ZipFile(path) as z:
      for info in z.infolist():
       if not h.seed_member(info.filename):continue
       if info.filename in item['seed_members']:raise ValueError('duplicate seed member')
       raw=z.read(info);v=np.load(io.BytesIO(raw),allow_pickle=False)
       if not np.issubdtype(v.dtype,np.number) or not np.isfinite(v).all() or (not np.issubdtype(v.dtype,np.integer) and np.any(v!=np.floor(v))):raise ValueError('invalid seed member')
       arrays+=1;item['seed_members'][info.filename]={'sha256':hashlib.sha256(raw).hexdigest(),'dtype':str(v.dtype),'shape':list(v.shape)}
       hit=sorted({int(x) for x in v.flat if LOW<=int(x)<HIGH})
       if hit:matches.append({'path':relative,'member':info.filename,'values':hit})
     if h.stat(path)!=st:raise ValueError('changed during scan')
    except (OSError,ValueError,zipfile.BadZipFile,EOFError) as e:errors.append({'path':relative,'synthetic_fixture':item['synthetic_fixture'],'error':type(e).__name__+': '+str(e)})
 command=['rg','--no-ignore','-l','-0','-P','--glob','*.json','--glob','!**/test_*/**',r'(?<![0-9.])(?:522[89]|523[01])[0-9]{4}(?![0-9.])','results','outputs']
 found=subprocess.run(command,cwd=ROOT,capture_output=True);assert found.returncode in (0,1)
 pins={};hits=[];json_errors=[]
 def visit(v,trail,p):
  if isinstance(v,dict):
   for k,x in v.items():visit(x,trail+[str(k)],p)
  elif isinstance(v,list):
   for i,x in enumerate(v):visit(x,trail+[str(i)],p)
  elif isinstance(v,int) and not isinstance(v,bool) and LOW<=v<=HIGH:hits.append({'path':p,'field':'.'.join(trail),'value':v})
 for raw in sorted(set(found.stdout.split(b'\0'))-{b''}):
  relative=raw.decode();path=ROOT/relative
  if path.is_relative_to(OUT) or path.is_relative_to(CURRENT):continue
  try:pins[relative]=sha(path);visit(read(path),[],relative)
  except (OSError,ValueError) as e:json_errors.append({'path':relative,'error':str(e)})
 classified=all(x['value']==LOW and x['field'] in ('whole_block_half_open.1','same_whole_blocks_half_open.1.1','whole_blocks_half_open.1.1') for x in hits)
 passed=not matches and not [x for x in errors if not x['synthetic_fixture']] and not json_errors and classified
 result={'reader_fixture_freeze_receipt_sha256':sha(reader_review),'status':'passed' if passed else 'requires_review','candidate_receipt_sha256':sha(OUT/'candidate_namespace_review.json'),'prior_candidate_inventory_sha256':sha(OUT/'candidate_namespace_inventory.json'),'same_whole_blocks_half_open':candidate['whole_blocks_half_open'],'AD_terminal_status':budget['status'],'AD_terminal_budget_sha256':sha(PREVIOUS/'budget.json'),'AD_root_clearance_sha256':sha(PREVIOUS/'terminal_process_clearance.json'),'AD_registered_schedule_sha256':sha(PREVIOUS/'seed_audit.json'),'current_npz_paths':len(seen),'unchanged_npz_paths':unchanged,'new_or_modified_npz_records':changed,'removed_prior_paths':sorted(set(prior)-seen),'seed_members_read':arrays,'actual_overlaps':matches,'NPZ_errors':errors,'JSON_source_pins':pins,'JSON_numeric_matches':hits,'JSON_errors':json_errors,'JSON_classification':'Prior AD block127 exclusive endpoint only' if classified else 'Needs independent classification','limits':'Same-candidate baseline reuse uses recorded filesystem identity/stat and the earlier SHA-pinned seed-payload audit; no full-NPZ cryptographic hash claim. New/modified seed-token members only. No outcomes read.','reserved':False,'registered':False,'simulation_calls':0,'compilation_calls':0,'genotype_copies':0,'script_sha256':sha(Path(__file__))}
 (OUT/'final_namespace_delta.json').write_text(json.dumps(result,indent=2)+'\n')
 print(json.dumps({k:result[k] for k in ('status','AD_terminal_status','current_npz_paths','unchanged_npz_paths','seed_members_read','actual_overlaps','NPZ_errors','JSON_errors')},indent=2))
 if not passed:raise SystemExit(1)
if __name__=='__main__':main()
