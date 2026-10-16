"""Publish/verify the saved-data-recovered modulation diagnostic; never build or simulate."""
import argparse
import csv
import hashlib
import json
import shutil
from collections import Counter
from pathlib import Path

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[1]
PUBLIC = ROOT / 'results/resource_patch_modulation_20261015'
SUFFIXES = {'.py', '.c', '.json', '.md', '.txt', '.log', '.csv', '.npy', '.npz', '.diff'}
EXCLUDE = {'build-cache', '__pycache__', '.pytest_cache', 'tmp'}


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def read(path):
    return json.loads(path.read_text())


def verify(folder, archive_only=False):
    manifest = read(folder / 'manifest.json')
    files = {str(p.relative_to(folder)): p for p in folder.rglob('*') if p.is_file()}
    assert set(files) == set(manifest['artifacts']) | {'manifest.json'}, 'archive file set'
    for name, item in manifest['artifacts'].items():
        assert files[name].stat().st_size == item['bytes'] and sha(files[name]) == item['sha256'], name
    protocol, recovery = read(folder / 'protocol.json'), read(folder / 'terminal_recovery.json')
    complete, budget = read(folder / 'measurement_complete.json'), read(folder / 'budget.json')
    assert complete['status'] == 'invalid' and budget['status'] == 'incomplete'
    assert complete['started_calls'] == complete['returned_calls'] == 148
    assert complete['error'] == "TypeError: dict() got multiple values for keyword argument 'path'"
    assert budget['reason'] == 'worker_failed' and budget['worker_exit_code'] == 1
    assert recovery['status'] == 'complete_saved_data_recovery'
    assert recovery['new_backend_calls'] == recovery['new_builds'] == recovery['new_random_draws'] == 0
    assert recovery['original_returned_calls'] == 148 and recovery['original_scientific_calls'] == 128
    assert recovery['original_engineering_calls'] == 20 and recovery['reused_native_scientific_rows'] == 64
    assert recovery['reused_native_engineering_rows'] == 8 and recovery['combined_csv_rows'] == 212
    assert recovery['engineering_checks_passed'] and recovery['production_pins_unchanged']
    bindings = {'protocol_sha256': 'protocol.json', 'original_measurement_sha256': 'measurement_complete.json',
        'original_budget_sha256': 'budget.json', 'row_index_sha256': 'row_index.json',
        'analyzer_sha256': 'analyze_terminal.py', 'wrapper_sha256': 'terminal_read.py',
        'amendment_sha256': 'terminal_recovery/amendment.json',
        'review_sha256': 'terminal_recovery/source_review.json', 'summary_sha256': 'summary.json',
        'per_life_sha256': 'per_life.csv'}
    for key, name in bindings.items():
        assert recovery[key] == sha(folder / name), key
    assert complete['protocol_sha256'] == budget['protocol_sha256'] == recovery['protocol_sha256']
    release = read(folder / 'release.json')
    assert release['status'] == 'released' and release['protocol_sha256'] == recovery['protocol_sha256']
    assert budget['release_sha256'] == sha(folder / 'release.json')
    assert budget['attempt_sha256'] == sha(folder / 'attempt.json')
    cleanup = budget['terminal_cleanup']
    assert cleanup['same_pid_namespace'] and cleanup['all_owned_groups_exited']
    assert cleanup['all_worker_identities_exited'] and not cleanup['remaining_descendants']
    assert not budget['running'] and not budget['queued']
    assert budget['cpu_seconds'] < 510 and budget['wall_seconds'] < 1080
    assert budget['peak_owned_rss_bytes'] < 2*1024**3
    resources = recovery['resources']
    assert resources['cpu_seconds'] < 30 and resources['wall_seconds'] < 60
    assert resources['peak_rss_bytes'] < 2*1024**3
    amendment = read(folder / 'terminal_recovery/amendment.json')
    for name, digest in amendment['original_evidence'].items():
        assert sha(folder / name) == sha(folder / 'terminal_recovery/original' / name) == digest, name
    before, after = (folder / 'analyze.py').read_text(), (folder / 'analyze_terminal.py').read_text()
    old = "backend=item['backend'], path=item['path'], origin=origin,"
    new = "backend=item['backend'], raw_path=item['path'], origin=origin,"
    assert before.count(old) == 1 and before.replace(old, new) == after
    index = read(folder / 'row_index.json')
    assert len(index) == len(protocol['schedule']) == 148
    assert {str(p.relative_to(folder)) for p in (folder / 'raw').glob('*.npz')} == set(index)
    assert Counter(x['group'] for x in protocol['schedule']) == {
        'native_equivalence': 8, 'constant_parity': 12, 'science': 128}
    for item in protocol['schedule']:
        row = index[item['path']]
        assert all(row[k] == v for k, v in item.items())
        assert sha(folder / item['path']) == row['sha256'], item['path']
    reuse = read(folder / 'inputs/reuse.json')
    assert len(reuse['native_rows']) == 64 and len(reuse['engineering_rows']) == 8
    reused = reuse['native_rows'] + reuse['engineering_rows']
    assert {str(p.relative_to(folder)) for p in (folder / 'inputs/baseline_rows').glob('*.npz')} == {
        x['copied_path'] for x in reused}
    for item in reused:
        assert sha(folder / item['copied_path']) == item['sha256']
    with (folder / 'per_life.csv').open(newline='') as stream:
        rows = list(csv.DictReader(stream))
    assert len(rows) == 212 and Counter(r['origin'] for r in rows) == {'new': 148, 'reused_baseline': 64}
    assert sum(r['group'] == 'science' for r in rows) == 192
    assert all('raw_path' in r and 'path' in r for r in rows)
    summary = read(folder / 'summary.json')
    assert summary['status'] == 'complete' and summary['valid'] and summary['engineering_checks_passed']
    assert summary['new_backend_calls'] == 148 and summary['new_scientific_lives'] == 128
    assert summary['new_engineering_lives'] == 20 and summary['reused_scientific_lives'] == 64
    assert summary['combined_scientific_rows'] == 192 and sum(summary['status_counts'].values()) == 212
    assert summary['new_native_ledger_values'] == 148*107 and summary['new_native_hash_values'] == 148*5
    assert summary['protocol_sha256'] == recovery['protocol_sha256']
    assert summary['row_index_sha256'] == recovery['row_index_sha256']
    audit = read(folder / 'reviews/independent_accounting.json')
    assert audit['status'] == 'passed' and audit['protocol_sha256'] == recovery['protocol_sha256']
    assert audit['terminal_recovery_verified'] and audit['original_failed_markers_preserved']
    assert audit['new_rows'] == 148 and audit['unique_raw_rows_audited'] == 220 and audit['csv_rows'] == 212
    for name, digest in audit['artifacts'].items():
        assert sha(folder / name) == digest, name
    for mode in ('native', 'constant1', 'constant055'):
        for speed in ('full', 'fast'):
            stem = folder / 'compiler_diagnostics' / f'{mode}_{speed}'
            assert read(Path(str(stem) + '.result.json'))['returncode'] == 0
            for suffix in ('.command.json', '.stdout.txt', '.stderr.txt'):
                assert Path(str(stem) + suffix).is_file()
    for key in ('source_pins', 'input_pins'):
        for name, digest in protocol[key].items():
            assert sha(folder / name) == digest, name
    for name, digest in protocol['production_pins'].items():
        assert sha(folder / 'production' / name) == digest, name
        if not archive_only:
            assert sha(ROOT / name) == digest, name
    return dict(status='passed', artifacts=len(manifest['artifacts']), new_raw_rows=148,
        new_scientific_calls=128, new_engineering_calls=20, reused_scientific_rows=64,
        reused_engineering_rows=8, csv_rows=212, original_attempt_status='incomplete',
        recovery_status=recovery['status'], manifest_sha256=sha(folder / 'manifest.json'), simulations=0, builds=0)


def publish():
    assert not PUBLIC.exists(), 'fresh destination required'
    protocol = read(HERE / 'protocol.json')
    assert read(HERE / 'terminal_recovery.json')['status'] == 'complete_saved_data_recovery'
    for required in ('README.md', 'REPORT.md', 'reviews/independent_accounting.json'):
        assert (HERE / required).is_file(), required
    selected = {str(p.relative_to(HERE)): p for p in HERE.rglob('*')
                if p.is_file() and p.suffix in SUFFIXES and not EXCLUDE.intersection(p.relative_to(HERE).parts)}
    selected.pop('manifest.json', None)
    for name, digest in protocol['production_pins'].items():
        assert sha(ROOT / name) == digest, name
        selected['production/' + name] = ROOT / name
    PUBLIC.mkdir()
    for name, source in selected.items():
        destination = PUBLIC / name
        destination.parent.mkdir(parents=True, exist_ok=True)
        shutil.copyfile(source, destination)
    records = {name: dict(sha256=sha(PUBLIC / name), bytes=(PUBLIC / name).stat().st_size) for name in sorted(selected)}
    (PUBLIC / 'manifest.json').write_text(json.dumps(dict(status='complete_saved_data_recovery', artifacts=records),
                                                  indent=2) + '\n')
    print(json.dumps(verify(PUBLIC), indent=2))


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--publish', action='store_true')
    parser.add_argument('--verify', action='store_true')
    parser.add_argument('--archive-only', action='store_true')
    args = parser.parse_args()
    if args.publish:
        publish()
    elif args.verify:
        print(json.dumps(verify(HERE, args.archive_only), indent=2))
    else:
        print('No publication or simulation requested.')
