"""Prepare AL by importing the exact retained population; no life or genetic draw."""
from __future__ import annotations

import argparse
import json
import os
import shutil
import sys
from dataclasses import asdict, replace

os.environ.setdefault('ATEN_CPU_CAPABILITY', 'avx2')
sys.dont_write_bytecode = True
from common import ROOT, STUDY, raw_sha, read, save, sha  # noqa: E402

sys.path.insert(0, str(ROOT))
ARMS = ['persistent_control', 'balanced_mixture']
ROLES = ['AI_control_start', 'persistent_control_final', 'mixture_final']
AI = ROOT / 'results/exploratory_reserve_replication_20261014'
AK = ROOT / 'results/retention_frontier_20261015'
SOURCE_FILES = ['common.py', 'prepare.py', 'monitor.py', 'population_loader.py', 'selection.py',
                'search.py', 'measure.py', 'analyze.py', 'native_replay.py', 'replay_ops.py']


def search_config(seed, record, arm, worlds):
    from omegaconf import OmegaConf
    from population_loader import loader_identity
    from selection import selection_identity

    cfg = OmegaConf.load(AI / 'runs/control/config.yaml')
    if 'exploratory_reserve' in cfg:
        del cfg['exploratory_reserve']
    cfg.seed, cfg.threads = seed, 2
    cfg.evolve.generations, cfg.evolve.heldout_every = 4, 4
    cfg.evolve.seed_genome = str(STUDY / record['population_file'])
    cfg.evolve.dup_rate, cfg.evolve.del_rate, cfg.evolve.dup_split = 0., 0., False
    cfg.evolve.recheck_k, cfg.evolve.recheck_lives, cfg.evolve.recheck_key = 64, 4, 'all'
    cfg.logging.output_dir = str(STUDY / 'runs' / arm)
    cfg.logging.checkpoint_every, cfg.logging.lineage = 1, 'all'
    cfg.life.abi, cfg.life.control, cfg.life.lives = 3, 'retention_selection_AL', 4
    cfg.life.T, cfg.life.T_choices, cfg.life.heldout = 1024, None, []
    cfg.life.flags, cfg.life.freeze_frac, cfg.life.t_open = [], None, 0.
    cfg.costs_life, cfg.envelope = {}, {'enabled': False}
    cfg.population_start = loader_identity(record)
    cfg.retention_selection = selection_identity(arm, worlds)
    return cfg


def prepare():
    if any((STUDY / name).exists() for name in ('protocol.json', 'inputs', 'configs', 'release.json', 'attempt.json')):
        raise ValueError('one-time preparation refuses preexisting input/runtime files')
    approval = read(STUDY / 'preparation_acceptance.json')
    if approval['status'] != 'accepted_by_root':
        raise ValueError('root source and scope review required')
    for name, digest in approval['review_pins'].items():
        if sha(ROOT / name) != digest:
            raise ValueError('changed review ' + name)
    source_pins = {name: sha(STUDY / name) for name in SOURCE_FILES}
    if source_pins != approval['source_pins']:
        raise ValueError('reviewed source changed')
    audit = read(ROOT / approval['seed_audit_path'])
    if (audit['status'] != 'passed' or audit['native_seed'] != 53229
            or audit['confirmation_seeds'] != list(range(52390000, 52390256))):
        raise ValueError('fresh exact namespace audit required')
    import torch
    from omegaconf import OmegaConf
    from population_loader import read_population

    from src import checkpoint
    from src.evolve import fill
    from src.genome import Layout
    from src.life import spec
    from src.life.evaluate import LifeEvaluator

    layout, endpoint = Layout.load(AI / 'runs/control/best_genome.json')
    saved = read(AI / 'runs/control/population.json')
    table = torch.stack([layout.from_dict(row) for row in saved['genomes']])
    state = checkpoint.load(AI / 'runs/control/checkpoint.pt')
    prior = read(AI / 'analysis_result/summary.json')['native_audit']['runs']['control']
    if (saved['dims'] != layout.dims.__dict__ or table.shape != (32, 875) or table.dtype != torch.float32
            or not bool(torch.isfinite(table).all()) or len(set(saved['ids'])) != 32
            or saved['ids'] != state['state']['ids'].tolist() or state['state']['generation'] != 4
            or table.numpy().tobytes() != state['state']['population'].numpy().tobytes()
            or table[0].numpy().tobytes() != endpoint.numpy().tobytes()
            or prior['checkpoint_sha256'] != sha(AI / 'runs/control/checkpoint.pt')
            or not prior['all_final_population_rows_bound']
            or not prior['genetic_replay']['raw_population_replay_bitwise']):
        raise ValueError('exact ordered full AI population/checkpoint/replay required')
    checkpoint.validate(state, OmegaConf.load(AI / 'runs/control/config.yaml'),
                        read(AI / 'runs/control/determinism.json'))
    hashes = [raw_sha(row.numpy()) for row in table]
    record = {'population_file': 'inputs/input_population.json',
        'file_sha256': sha(AI / 'runs/control/population.json'), 'population_raw_sha256': raw_sha(table.numpy()),
        'shape': [32, 875], 'old_ids': saved['ids'], 'new_ids': list(range(32)), 'row_sha256': hashes,
        'old_to_new': [{'old_id': old, 'new_id': i, 'row': i, 'raw_sha256': hashes[i]}
                       for i, old in enumerate(saved['ids'])]}
    original = {
        'input_population.json': AI / 'runs/control/population.json',
        'AI_control_start.json': AI / 'runs/control/best_genome.json',
        'AI_checkpoint.pt': AI / 'runs/control/checkpoint.pt',
        'AI_determinism.json': AI / 'runs/control/determinism.json',
        'AI_config.yaml': AI / 'runs/control/config.yaml',
        'AI_summary.json': AI / 'analysis_result/summary.json',
        'persistent_protocol.json': AI / 'protocol.json',
        'startup_identity.json': AK / 'inputs/startup_identity.json',
        'visibility_truth.json': AK / 'inputs/visibility_truth.json',
        'AK_protocol.json': AK / 'protocol.json',
        'seed_audit.json': ROOT / approval['seed_audit_path'],
    }
    inputs = STUDY / 'inputs'
    inputs.mkdir()
    for name, path in original.items():
        shutil.copyfile(path, inputs / name)
    save(inputs / 'population_import.json', record, exclusive=True)
    worlds = read(AK / 'protocol.json')['worlds']
    selection_worlds = {name: worlds[name]['world'] for name in ('pool', 'persistent')}
    worlds = {name: worlds[name] for name in ('pool', 'persistent', 'blink80_5')}
    combo = replace(spec.World(**worlds['blink80_5']['world']), tau_turn=100.)
    worlds['turn100_blink80_5'] = {'abi': 4, 'world': asdict(combo),
        'world_vector': spec.V4.pack_world(combo).tolist(), 'ledger_columns': list(spec.V4.LEDGER)}
    configs = {}
    for arm in ARMS:
        cfg = search_config(53229, record, arm, selection_worlds)
        evaluator = LifeEvaluator(cfg, layout)
        if (asdict(evaluator.world()) != selection_worlds['persistent'] or not evaluator.extinct_charge
                or not evaluator.fast or cfg.clones.every or cfg.clones.conditions or cfg.life.size_curve
                or (cfg.evolve.mu, cfg.evolve.lam, cfg.life.valid_lives, cfg.life.final_lives,
                    cfg.life.final_top) != (32, 224, 16, 2, 1)):
            raise ValueError('exact ordinary native scope/world required')
        imported = read_population(inputs / 'input_population.json', layout, record)
        generator = torch.Generator().manual_seed(53229)
        before, ops = generator.get_state().clone(), []
        initialized = fill(imported, 32, layout, generator, cfg.evolve, ops=ops)
        if (initialized.numpy().tobytes() != table.numpy().tobytes() or ops
                or not torch.equal(before, generator.get_state())):
            raise ValueError('full-population import must consume no genetics/RNG')
        path = STUDY / 'configs' / f'{arm}.yaml'
        path.parent.mkdir(exist_ok=True)
        path.write_text(OmegaConf.to_yaml(cfg, resolve=True))
        configs[arm] = {'path': str(path.relative_to(STUDY)), 'sha256': sha(path)}
    shutil.copyfile(STUDY / configs[ARMS[0]]['path'], inputs / 'config.yaml')
    expected = read(inputs / 'startup_identity.json')['identity']
    production = sorted((ROOT / 'src').rglob('*.py')) + [ROOT / 'src/life/kernel.c', ROOT / 'scripts/taskvar_gates.py']
    for name, digest in expected['sources'].items():
        if sha(ROOT / name) != digest:
            raise ValueError('production differs from retained numerical identity')
    protocol = {'study': 'AL two-context retention selection', 'roles': ROLES, 'runs': ARMS,
        'native_seed': 53229, 'seeds': audit['confirmation_seeds'], 'worlds': worlds,
        'selection_worlds': selection_worlds, 'configs': configs, 'population_start': record,
        'reference': {'role': ROLES[0], 'path': 'inputs/AI_control_start.json',
                      'file_sha256': sha(inputs / 'AI_control_start.json'), 'raw_sha256': hashes[0],
                      'source': str(original['AI_control_start.json'].relative_to(ROOT))},
        'research_lives': 13388, 'startup_lives': 8, 'total_calls': 13396,
        'confirmation_lives': 3072, 'confirmation_startup_lives': 4,
        'search': {'arms': ARMS, 'generations': 4, 'research_lives_per_arm': 5158,
                   'startup_lives_per_arm': 2, 'initial_lives': 4, 'recheck_lives': 4,
                   'parents': 32, 'offspring': 224},
        'budget': {'cpu_seconds': 5400, 'wall_seconds': 3600, 'search_cpu_seconds': 3600,
                   'confirmation_cpu_seconds': 1800, 'threads': 2, 'workers': 1, 'cleanup_margin_seconds': 10,
                   'rss_bytes': 4 * 1024**3, 'minimum_available_bytes': 4 * 1024**3,
                   'address_space_bytes': 8 * 1024**3},
        'extinct_charge': True, 'status_bits': spec.STATUS, 'hash_names': list(spec.V3.HASHES),
        'retention_margin_fraction': .1,
        'primary': [{'world': 'pool', 'new': ROLES[2], 'old': ROLES[1], 'metric': 'captures'}],
        'expected_numerical_identity': expected, 'source_pins': source_pins,
        'input_pins': {str(path.relative_to(STUDY)): sha(path) for folder in (inputs, STUDY / 'configs')
                       for path in sorted(folder.rglob('*')) if path.is_file()},
        'original_input_pins': {str(path.relative_to(ROOT)): sha(path) for path in original.values()},
        'production_pins': {str(path.relative_to(ROOT)): sha(path) for path in production},
        'review_pins': approval['review_pins'], 'prior_commit': approval['prior_commit'],
        'limitations': ['One chosen lineage and one paired search are not policy replication.',
            'Raw mean F may reward economy while reducing captures; report both worlds separately.',
            'Relative benefit over control is not actual recovery from the starting genome.',
            'A conventional 10% retention margin permits some loss; null loss is not retention.',
            'Combined turn/blink case is excluded from selection and endpoint choice; no broad generalization claim.',
            'Whole-genome development comparisons do not establish circuit mechanism, memory or prediction.',
            'Equal life budgets need not consume equal CPU. No automatic retry or scope extension.']}
    save(STUDY / 'protocol.json', protocol, exclusive=True)
    print(json.dumps({'status': 'prepared', 'protocol_sha256': sha(STUDY / 'protocol.json'),
                      'genetic_draws': 0, 'simulation_calls': 0, 'imported_rows': 32}))


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--prepare', action='store_true')
    if parser.parse_args().prepare:
        prepare()
    else:
        print(json.dumps({'status': 'source_only', 'research_lives': 13388, 'startup_lives': 8}))
