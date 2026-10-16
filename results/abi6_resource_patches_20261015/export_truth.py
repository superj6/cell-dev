"""Eight fixed ABI6 engineering cases; default is source-only, --run requires an externally bounded pass.

Exactly eight C-full, eight C-fast and eight Python lives. The JS truth checker adds sixteen lives.
Reused 42M engineering seeds are not fresh scientific cases. No outcome-based case selection or retry.
"""
from __future__ import annotations

import argparse
import copy
import hashlib
import json
import os
import sys
import time
from pathlib import Path

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[1]
RASTER_CAP, FATE_CAP = 65536, 8192
QUICK = dict(patch_refill_fast=8.0, patch_refill_slow=16.0)
CASES = (
    dict(name="reflex_count1", body=6, seed=42000000, world=dict(T=96, patch_count=1, **QUICK)),
    dict(name="reflex_count2", body=6, seed=42000001, world=dict(T=96, patch_count=2, **QUICK)),
    dict(name="grn_count3_preset", body=0, seed=42000002, world=dict(T=128)),
    dict(name="grn_count4_shifted_window", body=0, seed=42000003,
         world=dict(T=128, t0=32, t_open=32, patch_count=4, patch_capacity=3, **QUICK)),
    dict(name="reflex_negative_t0_window", body=6, seed=42000004,
         world=dict(T=96, t0=-32, t_open=12, **QUICK)),
    dict(name="reflex_equal_period_no_motor", body=6, seed=42000005, add_flags=("motor_off",),
         world=dict(T=96, patch_refill_fast=8, patch_refill_slow=8)),
    dict(name="reflex_extinct_world_continues", body=6, seed=42000006,
         world=dict(T=96, kill_t=1, kill_frac=1, **QUICK)),
    dict(name="grn_guard_before_window", body=0, seed=42000007,
         world=dict(T=96, t_open=16, n_max=1, **QUICK)),
)
PATCH_KEYS = ("patch_count", "patch_capacity", "patch_refill_fast", "patch_refill_slow", "patch_landmark",
              "task_mode", "sample_min", "sample_max", "blank_min", "blank_max", "choice_T", "reset_T",
              "visibility_mode", "visibility_on", "visibility_off", "visibility_low", "v_t", "tau_turn",
              "t_resp", "b2_amp", "b2_value", "b2_mode", "b2_p", "sigma", "rho_c", "R_min", "R_max",
              "R_cap", "c_miss")


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def save(path, value):
    temporary = path.with_suffix(path.suffix+".tmp")
    with temporary.open("x") as stream:
        json.dump(value, stream, indent=2, allow_nan=False)
        stream.write("\n")
    temporary.replace(path)


def plan():
    return dict(status="source_only", purpose="engineering parity, no behavioral gate", cases=list(CASES),
                calls=dict(C_full=8, C_fast=8, Python=8, JS_truth_full=8, JS_truth_stepped=8),
                exporter_lives=24, truth_lives_including_JS=40, threads=1,
                raster_cap=RASTER_CAP, fate_cap=FATE_CAP,
                resource_enforcement="parent-announced owned process monitor; no standalone release",
                extra_JS_suite="test_resource_patches.js default fixtures report construction/run counts separately")


def run(output):
    if output.exists():
        raise ValueError("fresh output directory required; preserve any earlier attempt")
    output.mkdir(parents=True)
    save(output/"manifest.json", plan() | {"status": "running"})
    for key in ("OPENBLAS_NUM_THREADS", "OMP_NUM_THREADS", "OMP_THREAD_LIMIT", "MKL_NUM_THREADS"):
        os.environ[key] = "1"
    os.environ.setdefault("CELL_DEV_CACHE", str(HERE/"build-cache"))
    os.environ["ATEN_CPU_CAPABILITY"] = "avx2"
    sys.dont_write_bytecode = True
    sys.path.insert(0, str(ROOT))
    from dataclasses import replace

    import numpy as np

    from src.life import build, reference, spec

    paths = [ROOT/name for name in ("src/life/spec.py", "src/life/build.py", "src/life/reference.py",
        "src/life/kernel.c", "results/atlas/play/lifesim.js", "results/atlas/play/test_resource_patches.js",
        "results/atlas/play/bodies.json")]+[Path(__file__), HERE/"DRAFT_CONTRACT.md"]
    pins = {str(path): sha(path) for path in paths}
    save(output/"source_pins.json", pins)
    abi = spec.V6
    preset = spec.world("catch_resource_patches_l4")
    document = json.loads((ROOT/"results/atlas/play/bodies.json").read_text())
    patch = {key: getattr(preset, key) for key in PATCH_KEYS}
    fixture = dict(status="incomplete", abi=6, raster_cap=RASTER_CAP, fate_cap=FATE_CAP,
                   source_sha256=pins, cases=[])
    calls = []
    start, cpu_start = time.monotonic(), time.process_time()

    def call(backend, case, function, *args, **kwargs):
        item = dict(index=len(calls), backend=backend, case=case["name"], seed=case["seed"], status="started")
        calls.append(item)
        save(output/"calls.json", calls)
        result = function(*args, **kwargs)
        raw = output/(case["name"]+"__"+backend+".npz")
        arrays = {key: getattr(result, key) for key in ("ledger", "hashes", "raster_t", "raster_uid", "raster_n",
                                                     "fate_i", "fate_f", "fate_n")}
        arrays = {key: np.asarray(value) for key, value in arrays.items() if value is not None}
        with raw.open("xb") as stream:
            np.savez_compressed(stream, **arrays)
        item.update(status="returned", raw=raw.name, raw_sha256=sha(raw))
        save(output/"calls.json", calls)
        return result

    def equal(a, b, message):
        a, b = np.asarray(a), np.asarray(b)
        if a.shape != b.shape or a.dtype != b.dtype or a.tobytes() != b.tobytes():
            raise AssertionError(message)

    try:
        for case in CASES:
            body = copy.deepcopy(document["bodies"][case["body"]])
            values = body["world"] | patch | dict(t0=0.0, t_open=0.0) | case["world"]
            values = {key: int(value) if isinstance(getattr(preset, key), int) else value
                      for key, value in values.items()}
            for flag in case.get("add_flags", ()):
                values["flags"] |= abi.FLAGS[flag]
            world = replace(preset, **values)
            vector = abi.pack_world(world)
            body.update(abi=6, world={key: float(getattr(world, key)) for key in abi.WORLD_KEYS},
                        lattice=document["lattice"], genome_slices=document["genome_slices"], drag=document["drag"])
            genome = np.asarray(body["genome"], dtype=np.float64) if body["mode"] == "grn" else None
            program = np.asarray(body["program"], dtype=np.float64) if body["mode"] == "program" else None
            cells = body.get("cells")
            tables = dict(genomes=None if genome is None else genome[None], programs=program, init=cells,
                          abi=abi, threads=1)
            full = call("C_full", case, build.run, world, [case["seed"]], **tables,
                        raster_cap=RASTER_CAP, fate_cap=FATE_CAP)
            fast = call("C_fast", case, build.run, world, [case["seed"]], **tables, fast=True)
            lat, unit = abi.lattice_tables(world.lattice)
            ref = call("Python", case, reference.run_life, vector, lat, unit, genome_table=genome,
                program=program, init=cells, seeds=(case["seed"], 0, 0, 0), raster_cap=RASTER_CAP,
                fate_cap=FATE_CAP, abi=abi)
            assert int(full.raster_n[0]) <= RASTER_CAP and int(full.fate_n[0]) <= FATE_CAP
            equal(full.ledger, fast.ledger, "C full/fast ledger bits")
            assert np.all(fast.hashes == spec.HASH_INIT), "fast constants are not replay truth"
            equal(full.ledger[0], ref.ledger, "C/Python ledger bits")
            equal(full.hashes[0], ref.hashes, "C/Python all five hashes")
            rt, ru = full.spikes(0)
            equal(rt, ref.raster_t, "raster time bits")
            equal(ru, ref.raster_uid, "raster UIDs")
            assert int(full.raster_n[0]) == ref.raster_n
            fi, ff = full.fates(0)
            assert int(full.fate_n[0]) == ref.fate_n
            equal(fi, ref.fate_i, "fate integers")
            equal(ff, ref.fate_f, "fate float bits")
            for i in range(4):
                def get(stem, row=ref.ledger, slot=i):
                    return row[abi.L[f"patch_{stem}_{slot}"]]
                assert get("source") == get("supply")+get("spill")
                assert get("stock_open")+get("supply") == get("harvest")+get("stock_end")
                assert get("harvest") == get("initial_harvest")+get("refill_harvest")
            assert not int(ref.ledger[abi.L["status"]]) & 64
            fixture["cases"].append(dict(name=case["name"], body=body, source_body=case["body"], seed=case["seed"],
                ledger=[repr(float(v)) for v in ref.ledger], hashes=[f"{int(v):016x}" for v in ref.hashes],
                raster_total=int(ref.raster_n), raster_t=[repr(float(v)) for v in rt],
                raster_uid=[f"{int(v):016x}" for v in ru],
                fate_i=fi.tolist(), fate_f=[[repr(float(v)) for v in row] for row in ff]))
            for item in calls[-3:]:
                item["status"] = "validated"
            save(output/"calls.json", calls)
            save(output/"progress.json", dict(status="running", complete_cases=len(fixture["cases"]), calls=len(calls)))
            print("C full/fast/Python agree: "+case["name"], flush=True)
        assert pins == {str(path): sha(path) for path in paths}, "source changed during export"
        fixture.update(status="complete", cpu_seconds=time.process_time()-cpu_start,
                       wall_seconds=time.monotonic()-start, C_full_lives=8, C_fast_lives=8, Python_lives=8)
        save(output/"truth.json", fixture)
        save(output/"progress.json", dict(status="complete", complete_cases=8, calls=24))
    except BaseException as error:
        save(output/"progress.json", dict(status="incomplete", complete_cases=len(fixture["cases"]),
                                         calls=len(calls), error=repr(error)))
        save(output/"partial_truth.json", fixture)
        raise


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--run", action="store_true")
    parser.add_argument("--out", type=Path)
    args = parser.parse_args()
    if not args.run:
        print(json.dumps(plan(), indent=2))
    elif args.out is None:
        parser.error("--out is required")
    else:
        run(args.out.resolve())
