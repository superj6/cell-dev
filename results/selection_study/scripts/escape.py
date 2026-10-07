"""How each scheme treats the bodies of hex seed 0's plateau escape (generations 12-16): the chance that at least one
body (median n_end >= 2) is among the 32 parents, the expected number of bodies chosen, and their true F, from the
measured genomes x lives matrices (sim.simulate with common random numbers)."""
from __future__ import annotations

import json
import sys

import numpy as np

import sim

PLAN = [s for s in sim.schemes() if s["name"] in sys.argv[2:]] if len(sys.argv) > 2 else sim.schemes()


def main() -> None:
    rows = {}
    for g in (12, 13, 14, 15, 16):
        z = np.load(f"meas/esc_hex_s0_g{g}.npz")
        F, ev, n_end = z["F"], z["events"].astype(float), z["n_end"]
        body = np.median(n_end, axis=1) >= 2
        res = sim.simulate(F, ev, body, np.arange(F.shape[1]), 4000, np.random.default_rng(g), PLAN, keep=True)
        tF = F.mean(1)
        rows[g] = {"n_body": int(body.sum()), "body_trueF": sorted([round(float(x), 5) for x in tF[body]])[::-1][:8],
                   "lone_F": float(z["lone_F"].mean())}
        for name, r in res.items():
            nb = body[r["chosen"]].sum(1)
            rows[g][name] = {"p_any_body": float((nb > 0).mean()), "mean_bodies": float(nb.mean())}
    print(json.dumps(rows))


if __name__ == "__main__":
    main()
