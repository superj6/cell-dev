"""Prepare AN from the exact AM current-value population; no life or genetic draw."""
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
ARMS = ['acquisition']
ROLES = ['AM_current_start', 'generation4', 'generation8']
AM = ROOT / 'results/capture_value_selection_20261015'
SOURCE_FILES = ['common.py', 'prepare.py', 'monitor.py', 'population_loader.py', 'selection.py',
                'search.py', 'measure.py', 'analyze.py', 'native_replay.py', 'replay_ops.py']


def planned_search_seeds(seed):
    """Unique native IDs, with the deliberate full/half final reuse counted once."""
    from src.life.evaluate import life_seed

    values = []
    for generation in range(8):
        values.extend(life_seed(seed, 'gen', generation, i) for i in range(16))
        if generation in (0, 4, 7):
            values.extend(life_seed(seed, 'valid', generation, i) for i in range(16))
    for index in (0, 1):
        values.extend(life_seed(seed, 'final', index, i) for i in range(2))
    if len(values) != len(set(values)) or len(values) != 180:
        raise ValueError('native life ID scope differs')
    return values


def search_config(seed, record, arm, worlds):
    from omegaconf import OmegaConf
    from population_loader import loader_identity
    from selection import selection_identity

    cfg = OmegaConf.load(AM / 'runs/current_value/config.yaml')
    if 'exploratory_reserve' in cfg:
        del cfg['exploratory_reserve']
    cfg.seed, cfg.threads = seed, 2
    cfg.evolve.generations, cfg.evolve.heldout_every = 8, 4
    cfg.evolve.seed_genome = str(STUDY / record['population_file'])
    cfg.evolve.dup_rate, cfg.evolve.del_rate, cfg.evolve.dup_split = 0., 0., False
    cfg.evolve.recheck_k, cfg.evolve.recheck_lives, cfg.evolve.recheck_key = 64, 8, 'all'
    cfg.logging.output_dir = str(STUDY / 'runs' / arm)
    cfg.logging.checkpoint_every, cfg.logging.lineage = 1, 'all'
    cfg.life.abi, cfg.life.control, cfg.life.lives = 4, 'occlusion_acquisition_AN', 8
    cfg.life.T, cfg.life.T_choices, cfg.life.heldout = 1024, None, []
    cfg.life.flags, cfg.life.freeze_frac, cfg.life.t_open = [], None, 0.
    cfg.costs_life, cfg.envelope = {}, {'enabled': False}
    cfg.population_start = loader_identity(record)
    cfg.retention_selection = selection_identity(arm, worlds)
    return cfg



def acquisition_worlds(prior_protocol, spec):
    """Preserve old contexts and change only declared visibility/turn constants."""
    import copy

    prior = prior_protocol['worlds']
    if list(prior) != ['pool', 'persistent', 'blink80_5', 'turn100_blink80_5']:
        raise ValueError('exact four AM development worlds required')
    for name, item in prior.items():
        abi = spec.V3 if item['abi'] == 3 else spec.V4
        world = spec.World(**item['world'])
        abi.validate_world(world)
        if (item['abi'] != (3 if name in ('pool', 'persistent') else 4)
                or world.R_cap != 500 or world.T != 1024
                or abi.pack_world(world).tolist() != item['world_vector']
                or list(abi.LEDGER) != item['ledger_columns']):
            raise ValueError('exact inherited physical world, price or ABI differs')
    worlds = {name: copy.deepcopy(prior[name]) for name in ('pool', 'persistent', 'blink80_5')}
    expected_blink = {**prior['persistent']['world'], 'visibility_mode': 2,
                      'visibility_on': 80., 'visibility_off': 5., 'visibility_low': 0.}
    if prior['blink80_5']['world'] != expected_blink:
        raise ValueError('inherited blink must differ only by declared visibility fields')
    for name, turn in (('blink80_20', 200.), ('turn100_blink80_20', 100.)):
        values = {**prior['blink80_5']['world'], 'visibility_off': 20., 'tau_turn': turn}
        world = spec.World(**values)
        spec.V4.validate_world(world)
        worlds[name] = {'abi': 4, 'world': values, 'world_vector': spec.V4.pack_world(world).tolist(),
                        'ledger_columns': list(spec.V4.LEDGER)}
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
    if (audit['status'] != 'passed' or audit['native_seed'] != 53231
            or audit['confirmation_seeds'] != list(range(52410000, 52410512))):
        raise ValueError('fresh exact namespace audit required')
    import torch
    from omegaconf import OmegaConf
    from population_loader import read_population

    from src import checkpoint
    from src.evolve import fill
    from src.genome import Layout
    from src.life import spec
    from src.life.evaluate import LifeEvaluator

    if audit['run_life_seeds'] != {arm: planned_search_seeds(53231) for arm in ARMS}:
        raise ValueError('audited native life schedule differs')
    prior_protocol = read(AM / 'protocol.json')
    prior_summary = read(AM / 'analysis_result/summary.json')
    prior_audit = read(AM / 'terminal_review/native/complete_native_audit.json')
    if (prior_summary['status'] != 'complete' or prior_audit['status'] != 'passed'
            or prior_summary['protocol_sha256'] != sha(AM / 'protocol.json')
            or prior_audit['protocol_sha256'] != sha(AM / 'protocol.json')):
        raise ValueError('complete AM scientific and genetic evidence required')
    layout, endpoint = Layout.load(AM / 'runs/current_value/best_genome.json')
    saved = read(AM / 'runs/current_value/population.json')
    table = torch.stack([layout.from_dict(row) for row in saved['genomes']])
    state = checkpoint.load(AM / 'runs/current_value/checkpoint.pt')
    prior = prior_audit['runs']['current_value']
    if (saved['dims'] != layout.dims.__dict__ or table.shape != (32, 875) or table.dtype != torch.float32
            or not bool(torch.isfinite(table).all()) or len(set(saved['ids'])) != 32
            or saved['ids'] != state['state']['ids'].tolist() or state['state']['generation'] != 4
            or table.numpy().tobytes() != state['state']['population'].numpy().tobytes()
            or table[0].numpy().tobytes() != endpoint.numpy().tobytes()
            or prior['checkpoint_sha256'] != sha(AM / 'runs/current_value/checkpoint.pt')
            or not prior['all_32_final_rows_bound']
            or not prior['genetic_replay']['raw_population_replay_bitwise']):
        raise ValueError('exact ordered full AM current-value population/checkpoint/replay required')
    checkpoint.validate(state, OmegaConf.load(AM / 'runs/current_value/config.yaml'),
                        read(AM / 'runs/current_value/determinism.json'))
    hashes = [raw_sha(row.numpy()) for row in table]
    record = {'population_file': 'inputs/input_population.json',
        'file_sha256': sha(AM / 'runs/current_value/population.json'), 'population_raw_sha256': raw_sha(table.numpy()),
        'shape': [32, 875], 'old_ids': saved['ids'], 'new_ids': list(range(32)), 'row_sha256': hashes,
        'old_to_new': [{'old_id': old, 'new_id': i, 'row': i, 'raw_sha256': hashes[i]}
                       for i, old in enumerate(saved['ids'])]}
    original = {
        'input_population.json': AM / 'runs/current_value/population.json',
        'AM_current_start.json': AM / 'runs/current_value/best_genome.json',
        'AM_checkpoint.pt': AM / 'runs/current_value/checkpoint.pt',
        'AM_determinism.json': AM / 'runs/current_value/determinism.json',
        'AM_config.yaml': AM / 'runs/current_value/config.yaml',
        'AM_summary.json': AM / 'analysis_result/summary.json',
        'AM_native_audit.json': AM / 'terminal_review/native/complete_native_audit.json',
        'AM_protocol.json': AM / 'protocol.json',
        'persistent_protocol.json': AM / 'inputs/persistent_protocol.json',
        'startup_identity.json': AM / 'inputs/startup_identity.json',
        'visibility_truth.json': AM / 'inputs/visibility_truth.json',
        'seed_audit.json': ROOT / approval['seed_audit_path'],
    }
    inputs = STUDY / 'inputs'
    inputs.mkdir()
    for name, path in original.items():
        shutil.copyfile(path, inputs / name)
    save(inputs / 'population_import.json', record, exclusive=True)
    worlds = acquisition_worlds(prior_protocol, spec)
    selection_worlds = {name: worlds[name]['world'] for name in ('pool', 'persistent', 'blink80_20')}
    configs = {}
    for arm in ARMS:
        cfg = search_config(53231, record, arm, selection_worlds)
        evaluator = LifeEvaluator(cfg, layout)
        if (asdict(evaluator.world()) != selection_worlds['persistent'] or not evaluator.extinct_charge
                or not evaluator.fast or cfg.clones.every or cfg.clones.conditions or cfg.life.size_curve
                or (cfg.evolve.mu, cfg.evolve.lam, cfg.life.valid_lives, cfg.life.final_lives,
                    cfg.life.final_top) != (32, 224, 16, 2, 1)):
            raise ValueError('exact ordinary native scope/world required')
        imported = read_population(inputs / 'input_population.json', layout, record)
        generator = torch.Generator().manual_seed(53231)
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
    protocol = {'study': 'AN occlusion acquisition', 'roles': ROLES, 'runs': ARMS,
        'native_seed': 53231, 'seeds': audit['confirmation_seeds'], 'worlds': worlds,
        'selection_worlds': selection_worlds, 'configs': configs, 'population_start': record,
        'reference': {'role': ROLES[0], 'path': 'inputs/AM_current_start.json',
                      'file_sha256': sha(inputs / 'AM_current_start.json'), 'raw_sha256': hashes[0],
                      'source': str(original['AM_current_start.json'].relative_to(ROOT))},
        'research_lives': 28214, 'startup_lives': 8, 'total_calls': 28222,
        'confirmation_lives': 7680, 'confirmation_startup_lives': 4,
        'search': {'arms': ARMS, 'generations': 8, 'research_lives_per_arm': 20534,
                   'startup_lives_per_arm': 4, 'initial_lives': 8, 'recheck_lives': 8,
                   'parents': 32, 'offspring': 224},
        'budget': {'cpu_seconds': 10800, 'wall_seconds': 5400, 'search_cpu_seconds': 7200,
                   'confirmation_cpu_seconds': 3600, 'threads': 2, 'workers': 1, 'cleanup_margin_seconds': 10,
                   'rss_bytes': 4 * 1024**3, 'minimum_available_bytes': 4 * 1024**3,
                   'address_space_bytes': 8 * 1024**3},
        'extinct_charge': True, 'status_bits': spec.STATUS, 'hash_names': list(spec.V3.HASHES),
        'retention_margin_fraction': .1,
        'primary': [{'world': 'blink80_20', 'new': ROLES[2], 'old': ROLES[0], 'metric': 'captures'}],
        'expected_numerical_identity': expected, 'source_pins': source_pins,
        'input_pins': {str(path.relative_to(STUDY)): sha(path) for folder in (inputs, STUDY / 'configs')
                       for path in sorted(folder.rglob('*')) if path.is_file()},
        'original_input_pins': {str(path.relative_to(ROOT)): sha(path) for path in original.values()},
        'production_pins': {str(path.relative_to(ROOT)): sha(path) for path in production},
        'review_pins': approval['review_pins'], 'prior_commit': approval['prior_commit'],
        'limitations': ['One deliberately chosen population and one eight-generation branch do not establish curriculum or depth superiority.',
            'AM current_value was chosen after its observed joint capture gains; this is not an outcome-independent background sample.',
            'Selection allocates 2 POOL, 2 persistent and 4 blink80_20 lives per eight, repeated for recheck, at unchanged R_cap 500.',
            'Generation 4 and generation 8 rank0 endpoints are both fixed before confirmation, without outcome-based replacement.',
            'The longer off period changes visible fraction and encounter history; dark captures alone do not establish memory.',
            'POOL and persistent retain their distinct physical fields; historical cross-study comparisons do not isolate one world factor.',
            'All five worlds are explicitly declared development or diagnostic contexts; no unqualified unseen-world generalization claim.',
            'Fitness may improve through economy; report captures and physical costs separately.',
            'A 10% retention margin permits some loss; failure to resolve loss does not establish retention.',
            'Whole-genome comparisons do not establish circuit mechanism or prediction. No retry or scope extension.']}
    save(STUDY / 'protocol.json', protocol, exclusive=True)
    print(json.dumps({'status': 'prepared', 'protocol_sha256': sha(STUDY / 'protocol.json'),
                      'genetic_draws': 0, 'simulation_calls': 0, 'imported_rows': 32}))


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--prepare', action='store_true')
    if parser.parse_args().prepare:
        prepare()
    else:
        print(json.dumps({'status': 'source_only', 'research_lives': 28214, 'startup_lives': 8}))
