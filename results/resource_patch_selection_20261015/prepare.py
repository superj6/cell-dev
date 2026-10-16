"""Prepare the matched acquisition-aware selection comparison; no build, life or genetic draw."""
from __future__ import annotations

import argparse
import copy
import os
import shutil
import subprocess
import sys
from dataclasses import asdict, replace

os.environ.setdefault('ATEN_CPU_CAPABILITY', 'avx2')
sys.dont_write_bytecode = True
from common import ROOT, STUDY, raw_sha, read, save, sha  # noqa: E402

sys.path.insert(0, str(ROOT))
AO = ROOT / 'results/retained_depth_20261015'
PILOT = ROOT / 'results/resource_patch_evolution_20261015'
BASELINE = ROOT / 'results/resource_patch_baseline_20261015'
ARMS = ('mean', 'pareto')
ROLES = ('AO_start', 'patch8_start', 'mean4', 'pareto4')
SOURCE_FILES = ('common.py', 'monitor.py', 'prepare.py', 'search.py', 'selection.py', 'pareto.py',
                'population_loader.py', 'measure.py', 'analyze.py', 'native_replay.py', 'replay_ops.py',
                'PROTOCOL.md', 'release_and_run.py')


def planned_search_seeds():
    from src.life.evaluate import life_seed

    values = []
    for generation in range(4):
        values.extend(life_seed(53235, 'gen', generation, i) for i in range(16))
        if generation in (0, 3):
            values.extend(life_seed(53235, 'valid', generation, i) for i in range(16))
    for index in (0, 1):
        values.extend(life_seed(53235, 'final', index, i) for i in range(2))
    if len(values) != len(set(values)) or len(values) != 100:
        raise ValueError('native seed schedule differs')
    return values


def prepare(revision):
    if any((STUDY / name).exists() for name in ('protocol.json', 'inputs', 'configs', 'release.json', 'attempt.json')):
        raise ValueError('preparation requires a new study directory')
    import torch
    from omegaconf import OmegaConf
    from population_loader import loader_identity, read_population
    from selection import expected_worlds, selection_identity

    from src import checkpoint
    from src.genome import Layout
    from src.life import spec
    from src.life.evaluate import LifeEvaluator

    torch.set_num_threads(1)
    audit = read(STUDY / 'namespace/seed_audit.json')
    schedule = planned_search_seeds()
    if (audit['status'] != 'passed' or audit['native_seed'] != 53235
            or audit['confirmation_seeds'] != list(range(52500000, 52500512))
            or audit['run_life_seeds'] != {arm: schedule for arm in ARMS}):
        raise ValueError('fresh audited matched schedule required')
    head = subprocess.check_output(['git', 'rev-parse', 'HEAD'], cwd=ROOT, text=True).strip()
    if revision != head or len(revision) != 40:
        raise ValueError('explicit current completed milestone revision required')
    baseline = read(BASELINE / 'protocol.json')
    prior = read(PILOT / 'protocol.json')
    for name, digest in prior['production_pins'].items():
        if sha(ROOT / name) != digest:
            raise ValueError('production changed since completed pilot: ' + name)
    if (read(PILOT / 'budget.json')['status'] != 'complete'
            or read(PILOT / 'reviews/independent_accounting.json')['status'] != 'passed'
            or sha(PILOT / 'summary.json') != 'f819c039ddb9a8751148b73afb4bdb7445fe7a5ca2d755bf7118490b0598c554'):
        raise ValueError('completed independently checked pilot required')
    layout, endpoint = Layout.load(PILOT / 'runs/mixed/best_genome.json')
    saved = read(PILOT / 'runs/mixed/population.json')
    table = torch.stack([layout.from_dict(row) for row in saved['genomes']])
    state = checkpoint.load(PILOT / 'runs/mixed/checkpoint.pt')
    checkpoint.validate(state, OmegaConf.load(PILOT / 'runs/mixed/config.yaml'),
                        read(PILOT / 'runs/mixed/determinism.json'))
    if (table.shape != (32, 875) or table.dtype != torch.float32 or not bool(torch.isfinite(table).all())
            or saved['ids'] != state['state']['ids'].tolist() or len(set(saved['ids'])) != 32
            or state['state']['generation'] != 8
            or table.numpy().tobytes() != state['state']['population'].numpy().tobytes()
            or table[0].numpy().tobytes() != endpoint.numpy().tobytes()):
        raise ValueError('exact ordered 32-survivor final patch population required')
    hashes = [raw_sha(row.numpy()) for row in table]
    population = dict(population_file='inputs/input_population.json',
        file_sha256=sha(PILOT / 'runs/mixed/population.json'), population_raw_sha256=raw_sha(table.numpy()),
        shape=[32, 875], old_ids=saved['ids'], new_ids=list(range(32)), row_sha256=hashes,
        old_to_new=[dict(old_id=old, new_id=i, row=i, raw_sha256=hashes[i])
                    for i, old in enumerate(saved['ids'])])
    sources = {
        'input_population.json': PILOT / 'runs/mixed/population.json',
        'patch8_start.json': PILOT / 'runs/mixed/best_genome.json',
        'AO_start.json': AO / 'runs/balanced/best_genome.json',
        'input_checkpoint.pt': PILOT / 'runs/mixed/checkpoint.pt',
        'input_config.yaml': PILOT / 'runs/mixed/config.yaml',
        'input_determinism.json': PILOT / 'runs/mixed/determinism.json',
        'prior_protocol.json': PILOT / 'protocol.json',
        'prior_summary.json': PILOT / 'summary.json',
        'prior_independent_accounting.json': PILOT / 'reviews/independent_accounting.json',
        'AO_protocol.json': AO / 'protocol.json',
        'AO_startup_identity.json': AO / 'inputs/startup_identity.json',
        'patch_truth.json': ROOT / 'results/abi6_resource_patches_20261015/validation/truth/truth.json',
        'baseline_startup.json': BASELINE / 'startup.json',
        'baseline_protocol.json': BASELINE / 'protocol.json',
        'seed_audit.json': STUDY / 'namespace/seed_audit.json',
    }
    (STUDY / 'inputs').mkdir()
    for name, source in sources.items():
        shutil.copyfile(source, STUDY / 'inputs' / name)
    save(STUDY / 'inputs/population_import.json', population, exclusive=True)
    imported = read_population(STUDY / population['population_file'], layout, population)
    if imported.numpy().tobytes() != table.numpy().tobytes():
        raise ValueError('external loader changed row bytes')
    selection_worlds = expected_worlds()
    if selection_worlds != prior['selection_worlds']:
        raise ValueError('selection physics or prices changed')
    patch = spec.World(**selection_worlds['patch'])
    definitions = {
        'patch': patch,
        'pool': spec.World(**selection_worlds['pool']),
        'persistent': spec.World(**selection_worlds['persistent']),
        'blink80_20': spec.World(**prior['worlds']['blink80_20']['world']),
        'transfer': replace(patch, patch_count=2, R_min=3.5, R_max=5.5,
                            patch_refill_fast=60., patch_refill_slow=180.),
    }
    worlds = {}
    for name, world in definitions.items():
        spec.V6.validate_world(world)
        worlds[name] = dict(abi=6, world=asdict(world), world_vector=spec.V6.pack_world(world).tolist(),
                            ledger_columns=list(spec.V6.LEDGER))
    (STUDY / 'configs').mkdir()
    for arm in ARMS:
        cfg = OmegaConf.load(PILOT / 'runs/mixed/config.yaml')
        cfg.seed, cfg.threads = 53235, 2
        cfg.evolve.generations, cfg.evolve.heldout_every = 4, 4
        cfg.evolve.seed_genome = str(STUDY / population['population_file'])
        cfg.logging.output_dir = str(STUDY / 'runs' / arm)
        cfg.population_start = loader_identity(population)
        cfg.retention_selection = selection_identity(arm, selection_worlds)
        cfg.life.control = 'resource_patch_selection_comparison'
        evaluator = LifeEvaluator(cfg, layout)
        if (asdict(evaluator.world()) != selection_worlds['patch'] or not evaluator.extinct_charge
                or not evaluator.fast or cfg.clones.every or cfg.clones.conditions or cfg.life.size_curve
                or cfg.life.final_fork_lives != 0 or cfg.evolve.dup_rate or cfg.evolve.del_rate
                or cfg.evolve.dup_split or cfg.life.T_choices or cfg.envelope.enabled
                or cfg.logging.lineage != 'all' or cfg.logging.checkpoint_every != 1
                or cfg.evolve.recheck_key != 'all'
                or (cfg.evolve.mu, cfg.evolve.lam, cfg.life.lives, cfg.evolve.recheck_k,
                    cfg.evolve.recheck_lives, cfg.life.valid_lives, cfg.life.final_lives, cfg.life.final_top)
                != (32, 224, 8, 64, 8, 16, 2, 1)):
            raise ValueError('ordinary matched search configuration differs')
        (STUDY / 'configs' / (arm + '.yaml')).write_text(OmegaConf.to_yaml(cfg, resolve=True))
    expected = copy.deepcopy(read(STUDY / 'inputs/AO_startup_identity.json')['identity'])
    old_expected = copy.deepcopy(expected)
    current_sources = sorted((ROOT / 'src').rglob('*.py'))
    expected['sources'] = {str(p.relative_to(ROOT)): sha(p) for p in current_sources}
    expected['sources']['src/life/kernel.c'] = sha(ROOT / 'src/life/kernel.c')
    compiled = read(STUDY / 'inputs/baseline_startup.json')['libraries']
    expected['kernels'] = {key: value['sha256'] for key, value in compiled.items()}
    if expected['flags'] != {key: value['flags'] for key, value in compiled.items()}:
        raise ValueError('native compiler flags changed')
    save(STUDY / 'inputs/startup_identity.json', dict(identity=expected,
        preexpected_fields='Versions/libm/noise/golden copied from completed AO, sources and binaries from integrated ABI6.',
        prior_identity_sha256=sha(STUDY / 'inputs/AO_startup_identity.json'),
        changed_fields=[key for key in expected if expected[key] != old_expected[key]],
        preparation_lives=0, preparation_builds=0, preparation_random_draws=0), exclusive=True)
    references = []
    for role in ROLES[:2]:
        path = STUDY / 'inputs' / (role + '.json')
        ref_layout, genome = Layout.load(path)
        if ref_layout.dims != layout.dims:
            raise ValueError('reference layout differs')
        references.append(dict(role=role, path=str(path.relative_to(STUDY)), file_sha256=sha(path),
            raw_sha256=raw_sha(genome.numpy()), source=str(sources[role + '.json'].relative_to(ROOT))))
    save(STUDY / 'reservation.json', dict(status='reserved', native_seed=53235,
        seed_blocks=[[52500000, 52510000]], confirmation_seeds=audit['confirmation_seeds'],
        native_ids={arm: schedule for arm in ARMS},
        intentional_native_reuse='Matched arms share the exact native schedule and initial genetic seed.',
        experiment='Mean-F versus acquisition-aware Pareto selection',
        audit_sha256=sha(STUDY / 'namespace/seed_audit.json')), exclusive=True)
    production = current_sources + [ROOT / 'src/life/kernel.c', ROOT / 'scripts/taskvar_gates.py']
    protocol = dict(study='Resource-patch acquisition-aware selection comparison', roles=list(ROLES), runs=list(ARMS),
        native_seed=53235, seeds=audit['confirmation_seeds'], worlds=worlds, selection_worlds=selection_worlds,
        configs={arm: dict(path=f'configs/{arm}.yaml', sha256=sha(STUDY / 'configs' / (arm+'.yaml'))) for arm in ARMS},
        population_start=population, references=references, reference=references[1],
        research_lives=30796, startup_lives=12, total_calls=30808, confirmation_lives=10240,
        confirmation_startup_lives=4,
        search=dict(arms=list(ARMS), generations=4, research_lives_per_arm=10278, startup_lives_per_arm=4,
            initial_lives=8, recheck_lives=8, parents=32, offspring=224,
            growth_diagnostic_T=512, growth_diagnostic_lives=2),
        budget=dict(cpu_seconds=5280, wall_seconds=3480, total_cpu_seconds=5400, total_wall_seconds=3600,
            preparation_cpu_allowance=120, preparation_wall_allowance=120,
            search_cpu_seconds=4080, confirmation_cpu_seconds=1200, threads=2, workers=1,
            cleanup_margin_seconds=10, rss_bytes=4*1024**3, minimum_available_bytes=4*1024**3,
            address_space_bytes=8*1024**3),
        extinct_charge=True, status_bits=spec.STATUS, hash_names=list(spec.V6.HASHES),
        retention_margin_fraction=.1, expected_numerical_identity=expected,
        primary=dict(world='patch', new='pareto4', old='mean4',
            outcomes=['total captures', 'refill-origin harvest', 'production_F', 'empty clicks', 'physical costs']),
        endpoint=dict(rule='maximum minimum normalized per-domain captures, then ordinary aggregate F, then ascending survivor ID',
            reference_roles=['AO_start'], reference_captures=[19.046875, 16.029296875, 5.919921875],
            worlds=['patch', 'pool', 'persistent'], selection_lives=16, per_world_lives=[8, 4, 4],
            candidates=32, fixed_before_confirmation=True, export='joint_genome.json'),
        retention=dict(worlds=['pool', 'persistent', 'blink80_20'], references=['AO_start'],
            retained_fraction=.9, diagnostic_only=True),
        transfer=dict(world='transfer', selection_exposure=False, endpoint_reselection=False,
            scope='New count2/radius3.5-5.5/refill60-180 joint combination; limited parameter transfer.'),
        exploratory_scope='Bounded search comparison; no formal section0.4 admission claim.',
        source_pins={name: sha(STUDY / name) for name in SOURCE_FILES},
        input_pins={str(p.relative_to(STUDY)): sha(p) for folder in (STUDY/'inputs', STUDY/'configs')
                    for p in sorted(folder.rglob('*')) if p.is_file()},
        original_input_pins={str(p.relative_to(ROOT)): sha(p) for p in sources.values()},
        production_pins={str(p.relative_to(ROOT)): sha(p) for p in production},
        seed_audit_sha256=sha(STUDY / 'namespace/seed_audit.json'), reservation_sha256=sha(STUDY/'reservation.json'),
        source_revision=revision, engine_revision=baseline['source_revision'],
        limitations=[
            'One matched pair, not independent evolutionary replications.',
            'Pareto selection may preserve specialists or noisy extremes rather than a single reusable organism.',
            'Common final32 joint selection uses noisy 16-life estimates; confirmation cannot replace either endpoint.',
            'Ordinary F remains a Pareto objective but only an endpoint tiebreaker; acquisition gains may be costly.',
            'Initial/refill food origins do not establish revisit order, memory or learned recovery rates.',
            'Same unchanged endpoints face all worlds; a portfolio of specialists is not generalization.',
            'Prior reserved combination is now revealed development evidence; this study uses a new combination.',
            'No cell rules, prices, world feedback, prescribed behaviors or global organism channels change.',
            'The exploratory exception does not supply missing formal admission comparisons.'])
    save(STUDY / 'protocol.json', protocol, exclusive=True)
    save(STUDY / 'READY.json', dict(status='prepared', protocol_sha256=sha(STUDY / 'protocol.json'),
        preparation_lives=0, preparation_builds=0, preparation_random_draws=0), exclusive=True)
    print({'status': 'prepared', 'total_calls': 30808, 'protocol_sha256': sha(STUDY / 'protocol.json')})


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--source-revision', required=True)
    prepare(parser.parse_args().source_revision)
