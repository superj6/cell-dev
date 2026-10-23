"""Pilot v2 behaviour check at generation 50: top genomes over generations, and standout behaviour-grid elites.

Fresh life seeds (8_300_000 + i) never used by the pilot. Two threads, run under nice.
"""
import json
import sys
from pathlib import Path

import numpy as np
import torch

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))
from src.genome import LifeLayout, make_dims  # noqa: E402
from src.life import build, ecology, spec  # noqa: E402

RUNS = ROOT / "outputs/open_worlds_pilot_v2/runs"
OUT = Path(__file__).resolve().parent
FAMS = ecology.FAMILIES
L = 24
WORLDS = {f: [ecology.realize(f, 8_300_000 + s, T=1024) for s in range(L)] for f in FAMS}
SENSES = {1: "odA", 2: "odB", 3: "odC", 4: "odD", 5: "flow", 6: "touch", 7: "vib", 8: "sun", 9: "spare"}


def ratio(r, a, b):
    return np.where(r[b] > 0, r[a] / np.where(r[b] > 0, r[b], 1), 0.0)


def metrics(r):
    """Per-life behaviour columns, all worlds (eco ledger)."""
    m = dict(F=r["F"], food=r["eco_food_eaten"], toxin=r["eco_toxin_eaten"], clicks=r["clicks"], misses=r["misses"],
             upflow=r["eco_upflow_path"], hits=r["eco_hits"], killed=r["eco_killed"],
             shelter=ratio(r, "eco_shelter_samples", "samples"), still_threat=ratio(r, "eco_still_samples",
                                                                                       "eco_threat_samples"),
             picked=r["eco_picked"], delivered=r["eco_delivered"], home=ratio(r, "eco_home_samples", "samples"),
             prey=r["eco_prey_caught"], alarms=r["eco_alarms"], planted=r["eco_planted"],
             harvested=r["eco_harvested"], spoiled=r["eco_spoiled"], pest=r["eco_pest_eaten"])
    for k, name in SENSES.items():
        m[f"on_{name}"] = (r[f"mod_cand_{k}"] > 0).astype(float)
    return m


def offsets(lay):
    off, o = {}, 0
    for f in lay.fields:
        n = int(np.prod(f.shape))
        off[f.name] = (o, f.shape)
        o += n
    return off


def lesion(g, lay, slots=range(1, 10)):
    g = g.clone()
    off = offsets(lay)
    oA, shA = off["A"]
    oa, _ = off["a0"]
    for m in slots:
        row = 22 + m
        g[:, oA + row * shA[1]: oA + (row + 1) * shA[1]] = 0.0
        g[:, oa + row] = 0.0
    return g


def run(lay, g, fam):
    gt = lay.pack(g, "hexprism")
    ws = WORLDS[fam]
    r = build.run([w for _ in range(len(g)) for w in ws], list(range(L)) * len(g), genomes=gt,
                  genome_of=np.repeat(np.arange(len(g)), L), abi=spec.V8, threads=2, fast=True)
    return {k: v.reshape(len(g), L) for k, v in metrics(r).items()}


def load(run_name, gen):
    d = json.load(open(RUNS / run_name / "populations" / f"g{gen:06d}.json"))
    return d, LifeLayout(make_dims(d["dims"]))


def summary(m):
    return {k: float(v.mean()) for k, v in m.items()}


def top_over_generations(run_name, gens):
    rows = {}
    for gen in gens:
        d, lay = load(run_name, gen)
        fit = np.array([x if x is not None else 0.0 for x in d["fitness"]]) if d.get("fitness") else None
        idx = np.argsort(-fit)[:8] if fit is not None else np.arange(8)
        g = torch.stack([lay.from_dict(d["genomes"][i]) for i in idx])
        rows[gen] = {f: summary(run(lay, g, f)) for f in FAMS}
    return rows


PICK = {  # (world, which grid cells count as standout, how to rank them)
    "home": lambda k0, k1: k0 >= 2,          # delivers at least half of what it picks
    "predator": lambda k0, k1: k1 >= 1 or k0 >= 2,  # freezes under threat, or shelters
    "prey": lambda k0, k1: k0 >= 2,          # 3+ prey per life
    "farm": lambda k0, k1: k1 >= 2 and k0 >= 1,    # 3+ plantings, half or more harvested
    "plume": lambda k0, k1: k0 >= 2,         # upstream progress of 15+
}


def standout_elites(run_name, gen):
    d, lay = load(run_name, gen)
    out = []
    for fam, ok in PICK.items():
        gr = d["elites"][fam]
        cand = [(v, c, i) for i, (c, v) in enumerate(zip(gr["cells"], gr["values"])) if ok(c // 4, c % 4)]
        for v, c, i in sorted(cand, reverse=True)[:2]:
            g = lay.from_dict(gr["genomes"][i])[None]
            full = run(lay, g, fam)
            blind = run(lay, lesion(g, lay), fam)
            dF = (full["F"] - blind["F"])[0]
            out.append(dict(run=run_name, world=fam, cell=[c // 4, c % 4], grid_value=v, id=gr["ids"][i],
                            since=gr["since"][i], fresh=summary(full), senses_off_F=float(blind["F"].mean()),
                            sense_value=float(dF.mean()), sense_value_se=float(dF.std(ddof=1) / np.sqrt(L))))
            print(json.dumps(out[-1]["fresh"] | {k: out[-1][k] for k in ("run", "world", "cell", "grid_value",
                                                                          "sense_value", "sense_value_se")}),
                  flush=True)
    return out


def main():
    res = {"top": {}, "elites": []}
    for run_name in ("AO_s7_LP", "AO_s7_U", "D90_Z_s5_LP"):
        res["elites"] += standout_elites(run_name, 50)
        (OUT / "g50.json").write_text(json.dumps(res, indent=1))
    for run_name, gens in (("AO_s7_LP", (0, 25, 50)), ("AO_s7_U", (0, 25, 50)), ("D90_Z_s5_LP", (0, 25, 50))):
        res["top"][run_name] = top_over_generations(run_name, gens)
        print(run_name, "top done", flush=True)
        (OUT / "g50.json").write_text(json.dumps(res, indent=1))
    print("done", flush=True)


if __name__ == "__main__":
    main()
