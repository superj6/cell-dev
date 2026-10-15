"""Prepare read-only candidate audit sources and committed proof references; no seeds reserved."""
from pathlib import Path
import hashlib, json, subprocess
ROOT=Path(__file__).resolve().parents[3]
OUT=Path(__file__).resolve().parent
OLD=ROOT/'outputs/audit_prediction_gradient_20261014/new_ae/namespace'
def sha(p):return hashlib.sha256(p.read_bytes()).hexdigest()
refs=json.loads((OLD/'history_references.json').read_text())
for name in ('candidate_namespace_inventory.json','candidate_namespace_review.json','final_namespace_delta.json','seed_audit.json'):
 p=ROOT/'results/prediction_gradient_20261014/original/outputs/audit_prediction_gradient_20261014/new_ae/namespace'/name
 refs['content_by_sha256'][sha(p)]={'repository_path':str(p.relative_to(ROOT)), 'source_origin':str((OLD/name).relative_to(ROOT)), 'bytes':p.stat().st_size,'containing_public_commit':'081d106b4b47a08af5e7824e06e3fc030c4f1c88'}
for digest,record in refs['content_by_sha256'].items():
 p=ROOT/record['repository_path']; assert sha(p)==digest and p.stat().st_size==record['bytes']
 b=subprocess.run(['git','show',record['containing_public_commit']+':'+record['repository_path']],cwd=ROOT,capture_output=True,check=True).stdout
 assert hashlib.sha256(b).hexdigest()==digest
refs['total_historical_bytes_not_recopied']=sum(x['bytes'] for x in refs['content_by_sha256'].values())
(OUT/'history_references.json').write_text(json.dumps(refs,indent=2)+'\n')
s=(OLD/'namespace_audit.py').read_text().replace('AE candidate','AF candidate').replace('parents[4]','parents[3]').replace("ROOT/'outputs/autonomous_prediction_gradient_20261014'","ROOT/'outputs/autonomous_prediction_continuation_20261014'")
s=s.replace('LOW,HIGH=52_280_000,52_310_000','LOW,HIGH=52_310_000,52_320_000').replace('RUNS={}',"RUNS={'D90':53224,'L92':53225}")
a=s.index('def derive():');b=s.index('\ndef main():',a)
s=s[:a]+'''def derive():
 # Execute only pure source definitions; no src/evolve/build/checkpoint imports or RNG draws.
 from types import SimpleNamespace
 ns={'MASK64':(1<<64)-1}
 pure_definitions(ROOT/'src/life/spec.py', ['splitmix64','hash64'], ns)
 ev={'spec':SimpleNamespace(hash64=ns['hash64']), '_SEED_STREAM':0x4C494645,
     'PURPOSES':dict(gen=1,founders=2,valid=3,heldout=4,final=5,clones=6,sizecurve=7,census=8)}
 pure_definitions(ROOT/'src/life/evaluate.py',['life_seed'],ev)
 plan={'life_seed':ev['life_seed']}
 pure_definitions(ROOT/'outputs/autonomous_prediction_continuation_20261014/prepare.py',['planned_search_seeds'],plan)
 lists={};records={}
 for background,run in RUNS.items():
  rows=[]
  for g in range(4):
   rows.extend({'purpose':'gen','index':g,'life':j,'seed':ev['life_seed'](run,'gen',g,j)} for j in range(7))
   if g in (0,3):rows.extend({'purpose':'valid','index':g,'life':j,'seed':ev['life_seed'](run,'valid',g,j)} for j in range(16))
  for g in (0,1):rows.extend({'purpose':'final','index':g,'life':j,'seed':ev['life_seed'](run,'final',g,j)} for j in range(2))
  values=[row['seed'] for row in rows]
  assert values==plan['planned_search_seeds'](run) and len(values)==len(set(values))==64
  lists[str(run)]=values;records[str(run)]=rows
 native=set(sum(lists.values(),[]));assert len(native)==128 and 11 not in native
 assert not any(LOW<=x<HIGH for x in native)
 return lists,records,{},native
''' + s[b:]
old="'811267e72e55e91fa1b030636cd12e9e1fd0d8b21802b564db281cb625757d27')"
new="'811267e72e55e91fa1b030636cd12e9e1fd0d8b21802b564db281cb625757d27','f54bdf9bed418dfa1b7981f9819a1304e6dca02b2e311e1ef3fcde966a42fa75','6e99958579745e54cbeecf702fae255f187f3d3380dc2f33df0d7002d3c7b5ea')"
assert old in s;s=s.replace(old,new)
s=s.replace("pattern=r'(?<![0-9.])(?:522[89]|523[01])[0-9]{4}(?![0-9.])'", "pattern=r'(?<![0-9.])(?:523[12][0-9]{4}|'+'|'.join(map(str,sorted(native|set(RUNS.values()))))+r')(?![0-9.])'")
s=s.replace("or v in native):jhits", "or v in native or v in RUNS.values()):jhits")
s=s.replace("r'52[_,]?(?:2[89]|3[01])[0-9_,]*|(?:block|fresh_seeds|reserve).{0,35}\\b(?:12[89]|130)\\b'", "r'52[_,]?3[12][0-9_,]*|5322[45]|(?:block|fresh_seeds|reserve).{0,35}\\b131\\b'")
s=s.replace("ROOT/'outputs/autonomous_visibility_dark_tail_information_20261014/seed_audit.json']:","ROOT/'outputs/autonomous_visibility_dark_tail_information_20261014/seed_audit.json',ROOT/'outputs/autonomous_prediction_gradient_20261014/registration.json',ROOT/'outputs/autonomous_prediction_gradient_20261014/seed_audit.json']:")
s=s.replace("'native_union_count':0", "'native_union_count':len(native)")
s=s.replace("'stage_seed_lists':{'calibration':list(range(52280000,52280002)),'screen':list(range(52290000,52290032)),'confirm':list(range(52300000,52300512))}","'stage_seed_lists':{'confirm':list(range(52310000,52310512))}")
s=s.replace("'whole_blocks_half_open':[[LOW,LOW+10000],[LOW+10000,LOW+20000],[LOW+20000,HIGH]]", "'whole_blocks_half_open':[[LOW,HIGH]]")
s=s.replace("'source_pins':{n:sha(ROOT/n) for n in ['src/life/spec.py'", "'source_pins':{n:sha(ROOT/n) for n in ['outputs/autonomous_prediction_continuation_20261014/prepare.py','src/evolve.py','src/checkpoint.py','outputs/autonomous_prediction_gradient_20261014/protocol.json','outputs/autonomous_prediction_gradient_20261014/registration.json','outputs/autonomous_prediction_gradient_20261014/seed_audit.json','outputs/autonomous_prediction_gradient_20261014/budget.json','outputs/autonomous_prediction_gradient_20261014/terminal_process_clearance.json','outputs/autonomous_prediction_gradient_20261014/ready.json','src/life/spec.py'")
s=s.replace('own unregistered AE producer','own unregistered AF producer').replace('all AD registered seeds and generated/public duplicates','all AE registered seeds and generated/public duplicates').replace('Other AE reader fixtures','AF reader fixtures')
(OUT/'namespace_audit.py').write_text(s)
print(json.dumps({'history_reference_count':len(refs['content_by_sha256']),'historical_bytes_not_recopied':refs['total_historical_bytes_not_recopied'],'history_sha256':sha(OUT/'history_references.json'),'scanner_sha256':sha(OUT/'namespace_audit.py')}))
