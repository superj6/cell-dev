"""Classify prospective seed references; no life, build, or genetic draw."""
import hashlib
import json
import re
from pathlib import Path

BASE = Path(__file__).resolve().parent
ROOT = BASE.parents[2]


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def main():
    data = json.loads((BASE / 'candidate_seed_inventory.json').read_text())
    assert not data['NPZ_matches'] and not data['NPZ_errors'] and not data['JSON_errors']
    assert data['native_seed'] == 53234
    assert len(set(data['run_life_seeds']['mixed'])) == 180
    assert data['whole_block_half_open'] == [52490000, 52500000]
    json_classes = []
    allowed = {'whole_blocks_half_open.1.1', 'seed_blocks.1.1', 'namespace.blocks_half_open.1.1'}
    for item in data['JSON_hits']:
        assert 'resource_patch_baseline_20261015' in item['path']
        assert item['value'] == 52490000 and item['field'] in allowed
        json_classes.append(dict(item, classification='exclusive upper endpoint of baseline block148'))
    text_classes = []
    for line in (BASE / 'candidate_text_matches.txt').read_text().splitlines():
        path, number, value = line.split(':', 2)
        residual = re.sub(r'(?<![0-9a-f])[0-9a-f]{64}(?![0-9a-f])', 'HASH', value)
        residual = re.sub(r'(?<![0-9])0\.532342', 'DECIMAL', residual)
        if 'resource_patch_baseline_20261015' in path and '52490000' in residual:
            kind = 'exclusive upper endpoint of baseline block148'
        elif not re.search(r'52[_,]?(?:49[0-9_,]*|500[0-9_,]*)|53[_,]?234|(?:block|fresh_seeds|reserve).{0,35}\b149\b', residual):
            kind = 'substring in retained hash or decimal statistic'
        else:
            raise ValueError('unclassified reference: ' + line)
        text_classes.append(dict(path=path, line=int(number), classification=kind))
    result = dict(status='passed', native_seed=53234, reserved=False,
        confirmation_seeds=data['candidate_seeds'], run_life_seeds=data['run_life_seeds'],
        whole_block_half_open=data['whole_block_half_open'], unique_native_ids=180,
        simulation_calls=0, engine_builds=0, genetic_draws=0,
        JSON_classification=json_classes, text_classification=text_classes,
        inventory_sha256=sha(BASE/'candidate_seed_inventory.json'),
        source_sha256=sha(Path(__file__)),
        source_audit_sha256=sha(BASE/'audit_namespace.py'),
        native_source_pins=data['native_source_pins'],
        historical_inventory_references=data['prior_inventory_pins'],
        scope='All recorded NPZ seed payloads and numeric JSON/text declarations; exact native schedule, no outcomes opened.',
        intentional_reuse='Native generation lives shared across candidates/recheck; final diagnostic IDs repeated at half duration; 512 confirmation IDs shared across three roles/five worlds; startup uses retained golden fixtures.')
    (BASE/'seed_audit.json').write_text(json.dumps(result,indent=2)+'\n')
    print(json.dumps(dict(status='passed',JSON_references=len(json_classes),text_references=len(text_classes),
                         unique_native_ids=180,confirmation_seeds=512,simulation_calls=0)))


if __name__ == '__main__':
    main()
