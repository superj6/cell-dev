"""Prepare one inherited resource-patch continuation; no simulator build, life or genetic draw."""
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
BASELINE = ROOT / 'results/resource_patch_baseline_20261015'
MODULATION = ROOT / 'results/resource_patch_modulation_20261015'
SOURCE_FILES = ('common.py', 'monitor.py', 'prepare.py', 'search.py', 'selection.py',
                'population_loader.py', 'measure.py', 'analyze.py', 'native_replay.py', 'replay_ops.py', 'PROTOCOL.md')
ROLES = ('AO_start', 'mixed4', 'mixed8')


def planned_search_seeds():
    from src.life.evaluate import life_seed

    values = []
    for generation in range(8):
        values.extend(life_seed(53234, 'gen', generation, i) for i in range(16))
        if generation in (0, 4, 7):
            values.extend(life_seed(53234, 'valid', generation, i) for i in range(16))
    for index in (0, 1):
        values.extend(life_seed(53234, 'final', index, i) for i in range(2))
    if len(values) != len(set(values)) or len(values) != 180:
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
    if (audit['status'] != 'passed' or audit['native_seed'] != 53234
            or audit['confirmation_seeds'] != list(range(52490000, 52490512))
            or audit['run_life_seeds'] != {'mixed': planned_search_seeds()}):
        raise ValueError('fresh audited schedule required')
    current_revision = subprocess.check_output(['git', 'rev-parse', 'HEAD'], cwd=ROOT, text=True).strip()
    if revision != current_revision or len(revision) != 40:
        raise ValueError('explicit current completed milestone revision required')
    baseline = read(BASELINE / 'protocol.json')
    for name, digest in baseline['production_pins'].items():
        if sha(ROOT / name) != digest:
            raise ValueError('production changed since ABI6 baseline: ' + name)
    if (read(BASELINE / 'budget.json')['status'] != 'complete' or
            read(MODULATION / 'terminal_recovery.json')['status'] != 'complete_saved_data_recovery'):
        raise ValueError('completed inherited baseline and modulation evidence required')
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
        'AO_checkpoint.pt': AO / 'runs/balanced/checkpoint.pt',
        'AO_config.yaml': AO / 'runs/balanced/config.yaml',
        'AO_determinism.json': AO / 'runs/balanced/determinism.json',
        'AO_protocol.json': AO / 'protocol.json',
        'AO_summary.json': AO / 'analysis_result/summary.json',
        'AO_startup_identity.json': AO / 'inputs/startup_identity.json',
        'patch_truth.json': ROOT / 'results/abi6_resource_patches_20261015/validation/truth/truth.json',
        'baseline_startup.json': BASELINE / 'startup.json',
        'baseline_protocol.json': BASELINE / 'protocol.json',
        'baseline_summary.json': BASELINE / 'summary.json',
        'modulation_protocol.json': MODULATION / 'protocol.json',
        'modulation_summary.json': MODULATION / 'summary.json',
        'modulation_recovery.json': MODULATION / 'terminal_recovery.json',
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
    patch = spec.World(**selection_worlds['patch'])
    definitions = {
        'patch': patch,
        'pool': spec.World(**selection_worlds['pool']),
        'persistent': spec.World(**selection_worlds['persistent']),
        'blink80_20': spec.World(**prior_worlds['blink80_20']['world']),
        'transfer': replace(patch, patch_count=4, R_min=3., R_max=5.,
                            patch_refill_fast=100., patch_refill_slow=200.),
    }
    worlds = {}
    for name, world in definitions.items():
        spec.V6.validate_world(world)
        worlds[name] = dict(abi=6, world=asdict(world), world_vector=spec.V6.pack_world(world).tolist(),
                            ledger_columns=list(spec.V6.LEDGER))
    cfg = OmegaConf.load(AO / 'runs/balanced/config.yaml')
    cfg.seed, cfg.threads = 53234, 2
    cfg.evolve.generations, cfg.evolve.heldout_every = 8, 4
    cfg.evolve.seed_genome = str(STUDY / population['population_file'])
    cfg.evolve.dup_rate, cfg.evolve.del_rate, cfg.evolve.dup_split = 0., 0., False
    cfg.evolve.recheck_k, cfg.evolve.recheck_lives, cfg.evolve.recheck_key = 64, 8, 'all'
    cfg.logging.output_dir = str(STUDY / 'runs/mixed')
    cfg.logging.checkpoint_every, cfg.logging.lineage = 1, 'all'
    cfg.life.abi, cfg.life.world, cfg.life.control = 6, 'catch_resource_patches_l4', 'resource_patch_continuation'
    cfg.life.T, cfg.life.founder_T, cfg.life.lives = 1024., 1024., 8
    cfg.life.T_choices, cfg.life.heldout = None, []
    cfg.life.flags, cfg.life.freeze_frac, cfg.life.t_open = [], None, 0.
    cfg.world, cfg.costs_life, cfg.envelope = {}, {}, {'enabled': False}
    cfg.population_start = loader_identity(population)
    cfg.retention_selection = selection_identity('mixed', selection_worlds)
    evaluator = LifeEvaluator(cfg, layout)
    if (asdict(evaluator.world()) != selection_worlds['patch'] or not evaluator.extinct_charge
            or not evaluator.fast or cfg.clones.every or cfg.clones.conditions or cfg.life.size_curve
            or cfg.life.final_fork_lives != 0
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
    compiled = read(STUDY / 'inputs/baseline_startup.json')['libraries']
    expected['kernels'] = {key: value['sha256'] for key, value in compiled.items()}
    if expected['flags'] != {key: value['flags'] for key, value in compiled.items()}:
        raise ValueError('native compiler flags changed')
    save(STUDY / 'inputs/startup_identity.json', dict(identity=expected,
        preexpected_fields='All identity fields predeclared; versions/libm/noise/golden copied from completed AO, sources and binary hashes from current integrated ABI6 and completed baseline.',
        prior_identity_sha256=sha(STUDY / 'inputs/AO_startup_identity.json'),
        changed_fields=[key for key in expected if expected[key] != prior_expected[key]],
        preparation_lives=0, preparation_builds=0, preparation_random_draws=0), exclusive=True)
    references = []
    for role in ROLES[:1]:
        path = STUDY / 'inputs' / (role + '.json')
        ref_layout, genome = Layout.load(path)
        if ref_layout.dims != layout.dims:
            raise ValueError('reference layout differs')
        references.append(dict(role=role, path=str(path.relative_to(STUDY)),
            file_sha256=sha(path), raw_sha256=raw_sha(genome.numpy()),
            source=str(sources[role + '.json'].relative_to(ROOT))))
    reservation = dict(status='reserved', native_seed=53234, seed_blocks=[[52490000, 52500000]],
        confirmation_seeds=audit['confirmation_seeds'], native_ids=audit['run_life_seeds']['mixed'],
        experiment='one bounded exploratory resource-patch mixed continuation', audit_sha256=sha(STUDY / 'namespace/seed_audit.json'))
    save(STUDY / 'reservation.json', reservation, exclusive=True)
    production = current_sources + [ROOT / 'src/life/kernel.c', ROOT / 'scripts/taskvar_gates.py']
    protocol = dict(study='Exploratory cumulative resource-patch continuation', roles=list(ROLES), runs=['mixed'],
        native_seed=53234, seeds=audit['confirmation_seeds'], worlds=worlds, selection_worlds=selection_worlds,
        configs={'mixed': dict(path='configs/mixed.yaml', sha256=sha(STUDY / 'configs/mixed.yaml'))},
        population_start=population, references=references, reference=references[0],
        research_lives=28214, startup_lives=8, total_calls=28222, confirmation_lives=7680,
        confirmation_startup_lives=4,
        search=dict(arms=['mixed'], generations=8, research_lives_per_arm=20534, startup_lives_per_arm=4,
                    initial_lives=8, recheck_lives=8, parents=32, offspring=224, midpoint=4,
                    growth_diagnostic_T=512, growth_diagnostic_lives=2),
        budget=dict(cpu_seconds=5280, wall_seconds=3480, total_cpu_seconds=5400, total_wall_seconds=3600,
                    preparation_cpu_allowance=120, preparation_wall_allowance=120,
                    search_cpu_seconds=4080, confirmation_cpu_seconds=1200, threads=2, workers=1,
                    cleanup_margin_seconds=10, rss_bytes=4*1024**3, minimum_available_bytes=4*1024**3,
                    address_space_bytes=8*1024**3),
        extinct_charge=True, status_bits=spec.STATUS, hash_names=list(spec.V6.HASHES),
        retention_margin_fraction=.1, expected_numerical_identity=expected,
        primary=dict(world='patch', new='mixed8', old='AO_start',
            outcomes=['refill-origin harvest', 'total captures', 'production_F', 'empty clicks', 'physical costs']),
        retention=dict(worlds=['pool', 'persistent', 'blink80_20'], references=['AO_start'],
                       retained_fraction=.9, diagnostic_only=True),
        transfer=dict(world='transfer', selection_exposure=False, endpoint_reselection=False,
            scope='One unchanged genome at reserved count4/radius3-5/refill100-200 joint combination; limited parameter transfer.'),
        exploratory_scope='Bounded exploration under explicit plan revision; no formal section0.4 admission claim.',
        source_pins={name: sha(STUDY / name) for name in SOURCE_FILES},
        input_pins={str(p.relative_to(STUDY)): sha(p) for folder in (STUDY/'inputs',STUDY/'configs')
                    for p in sorted(folder.rglob('*')) if p.is_file()},
        original_input_pins={str(p.relative_to(ROOT)): sha(p) for p in sources.values()},
        production_pins={str(p.relative_to(ROOT)): sha(p) for p in production},
        seed_audit_sha256=sha(STUDY / 'namespace/seed_audit.json'), reservation_sha256=sha(STUDY / 'reservation.json'),
        source_revision=revision, engine_revision=baseline['source_revision'],
        limitations=[
            'One inherited population and one search; confirmation lives are not independent evolutionary searches.',
            'Generation8 is primary; generation4 is a passive observation, never a replacement endpoint.',
            'Fixed mixed evaluation does not establish an optimal allocation or guarantee older-task retention.',
            'F gains can reflect economy; acquisition, initial/refill origins, physical costs and empty clicks are separate.',
            'Native patch stock/source/FIFO counters do not establish revisit order, memory or learned recovery rates.',
            'Same unchanged endpoints across worlds; reserved joint combination is narrow parameter transfer, not broad generality.',
            'Native search retains aggregate guard/invalid health, not every per-life ledger; confirmation retains all rows.',
            'No prices, local cell rules, prescribed behaviors, global channels, or population-responsive worlds change.',
            'Exploratory exception is explicit;512 confirmation lives do not supply missing formal admission controls.'])
    save(STUDY / 'protocol.json', protocol, exclusive=True)
    save(STUDY / 'READY.json', dict(status='prepared', protocol_sha256=sha(STUDY / 'protocol.json'),
        preparation_lives=0, preparation_builds=0, preparation_random_draws=0), exclusive=True)
    print({'status': 'prepared', 'total_calls': 28222, 'protocol_sha256': sha(STUDY / 'protocol.json')})


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--source-revision', required=True)
    prepare(parser.parse_args().source_revision)
