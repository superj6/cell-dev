"""Prepare AO from the exact AN final population; no life or genetic draw."""
from __future__ import annotations

import argparse
import json
import os
import shutil
import sys
from dataclasses import asdict

os.environ.setdefault('ATEN_CPU_CAPABILITY', 'avx2')
sys.dont_write_bytecode = True
from common import ROOT, STUDY, raw_sha, read, save, sha  # noqa: E402

sys.path.insert(0, str(ROOT))
ARMS = ['unchanged', 'balanced']
ROLES = ['AM_reference', 'AN_start', 'unchanged8', 'unchanged24', 'balanced8', 'balanced24']
AN = ROOT / 'results/occlusion_acquisition_20261015'
SOURCE_FILES = ['common.py', 'prepare.py', 'monitor.py', 'population_loader.py', 'selection.py',
                'search.py', 'measure.py', 'analyze.py', 'native_replay.py', 'replay_ops.py']


def planned_search_seeds(seed):
    """Unique native IDs, with the deliberate full/half final reuse counted once."""
    from src.life.evaluate import life_seed

    values = []
    for generation in range(24):
        values.extend(life_seed(seed, 'gen', generation, i) for i in range(16))
        if generation in (0, 4, 8, 12, 16, 20, 23):
            values.extend(life_seed(seed, 'valid', generation, i) for i in range(16))
    for index in (0, 1):
        values.extend(life_seed(seed, 'final', index, i) for i in range(2))
    if len(values) != len(set(values)) or len(values) != 500:
        raise ValueError('native life ID scope differs')
    return values


def search_config(seed, record, arm, worlds):
    from omegaconf import OmegaConf
    from population_loader import loader_identity
    from selection import selection_identity

    cfg = OmegaConf.load(AN / 'runs/acquisition/config.yaml')
    if 'exploratory_reserve' in cfg:
        del cfg['exploratory_reserve']
    cfg.seed, cfg.threads = seed, 2
    cfg.evolve.generations, cfg.evolve.heldout_every = 24, 4
    cfg.evolve.seed_genome = str(STUDY / record['population_file'])
    cfg.evolve.dup_rate, cfg.evolve.del_rate, cfg.evolve.dup_split = 0., 0., False
    cfg.evolve.recheck_k, cfg.evolve.recheck_lives, cfg.evolve.recheck_key = 64, 8, 'all'
    cfg.logging.output_dir = str(STUDY / 'runs' / arm)
    cfg.logging.checkpoint_every, cfg.logging.lineage = 1, 'all'
    cfg.life.abi, cfg.life.control, cfg.life.lives = 4, 'retained_depth_AO', 8
    cfg.life.T, cfg.life.T_choices, cfg.life.heldout = 1024, None, []
    cfg.life.flags, cfg.life.freeze_frac, cfg.life.t_open = [], None, 0.
    cfg.costs_life, cfg.envelope = {}, {'enabled': False}
    cfg.population_start = loader_identity(record)
    cfg.retention_selection = selection_identity(arm, worlds)
    return cfg



def retained_worlds(prior_protocol, spec):
    """All five contexts are copied unchanged and already development-known."""
    import copy

    worlds = copy.deepcopy(prior_protocol['worlds'])
    if list(worlds) != ['pool', 'persistent', 'blink80_5', 'blink80_20', 'turn100_blink80_20']:
        raise ValueError('exact five AN development worlds required')
    for name, item in worlds.items():
        abi = spec.V3 if name in ('pool', 'persistent') else spec.V4
        world = spec.World(**item['world'])
        abi.validate_world(world)
        if (item['abi'] != abi.version or world.R_cap != 500 or world.T != 1024
                or abi.pack_world(world).tolist() != item['world_vector']
                or list(abi.LEDGER) != item['ledger_columns']):
            raise ValueError('inherited physical world, price or ABI differs')
    return worlds


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
    if (audit['status'] != 'passed' or audit['native_seed'] != 53232
            or audit['confirmation_seeds'] != list(range(52420000, 52420512))):
        raise ValueError('fresh exact namespace audit required')
    import torch
    from omegaconf import OmegaConf
    from population_loader import read_population

    from src import checkpoint
    from src.evolve import fill
    from src.genome import Layout
    from src.life import spec
    from src.life.evaluate import LifeEvaluator

    if audit['run_life_seeds'] != {arm: planned_search_seeds(53232) for arm in ARMS}:
        raise ValueError('audited native life schedule differs')
    prior_protocol = read(AN / 'protocol.json')
    prior_summary = read(AN / 'analysis_result/summary.json')
    prior_audit = read(AN / 'terminal_review/native/complete_native_audit.json')
    if (prior_summary['status'] != 'complete' or prior_audit['status'] != 'passed'
            or prior_summary['protocol_sha256'] != sha(AN / 'protocol.json')
            or prior_audit['protocol_sha256'] != sha(AN / 'protocol.json')):
        raise ValueError('complete AN scientific and genetic evidence required')
    layout, endpoint = Layout.load(AN / 'runs/acquisition/best_genome.json')
    saved = read(AN / 'runs/acquisition/population.json')
    table = torch.stack([layout.from_dict(row) for row in saved['genomes']])
    state = checkpoint.load(AN / 'runs/acquisition/checkpoint.pt')
    prior = prior_audit['runs']['acquisition']
    if (saved['dims'] != layout.dims.__dict__ or table.shape != (32, 875) or table.dtype != torch.float32
            or not bool(torch.isfinite(table).all()) or len(set(saved['ids'])) != 32
            or saved['ids'] != state['state']['ids'].tolist() or state['state']['generation'] != 8
            or table.numpy().tobytes() != state['state']['population'].numpy().tobytes()
            or table[0].numpy().tobytes() != endpoint.numpy().tobytes()
            or prior['checkpoint_sha256'] != sha(AN / 'runs/acquisition/checkpoint.pt')
            or not prior['all_32_final_rows_bound']
            or not prior['genetic_replay']['raw_population_replay_bitwise']):
        raise ValueError('exact ordered full AN final population/checkpoint/replay required')
    checkpoint.validate(state, OmegaConf.load(AN / 'runs/acquisition/config.yaml'),
                        read(AN / 'runs/acquisition/determinism.json'))
    hashes = [raw_sha(row.numpy()) for row in table]
    record = {'population_file': 'inputs/input_population.json',
        'file_sha256': sha(AN / 'runs/acquisition/population.json'), 'population_raw_sha256': raw_sha(table.numpy()),
        'shape': [32, 875], 'old_ids': saved['ids'], 'new_ids': list(range(32)), 'row_sha256': hashes,
        'old_to_new': [{'old_id': old, 'new_id': i, 'row': i, 'raw_sha256': hashes[i]}
                       for i, old in enumerate(saved['ids'])]}
    ancestral_layout, ancestral = Layout.load(AN / 'inputs/AM_current_start.json')
    if ancestral_layout.dims != layout.dims or ancestral.shape != (875,) or not bool(torch.isfinite(ancestral).all()):
        raise ValueError('exact immutable AM reference layout required')
    original = {
        'input_population.json': AN / 'runs/acquisition/population.json',
        'AN_start.json': AN / 'runs/acquisition/best_genome.json',
        'AM_reference.json': AN / 'inputs/AM_current_start.json',
        'AN_checkpoint.pt': AN / 'runs/acquisition/checkpoint.pt',
        'AN_determinism.json': AN / 'runs/acquisition/determinism.json',
        'AN_config.yaml': AN / 'runs/acquisition/config.yaml',
        'AN_summary.json': AN / 'analysis_result/summary.json',
        'AN_native_audit.json': AN / 'terminal_review/native/complete_native_audit.json',
        'AN_protocol.json': AN / 'protocol.json',
        'persistent_protocol.json': AN / 'inputs/persistent_protocol.json',
        'startup_identity.json': AN / 'inputs/startup_identity.json',
        'visibility_truth.json': AN / 'inputs/visibility_truth.json',
        'seed_audit.json': ROOT / approval['seed_audit_path'],
    }
    inputs = STUDY / 'inputs'
    inputs.mkdir()
    for name, path in original.items():
        shutil.copyfile(path, inputs / name)
    save(inputs / 'population_import.json', record, exclusive=True)
    worlds = retained_worlds(prior_protocol, spec)
    selection_worlds = {name: worlds[name]['world'] for name in ('pool', 'persistent', 'blink80_20')}
    configs = {}
    for arm in ARMS:
        cfg = search_config(53232, record, arm, selection_worlds)
        evaluator = LifeEvaluator(cfg, layout)
        if (asdict(evaluator.world()) != selection_worlds['persistent'] or not evaluator.extinct_charge
                or not evaluator.fast or cfg.clones.every or cfg.clones.conditions or cfg.life.size_curve
                or (cfg.evolve.mu, cfg.evolve.lam, cfg.life.valid_lives, cfg.life.final_lives,
                    cfg.life.final_top) != (32, 224, 16, 2, 1)):
            raise ValueError('exact ordinary native scope/world required')
        imported = read_population(inputs / 'input_population.json', layout, record)
        generator = torch.Generator().manual_seed(53232)
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
    protocol = {'study': 'AO retained-depth comparison', 'roles': ROLES, 'runs': ARMS,
        'native_seed': 53232, 'seeds': audit['confirmation_seeds'], 'worlds': worlds,
        'selection_worlds': selection_worlds, 'configs': configs, 'population_start': record,
        'reference': {'role': ROLES[1], 'path': 'inputs/AN_start.json',
                      'file_sha256': sha(inputs / 'AN_start.json'), 'raw_sha256': hashes[0],
                      'source': str(original['AN_start.json'].relative_to(ROOT))},
        'ancestral_reference': {'role': ROLES[0], 'path': 'inputs/AM_reference.json',
                      'file_sha256': sha(inputs / 'AM_reference.json'), 'raw_sha256': raw_sha(ancestral.numpy()),
                      'source': str(original['AM_reference.json'].relative_to(ROOT))},
        'research_lives': 138476, 'startup_lives': 12, 'total_calls': 138488,
        'confirmation_lives': 15360, 'confirmation_startup_lives': 4,
        'search': {'arms': ARMS, 'generations': 24, 'research_lives_per_arm': 61558,
                   'startup_lives_per_arm': 4, 'initial_lives': 8, 'recheck_lives': 8,
                   'parents': 32, 'offspring': 224},
        'budget': {'cpu_seconds': 28800, 'wall_seconds': 14400, 'search_cpu_seconds': 24000,
                   'confirmation_cpu_seconds': 4800, 'threads': 2, 'workers': 1, 'cleanup_margin_seconds': 10,
                   'rss_bytes': 4 * 1024**3, 'minimum_available_bytes': 4 * 1024**3,
                   'address_space_bytes': 8 * 1024**3},
        'extinct_charge': True, 'status_bits': spec.STATUS, 'hash_names': list(spec.V3.HASHES),
        'retention_margin_fraction': .1,
        'primary': [{'world': name, 'new': ROLES[5], 'old': ROLES[3], 'metric': 'captures'}
                    for name in ('pool', 'blink80_20')],
        'primary_noninferiority': {'world': 'blink80_20', 'new': ROLES[5], 'old': ROLES[3],
                                  'metric': 'captures', 'retained_fraction': .9},
        'expected_numerical_identity': expected, 'source_pins': source_pins,
        'input_pins': {str(path.relative_to(STUDY)): sha(path) for folder in (inputs, STUDY / 'configs')
                       for path in sorted(folder.rglob('*')) if path.is_file()},
        'original_input_pins': {str(path.relative_to(ROOT)): sha(path) for path in original.values()},
        'production_pins': {str(path.relative_to(ROOT)): sha(path) for path in production},
        'review_pins': approval['review_pins'], 'prior_commit': approval['prior_commit'],
        'limitations': ['One deliberately selected population and one paired continuation do not establish general policy reliability.',
            'AN final survivors were selected after observing acquisition and old-task loss; this is an explicitly chosen retention case.',
            'Both arms use unchanged prices, local rules, genetic operators and known physical worlds. Only fixed generation-world allocation differs.',
            'The balanced arm switches absolute indices 2 and 6 from blink80_20 to POOL; other paired world positions and all native life IDs remain shared.',
            'Generation 8 and generation 24 rank0 endpoints from both arms are fixed before confirmation, without replacement by a favorable checkpoint.',
            'All five confirmation worlds are development-known. This study does not test unseen-world generalization.',
            'A 10% noninferiority or retention margin permits actual loss. Both raw paired differences and margin vectors remain visible.',
            'Fitness gains may reflect economy. Captures, misses, clicks and all physical costs are reported separately.',
            'The two arms have equal life counts, not necessarily equal CPU. Hard phase and memory caps decide completion, without retry or scope extension.',
            'Longer duration is observed within each branch, not independently randomized; no causal depth-superiority or memory claim follows.']}
    save(STUDY / 'protocol.json', protocol, exclusive=True)
    print(json.dumps({'status': 'prepared', 'protocol_sha256': sha(STUDY / 'protocol.json'),
                      'genetic_draws': 0, 'simulation_calls': 0, 'imported_rows': 32}))


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--prepare', action='store_true')
    if parser.parse_args().prepare:
        prepare()
    else:
        print(json.dumps({'status': 'source_only', 'research_lives': 138476, 'startup_lives': 12}))
