"""Verify the prospective archive without importing the simulator or running a life."""
from __future__ import annotations

import hashlib
import json
import subprocess
from pathlib import Path

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[1]


def digest(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def read(name):
    return json.loads((HERE / name).read_text())


def checked_path(name):
    path = (HERE / name).resolve()
    if not path.is_relative_to(HERE) or path.is_symlink():
        raise ValueError('unsafe archive path: ' + name)
    return path


def verify():
    manifest = read('manifest.json')
    actual = {str(p.relative_to(HERE)) for p in HERE.rglob('*') if p.is_file()
              and p.name != 'manifest.json' and '__pycache__' not in p.parts}
    if actual != set(manifest['files']):
        raise ValueError('archive file inventory differs')
    for name, pin in manifest['files'].items():
        path = checked_path(name)
        if path.stat().st_size != pin['bytes'] or digest(path) != pin['sha256']:
            raise ValueError('archive bytes differ: ' + name)
    protocol, ready = read('protocol.json'), read('READY.json')
    if (digest(HERE / 'protocol.json') != ready['protocol_sha256']
            or ready['simulation_calls'] != 0 or ready['builds'] != 0
            or ready['status'] != 'prepared_not_launched'):
        raise ValueError('prospective readiness differs')
    release = read('release.json')
    if (release['status'] != 'released' or release['protocol_sha256'] != ready['protocol_sha256']
            or release['source_input_review_sha256'] != digest(HERE / 'source_input_review.md')
            or release['research_calls_before_release'] != 0):
        raise ValueError('prospective release binding differs')
    for section in ('input_pins', 'source_pins'):
        for name, pin in protocol[section].items():
            if digest(checked_path(name)) != pin:
                raise ValueError('protocol pin differs: ' + name)
    for name in ('seed_audit', 'reservation'):
        if digest(HERE / (name + '.json')) != protocol[name + '_sha256']:
            raise ValueError('namespace pin differs: ' + name)
    if digest(HERE / 'source_checks.json') != ready['source_checks_sha256']:
        raise ValueError('preparation check receipt differs')
    audit, reservation = read('seed_audit.json'), read('reservation.json')
    inventory = read('candidate_seed_inventory.json')
    if (audit['status'] != 'passed' or audit['numeric_overlap_count'] != 0
            or inventory['NPZ_matches'] or inventory['NPZ_errors'] or inventory['JSON_errors']
            or digest(HERE / 'candidate_seed_inventory.json') != audit['inventory_sha256']
            or reservation['seed_audit_sha256'] != digest(HERE / 'seed_audit.json')
            or reservation['status'] != 'reserved_development_only' or reservation['confirmation_eligible']):
        raise ValueError('development namespace evidence differs')
    expected_roles = ['AM_reference', 'AN_start', 'unchanged8', 'unchanged24', 'balanced8', 'balanced24']
    if protocol['roles'] != expected_roles or protocol['seeds'] != list(range(52430000, 52430032)):
        raise ValueError('fixed roles or development seeds differ')
    schedule = protocol['schedule']
    expected = [(role, duration, seed, True) for duration in (85, 1024) for role in expected_roles
                for seed in range(52430000, 52430032)]
    expected += [(role, 85, 52430000, False) for role in expected_roles]
    if [(r['role'], r['T'], r['seed'], r['fast']) for r in schedule] != expected:
        raise ValueError('390-call fixed schedule differs')
    endpoints = read('inputs/endpoints.json')
    public = ROOT / endpoints['public_manifest']
    if digest(public) != endpoints['public_manifest_sha256']:
        raise ValueError('public AO endpoint manifest differs')
    public_genomes = json.loads(public.read_text())['genomes']
    for saved, original in zip(endpoints['genomes'], public_genomes, strict=True):
        if (saved['role'] != original['role'] or saved['raw_sha256'] != original['raw_sha256']
                or saved['file_sha256'] != original['file_sha256']
                or digest(checked_path(saved['path'])) != original['file_sha256']
                or digest(ROOT / saved['public_path']) != original['file_sha256']):
            raise ValueError('frozen public genotype differs')
    revision = protocol['source_revision']
    for name, expected_sha in protocol['production_pins'].items():
        data = subprocess.check_output(['git', 'show', f'{revision}:{name}'], cwd=ROOT)
        if hashlib.sha256(data).hexdigest() != expected_sha:
            raise ValueError('committed source differs: ' + name)
    references = read('references.json')
    for item in references['public_prior_inventory_references']:
        if digest(ROOT / item['public_path']) != item['sha256']:
            raise ValueError('retained prior inventory differs: ' + item['public_path'])
    for item in references['included_prior_inventory_references']:
        if digest(checked_path(item['archive_path'])) != item['sha256']:
            raise ValueError('included seed metadata differs: ' + item['archive_path'])
    return dict(status='passed', archive_files=len(manifest['files']), source_revision=revision,
                prospective_protocol_sha256=digest(HERE / 'protocol.json'), planned_calls=390,
                executed_calls_at_preparation=0, verifier_lives=0, verifier_builds=0,
                public_history_references=len(references['public_prior_inventory_references']))


if __name__ == '__main__':
    print(json.dumps(verify(), indent=2))
