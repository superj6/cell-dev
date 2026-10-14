"""Export bounded ABI-4 browser truth using unchanged, committed atlas bodies.

An explicit output directory is required. No historical browser fixture is rewritten.
All C and Python simulation calls use one thread; compare every ledger/hash/raster/fate
entry before writing a complete fixture. These are engine fixtures, not behavioral gates.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import time
from dataclasses import replace
from pathlib import Path

import numpy as np
from export_bodies import world_dict

from src.life import build, reference, spec

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[2]
RASTER_CAP = 256
FATE_CAP = 4096


def cases():
    for body in (0, 7):
        for abi in (3, 4):
            yield dict(name=f"body{body}_neutral_abi{abi}", body=body, abi=abi, seed=55_040_000,
                       world={})
        for seed in (55_040_000, 55_040_001):
            for mode, changes in (
                ("flash", dict(visibility_mode=1, visibility_on=5, visibility_low=0.25)),
                ("renewal", dict(visibility_mode=2, visibility_on=20, visibility_off=20, visibility_low=0)),
            ):
                yield dict(name=f"body{body}_{mode}_{seed}", body=body, abi=4, seed=seed, world=changes)
    for label, changes in (
        ("shifted_flash_open", dict(t0=32, t_open=5, visibility_mode=1, visibility_on=5, visibility_low=0.25)),
        ("shifted_renewal_open", dict(t0=-32, t_open=20, visibility_mode=2,
                                     visibility_on=20, visibility_off=20, visibility_low=0)),
        ("flash_low_one", dict(visibility_mode=1, visibility_on=5, visibility_low=1)),
        ("flash_at_end", dict(visibility_mode=1, visibility_on=96, visibility_low=0, t_resp=0)),
    ):
        yield dict(name=label, body=7, abi=4, seed=55_040_002, world=changes)


def equal_bits(a, b, label):
    left, right = np.asarray(a), np.asarray(b)
    if left.shape != right.shape or left.dtype != right.dtype or left.tobytes() != right.tobytes():
        raise ValueError(label + " differs between C and Python")


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def main(output):
    output = Path(output).resolve()
    if (output / "truth.json").exists():
        raise ValueError("truth already exists; choose a fresh output directory")
    output.mkdir(parents=True, exist_ok=True)
    doc = json.loads((HERE / "bodies.json").read_text())
    fixture = dict(status="incomplete", body_source_sha256=sha(HERE / "bodies.json"),
                   source_sha256={str(path.relative_to(ROOT)): sha(path) for path in (
                       ROOT / "src/life/spec.py", ROOT / "src/life/kernel.c", ROOT / "src/life/build.py",
                       ROOT / "src/life/reference.py", HERE / "lifesim.js", HERE / "export_visibility.py",
                       HERE / "export_bodies.py")}, raster_cap=RASTER_CAP, fate_cap=FATE_CAP, threads=1, cases=[])
    started = time.process_time()
    for case in cases():
        contract = spec.V3 if case["abi"] == 3 else spec.V4
        body = dict(doc["bodies"][case["body"]])
        defaults = spec.world("catch_speck_l4")
        values = {key: int(value) if isinstance(getattr(defaults, key), int) else value
                  for key, value in (body["world"] | {"T": 96} | case["world"]).items()}
        world = replace(defaults, **values)
        body.update(abi=case["abi"], world=world_dict(world, contract),
                    world_vec=contract.pack_world(world).tolist())
        genome = np.asarray(body["genome"], dtype=np.float64) if body["mode"] == "grn" else None
        program = np.asarray(body["program"], dtype=np.float64) if body["mode"] == "program" else None
        cells = body.get("cells")
        lat, unit = contract.lattice_tables(world.lattice)
        kernel = build.run(world, [case["seed"]], genomes=None if genome is None else genome[None],
                           programs=program, init=cells, abi=contract, threads=1,
                           raster_cap=RASTER_CAP, fate_cap=FATE_CAP)
        ref = reference.run_life(contract.pack_world(world), lat, unit, genome_table=genome,
                                 program=program, init=cells, seeds=(case["seed"], 0, 0, 0),
                                 raster_cap=RASTER_CAP, fate_cap=FATE_CAP, abi=contract)
        equal_bits(kernel.ledger[0], ref.ledger, case["name"] + " ledger")
        equal_bits(kernel.hashes[0], ref.hashes, case["name"] + " hashes")
        rt, ru = kernel.spikes(0)
        equal_bits(rt, ref.raster_t, case["name"] + " raster times")
        equal_bits(ru, ref.raster_uid, case["name"] + " raster uids")
        equal_bits(kernel.raster_n[:1], np.asarray([ref.raster_n], dtype=kernel.raster_n.dtype), "raster count")
        fi, ff = kernel.fates(0)
        equal_bits(fi, ref.fate_i, case["name"] + " fate integers")
        equal_bits(ff, ref.fate_f, case["name"] + " fate floats")
        if len(fi) != kernel.fate_n[0]:
            raise ValueError("increase fate capacity")
        fixture["cases"].append(dict(name=case["name"], source_body=case["body"], body=body, seed=case["seed"],
            ledger=[repr(float(value)) for value in ref.ledger], hashes=[f"{int(value):016x}" for value in ref.hashes],
            raster_t=[repr(float(value)) for value in rt], raster_uid=[f"{int(value):016x}" for value in ru],
            raster_total=int(ref.raster_n), fate_i=fi.tolist(), fate_f=[[repr(float(v)) for v in row] for row in ff]))
        (output / "progress.json").write_text(json.dumps(dict(status="running", complete_cases=len(fixture["cases"]))) + "\n")
        print(f"C/Python agree: {case['name']}", flush=True)
    fixture.update(status="complete", cpu_seconds=time.process_time() - started,
                   C_lives=len(fixture["cases"]), Python_lives=len(fixture["cases"]))
    (output / "truth.json").write_text(json.dumps(fixture, indent=2, allow_nan=False) + "\n")
    (output / "progress.json").write_text(json.dumps(dict(status="complete", complete_cases=len(fixture["cases"]))) + "\n")
    print(f"Wrote {len(fixture['cases'])} complete cases to {output / 'truth.json'}", flush=True)


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--out", type=Path, required=True)
    main(parser.parse_args().out)
