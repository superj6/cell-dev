"""Paired check of the flank_best gene input on square8 (review of ABI 2, 2026-10-07): R25-v1's GRN genome with its
rate gate on flank_best (ABI 1) or on n_view (ABI 2), on the gates' fresh lives (seeds 5,000,000 + s).

    git archive f2142c8 | tar -x -C /tmp/abi1                         # the ABI-1 tree
    python sq8_pair.py /tmp/abi1 abi1.npz flank                        # flank_best gate (ABI 1 only)
    python sq8_pair.py /path/to/cell-dev abi2.npz                      # n_view >= D - 1 gate (ABI 2 default)

pair.npz holds both runs, keys ``abi1/<k>`` and ``abi2/<k>``: per-life F of the genome on square8 (D = 8) at 49, 81,
121 and 169 cells (288 lives, ``grn/<N>``), the program at 81 (288 lives, ``prog/81``: bitwise equal in both trees,
so the lives are the same) and the hex genome (D = 6) at 61, 91 and 127 cells (144 lives, ``grn_hex/<N>``).
4 kernel threads; about 50 s per tree.
"""
import sys
import time

root, out = sys.argv[1], sys.argv[2]
gate = sys.argv[3] if len(sys.argv) > 3 else None
sys.path.insert(0, root)
sys.path.insert(0, root + "/scripts")
import numpy as np  # noqa: E402

import life_gates as lg  # noqa: E402
from src.life import handbuilt as hb  # noqa: E402


def genome(D: int):
    return hb.r25_genome(D=D) if gate is None else hb.r25_genome(gate=gate, D=D)


lg._THREADS[0] = 4
t0 = time.time()
org = hb.GrnOrganism("square8", genome(8))
res = {f"grn/{N}": lg.lives(org, N, 288, lattice="square8")["F"] for N in (49, 81, 121, 169)}
res["prog/81"] = lg.lives(hb.R25_V1, 81, 288, lattice="square8")["F"]
hexorg = hb.GrnOrganism("hex", genome(6))
for N in (61, 91, 127):
    res[f"grn_hex/{N}"] = lg.lives(hexorg, N, 144)["F"]
np.savez(out, **res)
print({k: round(float(v.mean()), 4) for k, v in res.items()}, round(time.time() - t0, 1), "s", flush=True)
