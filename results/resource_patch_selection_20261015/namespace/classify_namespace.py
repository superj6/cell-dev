"""Classify exact prospective seed references; no build, life or random draw."""
import hashlib
import json
from pathlib import Path

BASE = Path(__file__).resolve().parent
ROOT = BASE.parents[2]


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def main():
    data = json.loads((BASE / 'candidate_seed_inventory.json').read_text())
    assert not data['NPZ_matches'] and not data['NPZ_errors'] and not data['JSON_errors']
    assert data['native_seed'] == 53235 and data['whole_block_half_open'] == [52500000, 52510000]
    assert set(data['run_life_seeds']) == {'mean', 'pareto'}
    assert data['run_life_seeds']['mean'] == data['run_life_seeds']['pareto']
    assert len(set(data['run_life_seeds']['mean'])) == 100
    allowed = {'whole_block_half_open.1', 'namespace.block_half_open.1', 'seed_blocks.0.1'}
    json_classes = []
    for item in data['JSON_hits']:
        assert 'resource_patch_evolution' in item['path']
        assert item['value'] == 52500000 and item['field'] in allowed
        json_classes.append(dict(item, classification='exclusive upper endpoint of preceding block149'))
    text_classes = []
    for line in (BASE / 'candidate_text_matches.txt').read_text().splitlines():
        path, number, value = line.split(':', 2)
        if 'resource_patch_evolution' in path and '52490000, 52500000' in value:
            kind = 'preceding block149 has exclusive upper endpoint52500000'
        elif ('resource_patch_evolution' in path and '/namespace/audit_namespace.py' in path
              and '5249[0-9]{4}|52500000|53234|' in value):
            kind = 'previous audit search pattern, not a seed assignment'
        elif 'resource_patch_evolution' in path and path.endswith('/TABLES.md') and '0.105250' in value:
            kind = 'decimal standard error substring in completed table'
        elif path == 'outputs/openhr/switching/summary.md' and 'Lives: block 150, 1024 core' in value:
            kind = 'older harness block150 uses43million base:44500000..44501023, disjoint'
        else:
            raise ValueError('unclassified reference: ' + line)
        text_classes.append(dict(path=path, line=int(number), classification=kind))
    # Bind the inspected chain for the older, differently based block label.
    files = ('outputs/openhr/harness/harness.py', 'outputs/openhr/switching/swlib.py',
             'outputs/openhr/switching/score2.py', 'src/life/analysis.py')
    harness = (ROOT / files[0]).read_text()
    assert 'SEED_BASE = 43_000_000' in harness and 'SEED_BASE + 10_000 * block' in harness
    assert 'return H.seeds(n, block, first)' in (ROOT / files[1]).read_text()
    assert 'flip_mid=150' in (ROOT / files[2]).read_text()
    assert 'return [seed0 + s for s in range(first, lives)]' in (ROOT / files[3]).read_text()
    assert 43_000_000 + 10_000 * 150 + 1024 < 52500000
    result = dict(status='passed', native_seed=53235, reserved=False,
        confirmation_seeds=data['candidate_seeds'], run_life_seeds=data['run_life_seeds'],
        whole_block_half_open=data['whole_block_half_open'], unique_native_ids=100,
        simulation_calls=0, engine_builds=0, genetic_draws=0,
        JSON_classification=json_classes, text_classification=text_classes,
        inventory_sha256=sha(BASE / 'candidate_seed_inventory.json'),
        source_sha256=sha(Path(__file__)), source_audit_sha256=sha(BASE / 'audit_namespace.py'),
        native_source_pins=data['native_source_pins'],
        historical_inventory_references=data['prior_inventory_pins'],
        older_label_source_pins={name: sha(ROOT / name) for name in files},
        scope='All recorded NPZ seed payloads plus JSON/text declarations; exact native schedule; no outcome arrays read.',
        intentional_reuse='Native schedule shared across both search arms and candidates; final diagnostic IDs repeated at half duration;512 confirmation IDs shared across4roles/5worlds; startup uses retained golden fixtures.')
    (BASE / 'seed_audit.json').write_text(json.dumps(result, indent=2) + '\n')
    print(json.dumps(dict(status='passed', JSON_references=len(json_classes), text_references=len(text_classes),
                         unique_native_ids=100, confirmation_seeds=512, simulation_calls=0)))


if __name__ == '__main__':
    main()
