"""Independent prepared-input verification; never build, simulate or draw genetic randomness."""
from __future__ import annotations

import argparse
import ast
import copy
import hashlib
import json
import os
import resource
import signal
import subprocess
import sys
import time
from dataclasses import asdict, replace
from pathlib import Path

os.environ['OMP_NUM_THREADS'] = '1'
os.environ['OPENBLAS_NUM_THREADS'] = '1'
os.environ['MKL_NUM_THREADS'] = '1'
os.environ['ATEN_CPU_CAPABILITY'] = 'avx2'
sys.dont_write_bytecode = True
START_CPU, START_WALL = time.process_time(), time.perf_counter()
STUDY = Path(__file__).resolve().parents[1]
ROOT = STUDY.parents[1]
sys.path.insert(0, str(ROOT))
AO = ROOT / 'results/retained_depth_20261015'
PRIOR = ROOT / 'results/resource_patch_evolution_20261015'
BASELINE = ROOT / 'results/resource_patch_baseline_20261015'
ARMS = ('mean', 'pareto')
WORLD_NAMES = ('patch', 'pool', 'persistent', 'blink80_20', 'transfer')
AO_CAPTURES = [19.046875, 16.029296875, 5.919921875]


def read(path):
    return json.loads(path.read_text())


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def raw(value):
    return hashlib.sha256(value.numpy().tobytes()).hexdigest()


def forbidden(*args, **kwargs):
    raise AssertionError('actual-input review must not build, simulate or draw randomness')


def source_literal(path, name):
    for node in ast.parse(path.read_text()).body:
        if isinstance(node, ast.Assign) and any(isinstance(t, ast.Name) and t.id == name for t in node.targets):
            return ast.literal_eval(node.value)
    raise AssertionError('missing literal: ' + name)


def main(expected_protocol, expected_revision):
    available = next(int(line.split()[1]) * 1024 for line in Path('/proc/meminfo').read_text().splitlines()
                     if line.startswith('MemAvailable:'))
    assert available >= 4 * 1024**3
    os.sched_setaffinity(0, {min(os.sched_getaffinity(0))})
    resource.setrlimit(resource.RLIMIT_CPU, (30, 30))
    resource.setrlimit(resource.RLIMIT_AS, (2 * 1024**3, 2 * 1024**3))
    signal.alarm(60)
    import torch
    from omegaconf import OmegaConf

    from src import checkpoint
    from src.genome import Layout
    from src.life import build, spec
    from src.life.evaluate import LifeEvaluator, life_seed

    torch.set_num_threads(1)
    build.run = build.build = forbidden
    checkpoint.numerical_identity = checkpoint.golden_life = forbidden
    for name in ('rand', 'randn', 'randint', 'randperm', 'normal', 'multinomial'):
        setattr(torch, name, forbidden)
    digest = sha(STUDY / 'protocol.json')
    assert len(expected_protocol) == 64 and digest == expected_protocol
    p = read(STUDY / 'protocol.json')
    assert len(expected_revision) == 40 and p['source_revision'] == expected_revision
    assert subprocess.check_output(['git', 'rev-parse', 'HEAD'], cwd=ROOT, text=True).strip() == expected_revision
    assert not any((STUDY / name).exists() for name in
                   ('release.json', 'attempt.json', 'execution', 'runs', 'raw', 'scored', 'build-cache'))
    assert not (STUDY / 'reviews/actual_input_review.json').exists()
    for section, base in (('source_pins', STUDY), ('input_pins', STUDY),
                          ('production_pins', ROOT), ('original_input_pins', ROOT)):
        for name, pin in p[section].items():
            path = (base / name).resolve()
            assert path.is_relative_to(base.resolve()) and sha(path) == pin, (section, name)
    assert read(STUDY / 'READY.json') == dict(status='prepared', protocol_sha256=digest,
        preparation_lives=0, preparation_builds=0, preparation_random_draws=0)
    for name, key in (('preparation_source_review.json', 'source_pins'),
                      ('root_pareto_source_review.json', 'files')):
        review = read(STUDY / 'reviews' / name)
        assert review['status'] == 'passed'
        for filename, pin in review[key].items():
            assert sha(STUDY / filename) == pin, (name, filename)

    prior = read(STUDY / 'inputs/prior_protocol.json')
    assert sha(STUDY / 'inputs/prior_protocol.json') == sha(PRIOR / 'protocol.json')
    assert p['production_pins'] == prior['production_pins']
    assert sha(STUDY / 'inputs/prior_summary.json') == sha(PRIOR / 'summary.json')
    assert sha(PRIOR / 'summary.json') == 'f819c039ddb9a8751148b73afb4bdb7445fe7a5ca2d755bf7118490b0598c554'
    assert read(STUDY / 'inputs/prior_independent_accounting.json')['status'] == 'passed'
    assert read(PRIOR / 'budget.json')['status'] == 'complete'
    public = PRIOR / 'runs/mixed'
    for prepared, original in (('input_population.json', 'population.json'),
                               ('input_checkpoint.pt', 'checkpoint.pt'), ('input_config.yaml', 'config.yaml'),
                               ('input_determinism.json', 'determinism.json'),
                               ('patch8_start.json', 'best_genome.json')):
        assert sha(STUDY / 'inputs' / prepared) == sha(public / original)
    assert sha(STUDY / 'inputs/AO_start.json') == sha(AO / 'runs/balanced/best_genome.json')
    imported = read(STUDY / 'inputs/input_population.json')
    layout, endpoint = Layout.load(STUDY / 'inputs/patch8_start.json')
    table = torch.stack([layout.from_dict(row) for row in imported['genomes']])
    saved = checkpoint.load(STUDY / 'inputs/input_checkpoint.pt')
    ancestor_cfg = OmegaConf.load(STUDY / 'inputs/input_config.yaml')
    checkpoint.validate(saved, ancestor_cfg, read(STUDY / 'inputs/input_determinism.json'))
    assert saved['state']['generation'] == 8 and tuple(table.shape) == (32, 875)
    assert table.dtype == torch.float32 and bool(torch.isfinite(table).all())
    assert table.numpy().tobytes() == saved['state']['population'].numpy().tobytes()
    assert table[0].numpy().tobytes() == endpoint.numpy().tobytes()
    assert imported['ids'] == saved['state']['ids'].tolist() and len(set(imported['ids'])) == 32
    record = p['population_start']
    row_hashes = [raw(row) for row in table]
    assert record == read(STUDY / 'inputs/population_import.json')
    assert record['population_file'] == 'inputs/input_population.json'
    assert record['shape'] == [32, 875] and record['file_sha256'] == sha(STUDY / record['population_file'])
    assert record['population_raw_sha256'] == raw(table)
    assert record['row_sha256'] == row_hashes and record['old_ids'] == imported['ids']
    assert record['new_ids'] == list(range(32))
    assert record['old_to_new'] == [dict(old_id=old, new_id=i, row=i, raw_sha256=row_hashes[i])
                                    for i, old in enumerate(imported['ids'])]
    references = []
    for role, original in (('AO_start', AO / 'runs/balanced/best_genome.json'),
                           ('patch8_start', public / 'best_genome.json')):
        path = STUDY / 'inputs' / (role + '.json')
        ref_layout, genome = Layout.load(path)
        assert ref_layout.dims == layout.dims and tuple(genome.shape) == (875,)
        references.append(dict(role=role, path=str(path.relative_to(STUDY)), file_sha256=sha(path),
            raw_sha256=raw(genome), source=str(original.relative_to(ROOT))))
    assert p['references'] == references and p['reference'] == references[1]

    ao_worlds = read(STUDY / 'inputs/AO_protocol.json')['worlds']
    patch = spec.world('catch_resource_patches_l4', T=1024.)
    worlds = {'patch': patch, **{name: spec.World(**ao_worlds[name]['world'])
              for name in ('pool', 'persistent', 'blink80_20')},
              'transfer': replace(patch, patch_count=2, R_min=3.5, R_max=5.5,
                                  patch_refill_fast=60., patch_refill_slow=180.)}
    assert list(p['worlds']) == list(WORLD_NAMES) == list(worlds)
    baseline = read(STUDY / 'inputs/baseline_protocol.json')
    assert sha(STUDY / 'inputs/baseline_protocol.json') == sha(BASELINE / 'protocol.json')
    cost_keys = [name for name in asdict(patch) if name.startswith('c_')] + ['R_cap']
    expected_costs = {name: baseline['worlds']['patch']['world'][name] for name in cost_keys}
    assert expected_costs == dict(c_live=.02, c_spike=.004, c_tw=.004, c_msg=.001, c_div=.5,
                                  c_sec=.004, c_miss=10., c_rec=.001, R_cap=500.)
    for name, world in worlds.items():
        spec.V6.validate_world(world)
        assert p['worlds'][name] == dict(abi=6, world=asdict(world),
            world_vector=spec.V6.pack_world(world).tolist(), ledger_columns=list(spec.V6.LEDGER))
        assert len(p['worlds'][name]['world_vector']) == 82 and len(spec.V6.LEDGER) == 107
        assert {key: getattr(world, key) for key in cost_keys} == expected_costs
        assert world.T == 1024. and world.t_open == 0. and world.flags == 0 and world.fork_flags == 0
    assert p['selection_worlds'] == prior['selection_worlds'] == {
        name: asdict(worlds[name]) for name in ('patch', 'pool', 'persistent')}
    assert {key for key in asdict(patch) if getattr(patch, key) != getattr(worlds['transfer'], key)} == {
        'patch_count', 'R_min', 'R_max', 'patch_refill_fast', 'patch_refill_slow'}

    ancestor = OmegaConf.to_container(ancestor_cfg, resolve=True)
    configs = {}
    for arm in ARMS:
        path = STUDY / 'configs' / (arm + '.yaml')
        cfg = OmegaConf.to_container(OmegaConf.load(path), resolve=True)
        expected = copy.deepcopy(ancestor)
        overrides = {'seed': 53235, 'threads': 2, 'evolve.generations': 4, 'evolve.heldout_every': 4,
            'evolve.seed_genome': str(STUDY / 'inputs/input_population.json'),
            'logging.output_dir': str(STUDY / 'runs' / arm), 'life.control': 'resource_patch_selection_comparison'}
        for name, value in overrides.items():
            target = expected
            pieces = name.split('.')
            for piece in pieces[:-1]:
                target = target[piece]
            target[pieces[-1]] = value
        population_identity = {'version': 1, **record, 'source_pins': {
            name: p['source_pins'][name] for name in ('population_loader.py', 'search.py')}}
        selection_identity = dict(version=2, arm=arm, worlds=p['selection_worlds'],
            rule=source_literal(STUDY / 'selection.py', 'RULE'),
            pattern=['patch', 'pool', 'patch', 'persistent'] * 2,
            endpoint_rule=source_literal(STUDY / 'selection.py', 'ENDPOINT_RULE'), endpoint_reference=AO_CAPTURES,
            source_pins={name: p['source_pins'][name] for name in ('selection.py', 'pareto.py')})
        expected['population_start'], expected['retention_selection'] = population_identity, selection_identity
        assert cfg == expected, arm
        assert p['configs'][arm] == dict(path=f'configs/{arm}.yaml', sha256=sha(path))
        assert cfg['life']['extinct_charge'] and cfg['life']['final_fork_lives'] == 0
        assert cfg['evolve']['n_mut'] == 2 and cfg['evolve']['n_mut_scale'] and cfg['evolve']['breeding'] == 'sex'
        assert not cfg['costs_life'] and not cfg['world'] and cfg['envelope'] == {'enabled': False}
        evaluator = LifeEvaluator(OmegaConf.create(cfg), layout)  # Constructor/world only; build/run are forbidden.
        assert evaluator.abi.version == 6 and evaluator.extinct_charge and evaluator.fast
        assert asdict(evaluator.world()) == asdict(patch)
        configs[arm] = cfg
    left, right = copy.deepcopy(configs['mean']), copy.deepcopy(configs['pareto'])
    left['logging']['output_dir'] = right['logging']['output_dir']
    left['retention_selection']['arm'] = right['retention_selection']['arm']
    assert left == right  # No hidden exposure, mutation, price or sampling difference.

    identity = copy.deepcopy(read(STUDY / 'inputs/AO_startup_identity.json')['identity'])
    libraries = read(STUDY / 'inputs/baseline_startup.json')['libraries']
    identity['sources'] = {str(q.relative_to(ROOT)): sha(q) for q in sorted((ROOT / 'src').rglob('*.py'))}
    identity['sources']['src/life/kernel.c'] = sha(ROOT / 'src/life/kernel.c')
    identity['kernels'] = {key: value['sha256'] for key, value in libraries.items()}
    assert identity['flags'] == {key: value['flags'] for key, value in libraries.items()}
    assert identity == p['expected_numerical_identity'] == read(STUDY / 'inputs/startup_identity.json')['identity']
    assert p['engine_revision'] == baseline['source_revision'] == '71591f3ae133c3c2c193d3b394e7a5f2e9f61833'
    truth = read(STUDY / 'inputs/patch_truth.json')
    first = truth['cases'][0]
    assert truth['abi'] == 6 and truth['status'] == 'complete'
    assert first['name'] == 'reflex_count1' and first['seed'] == 42000000
    assert first['body']['world']['T'] == 96 and first['body']['world']['patch_count'] == 1
    assert len(first['body']['world']) == 82 and len(first['ledger']) == 107 and len(first['hashes']) == 5
    prior_summary = read(STUDY / 'inputs/prior_summary.json')
    assert AO_CAPTURES == [prior_summary['absolute'][name]['AO_start']['captures']['mean']
                           for name in ('patch', 'pool', 'persistent')]
    assert list(source_literal(STUDY / 'pareto.py', 'AO_REFERENCE')) == AO_CAPTURES
    assert list(source_literal(STUDY / 'selection.py', 'AO_REFERENCE')) == AO_CAPTURES
    endpoint_rule = ('maximum minimum normalized per-domain captures, then ordinary aggregate F, '
                     'then ascending survivor ID')
    assert p['endpoint'] == dict(rule=endpoint_rule,
        reference_roles=['AO_start'], reference_captures=AO_CAPTURES,
        worlds=['patch', 'pool', 'persistent'], selection_lives=16, per_world_lives=[8, 4, 4],
        candidates=32, fixed_before_confirmation=True, export='joint_genome.json')

    native = []
    for generation in range(4):
        native += [life_seed(53235, 'gen', generation, i) for i in range(16)]
        if generation in (0, 3):
            native += [life_seed(53235, 'valid', generation, i) for i in range(16)]
    native += [life_seed(53235, 'final', index, i) for index in (0, 1) for i in range(2)]
    audit, reservation = read(STUDY / 'namespace/seed_audit.json'), read(STUDY / 'reservation.json')
    assert len(set(native)) == 100
    assert audit['run_life_seeds'] == reservation['native_ids'] == {arm: native for arm in ARMS}
    confirmation = list(range(52500000, 52500512))
    assert p['seeds'] == audit['confirmation_seeds'] == reservation['confirmation_seeds'] == confirmation
    assert not set(native).intersection(p['seeds']) and p['native_seed'] == reservation['native_seed'] == 53235
    assert reservation['seed_blocks'] == [[52500000, 52510000]]
    assert audit['whole_block_half_open'] == [52500000, 52510000]
    assert sha(STUDY / 'reservation.json') == p['reservation_sha256']
    assert sha(STUDY / 'namespace/seed_audit.json') == p['seed_audit_sha256'] == reservation['audit_sha256']
    assert p['roles'] == ['AO_start', 'patch8_start', 'mean4', 'pareto4'] and p['runs'] == list(ARMS)
    assert p['search'] == dict(arms=list(ARMS), generations=4, research_lives_per_arm=10278,
        startup_lives_per_arm=4, initial_lives=8, recheck_lives=8, parents=32, offspring=224,
        growth_diagnostic_T=512, growth_diagnostic_lives=2)
    assert p['search']['research_lives_per_arm'] == 4*(256*8+64*8)+2*16+6
    assert p['confirmation_lives'] == 4*5*512 == 10240 and p['confirmation_startup_lives'] == 4
    assert p['research_lives'] == 2*10278+10240 == 30796
    assert p['startup_lives'] == 12 and p['total_calls'] == 30808
    assert p['extinct_charge'] is True and p['status_bits'] == spec.STATUS and p['hash_names'] == list(spec.V6.HASHES)
    assert p['budget'] == dict(cpu_seconds=5280, wall_seconds=3480, total_cpu_seconds=5400,
        total_wall_seconds=3600, preparation_cpu_allowance=120, preparation_wall_allowance=120,
        search_cpu_seconds=4080, confirmation_cpu_seconds=1200, threads=2, workers=1,
        cleanup_margin_seconds=10, rss_bytes=4*1024**3, minimum_available_bytes=4*1024**3,
        address_space_bytes=8*1024**3)
    result = dict(status='passed', reviewer='circuit_options', protocol_sha256=digest,
        source_revision=p['source_revision'], checker_sha256=sha(Path(__file__)),
        checks=['All exact prepared/source/production/original-input hashes and known source-review receipts',
                'All32 ordered G8 float32 genomes equal public/checkpoint bytes with complete ID crosswalk',
                'Both exact AO and patch8 rank0 references retained; no population row omitted or replaced',
                'Two configs differ only in arm/output; inherited settings have only explicit prospective overrides',
                'Exact5 ABI6 world vectors, unchanged baseline physical prices, native extinction surcharge',
                'Predeclared numerical identity and old truth fixtures inherited without builds or new lives',
                'Fixed common endpoint scales equal prior512-life AO means; cached16 inputs and ID tie rule',
                'Exact100 unique native IDs plus512 fresh shared block150 IDs and30,808 total calls',
                'No release or runtime artifacts; no simulator/build/random entry points used'],
        source_pins=p['source_pins'], population_raw_sha256=raw(table), row_sha256=row_hashes,
        references=references, physical_prices=expected_costs, native_unique_ids=100,
        confirmation_seed_count=512, total_calls=30808,
        resources=dict(cpu_seconds=time.process_time()-START_CPU, wall_seconds=time.perf_counter()-START_WALL,
                       max_rss_KiB=resource.getrusage(resource.RUSAGE_SELF).ru_maxrss, threads=1),
        new_lives=0, new_builds=0, new_genetic_draws=0)
    with (STUDY / 'reviews/actual_input_review.json').open('x') as stream:
        stream.write(json.dumps(result, indent=2, allow_nan=False)+'\n')
    print(json.dumps({key: result[key] for key in ('status', 'protocol_sha256', 'total_calls', 'resources')}))


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--protocol-sha256', required=True)
    parser.add_argument('--source-revision', required=True)
    args = parser.parse_args()
    main(args.protocol_sha256, args.source_revision)
