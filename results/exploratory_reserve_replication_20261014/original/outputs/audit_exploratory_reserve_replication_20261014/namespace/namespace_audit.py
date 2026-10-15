"""Read-only AI candidate audit: pinned unique seed payloads plus current-file delta.
No production imports, generation, reservation, kernel compilation or simulation.
"""
from __future__ import annotations
import ast
import hashlib
import io
import json
import os
from pathlib import Path
import re
import subprocess
import zipfile
import numpy as np
ROOT=Path(__file__).resolve().parents[3]
OUT=Path(__file__).resolve().parent
AA=ROOT/'outputs/audit_visibility_lateral_20261014'
EXCLUDE=(OUT,ROOT/'outputs/autonomous_exploratory_reserve_replication_20261014')
LOW,HIGH=52_360_000,52_370_000
RUNS={'control':53227,'reserve':53227}
SKIP={'.git','.venv','__pycache__','node_modules','.pytest_cache'}
def sha(p):return hashlib.sha256(p.read_bytes()).hexdigest()
def read(p):return json.loads(p.read_text())
def stat(p):
 s=p.stat();return {k:getattr(s,'st_'+k) for k in ('size','mtime_ns','ctime_ns','dev','ino')}
def seed_member(n):return n.endswith('.npy') and re.search(r'(^|[^A-Za-z0-9])seeds?(?=$|[^A-Za-z0-9])',n[:-4],re.I) is not None
def excluded(p):return any(p.is_relative_to(x) for x in EXCLUDE)
def pure_definitions(path,names,namespace):
 tree=ast.parse(path.read_text()); nodes=[n for n in tree.body if isinstance(n,(ast.FunctionDef,ast.AsyncFunctionDef)) and n.name in names]
 assert {x.name for x in nodes}==set(names)
 for n in nodes:n.body=[x for x in n.body if not isinstance(x,(ast.Import,ast.ImportFrom))]
 exec(compile(ast.Module(body=nodes,type_ignores=[]),str(path),'exec'),namespace)
def derive():
 # Execute only the pure hash/draw definitions, not producer or production imports.
 from types import SimpleNamespace
 ns={'MASK64':(1<<64)-1}
 pure_definitions(ROOT/'src/life/spec.py',['splitmix64','hash64'],ns)
 ev={'spec':SimpleNamespace(hash64=ns['hash64']),'_SEED_STREAM':0x4C494645,
     'PURPOSES':dict(gen=1,founders=2,valid=3,heldout=4,final=5,clones=6,sizecurve=7,census=8)}
 pure_definitions(ROOT/'src/life/evaluate.py',['life_seed'],ev)
 plan={'life_seed':ev['life_seed']}
 pure_definitions(OUT/'AI_prepare_candidate.py.txt',['planned_search_seeds'],plan)
 rows=[]
 for g in range(4):
  rows.extend({'purpose':'gen','index':g,'life':j,'seed':ev['life_seed'](53227,'gen',g,j)} for j in range(7))
  if g in (0,3):rows.extend({'purpose':'valid','index':g,'life':j,'seed':ev['life_seed'](53227,'valid',g,j)} for j in range(16))
 for index in (0,1):rows.extend({'purpose':'final','index':index,'life':j,'seed':ev['life_seed'](53227,'final',index,j)} for j in range(2))
 values=[r['seed'] for r in rows]
 assert values==plan['planned_search_seeds'](53227) and len(values)==len(set(values))==64
 assert 11 not in values and not any(LOW<=v<HIGH for v in values)
 return {arm:values for arm in RUNS},{arm:rows for arm in RUNS},values,set(values)

def main():
 lists,records,overlap,native=derive()
 references=read(OUT/'history_references.json')['content_by_sha256']
 def history(digest):
  p=ROOT/references[digest]['repository_path'];assert sha(p)==digest;return p
 baseline=history('b5fbb637071e0bebae670b532742c4e8dec33cf05c7d6399419f06bb3daffb58');assert sha(baseline)=='b5fbb637071e0bebae670b532742c4e8dec33cf05c7d6399419f06bb3daffb58'
 prior=read(baseline)['records'];cl=read(history('2b0a2c623ef2ec3303eb088094ee1ded1e33c59ad35c339e7c7e9c1c2b91a468'));assert cl['unexplained_nonfixture_errors']==0
 # Merge the accepted AC same-host inventory and its final pre-registration delta.
 # Reopen unique payloads for these DIFFERENT candidate blocks; never reuse prior no-match conclusions.
 prior_sources={str(baseline.relative_to(ROOT)):sha(baseline)}
 for digest in ('bb065a1f29f4e04a0f3017281b27788e6f2e1a92425cedb5b245830ed141a8d6','50e527b8269d0ea1b6066fdda5ef0633ec8c53cb40ee5be1848fc6e0e0d6a118','1c515418b1bbe25219970d445aba547bee0d9d97849f144601408a3cbeac51b3','811267e72e55e91fa1b030636cd12e9e1fd0d8b21802b564db281cb625757d27','f54bdf9bed418dfa1b7981f9819a1304e6dca02b2e311e1ef3fcde966a42fa75','6e99958579745e54cbeecf702fae255f187f3d3380dc2f33df0d7002d3c7b5ea','f29e30913de10d16dccd634c0aa07d38498745fb2e598a147c56504cf2ca6304','249a2c26ccdbd1e1de801d3c2ab8ecf73925109307a276075d241b2791fb6b04','126bf37a45ca8f6db88bf872bccd9adffce3fbaeff8a56e32e0ac8ff3aee708b','2f355af217767abf83762adae4bc10086141ef198aa89c1c81d78882c425a897','91e8a411ac735a451200b4dc69ab45854f1f42a58b87be1e00df0e7991923260','6d0eae362b0c78c969db0e5eaaa5e2fff439b8e6050183dfccc784c62f9bb083'):
  source=history(digest);item=read(source)
  changed=item.get('changed_npz_records',item.get('new_or_modified_npz_records'))
  assert changed is not None
  for path,record in changed.items():
   record=dict(record);members={}
   for member,value in record.get('seed_members',{}).items():
    digest2=value if isinstance(value,str) else value.get('sha256',value.get('npy_sha256'))
    assert digest2 is not None;members[member]={'npy_sha256':digest2}
   record['seed_members']=members;prior[path]=record
  prior_sources[str(source.relative_to(ROOT))]=sha(source)
 current={}
 for top in (ROOT/'results',ROOT/'outputs'):
  for folder,dirs,names in os.walk(top,followlinks=False):
   base=Path(folder);dirs[:]=sorted(n for n in dirs if n not in SKIP and not excluded(base/n))
   for n in sorted(names):
    if n.endswith('.npz'):
     p=base/n;current[str(p.relative_to(ROOT))]=stat(p)
 unchanged={p for p,s in current.items() if p in prior and prior[p].get('stat')==s}
 groups={}
 for p,r in prior.items():
  if p not in unchanged:continue
  for n,v in r.get('seed_members',{}).items():
   if seed_member(n) and 'npy_sha256' in v:groups.setdefault(v['npy_sha256'],[]).append((p,n))
 payloads={};matches=[];errors=[]
 def inspect(raw,p,n,expected=None):
  digest=hashlib.sha256(raw).hexdigest()
  if expected is not None and digest!=expected:raise ValueError('representative payload changed')
  if digest not in payloads:
   v=np.load(io.BytesIO(raw),allow_pickle=False)
   if not isinstance(v,np.ndarray) or not np.issubdtype(v.dtype,np.number) or not np.isfinite(v).all():raise ValueError('invalid seed member')
   if not np.issubdtype(v.dtype,np.integer) and np.any(v!=np.floor(v)):raise ValueError('non-integral seed member')
   hits=sorted({int(x) for x in v.flat if LOW<=int(x)<HIGH or int(x) in native})
   payloads[digest]={'representative_path':p,'member':n,'dtype':str(v.dtype),'shape':list(v.shape),'count':int(v.size),'matches':hits}
  if payloads[digest]['matches']:matches.append({'path':p,'member':n,'values':payloads[digest]['matches']})
  return digest
 for digest,members in sorted(groups.items()):
  p,n=members[0]
  with zipfile.ZipFile(ROOT/p) as z:inspect(z.read(n),p,n,digest)
  assert stat(ROOT/p)==current[p]
 delta={}
 for p in sorted(set(current)-unchanged):
  rec={'change':'modified' if p in prior else 'added','stat':current[p],'synthetic_fixture':any(x.startswith('test_') for x in Path(p).parts),'seed_members':{}}
  delta[p]=rec
  try:
   with zipfile.ZipFile(ROOT/p) as z:
    for info in z.infolist():
     if not seed_member(info.filename):continue
     if info.filename in rec['seed_members']:raise ValueError('duplicate seed member')
     rec['seed_members'][info.filename]=inspect(z.read(info),p,info.filename)
   if stat(ROOT/p)!=current[p]:raise ValueError('NPZ changed during audit')
  except (OSError,ValueError,zipfile.BadZipFile,EOFError) as e:
   rec['error']=type(e).__name__+': '+str(e);errors.append({'path':p,'error':rec['error'],'synthetic_fixture':rec['synthetic_fixture']})
 # New JSON candidates are selected by exact integer spelling; no large repeated full JSON scan.
 pattern=r'(?<![0-9.])(?:523[67][0-9]{4}|53227|'+ '|'.join(str(x) for x in sorted(native))+r')(?![0-9.])'
 cmd=['rg','--no-ignore','-l','-0','-P','--glob','*.json','--glob','!**/test_*/**','--glob','!**/__pycache__/**',pattern,'results','outputs']
 found=subprocess.run(cmd,cwd=ROOT,capture_output=True);assert found.returncode in (0,1),found.stderr.decode()
 jpins={};jhits=[];jstrings=[];jerrors=[]
 def visit(v,trail,p):
  if isinstance(v,dict):
   for k,x in v.items():
    if str(k).isdecimal() and (LOW<=int(k)<=HIGH or int(k) in native or int(k) in RUNS.values()):jstrings.append({'path':p,'field':'.'.join(trail),'kind':'key','value':str(k)})
    visit(x,trail+[str(k)],p)
  elif isinstance(v,list):
   for i,x in enumerate(v):visit(x,trail+[str(i)],p)
  elif isinstance(v,str) and v.isdecimal() and (LOW<=int(v)<=HIGH or int(v) in native or int(v) in RUNS.values()):jstrings.append({'path':p,'field':'.'.join(trail),'kind':'value','value':v})
  elif isinstance(v,int) and not isinstance(v,bool) and (LOW<=v<=HIGH or v in native or v in RUNS.values()):jhits.append({'path':p,'field':'.'.join(trail),'value':v})
 for raw in sorted(set(found.stdout.split(b'\0'))-{b''}):
  p=raw.decode();path=ROOT/p
  if excluded(path):continue
  try:
   v=read(path);jpins[p]=sha(path);visit(v,[],p)
  except (OSError,ValueError) as e:jerrors.append({'path':p,'error':type(e).__name__+': '+str(e)})
 # Keep literal source matches for explicit historical-base and endpoint classification.
 text=subprocess.run(['rg','--no-ignore','-n','-P','--glob','*.py','--glob','*.md','--glob','*.yaml','--glob','!**/test_*/**',r'52[_,]?3[67][0-9_,]*|53[_,]?227|(?:block|fresh_seeds|reserve).{0,35}\b136\b','results','outputs','docs'],cwd=ROOT,capture_output=True)
 assert text.returncode in (0,1)
 textlines=[x for x in text.stdout.decode().splitlines() if not excluded(ROOT/x.split(':',1)[0])]
 (OUT/'candidate_text_matches.txt').write_text('\n'.join(textlines)+'\n')
 historic=read(history('cb2defcdd9baa6f6e61bfc53dbdf1687d77bb0b1dbf20625ea6a2759a1431278'))
 def ints(v):
  if isinstance(v,dict):return [n for x in v.values() for n in ints(x)]
  if isinstance(v,list):return [n for x in v for n in ints(x)]
  return [v] if isinstance(v,int) and not isinstance(v,bool) else []
 historical=set(ints(historic))
 for file in [ROOT/'outputs/autonomous_visibility_continuation_20261014/seed_audit.json',ROOT/'outputs/autonomous_visibility_lateral_20261014/seed_audit.json', ROOT/'outputs/autonomous_visibility_precision_20261014/seed_audit.json', ROOT/'outputs/autonomous_visibility_precision_20261014/registration.json', ROOT/'outputs/autonomous_visibility_flash_gradient_20261014/registration.json', ROOT/'outputs/autonomous_visibility_flash_gradient_20261014/seed_audit.json', ROOT/'outputs/autonomous_visibility_dark_tail_information_20261014/registration.json', ROOT/'outputs/autonomous_visibility_dark_tail_information_20261014/seed_audit.json',ROOT/'outputs/autonomous_prediction_gradient_20261014/registration.json',ROOT/'outputs/autonomous_prediction_gradient_20261014/seed_audit.json',ROOT/'outputs/autonomous_prediction_continuation_20261014/registration.json',ROOT/'outputs/autonomous_prediction_continuation_20261014/seed_audit.json',ROOT/'outputs/autonomous_visibility_dark_tail_gradient_20261014/registration.json',ROOT/'outputs/autonomous_visibility_dark_tail_gradient_20261014/seed_audit.json',ROOT/'outputs/autonomous_exploratory_reserve_20261014/registration.json',ROOT/'outputs/autonomous_exploratory_reserve_20261014/seed_audit.json']:
  historical.update(ints(read(file)))
 hmatch=sorted(x for x in historical if x in native or LOW<=x<HIGH)
 result={'status':'completed_pending_JSON_text_classification','reserved':False,'registered':False,'paired_native_seeds':RUNS,'run_life_seeds':lists,'records_by_run':records,'intentional_overlap':overlap,'native_union_count':len(native),'stage_seed_lists':{'confirm':list(range(52360000,52360512))},'stage_seed_status':'candidate_only_not_reserved','whole_blocks_half_open':[[LOW,HIGH]],'whole_block_half_open':[LOW,HIGH],'baseline_sources':prior_sources,'baseline_sha256':sha(baseline),'baseline_classification_sha256':sha(history('2b0a2c623ef2ec3303eb088094ee1ded1e33c59ad35c339e7c7e9c1c2b91a468')),'current_npz_paths':len(current),'unchanged_npz_paths':len(unchanged),'unchanged_seed_members_covered':sum(len(x) for x in groups.values()),'baseline_unique_payloads_reopened':len(groups),'unique_payloads_total':len(payloads),'payload_reviews':payloads,'changed_npz_records':delta,'removed_baseline_paths':sorted(set(prior)-set(current)),'NPZ_numeric_matches':matches,'NPZ_errors':errors,'JSON_source_pins':jpins,'JSON_numeric_matches':jhits,'JSON_numeric_string_or_key_matches':jstrings,'JSON_errors':jerrors,'historical_declared_integer_count':len(historical),'historical_actual_matches_excluding_prior_endpoint':hmatch,'text_match_file_sha256':sha(OUT/'candidate_text_matches.txt'),'source_pins':{n:sha(ROOT/n) for n in ['outputs/autonomous_exploratory_reserve_20261014/registration.json','outputs/autonomous_exploratory_reserve_20261014/seed_audit.json','outputs/autonomous_exploratory_reserve_20261014/budget.json','outputs/autonomous_exploratory_reserve_20261014/terminal_process_clearance.json','outputs/audit_exploratory_reserve_replication_20261014/namespace/AI_prepare_candidate.py.txt','outputs/autonomous_visibility_dark_tail_gradient_20261014/registration.json','outputs/autonomous_visibility_dark_tail_gradient_20261014/seed_audit.json','outputs/autonomous_visibility_dark_tail_gradient_20261014/budget.json','outputs/autonomous_visibility_dark_tail_gradient_20261014/terminal_process_clearance.json','outputs/autonomous_prediction_continuation_20261014/registration.json','outputs/autonomous_prediction_continuation_20261014/seed_audit.json','outputs/autonomous_prediction_continuation_20261014/budget.json','outputs/autonomous_prediction_continuation_20261014/terminal_process_clearance.json','outputs/autonomous_prediction_continuation_20261014/ready.json','outputs/autonomous_prediction_continuation_20261014/prepare.py','src/evolve.py','src/checkpoint.py','outputs/autonomous_prediction_gradient_20261014/protocol.json','outputs/autonomous_prediction_gradient_20261014/registration.json','outputs/autonomous_prediction_gradient_20261014/seed_audit.json','outputs/autonomous_prediction_gradient_20261014/budget.json','outputs/autonomous_prediction_gradient_20261014/terminal_process_clearance.json','outputs/autonomous_prediction_gradient_20261014/ready.json','src/life/spec.py','src/life/evaluate.py','src/run.py','outputs/autonomous_visibility_precision_20261014/protocol.json','outputs/autonomous_visibility_precision_20261014/registration.json','outputs/autonomous_visibility_precision_20261014/seed_audit.json','outputs/autonomous_visibility_precision_20261014/ready.json','outputs/autonomous_visibility_lateral_20261014/protocol.json','outputs/autonomous_visibility_lateral_20261014/budget.json','outputs/autonomous_visibility_lateral_20261014/terminal_process_clearance.json','outputs/autonomous_visibility_flash_gradient_20261014/protocol.json','outputs/autonomous_visibility_flash_gradient_20261014/registration.json','outputs/autonomous_visibility_flash_gradient_20261014/seed_audit.json','outputs/autonomous_visibility_flash_gradient_20261014/ready.json','outputs/autonomous_visibility_dark_tail_information_20261014/protocol.json','outputs/autonomous_visibility_dark_tail_information_20261014/registration.json','outputs/autonomous_visibility_dark_tail_information_20261014/seed_audit.json','outputs/autonomous_visibility_dark_tail_information_20261014/budget.json','outputs/autonomous_visibility_dark_tail_information_20261014/terminal_process_clearance.json','outputs/autonomous_visibility_dark_tail_information_20261014/ready.json']},'limits':['Baseline reuse is based on recorded stat tuple plus exact SHA-pinned seed payload equivalence; no claim of full-NPZ byte hashes.','One representative per distinct unchanged seed payload was re-read for these new candidates; changed/new files have every actual seed/seeds-token member read.','Synthetic malformed fixture errors are separated from real records. No outcome members read.','Targeted JSON/source spelling checks supplement prior declared schedules and retained seed inventories; own unregistered AI producer and this namespace-audit folder excluded; all completed AH registered IDs/generated/public duplicates included. AI reader fixtures are scanned; own candidate declarations are separately classified.'],'simulation_calls':0,'compilation_calls':0,'generated_genotypes':0,'script_sha256':sha(Path(__file__))}
 (OUT/'candidate_namespace_inventory.json').write_text(json.dumps(result,indent=2)+'\n')
 print(json.dumps({k:result[k] for k in ('status','native_union_count','current_npz_paths','unchanged_npz_paths','unchanged_seed_members_covered','baseline_unique_payloads_reopened','unique_payloads_total')},indent=2))
 print(json.dumps({'changed_npz':len(delta),'removed':len(result['removed_baseline_paths']),'NPZ_matches':len(matches),'NPZ_errors':len(errors),'real_NPZ_errors':sum(not x['synthetic_fixture'] for x in errors),'JSON_files':len(jpins),'JSON_matches':len(jhits),'JSON_errors':len(jerrors),'historical_matches':hmatch,'text_matches':len(textlines)},indent=2))
if __name__=='__main__':main()
