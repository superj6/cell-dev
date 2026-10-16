"""Read-only verification of the prospective depth study; no simulator imports."""
from __future__ import annotations

import argparse
import hashlib
import json
import subprocess
from pathlib import Path, PurePosixPath

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[1]
REVISION = '1a7f38bd3222bacf27367fd99998d87776c34ec5'


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
            and manifest['planned_calls'] == 97342, 'prospective zero-call manifest required')
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
            and (protocol['research_lives'], protocol['startup_lives'], protocol['total_calls']) == (97334, 8, 97342),
            'fixed research/startup inventory')
    require(protocol['search'] == dict(generations=8, parents=32, children=224, shortlist=64,
                base_lives=32, recheck_lives=32, selection_lives=81920, validation_generations=[0, 4, 7],
                validation_lives=48, final_lives=6, research_lives=81974, startup_lives=4, total_calls=81978)
            and protocol['measurement'] == dict(endpoint_genomes=32, endpoint_worlds=3,
                endpoint_lives_per_genome_world=32, endpoint_lives=3072, confirmation_genomes=4,
                confirmation_worlds=6, confirmation_lives_per_genome_world=512, confirmation_lives=12288,
                research_lives=15360, startup_lives=4, total_calls=15364), 'exact two-phase call matrix')
    worlds = ['patch', 'pool', 'persistent', 'blink80_20', 'transfer', 'reserved_capacity3']
    require(protocol['reference_roles'] == ['AO', 'G8_joint', 'Pareto4_joint']
            and list(protocol['worlds']) == worlds and list(protocol['selection_worlds']) == worlds[:3]
            and protocol['endpoint_seeds'] == list(range(52520000, 52520032))
            and protocol['confirmation_seeds'] == list(range(52530000, 52530512))
            and protocol['native_seed'] == 53236 and protocol['extinct_charge'], 'fixed search and panels')
    require(protocol['endpoint_reference_captures'] == [19.046875, 16.029296875, 5.919921875]
            and protocol['endpoint_reference_worlds'] == worlds[:3], 'fixed endpoint capture scales')
    require(protocol['confirmation_roles'] == [*protocol['reference_roles'], 'depth8_joint']
            and protocol['primary_contrast'] == ['depth8_joint', 'Pareto4_joint']
            and protocol['endpoint_rule'] == dict(worlds=worlds[:3],
                capture_scales=[19.046875, 16.029296875, 5.919921875], fitness_weights=[.5, .25, .25],
                order=['minimum_capture_fraction_descending', 'weighted_production_F_descending',
                       'native_id_ascending'], frozen_before_confirmation=True, replaces_historical_endpoint=False),
            'frozen separate-panel endpoint and primary contrast')
    require(all(protocol['selection_worlds'][w] == protocol['worlds'][w]['world'] for w in worlds[:3]),
            'endpoint training physics equal search physics')
    reserved = dict(protocol['worlds']['patch']['world'], patch_count=4, patch_capacity=3,
                    R_min=2.5, R_max=4.5, patch_refill_fast=60., patch_refill_slow=180.)
    require(protocol['worlds']['reserved_capacity3']['world'] == reserved, 'reserved physical combination')
    start = protocol['population_start']
    require(start['shape'] == [32, 875] and start['new_ids'] == list(range(32))
            and len(start['old_ids']) == len(set(start['old_ids'])) == len(start['row_sha256']) == 32
            and start['old_to_new'] == [dict(old_id=old, new_id=i, row=i, raw_sha256=start['row_sha256'][i])
                                       for i, old in enumerate(start['old_ids'])], 'all32 ordered founders')
    require(set(protocol['configs']) == {'pareto'}, 'one continuation arm')
    for record in protocol['configs'].values():
        require(sha(checked(base, record['path'])) == record['sha256'], 'frozen search configuration')
    refs = read(checked(base, protocol['references_manifest']))
    require(refs['roles'] == protocol['reference_roles'] and refs['rows'] == protocol['references']
            and refs['shape'] == [3, 875] and refs['dtype'] == 'float32', 'three fixed reference rows')
    for row in refs['rows']:
        require(sha(checked(base, row['path'])) == row['file_sha256'], 'fixed reference genome')
    limits, package, phases = protocol['runtime_budget'], protocol['package_budget'], protocol['phase_budgets']
    require((limits['cpu_seconds'], limits['wall_seconds'], limits['threads'], limits['workers'])
            == (10620, 7020, 2, 1) and limits['rss_bytes'] == 4*1024**3
            and limits['address_space_bytes'] == 8*1024**3 and limits['minimum_available_bytes'] == 4*1024**3
            and limits['cleanup_margin_seconds'] == 10, 'fixed runtime bounds')
    require((package['cpu_seconds'], package['wall_seconds'], package['preparation_terminal_cpu_reserve'],
             package['preparation_terminal_wall_reserve']) == (10800, 7200, 180, 180), 'cumulative package caps')
    require(set(phases) == {'pareto', 'measurement'}
            and (phases['pareto']['cpu_seconds'], phases['pareto']['wall_seconds']) == (8700, 5400)
            and (phases['measurement']['cpu_seconds'], phases['measurement']['wall_seconds']) == (1920, 1620),
            'phase allocation')
    for category in ('source_pins', 'input_pins'):
        for name, pin in protocol[category].items():
            require(sha(checked(base, name)) == pin, 'frozen source/input: ' + name)
    for field, name in (('seed_audit_sha256', 'namespace/seed_audit.json'),
                        ('reservation_sha256', 'reservation.json')):
        require(sha(base / name) == protocol[field], 'namespace binding')
    audit, reservation = read(base / 'namespace/seed_audit.json'), read(base / 'reservation.json')
    blocks = [[52520000, 52530000], [52530000, 52540000]]
    require(audit['status'] == 'passed' and not audit['reserved'] and not audit['registered']
            and audit['source_revision'] == REVISION and audit['unique_native_ids'] == 564
            and audit['actual_seed_collisions'] == audit['unresolved_NPZ_errors'] == 0
            and reservation['status'] == 'reserved' and reservation['simulated_lives'] == 0
            and reservation['seed_audit_sha256'] == protocol['seed_audit_sha256'],
            'reviewed namespace before reservation')
    for key, expected in (('native_seed', 53236), ('native_life_seeds', protocol['native_life_seeds']),
                          ('endpoint_seeds', protocol['endpoint_seeds']),
                          ('confirmation_seeds', protocol['confirmation_seeds']), ('seed_blocks', blocks)):
        require(audit[key] == reservation[key] == expected, 'exact namespace scope: ' + key)
    native = protocol['native_life_seeds']
    require(len(native) == len(set(native)) == 564
            and not any(52520000 <= seed < 52540000 for seed in native), 'disjoint native IDs')
    records = audit['native_records']
    expected_keys = ({('gen', g, i) for g in range(8) for i in range(64)}
                     | {('valid', g, i) for g in (0, 4, 7) for i in range(16)}
                     | {('final', g, i) for g in (0, 1) for i in range(2)})
    require(len(records) == 564 and {r['seed'] for r in records} == set(native)
            and {(r['purpose'], r['index'], r['life']) for r in records} == expected_keys,
            'complete native seed schedule; growth repeats final index0')
    previous_audit = ROOT / 'results/resource_patch_population_20261015/namespace/seed_audit.json'
    require(sha(previous_audit) == audit['prior_fixture_review_sha256'], 'latest population fixture audit')
    for name, pin in audit['native_source_pins'].items():
        require(protocol['production_pins'][name] == pin, 'native seed source binding')
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
    return dict(status='passed', archive_files=len(actual), planned_calls=97342, scientific_calls=0,
                protocol_sha256=digest, simulator_calls=0, builds=0, random_draws=0)


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--archive', type=Path, default=HERE)
    print(json.dumps(verify(parser.parse_args().archive), indent=2))
