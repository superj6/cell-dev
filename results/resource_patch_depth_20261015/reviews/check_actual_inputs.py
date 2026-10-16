"""One bounded saved-input review; no simulator, build, identity probe or random draw."""
import copy
import hashlib
import json
import resource
import sys
from pathlib import Path

resource.setrlimit(resource.RLIMIT_CPU, (10, 10))
resource.setrlimit(resource.RLIMIT_AS, (8 * 1024**3, 8 * 1024**3))
sys.dont_write_bytecode = True
STUDY = Path(__file__).resolve().parents[1]
ROOT = STUDY.parents[1]
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(STUDY))

import numpy as np
import torch
from omegaconf import OmegaConf

from population_loader import loader_identity
from selection import selection_identity
from src import checkpoint
from src.genome import Layout
from src.life import spec
from src.life.evaluate import LifeEvaluator, life_seed


def read(path):
    return json.loads(path.read_text())


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def raw(value):
    return hashlib.sha256(value.tobytes()).hexdigest()


torch.set_num_threads(1)
p = read(STUDY / 'protocol.json')
protocol_sha = sha(STUDY / 'protocol.json')
assert protocol_sha == '86593f759c5c17823d4eaff19800728229f757eb2ffc82b2f54660e9b32653bb'
ready = read(STUDY / 'READY.json')
assert ready == dict(status='prepared_not_released', protocol_sha256=protocol_sha,
    source_revision='1a7f38bd3222bacf27367fd99998d87776c34ec5', planned_calls=97342,
    new_lives=0, builds=0, random_draws=0)
assert p['preparation_lives'] == p['preparation_builds'] == p['preparation_random_draws'] == 0
runtime_artifacts = ('release.json', 'execution', 'runs', 'raw', 'scored', 'endpoint_raw',
    'endpoint_scored', 'startup.json', 'row_index.json', 'endpoint_index.json', 'measurement_complete.json',
    'study_complete.json', 'budget.json', 'build-cache', 'joint_genome.json', 'summary.json')
assert not any((STUDY / name).exists() for name in runtime_artifacts)
for key, base in (('source_pins', STUDY), ('input_pins', STUDY),
                  ('production_pins', ROOT), ('original_input_pins', ROOT)):
    for name, digest in p[key].items():
        assert (base / name).resolve().is_relative_to(base.resolve()) and sha(base / name) == digest, name
review_names = ('prepare_source_review.json', 'adapter_checks.json',
                'readers_source_review.json', 'runner_source_review.json')
for name in review_names:
    review = read(STUDY / 'reviews' / name)
    assert review['status'] in ('passed', 'passed_source_review')
    for source, digest in review['source_pins'].items():
        assert sha(STUDY / source) == digest, (name, source)

audit, reservation = (read(STUDY / name) for name in ('namespace/seed_audit.json', 'reservation.json'))
audit_receipt = read(STUDY / 'namespace/audit_receipt.json')
assert audit['status'] == 'passed' and not audit['reserved'] and not audit['registered']
assert audit_receipt['status'] == 'passed_unreserved' and audit_receipt['actual_seed_collisions'] == 0
for name, digest in audit_receipt['artifact_pins'].items():
    assert sha(STUDY / 'namespace' / name) == digest, name
assert reservation['status'] == 'reserved' and reservation['simulated_lives'] == 0
assert p['seed_audit_sha256'] == reservation['seed_audit_sha256'] == sha(STUDY / 'namespace/seed_audit.json')
assert p['reservation_sha256'] == sha(STUDY / 'reservation.json')
assert p['native_seed'] == audit['native_seed'] == reservation['native_seed'] == 53236
native_seeds = []
for g in range(8):
    native_seeds += [life_seed(53236, 'gen', g, i) for i in range(64)]
    if g in (0, 4, 7):
        native_seeds += [life_seed(53236, 'valid', g, i) for i in range(16)]
native_seeds += [life_seed(53236, 'final', g, i) for g in range(2) for i in range(2)]
assert len(set(native_seeds)) == audit['unique_native_ids'] == 564
assert p['native_life_seeds'] == audit['native_life_seeds'] == reservation['native_life_seeds'] == native_seeds
for key, values in (('endpoint_seeds', list(range(52520000, 52520032))),
                    ('confirmation_seeds', list(range(52530000, 52530512)))):
    assert p[key] == audit[key] == reservation[key] == values
assert not set(p['endpoint_seeds']) & set(p['confirmation_seeds'])
assert not set(native_seeds) & set(p['endpoint_seeds'] + p['confirmation_seeds'])
assert audit['seed_blocks'] == reservation['seed_blocks'] == [[52520000, 52530000], [52530000, 52540000]]

panel = ROOT / 'results/resource_patch_population_20261015'
prior = read(panel / 'protocol.json')
prior_rows = read(panel / 'inputs/rows.json')
prior_matrix = np.load(panel / 'inputs/genomes.npy', allow_pickle=False)
prior_summary = read(panel / 'summary.json')
assert raw(prior_matrix) == prior_rows['raw_sha256']
for archive in (panel, ROOT / 'results/resource_patch_selection_20261015'):
    manifest = read(archive / 'manifest.json')
    assert manifest['status'] == 'complete'
    for source, digest in p['original_input_pins'].items():
        path = ROOT / source
        if path.is_relative_to(archive) and path.name != 'manifest.json':
            pin = manifest['files'][str(path.relative_to(archive))]
            assert pin['sha256'] == digest and pin['bytes'] == path.stat().st_size
assert p['production_pins'] == prior['production_pins']
assert p['expected_numerical_identity'] == prior['expected_numerical_identity']
assert read(STUDY / 'inputs/startup_identity.json')['identity'] == p['expected_numerical_identity']

layout, _ = Layout.load(STUDY / 'inputs/AO.json')
population = read(STUDY / 'inputs/input_population.json')
original_cfg = OmegaConf.load(STUDY / 'inputs/input_config.yaml')
saved = checkpoint.load(STUDY / 'inputs/input_checkpoint.pt')
checkpoint.validate(saved, original_cfg, read(STUDY / 'inputs/input_determinism.json'))
state = saved['state']
table = np.stack([layout.from_dict(row).numpy() for row in population['genomes']])
start = p['population_start']
assert read(STUDY / 'inputs/population_import.json') == start
assert table.shape == (32, 875) and table.dtype == np.float32 and np.isfinite(table).all()
assert population['dims'] == layout.dims.__dict__
assert table.tobytes() == state['population'].numpy().tobytes() == prior_matrix[64:96].tobytes()
assert state['generation'] == 4 and state['evals'] == 1024 and state['rc_lives'] == 2048
assert population['ids'] == state['ids'].tolist() == start['old_ids'] and len(set(start['old_ids'])) == 32
assert start['new_ids'] == list(range(32)) and start['shape'] == [32, 875]
assert raw(table) == start['population_raw_sha256'] and sha(STUDY / start['population_file']) == start['file_sha256']
assert start['row_sha256'] == [raw(row) for row in table]
assert start['old_to_new'] == [dict(old_id=old, new_id=i, row=i, raw_sha256=raw(table[i]))
                              for i, old in enumerate(start['old_ids'])]

ref_manifest = read(STUDY / p['references_manifest'])
refs = np.load(STUDY / p['reference_input'], allow_pickle=False)
assert ref_manifest['roles'] == p['reference_roles'] == ['AO', 'G8_joint', 'Pareto4_joint']
assert ref_manifest['rows'] == p['references'] and ref_manifest['dims'] == layout.dims.__dict__
assert refs.shape == (3, 875) and refs.dtype == np.float32 and np.isfinite(refs).all()
assert ref_manifest['shape'] == [3, 875] and ref_manifest['dtype'] == 'float32'
assert raw(refs) == ref_manifest['raw_sha256']
assert ref_manifest['prior_summary_sha256'] == sha(ROOT / ref_manifest['prior_summary_source'])
ref_expected = [('AO', 96, 'AO', 0, 5336), ('G8_joint', 20, 'G8', 20, 1795),
                ('Pareto4_joint', 90, 'pareto4', 26, 918)]
for i, (role, index, group, local, native_id) in enumerate(ref_expected):
    row = ref_manifest['rows'][i]
    source = prior_rows['rows'][index]
    assert (row['role'], row['panel_index'], row['group'], row['local_row'], row['native_id']) == (
        role, index, group, local, native_id)
    assert source['group'] == group and source['row'] == local and source['native_id'] == native_id
    assert prior_summary['descriptive_orders'][group]['fresh_order_local_rows'][0] == local
    loaded_layout, vector = Layout.load(STUDY / row['path'])
    assert loaded_layout.dims == layout.dims
    assert refs[i].tobytes() == vector.numpy().tobytes() == prior_matrix[index].tobytes()
    assert raw(refs[i]) == row['raw_sha256'] == source['raw_sha256']
    assert sha(STUDY / row['path']) == row['file_sha256']

assert list(p['worlds']) == ['patch', 'pool', 'persistent', 'blink80_20', 'transfer', 'reserved_capacity3']
assert {name: p['worlds'][name] for name in prior['worlds']} == prior['worlds']
assert p['selection_worlds'] == {name: p['worlds'][name]['world'] for name in ('patch', 'pool', 'persistent')}
reserved = dict(p['worlds']['patch']['world'], patch_count=4, patch_capacity=3,
                R_min=2.5, R_max=4.5, patch_refill_fast=60., patch_refill_slow=180.)
assert p['worlds']['reserved_capacity3']['world'] == reserved
for record in p['worlds'].values():
    world = spec.World(**record['world'])
    spec.V6.validate_world(world)
    assert record['abi'] == 6 and record['ledger_columns'] == list(spec.V6.LEDGER)
    assert len(record['ledger_columns']) == 107 and len(record['world_vector']) == 82
    assert spec.V6.pack_world(world).tolist() == record['world_vector'] and world.T == 1024 and world.t_open == 0

cfg = OmegaConf.load(STUDY / p['configs']['pareto']['path'])
cfg_dict = OmegaConf.to_container(cfg, resolve=True)
expected = copy.deepcopy(OmegaConf.to_container(original_cfg, resolve=True))
expected['seed'] = 53236
expected['evolve']['generations'] = 8
expected['evolve']['recheck_lives'] = 32
expected['life']['lives'] = 32
expected['life']['control'] = 'resource_patch_depth_continuation'
expected['evolve']['seed_genome'] = str(STUDY / start['population_file'])
expected['logging']['output_dir'] = str(STUDY / 'runs/pareto')
expected['population_start'] = loader_identity(start)
expected['retention_selection'] = selection_identity('pareto', p['selection_worlds'])
assert cfg_dict == expected
assert sha(STUDY / p['configs']['pareto']['path']) == p['configs']['pareto']['sha256']
ev = LifeEvaluator(cfg, layout)
assert ev.fast and ev.extinct_charge and not ev.has_envelope and ev.abi.version == 6 and ev.T == 1024
assert p['search'] == dict(generations=8, parents=32, children=224, shortlist=64, base_lives=32,
    recheck_lives=32, selection_lives=81920, validation_generations=[0, 4, 7], validation_lives=48,
    final_lives=6, research_lives=81974, startup_lives=4, total_calls=81978)
assert p['measurement'] == dict(endpoint_genomes=32, endpoint_worlds=3, endpoint_lives_per_genome_world=32,
    endpoint_lives=3072, confirmation_genomes=4, confirmation_worlds=6, confirmation_lives_per_genome_world=512,
    confirmation_lives=12288, research_lives=15360, startup_lives=4, total_calls=15364)
assert p['research_lives'] == 81974+3072+12288 == 97334 and p['startup_lives'] == 8
assert p['total_calls'] == 97342
assert p['confirmation_roles'] == ['AO', 'G8_joint', 'Pareto4_joint', 'depth8_joint']
assert p['primary_contrast'] == ['depth8_joint', 'Pareto4_joint']
assert p['endpoint_rule'] == dict(worlds=['patch', 'pool', 'persistent'],
    capture_scales=[19.046875, 16.029296875, 5.919921875], fitness_weights=[.5, .25, .25],
    order=['minimum_capture_fraction_descending', 'weighted_production_F_descending', 'native_id_ascending'],
    frozen_before_confirmation=True, replaces_historical_endpoint=False)
assert p['endpoint_reference_captures'] == p['endpoint_rule']['capture_scales']
assert p['endpoint_reference_worlds'] == p['endpoint_rule']['worlds']
assert p['runtime_budget'] == dict(cpu_seconds=10620, wall_seconds=7020, threads=2, workers=1,
    cleanup_margin_seconds=10, rss_bytes=4*1024**3, address_space_bytes=8*1024**3,
    minimum_available_bytes=4*1024**3)
assert p['phase_budgets'] == dict(pareto=dict(cpu_seconds=8700, wall_seconds=5400),
                                 measurement=dict(cpu_seconds=1920, wall_seconds=1620))
assert p['package_budget'] == dict(cpu_seconds=10800, wall_seconds=7200,
    preparation_terminal_cpu_reserve=180, preparation_terminal_wall_reserve=180)
assert not any((STUDY / name).exists() for name in runtime_artifacts)

usage = resource.getrusage(resource.RUSAGE_SELF)
receipt = dict(status='passed', protocol_sha256=protocol_sha, reviewer_source_sha256=sha(Path(__file__)),
    ready_sha256=sha(STUDY / 'READY.json'),
    review_pins={name: sha(STUDY / 'reviews' / name) for name in review_names},
    seed_audit_sha256=sha(STUDY / 'namespace/seed_audit.json'),
    namespace_receipt_sha256=sha(STUDY / 'namespace/audit_receipt.json'),
    source_pins=p['source_pins'],
    pinned_files_checked={key: len(p[key]) for key in
                          ('input_pins', 'source_pins', 'production_pins', 'original_input_pins')},
    ordered_population_rows=32, population_raw_sha256=raw(table),
    reference_rows=ref_manifest['rows'], references_raw_sha256=raw(refs),
    unchanged_worlds=5, reserved_worlds=1, native_unique_ids=564, endpoint_seeds=32, confirmation_seeds=512,
    native_observation_calls=54, planned_total_calls=97342, materialization_passes=1,
    native_lives_executed=0, builds=0, random_draws=0,
    resources=dict(cpu_seconds=usage.ru_utime+usage.ru_stime, peak_rss_bytes=usage.ru_maxrss*1024),
    scope='Exact saved populations/checkpoint/order, three prior-panel references, six world packings, '
          'nine-field config replacement, adapter identities, source/review/audit pins and inventory/resources.',
    limitations='No numerical identity call, build, simulator, genetic RNG or collision rescan. '
                'Only the evaluator constructor and deterministic life-ID hash were invoked.')
with (STUDY / 'reviews/actual_input_review.json').open('x') as stream:
    json.dump(receipt, stream, indent=2, allow_nan=False)
    stream.write('\n')
print(json.dumps(dict(status='passed', protocol_sha256=protocol_sha,
                     review_sha256=sha(STUDY / 'reviews/actual_input_review.json'))))
