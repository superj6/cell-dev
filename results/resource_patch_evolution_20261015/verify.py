"""Verify the terminal resource-patch archive without simulator imports, builds or draws."""
from __future__ import annotations

import argparse
import hashlib
import json
import subprocess
from pathlib import Path, PurePosixPath

HERE = Path(__file__).resolve().parent
ROOT = next(parent for parent in HERE.parents if (parent / '.git').is_dir())
PROTOCOL = '0b0fd4e0fd2392f3f03f7f6bf5822714d64ce312aa20887770d0338c9c452da1'
REVISION = '52e390ae0b39b6c954e414ae07a0386b8ccc075f'
ROLES = ('AO_start', 'mixed4', 'mixed8')
WORLDS = ('patch', 'pool', 'persistent', 'blink80_20', 'transfer')
VERSIONS = ('README.md', 'verify.py', 'manifest.json')


def require(value, message):
    if not value:
        raise ValueError(message)


def read(path):
    return json.loads(Path(path).read_text())


def sha(path):
    digest = hashlib.sha256()
    with Path(path).open('rb') as stream:
        for chunk in iter(lambda: stream.read(1024**2), b''):
            digest.update(chunk)
    return digest.hexdigest()


def checked(base, name):
    relative = PurePosixPath(name)
    require(relative.parts and not relative.is_absolute() and str(relative) == name
            and all(part not in ('', '.', '..') for part in relative.parts), 'unsafe path: ' + name)
    path = Path(base)
    for part in relative.parts:
        path /= part
        require(not path.is_symlink(), 'symlink: ' + name)
    require(path.resolve().is_relative_to(Path(base).resolve()), 'escaped path: ' + name)
    return path


def files(base):
    result = set()
    for path in Path(base).rglob('*'):
        require(not path.is_symlink(), 'symlink in archive')
        if path.is_file() and '__pycache__' not in path.parts:
            result.add(str(path.relative_to(base)))
    return result


def manifest_files(base, manifest):
    require(files(base) == set(manifest['files']) | {'manifest.json'}, 'manifest file set')
    for name, pin in manifest['files'].items():
        path = checked(base, name)
        require(sha(path) == pin['sha256'] and path.stat().st_size == pin['bytes'], 'manifest: ' + name)


def confirmation_files(base):
    index = read(base / 'row_index.json')
    expected = {f'raw/{world}/row_{i:02d}.npz' for world in WORLDS for i in range(3)}
    require(set(index) == expected, 'exact 15 confirmation batches')
    result = {}
    for world in WORLDS:
        for i, role in enumerate(ROLES):
            name = f'raw/{world}/row_{i:02d}.npz'
            scored = f'scored/{world}/row_{i:02d}.npz'
            item = index[name]
            require(item['status'] == 'validated' and item['requested_lives'] == item['lives'] == 512
                    and item['abi'] == 6 and item['role'] == role and item['world'] == world
                    and item['scored_path'] == scored, 'confirmation identity: ' + name)
            result[name], result[scored] = item['sha256'], item['scored_sha256']
    actual = {prefix + '/' + name for prefix in ('raw', 'scored') for name in files(base / prefix)}
    require(actual == set(result), 'exact 15 raw and 15 scored files')
    for name, digest in result.items():
        require(sha(checked(base, name)) == digest, 'raw/scored: ' + name)
    return result


def cleared(value):
    require(value['status'] == 'complete' and value['protocol_sha256'] == PROTOCOL
            and value['exit_code'] == value['worker_exit_code'] == 0
            and not value['running'] and not value['queued'], 'completed owned worker')
    cleanup = value['terminal_cleanup']
    require(cleanup['same_pid_namespace'] and cleanup['all_owned_groups_exited']
            and cleanup['all_worker_identities_exited'] and not cleanup['remaining_descendants']
            and not cleanup['remaining_group_members'] and not cleanup['remaining_worker_identities'],
            'owned worker cleanup')


def terminal_bindings(base):
    base = Path(base)
    protocol = read(base / 'protocol.json')
    require(sha(base / 'protocol.json') == PROTOCOL and protocol['source_revision'] == REVISION, 'fixed protocol')
    require(tuple(protocol['roles']) == ROLES and tuple(protocol['worlds']) == WORLDS, 'three roles/five worlds')
    require(protocol['seeds'] == list(range(52490000, 52490512)) and protocol['native_seed'] == 53234, 'seed scope')
    require((protocol['total_calls'], protocol['research_lives'], protocol['startup_lives']) == (28222, 28214, 8),
            'registered call inventory')
    require(read(base / 'READY.json')['protocol_sha256'] == PROTOCOL, 'READY binding')
    release = read(base / 'release.json')
    require(release['status'] == 'released' and release['protocol_sha256'] == PROTOCOL, 'release binding')
    require(release['launch_source_sha256'] == sha(base / 'release_and_run.py')
            and release['preflight_failure_sha256'] == sha(base / 'prelaunch_launcher_history/preflight_failure.json'),
            'retained zero-call launcher correction')
    failure = read(base / 'prelaunch_launcher_history/preflight_failure.json')
    require(failure['status'] == 'stopped_before_execution' and failure['protocol_sha256'] == PROTOCOL
            and failure['started_builds'] == failure['started_lives'] == 0
            and failure['original_release_sha256']
            == sha(base / 'prelaunch_launcher_history/release_before_namespace.json')
            and failure['frozen_monitor_sha256'] == sha(base / 'monitor.py'), 'preserved preflight failure')
    review = read(base / 'reviews/actual_input_review.json')
    require(review['status'] == 'passed' and review['protocol_sha256'] == PROTOCOL, 'input review binding')
    for category in ('source_pins', 'input_pins'):
        for name, digest in protocol[category].items():
            require(sha(checked(base, name)) == digest, 'frozen source/input: ' + name)
    for field, name in (('seed_audit_sha256', 'namespace/seed_audit.json'),
                        ('reservation_sha256', 'reservation.json')):
        require(sha(base / name) == protocol[field], 'namespace binding')
    require(read(base / 'namespace/seed_audit.json')['status'] == 'passed', 'namespace audit')
    budget, whole, measured = [read(base / name) for name in
                              ('budget.json', 'study_complete.json', 'measurement_complete.json')]
    require(all(item['status'] == 'complete' and item['protocol_sha256'] == PROTOCOL
                for item in (budget, whole, measured)), 'three terminal completion markers')
    require((whole['research_lives'], whole['startup_lives'], whole['total_calls']) == (28214, 8, 28222),
            'whole-study calls')
    require((measured['research_lives'], measured['startup_lives'], measured['rows']) == (7680, 4, 15),
            'confirmation calls')
    require(whole['measurement_complete_sha256'] == sha(base / 'measurement_complete.json')
            and measured['row_index_sha256'] == sha(base / 'row_index.json')
            and measured['endpoints_sha256'] == sha(base / 'endpoints.json'), 'terminal cross-links')
    require(budget['release_sha256'] == sha(base / 'release.json')
            and budget['attempt_sha256'] == sha(base / 'attempt.json'), 'owned attempt binding')
    require(budget['cpu_seconds'] < 5280 and budget['wall_seconds'] < 3480
            and budget['search_cpu_seconds'] < 4080 and budget['confirmation_cpu_seconds'] < 1200, 'runtime caps')
    cleared(budget)
    require(set(budget['phase_records']) == {'mixed', 'confirmation'}, 'exact owned phases')
    for phase, record in budget['phase_records'].items():
        require(record['path'] == f'execution/{phase}/budget.json', 'phase budget path')
        path = checked(base, record['path'])
        require(sha(path) == record['sha256'], 'phase budget pin')
        value = read(path)
        cleared(value)
        require(value['attempt_sha256'] == sha(path.parent / 'attempt.json')
                and value['release_sha256'] == sha(base / 'release.json'), 'phase attempt binding')
        require(value['peak_owned_rss_bytes'] < value['cap_rss_bytes'] == 4 * 1024**3
                and value['available_memory_bytes'] >= value['minimum_available_bytes'] == 4 * 1024**3
                and value['worker_address_space_bytes'] == 8 * 1024**3, 'phase memory bounds')
    folder = base / 'runs/mixed'
    marker = read(folder / 'search_complete.json')
    require(whole['search_complete_pins'] == {'mixed': sha(folder / 'search_complete.json')}, 'search marker pin')
    require(marker['status'] == 'complete' and marker['research_lives'] == 20534 and marker['startup_lives'] == 4
            and marker['protocol_sha256'] == PROTOCOL and marker['release_sha256'] == sha(base / 'release.json'),
            'search scope')
    require(marker['count_proof'] == dict(selection=20480, valid=48, final=6, growth_half=2,
            native_evals=2560, generations=8, children_per_generation=224, midpoint_added_lives=0), 'search counts')
    require(set(marker['output_pins']) == {'checkpoint.pt', 'config.yaml', 'determinism.json', 'curves.jsonl',
            'lineage.jsonl', 'population.json', 'best_genome.json', 'results.jsonl', 'search_startup.json',
            'generation4/checkpoint.pt', 'generation4/best_genome.json', 'generation4/snapshot.json'}, 'search files')
    require(set(marker['checkpoint_log_pins']) == {'curves.jsonl', 'lineage.jsonl', 'clones.jsonl'}, 'search logs')
    for name, digest in marker['output_pins'].items():
        require(sha(checked(folder, name)) == digest, 'search output: ' + name)
    for name, pin in marker['checkpoint_log_pins'].items():
        path = checked(folder, name)
        require(sha(path) == pin['sha256'] and path.stat().st_size == pin['bytes'], 'checkpoint log: ' + name)
    for phase, name in (('mixed', 'runs/mixed/search_startup.json'), ('confirmation', 'startup.json')):
        startup = read(base / name)
        require(startup['startup_lives'] == 4 and startup['protocol_sha256'] == PROTOCOL
                and startup['identity'] == protocol['expected_numerical_identity'], 'four-call startup identity')
        patches = startup['patches']
        require(patches['lives'] == 2 and patches['seed'] == 42000000 and patches['name'] == 'reflex_count1'
                and patches['fixture_sha256'] == sha(base / 'inputs/patch_truth.json')
                and patches['calls_path'] == f'execution/{phase}/patch_truth/calls.json', 'patch startup scope')
        callpath = checked(base, patches['calls_path'])
        require(patches['calls_sha256'] == sha(callpath), 'patch startup call pin')
        calls = read(callpath)
        require([item['backend'] for item in calls] == ['C_full', 'C_fast'], 'two patch startup calls')
        for item, raw in zip(calls, ('full.npz', 'fast.npz')):
            require(item['status'] == 'validated' and item['seed'] == 42000000
                    and item['raw_sha256'] == sha(callpath.parent / raw), 'startup raw pin')
    endpoints = read(base / 'endpoints.json')
    require(endpoints['roles'] == list(ROLES) and endpoints['protocol_sha256'] == PROTOCOL, 'endpoint scope')
    require([row['role'] for row in endpoints['genomes']] == list(ROLES), 'endpoint row order')
    for row in endpoints['genomes']:
        require(sha(checked(base, row['path'])) == row['file_sha256'], 'endpoint genome')
    result = read(base / 'summary.json')
    require(result['status'] == 'complete' and result['protocol_sha256'] == PROTOCOL
            and result['row_index_sha256'] == sha(base / 'row_index.json'), 'summary binding')
    require((result['research_lives'], result['startup_lives'], result['paired_life_clusters']) == (7680, 4, 512),
            'summary scope')
    rows = confirmation_files(base)
    audit = read(base / 'reviews/independent_accounting.json')
    require(audit['status'] == 'passed' and audit['protocol_sha256'] == PROTOCOL
            and audit['row_index_sha256'] == sha(base / 'row_index.json')
            and audit['summary_sha256'] == sha(base / 'summary.json'), 'independent accounting binding')
    require((audit['raw_batches'], audit['scored_batches'], audit['confirmation_lives']) == (15, 15, 7680),
            'independent accounting coverage')
    require(all(audit['artifacts'].get(name) == digest for name, digest in rows.items()), 'audited raw/scored pins')
    for name, digest in audit['artifacts'].items():
        require(sha(checked(base, name)) == digest, 'independently audited artifact: ' + name)
    native = read(base / 'native_replay_result.json')
    require(native['status'] == 'passed' and native['protocol_sha256'] == PROTOCOL
            and native['offspring_replayed'] == 1792 and native['point_additions_replayed'] == 3584
            and native['all_32_midpoint_rows_bound'] and native['all_32_final_rows_bound']
            and native['simulated_lives'] == native['random_draws'] == 0, 'recorded-genetics replay')
    for name, digest in native['source_sha256'].items():
        require(digest == protocol['source_pins'][name] == sha(checked(base, name)), 'genetics replay source')
    require(set(native['source_sha256']) == {'native_replay.py', 'replay_ops.py'}, 'genetics source coverage')
    replay = native['runs']['mixed']
    snapshot = read(folder / 'generation4/snapshot.json')
    require(snapshot == marker['midpoint']
            and snapshot['checkpoint_sha256'] == sha(folder / 'generation4/checkpoint.pt')
            and snapshot['genome_raw_sha256'] == replay['midpoint']['row_sha256'][0]
            == endpoints['genomes'][1]['raw_sha256']
            and replay['final']['row_sha256'][0] == endpoints['genomes'][2]['raw_sha256'], 'replayed fixed endpoints')
    return protocol, rows


def verify(base=HERE):
    base = Path(base).resolve()
    manifest = read(base / 'manifest.json')
    require(manifest['status'] == 'complete' and manifest['total_calls'] == 28222
            and manifest['protocol_sha256'] == PROTOCOL, 'terminal manifest')
    manifest_files(base, manifest)
    historical = read(base / 'registration_history/manifest.json')
    require(historical['status'] == 'prospective' and historical['protocol_sha256'] == PROTOCOL,
            'preserved prospective manifest')
    release = read(base / 'release.json')
    require(release['prospective_manifest_sha256'] == release['public_manifest_sha256']
            == sha(base / 'registration_history/manifest.json')
            and release['prospective_commit'] == release['public_commit'], 'published registration binding')
    for name, pin in historical['files'].items():
        path = checked(base, 'registration_history/' + name if name in VERSIONS else name)
        require(sha(path) == pin['sha256'] and path.stat().st_size == pin['bytes'], 'prospective byte: ' + name)
    protocol, rows = terminal_bindings(base)
    snapshot = base / 'production'
    if snapshot.exists():
        require(files(snapshot) == set(protocol['production_pins']), 'complete pinned production snapshot')
    for name, digest in protocol['production_pins'].items():
        if snapshot.exists():
            actual = sha(checked(snapshot, name))
        else:
            source = subprocess.check_output(['git', 'show', REVISION + ':' + name], cwd=ROOT)
            actual = hashlib.sha256(source).hexdigest()
        require(actual == digest, 'committed production dependency: ' + name)
    for row in read(base / 'namespace_references.json'):
        require(sha(checked(ROOT, row['public_path'])) == row['sha256'], 'historical namespace reference')
    receipt = read(base / 'packaging_receipt.json')
    require(receipt['status'] == 'staged' and receipt['protocol_sha256'] == PROTOCOL
            and receipt['prospective_manifest_sha256'] == sha(base / 'registration_history/manifest.json')
            and receipt['summary_sha256'] == sha(base / 'summary.json')
            and receipt['helper_sha256'] == sha(base / 'terminal_package/pack.py')
            and receipt['raw_scored_files'] == rows
            and receipt['simulator_calls'] == receipt['builds'] == receipt['random_draws'] == 0, 'packaging receipt')
    return dict(status='passed', archive_files=len(manifest['files']), protocol_sha256=PROTOCOL,
                raw_batches=15, scored_batches=15, confirmation_lives=7680, total_calls=28222,
                production_source='snapshot' if snapshot.exists() else 'git:' + REVISION,
                verifier_simulator_calls=0, verifier_builds=0, verifier_random_draws=0)


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--archive', type=Path, default=HERE)
    print(json.dumps(verify(parser.parse_args().archive), indent=2))
