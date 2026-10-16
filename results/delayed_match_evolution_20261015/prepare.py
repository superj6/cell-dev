"""Prepare one inherited matching continuation; no simulator build, life or genetic draw."""
from __future__ import annotations

import copy
import os
import shutil
import sys
from dataclasses import asdict, replace

os.environ.setdefault('ATEN_CPU_CAPABILITY', 'avx2')
sys.dont_write_bytecode = True
from common import ROOT, STUDY, raw_sha, read, save, sha  # noqa: E402

sys.path.insert(0, str(ROOT))
AO = ROOT / 'results/retained_depth_20261015'
INFO = ROOT / 'results/delayed_match_information_20261015'
SOURCE_FILES = ('common.py', 'monitor.py', 'prepare.py', 'search.py', 'selection.py',
                'population_loader.py', 'measure.py', 'analyze.py', 'native_replay.py', 'replay_ops.py')
ROLES = ('AM_reference', 'AO_start', 'mixed8', 'mixed24')


def planned_search_seeds():
    from src.life.evaluate import life_seed

    values = []
    for generation in range(24):
        values.extend(life_seed(53233, 'gen', generation, i) for i in range(16))
        if generation in (0, 4, 8, 12, 16, 20, 23):
            values.extend(life_seed(53233, 'valid', generation, i) for i in range(16))
    for index in (0, 1):
        values.extend(life_seed(53233, 'final', index, i) for i in range(2))
    if len(values) != len(set(values)) or len(values) != 500:
        raise ValueError('native seed schedule differs')
    return values


def prepare():
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
    if (audit['status'] != 'passed' or audit['native_seed'] != 53233
            or audit['confirmation_seeds'] != list(range(52460000, 52460512))
            or audit['run_life_seeds'] != {'mixed': planned_search_seeds()}):
        raise ValueError('fresh audited schedule required')
    admission = read(INFO / 'prelaunch/summary.json')
    marker = read(INFO / 'prelaunch/measurement_complete.json')
    if (not admission['section_0_4_thresholds_met'] or marker['status'] != 'complete'
            or marker['summary_sha256'] != sha(INFO / 'prelaunch/summary.json')
            or read(INFO / 'prelaunch/budget.json')['status'] != 'complete'):
        raise ValueError('completed exact T85 information evidence required')
    layout, endpoint = Layout.load(AO / 'runs/balanced/best_genome.json')
    saved = read(AO / 'runs/balanced/population.json')
    table = torch.stack([layout.from_dict(row) for row in saved['genomes']])
    state = checkpoint.load(AO / 'runs/balanced/checkpoint.pt')
    checkpoint.validate(state, OmegaConf.load(AO / 'runs/balanced/config.yaml'),
                        read(AO / 'runs/balanced/determinism.json'))
    if (table.shape != (32, 875) or table.dtype != torch.float32 or not bool(torch.isfinite(table).all())
            or saved['ids'] != state['state']['ids'].tolist() or len(set(saved['ids'])) != 32
            or state['state']['generation'] != 24
            or table.numpy().tobytes() != state['state']['population'].numpy().tobytes()
            or table[0].numpy().tobytes() != endpoint.numpy().tobytes()):
        raise ValueError('exact ordered 32-survivor AO balanced24 population required')
    row_hashes = [raw_sha(row.numpy()) for row in table]
    population = dict(population_file='inputs/input_population.json',
        file_sha256=sha(AO / 'runs/balanced/population.json'), population_raw_sha256=raw_sha(table.numpy()),
        shape=[32, 875], old_ids=saved['ids'], new_ids=list(range(32)), row_sha256=row_hashes,
        old_to_new=[dict(old_id=old, new_id=i, row=i, raw_sha256=row_hashes[i])
                    for i, old in enumerate(saved['ids'])])
    sources = {
        'input_population.json': AO / 'runs/balanced/population.json',
        'AO_start.json': AO / 'runs/balanced/best_genome.json',
        'AM_reference.json': AO / 'inputs/AM_reference.json',
        'AO_checkpoint.pt': AO / 'runs/balanced/checkpoint.pt',
        'AO_config.yaml': AO / 'runs/balanced/config.yaml',
        'AO_determinism.json': AO / 'runs/balanced/determinism.json',
        'AO_protocol.json': AO / 'protocol.json',
        'AO_summary.json': AO / 'analysis_result/summary.json',
        'AO_startup_identity.json': AO / 'inputs/startup_identity.json',
        'matching_truth.json': ROOT / 'results/abi5_delayed_match_20261015/validation/truth_conservation_fix/truth.json',
        'baseline_startup.json': ROOT / 'results/delayed_match_baseline_20261015/startup.json',
        'information_summary.json': INFO / 'prelaunch/summary.json',
        'information_complete.json': INFO / 'prelaunch/measurement_complete.json',
        'information_budget.json': INFO / 'prelaunch/budget.json',
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
    prior_worlds = read(AO / 'protocol.json')['worlds']
    for name in ('pool', 'persistent'):
        if selection_worlds[name] != asdict(spec.World(**prior_worlds[name]['world'])):
            raise ValueError('earlier selection physics changed')
    match = spec.World(**selection_worlds['match85'])
    definitions = {
        'match85': match,
        'pool': spec.World(**selection_worlds['pool']),
        'persistent': spec.World(**selection_worlds['persistent']),
        'blink80_20': spec.World(**prior_worlds['blink80_20']['world']),
        'match1024': replace(match, T=1024.),
        'short_blank': replace(match, blank_min=2., blank_max=4.),
        'transfer': replace(match, blank_min=10., blank_max=30., R_min=3., R_max=5.),
    }
    worlds = {}
    for name, world in definitions.items():
        spec.V5.validate_world(world)
        worlds[name] = dict(abi=5, world=asdict(world), world_vector=spec.V5.pack_world(world).tolist(),
                            ledger_columns=list(spec.V5.LEDGER))
    cfg = OmegaConf.load(AO / 'runs/balanced/config.yaml')
    cfg.seed, cfg.threads = 53233, 2
    cfg.evolve.generations, cfg.evolve.heldout_every = 24, 4
    cfg.evolve.seed_genome = str(STUDY / population['population_file'])
    cfg.evolve.dup_rate, cfg.evolve.del_rate, cfg.evolve.dup_split = 0., 0., False
    cfg.evolve.recheck_k, cfg.evolve.recheck_lives, cfg.evolve.recheck_key = 64, 8, 'all'
    cfg.logging.output_dir = str(STUDY / 'runs/mixed')
    cfg.logging.checkpoint_every, cfg.logging.lineage = 1, 'all'
    cfg.life.abi, cfg.life.world, cfg.life.control = 5, 'catch_delayed_match_l4', 'delayed_match_continuation'
    cfg.life.T, cfg.life.founder_T, cfg.life.lives = 85., 85., 8
    cfg.life.T_choices, cfg.life.heldout = None, []
    cfg.life.flags, cfg.life.freeze_frac, cfg.life.t_open = [], None, 0.
    cfg.world, cfg.costs_life, cfg.envelope = {}, {}, {'enabled': False}
    cfg.population_start = loader_identity(population)
    cfg.retention_selection = selection_identity('mixed', selection_worlds)
    evaluator = LifeEvaluator(cfg, layout)
    if (asdict(evaluator.world()) != selection_worlds['match85'] or not evaluator.extinct_charge
            or not evaluator.fast or cfg.clones.every or cfg.clones.conditions or cfg.life.size_curve
            or (cfg.evolve.mu, cfg.evolve.lam, cfg.life.valid_lives, cfg.life.final_lives, cfg.life.final_top)
            != (32, 224, 16, 2, 1)):
        raise ValueError('ordinary search configuration differs')
    (STUDY / 'configs').mkdir()
    (STUDY / 'configs/mixed.yaml').write_text(OmegaConf.to_yaml(cfg, resolve=True))
    shutil.copyfile(STUDY / 'configs/mixed.yaml', STUDY / 'inputs/config.yaml')
    expected = copy.deepcopy(read(STUDY / 'inputs/AO_startup_identity.json')['identity'])
    prior_expected = copy.deepcopy(expected)
    current_sources = sorted((ROOT / 'src').rglob('*.py'))
    expected['sources'] = {str(p.relative_to(ROOT)): sha(p) for p in current_sources}
    expected['sources']['src/life/kernel.c'] = sha(ROOT / 'src/life/kernel.c')
    compiled = read(STUDY / 'inputs/baseline_startup.json')['builds']
    expected['kernels'] = {key: value['sha256'] for key, value in compiled.items()}
    if expected['flags'] != {key: value['flags'] for key, value in compiled.items()}:
        raise ValueError('native compiler flags changed')
    save(STUDY / 'inputs/startup_identity.json', dict(identity=expected,
        preexpected_fields='All identity fields predeclared; versions/libm/noise/golden copied from completed AO, sources and binary hashes from current integrated ABI5 and completed baseline.',
        prior_identity_sha256=sha(STUDY / 'inputs/AO_startup_identity.json'),
        changed_fields=[key for key in expected if expected[key] != prior_expected[key]],
        preparation_lives=0, preparation_builds=0, preparation_random_draws=0), exclusive=True)
    references = []
    for role in ROLES[:2]:
        path = STUDY / 'inputs' / (role + '.json')
        ref_layout, genome = Layout.load(path)
        if ref_layout.dims != layout.dims:
            raise ValueError('reference layout differs')
        references.append(dict(role=role, path=str(path.relative_to(STUDY)),
            file_sha256=sha(path), raw_sha256=raw_sha(genome.numpy()),
            source=str(sources[role + '.json'].relative_to(ROOT))))
    reservation = dict(status='reserved', native_seed=53233, seed_blocks=[[52460000, 52470000]],
        confirmation_seeds=audit['confirmation_seeds'], native_ids=audit['run_life_seeds']['mixed'],
        experiment='one ordinary delayed-matching mixed continuation', audit_sha256=sha(STUDY / 'namespace/seed_audit.json'))
    save(STUDY / 'reservation.json', reservation, exclusive=True)
    production = current_sources + [ROOT / 'src/life/kernel.c', ROOT / 'scripts/taskvar_gates.py']
    protocol = dict(study='Delayed-matching cumulative continuation', roles=list(ROLES), runs=['mixed'],
        native_seed=53233, seeds=audit['confirmation_seeds'], worlds=worlds, selection_worlds=selection_worlds,
        configs={'mixed': dict(path='configs/mixed.yaml', sha256=sha(STUDY / 'configs/mixed.yaml'))},
        population_start=population, references=references, ancestral_reference=references[0], reference=references[1],
        research_lives=75894, startup_lives=8, total_calls=75902, confirmation_lives=14336,
        confirmation_startup_lives=4,
        search=dict(arms=['mixed'], generations=24, research_lives_per_arm=61558, startup_lives_per_arm=4,
                    initial_lives=8, recheck_lives=8, parents=32, offspring=224, midpoint=8,
                    growth_diagnostic_T=42, growth_diagnostic_lives=2),
        budget=dict(cpu_seconds=10680, wall_seconds=7080, total_cpu_seconds=10800, total_wall_seconds=7200,
                    preparation_cpu_allowance=120, preparation_wall_allowance=120,
                    search_cpu_seconds=8280, confirmation_cpu_seconds=2400, threads=2, workers=1,
                    cleanup_margin_seconds=10, rss_bytes=4*1024**3, minimum_available_bytes=4*1024**3,
                    address_space_bytes=8*1024**3),
        extinct_charge=True, status_bits=spec.STATUS, hash_names=list(spec.V5.HASHES),
        retention_margin_fraction=.1, expected_numerical_identity=expected,
        primary=dict(world='match85', new='mixed24', old='AO_start',
            outcomes=['cue-dependent narrow-choice response', 'correct narrow per opportunity',
                      'correct broad per opportunity', 'completion coverage', 'production_F']),
        retention=dict(worlds=['pool','persistent','blink80_20'], references=['AO_start','AM_reference'],
                       retained_fraction=.9, diagnostic_only=True),
        transfer=dict(world='transfer', selection_exposure=False, endpoint_reselection=False,
                      scope='One unchanged genome at a reserved joint blank10–30 / radius3–5 combination; narrow parameter transfer, not broad generalization.'),
        source_pins={name: sha(STUDY / name) for name in SOURCE_FILES},
        input_pins={str(p.relative_to(STUDY)): sha(p) for folder in (STUDY/'inputs',STUDY/'configs')
                    for p in sorted(folder.rglob('*')) if p.is_file()},
        original_input_pins={str(p.relative_to(ROOT)): sha(p) for p in sources.values()},
        production_pins={str(p.relative_to(ROOT)): sha(p) for p in production},
        seed_audit_sha256=sha(STUDY / 'namespace/seed_audit.json'), reservation_sha256=sha(STUDY / 'reservation.json'),
        source_revision='968bb81f2e146e2e729bca43004628d78a6e9b99',
        limitations=[
            'One deliberately chosen continuing population and one new search; confirmation lives are not independent searches.',
            'Generation24 is primary; generation8 is a fixed observation, never a replacement endpoint.',
            'Selection weights and life sample counts are fixed; this does not establish an optimal mixture or force retention.',
            'Existing native captures telemetry is a physical-slot counter, not matching correctness; use ABI5 class counters.',
            'Positive F or more broad choices does not establish conditional matching or memory.',
            'T1024 and shortblank are endpoint diagnostics only, with different opportunity throughput; no crossworldF memory effect.',
            'Old worlds and earlier baseline match1024 are development-known; only the stated combination is held out from selection.',
            'Native search retains aggregate guard/invalid health, not every per-life ledger; confirmation retains every returned row.',
            'No price, cell rule, prescribed behavior, global channel, or population-responsive world change.'])
    save(STUDY / 'protocol.json', protocol, exclusive=True)
    save(STUDY / 'READY.json', dict(status='prepared', protocol_sha256=sha(STUDY / 'protocol.json'),
        preparation_lives=0, preparation_builds=0, preparation_random_draws=0), exclusive=True)
    print({'status': 'prepared', 'total_calls': 75902, 'protocol_sha256': sha(STUDY / 'protocol.json')})


if __name__ == '__main__':
    prepare()
