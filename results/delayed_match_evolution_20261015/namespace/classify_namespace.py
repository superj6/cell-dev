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
    assert data['native_seed'] == 53233
    assert len(set(data['run_life_seeds']['mixed'])) == 500
    assert data['whole_block_half_open'] == [52460000, 52470000]
    json_classes = []
    for item in data['JSON_hits']:
        assert 'delayed_match_information_20261015' in item['path']
        assert item['value'] == 52460000
        assert item['field'] in ('whole_block_half_open.1', 'whole_blocks_half_open.1.1')
        json_classes.append(dict(item, classification='exclusive upper endpoint of information-study block145'))
    text_classes = []
    for line in (BASE / 'candidate_text_matches.txt').read_text().splitlines():
        path, number, value = line.split(':', 2)
        residual = re.sub(r'(?<![0-9a-f])[0-9a-f]{64}(?![0-9a-f])', 'HASH', value)
        residual = re.sub(r'(?<![0-9])(?:0)?\.52466', 'DECIMAL', residual)
        if path == 'outputs/delayed_match_information_20261015/next_recommendation.md' and ('53233' in residual or '146' in residual):
            kind = 'source-only recommendation for this same unregistered candidate'
        elif 'delayed_match_information_20261015' in path and '52460000' in residual:
            kind = 'exclusive upper endpoint of information-study blocks144/145'
        elif not re.search(r'52[_,]?(?:46[0-9_,]*|470[0-9_,]*)|53[_,]?233|(?:block|fresh_seeds|reserve).{0,35}\b146\b', residual):
            kind = 'substring in retained hash or decimal statistic'
        else:
            raise ValueError('unclassified reference: ' + line)
        text_classes.append(dict(path=path,line=int(number),classification=kind))
    result = dict(status='passed', native_seed=53233, reserved=False,
        confirmation_seeds=data['candidate_seeds'], run_life_seeds=data['run_life_seeds'],
        whole_block_half_open=data['whole_block_half_open'], unique_native_ids=500,
        simulation_calls=0, engine_builds=0, genetic_draws=0,
        JSON_classification=json_classes, text_classification=text_classes,
        inventory_sha256=sha(BASE/'candidate_seed_inventory.json'),
        source_sha256=sha(Path(__file__)),
        source_audit_sha256=sha(BASE/'audit_namespace.py'),
        native_source_pins=data['native_source_pins'],
        historical_inventory_references=data['prior_inventory_pins'],
        scope='All recorded NPZ seed payloads and numeric JSON/text declarations; exact native schedule, no outcomes opened.',
        intentional_reuse='Native generation lives shared across candidates/recheck; final diagnostic IDs repeated at half duration; 512 confirmation IDs shared across four roles/seven worlds; startup uses retained golden fixtures.')
    (BASE/'seed_audit.json').write_text(json.dumps(result,indent=2)+'\n')
    print(json.dumps(dict(status='passed',JSON_references=len(json_classes),text_references=len(text_classes),
                         unique_native_ids=500,confirmation_seeds=512,simulation_calls=0)))


if __name__ == '__main__':
    main()
