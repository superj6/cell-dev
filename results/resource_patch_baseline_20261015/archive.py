"""Publish/verify completed baseline evidence without builds or new lives."""
import argparse
import hashlib
import json
import shutil
from pathlib import Path

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[1]
PUBLIC = ROOT/'results/resource_patch_baseline_20261015'
SUFFIXES = {'.py', '.json', '.md', '.txt', '.log', '.csv', '.npy', '.npz'}
EXCLUDE = {'build-cache', '__pycache__', '.pytest_cache', 'tmp'}


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def read(path):
    return json.loads(path.read_text())


def verify(folder, archive_only=False):
    manifest = read(folder/'manifest.json')
    files = {str(p.relative_to(folder)): p for p in folder.rglob('*') if p.is_file()}
    assert set(files) == set(manifest['artifacts']) | {'manifest.json'}, 'archive file set'
    for name, item in manifest['artifacts'].items():
        assert files[name].stat().st_size == item['bytes'] and sha(files[name]) == item['sha256'], name
    protocol = read(folder/'protocol.json')
    complete, budget = read(folder/'measurement_complete.json'), read(folder/'budget.json')
    assert complete['status'] == budget['status'] == 'complete'
    assert complete['backend_calls'] == 456 and complete['scientific_lives'] == 448
    assert budget['terminal_cleanup']['all_owned_groups_exited']
    assert budget['terminal_cleanup']['all_worker_identities_exited']
    assert not budget['running'] and not budget['queued']
    index = read(folder/'row_index.json')
    assert len(index) == 456 and {str(p.relative_to(folder)) for p in (folder/'raw').glob('*.npz')} == set(index)
    for name, item in index.items():
        assert sha(folder/name) == item['sha256'], name
    assert complete['summary_sha256'] == sha(folder/'summary.json')
    assert complete['per_life_sha256'] == sha(folder/'per_life.csv')
    assert complete['protocol_sha256'] == sha(folder/'protocol.json')
    for name, digest in protocol['production_pins'].items():
        assert sha(folder/'production'/name) == digest, name
        if not archive_only:
            assert sha(ROOT/name) == digest, name
    return dict(status='passed', artifacts=len(manifest['artifacts']), raw_rows=456,
                manifest_sha256=sha(folder/'manifest.json'), simulations=0, builds=0)


def publish():
    assert not PUBLIC.exists(), 'fresh destination required'
    protocol = read(HERE/'protocol.json')
    assert read(HERE/'measurement_complete.json')['status'] == 'complete'
    assert read(HERE/'budget.json')['status'] == 'complete'
    for required in ('README.md', 'REPORT.md', 'reviews/independent_accounting.json'):
        assert (HERE/required).is_file(), required
    selected = {str(p.relative_to(HERE)): p for p in HERE.rglob('*')
                if p.is_file() and p.suffix in SUFFIXES and not EXCLUDE.intersection(p.relative_to(HERE).parts)}
    selected.pop('manifest.json', None)
    for name, digest in protocol['production_pins'].items():
        assert sha(ROOT/name) == digest, name
        selected['production/'+name] = ROOT/name
    PUBLIC.mkdir()
    for name, source in selected.items():
        destination = PUBLIC/name
        destination.parent.mkdir(parents=True, exist_ok=True)
        shutil.copyfile(source, destination)
    records = {name: dict(sha256=sha(PUBLIC/name), bytes=(PUBLIC/name).stat().st_size) for name in sorted(selected)}
    (PUBLIC/'manifest.json').write_text(json.dumps(dict(status='complete', artifacts=records), indent=2)+'\n')
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
