"""Rebuild short ABI-3 wound truth lives, checking C against Python before writing each result.

Run from the repository root: PYTHONPATH=. .venv/bin/python results/atlas/play/export_wounds.py
Uses the committed bodies.json and existing test controls; no pilot output directories are needed.
"""
from __future__ import annotations

import json
import math
from pathlib import Path

import numpy as np

from src.life import build, reference, spec
from tests.life_helpers import TURNOVER3, TURNOVER_BODY

HERE = Path(__file__).resolve().parent
V3 = spec.V3
RASTER_CAP = 64


def cases(doc):
    seed0 = 45_050_000
    for i, body in enumerate(doc["bodies"]):
        for label, wound in (("baseline", {}), ("partial", dict(kill_t=48.5, kill_frac=0.4))):
            yield dict(name=f"{body['name']} {label}", body=i, seed=seed0 + i, world=dict(T=96.0, **wound))
    for i in (0, 7):
        for label, world in (
            ("zero fraction", dict(kill_t=48.5, kill_frac=0.0)),
            ("full wound", dict(kill_t=48.5, kill_frac=1.0)),
            ("at birth", dict(kill_t=0.0, kill_frac=1.0)),
            ("at end", dict(kill_t=96.0, kill_frac=1.0)),
            ("shifted origin", dict(t0=32.0, kill_t=48.5, kill_frac=0.4)),
            ("open at wound", dict(t_open=48.5, kill_t=48.5, kill_frac=0.4)),
            ("apoptosis off", dict(kill_t=48.5, kill_frac=1.0,
                                   flags=int(doc["bodies"][i]["world"]["flags"]) | V3.FLAGS["apoptosis_off"])),
        ):
            yield dict(name=f"{doc['bodies'][i]['name']} {label}", body=i, seed=seed0 + i,
                       world=dict(T=96.0, **world))
    # Exact same-instant tick/wound ordering, using the first tick of the router's first cell.
    body = doc["bodies"][7]
    a, b, z, _ = body["cells"][0]
    sk, seed = spec.sitekey(a, b, z), seed0 + 7
    period = body["world"]["P0"] * math.exp(body["world"]["clock_sd"] * spec.normal(seed, spec.S_CLK, sk, 0))
    first_tick = spec.draw(seed, spec.S_PHASE, sk, 0) * float(period)
    yield dict(name="router tick coincides with wound", body=7, seed=seed,
               world=dict(T=16.0, kill_t=first_tick, kill_frac=1.0))
    # Existing turnover control exercises dead uids, refilled sites and morphogen packets at the wound.
    body = dict(name="existing turnover test control", mode="program", program=TURNOVER3.tolist(),
                cells=TURNOVER_BODY, world=dict(doc["bodies"][7]["world"]))
    body["world"]["L_max"] = 2
    for frac in (0.4, 1.0):
        yield dict(name=f"turnover wound {frac}", body=body, seed=seed0 + 20,
                   world=dict(T=48.0, kill_t=20.0, kill_frac=frac))


def bits_equal(a, b):
    return np.array_equal(np.asarray(a).view(np.uint64), np.asarray(b).view(np.uint64))


def main():
    doc = json.loads((HERE / "bodies.json").read_text())
    out = dict(abi=3, raster_cap=RASTER_CAP, cases=[])
    lat, unit = V3.lattice_tables("hexprism")
    for case in cases(doc):
        body = doc["bodies"][case["body"]] if isinstance(case["body"], int) else case["body"]
        base = spec.world("catch_speck_l4")
        settings = {k: int(v) if isinstance(getattr(base, k), int) else v
                    for k, v in (body["world"] | case["world"]).items()}
        world = spec.world("catch_speck_l4", **settings)
        program = np.asarray(body["program"], dtype=np.float64) if body["mode"] == "program" else None
        genome = np.asarray(body["genome"], dtype=np.float64) if body["mode"] == "grn" else None
        cells = body.get("cells")
        args = dict(programs=program, genomes=None if genome is None else genome[None], init=cells)
        kernel = build.run(world, [case["seed"]], **args, abi=V3, raster_cap=RASTER_CAP, fate_cap=4096)
        ref = reference.run_life(V3.pack_world(world), lat, unit, genome_table=genome, program=program,
                                 init=cells, seeds=(case["seed"], 0, 0, 0), raster_cap=RASTER_CAP,
                                 fate_cap=4096, abi=V3)
        assert bits_equal(kernel.ledger[0], ref.ledger), case["name"]
        assert np.array_equal(kernel.hashes[0], ref.hashes), case["name"]
        rt, ru = kernel.spikes(0)
        assert bits_equal(rt, ref.raster_t) and np.array_equal(ru, ref.raster_uid), case["name"]
        fi, ff = kernel.fates(0)
        assert np.array_equal(fi, ref.fate_i) and bits_equal(ff, ref.fate_f), case["name"]
        assert len(fi) == kernel.fate_n[0], "increase fate capacity"
        wound = world.t0 + world.kill_t
        deaths = [[repr(float(f[0])), f"{int(row[1]) & spec.MASK64:016x}", int(row[5])]
                  for row, f in zip(fi, ff) if row[0] == 2]
        coverage = dict(births_after_wound=int(np.sum((fi[:, 0] == 1) & (ff[:, 0] > wound))),
                        deaths_before_wound=int(np.sum((fi[:, 0] == 2) & (ff[:, 0] < wound))),
                        refills=int(np.sum((fi[:, 0] == 1) & (fi[:, 5] > 0))))
        case.update(ledger=[repr(float(x)) for x in ref.ledger], hashes=[f"{int(x):016x}" for x in ref.hashes],
                    raster_t=[repr(float(x)) for x in rt], raster_uid=[f"{int(x):016x}" for x in ru],
                    raster_total=int(ref.raster_n), deaths=deaths, coverage=coverage)
        out["cases"].append(case)
        (HERE / "truth_wounds.json").write_text(json.dumps(out, indent=2) + "\n")
        print(f"C = reference: {case['name']}; kills={ref['kills']:.0f}, deaths={ref['deaths']:.0f}", flush=True)


if __name__ == "__main__":
    main()
