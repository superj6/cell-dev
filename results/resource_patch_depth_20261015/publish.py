"""Publish the reviewed prospective depth study; no simulations, builds or namespace rescan."""
from __future__ import annotations

import json
import shutil
from pathlib import Path

import verify_public as verify

SOURCE = Path(__file__).resolve().parent
ROOT = SOURCE.parents[1]
TARGET = ROOT / 'results/resource_patch_depth_20261015'
SKIP = {'__pycache__', '.pytest_cache', '.ruff_cache', 'build-cache', 'fixtures', 'tmp',
        'reader_test_tmp', 'publication_logs'}
RUNTIME = ('release.json', 'attempt.json', 'execution', 'runs', 'raw', 'scored', 'startup.json', 'row_index.json',
           'measurement_complete.json', 'study_complete.json', 'budget.json', 'summary.json', 'build-cache',
           'endpoint_raw', 'endpoint_scored', 'endpoint_index.json', 'endpoint_population.npz',
           'endpoint_population.json', 'endpoint_selection.json', 'joint_genome.json', 'endpoints.json')


def excluded(relative):
    return any(part in SKIP or part.startswith('test_') or part.endswith('_tmp')
               for part in relative.parts[:-1]) or relative.suffix in ('.pyc', '.so', '.tmp')


def main():
    verify.require(not TARGET.exists(), 'public destination must not already exist')
    verify.require(not any((SOURCE / name).exists() for name in RUNTIME), 'prospective publication precedes runtime')
    protocol = verify.read(SOURCE / 'protocol.json')
    review = verify.read(SOURCE / 'reviews/actual_input_review.json')
    digest = verify.sha(SOURCE / 'protocol.json')
    verify.require(protocol['source_revision'] == verify.REVISION and protocol['total_calls'] == 97342
                   and review['status'] == 'passed' and review['protocol_sha256'] == digest,
                   'reviewed exact protocol required')
    verify.require(verify.read(SOURCE / 'READY.json')['protocol_sha256'] == digest, 'READY binding')
    for category, base in (('source_pins', SOURCE), ('input_pins', SOURCE), ('production_pins', ROOT),
                           ('original_input_pins', ROOT)):
        for name, pin in protocol[category].items():
            verify.require(verify.sha(verify.checked(base, name)) == pin, 'current pinned input/source: ' + name)
    audit = verify.read(SOURCE / 'namespace/seed_audit.json')
    verify.require(audit['status'] == 'passed' and verify.sha(SOURCE / 'namespace/seed_audit.json')
                   == protocol['seed_audit_sha256'] and verify.sha(SOURCE / 'reservation.json')
                   == protocol['reservation_sha256'], 'accepted namespace pins')
    previous = ROOT / 'results/resource_patch_population_20261015'
    by_sha = {row['sha256']: row['public_path'] for row in verify.read(previous / 'namespace_references.json')}
    latest = previous / 'namespace/candidate_seed_inventory.json'
    by_sha[verify.sha(latest)] = str(latest.relative_to(ROOT))
    references = []
    for original, pin in audit['historical_inventory_references'].items():
        public = by_sha.get(pin, original if original.startswith('results/') else None)
        verify.require(public is not None and verify.sha(verify.checked(ROOT, public)) == pin,
                       'missing pinned public inventory: ' + original)
        references.append(dict(original_path=original, public_path=public, sha256=pin))
    selected = {path for path in SOURCE.iterdir()
                if path.is_file() and path.suffix in ('.py', '.json', '.md', '.txt', '.log', '.diff')}
    for name in ('inputs', 'configs', 'namespace', 'reviews', 'tests', 'preparation_history'):
        for path in (SOURCE / name).rglob('*'):
            relative = path.relative_to(SOURCE)
            if excluded(relative):
                continue
            verify.require(not path.is_symlink(), 'symlink in prospective evidence')
            if path.is_file():
                selected.add(path)
    required = {'README.md', 'verify_public.py', 'publish.py', 'protocol.json', 'READY.json',
                'reviews/actual_input_review.json', *protocol['source_pins'], *protocol['input_pins'],
                *(record['path'] for record in protocol['configs'].values())}
    verify.require(required <= {str(path.relative_to(SOURCE)) for path in selected}, 'required source/input omitted')
    TARGET.mkdir()
    for path in sorted(selected):
        verify.require(not path.is_symlink(), 'regular evidence required')
        target = verify.checked(TARGET, str(path.relative_to(SOURCE)))
        target.parent.mkdir(parents=True, exist_ok=True)
        shutil.copyfile(path, target)
    for name, pin in audit['older_label_source_pins'].items():
        source = verify.checked(ROOT, name)
        verify.require(verify.sha(source) == pin, 'older label source changed')
        target = verify.checked(TARGET / 'namespace/older_label_sources', name)
        target.parent.mkdir(parents=True, exist_ok=True)
        shutil.copyfile(source, target)
    (TARGET / 'namespace_references.json').write_text(json.dumps(references, indent=2) + '\n')
    manifest = dict(status='prospective', scientific_calls=0, planned_calls=97342, protocol_sha256=digest,
        files={str(path.relative_to(TARGET)): dict(sha256=verify.sha(path), bytes=path.stat().st_size)
               for path in sorted(TARGET.rglob('*')) if path.is_file()})
    (TARGET / 'manifest.json').write_text(json.dumps(manifest, indent=2) + '\n')
    print(json.dumps(verify.verify(TARGET), indent=2))


if __name__ == '__main__':
    main()
