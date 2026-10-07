"""Uncapped hand-built reference: R25-v1 as a GRN genome without the oracle cap, with and without its lineage timer.

    python scripts/life_reference.py [--threads 4] [--screen-lives 64] [--lives 144]

R25-v1 has no stop rule, so without the cap it grows until the N_max guard. The optional lineage-timer gene
(``handbuilt.r25_genome(timer=w)``) lowers p_div as it rises, a local size control. The timer weight is screened on
screen seeds (``analysis.SCREEN_SEED0``), and the pick is measured on fresh lives (``analysis.FRESH_SEED0``), as in
the gates. Writes ``<out>/reference.json``.
"""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

import numpy as np

repo_root = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(repo_root))

from src.life import analysis  # noqa: E402
from src.life import handbuilt as hb  # noqa: E402

TIMERS = (0.625, 0.75, 0.875, 1.0, 1.125, 1.25, 1.5)


def measure(genome, seeds, threads: int) -> dict:
    res = hb.GrnOrganism("ref", genome).run(seeds, threads=threads)
    p = analysis.point(res)
    p.update(n_end_q=[float(x) for x in np.quantile(res["n_end"], [0.1, 0.5, 0.9])], t_end=float(res["t_end"].mean()),
             guard=float(np.mean(res.status("guard_cells") | res.status("guard_events"))))
    return p


def reference(threads: int = 4, screen_lives: int = 64, lives: int = 144, timers=TIMERS) -> dict:
    screen = analysis.fresh_seeds(screen_lives, analysis.SCREEN_SEED0)
    fresh = analysis.fresh_seeds(lives)
    rows = {str(w): measure(hb.r25_genome(timer=w), screen, threads) for w in timers}
    best = max(timers, key=lambda w: rows[str(w)]["mean"])
    out = dict(screen=rows, best_timer=best, fresh={"uncapped": measure(hb.r25_genome(), fresh, threads),
                                                     f"timer {best:g}": measure(hb.r25_genome(timer=best), fresh, threads)})
    return out


if __name__ == "__main__":
    p = argparse.ArgumentParser()
    p.add_argument("--threads", type=int, default=4)
    p.add_argument("--screen-lives", type=int, default=64)
    p.add_argument("--lives", type=int, default=144)
    p.add_argument("--out", default="outputs/life_reference")
    args = p.parse_args()
    res = reference(args.threads, args.screen_lives, args.lives)
    for w, r in res["screen"].items():
        print(f"screen timer {w}: F {r['mean']:+.3f} +- {r['se']:.3f}, n_end {r['n_end']:.1f}")
    for name, r in res["fresh"].items():
        print(f"fresh {name}: F {r['mean']:+.3f} +- {r['se']:.3f} (median {r['median']:+.3f}, F > 0 in "
              f"{100 * r['frac_pos']:.0f}%), n_end q10/50/90 {r['n_end_q']}, guard {r['guard']:.2f}")
    out = repo_root / args.out
    out.mkdir(parents=True, exist_ok=True)
    (out / "reference.json").write_text(json.dumps(res, indent=1))
