"""Classify the single completed block151 scan; no rescan, reservation, build or life."""
from __future__ import annotations

import hashlib
import json
import re
import resource
import time
from collections import Counter
from pathlib import Path

BASE = Path(__file__).resolve().parent
ROOT = BASE.parents[2]
LOW, HIGH = 52510000, 52520000
PLACEHOLDERS = {
    b'synthetic file-hash placeholder, not a genotype archive': 1,
    b'{\n  "frozen": "confirmation_genotypes.npz"\n}\n': 35,
    b'{\n  "altered": true\n}\n': 5,
    b'corrupt': 6,
    b'synthetic output; not a real numerical archive': 129,
    b'changed': 1,
}


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def read(path):
    return json.loads(Path(path).read_text())


def require(value, message):
    if not value:
        raise ValueError(message)


def numerical_hits(value):
    stack, hits = [value], []
    while stack:
        item = stack.pop()
        if isinstance(item, dict):
            stack.extend(item.values())
            stack.extend(item.keys())
        elif isinstance(item, list):
            stack.extend(item)
        elif isinstance(item, int) and not isinstance(item, bool) or isinstance(item, str) and item.isdecimal():
            if LOW <= int(item) < HIGH:
                hits.append(int(item))
    return hits


def main():
    started, cpu = time.monotonic(), time.process_time()
    data = read(BASE / 'candidate_seed_inventory.json')
    require(not (BASE / 'seed_audit.json').exists(), 'first literal classification only')
    require(data['status'] == 'pending_literal_classification' and not data['reserved']
            and data['whole_block_half_open'] == [LOW, HIGH]
            and data['candidate_seeds'] == list(range(LOW, LOW+32)), 'exact development candidate')
    require(not data['NPZ_matches'] and not data['JSON_errors'], 'no collision or unreadable JSON allowed')
    prior, historical = {}, data['prior_inventory_pins']
    for name, digest in historical.items():
        require(sha(ROOT / name) == digest, 'historical inventory changed')
        value = read(ROOT / name)
        prior.update(value.get('changed_npz_records', value.get('new_or_modified_npz_records', value.get('records', {}))))
    classified_errors, counts = [], Counter()
    for item in data['NPZ_errors']:
        path = item['path']
        old, current = prior[path], data['changed_npz_records'][path]
        require(item['synthetic_fixture'] and old.get('synthetic_fixture') and old.get('error')
                and old['stat'] == current['stat']
                and any(part.startswith('test_') for part in Path(path).parts),
                'unreadable file is not an unchanged prior synthetic fixture: ' + path)
        raw = (ROOT / path).read_bytes()
        require(raw in PLACEHOLDERS, 'unclassified unreadable payload: ' + path)
        counts[raw] += 1
        classified_errors.append(dict(path=path, sha256=hashlib.sha256(raw).hexdigest(), bytes=len(raw),
            prior_stat=current['stat'], classification='unchanged literal synthetic placeholder/corruption fixture; no seed payload'))
    require(dict(counts) == PLACEHOLDERS and len(classified_errors) == 177, 'exact known fixture coverage')
    json_classes = []
    prefixes = ('outputs/resource_patch_selection_20261015/',
                'outputs/resource_patch_selection_terminal_stage_20261015/',
                'results/resource_patch_selection_20261015/')
    allowed = {'whole_block_half_open.1', 'seed_blocks.0.1', 'checks.namespace.block_half_open.1'}
    for name, digest in data['JSON_source_pins'].items():
        require(sha(ROOT / name) == digest, 'JSON declaration changed')
    for item in data['JSON_hits']:
        require(item['path'].startswith(prefixes) and item['value'] == LOW and item['field'] in allowed,
                'unclassified JSON declaration')
        json_classes.append(dict(item, classification='exclusive upper endpoint of preceding block150'))
    require(len(json_classes) == 24, 'exact JSON hit coverage')
    require(sha(BASE / 'candidate_text_matches.txt') == data['text_matches_sha256'], 'retained text hits changed')
    text_classes, text_pins = [], {}
    for line in (BASE / 'candidate_text_matches.txt').read_text().splitlines():
        path, number, source = line.split(':', 2)
        number = int(number)
        actual = (ROOT / path).read_text().splitlines()[number-1]
        require(actual == source, 'text declaration changed')
        text_pins[path] = sha(ROOT / path)
        if path.startswith(prefixes) and '52500000,52510000' in source.replace(' ', ''):
            kind = 'preceding block150 has exclusive upper endpoint52510000'
        elif path.startswith(prefixes) and '/namespace/audit_namespace.py' in path and '|52510000|53235|' in source:
            kind = 'preceding candidate audit search pattern, not an assignment'
        elif path.endswith('/archive_operational.py') and source.strip() == 'assert len(preserved) == 151':
            kind = 'count of preserved artifacts, not a seed block'
        elif path == 'outputs/openhr/switching/summary.md' and 'Lives: block 151, 1024 core / 512 secondary' in source:
            kind = 'older43million-base block151 means44510000..44511023; disjoint'
        elif path.endswith(('/atlas/atlas.html', '/atlas/atlas_play.html')):
            match = re.fullmatch(r'<script type="application/json" id="atlas-data">(.*)</script>', source)
            require(match is not None, 'known embedded atlas JSON syntax required')
            require(not numerical_hits(json.loads(match.group(1))), 'actual candidate ID in embedded atlas JSON')
            kind = 'comma-separated small array indices matched formatting regex; no actual candidate integer'
        else:
            raise ValueError('unclassified text reference: ' + path + ':' + str(number))
        text_classes.append(dict(path=path, line=number, classification=kind))
    require(len(text_classes) == 32, 'exact text coverage')
    chain = ('outputs/openhr/harness/harness.py', 'outputs/openhr/switching/swlib.py',
             'outputs/openhr/switching/score2.py', 'src/life/analysis.py')
    require('SEED_BASE = 43_000_000' in (ROOT / chain[0]).read_text()
            and 'SEED_BASE + 10_000 * block' in (ROOT / chain[0]).read_text()
            and 'return H.seeds(n, block, first)' in (ROOT / chain[1]).read_text()
            and 'flip_mix=151' in (ROOT / chain[2]).read_text()
            and 'return [seed0 + s for s in range(first, lives)]' in (ROOT / chain[3]).read_text(),
            'old block label numerical source chain differs')
    require(43_000_000 + 10_000*151 + 1024 < LOW, 'older actual seed range overlaps')
    result = dict(status='passed', reserved=False, registered=False, development_seeds=list(range(LOW,LOW+32)),
        whole_block_half_open=[LOW,HIGH], source_revision=data['source_revision'],
        inventory_sha256=sha(BASE / 'candidate_seed_inventory.json'), source_sha256=sha(Path(__file__)),
        source_audit_sha256=sha(BASE / 'audit_namespace.py'),
        historical_inventory_references=historical, classified_legacy_fixture_errors=classified_errors,
        unresolved_NPZ_errors=0, original_NPZ_error_count=177, actual_seed_collisions=0,
        JSON_classification=json_classes, text_classification=text_classes, text_source_pins=text_pins,
        older_label_source_pins={name:sha(ROOT / name) for name in chain},
        simulation_calls=0, engine_builds=0, genetic_draws=0,
        scope='Actual recorded NPZ seed payloads and numeric JSON/embedded-JSON declarations, plus literal text review.',
        intentional_reuse='All97 fixed rows/five worlds share32 new development seeds; startup alone replays retained fixtures.',
        resources=dict(cpu_seconds=time.process_time()-cpu, wall_seconds=time.monotonic()-started,
                       peak_rss_bytes=resource.getrusage(resource.RUSAGE_SELF).ru_maxrss*1024))
    with (BASE / 'seed_audit.json').open('x') as stream:
        json.dump(result,stream,indent=2);stream.write('\n')
    print(json.dumps(dict(status='passed', development_seeds=32, actual_seed_collisions=0,
        classified_legacy_fixture_errors=177, JSON_references=24, text_references=32,
        reserved=False, simulation_calls=0, resources=result['resources'])))


if __name__ == '__main__':
    main()
