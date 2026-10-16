"""Prepare four fixed saved-C comparisons after terminal completion; no lives/builds/draws."""
import argparse
import hashlib
import json
import shutil
import sys
from pathlib import Path

import numpy as np

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[1]
BASE = ROOT / 'outputs/resource_patch_depth_20261015'
PROTOCOL_SHA = '86593f759c5c17823d4eaff19800728229f757eb2ffc82b2f54660e9b32653bb'
ROLES = ('AO', 'G8_joint', 'Pareto4_joint', 'depth8_joint')
DESCRIPTIONS = (
    'AO: inherited pursuit reference; no evolution on resource patches.',
    'G8_joint: fixed G8 population diagnostic comparator; the earlier published endpoint is unchanged.',
    'Pareto4_joint: fixed Pareto4 population diagnostic comparator; the earlier published endpoint is unchanged.',
    'depth8_joint: reporting genome selected on a separate training-world panel before confirmation.',
)


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def read(path):
    return json.loads(Path(path).read_text())


def save(path, value):
    with Path(path).open('x') as stream:
        json.dump(value, stream, indent=2, allow_nan=False)
        stream.write('\n')


def main():
    prepared = read(HERE / 'preparation_receipt.json')
    assert prepared['status'] == 'source_prepared'
    for name, digest in prepared['source_pins'].items():
        assert sha(HERE / name) == digest, name
    for name, digest in prepared['dependency_pins'].items():
        assert sha(ROOT / name) == digest, name
    assert sha(BASE / 'protocol.json') == PROTOCOL_SHA
    protocol = read(BASE / 'protocol.json')
    complete, measured, budget = [read(BASE / name) for name in
                                  ('study_complete.json', 'measurement_complete.json', 'budget.json')]
    assert all(x['status'] == 'complete' and x['protocol_sha256'] == PROTOCOL_SHA
               for x in (complete, measured, budget))
    assert complete['total_calls'] == 97342 and not budget['running'] and not budget['queued']
    assert complete['measurement_complete_sha256'] == sha(BASE / 'measurement_complete.json')
    assert complete['budget_sha256'] == sha(BASE / 'budget.json')
    assert complete['search_complete_sha256'] == sha(BASE / 'runs/pareto/search_complete.json')
    assert budget['terminal_cleanup']['all_owned_groups_exited']
    assert budget['terminal_cleanup']['all_worker_identities_exited']
    assert not budget['terminal_cleanup']['remaining_descendants']
    assert measured['row_index_sha256'] == sha(BASE / 'row_index.json')
    assert measured['endpoints_sha256'] == sha(BASE / 'endpoints.json')
    assert measured['endpoint_selection_sha256'] == sha(BASE / 'endpoint_selection.json')
    endpoints, index = read(BASE / 'endpoints.json'), read(BASE / 'row_index.json')
    assert endpoints['protocol_sha256'] == PROTOCOL_SHA and endpoints['roles'] == list(ROLES)
    assert endpoints['endpoint_selection_sha256'] == measured['endpoint_selection_sha256']
    assert protocol['confirmation_roles'] == list(ROLES) and protocol['confirmation_seeds'][0] == 52530000
    definition = protocol['worlds']['patch']
    world = definition['world']
    assert world['T'] == 1024 and world['patch_count'] == 3 and world['t_open'] == 0
    assert hashlib.sha256(json.dumps(definition, sort_keys=True).encode()).hexdigest() == prepared['world_sha256']
    for name in ('src/__init__.py', 'src/life/__init__.py', 'src/life/spec.py', 'src/lattice.py'):
        assert sha(ROOT / name) == protocol['production_pins'][name]
    sys.path.insert(0, str(ROOT))
    from src.life import spec  # Packing only; no build, evaluator, reference life or RNG import.

    assert list(spec.V6.LEDGER) == definition['ledger_columns'] and len(spec.V6.LEDGER) == 107
    assert spec.V6.pack_world(spec.World(**world)).tolist() == definition['world_vector']
    atlas_path = ROOT / 'results/atlas/play/bodies.json'
    atlas = read(atlas_path)
    inputs = HERE / 'inputs'
    inputs.mkdir(exist_ok=False)
    dependencies = {}
    for name in ('lifesim.js', 'resource_patches_view.js', 'test_resource_patches_view.js'):
        source = ROOT / 'results/atlas/play' / name
        shutil.copyfile(source, inputs / name)
        dependencies[str(source.relative_to(ROOT))] = sha(source)
    filename = 'raw/patch.npz'
    source = BASE / filename
    row = index[filename]
    assert row['status'] == 'validated' and row['world'] == 'patch' and row['stage'] == 'confirmation'
    assert sha(source) == row['sha256'] and row['lives'] == 2048 and row['row_ids'] == list(range(4))
    shutil.copyfile(source, inputs / 'patch_C_fast.npz')
    with np.load(source, allow_pickle=False) as file:
        native = {key: file[key].copy() for key in file.files}
    assert native['ledger'].shape == (2048, 107) and native['hashes'].shape == (2048, 5)
    assert native['seeds'].tolist() == protocol['confirmation_seeds'] and int(native['seeds'][0]) == 52530000
    assert native['protocol_sha256'].item() == PROTOCOL_SHA and native['stage'].item() == 'confirmation'
    assert native['world_name'].item() == 'patch' and native['raw_path'].item() == filename
    assert native['binding_sha256'].item() == sha(BASE / 'endpoints.json')
    assert native['row_ids'].tolist() == list(range(4))
    assert np.all(native['hashes'] == spec.HASH_INIT)
    bodies, cases, genome_pins, parent_paths = [], [], {}, [source]
    for i, role in enumerate(ROLES):
        item = endpoints['genomes'][i]
        assert item['role'] == role and sha(BASE / item['path']) == item['file_sha256']
        genome = read(BASE / item['path'])
        raw = np.concatenate([np.asarray(genome['params'][f.name], dtype=np.float32).reshape(-1)
                              for f in spec.V6.GENOME_FIELDS])
        assert raw.shape == (875,) and hashlib.sha256(raw.tobytes()).hexdigest() == item['raw_sha256']
        packed = spec.V6.pack_genomes(raw[None], world['lattice'])[0]
        packed_sha = hashlib.sha256(packed.tobytes()).hexdigest()
        shutil.copyfile(BASE / item['path'], inputs / f'{role}_genome.json')
        assert native['genome_raw_sha256'][i] == item['raw_sha256']
        truth = [repr(float(x)) for x in native['ledger'][i*512]]
        bodies.append(dict(name=role, abi=6, mode='grn', genotype_sha256=item['raw_sha256'],
                           genome=packed.tolist(), world=world))
        cases.append(dict(role=role, body=i, seed=52530000, native_row=i*512, seed_row=0, ledger=truth,
                          native_file='inputs/patch_C_fast.npz', native_sha256=sha(source)))
        genome_pins[role] = dict(raw_sha256=item['raw_sha256'], packed_sha256=packed_sha,
                                 source_path=item['path'], source_sha256=item['file_sha256'])
        parent_paths.append(BASE / item['path'])
    doc = dict(abi=6, bodies=bodies, lattice=atlas['lattice'], drag=atlas['drag'],
               genome_slices=atlas['genome_slices'])
    fixture = dict(seed=52530000, doc=doc, cases=cases,
                   roles=[dict(name=r, description=d) for r, d in zip(ROLES, DESCRIPTIONS, strict=True)])
    save(inputs / 'fixture.json', fixture)
    parent_paths.extend(BASE / name for name in
                        ('protocol.json', 'row_index.json', 'endpoints.json', 'study_complete.json',
                         'measurement_complete.json', 'budget.json', 'endpoint_selection.json',
                         'runs/pareto/search_complete.json'))
    parent_paths.append(atlas_path)
    for name in ('src/__init__.py', 'src/life/__init__.py', 'src/life/spec.py', 'src/lattice.py'):
        dependencies[name] = sha(ROOT / name)
    sources = ('prepare.py', 'run.py', 'replay.js', 'template.html', 'page.js', 'test_page.js',
               'verify.py', 'monitor_core.py', 'common.py', 'source_origins.json', 'preparation_receipt.json')
    record = dict(status='fixed_cases_ready', seed=52530000, roles=list(ROLES), world='patch', T=1024,
                  JS_replays=4, new_C_lives=0, new_Python_lives=0, builds=0, genome_pins=genome_pins,
                  scientific_protocol_sha256=PROTOCOL_SHA, dependencies=dependencies,
                  parent_pins={str(path.relative_to(ROOT)): sha(path) for path in parent_paths},
                  source_pins={name: sha(HERE / name) for name in sources},
                  input_pins={str(path.relative_to(HERE)): sha(path) for path in sorted(inputs.iterdir())},
                  package_caps=dict(cpu_seconds=15, wall_seconds=60),
                  outside_runtime_reserve=dict(cpu_seconds=3, wall_seconds=5),
                  runtime_budget=dict(cpu_seconds=12, wall_seconds=55, workers=1, threads=1,
                                      cleanup_margin_seconds=1, rss_bytes=1024**3, address_space_bytes=2*1024**3,
                                      minimum_available_bytes=4*1024**3),
                  comparison='107 native ledger values per role; fast-C hashes are constant and prove no trajectory.')
    save(HERE / 'execution_record.json', record)
    print(json.dumps({'status': 'prepared', 'cases': 4, 'new_simulator_calls': 0, 'builds': 0}))


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--run', action='store_true')
    if parser.parse_args().run:
        main()
    else:
        print(json.dumps({'status': 'source_only', 'outcome_reads': 0}))
