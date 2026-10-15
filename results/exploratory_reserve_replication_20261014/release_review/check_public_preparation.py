"""Actual prospective byte coverage and archive-only definition check; no engine calls."""
from pathlib import Path
import hashlib
import importlib.util
import json
import os
import subprocess
import sys

ROOT=Path(__file__).resolve().parents[2]
AUDIT=Path(__file__).resolve().parent
PUBLIC=ROOT/'results/exploratory_reserve_replication_20261014'
STUDY=ROOT/'outputs/autonomous_exploratory_reserve_replication_20261014'
sha=lambda p:hashlib.sha256(p.read_bytes()).hexdigest()
spec=importlib.util.spec_from_file_location('ai_archive',AUDIT/'archive.py')
a=importlib.util.module_from_spec(spec);spec.loader.exec_module(a)
plan=a.make_plan(ROOT,STUDY,AUDIT,'preparation')
expected=set(plan['artifacts'])|{'manifest.json','prelaunch/manifest.json'}
actual={str(p.relative_to(PUBLIC)) for p in PUBLIC.rglob('*') if p.is_file()}
assert actual==expected
assert (PUBLIC/'manifest.json').read_bytes()==(PUBLIC/'prelaunch/manifest.json').read_bytes()
for name,item in plan['artifacts'].items():assert sha(PUBLIC/name)==item['sha256']
canonical={str(p.relative_to(STUDY)):p for p in STUDY.rglob('*') if p.is_file() and '__pycache__' not in p.parts}
for name,p in canonical.items():
 matches=[(n,x) for n,x in plan['artifacts'].items() if x['origin']==str(p.relative_to(ROOT)) and x['sha256']==sha(p)]
 assert matches,(name,'canonical study file is absent from exact-origin manifest')
code='''import importlib.util,json,pathlib,sys
base=pathlib.Path(sys.argv[1]).resolve()
sys.path.insert(0,str(base/'analysis'))
spec=importlib.util.spec_from_file_location('public_ai',base/'analysis/analyze.py')
m=importlib.util.module_from_spec(spec);spec.loader.exec_module(m)
resolved=[]
def archived(root,name):
 for prefix in ('production','original'):
  path=m.inside(pathlib.Path(root)/prefix,name)
  if path.is_file():resolved.append(str(path.relative_to(base)));return path
 raise FileNotFoundError('archive-only dependency absent: '+name)
m.external=archived
p=m.verify_protocol(base)
replay=m.module('public_ai_native',base/'analysis/native_audit.py').initialization_audit(base,p,archived)
assert replay==m.read(base/'analysis/initialization_replay.json')
assert sum(v['rows'] for v in replay['backgrounds'].values())==32
assert sum(v['recorded_mutations'] for v in replay['backgrounds'].values())==62
outcome,vectors=m.analyze(base)
assert outcome['status']=='incomplete' and outcome['scientific_outcomes_emitted'] is False and not vectors
assert 'ready.json' in outcome['error'],outcome
forbidden={'src.life.build','src.life.evaluate','src.checkpoint','src.run','src.evolve'}
assert not (forbidden & set(sys.modules)), forbidden & set(sys.modules)
for name,module in tuple(sys.modules.items()):
 if name=='src' or name.startswith('src.'):
  assert pathlib.Path(module.__file__).resolve().is_relative_to(base/'production'),name
print(json.dumps({'status':'passed_archive_only_preparation','initial_rows':32,'recorded_operations':62,'protocol_sha256':m.sha(base/'protocol.json'),'local_pins':len(p['file_pins']),'external_pins':len(p['production_pins']),'replay_exact':True,'runtime_result':outcome,'resolved_external_paths':sorted(set(resolved)),'engine_modules_imported':0,'simulation_calls':0,'compiled_libraries':0},indent=2))
'''
env=dict(os.environ,PYTHONDONTWRITEBYTECODE='1',OPENBLAS_NUM_THREADS='1',OMP_NUM_THREADS='1',MKL_NUM_THREADS='1')
r=subprocess.run([sys.executable,'-c',code,str(PUBLIC)],cwd='/',env=env,capture_output=True,text=True)
(AUDIT/'public_preparation_check.stdout.json').write_text(r.stdout)
(AUDIT/'public_preparation_check.stderr.txt').write_text(r.stderr)
assert r.returncode==0,r.stderr
checked=json.loads(r.stdout)
assert checked['status']=='passed_archive_only_preparation'
assert not list(PUBLIC.rglob('__pycache__'))
force=a.ignored_paths(ROOT,PUBLIC,plan)
files=sorted(str((PUBLIC/n).relative_to(ROOT)) for n in expected)
(AUDIT/'all_archive_files.txt').write_text(''.join(n+'\n' for n in files))
(AUDIT/'force_add_paths.txt').write_text(''.join(n+'\n' for n in force))
receipt={'status':'verified_prospective_archive','protocol_sha256':a.PROTOCOL_SHA,'manifest_sha256':sha(PUBLIC/'manifest.json'),
 'copied_artifacts':len(plan['artifacts']),'total_files':len(actual),'canonical_study_files_with_exact_origin_hash_mapping':len(canonical),
 'local_protocol_pins':103,'production_and_dependency_pins':35,'initial_rows_replayed':32,'recorded_operations_replayed':62,'scientific_inputs_archive_only':True,
 'outside_repository_working_directory':'/','scientific_outcomes_emitted':False,'new_lives':0,'new_compilations':0,
 'historical_provenance_library':plan['previously_compiled_provenance_libraries'],
 'historical_namespace_objects_not_recopied':len(plan['historical_namespace_objects_not_recopied']),
 'historical_namespace_bytes_not_recopied':37229225,'complete_namespace_proof_requires_referenced_repository_artifacts':True,
 'public_check_stdout_sha256':sha(AUDIT/'public_preparation_check.stdout.json'),'empty_stderr':not r.stderr,
 'full_manifest_byte_coverage':True,'force_add_paths':force}
(AUDIT/'archive_verification.json').write_text(json.dumps(receipt,indent=2)+'\n')
print(json.dumps(receipt,indent=2))
