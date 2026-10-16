"""Read fixed inputs only; no simulator, build, identity probe or random draw."""
import hashlib
import json
import os
import resource
import sys
from pathlib import Path

resource.setrlimit(resource.RLIMIT_CPU, (8, 9))
resource.setrlimit(resource.RLIMIT_AS, (2 * 1024**3, 2 * 1024**3))
sys.dont_write_bytecode = True
STUDY = Path(__file__).resolve().parents[1]
ROOT = STUDY.parents[1]
sys.path.insert(0, str(ROOT))

import numpy as np
import torch
from omegaconf import OmegaConf

from src import checkpoint
from src.genome import Layout
from src.life import spec
from src.life.evaluate import LifeEvaluator


def read(path):
    return json.loads(path.read_text())


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def raw(value):
    return hashlib.sha256(value.tobytes()).hexdigest()


torch.set_num_threads(1)
p = read(STUDY / 'protocol.json')
assert sha(STUDY / 'protocol.json') == '6fb2a4f9744ff15377346bde4b2d7af42a7e12087e5f9d2d9cc622af7a5ee33f'
ready = read(STUDY / 'READY.json')
assert ready['status'] == 'prepared_not_released' and ready['protocol_sha256'] == sha(STUDY / 'protocol.json')
assert ready['planned_calls'] == 15524 and ready['new_lives'] == ready['builds'] == ready['random_draws'] == 0
assert not any((STUDY / name).exists() for name in ('release.json', 'execution', 'raw', 'build-cache'))
amendment = read(STUDY / 'reviews/root_runner_source_amendment.json')
for names, base in ((p['source_pins'], STUDY), (p['input_pins'], STUDY),
                    (p['production_pins'], ROOT), (p['original_input_pins'], ROOT)):
    for name, digest in names.items():
        assert sha(base / name) == digest, name
for name, digest in amendment['source_pins'].items():
    assert sha(STUDY / name) == digest, name
assert amendment['status'] == 'passed'
assert sha(STUDY / amendment['prior_review']) == amendment['prior_review_sha256']
reader = read(STUDY / 'reviews/reader_checks.json')
assert reader['status'] == 'passed' and reader['test_cases'] == 7
for name, digest in reader['files'].items():
    assert sha(STUDY / name) == digest

seeds = list(range(52510000, 52510032))
audit, reservation = (read(STUDY / name) for name in ('namespace/seed_audit.json', 'reservation.json'))
assert audit['status'] == 'passed' and audit['actual_seed_collisions'] == audit['unresolved_NPZ_errors'] == 0
assert reservation['status'] == 'reserved' and reservation['genetic_seed'] is None
assert p['seeds'] == audit['development_seeds'] == reservation['development_seeds'] == seeds
assert audit['whole_block_half_open'] == reservation['whole_block_half_open'] == [52510000, 52520000]
assert p['seed_audit_sha256'] == reservation['seed_audit_sha256'] == sha(STUDY / 'namespace/seed_audit.json')
assert p['reservation_sha256'] == sha(STUDY / 'reservation.json')
assert audit['inventory_sha256'] == sha(STUDY / 'namespace/candidate_seed_inventory.json')

prior = read(ROOT / 'results/resource_patch_selection_20261015/protocol.json')
assert p['worlds'] == prior['worlds'] and p['production_pins'] == prior['production_pins']
assert p['expected_numerical_identity'] == prior['expected_numerical_identity']
assert read(STUDY / 'inputs/startup_identity.json')['identity'] == p['expected_numerical_identity']
assert p['groups'] == ['G8', 'mean4', 'pareto4', 'AO']
assert list(p['worlds']) == ['patch', 'pool', 'persistent', 'blink80_20', 'transfer']
for name, record in p['worlds'].items():
    world = spec.World(**record['world'])
    spec.V6.validate_world(world)
    assert record['abi'] == 6 and record['ledger_columns'] == list(spec.V6.LEDGER)
    assert spec.V6.pack_world(world).tolist() == record['world_vector']
    assert world.T == 1024 and world.t_open == 0

manifest = read(STUDY / p['rows_input'])
matrix = np.load(STUDY / p['genome_input'], allow_pickle=False)
assert matrix.shape == (97, 875) and matrix.dtype == np.float32 and np.isfinite(matrix).all()
assert raw(matrix) == manifest['raw_sha256'] and len(manifest['rows']) == 97
layout, ao = Layout.load(STUDY / 'inputs/AO.json')
assert manifest['dims'] == layout.dims.__dict__
population_hashes, cached = {}, {}
for group, start, generation in (('G8', 0, 8), ('mean4', 32, 4), ('pareto4', 64, 4)):
    folder = STUDY / 'inputs/populations' / group
    public = read(folder / 'population.json')
    saved = checkpoint.load(folder / 'checkpoint.pt')
    checkpoint.validate(saved, OmegaConf.load(folder / 'config.yaml'), read(folder / 'determinism.json'))
    state = saved['state']
    decoded = np.stack([layout.from_dict(row).numpy() for row in public['genomes']])
    assert decoded.tobytes() == matrix[start:start+32].tobytes() == state['population'].numpy().tobytes()
    assert public['ids'] == state['ids'].tolist() == manifest['populations'][group]['native_ids']
    assert len(set(public['ids'])) == 32 and state['generation'] == generation
    metadata = manifest['populations'][group]
    assert sha(folder / 'population.json') == sha(ROOT / metadata['source'])
    assert sha(folder / 'checkpoint.pt') == sha(ROOT / metadata['checkpoint_source'])
    population_hashes[group] = raw(decoded)
    assert raw(decoded) == metadata['population_raw_sha256']
    for local, row in enumerate(manifest['rows'][start:start+32]):
        assert row['index'] == start+local and row['group'] == group and row['row'] == local
        assert row['native_id'] == public['ids'][local] and row['raw_sha256'] == raw(decoded[local])
        assert row['reported_endpoint'] == (local == metadata['reported_endpoint_row'])
    if group != 'G8':
        folder = STUDY / 'inputs/cached' / group
        endpoint = read(folder / 'endpoint_selection.json')
        lineage = [json.loads(line) for line in (folder / 'lineage.jsonl').read_text().splitlines()]
        assert lineage[-1]['survivors'] == public['ids'] and lineage[-1]['gen'] == 3
        assert sha(folder / 'g003.npz') == lineage[-1]['selection']['sha256'] == endpoint['selection_sha256']
        with np.load(folder / 'g003.npz', allow_pickle=False) as a:
            short, pick = a['shortlist'], a['pick']
            assert a['candidate_ids'][short[pick]].tolist() == public['ids']
            assert a['base_genomes'][short[pick]].tobytes() == decoded.tobytes()
            captures = np.concatenate((a['base_captures'][short], a['recheck_captures']), axis=1)[pick]
            fitness = np.concatenate((a['base_production_F'][short], a['recheck_production_F']), axis=1)[pick]
        pattern = np.asarray([0, 1, 0, 2] * 4)
        assert captures.shape == fitness.shape == (32, 16)
        objectives = np.column_stack([captures[:, pattern == d].mean(axis=1) for d in range(3)]
                                     + [fitness.mean(axis=1)])
        assert objectives.tolist() == endpoint['selection']['objectives']
        assert endpoint['rank'] == metadata['reported_endpoint_row']
        assert endpoint['id'] == public['ids'][endpoint['rank']]
        assert endpoint['genome_raw_sha256'] == raw(decoded[endpoint['rank']])
        cached[group] = {'rows': 32, 'lives_per_row': 16, 'domain_lives': [8, 4, 4],
                         'reported_endpoint_row': endpoint['rank'], 'reported_endpoint_id': endpoint['id']}
assert matrix[96].tobytes() == ao.numpy().tobytes()
assert raw(matrix[96]) == prior['references'][0]['raw_sha256'] == manifest['rows'][96]['raw_sha256']
assert manifest['rows'][96]['index'] == 96 and manifest['rows'][96]['group'] == 'AO'
assert manifest['rows'][96]['reported_endpoint'] and manifest['rows'][96]['row'] == 0
ao_public = read(ROOT / 'results/retained_depth_20261015/runs/balanced/population.json')
assert manifest['rows'][96]['native_id'] == ao_public['ids'][0]
assert matrix[96].tobytes() == layout.from_dict(ao_public['genomes'][0]).numpy().tobytes()

cfg = OmegaConf.load(STUDY / p['config_input'])
evaluator = LifeEvaluator(cfg, layout)
assert evaluator.fast and evaluator.extinct_charge and not evaluator.has_envelope
assert evaluator.abi.version == 6 and evaluator.T == 1024
assert p['research_lives'] == 97*5*32 == 15520 and p['startup_lives'] == 4 and p['total_calls'] == 15524
assert p['batches'] == 4*5 == 20 and p['genomes'] == 97 and p['genome_world_rows'] == 485
assert p['lives_per_genome_world'] == 32
assert p['runtime_budget'] == dict(cpu_seconds=2640, wall_seconds=1740, threads=2, workers=1,
    cleanup_margin_seconds=10, rss_bytes=4*1024**3, address_space_bytes=8*1024**3,
    minimum_available_bytes=4*1024**3)
assert p['package_budget'] == dict(cpu_seconds=2700, wall_seconds=1800,
    preparation_terminal_cpu_reserve=60, preparation_terminal_wall_reserve=60)
assert p['joint_diagnostic']['capture_scales'] == [19.046875, 16.029296875, 5.919921875]
assert p['joint_diagnostic']['fitness_weights'] == [.5, .25, .25] and not p['joint_diagnostic']['certified_winner']
receipt = dict(status='passed', protocol_sha256=sha(STUDY/'protocol.json'),
    source_amendment_sha256=sha(STUDY/'reviews/root_runner_source_amendment.json'),
    reader_checks_sha256=sha(STUDY/'reviews/reader_checks.json'),
    reviewer_source_sha256=sha(Path(__file__)), ready_sha256=sha(STUDY/'READY.json'),
    rows_manifest_sha256=sha(STUDY/p['rows_input']), matrix_file_sha256=sha(STUDY/p['genome_input']),
    matrix_raw_sha256=raw(matrix), population_raw_sha256=population_hashes, cached16_mapping=cached,
    pinned_files_checked={name: len(p[name]) for name in ('input_pins','source_pins','production_pins','original_input_pins')},
    ordered_genomes=97, unchanged_worlds=5, shared_development_seeds=32, research_lives=15520,
    startup_lives=4, planned_total_calls=15524, native_lives_executed=0, builds=0, random_draws=0,
    scope='Exact saved inputs, checkpoint order/IDs, cached16 mapping, unchanged world/prices, constructor-only scorer, pins and resource/count contract.',
    limitations='No numerical identity call, kernel build, simulation or fresh namespace scan; the already accepted collision receipt is hash-bound.')
with (STUDY/'reviews/actual_input_review.json').open('x') as stream:
    json.dump(receipt, stream, indent=2, allow_nan=False)
    stream.write('\n')
print(json.dumps({'status':'passed','protocol_sha256':receipt['protocol_sha256'],
                  'review_sha256':sha(STUDY/'reviews/actual_input_review.json')}))
