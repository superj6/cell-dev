"""One fixed all-survivor development panel; raw native bytes precede scoring checks."""
from __future__ import annotations

import argparse
import os
import sys
import time
from pathlib import Path

os.environ.setdefault('ATEN_CPU_CAPABILITY', 'avx2')
sys.dont_write_bytecode = True

from common import ROOT, STUDY, checked_release, parent_check, raw_sha, read, save, sha  # noqa: E402

sys.path.insert(0, str(ROOT))


def atomic_npz(path, **values):
    import numpy as np

    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    if path.exists():
        raise ValueError('first attempt refuses an existing data row')
    temporary = path.with_suffix('.tmp.npz')
    with temporary.open('xb') as stream:
        np.savez_compressed(stream, **values)
        stream.flush()
        os.fsync(stream.fileno())
    temporary.replace(path)


def check_patch_truth():
    """Reuse the fixed ABI6 truth pair; only its local output/ownership path changes."""
    import numpy as np

    from src.life import build, spec

    parent_check()
    document = read(STUDY / 'inputs/patch_truth.json')
    if document['status'] != 'complete' or document['abi'] != 6:
        raise ValueError('completed retained ABI6 truth document required')
    fixture = document['cases'][0]
    if fixture['name'] != 'reflex_count1' or fixture['seed'] != 42000000:
        raise ValueError('first fixed engineering case changed')
    body = fixture['body']
    fields = dict(body['world'])
    for key in (*spec.INT_WORLD_KEYS, 'flags', 'fork_flags'):
        if key in fields:
            if int(fields[key]) != fields[key]:
                raise ValueError('nonintegral integer field in engineering fixture')
            fields[key] = int(fields[key])
    world = spec.world(body['preset'], lattice='hexprism', **fields)
    if (body['mode'] != 'program' or world.patch_count != 1 or world.T != 96
            or spec.V6.pack_world(world).tolist() != [body['world'][key] for key in spec.V6.WORLD_KEYS]):
        raise ValueError('fixed program truth tables differ')
    tables = dict(programs=np.asarray(body['program'], dtype=np.float64), init=body['cells'],
                  abi=spec.V6, threads=1)
    out = STUDY / 'startup_truth'
    out.mkdir(exist_ok=False)
    calls = [{'backend': 'C_full', 'seed': fixture['seed'], 'status': 'started'}]
    save(out / 'calls.json', calls)
    full = build.run(world, [fixture['seed']], **tables,
                     raster_cap=document['raster_cap'], fate_cap=document['fate_cap'])
    atomic_npz(out / 'full.npz', ledger=full.ledger, hashes=full.hashes,
               raster_t=full.raster_t, raster_uid=full.raster_uid, raster_n=full.raster_n,
               fate_i=full.fate_i, fate_f=full.fate_f, fate_n=full.fate_n)
    calls[0].update(status='returned', raw_sha256=sha(out / 'full.npz'))
    save(out / 'calls.json', calls)
    ledger = np.asarray(fixture['ledger'], dtype=np.float64)
    hashes = np.asarray([int(value, 16) for value in fixture['hashes']], dtype=np.uint64)
    if full.ledger[0].tobytes() != ledger.tobytes() or full.hashes[0].tobytes() != hashes.tobytes():
        raise ValueError('retained ABI6 full ledger or hash families differ')
    calls.append({'backend': 'C_fast', 'seed': fixture['seed'], 'status': 'started'})
    save(out / 'calls.json', calls)
    fast = build.run(world, [fixture['seed']], **tables, fast=True)
    atomic_npz(out / 'fast.npz', ledger=fast.ledger, hashes=fast.hashes)
    calls[1].update(status='returned', raw_sha256=sha(out / 'fast.npz'))
    save(out / 'calls.json', calls)
    if fast.ledger.tobytes() != full.ledger.tobytes() or not np.all(fast.hashes == spec.HASH_INIT):
        raise ValueError('ABI6 full/fast ledger or fast constant hashes differ')
    for call in calls:
        call['status'] = 'validated'
    save(out / 'calls.json', calls)
    return {'name': fixture['name'], 'seed': fixture['seed'], 'lives': 2,
            'ledger_sha256': raw_sha(full.ledger), 'hashes_sha256': raw_sha(full.hashes),
            'fixture_sha256': sha(STUDY / 'inputs/patch_truth.json'),
            'calls_path': str((out / 'calls.json').relative_to(STUDY)), 'calls_sha256': sha(out / 'calls.json')}


def measure():
    parent_check()
    protocol = checked_release()
    release_sha = sha(STUDY / 'release.json')
    if any((STUDY / name).exists() for name in
           ('raw', 'scored', 'startup.json', 'startup_truth', 'row_index.json', 'measurement_complete.json')):
        raise ValueError('first attempt refuses previous measurements')
    threads = int(protocol['runtime_budget']['threads'])
    if threads not in (1, 2):
        raise ValueError('fixed small native thread count required')
    os.environ['CELL_DEV_CACHE'] = str(STUDY / 'build-cache')
    os.environ['OMP_NUM_THREADS'] = str(threads)
    os.environ['OPENBLAS_NUM_THREADS'] = '1'

    import numpy as np
    import torch
    from analyze import GROUPS, RANGES, WORLDS, accounting, inputs, reconstruct_batch
    from omegaconf import OmegaConf

    from src import checkpoint
    from src.genome import make_dims, make_layout
    from src.life import spec
    from src.life.evaluate import LifeDraw, LifeEvaluator

    manifest, genomes = inputs(STUDY, protocol)
    helper = accounting(STUDY, protocol)
    layout = make_layout(make_dims(manifest['dims']))
    if layout.size != 875:
        raise ValueError('exact ABI6 raw genome layout required')
    torch.set_num_threads(1)
    identity = checkpoint.numerical_identity()  # Existing golden full/fast pair: exactly two lives.
    if identity != protocol['expected_numerical_identity']:
        raise ValueError('numerical identity differs from frozen current sources/binaries')
    patches = check_patch_truth()  # Exactly two additional retained ABI6 engineering lives.
    save(STUDY / 'startup.json', dict(identity=identity, patches=patches, startup_lives=4,
         protocol_sha256=sha(STUDY / 'protocol.json')), exclusive=True)
    seeds = np.asarray(protocol['seeds'], dtype=np.uint64)
    cfg_base = OmegaConf.load(STUDY / protocol['config_input'])
    rows_pin = sha(STUDY / protocol['rows_input'])
    index = {}
    for world_name in WORLDS:
        definition = protocol['worlds'][world_name]
        world = spec.World(**definition['world'])
        if (definition['abi'] != 6 or definition['ledger_columns'] != list(helper.LEDGER)
                or spec.V6.pack_world(world).tolist() != definition['world_vector']):
            raise ValueError('ABI6 world or ledger schema differs')
        cfg = OmegaConf.create(OmegaConf.to_container(cfg_base, resolve=True))
        cfg.life.abi, cfg.threads = 6, threads
        evaluator = LifeEvaluator(cfg, layout)
        if (evaluator.abi.version != 6 or not evaluator.extinct_charge or evaluator.has_envelope
                or not evaluator.fast or evaluator.kind != world.lattice):
            raise ValueError('fixed ABI6 scorer and original extinction accounting required')
        draw = LifeDraw(tuple(int(s) for s in seeds), tuple(world for _ in seeds))
        for group in GROUPS:
            parent_check()
            if checked_release() != protocol or sha(STUDY / protocol['rows_input']) != rows_pin:
                raise ValueError('release or row manifest changed')
            start, stop = RANGES[group]
            indices, B = list(range(start, stop)), stop-start
            relative = f'raw/{world_name}/{group}.npz'
            path = STUDY / relative
            index[relative] = dict(status='started', requested_lives=B*32, abi=6, group=group,
                                   world=world_name, row_indices=indices)
            save(STUDY / 'row_index.json', index)
            before_cpu, before_wall = time.process_time(), time.perf_counter()
            result = evaluator.run(genomes[start:stop], draw)  # Validated B x L Cartesian/native ordering.
            native = dict(ledger=result.ledger, hashes=result.hashes, seeds=seeds,
                          row_indices=np.asarray(indices, dtype=np.int64),
                          genome_raw_sha256=np.asarray([r['raw_sha256'] for r in manifest['rows'][start:stop]]),
                          protocol_sha256=np.asarray(sha(STUDY / 'protocol.json')),
                          rows_manifest_sha256=np.asarray(rows_pin), world_name=np.asarray(world_name),
                          group=np.asarray(group), raw_path=np.asarray(relative),
                          cpu_seconds=np.asarray(time.process_time()-before_cpu),
                          wall_seconds=np.asarray(time.perf_counter()-before_wall))
            atomic_npz(path, **native)  # Every returned native byte is retained before rejection/scoring.
            index[relative].update(status='returned', sha256=sha(path), lives=B*32,
                                   cpu_seconds=float(native['cpu_seconds']), wall_seconds=float(native['wall_seconds']))
            save(STUDY / 'row_index.json', index)
            metrics, health = reconstruct_batch(native, definition, protocol['seeds'], indices, helper)
            columns = evaluator.columns(result, B, draw)
            expected = {name: np.stack([row[key] for row in metrics]) for name, key in
                        (('F', 'F'), ('F_kernel', 'native_F'), ('extinct_charge', 'extinct_charge'))}
            if any(not helper.identical(columns[name], value) for name, value in expected.items()):
                raise ValueError('production evaluator differs from reused accounting')
            scored = STUDY / 'scored' / world_name / (group + '.npz')
            atomic_npz(scored, raw_sha256=np.asarray(sha(path)), production_F=columns['F'],
                       native_F=columns['F_kernel'], extinct_charge=columns['extinct_charge'])
            index[relative].update(status='validated', scored_path=str(scored.relative_to(STUDY)),
                                   scored_sha256=sha(scored), health=health)
            save(STUDY / 'row_index.json', index)
            print(f'completed {world_name}/{group}: {B} fixed rows x32 lives', flush=True)
    parent_check()
    if checked_release() != protocol or sha(STUDY / 'release.json') != release_sha:
        raise ValueError('frozen protocol or release changed during measurement')
    save(STUDY / 'measurement_complete.json', dict(status='complete', research_lives=15520,
         startup_lives=4, total_calls=15524, batches=20, genomes=97, genome_world_rows=485,
         lives_per_genome_world=32, protocol_sha256=sha(STUDY / 'protocol.json'),
         row_index_sha256=sha(STUDY / 'row_index.json'), rows_manifest_sha256=rows_pin,
         startup_sha256=sha(STUDY / 'startup.json')), exclusive=True)


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--run-child', action='store_true')
    if parser.parse_args().run_child:
        measure()
        from analyze import analyze
        save(STUDY / 'summary.json', analyze(STUDY), exclusive=True)
    else:
        print('source only: measurement requires --run-child in the owned monitor')
