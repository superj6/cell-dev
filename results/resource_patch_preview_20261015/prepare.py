"""Export one already-recorded AO engineering case; no engine imports, builds, lives or random draws."""
import hashlib
import json
import shutil
from pathlib import Path

import numpy as np

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[1]
BASE = ROOT / 'results/resource_patch_baseline_20261015'


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def read(path):
    return json.loads(path.read_text())


def save(path, value):
    with path.open('x') as stream:
        json.dump(value, stream, indent=2, allow_nan=False)
        stream.write('\n')


def main():
    protocol, index = read(BASE / 'protocol.json'), read(BASE / 'row_index.json')
    assert sha(BASE / 'protocol.json') == 'b1b4cbdb2c1d2d7f2e1eeac05d28a8944dc4ed8e0fc3fdd3efc5190d9ded55cc'
    assert read(BASE / 'measurement_complete.json')['status'] == read(BASE / 'budget.json')['status'] == 'complete'
    case = protocol['schedule'][0]
    assert case['role'] == 'AO_rank0' and case['row'] == 0 and case['seed'] == 42000000
    assert case['world'] == 'patch' and not case['fast'] and case['group'] == 'engineering'
    native = BASE / case['path']
    assert sha(native) == index[case['path']]['sha256']
    ancestry = read(BASE / 'inputs/ancestry.json')
    raw_path, packed_path = BASE / 'inputs/raw_genomes.npy', BASE / 'inputs/packed_genomes.npy'
    for path in (raw_path, packed_path, BASE / 'inputs/ancestry.json'):
        assert sha(path) == protocol['input_pins'][str(path.relative_to(BASE))]
    raw, packed = np.load(raw_path, allow_pickle=False), np.load(packed_path, allow_pickle=False)
    assert raw.dtype == np.float32 and packed.dtype == np.float64 and raw.shape == packed.shape == (33, 875)
    genotype = hashlib.sha256(raw[0].tobytes()).hexdigest()
    assert genotype == ancestry['roles']['AO_rank0']['raw_sha256'] == ancestry['row_raw_sha256'][0]
    assert hashlib.sha256(packed[0].tobytes()).hexdigest() == ancestry['row_packed_sha256'][0]
    atlas_path = ROOT / 'results/atlas/play/bodies.json'
    atlas = read(atlas_path)
    body = dict(name='AO balanced24 rank0 (unchanged inherited genome)', abi=6, mode='grn',
                genotype_sha256=genotype, genome=packed[0].tolist(), world=protocol['worlds']['patch']['world'])
    assert body['world']['T'] == 1024 and body['world']['patch_count'] == 3 and body['world']['t_open'] == 0
    doc = dict(abi=6, bodies=[body], lattice=atlas['lattice'], drag=atlas['drag'], genome_slices=atlas['genome_slices'])
    inputs = HERE / 'inputs'
    inputs.mkdir(exist_ok=False)
    dependencies = {}
    for name in ('lifesim.js', 'resource_patches_view.js', 'test_resource_patches_view.js'):
        path = ROOT / 'results/atlas/play' / name
        shutil.copyfile(path, inputs / name)
        dependencies[str(path.relative_to(ROOT))] = sha(path)
    shutil.copyfile(native, inputs / 'saved_C_full.npz')
    with np.load(native, allow_pickle=False) as value:
        assert value['ledger'].shape == (1, 107) and value['hashes'].shape == (1, 5)
        assert int(value['seed'][0]) == 42000000 and value['protocol_sha256'].item() == sha(BASE / 'protocol.json')
        truth = dict(ledger=[repr(float(x)) for x in value['ledger'][0]],
                     hashes=[f'{int(x):016x}' for x in value['hashes'][0]])
    save(inputs / 'fixture.json', dict(seed=42000000, doc=doc, truth=truth))
    parents = {str(path.relative_to(ROOT)): sha(path) for path in (
        BASE / 'protocol.json', BASE / 'row_index.json', BASE / 'measurement_complete.json', BASE / 'budget.json',
        BASE / 'inputs/ancestry.json', raw_path, packed_path, native, atlas_path)}
    record = dict(status='fixed_case_ready', seed=42000000, role='AO_rank0', world='patch', T=1024,
        JS_replays=1, new_C_lives=0, new_Python_lives=0, builds=0, genotype_sha256=genotype,
        packed_genotype_sha256=ancestry['row_packed_sha256'][0], parent_pins=parents, dependencies=dependencies,
        source_pins={name: sha(HERE / name) for name in ('prepare.py', 'run.py', 'replay.js', 'template.html',
                     'monitor_core.py', 'common.py', 'source_origins.json')},
        input_pins={str(path.relative_to(HERE)): sha(path) for path in sorted(inputs.iterdir())},
        package_caps=dict(cpu_seconds=30, wall_seconds=60), outside_runtime_reserve=dict(cpu_seconds=2, wall_seconds=5),
        runtime_budget=dict(cpu_seconds=28, wall_seconds=55, workers=1, threads=1, cleanup_margin_seconds=1,
                            rss_bytes=2 * 1024**3, address_space_bytes=8 * 1024**3,
                            minimum_available_bytes=4 * 1024**3),
        interpretation='Unchanged evolved AO inherited behavior; no evolution on patches; fixed engineering seed.')
    save(HERE / 'execution_record.json', record)
    print('Exported saved inputs only; zero new lives, builds or random draws.')


if __name__ == '__main__':
    main()
