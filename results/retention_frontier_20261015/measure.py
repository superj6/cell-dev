"""AK fixed-genome retention and edge cases. Default is a simulation-free description."""
from __future__ import annotations

import argparse
import os
import sys
import time
from pathlib import Path

os.environ.setdefault("ATEN_CPU_CAPABILITY", "avx2")
sys.dont_write_bytecode = True

from common import ROOT, STUDY, checked_release, raw_sha, read, save, sha  # noqa: E402

sys.path.insert(0, str(ROOT))


def parent_check():
    monitor = int(os.environ.get("CELLDEV_MONITOR_PID", "0"))
    if monitor <= 1 or os.getppid() != monitor or os.getpgrp() != os.getpid():
        raise ValueError("measurement must run in the monitor's owned child session")
    if os.environ.get("CELLDEV_PROTOCOL_SHA256") != sha(STUDY / "protocol.json"):
        raise ValueError("monitor protocol binding differs")
    attempt_path = STUDY / "attempt.json"
    if os.environ.get("CELLDEV_ATTEMPT_SHA256") != sha(attempt_path):
        raise ValueError("monitor attempt binding differs")
    attempt = read(attempt_path)
    fields = Path(f"/proc/{monitor}/stat").read_text().rsplit(")", 1)[1].split()
    identity = {"pid": monitor, "ppid": int(fields[1]), "pgid": int(fields[2]),
                "start_ticks": int(fields[19])}
    namespace = os.readlink("/proc/self/ns/pid")
    if (attempt["monitor"] != identity
            or int(os.environ.get("CELLDEV_MONITOR_START_TICKS", "0")) != identity["start_ticks"]
            or attempt["pid_namespace"] != namespace
            or os.environ.get("CELLDEV_PID_NAMESPACE") != namespace
            or os.readlink(f"/proc/{monitor}/ns/pid") != namespace
            or attempt["protocol_sha256"] != sha(STUDY / "protocol.json")
            or attempt["release_sha256"] != sha(STUDY / "release.json")):
        raise ValueError("monitor identity, namespace or release binding differs")
    if "CELLDEV_THREADS_FILE" in os.environ:
        raise ValueError("fixed two-thread budget forbids elastic thread override")


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
    if (STUDY / "raw").exists() or (STUDY / "startup.json").exists():
        raise ValueError("first attempt refuses previous measurements")
    os.environ["CELL_DEV_CACHE"] = str(STUDY / "build-cache")
    os.environ["OMP_NUM_THREADS"] = "2"
    os.environ["OPENBLAS_NUM_THREADS"] = "1"

    import numpy as np
    import torch
    from omegaconf import OmegaConf

    from scripts.taskvar_gates import validate_lives
    from src import checkpoint
    from src.genome import Layout
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
    loaded = [Layout.load(STUDY / rec["path"]) for rec in protocol["genomes"]]
    layout = loaded[0][0]
    genomes = np.stack([genome.numpy() for _, genome in loaded])
    if genomes.shape != (3, 875) or genomes.dtype != np.float32:
        raise ValueError("three exact BODY-1 genomes required")
    if [raw_sha(g) for g in genomes] != [rec["raw_sha256"] for rec in protocol["genomes"]]:
        raise ValueError("raw genotype identity differs")
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
                role=np.asarray(role), cpu_seconds=np.asarray(cpu), wall_seconds=np.asarray(wall),
                production_F=columns["F"][0])
            temp.replace(path)
            index[str(path.relative_to(STUDY))] = {"sha256": sha(path), "lives": len(seeds),
                "cpu_seconds": cpu, "wall_seconds": wall, "abi": abi.version}
            save(STUDY / "row_index.json", index)
            print(f"completed {name}/{role}: {len(seeds)} lives, {cpu:.3f} CPU-s", flush=True)
    save(STUDY / "measurement_complete.json", {"status": "complete", "research_lives": 3072,
         "startup_lives": 4, "rows": 12, "protocol_sha256": sha(STUDY / "protocol.json"),
         "row_index_sha256": sha(STUDY / "row_index.json")}, exclusive=True)


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--run-child", action="store_true")
    args = parser.parse_args()
    if args.run_child:
        measure()
    else:
        print("source only: 3 fixed genomes x 4 worlds x 256 fresh seeds; zero simulation calls")
