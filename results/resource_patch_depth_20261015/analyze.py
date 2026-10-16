"""Saved-data endpoint selection and paired confirmation; no simulator entrypoints."""
from __future__ import annotations

import argparse
import hashlib
import importlib.util
import json
import sys
from pathlib import Path

import numpy as np

STUDY = Path(__file__).resolve().parent
sys.dont_write_bytecode = True
sys.path.insert(0, str(STUDY.parents[1]))
ROLES = ('AO', 'G8_joint', 'Pareto4_joint', 'depth8_joint')
TRAIN = ('patch', 'pool', 'persistent')
WORLDS = (*TRAIN, 'blink80_20', 'transfer', 'reserved_capacity3')
SCALES = (19.046875, 16.029296875, 5.919921875)
WEIGHTS = (.5, .25, .25)
ACCOUNTING_SHA = '0ac39bb7b11a754f73acff2b77c0690ce4b525b688664da34cc6006b9da1373b'
ENDPOINT_RULE = ('Among all32 final survivors maximize the minimum of three capture means divided by fixed AO '
                 'scales, then 0.5patch+0.25POOL+0.25persistent production F, then native survivor ID ascending; '
                 '32 separate fresh lives per training world; confirmation never selects an endpoint.')
ENDPOINT_METRICS = ('captures', 'F', 'cost', 'total_patch_initial_harvest', 'total_patch_refill_harvest',
                    'total_patch_empty', 'misses', 'path', 'n_end', 'guarded', 'extinct')


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def read(path):
    return json.loads(Path(path).read_text())


def raw_sha(value):
    return hashlib.sha256(np.asarray(value).tobytes()).hexdigest()


def require(condition, message):
    if not condition:
        raise ValueError(message)


def protocol_scope(protocol):
    require(tuple(protocol['worlds']) == WORLDS and tuple(protocol['selection_worlds']) == TRAIN
            and protocol['endpoint_seeds'] == list(range(52520000, 52520032))
            and protocol['confirmation_seeds'] == list(range(52530000, 52530512))
            and protocol['endpoint_reference_captures'] == list(SCALES)
            and protocol['endpoint_reference_worlds'] == list(TRAIN) and protocol['extinct_charge'],
            'fixed endpoint/confirmation scope differs')
    require(all(protocol['selection_worlds'][w] == protocol['worlds'][w]['world'] for w in TRAIN),
            'selection and endpoint training worlds differ')
    reserved = dict(protocol['worlds']['patch']['world'], patch_count=4, patch_capacity=3,
                    R_min=2.5, R_max=4.5, patch_refill_fast=60., patch_refill_slow=180.)
    require(protocol['worlds']['reserved_capacity3']['world'] == reserved, 'reserved physical combination differs')


def accounting(study, protocol):
    path = study / protocol['accounting_input']
    require(sha(path) == ACCOUNTING_SHA == protocol['input_pins'][protocol['accounting_input']],
            'unchanged validated physical accounting helper required')
    descriptor = importlib.util.spec_from_file_location('depth_pinned_accounting', path)
    module = importlib.util.module_from_spec(descriptor)
    descriptor.loader.exec_module(module)
    return module


def references(study, protocol):
    for name, digest in protocol['input_pins'].items():
        require(sha(study / name) == digest, 'input pin differs: ' + name)
    manifest = read(study / protocol['references_manifest'])
    array = np.load(study / protocol['reference_input'], allow_pickle=False)
    require(manifest['roles'] == list(ROLES[:3]) == protocol['reference_roles']
            and manifest['rows'] == protocol['references'] and manifest['shape'] == [3, 875]
            and manifest['dtype'] == 'float32' and array.shape == (3, 875) and array.dtype == np.float32
            and np.isfinite(array).all() and raw_sha(array) == manifest['raw_sha256'],
            'three exact ordered reference genomes required')
    for i, row in enumerate(manifest['rows']):
        require(row['role'] == ROLES[i] and row['raw_sha256'] == raw_sha(array[i])
                and row['file_sha256'] == sha(study / row['path']), 'reference identity differs')
    return manifest, array


def endpoint_population(study):
    """Bind the panel to the completed native checkpoint/public population without new identity calls."""
    from src import checkpoint
    from src.genome import make_dims, make_layout

    meta = read(study / 'endpoint_population.json')
    require(meta['status'] == 'complete' and meta['protocol_sha256'] == sha(study / 'protocol.json'),
            'endpoint population provenance differs')
    for name, digest in meta['source_pins'].items():
        require(sha(study / name) == digest, 'completed population source differs: ' + name)
    with np.load(study / 'endpoint_population.npz', allow_pickle=False) as data:
        population, ids = data['genomes'].copy(), data['ids'].copy()
    require(population.shape == (32, 875) and population.dtype == np.float32 and np.isfinite(population).all()
            and ids.shape == (32,) and ids.dtype == np.int64 and len(set(ids.tolist())) == 32
            and np.all(ids >= 0) and raw_sha(population) == meta['population_raw_sha256']
            and ids.tolist() == meta['ids'] and sha(study / 'endpoint_population.npz') == meta['array_sha256'],
            'complete ordered endpoint population differs')
    saved = checkpoint.load(study / 'runs/pareto/checkpoint.pt')
    state = saved['state']
    require(state['generation'] == 8 and state['evals'] == 2048 and state['rc_lives'] == 16384
            and state['population'].numpy().tobytes() == population.tobytes()
            and state['ids'].tolist() == ids.tolist(), 'endpoint population differs from native checkpoint')
    public = read(study / 'runs/pareto/population.json')
    layout = make_layout(make_dims(meta['dims']))
    decoded = np.stack([layout.from_dict(row).numpy() for row in public['genomes']])
    require(public['dims'] == meta['dims'] and public['ids'] == ids.tolist()
            and decoded.tobytes() == population.tobytes(), 'public endpoint population differs')
    return population, ids, meta


def reconstruct_batch(native, definition, seeds, row_ids, helper, scored=None):
    B, n = len(row_ids), len(seeds)
    require(native['ledger'].shape == (B*n, 107) and native['hashes'].shape == (B*n, 5)
            and helper.identical(native['row_ids'], np.asarray(row_ids, dtype=np.int64)),
            'genotype-major cohort dimensions or identities differ')
    if scored is not None:
        require(all(scored[k].shape == (B, n) for k in ('production_F', 'native_F', 'extinct_charge')),
                'scored cohort shape differs')
    values, health = [], []
    for j in range(B):
        row = {k: native[k] for k in ('seeds', 'cpu_seconds', 'wall_seconds')}
        row.update(ledger=native['ledger'][j*n:(j+1)*n], hashes=native['hashes'][j*n:(j+1)*n])
        if scored is not None:
            row['production_F'] = scored['production_F'][j]
        metric, checked = helper.reconstruct(row, definition, seeds)
        if scored is not None:
            require(helper.identical(scored['native_F'][j], metric['native_F'])
                    and helper.identical(scored['extinct_charge'][j], metric['extinct_charge']),
                    'native/extinction scoring differs')
        values.append(metric)
        health.append(checked)
    return values, health


def load_batch(study, protocol, helper, index, world, stage, row_ids, genome_hashes, binding):
    prefix = 'endpoint_' if stage == 'endpoint' else ''
    raw_path, scored_path = f'{prefix}raw/{world}.npz', f'{prefix}scored/{world}.npz'
    entry = index[raw_path]
    seeds = protocol['endpoint_seeds' if stage == 'endpoint' else 'confirmation_seeds']
    require(entry['status'] == 'validated' and entry['world'] == world and entry['stage'] == stage
            and entry['abi'] == 6 and entry['row_ids'] == list(row_ids)
            and entry['lives'] == len(row_ids)*len(seeds) and entry['sha256'] == sha(study / raw_path)
            and entry['scored_path'] == scored_path and entry['scored_sha256'] == sha(study / scored_path),
            'returned cohort index differs')
    with np.load(study / raw_path, allow_pickle=False) as data:
        native = {key: data[key].copy() for key in data.files}
    with np.load(study / scored_path, allow_pickle=False) as data:
        scored = {key: data[key].copy() for key in data.files}
    for key, expected in (('world_name', world), ('stage', stage), ('raw_path', raw_path),
                          ('protocol_sha256', sha(study / 'protocol.json')), ('binding_sha256', binding)):
        require(np.asarray(native[key]).shape == () and native[key].item() == expected,
                'raw cohort metadata differs: ' + key)
    require(native['genome_raw_sha256'].tolist() == list(genome_hashes)
            and scored['raw_sha256'].item() == entry['sha256'], 'cohort genotype/scored binding differs')
    values, health = reconstruct_batch(native, protocol['worlds'][world], seeds, row_ids, helper, scored)
    require(health == entry['health'], 'cohort health differs')
    return values, health


def endpoint_statistics(values, ids, genome_hashes, helper):
    """Pure supplied-array ranking: fixed capture scales, weighted ordinary F and deterministic native IDs."""
    ids = np.asarray(ids)
    require(ids.shape == (32,) and len(set(ids.tolist())) == 32 and len(genome_hashes) == 32,
            'all32 unique survivor IDs required')
    require(all(len(values[w]) == 32 for w in TRAIN), 'three complete endpoint cohorts required')
    rows, objectives = [], []
    for j, native_id in enumerate(ids):
        for w in TRAIN:
            require(all(np.asarray(values[w][j][k]).shape == (32,) for k in ENDPOINT_METRICS),
                    'endpoint values must retain32 whole lives')
        cap = [float(values[w][j]['captures'].mean()) for w in TRAIN]
        weighted = sum(weight*values[w][j]['F'] for weight, w in zip(WEIGHTS, TRAIN, strict=True))
        objective = cap + [float(weighted.mean())]
        require(np.isfinite(objective).all(), 'nonfinite endpoint objectives')
        fractions = [x/scale for x, scale in zip(cap, SCALES, strict=True)]
        objectives.append(objective)
        rows.append(dict(row=j, native_id=int(native_id), raw_sha256=genome_hashes[j],
            objectives=objective, capture_fractions=fractions, joint_minimum=min(fractions),
            weighted_F=helper.describe(weighted),
            worlds={w: {k: helper.describe(values[w][j][k]) for k in ENDPOINT_METRICS} for w in TRAIN}))
    order = sorted(range(32), key=lambda j: (-rows[j]['joint_minimum'], -objectives[j][3], int(ids[j])))
    selected = order[0]
    return dict(rule=ENDPOINT_RULE, capture_scales=list(SCALES), fitness_weights=list(WEIGHTS),
                rows=rows, order=order, selected_row=selected, selected_id=int(ids[selected]),
                selected_raw_sha256=genome_hashes[selected], development_only=True,
                minimum_has_no_linear_SE=True, endpoint_lives=3072, random_draws=0)


def verify_endpoint(study, protocol, helper):
    population, ids, meta = endpoint_population(study)
    index = read(study / 'endpoint_index.json')
    require(set(index) == {f'endpoint_raw/{w}.npz' for w in TRAIN}, 'three endpoint batches required')
    hashes = [raw_sha(row) for row in population]
    values = {w: load_batch(study, protocol, helper, index, w, 'endpoint', ids.tolist(), hashes,
                            sha(study / 'endpoint_population.json'))[0] for w in TRAIN}
    computed = endpoint_statistics(values, ids, hashes, helper)
    selection = read(study / 'endpoint_selection.json')
    require(selection['selection'] == computed and selection['status'] == 'complete'
            and selection['protocol_sha256'] == sha(study / 'protocol.json')
            and selection['endpoint_index_sha256'] == sha(study / 'endpoint_index.json')
            and selection['population_manifest_sha256'] == sha(study / 'endpoint_population.json')
            and selection['genome_file_sha256'] == sha(study / 'joint_genome.json'),
            'independent fresh-panel endpoint receipt differs')
    from src.genome import Layout
    _, chosen = Layout.load(study / 'joint_genome.json')
    require(chosen.numpy().tobytes() == population[computed['selected_row']].tobytes(),
            'reported genome differs from selected native survivor')
    return selection, population[computed['selected_row']], meta


def analyze(study):
    protocol = read(study / 'protocol.json')
    protocol_scope(protocol)
    helper = accounting(study, protocol)
    reference_manifest, reference_genomes = references(study, protocol)
    selection, chosen, _ = verify_endpoint(study, protocol, helper)
    endpoints = read(study / 'endpoints.json')
    genomes = np.concatenate((reference_genomes, chosen[None, :]), axis=0)
    require(endpoints['roles'] == list(ROLES) and endpoints['protocol_sha256'] == sha(study / 'protocol.json')
            and endpoints['references_manifest_sha256'] == sha(study / protocol['references_manifest'])
            and endpoints['endpoint_selection_sha256'] == sha(study / 'endpoint_selection.json')
            and len(endpoints['genomes']) == 4, 'confirmation endpoint provenance differs')
    for i, record in enumerate(endpoints['genomes']):
        require(record['role'] == ROLES[i] and record['raw_sha256'] == raw_sha(genomes[i])
                and record['file_sha256'] == sha(study / record['path']), 'fixed confirmation genome differs')
    complete = read(study / 'measurement_complete.json')
    expected = dict(status='complete', research_lives=15360, startup_lives=4, total_calls=15364,
                    endpoint_lives=3072, confirmation_lives=12288, endpoint_batches=3, confirmation_batches=6,
                    protocol_sha256=sha(study / 'protocol.json'),
                    endpoint_index_sha256=sha(study / 'endpoint_index.json'),
                    row_index_sha256=sha(study / 'row_index.json'),
                    endpoint_selection_sha256=sha(study / 'endpoint_selection.json'),
                    endpoints_sha256=sha(study / 'endpoints.json'), startup_sha256=sha(study / 'startup.json'))
    require(complete == expected, 'complete measurement count/provenance marker differs')
    index = read(study / 'row_index.json')
    require(set(index) == {f'raw/{w}.npz' for w in WORLDS}, 'six confirmation batches required')
    absolute, paired, health, retention = {}, {}, {}, {}
    for world in WORLDS:
        metrics, checked = load_batch(study, protocol, helper, index, world, 'confirmation', list(range(4)),
                                     [raw_sha(row) for row in genomes], sha(study / 'endpoints.json'))
        absolute[world] = {role: {k: helper.describe(v) for k, v in row.items()}
                           for role, row in zip(ROLES, metrics, strict=True)}
        health[world] = dict(zip(ROLES, checked, strict=True))
        paired[world] = {f'depth8_joint_minus_{role}': {
            k: helper.describe(metrics[3][k]-metrics[i][k]) for k in metrics[3]}
            for i, role in enumerate(ROLES[:3])}
        if world in ('pool', 'persistent', 'blink80_20'):
            retention[world] = {}
            for i, role in enumerate(ROLES[:3]):
                new, old = metrics[3]['captures'], metrics[i]['captures']
                margin = helper.describe(new-.9*old)
                retention[world][f'depth8_joint_vs_{role}'] = dict(
                    captures_difference=helper.describe(new-old), retained_90_percent_margin=margin,
                    mean_capture_ratio=None if old.mean() == 0 else float(new.mean()/old.mean()),
                    lower_3se_positive=margin['lower_3se'] > 0, diagnostic_only_not_a_gate=True)
    return dict(status='complete', research_lives=15360, endpoint_lives=3072, confirmation_lives=12288,
                startup_lives=4, paired_life_clusters=512, endpoint_batches=3, confirmation_batches=6,
                absolute=absolute, paired=paired, health=health, old_world_retention=retention,
                primary_contrast='depth8_joint_minus_Pareto4_joint', endpoint_development=selection['selection'],
                fixed_references=reference_manifest['rows'], protocol_sha256=sha(study / 'protocol.json'),
                row_index_sha256=sha(study / 'row_index.json'),
                endpoint_index_sha256=sha(study / 'endpoint_index.json'),
                endpoints_sha256=sha(study / 'endpoints.json'),
                endpoint_selection_sha256=sha(study / 'endpoint_selection.json'),
                limitations=[
                    'One combined deeper/denser continuation; no causal comparison of evaluation precision or depth.',
                    'Life SE does not measure evolutionary replication; three-SE bounds are descriptive.',
                    'G8_joint/Pareto4_joint are new-study development references; historical endpoints stay fixed.',
                    'All 32 final rows use a separate 32-per-world endpoint panel; confirmation selects no genome.',
                    'Endpoint ranks/minima have development selection optimism; they are not confirmed scores.',
                    'Initial/refill FIFO origin is physical accounting, not evidence of revisit strategies or memory.',
                    'The first five worlds are development-known; reserved_capacity3 is one new parameter combination.',
                    'Four capacity-three patches start with more food; initial and refill harvest stay separate.',
                    'Guards/extinction retain ordinary charges; all returned rows are preserved before validation.',
                    'Fast hashes are constants. No trajectory, formal admission or broad generality claim.'])


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--study', type=Path, default=STUDY)
    parser.add_argument('--output', type=Path)
    args = parser.parse_args()
    if args.output is None:
        print('source only: saved-data analysis requires --output')
    else:
        with args.output.open('x') as stream:
            json.dump(analyze(args.study), stream, separators=(',', ':'), allow_nan=False)
            stream.write('\n')
