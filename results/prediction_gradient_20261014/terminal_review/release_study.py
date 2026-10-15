"""Root AE release after prospective publication; no engine calls here."""
from pathlib import Path
import datetime
import hashlib
import importlib.util
import json
import subprocess
import sys

sys.dont_write_bytecode = True

ROOT = Path(__file__).resolve().parents[3]
STUDY = ROOT / 'outputs/autonomous_prediction_gradient_20261014'
PUBLIC = ROOT / 'results/prediction_gradient_20261014'


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def read(path):
    return json.loads(path.read_text())


assert not any((STUDY / name).exists() for name in
               ['ready.json', 'attempt.json', 'budget.json', 'measurement', 'logs', 'build-cache', 'startup_identity.json'])
preflight = read(Path(__file__).resolve().parent / 'release_prerequisites.json')
assert preflight['status'] == 'accepted_by_root'
for name, digest in preflight['review_pins'].items():
    assert sha(ROOT / name) == digest, name
manifest = read(PUBLIC / 'manifest.json')
assert manifest['phase'] == 'preparation' and manifest['release'] is False
assert (PUBLIC / 'manifest.json').read_bytes() == (PUBLIC / 'prelaunch/manifest.json').read_bytes()
head = subprocess.check_output(['git', 'rev-parse', 'HEAD'], cwd=ROOT, text=True).strip()
assert head == subprocess.check_output(['git', 'rev-parse', 'origin/master'], cwd=ROOT, text=True).strip()
origins = {}
for name, item in manifest['artifacts'].items():
    path = PUBLIC / name
    assert sha(path) == item['sha256'] and path.stat().st_size == item['bytes'], name
    assert subprocess.check_output(['git', 'show', head + ':' + str(path.relative_to(ROOT))], cwd=ROOT) == path.read_bytes()
    if item.get('origin'):
        origins[item['origin']] = item['sha256']
for name in ['manifest.json', 'prelaunch/manifest.json']:
    path = PUBLIC / name
    assert subprocess.check_output(['git', 'show', head + ':' + str(path.relative_to(ROOT))], cwd=ROOT) == path.read_bytes()
local = {}
for path in sorted(STUDY.rglob('*')):
    if not path.is_file():
        continue
    assert '__pycache__' not in path.parts and path.suffix not in ['.so', '.pyc'], str(path)
    assert origins.get(str(path.relative_to(ROOT))) == sha(path), str(path)
    local[str(path.relative_to(STUDY))] = sha(path)
protocol = read(STUDY / 'protocol.json')
assert sha(STUDY / 'protocol.json') == '0f5a591fbfb66fd29b5f9cd11d42b482eb8cb09e74613b17cc384ed2c3daa849'
assert set(protocol['file_pins']).issubset(local)
assert sha(STUDY / 'analysis_pins.json') == read(Path(__file__).resolve().parent / 'release_prerequisites.json')['analysis_pins_sha256']
for name, digest in protocol['production_pins'].items():
    assert sha(ROOT / name) == digest, name
sys.path.insert(0, str(STUDY))
spec = importlib.util.spec_from_file_location('ae_monitor', STUDY / 'monitor.py')
monitor = importlib.util.module_from_spec(spec)
spec.loader.exec_module(monitor)
assert monitor.check_protocol() == protocol
monitor.resource_clearance()
ready = {'status': 'released',
         'released_at_utc': datetime.datetime.now(datetime.timezone.utc).isoformat(),
         'public_prelaunch_commit': head,
         'public_prelaunch_manifest_sha256': sha(PUBLIC / 'manifest.json'),
         'source_pins': local, 'production_pins': protocol['production_pins'],
         'scope': protocol['monitor_scope'],
         'authorization': 'Bounded retained-panel mutation accessibility study under standing autonomous authorization; '
                          'reported before launch. Exact existing V persistent-target world and all retained Y mutants; '
                          'no new genetic draws or price change. First attempt only; no retry, scope reduction, paid compute, '
                          'new organism rule or larger selection rollout.'}
with (STUDY / 'ready.json').open('x') as stream:
    stream.write(json.dumps(ready, indent=2) + '\n')
assert monitor.check_ready(protocol) == ready
print(json.dumps({'status': 'released', 'source_pins': len(local),
                  'production_pins': len(protocol['production_pins']),
                  'ready_sha256': sha(STUDY / 'ready.json'), 'public_commit': head}, indent=2))
