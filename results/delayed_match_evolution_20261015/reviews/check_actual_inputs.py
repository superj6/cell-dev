"""Independent deterministic input review; no engine build, execution, or random draw."""
from __future__ import annotations

import ast
import hashlib
import json
import resource
import sys
import time
from dataclasses import asdict, replace
from pathlib import Path

START = time.monotonic()
STUDY = Path(__file__).resolve().parents[1]
ROOT = STUDY.parents[1]
sys.dont_write_bytecode = True
sys.path[:0] = [str(STUDY), str(ROOT)]

import torch
from omegaconf import OmegaConf

from common import checked_protocol, raw_sha, read, sha
from population_loader import loader_identity, read_population
from selection import selection_identity
from src import checkpoint
from src.genome import Layout
from src.life import spec
from src.life.evaluate import LifeEvaluator

torch.set_num_threads(1)
p = checked_protocol()
protocol_hash = sha(STUDY / 'protocol.json')
assert protocol_hash == '2941610e25eb55f5e3b4ca2f0be91db46931573b24788bb85709c5b8464d9345'
ready = read(STUDY / 'READY.json')
assert ready == dict(status='prepared', protocol_sha256=protocol_hash,
                     preparation_lives=0, preparation_builds=0, preparation_random_draws=0)
assert not any((STUDY / name).exists() for name in
               ('release.json', 'attempt.json', 'execution', 'runs', 'raw', 'measurement_complete.json'))
for name, digest in p['original_input_pins'].items():
    assert sha(ROOT / name) == digest, name

cfg = OmegaConf.load(STUDY / 'configs/mixed.yaml')
old_cfg = OmegaConf.load(STUDY / 'inputs/AO_config.yaml')
assert sha(STUDY / 'configs/mixed.yaml') == sha(STUDY / 'inputs/config.yaml')
layout, endpoint = Layout.load(STUDY / 'inputs/AO_start.json')
saved = read(STUDY / 'inputs/input_population.json')
table = torch.stack([layout.from_dict(row) for row in saved['genomes']])
state = checkpoint.load(STUDY / 'inputs/AO_checkpoint.pt')
checkpoint.validate(state, old_cfg, read(STUDY / 'inputs/AO_determinism.json'))
assert table.shape == (32, 875) and table.dtype == torch.float32 and bool(torch.isfinite(table).all())
assert state['state']['generation'] == 24
assert table.numpy().tobytes() == state['state']['population'].numpy().tobytes()
assert saved['ids'] == state['state']['ids'].tolist() == p['population_start']['old_ids']
assert len(set(saved['ids'])) == 32
assert raw_sha(table.numpy()) == p['population_start']['population_raw_sha256']
assert [raw_sha(row.numpy()) for row in table] == p['population_start']['row_sha256']
assert table[0].numpy().tobytes() == endpoint.numpy().tobytes()
assert read(STUDY / 'inputs/population_import.json') == p['population_start']
assert read_population(STUDY / 'inputs/input_population.json', layout, p['population_start']).numpy().tobytes() == table.numpy().tobytes()
assert OmegaConf.to_container(cfg.population_start, resolve=True) == loader_identity(p['population_start'])
for row in p['references']:
    other_layout, genome = Layout.load(STUDY / row['path'])
    assert other_layout.dims == layout.dims
    assert sha(STUDY / row['path']) == sha(ROOT / row['source']) == row['file_sha256']
    assert raw_sha(genome.numpy()) == row['raw_sha256']

assert cfg.seed == 53233 and cfg.threads == 2 and cfg.mode == 'life'
assert (cfg.evolve.mu, cfg.evolve.lam, cfg.evolve.generations, cfg.evolve.recheck_k,
        cfg.evolve.recheck_lives, cfg.life.lives) == (32, 224, 24, 64, 8, 8)
assert cfg.evolve.recheck_key == 'all' and cfg.evolve.heldout_every == 4
for name in ('breeding', 'n_mut', 'n_mut_scale', 'p_cell', 'immigrants', 'random_ties', 'batch'):
    assert cfg.evolve[name] == old_cfg.evolve[name], name
assert (cfg.evolve.dup_rate, cfg.evolve.del_rate, cfg.evolve.dup_split) == (0., 0., False)
assert Path(cfg.evolve.seed_genome) == STUDY / 'inputs/input_population.json'
assert Path(cfg.logging.output_dir) == STUDY / 'runs/mixed'
assert cfg.logging.checkpoint_every == 1 and cfg.logging.lineage == 'all'
assert cfg.life.abi == 5 and cfg.life.T == cfg.life.founder_T == 85.
assert cfg.life.valid_lives == 16 and cfg.life.final_lives == 2 and cfg.life.final_top == 1
assert cfg.life.final_fork_lives == 0 and cfg.life.T_choices is None
assert not cfg.life.heldout and not cfg.life.flags and not cfg.life.size_curve
assert cfg.life.freeze_frac is None and cfg.life.t_open == 0.
assert not cfg.clones.every and not cfg.clones.conditions and not cfg.envelope.enabled
assert not cfg.world and not cfg.costs_life
assert OmegaConf.to_container(cfg.retention_selection, resolve=True) == selection_identity('mixed', p['selection_worlds'])
assert list(cfg.retention_selection.pattern) == ['match85', 'pool', 'match85', 'persistent'] * 2
evaluator = LifeEvaluator(cfg, layout)  # constructor and world accessor only, never draw or evaluate
assert evaluator.fast and evaluator.extinct_charge and asdict(evaluator.world()) == p['selection_worlds']['match85']

prior_worlds = read(STUDY / 'inputs/AO_protocol.json')['worlds']
match = spec.world('catch_delayed_match_l4', T=85.)
expected_worlds = {'match85': match,
    **{name: spec.World(**prior_worlds[name]['world']) for name in ('pool', 'persistent', 'blink80_20')},
    'match1024': replace(match, T=1024.), 'short_blank': replace(match, blank_min=2., blank_max=4.),
    'transfer': replace(match, blank_min=10., blank_max=30., R_min=3., R_max=5.)}
assert list(p['worlds']) == list(expected_worlds)
for name, expected in expected_worlds.items():
    actual = p['worlds'][name]
    assert actual['abi'] == 5 and actual['world'] == asdict(expected), name
    spec.V5.validate_world(expected)
    assert actual['world_vector'] == spec.V5.pack_world(expected).tolist(), name
    assert len(actual['world_vector']) == 77 and actual['ledger_columns'] == list(spec.V5.LEDGER)
    assert len(actual['ledger_columns']) == 70 and expected.t_open == 0.
assert list(p['roles']) == ['AM_reference', 'AO_start', 'mixed8', 'mixed24']

audit = read(STUDY / 'namespace/seed_audit.json')
reservation = read(STUDY / 'reservation.json')
assert audit['status'] == 'passed' and audit['native_seed'] == 53233
assert p['seeds'] == audit['confirmation_seeds'] == reservation['confirmation_seeds'] == list(range(52460000, 52460512))
native_ids = audit['run_life_seeds']['mixed']
assert len(native_ids) == len(set(native_ids)) == 500 and native_ids == reservation['native_ids']
assert not any(52460000 <= seed < 52470000 for seed in native_ids)
assert reservation['status'] == 'reserved' and reservation['native_seed'] == 53233
assert reservation['seed_blocks'] == [[52460000, 52470000]]
assert reservation['audit_sha256'] == sha(STUDY / 'namespace/seed_audit.json')

numerical = p['expected_numerical_identity']
identity_file = read(STUDY / 'inputs/startup_identity.json')
old_identity = read(STUDY / 'inputs/AO_startup_identity.json')['identity']
compiled = read(STUDY / 'inputs/baseline_startup.json')['builds']
assert identity_file['identity'] == numerical and identity_file['changed_fields'] == ['kernels', 'sources']
assert all(value == old_identity[key] for key, value in numerical.items() if key not in ('sources', 'kernels'))
assert numerical['kernels'] == {key: row['sha256'] for key, row in compiled.items()}
assert numerical['flags'] == {key: row['flags'] for key, row in compiled.items()}
assert numerical['sources'] == {name: digest for name, digest in p['production_pins'].items() if name.startswith('src/')}
assert all(sha(ROOT / name) == digest for name, digest in numerical['sources'].items())
truth = read(STUDY / 'inputs/matching_truth.json')
assert truth['status'] == 'complete' and truth['cases'][0]['name'] == 'reflex_preset_0'
assert truth['cases'][0]['seed'] == 42000000
assert read(STUDY / 'inputs/information_complete.json')['summary_sha256'] == sha(STUDY / 'inputs/information_summary.json')
assert read(STUDY / 'inputs/information_summary.json')['section_0_4_thresholds_met']
assert read(STUDY / 'inputs/information_budget.json')['status'] == 'complete'

expected_budget = dict(cpu_seconds=10680, wall_seconds=7080, total_cpu_seconds=10800, total_wall_seconds=7200,
    preparation_cpu_allowance=120, preparation_wall_allowance=120, search_cpu_seconds=8280,
    confirmation_cpu_seconds=2400, threads=2, workers=1, cleanup_margin_seconds=10,
    rss_bytes=4*1024**3, minimum_available_bytes=4*1024**3, address_space_bytes=8*1024**3)
assert p['budget'] == expected_budget
search_lives = 24 * ((32 + 224) * 8 + 64 * 8) + 7 * 16 + 6
confirm_lives = 4 * 7 * 512
assert search_lives == p['search']['research_lives_per_arm'] == 61558
assert confirm_lives == p['confirmation_lives'] == 14336
assert search_lives + confirm_lives == p['research_lives'] == 75894
assert p['startup_lives'] == 8 and p['total_calls'] == 75902
assert p['search']['startup_lives_per_arm'] == p['confirmation_startup_lives'] == 4
assert p['search']['midpoint'] == 8 and p['search']['growth_diagnostic_T'] == 42
assert p['search']['growth_diagnostic_lives'] == 2
tree = ast.parse((STUDY / 'native_replay.py').read_text())
expected_search = [node.value for node in ast.walk(tree) if isinstance(node, ast.Assign)
                   and any(isinstance(t, ast.Name) and t.id == 'expected_search' for t in node.targets)]
assert len(expected_search) == 1 and ast.literal_eval(expected_search[0]) == p['search']
test_receipt = read(STUDY / 'reviews/source_checks.json')
assert test_receipt['status'] == 'passed' and test_receipt['tests'] == 53
amendment = read(STUDY / 'reviews/native_metadata_schema_amendment.json')
for name, digest in test_receipt['source_sha256'].items():
    if name == 'native_replay.py':
        assert digest == amendment['previous_source_sha256']
        assert sha(STUDY / name) == amendment['source_sha256']
    else:
        assert sha(STUDY / name) == digest, name
assert amendment['prior_53_test_receipt_sha256'] == sha(STUDY / 'reviews/source_checks.json')
assert read(STUDY / 'source_checks/stdout.log')['status'] == 'passed'

usage = resource.getrusage(resource.RUSAGE_SELF)
result = dict(status='passed', protocol_sha256=protocol_hash, ready_sha256=sha(STUDY / 'READY.json'),
    checker_sha256=sha(__file__), source_revision=p['source_revision'], source_pins=p['source_pins'],
    config_sha256=sha(STUDY / 'configs/mixed.yaml'), input_files_verified=len(p['input_pins']),
    original_input_files_verified=len(p['original_input_pins']), production_files_verified=len(p['production_pins']),
    population=dict(shape=list(table.shape), dtype=str(table.dtype), checkpoint_generation=24,
        raw_sha256=raw_sha(table.numpy()), all_32_rows_and_ids_preserved=True,
        row_zero_equals_AO_start=True, imported_scores_or_rng=False),
    world_checks=dict(worlds=list(expected_worlds), all_abi=5, world_fields=77, ledger_columns=70,
        exact_presets_and_inherited_controls=True, physical_prices_unchanged=True,
        matching_only_changes=['T1024', 'short blank2..4', 'transfer blank10..30/radius3..5']),
    numerical_identity='Predeclared saved identity verified; no numerical_identity(), golden life, or build invoked.',
    seed_checks=dict(native_seed=53233, distinct_native_ids=500, confirmation_count=512,
        confirmation_inclusive=[52460000,52460511], reserved_half_open=[52460000,52470000]),
    budget=expected_budget, calls=dict(search_research=search_lives, confirmation=confirm_lives,
        startup=8, total=75902, confirmation_batch_rows=28, declared_growth_T42_lives=2),
    evidence_pins={name: sha(STUDY / name) for name in ('reviews/namespace_review.json',
        'reviews/watchdog_source_review.json', 'reviews/source_checks.json',
        'reviews/native_metadata_schema_amendment.json', 'source_checks/stdout.log')},
    interpretation=['Generation24 is primary; generation8 is a fixed passive observation, not a replacement.',
        'The 53 source tests predate only the preserved metadata-schema amendment; that amendment is separately source-reviewed.',
        'Monitor completion rehashes raw rows and binds the index. Frozen terminal reader verifies both raw and scored hashes before complete analysis.',
        'T42 growth is the declared two-life integer-time diagnostic, not an exact T85 half-life or selection exposure.',
        'No successful outcome, retention, broad generalization, or neural-memory claim follows from this prelaunch review.'],
    material_blockers=[], simulator_calls=0, builds=0, random_draws=0,
    cpu_seconds=usage.ru_utime+usage.ru_stime, wall_seconds=time.monotonic()-START,
    maximum_rss_kib=usage.ru_maxrss)
output = STUDY / 'reviews/actual_input_review.json'
output.write_text(json.dumps(result, indent=2, allow_nan=False)+'\n')
print(json.dumps(dict(status=result['status'], protocol_sha256=protocol_hash,
                     review_sha256=sha(output), cpu_seconds=result['cpu_seconds'])))
