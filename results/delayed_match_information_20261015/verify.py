"""Verify the frozen and completed study without importing or invoking a simulator."""
import hashlib
import json
from pathlib import Path, PurePosixPath
import subprocess
import tarfile

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[1]
ROLES = ('I', 'E', 'P', 'N', 'B', 'R0', 'R1', 'D0', 'D1', 'D2', 'D3')
MAX_MEMBER_BYTES = 64 * 1024**2
MAX_RAW_BYTES = 1024**3


def require(condition, message):
    if not condition:
        raise ValueError(message)


def sha(path):
    value = hashlib.sha256()
    with Path(path).open('rb') as stream:
        for chunk in iter(lambda: stream.read(1024**2), b''):
            value.update(chunk)
    return value.hexdigest()


def read(path):
    return json.loads(Path(path).read_text())


def checked_path(base, name):
    relative = PurePosixPath(name)
    require(not relative.is_absolute() and relative.as_posix() == name
            and all(part not in ('', '.', '..') for part in relative.parts), 'unsafe path: ' + name)
    path = base
    for part in relative.parts:
        path = path / part
        require(not path.is_symlink(), 'symlink path: ' + name)
    require(path.resolve().is_relative_to(base.resolve()), 'escaped path: ' + name)
    return path


def scheduled_rows(study, protocol):
    rows = read(study / 'row_index.json')
    inputs = read(study / 'inputs.json')
    candidates = inputs['reflex_panel'] + inputs['instrument_panel']
    expected = [('development', seed, entry['id'], 'tissue' if i < 12 else 'instrument')
                for seed in range(52440000, 52440064) for i, entry in enumerate(candidates)]
    expected += [('confirmation', seed, role, 'instrument' if role in ROLES[:5] else 'tissue')
                 for seed in range(52450000, 52450512) for role in ROLES]
    require(len(candidates) == 16 and len(rows) == len(expected) == 6656, 'scheduled row count')
    require(tuple(protocol['roles']) == ROLES, 'confirmation roles')
    names = set()
    for i, (row, actual) in enumerate(zip(rows, expected)):
        stage, seed, role, _ = actual
        require(row['index'] == i and row['status'] == 'complete', 'incomplete or reordered row')
        require((row['stage'], row['seed'], row['role'], row['backend']) == actual, 'scheduled row differs')
        require(row['path'] == f'raw/{stage}_{seed}_{role}.npz', 'raw row path differs')
        require(row['path'] not in names, 'duplicate raw row')
        names.add(row['path'])
    return rows


def verify_raw(rows, destination=None):
    """Stream exact regular NPZ members; optional extraction never uses extractall."""
    expected = {'prelaunch/' + row['path']: row['sha256'] for row in rows}
    seen = set()
    total = 0
    previous = ''
    with tarfile.open(HERE / 'raw.tar.gz', 'r:gz') as archive:
        for member in archive:
            name = member.name
            require(name in expected and name not in seen and name > previous,
                    'unexpected, duplicate or unsorted tar member: ' + name)
            require(member.type == tarfile.REGTYPE and not member.issparse(), 'nonregular tar member: ' + name)
            require(0 < member.size <= MAX_MEMBER_BYTES, 'tar member size: ' + name)
            require(member.mode == 0o644 and member.uid == member.gid == member.mtime == 0
                    and member.uname == member.gname == '', 'tar metadata: ' + name)
            total += member.size
            require(total <= MAX_RAW_BYTES, 'raw extraction byte ceiling')
            stream = archive.extractfile(member)
            require(stream is not None, 'missing regular member bytes')
            output = None
            if destination is not None:
                path = checked_path(destination, name)
                path.parent.mkdir(parents=True, exist_ok=True)
                output = path.open('xb')
            digest = hashlib.sha256()
            count = 0
            try:
                with stream:
                    for chunk in iter(lambda: stream.read(1024**2), b''):
                        count += len(chunk)
                        digest.update(chunk)
                        if output is not None:
                            output.write(chunk)
            finally:
                if output is not None:
                    output.close()
            require(count == member.size and digest.hexdigest() == expected[name], 'raw member digest: ' + name)
            seen.add(name)
            previous = name
    require(seen == set(expected) and len(seen) == 6656, 'raw tar coverage differs')
    return {'raw_members': len(seen), 'raw_uncompressed_bytes': total}


def verify():
    manifest = read(HERE / 'manifest.json')
    require(not any(path.is_symlink() for path in HERE.rglob('*')), 'archive contains a symlink')
    actual = {str(p.relative_to(HERE)) for p in HERE.rglob('*')
              if p.is_file() and p != HERE / 'manifest.json' and '__pycache__' not in p.parts}
    require(actual == set(manifest['files']), 'archive inventory changed')
    for name, pin in manifest['files'].items():
        path = checked_path(HERE, name)
        require(sha(path) == pin['sha256'] and path.stat().st_size == pin['bytes'], 'archive pin: ' + name)
    historical = read(HERE / 'registration_history/manifest.json')
    for name, pin in historical['files'].items():
        retained = 'registration_history/' + name if name in ('README.md', 'verify.py') else name
        require(sha(checked_path(HERE, retained)) == pin['sha256'], 'prospective bytes changed: ' + name)
    study = HERE / 'prelaunch'
    protocol = read(study / 'protocol.json')
    ready, release = read(study / 'READY.json'), read(study / 'release.json')
    protocol_sha = sha(study / 'protocol.json')
    require(ready['protocol_sha256'] == release['protocol_sha256'] == protocol_sha, 'release protocol binding')
    require(release['status'] == 'released', 'unreleased study')
    require(release['scientific_calls_before_release'] == 0
            and release['actual_input_review_sha256'] == sha(study / 'actual_input_review.md')
            and release['policy_source_review_sha256'] == sha(study / 'source_review.md'), 'release review binding')
    require(ready['preparation_lives'] == ready['preparation_builds'] == ready['preparation_random_draws'] == 0,
            'preparation call inventory')
    for label in ('source_pins', 'input_pins'):
        for name, expected in protocol[label].items():
            require(sha(checked_path(study, name)) == expected, 'protocol pin: ' + name)
    require(sha(HERE / 'seed_audit.json') == protocol['seed_audit_sha256'], 'seed audit pin')
    require(sha(study / 'reservation.json') == protocol['reservation_sha256'], 'reservation pin')
    require(protocol['development_seeds'] == list(range(52440000, 52440064)), 'development seeds')
    require(protocol['confirmation_seeds'] == list(range(52450000, 52450512)), 'confirmation seeds')
    require(protocol['scientific_calls'] == 6656 and protocol['engineering_calls'] == 40
            and protocol['development_calls'] == 1024 and protocol['confirmation_calls'] == 5632,
            'declared call inventory')
    for name, expected in protocol['production_pins'].items():
        data = subprocess.check_output(['git', 'show', protocol['source_revision'] + ':' + name], cwd=ROOT)
        require(hashlib.sha256(data).hexdigest() == expected, 'committed source pin: ' + name)
    for item in read(HERE / 'namespace_references.json'):
        require(sha(checked_path(ROOT, item['public_path'])) == item['sha256'], 'namespace reference')
    marker, budget = read(study / 'measurement_complete.json'), read(study / 'budget.json')
    require(marker['status'] == budget['status'] == 'complete', 'incomplete measurement')
    require(not (study / 'measurement_incomplete.json').exists(), 'retained incomplete marker')
    require(marker['protocol_sha256'] == budget['protocol_sha256'] == protocol_sha, 'runtime protocol binding')
    require(budget['release_sha256'] == sha(study / 'release.json')
            and budget['attempt_sha256'] == sha(study / 'attempt.json'), 'runtime ownership binding')
    require(marker['backend_calls'] == 6656 and marker['engineering_calls'] == 40
            and marker['total_package_calls'] == 6696 and marker['development_calls'] == 1024
            and marker['confirmation_calls'] == 5632, 'completed call inventory')
    for key, name in (('row_index_sha256', 'row_index.json'), ('summary_sha256', 'summary.json'),
                      ('selected_arms_sha256', 'selected_arms.json')):
        require(marker[key] == sha(study / name), 'completion binding: ' + name)
    require(read(study / 'summary.json')['status'] == 'complete', 'incomplete summary')
    require(budget['exit_code'] == budget['worker_exit_code'] == 0
            and not budget['running'] and not budget['queued'], 'uncleared execution')
    limits = protocol['remaining_monitored_budget']
    require(limits['threads'] == limits['workers'] == 1, 'worker concurrency differs')
    require(abs(limits['cpu_seconds'] + protocol['cumulative_budget']['prior_allocated_cpu_seconds'] - 3600.) < 1e-9
            and abs(limits['wall_seconds'] + protocol['cumulative_budget']['prior_allocated_wall_seconds'] - 5400.)
            < 1e-9, 'cumulative package limits differ')
    require(budget['cap_cpu_seconds'] == limits['cpu_seconds']
            and budget['cap_wall_seconds'] == limits['wall_seconds']
            and budget['cap_rss_bytes'] == limits['rss_bytes']
            and budget['minimum_available_bytes'] == limits['minimum_available_bytes']
            and budget['worker_address_space_bytes'] == limits['address_space_bytes'], 'runtime limits differ')
    require(budget['cpu_seconds'] < budget['cap_cpu_seconds'] and budget['wall_seconds'] < budget['cap_wall_seconds']
            and budget['peak_owned_rss_bytes'] < budget['cap_rss_bytes']
            and budget['available_memory_bytes'] >= budget['minimum_available_bytes'], 'runtime bounds exceeded')
    cleanup = budget['terminal_cleanup']
    require(cleanup['same_pid_namespace'] and cleanup['all_owned_groups_exited']
            and cleanup['all_worker_identities_exited'] and not cleanup['remaining_descendants'], 'cleanup differs')
    raw = verify_raw(scheduled_rows(study, protocol))
    return dict(status='passed', archive_files=len(actual), protocol_sha256=protocol_sha,
                source_revision=protocol['source_revision'], planned_scientific_calls=6656,
                completed_scientific_calls=6656, completed_engineering_calls=40,
                summary_sha256=sha(study / 'summary.json'), row_index_sha256=sha(study / 'row_index.json'),
                raw_tar_sha256=sha(HERE / 'raw.tar.gz'), verifier_simulations=0, verifier_builds=0, **raw)


if __name__ == '__main__':
    print(json.dumps(verify(), indent=2))
