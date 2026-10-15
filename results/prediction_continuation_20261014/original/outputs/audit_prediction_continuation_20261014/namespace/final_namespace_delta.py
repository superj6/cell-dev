"""AF final candidate delta after reader freeze; seed metadata only, no reservation or lives."""
from pathlib import Path
import hashlib, importlib.util, io, json, os, re, subprocess, zipfile
import numpy as np
ROOT=Path(__file__).resolve().parents[3]
OUT=Path(__file__).resolve().parent
LOW,HIGH=52_310_000,52_320_000
CURRENT=ROOT/'outputs/autonomous_prediction_continuation_20261014'
AE=ROOT/'outputs/autonomous_prediction_gradient_20261014'
def sha(p):return hashlib.sha256(p.read_bytes()).hexdigest()
def read(p):return json.loads(p.read_text())
def main():
 candidate=read(OUT/'candidate_namespace_review.json')
 assert sha(OUT/'candidate_namespace_review.json')=='e222ea04351e44c84216cc7c8817a4bfa8b77dcce1e457b8a0db39c67edee26a'
 assert sha(OUT.parent/'reader_source_review.json')=='49784209ceb2c4b2f92157a2b2af10c459bd91ffe83b7776f939eebad827350d'
 d=read(OUT/'candidate_namespace_inventory.json');assert sha(OUT/'candidate_namespace_inventory.json')==candidate['inventory_sha256']
 s=importlib.util.spec_from_file_location('af_delta_predicate',OUT/'namespace_audit.py');h=importlib.util.module_from_spec(s);s.loader.exec_module(h)
 native=set(sum(d['run_life_seeds'].values(),[]));runs=set(candidate['runs'])
 budget=read(AE/'budget.json');clear=read(AE/'terminal_process_clearance.json')
 assert budget['status']=='complete' and not budget['running'] and not budget['queued'] and not budget.get('cleanup_error')
 assert clear['status']=='cleared' and clear['all_processes_exited'] and clear['budget_sha256']==sha(AE/'budget.json')
 prior={}
 for relative,digest in d['baseline_sources'].items():
  source=ROOT/relative;assert sha(source)==digest;x=read(source)
  prior.update(x.get('records',x.get('changed_npz_records',x.get('new_or_modified_npz_records'))))
 prior.update(d['changed_npz_records']);prior.update(candidate['postfreeze_synthetic_records'])
 changed={};seen=set();unchanged=arrays=0;matches=[];errors=[]
 for top in (ROOT/'results',ROOT/'outputs'):
  for folder,dirs,names in os.walk(top,followlinks=False):
   base=Path(folder);dirs[:]=sorted(n for n in dirs if n not in h.SKIP and not (base/n).is_relative_to(OUT) and not (base/n).is_relative_to(CURRENT))
   for name in sorted(names):
    if not name.endswith('.npz'):continue
    p=base/name;rel=str(p.relative_to(ROOT));seen.add(rel);st=h.stat(p)
    if rel in prior and prior[rel].get('stat')==st:unchanged+=1;continue
    record={'stat':st,'synthetic_fixture':any(v.startswith('test_') for v in p.parts),'seed_members':{}};changed[rel]=record
    try:
     with zipfile.ZipFile(p) as z:
      for info in z.infolist():
       if not h.seed_member(info.filename):continue
       assert info.filename not in record['seed_members']
       raw=z.read(info);a=np.load(io.BytesIO(raw),allow_pickle=False)
       if not np.issubdtype(a.dtype,np.number) or not np.isfinite(a).all() or (not np.issubdtype(a.dtype,np.integer) and np.any(a!=np.floor(a))):raise ValueError('invalid seed member')
       arrays+=1;record['seed_members'][info.filename]={'sha256':hashlib.sha256(raw).hexdigest(),'shape':list(a.shape),'dtype':str(a.dtype)}
       hits=sorted({int(x) for x in a.flat if LOW<=int(x)<HIGH or int(x) in native})
       if hits:matches.append({'path':rel,'member':info.filename,'values':hits})
     if h.stat(p)!=st:raise ValueError('file changed during delta scan')
    except (OSError,ValueError,zipfile.BadZipFile,EOFError) as e:errors.append({'path':rel,'error':type(e).__name__+': '+str(e),'synthetic_fixture':record['synthetic_fixture']})
 pattern=r'(?<![0-9.])(?:523[12][0-9]{4}|'+'|'.join(map(str,sorted(native|runs)))+r')(?![0-9.])'
 found=subprocess.run(['rg','--no-ignore','-l','-0','-P','--glob','*.json','--glob','!**/test_*/**',pattern,'results','outputs'],cwd=ROOT,capture_output=True);assert found.returncode in (0,1)
 pins={};hits=[];jerrors=[]
 def visit(v,trail,path):
  if isinstance(v,dict):
   for key,value in v.items():visit(value,trail+[str(key)],path)
  elif isinstance(v,list):
   for i,value in enumerate(v):visit(value,trail+[str(i)],path)
  elif type(v) is int and (LOW<=v<=HIGH or v in native|runs):hits.append({'path':path,'field':'.'.join(trail),'value':v})
 for raw in sorted(set(found.stdout.split(b'\0'))-{b''}):
  rel=raw.decode();p=ROOT/rel
  if p.is_relative_to(OUT) or p.is_relative_to(CURRENT):continue
  try:pins[rel]=sha(p);visit(read(p),[],rel)
  except (OSError,ValueError) as e:jerrors.append({'path':rel,'error':str(e)})
 fields={'whole_blocks_half_open.2.1','whole_block_half_open.1','same_whole_blocks_half_open.2.1'}
 assert all(x['value']==LOW and x['field'] in fields and 'prediction_gradient_20261014' in x['path'] for x in hits)
 # Bound the separate root-owned illustrative reuse without loading genome or outcome arrays.
 watch=ROOT/'outputs/ae_watchable_20261014';watchreview={}
 if (watch/'validation_budget.json').exists():
  w=read(watch/'validation_budget.json')
  assert w['status']=='complete' and w['all_processes_exited'] and w['js_replay_lives']==4 and w['new_C_lives']==w['new_research_lives']==0
  watch_names=('bodies.json','truth.json','export_receipt.json','export_initial_error.json','validation_attempt.json','replay_stdout.json','validation_budget.json')
  wpins={str((watch/n).relative_to(ROOT)):sha(watch/n) for n in watch_names}
  values={n:sorted({int(x) for x in re.findall(r'"seed"\s*:\s*"?([0-9]+)',(watch/n).read_text())}) for n in ('bodies.json','truth.json')}
  assert set(sum(values.values(),[]))=={52300000}
  assert 52300000 in read(AE/'protocol.json')['seeds']['confirm'] and not LOW<=52300000<HIGH and 52300000 not in native
  watchreview={'status':'existing_AE_seed_reused_for_four_illustrative_JS_replays','source_pins':wpins,'seed_fields':values,'no_genotype_or_ledger_arrays_loaded':True,'counts':{k:w[k] for k in ('js_replay_lives','new_C_lives','new_research_lives')},'new_candidate_ids_used':0}
 assert not matches and not errors and not jerrors
 result={'status':'passed','registered':False,'reserved':False,'candidate_receipt_sha256':sha(OUT/'candidate_namespace_review.json'),'prior_candidate_inventory_sha256':sha(OUT/'candidate_namespace_inventory.json'),'same_whole_blocks_half_open':[[LOW,HIGH]],'native_union_count':len(native),'reader_fixture_freeze_sha256':sha(OUT.parent/'reader_source_review.json'),'AE_terminal_budget_sha256':sha(AE/'budget.json'),'AE_root_clearance_sha256':sha(AE/'terminal_process_clearance.json'),'AE_registered_schedule_sha256':sha(AE/'seed_audit.json'),'current_npz_paths':len(seen),'unchanged_npz_paths':unchanged,'new_or_modified_npz_records':changed,'removed_prior_paths':sorted(set(prior)-seen),'seed_members_read':arrays,'actual_overlaps':matches,'NPZ_errors':errors,'JSON_source_pins':pins,'JSON_numeric_matches':hits,'JSON_errors':jerrors,'JSON_classification':'Prior AE block130 exclusive endpoint52310000 only. No new whole-block or native-ID reservation.','root_watchable_illustration':watchreview,'limits':['Unchanged files reuse filesystem identity/stat and prior exact seed-payload proof; no full-NPZ cryptographic rehash claim.','This same-candidate delta re-reads only added/changed seed-token members; the initial audit re-read every distinct known seed payload against new candidates.','Root illustration artifacts after this snapshot require a compact registration supplement; no scientific/world/genotype arrays read.'],'simulation_calls':0,'compiled_libraries':0,'genetic_draws':0,'genotype_copies':0,'source_sha256':sha(Path(__file__))}
 (OUT/'final_namespace_delta.json').write_text(json.dumps(result,indent=2)+'\n')
 audit={'status':'passed','registered':False,'reserved':False,'runs':candidate['runs'],'run_backgrounds':candidate['run_backgrounds'],'run_life_seeds':candidate['run_life_seeds'],'confirmation_seeds':candidate['confirmation_seeds'],'whole_blocks_half_open':[[LOW,HIGH]],'genetic_RNG':candidate['genetic_RNG'],'intentional_reuse':candidate['intentional_reuse'],'native_unique_count':128,'confirmation_unique_count':512,'total_unique_research_life_ids':640,'candidate_review_sha256':sha(OUT/'candidate_namespace_review.json'),'final_delta_sha256':sha(OUT/'final_namespace_delta.json'),'historical_reference_sha256':sha(OUT/'history_references.json'),'source_pins':{str(p.relative_to(ROOT)):sha(p) for p in [OUT/'namespace_audit.py',OUT/'classify_candidate.py',Path(__file__),OUT/'candidate_namespace_inventory.json',OUT/'candidate_namespace_review.json',OUT/'final_namespace_delta.json',OUT/'history_references.json']},'scope':'Candidate namespace audit only. Exact genetic run seeds53224/53225 are distinct from128 hashed evaluation life IDs; four confirmations intentionally share512 fresh IDs. Standard seed11 goldens and final0 half-life repetitions are explicit. Root registration/release remains separate.','simulation_calls':0,'compiled_libraries':0,'genetic_draws':0,'genotype_copies':0}
 (OUT/'seed_audit.json').write_text(json.dumps(audit,indent=2)+'\n')
 print(json.dumps({'status':'passed','seed_audit_sha256':sha(OUT/'seed_audit.json'),'delta_sha256':sha(OUT/'final_namespace_delta.json'),'current_npz_paths':len(seen),'new_or_modified_npz':len(changed),'seed_members_read':arrays,'actual_overlaps':len(matches),'errors':len(errors)+len(jerrors),'watchable_reuse_pinned':bool(watchreview)}))
if __name__=='__main__':main()
