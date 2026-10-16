"""Inspect fixed renderer/genotype/reuse/schedule inputs without building or simulating."""
import ast
import hashlib
import json
import os
import resource
import sys
import time
from collections import Counter
from dataclasses import asdict, replace
from pathlib import Path

START, CPU = time.monotonic(), time.process_time()
STUDY = Path(__file__).resolve().parents[1]
ROOT = STUDY.parents[1]
BASE = ROOT / 'results/resource_patch_baseline_20261015'
PROTOCOL_SHA = '435d8439a33cc160ecdc4150e22fd845fb2ff8e31fdc532b570c4c2a568209c1'
BASE_SHA = 'b1b4cbdb2c1d2d7f2e1eeac05d28a8944dc4ed8e0fc3fdd3efc5190d9ded55cc'


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def digest(array):
    return hashlib.sha256(array.tobytes()).hexdigest()


def read(path):
    return json.loads(path.read_text())


def main():
    resource.setrlimit(resource.RLIMIT_CPU, (30, 31))
    resource.setrlimit(resource.RLIMIT_AS, (8*1024**3, 8*1024**3))
    os.sched_setaffinity(0, {min(os.sched_getaffinity(0))})
    for key in ('OPENBLAS_NUM_THREADS', 'OMP_NUM_THREADS', 'MKL_NUM_THREADS'):
        os.environ[key] = '1'
    sys.dont_write_bytecode = True
    sys.path.insert(0, str(ROOT))
    import numpy as np

    from src.life import spec

    protocol, baseline = read(STUDY / 'protocol.json'), read(BASE / 'protocol.json')
    assert sha(STUDY / 'protocol.json') == PROTOCOL_SHA and sha(BASE / 'protocol.json') == BASE_SHA
    assert read(STUDY / 'READY.json')['protocol_sha256'] == PROTOCOL_SHA
    reviewed = read(STUDY / 'reviews/source_review.json')
    for name, pin in reviewed['source_pins'].items():
        assert sha(STUDY / name) == pin, name
    for field, base in (('production_pins', ROOT), ('input_pins', STUDY), ('source_pins', STUDY)):
        for name, pin in protocol[field].items():
            assert sha(base / name) == pin, (field, name)
    assert protocol['production_pins'] == baseline['production_pins']
    assert protocol['engine_revision'] == baseline['source_revision'] == '71591f3ae133c3c2c193d3b394e7a5f2e9f61833'
    assert sha(STUDY / 'baseline_accounting.py') == sha(BASE / 'analyze.py')
    native = (STUDY / 'inputs/kernel.native.c').read_bytes()
    assert native == (ROOT / 'src/life/kernel.c').read_bytes()
    constants = {}
    for node in ast.parse((STUDY / 'renderer.py').read_text()).body:
        if isinstance(node, ast.Assign) and isinstance(node.targets[0], ast.Name):
            if node.targets[0].id in ('NATIVE_RATE_LINES', 'RENDERER_RATE_LINES'):
                constants[node.targets[0].id] = ast.literal_eval(node.value).encode()
    old, new = constants['NATIVE_RATE_LINES'], constants['RENDERER_RATE_LINES']
    renderer = (STUDY / 'inputs/renderer.c').read_bytes()
    assert native.count(old) == 1 and renderer == native.replace(old, new)
    assert renderer.replace(new, old) == native
    assert sha(STUDY / 'inputs/renderer.c') == reviewed['expected_isolated_source_sha256']
    assert protocol['amplitudes'] == dict(native=None, constant1=1.0, constant055=0.55)
    raw = np.load(STUDY / 'inputs/raw_genomes.npy', allow_pickle=False)
    packed = np.load(STUDY / 'inputs/packed_genomes.npy', allow_pickle=False)
    assert raw.shape == packed.shape == (2, 875) and raw.dtype == np.float32 and packed.dtype == np.float64
    assert np.isfinite(raw).all() and np.isfinite(packed).all()
    assert raw.tobytes() == np.load(BASE / 'inputs/raw_genomes.npy', allow_pickle=False)[[0, 32]].tobytes()
    assert packed.tobytes() == np.load(BASE / 'inputs/packed_genomes.npy', allow_pickle=False)[[0, 32]].tobytes()
    assert spec.V6.pack_genomes(raw, 'hexprism').tobytes() == packed.tobytes()
    for role, row, source_row in (('AO_rank0', 0, 0), ('AM_reference', 1, 32)):
        record = protocol['roles'][role]
        assert record['row'] == row and record['baseline_row'] == record['table_row'] == source_row
        assert record['raw_sha256'] == digest(raw[row])
        assert record['file_sha256'] == sha(ROOT / record['public_path'])
    for name in ('protocol.json', 'measurement_complete.json', 'budget.json', 'row_index.json', 'summary.json'):
        assert (STUDY / 'inputs' / ('baseline_' + name)).read_bytes() == (BASE / name).read_bytes()
    complete, budget = read(BASE / 'measurement_complete.json'), read(BASE / 'budget.json')
    assert complete['status'] == budget['status'] == 'complete'
    assert complete['protocol_sha256'] == budget['protocol_sha256'] == BASE_SHA
    assert complete['row_index_sha256'] == sha(BASE / 'row_index.json')
    assert complete['summary_sha256'] == sha(BASE / 'summary.json')
    assert budget['terminal_cleanup']['all_owned_groups_exited']
    assert budget['terminal_cleanup']['all_worker_identities_exited']
    assert not budget['terminal_cleanup']['remaining_descendants']
    reuse, index = read(STUDY / 'inputs/reuse.json'), read(BASE / 'row_index.json')
    assert reuse['baseline_protocol_sha256'] == BASE_SHA
    assert reuse['baseline_manifest_sha256'] == sha(BASE / 'manifest.json')
    assert reuse['confirmation_eligible'] is False and reuse['newly_reserved_blocks'] == []
    assert len(reuse['native_rows']) == 64 and len(reuse['engineering_rows']) == 8
    wanted = [item for item in baseline['schedule'] if item['group'] == 'engineering' or
              (item['group'] == 'reference' and item['world'] == 'patch')]
    copied = reuse['engineering_rows'] + reuse['native_rows']
    assert {item['index'] for item in copied} == {item['index'] for item in wanted}
    for item in copied:
        original = baseline['schedule'][item['index']]
        assert all(item[key] == value for key, value in original.items())
        assert item['baseline_public_path'] == str((BASE / item['path']).relative_to(ROOT))
        path = STUDY / item['copied_path']
        assert sha(path) == sha(BASE / item['path']) == item['sha256'] == index[item['path']]['sha256']
        with np.load(path, allow_pickle=False) as data:
            assert set(data.files) == {'ledger', 'hashes', 'seed', 'protocol_sha256'}
            assert data['ledger'].dtype == np.float64 and data['ledger'].shape == (1, 107)
            assert data['hashes'].dtype == np.uint64 and data['hashes'].shape == (1, 5)
            assert data['seed'].dtype == np.uint64 and data['seed'].shape == (1,)
            assert int(data['seed'][0]) == item['seed'] and data['protocol_sha256'].item() == BASE_SHA
            if item['fast']:
                assert np.all(data['hashes'] == spec.HASH_INIT)
    assert len(list((STUDY / 'inputs/baseline_rows').glob('*.npz'))) == 72
    for name, record in protocol['worlds'].items():
        world = spec.World(**baseline['worlds']['patch' if name == 'patch256' else name]['world'])
        if name == 'patch256':
            world = replace(world, T=256)
        assert asdict(world) == record['world']
        assert spec.V6.pack_world(world).tobytes() == np.asarray(record['vector'], np.float64).tobytes()
    assert set(protocol['worlds']) == {'patch', 'patch256', 'pool', 'persistent'}
    expected = []
    for item in reuse['engineering_rows']:
        expected.append(('native_equivalence', item['role'], 'native', item['world'], item['seed'],
                         'C_fast' if item['fast'] else 'C_full', item['pair'], item['copied_path']))
    for mode in ('constant1', 'constant055'):
        for role, seed in (('AO_rank0', 42000000), ('AM_reference', 42000001)):
            expected.extend(('constant_parity', role, mode, 'patch256', seed, backend, mode+'_'+role, None)
                            for backend in ('C_full', 'C_fast', 'Python'))
    expected.extend(('science', role, mode, 'patch', seed, 'C_fast', None, None)
                    for mode in ('constant1', 'constant055') for role in ('AO_rank0', 'AM_reference')
                    for seed in range(52480000, 52480032))
    schedule = protocol['schedule']
    assert len(schedule) == len(expected) == 148 and len({item['path'] for item in schedule}) == 148
    for i, (item, row) in enumerate(zip(schedule, expected)):
        assert item['index'] == i and item['row'] == {'AO_rank0': 0, 'AM_reference': 1}[item['role']]
        assert tuple(item[key] for key in ('group', 'role', 'mode', 'world', 'seed', 'backend',
                                           'pair', 'comparison')) == row
        assert item['path'] == (f"raw/{i:03d}_{item['group']}_{item['mode']}_{item['role']}_"
                                f"{item['seed']}_{item['backend']}.npz")
    assert Counter(item['backend'] for item in schedule) == protocol['call_breakdown'] == dict(C_full=8, C_fast=136, Python=4)
    assert Counter(item['group'] for item in schedule) == dict(native_equivalence=8, constant_parity=12, science=128)
    assert protocol['seeds'] == reuse['seeds'] == list(range(52480000, 52480032))
    assert protocol['startup_lives'] == protocol['raster_cap'] == protocol['fate_cap'] == 0
    assert protocol['budget'] == dict(cpu_seconds=510, wall_seconds=1080, workers=1, threads=1,
        cleanup_margin_seconds=5, rss_bytes=2*1024**3, address_space_bytes=8*1024**3, minimum_available_bytes=4*1024**3)
    assert protocol['package_budget'] == dict(cpu_seconds=600, wall_seconds=1200)
    assert protocol['preparation_allowance'] == dict(cpu_seconds=90, wall_seconds=120)
    absent = ('release.json', 'attempt.json', 'raw', 'startup.json', 'build-cache', 'compiler_diagnostics')
    assert all(not (STUDY / name).exists() for name in absent)
    report = dict(status='passed_actual_input_review_ready_for_root_release', protocol_sha256=PROTOCOL_SHA,
        reviewer_source_sha256=sha(Path(__file__)), source_review_sha256=sha(STUDY / 'reviews/source_review.json'),
        production_files_verified=len(protocol['production_pins']), input_pins=protocol['input_pins'],
        native_kernel_sha256=sha(STUDY / 'inputs/kernel.native.c'), renderer_sha256=sha(STUDY / 'inputs/renderer.c'),
        raw_table_sha256=digest(raw), packed_table_sha256=digest(packed), genome_rows=2,
        baseline_protocol_sha256=BASE_SHA, reused_scientific_rows=64, reused_engineering_rows=8,
        every_reused_npz_schema_seed_hash_checked=True, every_new_schedule_entry_checked=True,
        new_calls=dict(total=148, engineering=20, science=128, C_full=8, C_fast=136, Python=4),
        no_fresh_seed_claim=True, no_execution_artifacts=True, simulations=0, builds=0, random_draws=0,
        resources=dict(cpu_seconds=time.process_time()-CPU, wall_seconds=time.monotonic()-START,
                       max_rss_kib=resource.getrusage(resource.RUSAGE_SELF).ru_maxrss))
    output = STUDY / 'reviews/actual_input_review.json'
    with output.open('x') as stream:
        json.dump(report, stream, indent=2)
        stream.write('\n')
    print(json.dumps(dict(status=report['status'], receipt_sha256=sha(output), resources=report['resources'])))


if __name__ == '__main__':
    main()
