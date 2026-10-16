"""Independent fixed-input check; pure decoding/packing only, no engine imports, builds or draws."""
import hashlib
import json
import os
import resource
import subprocess
import sys
import time
from collections import Counter
from dataclasses import asdict
from pathlib import Path

START, CPU = time.monotonic(), time.process_time()
STUDY = Path(__file__).resolve().parents[1]
ROOT = STUDY.parents[1]


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def digest(array):
    return hashlib.sha256(array.tobytes()).hexdigest()


def read(path):
    return json.loads(path.read_text())


def main():
    resource.setrlimit(resource.RLIMIT_CPU, (30, 31))
    resource.setrlimit(resource.RLIMIT_AS, (8 * 1024**3, 8 * 1024**3))
    os.sched_setaffinity(0, {min(os.sched_getaffinity(0))})
    for key in ('OPENBLAS_NUM_THREADS', 'OMP_NUM_THREADS', 'MKL_NUM_THREADS'):
        os.environ[key] = '1'
    sys.dont_write_bytecode = True
    sys.path.insert(0, str(ROOT))
    import numpy as np

    from src.life import spec

    protocol = read(STUDY / 'protocol.json')
    expected_sha = 'b1b4cbdb2c1d2d7f2e1eeac05d28a8944dc4ed8e0fc3fdd3efc5190d9ded55cc'
    assert sha(STUDY / 'protocol.json') == expected_sha
    assert read(STUDY / 'READY.json')['protocol_sha256'] == expected_sha
    assert subprocess.check_output(['git', 'rev-parse', 'HEAD'], cwd=ROOT, text=True).strip() == protocol['source_revision']
    assert protocol['source_revision'] == '71591f3ae133c3c2c193d3b394e7a5f2e9f61833'
    for field, base in (('production_pins', ROOT), ('input_pins', STUDY), ('source_pins', STUDY)):
        for name, pin in protocol[field].items():
            assert sha(base / name) == pin, (field, name)
    assert all(not (STUDY / name).exists() for name in ('release.json', 'attempt.json', 'raw', 'startup.json'))
    raw = np.load(STUDY / 'inputs/raw_genomes.npy', allow_pickle=False)
    packed = np.load(STUDY / 'inputs/packed_genomes.npy', allow_pickle=False)
    assert raw.shape == packed.shape == (33, 875)
    assert raw.dtype == np.float32 and packed.dtype == np.float64
    assert np.isfinite(raw).all() and np.isfinite(packed).all()
    ao = ROOT / 'results/retained_depth_20261015'
    ancestry = read(STUDY / 'inputs/ancestry.json')
    pop = read(ao / 'runs/balanced/population.json')
    assert sha(STUDY / 'inputs/population.json') == sha(ao / 'runs/balanced/population.json')
    assert protocol['population_ids'] == ancestry['ids'] == pop['ids']
    assert len(pop['ids']) == len(set(pop['ids'])) == 32 and pop['ids'][0] == 5336

    def decode(params):
        return np.concatenate([np.asarray(params[field.name], np.float32).reshape(-1)
                               for field in spec.V6.GENOME_FIELDS])

    decoded = np.stack([decode(params) for params in pop['genomes']])
    assert decoded.tobytes() == raw[:32].tobytes()
    assert digest(decoded) == ancestry['population_raw_sha256'] == (
        'd9e04d3a38a9f236e5a450ac869b514d67d143e31573360d8779bb9534cbdc87')
    for role, index in (('AO_rank0', 0), ('AM_reference', 32)):
        record = ancestry['roles'][role]
        source = ROOT / record['public_path']
        assert record['table_row'] == index
        assert sha(STUDY / 'inputs' / (role + '.json')) == sha(source) == record['file_sha256']
        assert decode(read(source)['params']).tobytes() == raw[index].tobytes()
        assert digest(raw[index]) == record['raw_sha256']
    assert [digest(row) for row in raw] == ancestry['row_raw_sha256']
    assert [digest(row) for row in packed] == ancestry['row_packed_sha256']
    assert spec.V6.pack_genomes(raw, 'hexprism').tobytes() == packed.tobytes()
    for name, pin in ancestry['sources'].items():
        assert sha(ROOT / name) == pin
    worlds = read(STUDY / 'inputs/worlds.json')
    assert worlds == protocol['worlds']
    originals = read(ao / 'protocol.json')['worlds']
    for name in ('patch', 'pool', 'persistent'):
        world = spec.world('catch_resource_patches_l4') if name == 'patch' else spec.World(**originals[name]['world'])
        assert asdict(world) == worlds[name]['world']
        assert spec.V6.pack_world(world).tobytes() == np.asarray(worlds[name]['vector'], np.float64).tobytes()
        assert world.T == 1024 and world.t_open == world.t0 == world.flags == world.fork_flags == 0
    expected = []
    for pair, (role, row, world, seed) in enumerate((('AO_rank0', 0, 'patch', 42000000),
            ('AM_reference', 32, 'patch', 42000001), ('AO_rank0', 0, 'pool', 42000002),
            ('AM_reference', 32, 'persistent', 42000003))):
        expected.extend(('engineering', role, row, world, seed, fast, pair) for fast in (False, True))
    expected.extend(('population', f'row{row:02d}', row, 'patch', seed, True, None)
                    for row in range(32) for seed in range(52470000, 52470008))
    expected.extend(('reference', role, row, world, seed, True, None)
                    for world in ('patch', 'pool', 'persistent')
                    for role, row in (('AO_rank0', 0), ('AM_reference', 32)) for seed in range(52480000, 52480032))
    schedule = read(STUDY / 'inputs/schedule.json')
    assert schedule == protocol['schedule'] and len(schedule) == len(expected) == 456
    assert len({item['path'] for item in schedule}) == 456
    for index, (item, values) in enumerate(zip(schedule, expected)):
        assert item['index'] == index
        assert tuple(item[key] for key in ('group', 'role', 'row', 'world', 'seed', 'fast', 'pair')) == values
        assert item['path'] == f"raw/{index:04d}_{item['group']}_{item['world']}_{item['role']}_{item['seed']}.npz"
    assert Counter(item['group'] for item in schedule) == dict(engineering=8, population=256, reference=192)
    assert protocol['raster_cap'] == protocol['fate_cap'] == protocol['startup_lives'] == 0
    assert protocol['budget'] == dict(cpu_seconds=360, wall_seconds=780, workers=1, threads=1,
        cleanup_margin_seconds=5, rss_bytes=2*1024**3, address_space_bytes=8*1024**3, minimum_available_bytes=4*1024**3)
    assert protocol['package_budget'] == dict(cpu_seconds=450, wall_seconds=900)
    assert protocol['preparation_allowance']['cpu_seconds'] == 90
    assert protocol['preparation_allowance']['wall_seconds'] == 120
    report = dict(status='passed_actual_input_review_ready_for_root_release', protocol_sha256=expected_sha,
        reviewer_source_sha256=sha(Path(__file__)), source_review_sha256=sha(STUDY / 'reviews/source_review.json'),
        production_files_verified=len(protocol['production_pins']), input_pins=protocol['input_pins'],
        native_calls_planned=456, engineering_calls=8, scientific_calls=448, startup_calls=0,
        population_shape=[32, 875], table_shape=[33, 875], ordered_ids=pop['ids'],
        population_raw_sha256=digest(decoded), raw_table_sha256=digest(raw), packed_table_sha256=digest(packed),
        world_vector_sha256={name: digest(np.asarray(row['vector'], np.float64)) for name, row in worlds.items()},
        schedule_sha256=sha(STUDY / 'inputs/schedule.json'), all456_schedule_entries_checked=True,
        seed_checks=dict(population=list(range(52470000, 52470008)), reference=list(range(52480000, 52480032)),
                         engineering=[42000000, 42000001, 42000002, 42000003], disjoint_scientific_sets=True),
        namespace_audit_sha256=protocol['seed_audit_sha256'], reservation_sha256=protocol['reservation_sha256'],
        installed_source_revision=protocol['source_revision'], execution_artifacts_absent=True,
        simulations=0, builds=0, random_draws=0,
        resources=dict(cpu_seconds=time.process_time()-CPU, wall_seconds=time.monotonic()-START,
                       max_rss_kib=resource.getrusage(resource.RUSAGE_SELF).ru_maxrss))
    output = STUDY / 'reviews/actual_input_review.json'
    with output.open('x') as stream:
        json.dump(report, stream, indent=2)
        stream.write('\n')
    print(json.dumps(dict(status=report['status'], receipt_sha256=sha(output), resources=report['resources'])))


if __name__ == '__main__':
    main()
