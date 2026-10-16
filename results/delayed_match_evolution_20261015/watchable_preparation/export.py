"""Prepare twelve fixed lineage illustrations only after a separately bounded execution record."""
from __future__ import annotations

import argparse
import hashlib
import json
import os
import sys
import time
from pathlib import Path

HERE = Path(__file__).resolve().parent
STUDY = HERE.parent
ROOT = HERE.parents[2]
ARTIFACT = HERE / "artifact"
ROLES = ("AO_start", "mixed8", "mixed24")
SEEDS = (52460000, 52460001, 52460002, 52460003)
SOURCE_FILES = ("export.py", "replay.js", "viewer.js", "template.html", "delayed_match_view.js",
                "assemble.py", "test_ui.js", "run.py", "monitor_core.py", "PLAN.md", "source_origins.json")
BUDGET = dict(cpu_seconds=60, wall_seconds=180, workers=1, threads=1,
              address_space_bytes=8*1024**3, rss_bytes=4*1024**3, minimum_available_bytes=4*1024**3)


def read(path):
    return json.loads(Path(path).read_text())


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def save(path, value, *, exclusive=False):
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path if exclusive else path.with_suffix(path.suffix+".tmp")
    with temporary.open("x") as stream:
        json.dump(value, stream, indent=2, allow_nan=False)
        stream.write("\n")
        stream.flush()
        os.fsync(stream.fileno())
    if not exclusive:
        temporary.replace(path)


def checked_record(path, *, worker=False):
    registered = read(path)
    if (registered["status"] != "registered_fixed_delayed_match_viewer"
            or registered["roles"] != list(ROLES) or registered["seeds"] != list(SEEDS)
            or registered["world"] != "match85" or registered["budget"] != BUDGET
            or registered["C_full_lives"] != 12 or registered["JS_replay_lives"] != 12
            or set(registered["source_pins"]) != set(SOURCE_FILES)):
        raise ValueError("exact twelve-case viewer execution record required")
    for name, digest in registered["source_pins"].items():
        if sha(HERE/name) != digest:
            raise ValueError("changed watchable source: "+name)
    expected = ("protocol.json", "budget.json", "measurement_complete.json", "endpoints.json", "row_index.json")
    if set(registered["study_pins"]) != set(expected):
        raise ValueError("complete scientific artifact pins required")
    for name, digest in registered["study_pins"].items():
        if sha(STUDY/name) != digest:
            raise ValueError("changed completed study artifact: "+name)
    for name in ("results/atlas/play/lifesim.js", "results/atlas/play/bodies.json"):
        if sha(ROOT/name) != registered["dependency_pins"][name]:
            raise ValueError("changed maintained viewer dependency: "+name)
    budget, complete = read(STUDY/"budget.json"), read(STUDY/"measurement_complete.json")
    if (budget["protocol_sha256"] != sha(STUDY/"protocol.json")
            or complete["protocol_sha256"] != sha(STUDY/"protocol.json")
            or complete["row_index_sha256"] != sha(STUDY/"row_index.json")
            or complete["endpoints_sha256"] != sha(STUDY/"endpoints.json")):
        raise ValueError("terminal scientific artifacts must bind the same completed study")
    clear = budget["terminal_cleanup"]
    if (budget["status"] != "complete" or complete["status"] != "complete"
            or complete["research_lives"] != 14336 or complete["rows"] != 28
            or budget.get("running") or budget.get("queued") or budget.get("cleanup_error")
            or not clear["all_owned_groups_exited"] or not clear["all_worker_identities_exited"]
            or clear["remaining_descendants"]):
        raise ValueError("scientific run must be complete and cleared before viewer validation")
    if worker:
        monitor = int(os.environ.get("CELLDEV_MONITOR_PID", "0"))
        if (monitor <= 1 or os.getppid() != monitor or os.getpgrp() != os.getpid()
                or os.environ.get("CELL_DEV_WATCHABLE_RECORD_SHA256") != sha(path)):
            raise ValueError("use the separate owned monitor worker")
        attempt_path = HERE/"execution/attempt.json"
        if (os.environ.get("CELLDEV_ATTEMPT_PATH") != str(attempt_path)
                or os.environ.get("CELLDEV_ATTEMPT_SHA256") != sha(attempt_path)):
            raise ValueError("owned execution attempt binding differs")
        attempt = read(attempt_path)
        fields = Path(f"/proc/{monitor}/stat").read_text().rsplit(")", 1)[1].split()
        actual = dict(pid=monitor, ppid=int(fields[1]), pgid=int(fields[2]), start_ticks=int(fields[19]))
        namespace = os.readlink("/proc/self/ns/pid")
        if (attempt["monitor"] != actual or attempt["pid_namespace"] != namespace
                or os.environ.get("CELLDEV_PID_NAMESPACE") != namespace
                or int(os.environ.get("CELLDEV_MONITOR_START_TICKS", "0")) != actual["start_ticks"]
                or attempt["protocol_sha256"] != sha(path) or attempt["release_sha256"] != sha(path)
                or os.environ.get("CELLDEV_PROTOCOL_SHA256") != sha(path)):
            raise ValueError("monitor identity, namespace or execution record differs")
        if any(os.environ.get(key) != "1" for key in
               ("OMP_NUM_THREADS", "OMP_THREAD_LIMIT", "MKL_NUM_THREADS", "OPENBLAS_NUM_THREADS",
                "NUMEXPR_NUM_THREADS")):
            raise ValueError("viewer validation requires one thread")
    return registered


def export(record_path):
    registered = checked_record(record_path, worker=True)
    ARTIFACT.mkdir(exist_ok=False)
    protocol, endpoints = read(STUDY/"protocol.json"), read(STUDY/"endpoints.json")
    if (protocol["roles"] != ["AM_reference", *ROLES] or protocol["seeds"][:4] != list(SEEDS)
            or endpoints["roles"] != protocol["roles"]
            or endpoints["protocol_sha256"] != sha(STUDY/"protocol.json")):
        raise ValueError("fixed roles/seeds/endpoints differ")
    for name, digest in protocol["production_pins"].items():
        if sha(ROOT/name) != digest:
            raise ValueError("production source changed: "+name)
    os.environ["CELL_DEV_CACHE"] = str(STUDY/"build-cache")
    os.environ["ATEN_CPU_CAPABILITY"] = "avx2"
    sys.dont_write_bytecode = True
    sys.path.insert(0, str(ROOT))
    import numpy as np

    from src.genome import Layout
    from src.life import build, spec

    world_record = protocol["worlds"]["match85"]
    world = spec.World(**world_record["world"])
    if (world_record["abi"] != 5 or world.T != 85 or world.t0 != 0 or world.t_open != 0 or world.task_mode != 1
            or spec.V5.pack_world(world).tolist() != world_record["world_vector"]):
        raise ValueError("registered matching T85 world required")
    index = read(STUDY/"row_index.json")
    atlas = read(ROOT/"results/atlas/play/bodies.json")
    bodies, recorded, retained, genome_pins = [], [], {}, {}
    for body_index, role in enumerate(ROLES):
        i = body_index+1
        record = endpoints["genomes"][i]
        path = STUDY/record["path"]
        if record["role"] != role or sha(path) != record["file_sha256"]:
            raise ValueError("fixed endpoint file differs")
        _, genome = Layout.load(path)
        values = genome.numpy()
        if (values.shape != (875,) or values.dtype != np.float32
                or hashlib.sha256(values.tobytes()).hexdigest() != record["raw_sha256"]):
            raise ValueError("fixed genome bytes differ")
        genome_pins[record["path"]] = sha(path)
        packed = spec.V5.pack_genomes(values[None], "hexprism")[0]
        bodies.append(dict(name=role, role=role, abi=5, mode="grn", genotype_sha256=record["raw_sha256"],
            world={key: float(getattr(world, key)) for key in spec.V5.WORLD_KEYS}, genome=packed.tolist()))
        raw_name = f"raw/match85/row_{i:02d}.npz"
        entry = index[raw_name]
        if (entry["status"] != "validated" or sha(STUDY/raw_name) != entry["sha256"]
                or sha(STUDY/entry["scored_path"]) != entry["scored_sha256"]):
            raise ValueError("retained confirmation rows differ")
        with np.load(STUDY/raw_name, allow_pickle=False) as raw, \
                np.load(STUDY/entry["scored_path"], allow_pickle=False) as scored:
            if (raw["seeds"].tolist() != protocol["seeds"] or raw["ledger"].shape != (512, 70)
                    or str(raw["role"]) != role or str(raw["genome_raw_sha256"]) != record["raw_sha256"]
                    or str(scored["raw_sha256"]) != entry["sha256"]):
                raise ValueError("retained row identity differs")
            for j, seed in enumerate(SEEDS):
                retained[role, seed] = raw["ledger"][j].copy()
                recorded.append(dict(role=role, seed=seed, native_F=float(raw["ledger"][j, spec.V5.L["F"]]),
                    production_F=float(scored["production_F"][j]),
                    extinct_charge=float(scored["extinct_charge"][j]),
                    status=int(raw["ledger"][j, spec.V5.L["status"]])))
    doc = dict(abi=5, roles=list(ROLES), seeds=list(SEEDS), bodies=bodies, recorded=recorded,
               drag=atlas["drag"], lattice=atlas["lattice"], genome_slices=atlas["genome_slices"],
               study_protocol_sha256=sha(STUDY/"protocol.json"))
    save(ARTIFACT/"bodies.json", doc)
    calls, cases = [], []
    started, cpu_started = time.monotonic(), time.process_time()
    for body_index, body in enumerate(bodies):
        for seed in SEEDS:
            name = f"{body['role']}__{seed}"
            call = dict(index=len(calls), name=name, role=body["role"], seed=seed, status="started")
            calls.append(call)
            save(ARTIFACT/"C_calls.json", calls)
            result = build.run(world, [seed], genomes=np.asarray(body["genome"], dtype=np.float64)[None],
                               abi=spec.V5, threads=1, raster_cap=65536, fate_cap=8192)
            path = ARTIFACT/(name+".npz")
            with path.open("xb") as stream:
                np.savez_compressed(stream, ledger=result.ledger, hashes=result.hashes, raster_t=result.raster_t,
                    raster_uid=result.raster_uid, raster_n=result.raster_n,
                    fate_i=result.fate_i, fate_f=result.fate_f, fate_n=result.fate_n)
            call.update(status="returned", raw_sha256=sha(path))
            save(ARTIFACT/"C_calls.json", calls)
            if (result.ledger[0].tobytes() != retained[body["role"], seed].tobytes()
                    or result.raster_n[0] > 65536 or result.fate_n[0] > 8192):
                raise ValueError("C-full differs from retained confirmation or log capacity: "+name)
            times, uids = result.spikes(0)
            cases.append(dict(name=name, role=body["role"], body_index=body_index, seed=seed,
                ledger=[repr(float(value)) for value in result.ledger[0]],
                hashes=[f"{int(value):016x}" for value in result.hashes[0]], raster_total=int(result.raster_n[0]),
                raster_t=[repr(float(value)) for value in times], raster_uid=[f"{int(value):016x}" for value in uids],
                native_file=path.name, native_file_sha256=sha(path)))
            call["status"] = "validated"
            save(ARTIFACT/"C_calls.json", calls)
    save(ARTIFACT/"truth.json", dict(status="complete", abi=5, raster_cap=65536, fate_cap=8192,
                                     ledger_columns=list(spec.V5.LEDGER), hash_names=list(spec.V5.HASHES), cases=cases))
    checked_record(record_path, worker=True)
    for name, digest in genome_pins.items():
        if sha(STUDY/name) != digest:
            raise ValueError("endpoint changed during illustration export")
    save(ARTIFACT/"export_receipt.json", dict(status="complete", C_full_lives=12, JS_replay_lives=0,
         new_research_cases=0, roles=list(ROLES), seeds=list(SEEDS), genome_pins=genome_pins,
         record_sha256=sha(record_path), source_pins=registered["source_pins"],
         bodies_sha256=sha(ARTIFACT/"bodies.json"), truth_sha256=sha(ARTIFACT/"truth.json"),
         C_calls_sha256=sha(ARTIFACT/"C_calls.json"), cpu_seconds=time.process_time()-cpu_started,
         wall_seconds=time.monotonic()-started, budget_accounting="external cumulative monitor is authoritative"))


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--export-child", action="store_true")
    parser.add_argument("--record", type=Path)
    args = parser.parse_args()
    if args.export_child:
        if args.record is None:
            parser.error("--record is required")
        export(args.record.resolve())
    else:
        print(json.dumps(dict(status="source_only", C_full_lives=0, JS_replay_lives=0)))
