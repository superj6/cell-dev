"""The compact decision table (simres/*.json): per scheme, cost in lives and kernel events, and per stage the paired
change in the mean true F of the 32 chosen vs A (SE), the share of A's regret removed, and the changes in P(true best
chosen), share of chosen bodies beating the lone pump and true F of the rank-0 genome.

    python compact_table.py > compact_table.txt
"""
from __future__ import annotations

import glob

import numpy as np

import report

SCHEMES = ("A", "C n4", "C n5", "B1 K128 L2", "B2 K128 L2", "B2 K64 L3", "B1 K64 L4", "B2 K64 L4", "B1 K48 L5",
           "B2 K48 L5", "B2 K96 L3", "B1 K64 L6", "B2 K64 L6", "B2 K48 L8")
INFORMATIVE = ("escape", "bodies", "big")


def main() -> None:
    res = report.load(sorted(glob.glob("simres/*.json")))
    st = {s: [] for s in report.STAGES}
    for p, r in res.items():
        st[report.stage_of(r["desc"])].append(p)
    cost = next(iter(res.values()))["cost"]
    print("stage sizes:", {s: len(v) for s, v in st.items()})
    for s in report.STAGES:
        a = np.mean([res[p]["point"]["A"]["meanF"] for p in st[s]])
        top = np.mean([res[p]["desc"]["true_top32"] for p in st[s]])
        print(f"  {s:8s} A: chosen true F {a:+.5f}, true top-32 {top:+.5f}")
    print("\nscheme      lives  events | " + " | ".join(f"{s}: dF (SE) rr dp_best dbeatB dr0" for s in INFORMATIVE)
          + " | eq-mean rr | max |dF| founders/early/plateau")
    for n in SCHEMES:
        ev = np.mean([report.aggregate(res, st[s], n, "cost_ev", False)[0] for s in ("bodies", "big")])
        cells, rrs = [], []
        for s in INFORMATIVE:
            dF, dse = report.aggregate(res, st[s], n, "meanF", True)
            rr = report.regret_removed(res, st[s], n)[0] if n != "A" else 0.0
            rrs.append(rr)
            dpb = report.aggregate(res, st[s], n, "p_best", True)[0]
            dbb = report.aggregate(res, st[s], n, "beat_body", True)[0]
            dr0 = report.aggregate(res, st[s], n, "rank0F", True)[0]
            cells.append(f"{dF:+.5f} ({dse:.5f}) {rr:+.2f} {dpb:+.3f} {dbb:+.3f} {dr0:+.4f}")
        rest = max(abs(report.aggregate(res, st[s], n, "meanF", True)[0]) for s in ("founders", "early", "plateau"))
        print(f"{n:11s} {cost[n]:.3f} {ev:.3f} | " + " | ".join(cells) + f" | {np.mean(rrs):+.3f} | {rest:.5f}")


if __name__ == "__main__":
    main()
