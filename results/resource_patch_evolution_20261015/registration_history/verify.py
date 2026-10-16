"""Verify the prospective evolution archive with no simulator imports or calls."""
import hashlib
import json
import subprocess
from pathlib import Path

HERE=Path(__file__).resolve().parent
ROOT=HERE.parents[1]


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def read(path):
    return json.loads(path.read_text())


def verify():
    manifest=read(HERE/'manifest.json')
    actual={str(p.relative_to(HERE)) for p in HERE.rglob('*')
            if p.is_file() and p!=HERE/'manifest.json' and '__pycache__' not in p.parts}
    assert actual==set(manifest['files'])
    for name,pin in manifest['files'].items():
        path=HERE/name
        assert not path.is_symlink() and path.resolve().is_relative_to(HERE)
        assert sha(path)==pin['sha256'] and path.stat().st_size==pin['bytes'],name
    protocol=read(HERE/'protocol.json')
    assert manifest['protocol_sha256']==read(HERE/'READY.json')['protocol_sha256']==sha(HERE/'protocol.json')
    assert protocol['total_calls']==28222 and protocol['research_lives']==28214 and protocol['startup_lives']==8
    assert protocol['seeds']==list(range(52490000,52490512))
    assert protocol['native_seed']==53234
    review=read(HERE/'reviews/actual_input_review.json')
    assert review['status']=='passed' and review['protocol_sha256']==sha(HERE/'protocol.json')
    for label in ('source_pins','input_pins'):
        for name,digest in protocol[label].items():
            assert sha(HERE/name)==digest,name
    for field,name in (('seed_audit_sha256','namespace/seed_audit.json'),('reservation_sha256','reservation.json')):
        assert sha(HERE/name)==protocol[field]
    assert read(HERE/'namespace/seed_audit.json')['status']=='passed'
    for name,digest in protocol['production_pins'].items():
        value=subprocess.check_output(['git','show',protocol['source_revision']+':'+name],cwd=ROOT)
        assert hashlib.sha256(value).hexdigest()==digest,name
    for item in read(HERE/'namespace_references.json'):
        assert sha(ROOT/item['public_path'])==item['sha256']
    return dict(status='passed',archive_files=len(actual),planned_calls=28222,simulator_calls=0,
                protocol_sha256=sha(HERE/'protocol.json'))


if __name__=='__main__':
    print(json.dumps(verify(),indent=2))
