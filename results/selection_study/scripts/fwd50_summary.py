"""Summarize the 50-generation forward escape runs from their logs (logs/fwd50_*.log): per scheme and checkpoint,
replicates whose parents are mostly bodies, whose parents' mean true F beats the lone cell by 0.0005, and the mean
and median of the parents' mean F (32 fresh shared lives). Only replicates finished by every scheme are compared."""
from __future__ import annotations

import glob
import json
from collections import defaultdict

import numpy as np

LONE = 0.0328


def main() -> None:
    rows = defaultdict(dict)
    for f in sorted(glob.glob("logs/fwd50_*.log")):
        for line in open(f):
            r = json.loads(line)
            rows[r["scheme"]][(r["rep"], r["gens"])] = r
    done = {s: {rep for rep, g in v if g == 50} for s, v in rows.items()}
    common = sorted(set.intersection(*done.values())) if done else []
    print(f"replicates finished by every scheme: {len(common)} {common}")
    for g in (20, 35, 50):
        for s, v in rows.items():
            rs = [v[(rep, g)] for rep in common if (rep, g) in v]
            mf = np.array([r["mean_F"] for r in rs])
            body = sum(r["body_share"] >= 0.5 for r in rs)
            beat = int((mf > LONE + 0.0005).sum())
            print(f"gen {g:2d} {s:8s} n {len(rs):2d} body-parents {body:2d} beat-lone {beat:2d} mean F {mf.mean():+.4f} "
                  f"median {np.median(mf):+.4f} best-run {mf.max():+.4f}")


if __name__ == "__main__":
    main()
