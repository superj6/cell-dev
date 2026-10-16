"""Owned fresh-panel endpoint selection followed by four-reference ABI6 confirmation."""
from __future__ import annotations

import argparse
import json
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
        raise ValueError("first attempt refuses an existing data row")
    temporary = path.with_suffix(".tmp.npz")
    with temporary.open("xb") as stream:
        np.savez_compressed(stream, **values)
        stream.flush()
        os.fsync(stream.fileno())
    temporary.replace(path)


def check_patch_truth():
    """Exactly two ABI6 engineering replays of the pinned first conservation fixture."""
    import numpy as np

    from src.life import build, spec

    parent_check()
    document = read(STUDY / "inputs/patch_truth.json")
    if document["status"] != "complete" or document["abi"] != 6:
        raise ValueError("completed retained ABI6 truth document required")
    fixture = document["cases"][0]
    if fixture["name"] != "reflex_count1" or fixture["seed"] != 42000000:
        raise ValueError("first fixed engineering case changed")
    body = fixture["body"]
    fields = dict(body["world"])
    for key in (*spec.INT_WORLD_KEYS, "flags", "fork_flags"):
        if key in fields:
            if int(fields[key]) != fields[key]:
                raise ValueError("nonintegral integer field in engineering fixture")
            fields[key] = int(fields[key])
    world = spec.world(body["preset"], lattice="hexprism", **fields)
    if (body["mode"] != "program" or world.patch_count != 1 or world.T != 96
            or spec.V6.pack_world(world).tolist() != [body["world"][key] for key in spec.V6.WORLD_KEYS]):
        raise ValueError("fixed program truth tables differ")
    tables = dict(programs=np.asarray(body["program"], dtype=np.float64), init=body["cells"],
                  abi=spec.V6, threads=1)
    attempt = Path(os.environ["CELLDEV_ATTEMPT_PATH"])
    if attempt not in [STUDY / "execution" / phase / "attempt.json" for phase in ("pareto", "measurement")]:
        raise ValueError("engineering truth must belong to the monitored phase")
    out = attempt.parent / "patch_truth"
    out.mkdir(exist_ok=False)
    calls = [{"backend": "C_full", "seed": fixture["seed"], "status": "started"}]
    save(out / "calls.json", calls)
    full = build.run(world, [fixture["seed"]], **tables,
                     raster_cap=document["raster_cap"], fate_cap=document["fate_cap"])
    atomic_npz(out / "full.npz", ledger=full.ledger, hashes=full.hashes,
               raster_t=full.raster_t, raster_uid=full.raster_uid, raster_n=full.raster_n,
               fate_i=full.fate_i, fate_f=full.fate_f, fate_n=full.fate_n)
    calls[0].update(status="returned", raw_sha256=sha(out / "full.npz"))
    save(out / "calls.json", calls)
    ledger = np.asarray(fixture["ledger"], dtype=np.float64)
    hashes = np.asarray([int(value, 16) for value in fixture["hashes"]], dtype=np.uint64)
    if full.ledger[0].tobytes() != ledger.tobytes() or full.hashes[0].tobytes() != hashes.tobytes():
        raise ValueError("retained ABI6 full ledger or hash families differ")
    calls.append({"backend": "C_fast", "seed": fixture["seed"], "status": "started"})
    save(out / "calls.json", calls)
    fast = build.run(world, [fixture["seed"]], **tables, fast=True)
    atomic_npz(out / "fast.npz", ledger=fast.ledger, hashes=fast.hashes)
    calls[1].update(status="returned", raw_sha256=sha(out / "fast.npz"))
    save(out / "calls.json", calls)
    if (fast.ledger.tobytes() != full.ledger.tobytes()
            or not np.all(fast.hashes == spec.HASH_INIT)):
        raise ValueError("ABI6 full/fast ledger or fast constant hashes differ")
    for call in calls:
        call["status"] = "validated"
    save(out / "calls.json", calls)
    return {"name": fixture["name"], "seed": fixture["seed"], "lives": 2,
            "ledger_sha256": raw_sha(full.ledger), "hashes_sha256": raw_sha(full.hashes),
            "fixture_sha256": sha(STUDY / "inputs/patch_truth.json"),
            "calls_path": str((out / "calls.json").relative_to(STUDY)),
            "calls_sha256": sha(out / "calls.json")}


def freeze_population(protocol, identity):
    """Validate the completed native search, then retain all32 rows before any endpoint lives."""
    import numpy as np
    from omegaconf import OmegaConf
    from population_loader import extended_identity as population_identity
    from population_loader import loader_identity
    from search import complete_search
    from selection import extended_identity as selection_identity
    from selection import selection_identity as selection_config

    from src import checkpoint
    from src.genome import Layout

    cfg = OmegaConf.load(STUDY / protocol['configs']['pareto']['path'])
    out = STUDY / 'runs/pareto'
    if Path(cfg.logging.output_dir).resolve() != out.resolve():
        raise ValueError('native output path differs')
    population = loader_identity(protocol['population_start'])
    selection = selection_config('pareto', protocol['selection_worlds'])
    if (OmegaConf.to_container(cfg.population_start, resolve=True) != population
            or OmegaConf.to_container(cfg.retention_selection, resolve=True) != selection):
        raise ValueError('configured population/selection identity differs')
    extended = selection_identity(population_identity(identity, population), selection)
    marker = complete_search(cfg, 'pareto', extended)  # Saved files only; no fresh identity/life call.
    if marker != read(out / 'search_complete.json'):
        raise ValueError('completed native search marker differs')
    saved = checkpoint.load(out / 'checkpoint.pt')
    checkpoint.validate(saved, cfg, extended)
    state = saved['state']
    genomes, ids = state['population'].numpy(), state['ids'].numpy()
    if (state['generation'] != 8 or genomes.shape != (32, 875) or genomes.dtype != np.float32
            or not np.isfinite(genomes).all() or ids.shape != (32,) or ids.dtype != np.int64
            or len(set(ids.tolist())) != 32):
        raise ValueError('all32 ordered final raw genomes and native IDs required')
    layout, native_best = Layout.load(out / 'best_genome.json')
    if native_best.numpy().tobytes() != genomes[0].tobytes():
        raise ValueError('native rank0 differs; it is not automatically the reporting endpoint')
    atomic_npz(STUDY / 'endpoint_population.npz', genomes=genomes, ids=ids)
    meta = dict(status='complete', protocol_sha256=sha(STUDY / 'protocol.json'), dims=layout.dims.__dict__,
        population_raw_sha256=raw_sha(genomes), ids=ids.tolist(),
        array_sha256=sha(STUDY / 'endpoint_population.npz'),
        source_pins={f'runs/pareto/{name}': sha(out / name) for name in
                     ('checkpoint.pt', 'population.json', 'determinism.json', 'search_complete.json')},
        reporting_endpoint_selected=False)
    save(STUDY / 'endpoint_population.json', meta, exclusive=True)
    return cfg, layout, genomes, ids


def run_batch(protocol, helper, evaluator, genomes, ids, world_name, stage, binding, index):
    import numpy as np
    from analyze import reconstruct_batch

    from src.life import spec
    from src.life.evaluate import LifeDraw

    parent_check()
    if checked_release() != protocol:
        raise ValueError('frozen release changed before a cohort')
    prefix = 'endpoint_' if stage == 'endpoint' else ''
    binding_path = STUDY / ('endpoint_population.json' if stage == 'endpoint' else 'endpoints.json')
    if sha(binding_path) != binding:
        raise ValueError('frozen cohort genotype manifest changed')
    if stage == 'confirmation':
        for row in read(binding_path)['genomes']:
            if sha(STUDY / row['path']) != row['file_sha256']:
                raise ValueError('fixed confirmation genome changed')
    seeds = np.asarray(protocol['endpoint_seeds' if stage == 'endpoint' else 'confirmation_seeds'], dtype=np.uint64)
    definition = protocol['worlds'][world_name]
    world = spec.World(**definition['world'])
    if (definition['abi'] != 6 or definition['ledger_columns'] != list(helper.LEDGER)
            or spec.V6.pack_world(world).tolist() != definition['world_vector']):
        raise ValueError('fixed ABI6 world/ledger packing differs')
    draw = LifeDraw(tuple(int(seed) for seed in seeds), tuple(world for _ in seeds))
    relative = f'{prefix}raw/{world_name}.npz'
    path = STUDY / relative
    count = len(genomes)*len(seeds)
    index[relative] = dict(status='started', requested_lives=count, world=world_name,
                          stage=stage, row_ids=list(ids), abi=6)
    save(STUDY / ('endpoint_index.json' if stage == 'endpoint' else 'row_index.json'), index)
    cpu, wall = time.process_time(), time.perf_counter()
    result = evaluator.run(genomes, draw)
    native = dict(ledger=result.ledger, hashes=result.hashes, seeds=seeds,
        row_ids=np.asarray(ids, dtype=np.int64), genome_raw_sha256=np.asarray([raw_sha(row) for row in genomes]),
        protocol_sha256=np.asarray(sha(STUDY / 'protocol.json')), world_name=np.asarray(world_name),
        stage=np.asarray(stage), raw_path=np.asarray(relative), binding_sha256=np.asarray(binding),
        cpu_seconds=np.asarray(time.process_time()-cpu), wall_seconds=np.asarray(time.perf_counter()-wall))
    atomic_npz(path, **native)  # Every returned native row precedes any accounting/status check.
    index[relative].update(status='returned', lives=count, sha256=sha(path),
        cpu_seconds=float(native['cpu_seconds']), wall_seconds=float(native['wall_seconds']))
    save(STUDY / ('endpoint_index.json' if stage == 'endpoint' else 'row_index.json'), index)
    values, health = reconstruct_batch(native, definition, seeds.tolist(), ids, helper)
    columns = evaluator.columns(result, len(genomes), draw)
    for field, key in (('F', 'F'), ('F_kernel', 'native_F'), ('extinct_charge', 'extinct_charge')):
        if not helper.identical(columns[field], np.stack([row[key] for row in values])):
            raise ValueError('production scoring differs from retained physical accounting')
    scored = STUDY / f'{prefix}scored/{world_name}.npz'
    atomic_npz(scored, raw_sha256=np.asarray(sha(path)), production_F=columns['F'],
               native_F=columns['F_kernel'], extinct_charge=columns['extinct_charge'])
    index[relative].update(status='validated', scored_path=str(scored.relative_to(STUDY)),
                           scored_sha256=sha(scored), health=health)
    save(STUDY / ('endpoint_index.json' if stage == 'endpoint' else 'row_index.json'), index)
    print(f'completed {stage}/{world_name}: {count} lives', flush=True)
    return values


def measure():
    parent_check()
    if Path(os.environ['CELLDEV_ATTEMPT_PATH']) != STUDY / 'execution/measurement/attempt.json':
        raise ValueError('measurement must belong to its sole owned phase')
    protocol = checked_release()
    release_pin = sha(STUDY / 'release.json')
    absent = ('endpoint_population.npz', 'endpoint_population.json', 'endpoint_raw', 'endpoint_scored',
              'endpoint_index.json', 'endpoint_selection.json', 'joint_genome.json', 'endpoints.json',
              'raw', 'scored', 'row_index.json', 'startup.json', 'measurement_complete.json', 'summary.json')
    if any((STUDY / name).exists() for name in absent):
        raise ValueError('first measurement refuses existing artifacts')
    os.environ['CELL_DEV_CACHE'] = str(STUDY / 'build-cache')
    os.environ['OMP_NUM_THREADS'] = '2'
    os.environ['OPENBLAS_NUM_THREADS'] = '1'

    import numpy as np
    import torch
    from analyze import (
        ROLES,
        TRAIN,
        WORLDS,
        accounting,
        endpoint_statistics,
        protocol_scope,
        references,
        verify_endpoint,
    )

    from src import checkpoint
    from src.genome import Layout
    from src.life.evaluate import LifeEvaluator

    protocol_scope(protocol)
    helper = accounting(STUDY, protocol)
    ref_manifest, ref_genomes = references(STUDY, protocol)
    torch.set_num_threads(1)
    identity = checkpoint.numerical_identity()  # Exactly the retained golden full/fast pair.
    if (identity != protocol['expected_numerical_identity']
            or identity != read(STUDY / 'inputs/startup_identity.json')['identity']):
        raise ValueError('frozen numerical identity differs')
    truth = check_patch_truth()  # Exactly two retained ABI6 engineering lives, once in this worker.
    save(STUDY / 'startup.json', dict(identity=identity, patches=truth, startup_lives=4,
         protocol_sha256=sha(STUDY / 'protocol.json')), exclusive=True)
    cfg, layout, population, ids = freeze_population(protocol, identity)
    for i, record in enumerate(ref_manifest['rows']):
        ref_layout, vector = Layout.load(STUDY / record['path'])
        if ref_layout.dims != layout.dims or vector.numpy().tobytes() != ref_genomes[i].tobytes():
            raise ValueError('reference file/array/layout differs')
    evaluator = LifeEvaluator(cfg, layout)
    if (evaluator.abi.version != 6 or not evaluator.fast or not evaluator.extinct_charge
            or evaluator.has_envelope or evaluator.threads != 2):
        raise ValueError('fixed fast ABI6 production scorer required')
    endpoint_index, values = {}, {}
    population_pin = sha(STUDY / 'endpoint_population.json')
    for world in TRAIN:
        values[world] = run_batch(protocol, helper, evaluator, population, ids.tolist(), world,
                                  'endpoint', population_pin, endpoint_index)
    selected = endpoint_statistics(values, ids, [raw_sha(row) for row in population], helper)
    row = selected['selected_row']
    chosen = population[row]
    save(STUDY / 'joint_genome.json', dict(dims=layout.dims.__dict__,
         params=layout.to_dict(torch.from_numpy(chosen.copy()))), exclusive=True)
    endpoint = dict(status='complete', protocol_sha256=sha(STUDY / 'protocol.json'),
        population_manifest_sha256=population_pin, endpoint_index_sha256=sha(STUDY / 'endpoint_index.json'),
        genome_file_sha256=sha(STUDY / 'joint_genome.json'), selection=selected)
    save(STUDY / 'endpoint_selection.json', endpoint, exclusive=True)
    verified, _, _ = verify_endpoint(STUDY, protocol, helper)  # Re-read exact saved panel, no extra life.
    if verified != endpoint:
        raise ValueError('saved endpoint selection changed before confirmation')
    records = [dict(role=record['role'], path=record['path'], file_sha256=record['file_sha256'],
                    raw_sha256=record['raw_sha256'], native_id=record['native_id'])
               for record in ref_manifest['rows']]
    records.append(dict(role=ROLES[3], path='joint_genome.json', file_sha256=sha(STUDY/'joint_genome.json'),
                        raw_sha256=raw_sha(chosen), native_id=selected['selected_id'], native_row=row))
    manifest = dict(protocol_sha256=sha(STUDY/'protocol.json'), roles=list(ROLES), genomes=records,
        references_manifest_sha256=sha(STUDY/protocol['references_manifest']),
        endpoint_selection_sha256=sha(STUDY/'endpoint_selection.json'),
        selection_scope='Fresh training-only endpoint panel; confirmation never selects or replaces a genome.')
    save(STUDY/'endpoints.json', manifest, exclusive=True)
    genomes = np.concatenate((ref_genomes, chosen[None, :]), axis=0)
    index = {}
    endpoint_pin = sha(STUDY/'endpoints.json')
    for world in WORLDS:
        run_batch(protocol, helper, evaluator, genomes, list(range(4)), world,
                  'confirmation', endpoint_pin, index)
    parent_check()
    if checked_release() != protocol or sha(STUDY/'release.json') != release_pin:
        raise ValueError('frozen protocol/release changed during measurement')
    save(STUDY/'measurement_complete.json', dict(status='complete', research_lives=15360,
        startup_lives=4, total_calls=15364, endpoint_lives=3072, confirmation_lives=12288,
        endpoint_batches=3, confirmation_batches=6, protocol_sha256=sha(STUDY/'protocol.json'),
        endpoint_index_sha256=sha(STUDY/'endpoint_index.json'), row_index_sha256=sha(STUDY/'row_index.json'),
        endpoint_selection_sha256=sha(STUDY/'endpoint_selection.json'),
        endpoints_sha256=sha(STUDY/'endpoints.json'), startup_sha256=sha(STUDY/'startup.json')), exclusive=True)


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--run-child', action='store_true')
    if parser.parse_args().run_child:
        measure()
        from analyze import analyze
        result = analyze(STUDY)  # Same owned worker; no further simulator calls.
        with (STUDY/'summary.json').open('x') as stream:
            json.dump(result, stream, separators=(',', ':'), allow_nan=False)
            stream.write('\n')
            stream.flush()
            os.fsync(stream.fileno())
    else:
        print('source only: endpoint selection and confirmation require the owned --run-child phase')


