"""Root AD release after prospective publication; no engine calls here."""
from pathlib import Path
import datetime
import hashlib
import importlib.util
import json
import subprocess

ROOT = Path(__file__).resolve().parents[2]
STUDY = ROOT / 'outputs/autonomous_visibility_dark_tail_information_20261014'
PUBLIC = ROOT / 'results/visibility_dark_tail_information_20261014'


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def read(path):
    return json.loads(path.read_text())


assert not any((STUDY / name).exists() for name in
               ['ready.json', 'attempt.json', 'budget.json', 'validation', 'rows', 'logs', 'build-cache'])
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
assert sha(STUDY / 'protocol.json') == 'ee041636fec03ab3dc8e468b0d3427d75a2ac2736436b4dd954e3ac1c96100fe'
assert set(protocol['file_pins']).issubset(local)
assert sha(STUDY / 'analysis_pins.json') == '4a87a35aa1572b1e3b63ec71a079da3656ffb8ef84c6dd0fa748f3874ce06549'
for name, digest in protocol['production_pins'].items():
    assert sha(ROOT / name) == digest, name
spec = importlib.util.spec_from_file_location('ad_monitor', STUDY / 'monitor.py')
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
         'authorization': 'Bounded information-payoff measurement under standing autonomous authorization; '
                          'reported before launch. Only existing flash low amplitude and I/B physical amplitude '
                          'parameter21 change to zero. First attempt only; no retry, scope reduction, paid compute, '
                          'new organism rule or larger selection rollout.'}
with (STUDY / 'ready.json').open('x') as stream:
    stream.write(json.dumps(ready, indent=2) + '\n')
assert monitor.check_ready(protocol) == ready
print(json.dumps({'status': 'released', 'source_pins': len(local),
                  'production_pins': len(protocol['production_pins']),
                  'ready_sha256': sha(STUDY / 'ready.json'), 'public_commit': head}, indent=2))
