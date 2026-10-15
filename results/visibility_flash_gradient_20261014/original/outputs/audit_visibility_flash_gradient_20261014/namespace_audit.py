"""Read-only AC candidate audit: pinned unique seed payloads plus current-file delta.
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
ROOT=Path(__file__).resolve().parents[2]
OUT=Path(__file__).resolve().parent
AA=ROOT/'outputs/audit_visibility_lateral_20261014'
EXCLUDE=(OUT,ROOT/'outputs/autonomous_visibility_flash_gradient_20261014')
LOW,HIGH=52_230_000,52_260_000
RUNS={}
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
 # AC has no newly sampled genotype or native evolutionary run seed.
 return {},{},{},set()

def main():
 lists,records,overlap,native=derive()
 baseline=AA/'npz_seed_baseline.json';assert sha(baseline)=='b5fbb637071e0bebae670b532742c4e8dec33cf05c7d6399419f06bb3daffb58'
 prior=read(baseline)['records'];cl=read(AA/'npz_seed_classification.json');assert cl['unexplained_nonfixture_errors']==0
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
 pattern=r'(?<![0-9.])522[3456][0-9]{4}(?![0-9.])'
 cmd=['rg','--no-ignore','-l','-0','-P','--glob','*.json','--glob','!**/test_*/**','--glob','!**/__pycache__/**',pattern,'results','outputs']
 found=subprocess.run(cmd,cwd=ROOT,capture_output=True);assert found.returncode in (0,1),found.stderr.decode()
 jpins={};jhits=[];jerrors=[]
 def visit(v,trail,p):
  if isinstance(v,dict):
   for k,x in v.items():visit(x,trail+[str(k)],p)
  elif isinstance(v,list):
   for i,x in enumerate(v):visit(x,trail+[str(i)],p)
  elif isinstance(v,int) and not isinstance(v,bool) and (LOW<=v<=HIGH or v in native):jhits.append({'path':p,'field':'.'.join(trail),'value':v})
 for raw in sorted(set(found.stdout.split(b'\0'))-{b''}):
  p=raw.decode();path=ROOT/p
  if excluded(path):continue
  try:
   v=read(path);jpins[p]=sha(path);visit(v,[],p)
  except (OSError,ValueError) as e:jerrors.append({'path':p,'error':type(e).__name__+': '+str(e)})
 # Keep literal source matches for explicit historical-base and endpoint classification.
 text=subprocess.run(['rg','--no-ignore','-n','-P','--glob','*.py','--glob','*.md','--glob','*.yaml','--glob','!**/test_*/**',r'52[_,]?2[3456][0-9_,]*|(?:block|fresh_seeds|reserve).{0,35}\b12[345]\b','results','outputs','docs'],cwd=ROOT,capture_output=True)
 assert text.returncode in (0,1)
 textlines=[x for x in text.stdout.decode().splitlines() if not excluded(ROOT/x.split(':',1)[0])]
 (OUT/'candidate_text_matches.txt').write_text('\n'.join(textlines)+'\n')
 historic=read(ROOT/'results/decoy_evolution_20261014/sources/seed_review/namespace_lists.json')
 def ints(v):
  if isinstance(v,dict):return [n for x in v.values() for n in ints(x)]
  if isinstance(v,list):return [n for x in v for n in ints(x)]
  return [v] if isinstance(v,int) and not isinstance(v,bool) else []
 historical=set(ints(historic))
 for file in [ROOT/'outputs/autonomous_visibility_continuation_20261014/seed_audit.json',ROOT/'outputs/autonomous_visibility_lateral_20261014/seed_audit.json', ROOT/'outputs/autonomous_visibility_precision_20261014/seed_audit.json', ROOT/'outputs/autonomous_visibility_precision_20261014/registration.json']:
  historical.update(ints(read(file)))
 hmatch=sorted(x for x in historical if x in native or LOW<x<HIGH)
 result={'status':'completed_pending_JSON_text_classification','reserved':False,'registered':False,'paired_native_seeds':RUNS,'run_life_seeds':lists,'records_by_run':records,'intentional_overlap':overlap,'native_union_count':0,'calibration_seeds':[52230000,52230001],'screen_seeds':list(range(52240000,52240032)),'confirmation_seeds':list(range(52250000,52250512)),'whole_block_half_open':[LOW,HIGH],'baseline_sha256':sha(baseline),'baseline_classification_sha256':sha(AA/'npz_seed_classification.json'),'current_npz_paths':len(current),'unchanged_npz_paths':len(unchanged),'unchanged_seed_members_covered':sum(len(x) for x in groups.values()),'baseline_unique_payloads_reopened':len(groups),'unique_payloads_total':len(payloads),'payload_reviews':payloads,'changed_npz_records':delta,'removed_baseline_paths':sorted(set(prior)-set(current)),'NPZ_numeric_matches':matches,'NPZ_errors':errors,'JSON_source_pins':jpins,'JSON_numeric_matches':jhits,'JSON_errors':jerrors,'historical_declared_integer_count':len(historical),'historical_actual_matches_excluding_prior_endpoint':hmatch,'text_match_file_sha256':sha(OUT/'candidate_text_matches.txt'),'source_pins':{n:sha(ROOT/n) for n in ['src/life/spec.py','src/life/evaluate.py','src/run.py','outputs/autonomous_visibility_precision_20261014/protocol.json','outputs/autonomous_visibility_precision_20261014/registration.json','outputs/autonomous_visibility_precision_20261014/seed_audit.json','outputs/autonomous_visibility_precision_20261014/ready.json','outputs/autonomous_visibility_lateral_20261014/protocol.json','outputs/autonomous_visibility_lateral_20261014/budget.json','outputs/autonomous_visibility_lateral_20261014/terminal_process_clearance.json']},'limits':['Baseline reuse is based on recorded stat tuple plus exact SHA-pinned seed payload equivalence; no claim of full-NPZ byte hashes.','One representative per distinct unchanged seed payload was re-read for these new candidates; changed/new files have every actual seed/seeds-token member read.','Synthetic malformed fixture errors are separated from real records. No outcome members read.','Targeted JSON/source spelling checks supplement prior declared schedules and retained seed inventories; own unregistered AC preparation/audit excluded.'],'simulation_calls':0,'compilation_calls':0,'generated_genotypes':0,'script_sha256':sha(Path(__file__))}
 (OUT/'candidate_namespace_inventory.json').write_text(json.dumps(result,indent=2)+'\n')
 print(json.dumps({k:result[k] for k in ('status','native_union_count','current_npz_paths','unchanged_npz_paths','unchanged_seed_members_covered','baseline_unique_payloads_reopened','unique_payloads_total')},indent=2))
 print(json.dumps({'changed_npz':len(delta),'removed':len(result['removed_baseline_paths']),'NPZ_matches':len(matches),'NPZ_errors':len(errors),'real_NPZ_errors':sum(not x['synthetic_fixture'] for x in errors),'JSON_files':len(jpins),'JSON_matches':len(jhits),'JSON_errors':len(jerrors),'historical_matches':hmatch,'text_matches':len(textlines)},indent=2))
if __name__=='__main__':main()
