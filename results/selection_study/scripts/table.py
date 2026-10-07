"""Compact per-stage table of chosen schemes from simres/*.json (report.py stages).

    python table.py "A" "B2 K64 L4" ... > table.txt

Per stage and scheme: dF = mean true F of the 32 chosen minus scheme A's (paired, mean over the stage's populations,
SE from half-splits), rr = share of A's regret (true top-32 mean minus chosen mean) removed, p_best = chance the
true best genome is chosen, beat = share of chosen genomes with true F > +0.0328 (lone pump), beatB = the same for
multi-cell bodies only, r0 = true F of the scheme's rank-0 genome, cost = extra lives / 768 (ev: extra kernel events
over the base 3 lives' events).
"""
from __future__ import annotations

import glob
import sys

import numpy as np

import report


def main() -> None:
    res = report.load(sorted(glob.glob("simres/*.json")))
    names = sys.argv[1:]
    by_stage = {s: [] for s in report.STAGES}
    for p, r in sorted(res.items()):
        by_stage[report.stage_of(r["desc"])].append(p)
    cost = next(iter(res.values()))["cost"]
    for s, pops in by_stage.items():
        if not pops:
            continue
        top = np.mean([res[p]["desc"]["true_top32"] for p in pops])
        print(f"\n[{s}] {len(pops)} populations; mean true top-32 F {top:+.4f}; A's regret "
              f"{np.mean([res[p]['point']['A']['regret'] for p in pops]):.5f}")
        for n in names:
            dF, dse = report.aggregate(res, pops, n, "meanF", True)
            rr, rse = report.regret_removed(res, pops, n) if n != "A" else (0.0, 0.0)
            vals = {m: report.aggregate(res, pops, n, m, False) for m in ("meanF", "p_best", "beat", "beat_body",
                                                                          "rank0F", "cost_ev")}
            print(f"  {n:11s} cost {cost[n]:.3f} ev {vals['cost_ev'][0]:.3f} | F {vals['meanF'][0]:+.5f} "
                  f"dF {dF:+.5f}±{dse:.5f} rr {rr:+.3f}±{rse:.3f} | p_best {vals['p_best'][0]:.3f} "
                  f"beat {vals['beat'][0]:.3f} beatB {vals['beat_body'][0]:.3f} | r0 {vals['rank0F'][0]:+.4f}"
                  f"±{vals['rank0F'][1]:.4f}")


if __name__ == "__main__":
    main()
