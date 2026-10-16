"""Materialize only the fixed population diagnostic inputs; never build, simulate or draw."""
from __future__ import annotations

import hashlib
import json
import os
import shutil
import subprocess
import sys
from pathlib import Path

os.environ.setdefault('ATEN_CPU_CAPABILITY', 'avx2')
sys.dont_write_bytecode = True
STUDY = Path(__file__).resolve().parent
ROOT = STUDY.parents[1]
CURRENT = ROOT / 'results/resource_patch_selection_20261015'
PRIOR = ROOT / 'results/resource_patch_evolution_20261015'
AO = ROOT / 'results/retained_depth_20261015'
GROUPS = ('G8', 'mean4', 'pareto4', 'AO')
WORLDS = ('patch', 'pool', 'persistent', 'blink80_20', 'transfer')
SEEDS = tuple(range(52510000, 52510032))
REVISION = '5d556443e91d558de8de27ab2e5dc7ae11a51415'


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def read(path):
    return json.loads(Path(path).read_text())


def save(path, value):
    with Path(path).open('x') as stream:
        json.dump(value, stream, indent=2, allow_nan=False)
        stream.write('\n')


def raw_sha(array):
    return hashlib.sha256(array.tobytes()).hexdigest()


def materialize_inputs(revision):
    """Return protocol-ready records; caller owns protocol, reservation, release and execution."""
    if any((STUDY / name).exists() for name in ('inputs', 'protocol.json', 'release.json', 'attempt.json')):
        raise ValueError('first materialization requires absent inputs/protocol/runtime artifacts')
    head = subprocess.check_output(['git', 'rev-parse', 'HEAD'], cwd=ROOT, text=True).strip()
    if revision != REVISION or revision != head:
        raise ValueError('explicit current completed milestone revision required')
    audit = read(STUDY / 'namespace/seed_audit.json')
    if (audit['status'] != 'passed' or audit['reserved']
            or audit['whole_block_half_open'] != [52510000, 52520000]
            or audit['development_seeds'] != list(SEEDS)):
        raise ValueError('passed unreserved development seed audit required')

    sys.path.insert(0, str(ROOT))
    import numpy as np
    import torch
    from omegaconf import OmegaConf

    from src import checkpoint
    from src.genome import Layout
    from src.life import spec
    from src.life.evaluate import LifeEvaluator

    torch.set_num_threads(1)
    public = {root: read(root / 'manifest.json') for root in (CURRENT, PRIOR, AO)}
    manifest_entries = {}
    for archive, item in public.items():
        if archive == AO:
            if item.get('phase') != 'terminal' or not isinstance(item.get('artifacts'), dict):
                raise ValueError('AO terminal phase/artifacts manifest required')
            manifest_entries[archive] = item['artifacts']
        else:
            if item.get('status') != 'complete' or not isinstance(item.get('files'), dict):
                raise ValueError('patch complete status/files manifest required')
            manifest_entries[archive] = item['files']
    source_pins, copies = {}, {}

    def bind(source, archive, destination=None):
        relative = str(source.relative_to(archive))
        pin = manifest_entries[archive][relative]
        digest = sha(source)
        if digest != pin['sha256'] or source.stat().st_size != pin['bytes']:
            raise ValueError('public scientific input differs: ' + str(source))
        source_pins[str(source.relative_to(ROOT))] = digest
        if destination is not None:
            if destination in copies:
                raise ValueError('duplicate input destination')
            copies[destination] = source
        return digest

    for archive in (CURRENT, PRIOR, AO):
        source_pins[str((archive / 'manifest.json').relative_to(ROOT))] = sha(archive / 'manifest.json')
    bind(CURRENT / 'protocol.json', CURRENT, 'prior_protocol.json')
    previous = read(CURRENT / 'protocol.json')
    if (previous['total_calls'] != 30808 or tuple(previous['worlds']) != WORLDS
            or previous['endpoint']['reference_captures'] != [19.046875, 16.029296875, 5.919921875]):
        raise ValueError('completed comparison schema differs')
    for name in ('budget.json', 'study_complete.json', 'measurement_complete.json'):
        bind(CURRENT / name, CURRENT)
        if read(CURRENT / name)['status'] != 'complete':
            raise ValueError('completed comparison required')
    for name in ('independent_accounting.json', 'independent_selection.json'):
        bind(CURRENT / 'reviews' / name, CURRENT)
        if read(CURRENT / 'reviews' / name)['status'] != 'passed':
            raise ValueError('independently checked completed comparison required')
    for name, digest in previous['production_pins'].items():
        if sha(ROOT / name) != digest:
            raise ValueError('unchanged production required: ' + name)

    bind(AO / 'runs/balanced/best_genome.json', AO, 'AO.json')
    layout, ao = Layout.load(AO / 'runs/balanced/best_genome.json')
    bind(AO / 'runs/balanced/population.json', AO)
    ao_population = read(AO / 'runs/balanced/population.json')
    if (ao_population['dims'] != layout.dims.__dict__
            or layout.from_dict(ao_population['genomes'][0]).numpy().tobytes() != ao.numpy().tobytes()
            or raw_sha(ao.numpy()) != previous['references'][0]['raw_sha256']):
        raise ValueError('unchanged AO rank-zero reference differs')

    rows, arrays, populations, cached = [], [], {}, {}
    sources = (('G8', PRIOR, 'runs/mixed', 8), ('mean4', CURRENT, 'runs/mean', 4),
               ('pareto4', CURRENT, 'runs/pareto', 4))
    for group, archive, relative, generation in sources:
        folder = archive / relative
        for name in ('population.json', 'checkpoint.pt', 'config.yaml', 'determinism.json'):
            bind(folder / name, archive, f'populations/{group}/{name}')
        population = read(folder / 'population.json')
        saved = checkpoint.load(folder / 'checkpoint.pt')
        checkpoint.validate(saved, OmegaConf.load(folder / 'config.yaml'), read(folder / 'determinism.json'))
        state = saved['state']
        table = np.stack([layout.from_dict(row).numpy() for row in population['genomes']])
        if (population['dims'] != layout.dims.__dict__ or table.shape != (32, 875)
                or table.dtype != np.float32 or not np.isfinite(table).all()
                or len(set(population['ids'])) != 32 or population['ids'] != state['ids'].tolist()
                or state['generation'] != generation or table.tobytes() != state['population'].numpy().tobytes()):
            raise ValueError('exact ordered 32-row population/checkpoint differs: ' + group)
        endpoint_rank = 0
        if group == 'G8':
            bind(folder / 'best_genome.json', archive, 'populations/G8/best_genome.json')
            _, endpoint = Layout.load(folder / 'best_genome.json')
            if endpoint.numpy().tobytes() != table[0].tobytes():
                raise ValueError('G8 fixed rank-zero endpoint differs')
            cached[group] = dict(available=False, reason='No comparable per-life domain capture table was saved.')
        else:
            for name, source in (('g003.npz', folder / 'selection/g003.npz'),
                                 ('endpoint_selection.json', folder / 'endpoint_selection.json'),
                                 ('lineage.jsonl', folder / 'lineage.jsonl')):
                bind(source, archive, f'cached/{group}/{name}')
            record = read(folder / 'endpoint_selection.json')
            endpoint_rank = record['rank']
            if (type(endpoint_rank) is not int or endpoint_rank not in range(32)
                    or record['id'] != population['ids'][endpoint_rank]
                    or record['genome_raw_sha256'] != raw_sha(table[endpoint_rank])
                    or record['checkpoint_sha256'] != sha(folder / 'checkpoint.pt')):
                raise ValueError('fixed reported endpoint differs: ' + group)
            with np.load(folder / 'selection/g003.npz', allow_pickle=False) as data:
                selected = data['shortlist'][data['pick']]
                if (not np.array_equal(data['candidate_ids'][selected], state['ids'].numpy())
                        or data['base_genomes'][selected].tobytes() != table.tobytes()
                        or data['pooled_objectives'][data['pick']].shape != (32, 4)):
                    raise ValueError('cached final-survivor rows differ: ' + group)
            cached[group] = dict(available=True, path=f'inputs/cached/{group}/g003.npz',
                endpoint_path=f'inputs/cached/{group}/endpoint_selection.json',
                lineage_path=f'inputs/cached/{group}/lineage.jsonl', lives=16, per_world_lives=[8, 4, 4])
        start = len(rows)
        for local_row, (genome, native_id) in enumerate(zip(table, population['ids'])):
            rows.append(dict(index=len(rows), label=f'{group}_{local_row:02d}', group=group, row=local_row,
                native_id=native_id, raw_sha256=raw_sha(genome), reported_endpoint=local_row == endpoint_rank))
            arrays.append(genome)
        populations[group] = dict(start=start, count=32, generation=generation, native_ids=population['ids'],
            reported_endpoint_row=endpoint_rank, population_raw_sha256=raw_sha(table),
            source=str((folder / 'population.json').relative_to(ROOT)),
            checkpoint_source=str((folder / 'checkpoint.pt').relative_to(ROOT)))
    rows.append(dict(index=96, label='AO', group='AO', row=0, native_id=ao_population['ids'][0],
                     raw_sha256=raw_sha(ao.numpy()), reported_endpoint=True))
    arrays.append(ao.numpy())
    genomes = np.stack(arrays)
    if genomes.shape != (97, 875) or genomes.dtype != np.float32 or not np.isfinite(genomes).all():
        raise ValueError('97 exact finite raw genotypes required')
    for name, world_record in previous['worlds'].items():
        world = spec.World(**world_record['world'])
        spec.V6.validate_world(world)
        if (world_record['abi'] != 6 or list(spec.V6.LEDGER) != world_record['ledger_columns']
                or spec.V6.pack_world(world).tolist() != world_record['world_vector']):
            raise ValueError('exact ABI6 world packing differs: ' + name)
    cfg = OmegaConf.load(CURRENT / 'runs/mean/config.yaml')
    evaluator = LifeEvaluator(cfg, layout)
    if not evaluator.fast or not evaluator.extinct_charge:
        raise ValueError('unchanged fast production scoring including extinction required')
    bind(CURRENT / 'runs/mean/config.yaml', CURRENT, 'evaluator_config.yaml')
    bind(CURRENT / 'analyze.py', CURRENT, 'accounting.py')
    bind(CURRENT / 'inputs/patch_truth.json', CURRENT, 'patch_truth.json')
    bind(CURRENT / 'inputs/startup_identity.json', CURRENT, 'startup_identity.json')
    if read(CURRENT / 'inputs/startup_identity.json')['identity'] != previous['expected_numerical_identity']:
        raise ValueError('unchanged numerical identity required')
    inputs = STUDY / 'inputs'
    inputs.mkdir()
    for relative, source in copies.items():
        target = inputs / relative
        target.parent.mkdir(parents=True, exist_ok=True)
        shutil.copyfile(source, target)
    with (inputs / 'genomes.npy').open('xb') as stream:
        np.save(stream, genomes, allow_pickle=False)
    save(inputs / 'rows.json', dict(rows=rows, dims=layout.dims.__dict__, shape=[97, 875], dtype='float32',
        raw_sha256=raw_sha(genomes), groups=list(GROUPS), populations=populations, cached=cached,
        original_input_pins=source_pins, fixed_endpoints_only=True))
    result = dict(source_revision=revision, engine_revision=previous['engine_revision'],
        groups=list(GROUPS), seeds=list(SEEDS), worlds=previous['worlds'],
        genome_input='inputs/genomes.npy', rows_input='inputs/rows.json',
        config_input='inputs/evaluator_config.yaml', accounting_input='inputs/accounting.py',
        expected_numerical_identity=previous['expected_numerical_identity'], extinct_charge=True,
        endpoint_reference_captures=previous['endpoint']['reference_captures'],
        endpoint_reference_worlds=previous['endpoint']['worlds'],
        input_pins={str(p.relative_to(STUDY)): sha(p) for p in sorted(inputs.rglob('*')) if p.is_file()},
        original_input_pins=source_pins, production_pins=previous['production_pins'],
        seed_audit_sha256=sha(STUDY / 'namespace/seed_audit.json'),
        preparation_lives=0, preparation_builds=0, preparation_random_draws=0)
    save(STUDY / 'materialized_inputs.json', result)
    return result


if __name__ == '__main__':
    print('Source only. Root preparation calls materialize_inputs(revision) after namespace and source review.')
