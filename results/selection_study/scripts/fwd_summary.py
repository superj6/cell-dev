"""Summarize forward escape runs (fwd/*.json): per scheme, replicates whose final parents are mostly bodies (escape),
any body kept, final parents beating the lone cell on average, and Fisher exact p against A."""
from __future__ import annotations

import glob
import json
import sys
from collections import defaultdict
from math import comb

LONE = 0.0328


def fisher(a: int, n1: int, b: int, n2: int) -> float:
    """Two-sided Fisher exact p for a/n1 vs b/n2."""
    k, n = a + b, n1 + n2
    p0 = comb(n1, a) * comb(n2, b) / comb(n, k)
    tot = 0.0
    for x in range(max(0, k - n2), min(k, n1) + 1):
        p = comb(n1, x) * comb(n2, k - x) / comb(n, k)
        if p <= p0 * (1 + 1e-9):
            tot += p
    return tot


def main() -> None:
    rows = [r for f in sorted(glob.glob(sys.argv[1] if len(sys.argv) > 1 else "fwd/esc_g12*.json"))
            for r in json.load(open(f))]
    by = defaultdict(dict)
    for r in rows:
        by[r["scheme"]][r["rep"]] = r
    a = by.get("A", {})
    a_esc = sum(r["body_share"] >= 0.5 for r in a.values())
    for s, reps in by.items():
        v = list(reps.values())
        esc = sum(r["body_share"] >= 0.5 for r in v)
        anyb = sum(r["body_share"] > 0 for r in v)
        beat = sum(r["mean_F"] > LONE + 0.0005 for r in v)
        p = fisher(esc, len(v), a_esc, len(a)) if s != "A" and a else float("nan")
        mf = sorted(r["mean_F"] for r in v if r["body_share"] >= 0.5)
        print(f"{s:10s} reps {len(v):2d} escaped {esc:2d} ({esc / len(v):.2f}) any-body {anyb:2d} "
              f"parents-beat-lone {beat:2d} | Fisher p vs A {p:.3f} | escaped runs' mean F {[round(x, 4) for x in mf]}")


if __name__ == "__main__":
    main()
