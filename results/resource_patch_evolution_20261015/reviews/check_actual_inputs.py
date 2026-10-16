"""Independent prepared-input checks; no simulator, build, evolution or genetic RNG."""
from __future__ import annotations

import copy
import hashlib
import json
import os
import resource
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


def read(path):
    return json.loads(path.read_text())


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def raw(value):
    return hashlib.sha256(value.numpy().tobytes()).hexdigest()


def main():
    import torch
    from omegaconf import OmegaConf

    from src.genome import Layout
    from src.life import spec
    from src.life.evaluate import life_seed

    torch.set_num_threads(1)
    digest = sha(STUDY / 'protocol.json')
    assert digest == '0b0fd4e0fd2392f3f03f7f6bf5822714d64ce312aa20887770d0338c9c452da1'
    p = read(STUDY / 'protocol.json')
    assert p['source_revision'] == '52e390ae0b39b6c954e414ae07a0386b8ccc075f'
    for section, base in (('source_pins', STUDY), ('input_pins', STUDY),
                          ('production_pins', ROOT), ('original_input_pins', ROOT)):
        for name, pin in p[section].items():
            assert sha(base / name) == pin, (section, name)
    for receipt in ('root_adapter_review', 'reader_source_review', 'preparation_source_review'):
        review = read(STUDY / 'reviews' / (receipt + '.json'))
        assert review['status'].startswith('passed')
        for name, pin in review['source_pins'].items():
            assert sha(STUDY / name) == pin
    assert read(STUDY / 'READY.json')['protocol_sha256'] == digest
    assert not any((STUDY / name).exists() for name in ('release.json', 'execution', 'runs', 'raw', 'build-cache'))

    imported = read(STUDY / 'inputs/input_population.json')
    public = ROOT / 'results/retained_depth_20261015/runs/balanced'
    assert sha(STUDY / 'inputs/input_population.json') == sha(public / 'population.json')
    layout, endpoint = Layout.load(STUDY / 'inputs/AO_start.json')
    table = torch.stack([layout.from_dict(row) for row in imported['genomes']])
    saved = torch.load(STUDY / 'inputs/AO_checkpoint.pt', map_location='cpu', weights_only=True)
    assert saved['state']['generation'] == 24 and tuple(table.shape) == (32, 875)
    assert table.dtype == torch.float32 and bool(torch.isfinite(table).all())
    assert table.numpy().tobytes() == saved['state']['population'].numpy().tobytes()
    assert table[0].numpy().tobytes() == endpoint.numpy().tobytes()
    assert imported['ids'] == saved['state']['ids'].tolist() and len(set(imported['ids'])) == 32
    assert imported['ids'][0] == 5336
    record = p['population_start']
    rows = [raw(row) for row in table]
    assert record == read(STUDY / 'inputs/population_import.json')
    assert record['population_file'] == 'inputs/input_population.json'
    assert record['shape'] == [32, 875] and record['file_sha256'] == sha(STUDY / record['population_file'])
    assert record['population_raw_sha256'] == raw(table) == 'd9e04d3a38a9f236e5a450ac869b514d67d143e31573360d8779bb9534cbdc87'
    assert record['row_sha256'] == rows and record['old_ids'] == imported['ids']
    assert record['new_ids'] == list(range(32))
    assert record['old_to_new'] == [dict(old_id=old, new_id=i, row=i, raw_sha256=rows[i])
                                    for i, old in enumerate(imported['ids'])]

    cfg = OmegaConf.to_container(OmegaConf.load(STUDY / 'configs/mixed.yaml'), resolve=True)
    ancestor = OmegaConf.to_container(OmegaConf.load(STUDY / 'inputs/AO_config.yaml'), resolve=True)
    expected_cfg = copy.deepcopy(ancestor)
    overrides = {'seed': 53234, 'threads': 2,
        'evolve.generations': 8, 'evolve.heldout_every': 4,
        'evolve.seed_genome': str(STUDY / 'inputs/input_population.json'),
        'evolve.dup_rate': 0., 'evolve.del_rate': 0., 'evolve.dup_split': False,
        'evolve.recheck_k': 64, 'evolve.recheck_lives': 8, 'evolve.recheck_key': 'all',
        'logging.output_dir': str(STUDY / 'runs/mixed'), 'logging.checkpoint_every': 1,
        'logging.lineage': 'all', 'life.abi': 6, 'life.world': 'catch_resource_patches_l4',
        'life.control': 'resource_patch_continuation', 'life.T': 1024., 'life.founder_T': 1024.,
        'life.lives': 8, 'life.T_choices': None, 'life.heldout': [], 'life.flags': [],
        'life.freeze_frac': None, 'life.t_open': 0., 'world': {}, 'costs_life': {}, 'envelope': {'enabled': False}}
    for name, value in overrides.items():
        target = expected_cfg
        pieces = name.split('.')
        for piece in pieces[:-1]:
            target = target[piece]
        target[pieces[-1]] = value
    for name in ('population_start', 'retention_selection'):
        expected_cfg[name] = cfg[name]
    assert cfg == expected_cfg
    assert cfg['life']['final_fork_lives'] == 0 and cfg['life']['final_top'] == 1
    assert cfg['population_start'] == {'version': 1, **record, 'source_pins': {
        name: p['source_pins'][name] for name in ('population_loader.py', 'search.py')}}
    selection = cfg['retention_selection']
    assert selection['arm'] == 'mixed' and selection['worlds'] == p['selection_worlds']
    assert selection['pattern'] == ['patch', 'pool', 'patch', 'persistent'] * 2
    assert selection['source_pins'] == {'selection.py': p['source_pins']['selection.py']}
    assert sha(STUDY / 'inputs/config.yaml') == sha(STUDY / 'configs/mixed.yaml')

    ao_worlds = read(STUDY / 'inputs/AO_protocol.json')['worlds']
    patch = spec.world('catch_resource_patches_l4', T=1024.)
    worlds = {'patch': patch, **{name: spec.World(**ao_worlds[name]['world'])
              for name in ('pool', 'persistent', 'blink80_20')},
              'transfer': replace(patch, patch_count=4, R_min=3., R_max=5.,
                                  patch_refill_fast=100., patch_refill_slow=200.)}
    assert list(p['worlds']) == list(worlds)
    for name, world in worlds.items():
        assert p['worlds'][name] == dict(abi=6, world=asdict(world),
            world_vector=spec.V6.pack_world(world).tolist(), ledger_columns=list(spec.V6.LEDGER))
        assert len(p['worlds'][name]['world_vector']) == 82 and len(spec.V6.LEDGER) == 107
    assert p['selection_worlds'] == {name: asdict(worlds[name]) for name in ('patch', 'pool', 'persistent')}

    identity = copy.deepcopy(read(STUDY / 'inputs/AO_startup_identity.json')['identity'])
    baseline = read(STUDY / 'inputs/baseline_startup.json')
    identity['sources'] = {str(q.relative_to(ROOT)): sha(q) for q in sorted((ROOT / 'src').rglob('*.py'))}
    identity['sources']['src/life/kernel.c'] = sha(ROOT / 'src/life/kernel.c')
    identity['kernels'] = {key: value['sha256'] for key, value in baseline['libraries'].items()}
    assert identity['flags'] == {key: value['flags'] for key, value in baseline['libraries'].items()}
    assert identity == p['expected_numerical_identity'] == read(STUDY / 'inputs/startup_identity.json')['identity']
    truth = read(STUDY / 'inputs/patch_truth.json')
    first = truth['cases'][0]
    assert truth['abi'] == 6 and truth['status'] == 'complete'
    assert first['name'] == 'reflex_count1' and first['seed'] == 42000000
    assert first['body']['world']['T'] == 96 and first['body']['world']['patch_count'] == 1
    assert len(first['body']['world']) == 82 and len(first['ledger']) == 107 and len(first['hashes']) == 5

    native = []
    for generation in range(8):
        native += [life_seed(53234, 'gen', generation, i) for i in range(16)]
        if generation in (0, 4, 7):
            native += [life_seed(53234, 'valid', generation, i) for i in range(16)]
    native += [life_seed(53234, 'final', index, i) for index in (0, 1) for i in range(2)]
    audit = read(STUDY / 'namespace/seed_audit.json')
    reservation = read(STUDY / 'reservation.json')
    assert len(set(native)) == 180 and native == audit['run_life_seeds']['mixed'] == reservation['native_ids']
    assert p['seeds'] == audit['confirmation_seeds'] == reservation['confirmation_seeds'] == list(range(52490000, 52490512))
    assert not set(native).intersection(p['seeds']) and p['native_seed'] == reservation['native_seed'] == 53234
    assert reservation['seed_blocks'] == [[52490000, 52500000]]
    assert sha(STUDY / 'reservation.json') == p['reservation_sha256']
    assert sha(STUDY / 'namespace/seed_audit.json') == p['seed_audit_sha256'] == reservation['audit_sha256']
    assert p['roles'] == ['AO_start', 'mixed4', 'mixed8'] and p['runs'] == ['mixed']
    assert p['search']['research_lives_per_arm'] == 8*(256*8+64*8)+3*16+6 == 20534
    assert p['confirmation_lives'] == 3*5*512 == 7680
    assert p['research_lives'] == 20534+7680 == 28214 and p['startup_lives'] == 8 and p['total_calls'] == 28222
    assert p['budget'] == dict(cpu_seconds=5280, wall_seconds=3480, total_cpu_seconds=5400,
        total_wall_seconds=3600, preparation_cpu_allowance=120, preparation_wall_allowance=120,
        search_cpu_seconds=4080, confirmation_cpu_seconds=1200, threads=2, workers=1,
        cleanup_margin_seconds=10, rss_bytes=4*1024**3, minimum_available_bytes=4*1024**3,
        address_space_bytes=8*1024**3)
    result = dict(status='passed', reviewer='delayed_match_review', protocol_sha256=digest,
        source_revision=p['source_revision'], checker_sha256=sha(Path(__file__)),
        checks=['All prepared, source, production, ancestor and independent-review pins exact',
                'All32 raw875-parameter rows equal AO checkpoint/public order; crosswalk and fixed rank0 exact',
                'Configuration differs from AO only in the reviewed listed settings and bound adapters',
                'Exact ABI6 fiveworld82-vectors/107-ledger schemas; three selection worlds exclude transfer',
                'Expected numerical identity predeclared from current source and retained binary records, never executed',
                'Native180 IDs and512 confirmation IDs equal audited/reserved exact schedule',
                '28,222 exact calls, passiveg4,primaryg8,originaloperators/prices and budget',
                'No runtime release, engine artifacts, lives or genetic draws exist'],
        population_raw_sha256=raw(table), row_sha256=rows, native_unique_ids=180,
        confirmation_seed_count=512, total_calls=28222,
        resources=dict(cpu_seconds=time.process_time()-START_CPU, wall_seconds=time.perf_counter()-START_WALL,
                       max_rss_KiB=resource.getrusage(resource.RUSAGE_SELF).ru_maxrss, threads=1),
        new_lives=0, new_builds=0, new_genetic_draws=0)
    (STUDY / 'reviews/actual_input_review.json').write_text(json.dumps(result, indent=2)+'\n')
    print(json.dumps({key: result[key] for key in ('status', 'protocol_sha256', 'total_calls', 'resources')}))


if __name__ == '__main__':
    main()
