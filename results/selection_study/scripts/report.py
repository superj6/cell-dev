"""Aggregate sim.py results by population stage and rank the selection schemes.

    python report.py sim_results.json [more.json ...]

Stages: founders (generation 0), early (generation 10), plateau (generations 30-150 whose parents are lone cells),
escape (hex seed 0, generations 11-16: the first bodies, below and then above the lone cell, among lone parents),
bodies (generations 30-200 whose parents are mostly multi-cell bodies near the lone-pump plateau), big (the seeded
R25-v1 + timer populations and their mutants). Within a stage, values are means over populations; SEs combine the
per-population half-split SEs (conditional on these populations). Duplicate populations (identical genomes and
identical F, e.g. square8 seed 1 = hex seed 1 while both stay lone cells) are dropped.
"""
from __future__ import annotations

import json
import sys

import numpy as np

STAGES = ("founders", "early", "plateau", "escape", "bodies", "big")
SHOW = ("meanF", "regret", "p_best", "beat", "beat_body", "rank0F", "rank0_beat")


def stage_of(desc: dict) -> str:
    pop = desc["pop"]
    if pop.startswith("seeded"):
        return "big"
    if pop.startswith("esc_"):
        return "escape"
    gen = int(desc["meta"]["gen"])
    if gen == 0:
        return "founders"
    if gen <= 10:
        return "early"
    return "bodies" if desc["parents_body"] >= 0.5 else "plateau"


def load(paths) -> dict:
    res = {}
    for p in paths:
        res.update(json.loads(open(p).read()))
    return res


def aggregate(res: dict, pops: list[str], scheme: str, metric: str, diff: bool) -> tuple[float, float]:
    pt, se = ("dpoint", "dse") if diff else ("point", "se")
    v = [res[p][pt][scheme][metric] for p in pops]
    s = [res[p][se][scheme][metric] for p in pops]
    return float(np.mean(v)), float(np.sqrt(np.sum(np.square(s))) / len(s))


def regret_removed(res: dict, pops: list[str], scheme: str) -> tuple[float, float]:
    """Mean over populations of the share of A's regret a scheme removes (paired, per population), with SE."""
    v, s = [], []
    for p in pops:
        ra = res[p]["point"]["A"]["regret"]
        v.append(-res[p]["dpoint"][scheme]["regret"] / ra)
        s.append(res[p]["dse"][scheme]["regret"] / ra)
    return float(np.mean(v)), float(np.sqrt(np.sum(np.square(s))) / len(s))


def main() -> None:
    res = load(sys.argv[1:])
    by_stage = {s: [] for s in STAGES}
    for p, r in sorted(res.items()):
        if r["desc"].get("duplicate_of"):
            continue
        by_stage[stage_of(r["desc"])].append(p)
    schemes = list(next(iter(res.values()))["point"])
    cost = next(iter(res.values()))["cost"]
    print("populations:", {s: len(v) for s, v in by_stage.items()})
    for s, pops in by_stage.items():
        for p in pops:
            d = res[p]["desc"]
            print(f"  {s:8s} {p:28s} top32 {d['true_top32']:+.4f} best {d['true_best']:+.4f} "
                  f"body&beat {d['n_body_beat']:3d} regretA {res[p]['point']['A']['regret']:.5f} "
                  f"sd_life(top32) {d['sd_life_top32']:.4f}")
    informative = by_stage["bodies"] + by_stage["big"]
    rows = []
    for sc in schemes:
        row = {"scheme": sc, "cost": cost[sc]}
        for s, pops in by_stage.items():
            if pops:
                row[s] = regret_removed(res, pops, sc) if sc != "A" else (0.0, 0.0)
        row["inf"] = regret_removed(res, informative, sc) if sc != "A" else (0.0, 0.0)
        row["cost_ev"] = float(np.mean([res[p]["point"][sc]["cost_ev"] for p in informative]))
        rows.append(row)
    rows.sort(key=lambda r: -r["inf"][0])
    print("\nshare of A's regret removed (mean over populations, SE); inf = bodies + big")
    for r in rows:
        cells = " ".join(f"{s} {r[s][0]:+.3f}±{r[s][1]:.3f}" for s in STAGES if s in r)
        print(f"{r['scheme']:16s} cost {r['cost']:.3f} ev {r['cost_ev']:.3f} | inf {r['inf'][0]:+.3f}±{r['inf'][1]:.3f}"
              f" | {cells}")


if __name__ == "__main__":
    main()
