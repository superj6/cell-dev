"""Archive exact AN evidence without overwriting changed prospective files."""
import hashlib
import json
import shutil
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
STUDY = ROOT / 'outputs/autonomous_occlusion_acquisition_20261015'
AUDIT = ROOT / 'outputs/audit_occlusion_acquisition_20261015'
PUBLIC = ROOT / 'results/occlusion_acquisition_20261015'
phase = sys.argv[1]
assert phase in ('prospective', 'terminal')


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def copy(source, target):
    target.parent.mkdir(parents=True, exist_ok=True)
    if target.exists() and sha(source) != sha(target):
        raise ValueError('refuse changed archive: ' + str(target))
    shutil.copyfile(source, target)


for base, target in ((STUDY, PUBLIC), (AUDIT, PUBLIC / 'evidence')):
    for source in sorted(base.rglob('*')):
        if (source.is_file() and not {'__pycache__'} & set(source.parts)
                and not (phase == 'prospective' and {'new_terminal_prep', 'new_genetics_prep'} & set(source.parts))
                and source.suffix not in ('.tmp', '.pyc')):
            copy(source, target / source.relative_to(base))
protocol = json.loads((STUDY / 'protocol.json').read_text())
for key, target in (('production_pins', 'production'), ('original_input_pins', 'original'),
                    ('review_pins', 'review_sources')):
    for name in protocol[key]:
        copy(ROOT / name, PUBLIC / target / name)
artifacts = {str(path.relative_to(PUBLIC)): {'sha256': sha(path), 'bytes': path.stat().st_size}
             for path in sorted(PUBLIC.rglob('*')) if path.is_file() and path.name != 'manifest.json'}
(PUBLIC / 'manifest.json').write_text(json.dumps({'phase': phase,
    'canonical_study': str(STUDY.relative_to(ROOT)), 'protocol_sha256': sha(STUDY / 'protocol.json'),
    'artifacts': artifacts}, indent=2) + '\n')
print(json.dumps({'phase': phase, 'files': len(artifacts),
                  'bytes': sum(row['bytes'] for row in artifacts.values())}))
