"""Publish a prospective, source-bound study; never execute a life."""
import hashlib
import json
import shutil
from pathlib import Path

SOURCE = Path(__file__).resolve().parent
ROOT = SOURCE.parents[1]
TARGET = ROOT / 'results/resource_patch_selection_20261015'


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def main():
    protocol = json.loads((SOURCE/'protocol.json').read_text())
    review = json.loads((SOURCE/'reviews/actual_input_review.json').read_text())
    assert review['status'] == 'passed'
    assert review['protocol_sha256'] == sha(SOURCE/'protocol.json')
    assert protocol['total_calls'] == 30808
    assert (SOURCE/'README.md').is_file()
    assert not any((SOURCE/name).exists() for name in ('attempt.json','raw','runs'))
    TARGET.mkdir(exist_ok=False)
    for path in SOURCE.iterdir():
        if path.is_file() and path.suffix in ('.py','.json','.md','.txt','.log'):
            shutil.copy2(path,TARGET/path.name)
    for name in ('inputs','configs','namespace','reviews','source_checks','preparation_history','tests'):
        if (SOURCE/name).exists():
            shutil.copytree(SOURCE/name,TARGET/name,ignore=shutil.ignore_patterns('__pycache__','*.pyc'))
    previous = json.loads((ROOT/'results/delayed_match_evolution_20261015/namespace_references.json').read_text())
    by_sha = {item['sha256']:item['public_path'] for item in previous}
    for name in ('results/retained_depth_20261015/new_prepare_prep/candidate_seed_inventory.json',
                 'results/delayed_match_baseline_20261015/candidate_seed_inventory.json',
                 'results/delayed_match_information_20261015/candidate_seed_inventory.json',
                 'results/delayed_match_evolution_20261015/namespace/candidate_seed_inventory.json',
                 'results/resource_patch_baseline_20261015/namespace/candidate_seed_inventory.json',
                 'results/resource_patch_evolution_20261015/namespace/candidate_seed_inventory.json'):
        if (ROOT/name).exists():
            by_sha[sha(ROOT/name)] = name
    references = []
    audit = json.loads((SOURCE/'namespace/seed_audit.json').read_text())
    for original,digest in audit['historical_inventory_references'].items():
        if digest not in by_sha:
            # Prior archives occasionally used a different enclosing review directory.
            matches = [p for p in (ROOT/'results').rglob(Path(original).name) if p.is_file() and sha(p)==digest]
            if not matches:
                raise ValueError('no public historical inventory: '+original)
            by_sha[digest] = str(matches[0].relative_to(ROOT))
        references.append(dict(original_path=original,public_path=by_sha[digest],sha256=digest))
    (TARGET/'namespace_references.json').write_text(json.dumps(references,indent=2)+'\n')
    manifest = dict(status='prospective',scientific_calls=0,planned_calls=30808,
                    protocol_sha256=sha(TARGET/'protocol.json'),files={})
    for path in sorted(TARGET.rglob('*')):
        if path.is_file() and path!=TARGET/'manifest.json':
            manifest['files'][str(path.relative_to(TARGET))]=dict(sha256=sha(path),bytes=path.stat().st_size)
    (TARGET/'manifest.json').write_text(json.dumps(manifest,indent=2)+'\n')
    print(json.dumps(dict(status='published',files=len(manifest['files']),simulator_calls=0)))


if __name__ == '__main__':
    main()
