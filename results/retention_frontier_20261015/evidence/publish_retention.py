"""Copy reviewed AK evidence; never execute a study or overwrite changed prospective source."""
from pathlib import Path
import hashlib,json,shutil,sys
ROOT=Path(__file__).resolve().parents[2]
STUDY=ROOT/'outputs/autonomous_retention_frontier_20261015'
PUBLIC=ROOT/'results/retention_frontier_20261015'
AUDIT=ROOT/'outputs/cumulative_capability_20261015'
phase=sys.argv[1]
assert phase in ('prospective','terminal')
PUBLIC.mkdir(exist_ok=True)
def sha(p):return hashlib.sha256(p.read_bytes()).hexdigest()
def copy(source,target):
    target.parent.mkdir(parents=True,exist_ok=True)
    if target.exists() and sha(source)!=sha(target):
        raise ValueError('refuse changed archived file: '+str(target))
    shutil.copyfile(source,target)
for source in STUDY.rglob('*'):
    if source.is_file() and '__pycache__' not in source.parts and source.suffix not in ('.tmp','.pyc'):
        copy(source,PUBLIC/source.relative_to(STUDY))
protocol=json.loads((STUDY/'protocol.json').read_text())
for name in protocol['production_pins']:
    copy(ROOT/name,PUBLIC/'production'/name)
for name in protocol['original_input_pins']:
    copy(ROOT/name,PUBLIC/'original'/name)
for folder in ('operations','design','reviews'):
    for source in (AUDIT/folder).rglob('*'):
        if source.is_file() and '__pycache__' not in source.parts and source.suffix!='.pyc':
            copy(source,PUBLIC/'evidence'/source.relative_to(ROOT))
copy(Path(__file__),PUBLIC/'evidence/publish_retention.py')
artifacts={str(p.relative_to(PUBLIC)):{'sha256':sha(p),'bytes':p.stat().st_size} for p in sorted(PUBLIC.rglob('*')) if p.is_file() and p.name!='manifest.json'}
(PUBLIC/'manifest.json').write_text(json.dumps({'phase':phase,'canonical_study':str(STUDY.relative_to(ROOT)),'protocol_sha256':sha(STUDY/'protocol.json'),'artifacts':artifacts},indent=2)+'\n')
print(json.dumps({'phase':phase,'files':len(artifacts),'bytes':sum(x['bytes'] for x in artifacts.values()),'protocol_sha256':sha(STUDY/'protocol.json')}))
