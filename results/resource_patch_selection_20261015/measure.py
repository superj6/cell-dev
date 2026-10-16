"""ABI6 four-role confirmation after matched mean/Pareto continuations; simulation-free by default."""
from __future__ import annotations

import argparse
import hashlib
import math
import os
import sys
import time
from pathlib import Path

os.environ.setdefault("ATEN_CPU_CAPABILITY", "avx2")
sys.dont_write_bytecode = True

from common import ROOT, STUDY, checked_release, raw_sha, read, save, sha  # noqa: E402

sys.path.insert(0, str(ROOT))
ARMS = ("mean", "pareto")
ROLES = ("AO_start", "patch8_start", "mean4", "pareto4")
WORLDS = ("patch", "pool", "persistent", "blink80_20", "transfer")


def parent_check():
    from common import parent_check as checked_parent
    checked_parent()
    if read(STUDY / "budget.json").get("phase") != "confirmation":
        raise ValueError("confirmation requires its active monitored phase")


def validate_search_state(state):
    if state["generation"] != 4 or [r["gen"] for r in state["curves"]] != list(range(4)):
        raise ValueError("the fixed four-generation final checkpoint is required")
    keys = ("pop_invalid", "pop_mismatch", "recheck_invalid")
    if any(not math.isfinite(float(row[k])) or float(row[k]) != 0
           for row in state["curves"] for k in keys):
        raise ValueError("invalid or mismatched search lives block inference")
    return {key: max(float(row[key]) for row in state["curves"]) for key in keys}


def freeze_endpoints(protocol, identity):
    """Bind both ancestors and the common-rule final endpoints before confirmation."""
    import numpy as np
    from omegaconf import OmegaConf
    from population_loader import extended_identity as population_identity
    from population_loader import loader_identity
    from search import verify_endpoint
    from selection import extended_identity as selection_identity
    from selection import selection_identity as selection_config

    from src import checkpoint
    from src.genome import Layout

    references = protocol["references"]
    if len(references) != 2 or [item["role"] for item in references] != list(ROLES[:2]):
        raise ValueError("ordered AO and patch-generation-eight references required")
    for reference in references:
        if sha(STUDY / reference["path"]) != reference["file_sha256"]:
            raise ValueError("fixed ancestral reference differs")
    paths = [STUDY / reference["path"] for reference in references]
    searches = {}
    for arm in ARMS:
        folder = STUDY / "runs" / arm
        cfg = OmegaConf.load(STUDY / protocol["configs"][arm]["path"])
        population = loader_identity(protocol["population_start"])
        selection = selection_config(arm, protocol["selection_worlds"])
        if (OmegaConf.to_container(cfg.population_start, resolve=True) != population
                or OmegaConf.to_container(cfg.retention_selection, resolve=True) != selection):
            raise ValueError("configured external identities differ")
        extended = selection_identity(population_identity(identity, population), selection)
        if read(folder / "determinism.json") != extended:
            raise ValueError("search numerical/source identity differs")
        marker = read(folder / "search_complete.json")
        if (marker["status"] != "complete" or marker["protocol_sha256"] != sha(STUDY / "protocol.json")
                or marker["release_sha256"] != sha(STUDY / "release.json")
                or any(sha(folder / name) != digest for name, digest in marker["output_pins"].items())):
            raise ValueError("completed search artifacts differ")
        if marker["arm"] != arm or marker["research_lives"] != 10278 or marker["startup_lives"] != 4:
            raise ValueError("completed search call inventory differs")
        if marker["count_proof"] != {"selection": 10240, "valid": 32, "final": 6, "growth_half": 2,
                                     "native_evals": 1280, "generations": 4, "children_per_generation": 224}:
            raise ValueError("fixed search counts or T512 growth diagnostic differ")
        saved = checkpoint.load(folder / "checkpoint.pt")
        checkpoint.validate(saved, cfg, extended)  # Captured identity; no extra golden calls.
        state = saved["state"]
        health = validate_search_state(state)
        if (state["evals"] != 1024 or state["rc_lives"] != 2048
                or tuple(state["population"].shape) != (32, 875)):
            raise ValueError("fixed final checkpoint population/counts differ")
        if set(saved["logs"]) != {"curves.jsonl", "lineage.jsonl", "clones.jsonl"}:
            raise ValueError("checkpoint log coverage differs")
        for name, pin in saved["logs"].items():
            data = (folder / name).read_bytes()
            if len(data) != pin["bytes"] or hashlib.sha256(data).hexdigest() != pin["sha256"]:
                raise ValueError("final checkpoint log bytes differ")
        endpoint = verify_endpoint(folder, cfg, extended)  # Recompute from cached pooled16; no lives/RNG.
        if endpoint != read(folder / "endpoint_selection.json") or endpoint != marker["endpoint"]:
            raise ValueError("common endpoint selection receipt differs")
        rank = endpoint["rank"]
        if (type(rank) is not int or rank not in range(32) or endpoint["status"] != "complete"
                or endpoint["arm"] != arm or endpoint["generation"] != 4
                or endpoint["id"] != int(state["ids"][rank])
                or endpoint["added_lives"] != 0 or endpoint["random_draws"] != 0):
            raise ValueError("common endpoint identity or zero-call selection differs")
        path = folder / "joint_genome.json"
        endpoint_layout, genome = Layout.load(path)
        if (genome.numpy().tobytes() != state["population"][rank].numpy().tobytes()
                or endpoint["genome_file_sha256"] != sha(path)
                or endpoint["genome_raw_sha256"] != raw_sha(genome.numpy())
                or endpoint["checkpoint_sha256"] != sha(folder / "checkpoint.pt")
                or endpoint["population_raw_sha256"] != raw_sha(state["population"].numpy())):
            raise ValueError("joint endpoint differs from its recorded checkpoint row")
        public = read(folder / "population.json")
        rows = np.stack([endpoint_layout.from_dict(item).numpy() for item in public["genomes"]])
        if (rows.shape != (32, 875) or rows.tobytes() != state["population"].numpy().tobytes()
                or public["ids"] != state["ids"].tolist() or public["fitness"] != state["fitness"].tolist()):
            raise ValueError("public final population differs from checkpoint")
        searches[arm] = {"generation": 4, "selected_rank": rank, "selected_id": endpoint["id"],
                        "search_health": health, "checkpoint_sha256": sha(folder / "checkpoint.pt"),
                        "checkpoint_log_pins": saved["logs"], "endpoint": endpoint,
                        "endpoint_selection_sha256": sha(folder / "endpoint_selection.json"),
                        "population_file_sha256": sha(folder / "population.json"),
                        "determinism_sha256": sha(folder / "determinism.json"),
                        "results_sha256": sha(folder / "results.jsonl"), "numerical_identity": extended}
        paths.append(path)
    loaded = [Layout.load(path) for path in paths]
    layout = loaded[0][0]
    if any(other.dims != layout.dims for other, _ in loaded):
        raise ValueError("confirmation genome layouts differ")
    genomes = np.stack([genome.numpy() for _, genome in loaded])
    if genomes.shape != (4, 875) or genomes.dtype != np.float32 or not np.isfinite(genomes).all():
        raise ValueError("four exact BODY-1 genotypes required")
    if any(raw_sha(genomes[i]) != reference["raw_sha256"] for i, reference in enumerate(references)):
        raise ValueError("ancestral reference raw bytes differ")
    genotypes = [{"role": role, "path": str(path.relative_to(STUDY)),
                  "file_sha256": sha(path), "raw_sha256": raw_sha(genome)}
                 for role, path, genome in zip(ROLES, paths, genomes)]
    manifest = {"protocol_sha256": sha(STUDY / "protocol.json"), "roles": list(ROLES),
                "genomes": genotypes, "searches": searches,
                "selection": "Both arms use their frozen common-rule endpoint from all32 final survivors' "
                             "cached base8+recheck8 lives, before confirmation; native rank0 remains distinct."}
    save(STUDY / "endpoints.json", manifest, exclusive=True)
    return layout, genomes, manifest


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
    if attempt not in [STUDY / "execution" / phase / "attempt.json" for phase in (*ARMS, "confirmation")]:
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


def measure():
    parent_check()
    protocol = checked_release()
    if (tuple(protocol["roles"]) != ROLES or tuple(protocol["worlds"]) != WORLDS
            or protocol["seeds"] != list(range(52500000, 52500512))
            or not protocol["extinct_charge"]):
        raise ValueError("exact four-role/five-world/512-seed confirmation required")
    if any((STUDY / name).exists() for name in ("raw", "scored", "startup.json", "endpoints.json", "row_index.json")):
        raise ValueError("first attempt refuses previous measurements")
    os.environ["CELL_DEV_CACHE"] = str(STUDY / "build-cache")
    os.environ["OMP_NUM_THREADS"] = "2"
    os.environ["OPENBLAS_NUM_THREADS"] = "1"

    import numpy as np
    import torch
    from analyze import LEDGER, identical, reconstruct
    from omegaconf import OmegaConf

    from src import checkpoint
    from src.life import build, spec
    from src.life.evaluate import LifeDraw, LifeEvaluator

    torch.set_num_threads(1)
    identity = checkpoint.numerical_identity()  # Existing ABI3 full/fast golden pair: exactly two lives.
    expected = read(STUDY / "inputs/startup_identity.json")["identity"]
    if identity != expected or identity != protocol["expected_numerical_identity"]:
        raise ValueError("numerical identity differs from the frozen current source/binary record")
    patches = check_patch_truth()  # Exactly two additional ABI6 truth lives.
    save(STUDY / "startup.json", {"identity": identity, "patches": patches, "startup_lives": 4,
         "protocol_sha256": sha(STUDY / "protocol.json")}, exclusive=True)
    seeds = np.asarray(protocol["seeds"], dtype=np.uint64)
    cfg_base = OmegaConf.load(STUDY / protocol["configs"]["mean"]["path"])
    layout, genomes, endpoints = freeze_endpoints(protocol, identity)
    endpoint_digest = sha(STUDY / "endpoints.json")
    index = {}
    for name, definition in protocol["worlds"].items():
        abi = spec.V6
        world = spec.World(**definition["world"])
        if (definition["abi"] != 6 or definition["ledger_columns"] != list(LEDGER)
                or tuple(abi.LEDGER) != LEDGER or abi.pack_world(world).tolist() != definition["world_vector"]):
            raise ValueError("ABI6 world or ledger schema differs")
        cfg = OmegaConf.create(OmegaConf.to_container(cfg_base, resolve=True))
        cfg.life.abi, cfg.threads = 6, 2
        evaluator = LifeEvaluator(cfg, layout)
        if evaluator.abi.version != 6 or not evaluator.extinct_charge or evaluator.has_envelope:
            raise ValueError("fixed ABI6 scorer and original extinction accounting required")
        draw = LifeDraw(tuple(int(seed) for seed in seeds), tuple(world for _ in seeds))
        for role_index, role in enumerate(ROLES):
            parent_check()
            if checked_release() != protocol or sha(STUDY / "endpoints.json") != endpoint_digest:
                raise ValueError("release or frozen endpoint manifest changed")
            if any(sha(STUDY / item["path"]) != item["file_sha256"] for item in endpoints["genomes"]):
                raise ValueError("frozen endpoint genome file changed")
            path = STUDY / "raw" / name / f"row_{role_index:02d}.npz"
            relative = str(path.relative_to(STUDY))
            index[relative] = {"status": "started", "requested_lives": 512, "abi": 6,
                               "role": role, "world": name}
            save(STUDY / "row_index.json", index)
            start_cpu, start_wall = time.process_time(), time.perf_counter()
            result = build.run(world, seeds, genomes=abi.pack_genomes(genomes[role_index:role_index+1],
                               world.lattice), abi=abi, fast=True, threads=2)
            cpu, wall = time.process_time()-start_cpu, time.perf_counter()-start_wall
            native = dict(ledger=result.ledger, hashes=result.hashes, seeds=seeds,
                genome_raw_sha256=np.asarray(raw_sha(genomes[role_index])),
                protocol_sha256=np.asarray(sha(STUDY / "protocol.json")), world_name=np.asarray(name),
                raw_path=np.asarray(relative),
                endpoints_sha256=np.asarray(endpoint_digest), role=np.asarray(role),
                cpu_seconds=np.asarray(cpu), wall_seconds=np.asarray(wall))
            atomic_npz(path, **native)  # Preserve every returned row before accounting or status checks.
            index[relative].update(status="returned", sha256=sha(path), lives=512,
                                   cpu_seconds=cpu, wall_seconds=wall)
            save(STUDY / "row_index.json", index)
            metrics, health = reconstruct(native, definition, protocol["seeds"])
            columns = evaluator.columns(result, 1, draw)
            if (not identical(columns["F"][0], metrics["F"])
                    or not identical(columns["F_kernel"][0], metrics["native_F"])
                    or not identical(columns["extinct_charge"][0], metrics["extinct_charge"])):
                raise ValueError("production evaluator differs from independent extinction accounting")
            scored = STUDY / "scored" / name / f"row_{role_index:02d}.npz"
            atomic_npz(scored, raw_sha256=np.asarray(sha(path)), production_F=columns["F"][0],
                       native_F=columns["F_kernel"][0], extinct_charge=columns["extinct_charge"][0])
            index[relative].update(status="validated", scored_path=str(scored.relative_to(STUDY)),
                                   scored_sha256=sha(scored), health=health)
            save(STUDY / "row_index.json", index)
            print(f"completed {name}/{role}: 512 lives, {cpu:.3f} CPU-s", flush=True)
    save(STUDY / "measurement_complete.json", {"status": "complete", "research_lives": 10240,
         "startup_lives": 4, "rows": 20, "protocol_sha256": sha(STUDY / "protocol.json"),
         "row_index_sha256": sha(STUDY / "row_index.json"), "endpoints_sha256": endpoint_digest}, exclusive=True)


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--run-child", action="store_true")
    args = parser.parse_args()
    if args.run_child:
        measure()
    else:
        print("source only: 4 fixed genomes x 5 worlds x 512 fresh seeds + 4 startup lives; zero calls")

