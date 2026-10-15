"""Root AH release after prospective publication; no engine calls."""
from pathlib import Path
import datetime
import hashlib
import importlib.util
import json
import subprocess
import sys
sys.dont_write_bytecode = True
AUDIT=Path(__file__).resolve().parent
ROOT=AUDIT.parents[1]
STUDY=ROOT/'outputs/autonomous_exploratory_reserve_20261014'
PUBLIC=ROOT/'results/exploratory_reserve_20261014'
def sha(p):return hashlib.sha256(p.read_bytes()).hexdigest()
def read(p):return json.loads(p.read_text())
assert not any((STUDY/n).exists() for n in ['ready.json','attempt.json','budget.json','runs','confirmation','logs','build-cache'])
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
spec=importlib.util.spec_from_file_location('ah_monitor',STUDY/'run_budgeted.py')
monitor=importlib.util.module_from_spec(spec);spec.loader.exec_module(monitor)
assert monitor.check_protocol()==protocol
monitor.resource_clearance()
ready={'status':'released','released_at_utc':datetime.datetime.now(datetime.timezone.utc).isoformat(),
 'public_prelaunch_commit':head,'public_prelaunch_manifest_sha256':sha(PUBLIC/'manifest.json'),
 'source_pins':local,'production_pins':protocol['production_pins'],
 'scope':{k:protocol[k] for k in ['search_genome_lives','confirmation_genome_lives','planned_genome_lives',
 'startup_validation_genome_lives','max_cpu_seconds','search_cpu_seconds','max_simulation_threads']},
 'authorization':'One matched four-generation control/reserve pair under standing minor-selection and autonomous '
 'authorization; reported before launch. Fixed AE L92 start, exact V world, unchanged task F, prices and local '
 'asynchronous rules. Two uniformly chosen fresh offspring protected in generations 0 through 2; ordinary final '
 'selection. First attempt only; no retry, resume, scope reduction, extension, paid compute or larger family.'}
with (STUDY/'ready.json').open('x') as f:f.write(json.dumps(ready,indent=2)+'\n')
assert monitor.check_ready()==ready
print(json.dumps({'status':'released','source_pins':len(local),'production_pins':len(protocol['production_pins']),
 'ready_sha256':sha(STUDY/'ready.json'),'public_commit':head},indent=2))
