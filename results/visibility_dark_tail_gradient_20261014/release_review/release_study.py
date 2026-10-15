"""Root AG release only after prospective publication and exact review pins."""
from pathlib import Path
import datetime
import hashlib
import importlib.util
import json
import subprocess
import sys
sys.dont_write_bytecode=True
AUDIT=Path(__file__).resolve().parent
ROOT=AUDIT.parents[1]
STUDY=ROOT/'outputs/autonomous_visibility_dark_tail_gradient_20261014'
PUBLIC=ROOT/'results/visibility_dark_tail_gradient_20261014'
def sha(p):return hashlib.sha256(p.read_bytes()).hexdigest()
def read(p):return json.loads(p.read_text())
assert not any((STUDY/n).exists() for n in ['ready.json','attempt.json','budget.json','measurement','logs','build-cache','startup_identity.json'])
preflight=read(AUDIT/'release_prerequisites.json')
assert preflight['status']=='accepted_by_root'
for name,digest in preflight['review_pins'].items():assert sha(ROOT/name)==digest,name
manifest=read(PUBLIC/'manifest.json')
assert manifest['phase']=='preparation' and manifest['release'] is False
assert sha(PUBLIC/'manifest.json')==preflight['prospective_manifest_sha256']
assert (PUBLIC/'manifest.json').read_bytes()==(PUBLIC/'prelaunch/manifest.json').read_bytes()
head=subprocess.check_output(['git','rev-parse','HEAD'],cwd=ROOT,text=True).strip()
assert head==subprocess.check_output(['git','rev-parse','origin/master'],cwd=ROOT,text=True).strip()
origins={}
for name,item in manifest['artifacts'].items():
 p=PUBLIC/name
 assert sha(p)==item['sha256'] and p.stat().st_size==item['bytes'],name
 assert subprocess.check_output(['git','show',head+':'+str(p.relative_to(ROOT))],cwd=ROOT)==p.read_bytes(),name
 if item.get('origin'):origins[item['origin']]=item['sha256']
for name in ['manifest.json','prelaunch/manifest.json']:
 p=PUBLIC/name
 assert subprocess.check_output(['git','show',head+':'+str(p.relative_to(ROOT))],cwd=ROOT)==p.read_bytes()
local={}
for p in sorted(STUDY.rglob('*')):
 if not p.is_file():continue
 assert '__pycache__' not in p.parts and p.suffix not in ['.pyc','.so'],str(p)
 assert origins.get(str(p.relative_to(ROOT)))==sha(p),str(p)
 local[str(p.relative_to(STUDY))]=sha(p)
protocol=read(STUDY/'protocol.json')
assert sha(STUDY/'protocol.json')==preflight['protocol_sha256']
assert set(protocol['file_pins']).issubset(local)
assert sha(STUDY/'analysis_pins.json')==preflight['analysis_pins_sha256']
for name,digest in protocol['production_pins'].items():assert sha(ROOT/name)==digest,name
sys.path.insert(0,str(STUDY))
spec=importlib.util.spec_from_file_location('ag_monitor',STUDY/'monitor.py')
monitor=importlib.util.module_from_spec(spec);spec.loader.exec_module(monitor)
assert monitor.check_protocol()==protocol
monitor.resource_clearance()
ready={'status':'released','released_at_utc':datetime.datetime.now(datetime.timezone.utc).isoformat(),
 'public_prelaunch_commit':head,'public_prelaunch_manifest_sha256':sha(PUBLIC/'manifest.json'),
 'source_pins':local,'production_pins':protocol['production_pins'],'scope':protocol['monitor_scope'],
 'authorization':'Bounded retained-panel dark-flash accessibility study under standing autonomous authorization; '
 'reported before launch. Exact AD ABI4 production world, all retained Y mutants, unchanged prices and local '
 'asynchronous rules. First attempt only; no retry, scope reduction, extension, paid compute or larger selection family.'}
with (STUDY/'ready.json').open('x') as f:f.write(json.dumps(ready,indent=2)+'\n')
assert monitor.check_ready(protocol)==ready
print(json.dumps({'status':'released','source_pins':len(local),'production_pins':len(protocol['production_pins']),
 'ready_sha256':sha(STUDY/'ready.json'),'public_commit':head},indent=2))
