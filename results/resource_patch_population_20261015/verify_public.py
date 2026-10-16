"""Read-only verification of the prospective population diagnostic; no simulator imports."""
from __future__ import annotations

import argparse
import hashlib
import json
import subprocess
from pathlib import Path, PurePosixPath

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[1]
REVISION = '5d556443e91d558de8de27ab2e5dc7ae11a51415'


def require(value, message):
    if not value:
        raise ValueError(message)


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def read(path):
    return json.loads(Path(path).read_text())


def checked(base, name):
    relative = PurePosixPath(name)
    require(relative.parts and not relative.is_absolute() and str(relative) == name
            and all(part not in ('.', '..') for part in relative.parts), 'unsafe archive path')
    path = Path(base)
    for part in relative.parts:
        path /= part
        require(not path.is_symlink(), 'symlink in archive')
    require(path.resolve().is_relative_to(Path(base).resolve()), 'escaped archive path')
    return path


def verify(base=HERE):
    base = Path(base).resolve()
    manifest = read(base / 'manifest.json')
    require(manifest['status'] == 'prospective' and manifest['scientific_calls'] == 0
            and manifest['planned_calls'] == 15524, 'prospective zero-call manifest required')
    actual = set()
    for path in base.rglob('*'):
        require(not path.is_symlink(), 'symlink in public archive')
        if path.is_file() and path != base / 'manifest.json' and '__pycache__' not in path.parts:
            actual.add(str(path.relative_to(base)))
    require(actual == set(manifest['files']), 'exact manifest file set')
    for name, pin in manifest['files'].items():
        path = checked(base, name)
        require(sha(path) == pin['sha256'] and path.stat().st_size == pin['bytes'], 'artifact: ' + name)
    protocol, ready, review = [read(base / name) for name in
                               ('protocol.json', 'READY.json', 'reviews/actual_input_review.json')]
    digest = sha(base / 'protocol.json')
    require(manifest['protocol_sha256'] == ready['protocol_sha256'] == review['protocol_sha256'] == digest
            and review['status'] == 'passed' and ready['status'] == 'prepared_not_released', 'review/READY binding')
    require(protocol['source_revision'] == REVISION
            and (protocol['research_lives'], protocol['startup_lives'], protocol['total_calls']) == (15520, 4, 15524)
            and (protocol['genomes'], protocol['batches'], protocol['genome_world_rows'],
                 protocol['lives_per_genome_world']) == (97, 20, 485, 32), 'fixed inventory')
    require(protocol['groups'] == ['G8', 'mean4', 'pareto4', 'AO']
            and list(protocol['worlds']) == ['patch', 'pool', 'persistent', 'blink80_20', 'transfer']
            and protocol['seeds'] == list(range(52510000, 52510032)), 'fixed development panel')
    for category in ('source_pins', 'input_pins'):
        for name, pin in protocol[category].items():
            require(sha(checked(base, name)) == pin, 'frozen source/input: ' + name)
    for field, name in (('seed_audit_sha256', 'namespace/seed_audit.json'),
                        ('reservation_sha256', 'reservation.json')):
        require(sha(base / name) == protocol[field], 'namespace binding')
    audit, reservation = read(base / 'namespace/seed_audit.json'), read(base / 'reservation.json')
    require(audit['status'] == 'passed' and not audit['reserved']
            and audit['development_seeds'] == protocol['seeds']
            and reservation['status'] == 'reserved' and reservation['development_seeds'] == protocol['seeds']
            and audit['whole_block_half_open'] == reservation['whole_block_half_open'] == [52510000, 52520000],
            'development namespace scope')
    for field, name in (('inventory_sha256', 'candidate_seed_inventory.json'),
                        ('source_sha256', 'classify_namespace.py'), ('source_audit_sha256', 'audit_namespace.py')):
        require(sha(base / 'namespace' / name) == audit[field], 'audit evidence binding')
    for name, pin in audit['older_label_source_pins'].items():
        require(sha(checked(base / 'namespace/older_label_sources', name)) == pin, 'older label numerical source')
    references = read(base / 'namespace_references.json')
    require({row['original_path']: row['sha256'] for row in references}
            == audit['historical_inventory_references'], 'complete historical namespace references')
    for item in references:
        require(item['public_path'].startswith('results/')
                and sha(checked(ROOT, item['public_path'])) == item['sha256'], 'public namespace inventory')
    for name, pin in protocol['original_input_pins'].items():
        require(name.startswith('results/') and sha(checked(ROOT, name)) == pin, 'public scientific source: ' + name)
    for name, pin in protocol['production_pins'].items():
        source = subprocess.check_output(['git', 'show', REVISION + ':' + name], cwd=ROOT)
        require(hashlib.sha256(source).hexdigest() == pin, 'committed production source: ' + name)
    return dict(status='passed', archive_files=len(actual), planned_calls=15524, scientific_calls=0,
                protocol_sha256=digest, simulator_calls=0, builds=0, random_draws=0)


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--archive', type=Path, default=HERE)
    print(json.dumps(verify(parser.parse_args().archive), indent=2))
