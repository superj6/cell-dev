"""AM frozen four-role confirmation after both searches; simulation-free by default."""
from __future__ import annotations

import argparse
import hashlib
import math
import os
import sys
import time

os.environ.setdefault("ATEN_CPU_CAPABILITY", "avx2")
sys.dont_write_bytecode = True

from common import ROOT, STUDY, checked_release, raw_sha, read, save, sha  # noqa: E402

sys.path.insert(0, str(ROOT))
ARMS = ("current_value", "high_value")
ROLES = ("AI_control_start", "AL_mixture_start", "current_value_final", "high_value_final")


def parent_check():
    from common import parent_check as checked_parent
    checked_parent()
    if read(STUDY / "budget.json").get("phase") != "confirmation":
        raise ValueError("confirmation requires its active monitored phase")


def validate_search_state(state):
    if state["generation"] != 4 or [r["gen"] for r in state["curves"]] != list(range(4)):
        raise ValueError("both complete four-generation endpoints are required")
    keys = ("pop_invalid", "pop_mismatch", "recheck_invalid")
    if any(not math.isfinite(float(row[k])) or float(row[k]) != 0
           for row in state["curves"] for k in keys):
        raise ValueError("invalid or mismatched search lives block inference")
    return {key: max(float(row[key]) for row in state["curves"]) for key in keys}


def freeze_endpoints(protocol, identity):
    """Bind both final rank-zero genomes before any fresh confirmation result exists."""
    import numpy as np
    from native_replay import first_cohort
    from omegaconf import OmegaConf
    from population_loader import extended_identity as population_identity
    from population_loader import loader_identity
    from selection import extended_identity as selection_identity
    from selection import selection_identity as selection_config

    from src import checkpoint
    from src.genome import Layout

    references = (protocol["ancestral_reference"], protocol["reference"])
    for role, reference in zip(ROLES[:2], references):
        if reference["role"] != role or sha(STUDY / reference["path"]) != reference["file_sha256"]:
            raise ValueError("fixed starting reference differs")
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
        saved = checkpoint.load(folder / "checkpoint.pt")
        checkpoint.validate(saved, cfg, extended)  # Reuse the one captured identity; zero extra goldens.
        health = validate_search_state(saved["state"])
        if read(folder / "determinism.json") != extended:
            raise ValueError("search numerical/source identity differs")
        logs = {}
        for name, metadata in saved["logs"].items():
            data = (folder / name).read_bytes()
            if len(data) != metadata["bytes"] or hashlib.sha256(data).hexdigest() != metadata["sha256"]:
                raise ValueError("checkpoint log bytes differ")
            logs[name] = sha(folder / name)
        path = folder / "best_genome.json"
        endpoint_layout, genome = Layout.load(path)
        if genome.numpy().tobytes() != saved["state"]["population"][0].numpy().tobytes():
            raise ValueError("endpoint differs from final population rank zero")
        public = read(folder / "population.json")
        public_rows = np.stack([endpoint_layout.from_dict(p).numpy() for p in public["genomes"]])
        if (public_rows.shape != (32, 875)
                or public_rows.tobytes() != saved["state"]["population"].numpy().tobytes()
                or public["ids"] != saved["state"]["ids"].tolist()
                or public["fitness"] != saved["state"]["fitness"].tolist()):
            raise ValueError("public final population differs from checkpoint")
        paths.append(path)
        searches[arm] = {"generation": 4, "rank": 0, "search_health": health,
            "checkpoint_sha256": sha(folder / "checkpoint.pt"), "log_pins": logs,
            "genome_file_sha256": sha(path), "genome_raw_sha256": raw_sha(genome.numpy()),
            "population_file_sha256": sha(folder / "population.json"),
            "population_raw_sha256": raw_sha(public_rows), "determinism_sha256": sha(folder / "determinism.json"),
            "results_sha256": sha(folder / "results.jsonl"), "numerical_identity": extended}
    loaded = [Layout.load(path) for path in paths]
    layout = loaded[0][0]
    if any(other.dims != layout.dims for other, _ in loaded):
        raise ValueError("confirmation genome layouts differ")
    genomes = np.stack([genome.numpy() for _, genome in loaded])
    if genomes.shape != (4, 875) or genomes.dtype != np.float32 or not np.isfinite(genomes).all():
        raise ValueError("four exact BODY-1 genotypes required")
    if any(raw_sha(genomes[i]) != reference["raw_sha256"] for i, reference in enumerate(references)):
        raise ValueError("starting reference raw bytes differ")
    records = [{"role": role, "path": str(path.relative_to(STUDY)),
                "file_sha256": sha(path), "raw_sha256": raw_sha(genome)}
               for role, path, genome in zip(ROLES, paths, genomes)]
    replay = first_cohort(STUDY, protocol)  # Recorded operations only: no RNG, builds or lives.
    save(STUDY / "first_cohort_replay.json", replay, exclusive=True)
    manifest = {"protocol_sha256": sha(STUDY / "protocol.json"), "roles": list(ROLES),
                "genomes": records, "searches": searches,
                "first_cohort_replay_sha256": sha(STUDY / "first_cohort_replay.json"),
                "selection": "Both complete generation4 final population rank0 endpoints fixed before confirmation."}
    save(STUDY / "endpoints.json", manifest, exclusive=True)
    return layout, genomes, manifest


def check_visibility_truth():
    """Two exact replays of one already retained ABI4 truth case, not research."""
    import numpy as np

    from src.life import build, spec

    fixture = read(STUDY / "inputs/visibility_truth.json")
    body = fixture["body"]
    fields = dict(body["world"])
    for key in (*spec.INT_WORLD_KEYS, "flags", "fork_flags"):
        if key in fields:
            if int(fields[key]) != fields[key]:
                raise ValueError("nonintegral integer world field in retained fixture")
            fields[key] = int(fields[key])
    world = spec.world(body["preset"], lattice="hexprism", **fields)
    kwargs = dict(genomes=np.asarray(body["genome"], dtype=np.float64)[None],
                  abi=spec.V4, threads=1)
    full = build.run(world, [fixture["seed"]], **kwargs)
    ledger = np.asarray(fixture["ledger"], dtype=np.float64)
    hashes = np.asarray([int(x, 16) for x in fixture["hashes"]], dtype=np.uint64)
    if full.ledger[0].tobytes() != ledger.tobytes() or full.hashes[0].tobytes() != hashes.tobytes():
        raise ValueError("retained ABI4 renewal truth differs")
    fast = build.run(world, [fixture["seed"]], fast=True, **kwargs)
    if fast.ledger.tobytes() != full.ledger.tobytes():
        raise ValueError("ABI4 full/fast truth ledgers differ")
    return {"name": fixture["name"], "seed": fixture["seed"], "lives": 2,
            "ledger_sha256": raw_sha(full.ledger), "hashes_sha256": raw_sha(full.hashes)}


def measure():
    parent_check()
    protocol = checked_release()
    if any((STUDY / name).exists() for name in ("raw", "startup.json", "endpoints.json", "first_cohort_replay.json")):
        raise ValueError("first attempt refuses previous measurements")
    os.environ["CELL_DEV_CACHE"] = str(STUDY / "build-cache")
    os.environ["OMP_NUM_THREADS"] = "2"
    os.environ["OPENBLAS_NUM_THREADS"] = "1"

    import numpy as np
    import torch
    from omegaconf import OmegaConf

    from scripts.taskvar_gates import validate_lives
    from src import checkpoint
    from src.life import build, spec
    from src.life.evaluate import LifeDraw, LifeEvaluator

    torch.set_num_threads(1)
    identity = checkpoint.numerical_identity()  # One existing ABI3 full/fast golden pair.
    expected = read(STUDY / "inputs/startup_identity.json")["identity"]
    if identity != expected:
        raise ValueError("numerical identity changed from the completed AG study")
    visibility = check_visibility_truth()
    save(STUDY / "startup.json", {"identity": identity, "visibility": visibility,
         "startup_lives": 4, "protocol_sha256": sha(STUDY / "protocol.json")}, exclusive=True)
    seeds = np.asarray(protocol["seeds"], dtype=np.uint64)
    cfg_base = OmegaConf.load(STUDY / "inputs/config.yaml")
    layout, genomes, endpoints = freeze_endpoints(protocol, identity)
    endpoint_digest = sha(STUDY / "endpoints.json")
    index = {}
    for name, definition in protocol["worlds"].items():
        abi = {3: spec.V3, 4: spec.V4}[definition["abi"]]
        world = spec.World(**definition["world"])
        cfg = OmegaConf.create(OmegaConf.to_container(cfg_base, resolve=True))
        cfg.life.abi = abi.version
        cfg.threads = 2
        evaluator = LifeEvaluator(cfg, layout)
        if not evaluator.extinct_charge or not protocol["extinct_charge"]:
            raise ValueError("original extinction accounting must remain active")
        if abi.pack_world(world).tolist() != definition["world_vector"]:
            raise ValueError("world packing differs")
        draw = LifeDraw(tuple(int(s) for s in seeds), tuple(world for _ in seeds))
        for role_index, role in enumerate(protocol["roles"]):
            parent_check()
            if checked_release() != protocol:
                raise ValueError("release changed during measurement")
            if sha(STUDY / "endpoints.json") != endpoint_digest:
                raise ValueError("frozen endpoint manifest changed")
            if any(sha(STUDY / item["path"]) != item["file_sha256"] for item in endpoints["genomes"]):
                raise ValueError("frozen endpoint genome file changed")
            path = STUDY / "raw" / name / f"row_{role_index:02d}.npz"
            path.parent.mkdir(parents=True, exist_ok=True)
            if path.exists():
                raise ValueError("refuse repeated row")
            start_cpu, start_wall = time.process_time(), time.perf_counter()
            result = build.run(world, seeds, genomes=abi.pack_genomes(genomes[role_index:role_index + 1],
                               world.lattice), abi=abi, fast=True, threads=2)
            cpu, wall = time.process_time() - start_cpu, time.perf_counter() - start_wall
            validate_lives(result, world, allow_guards=True)
            columns = evaluator.columns(result, 1, draw)
            temp = path.with_suffix(".tmp.npz")
            np.savez_compressed(temp, ledger=result.ledger, hashes=result.hashes, seeds=seeds,
                genome_raw_sha256=np.asarray(raw_sha(genomes[role_index])),
                protocol_sha256=np.asarray(sha(STUDY / "protocol.json")), world_name=np.asarray(name),
                endpoints_sha256=np.asarray(endpoint_digest),
                role=np.asarray(role), cpu_seconds=np.asarray(cpu), wall_seconds=np.asarray(wall),
                production_F=columns["F"][0])
            temp.replace(path)
            index[str(path.relative_to(STUDY))] = {"sha256": sha(path), "lives": len(seeds),
                "cpu_seconds": cpu, "wall_seconds": wall, "abi": abi.version}
            save(STUDY / "row_index.json", index)
            print(f"completed {name}/{role}: {len(seeds)} lives, {cpu:.3f} CPU-s", flush=True)
    save(STUDY / "measurement_complete.json", {"status": "complete", "research_lives": 8192,
         "startup_lives": 4, "rows": 16, "protocol_sha256": sha(STUDY / "protocol.json"),
         "row_index_sha256": sha(STUDY / "row_index.json"), "endpoints_sha256": endpoint_digest}, exclusive=True)


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--run-child", action="store_true")
    args = parser.parse_args()
    if args.run_child:
        measure()
    else:
        print("source only: 4 fixed genomes x 4 worlds x 512 fresh seeds; zero simulation calls")
