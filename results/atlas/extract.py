"""Data for the pilot visualisation page: evolution curves of every run and one fully traced, representative life
(F nearest the median of 24 kernel lives) per showcased body."""
import json
import math
import sys
from multiprocessing import get_context
from pathlib import Path

import numpy as np

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))
from src.life import analysis  # noqa: E402
from src.life import probe as P  # noqa: E402

OUT = Path(__file__).with_name("data")
OUT.mkdir(exist_ok=True)
ROOT = Path(__file__).resolve().parents[2] / "outputs" / "catch_pilot"
BODIES = ["speck_lmax4_hexprism_sex_s5", "speck_lmax4_hexprism_sex_s4", "speck_lmax4_hexprism_sex_s2",
          "speck_lmax4_hexprism_sex_s6", "speck_lmax4_hexprism_sex_s7", "lmax4_hexprism_sex_s5",
          "reflex@hollow3", "router@ring4"]
SEED0 = 38_000_000


def curves():
    out = {}
    for d in sorted(ROOT.glob("*_hexprism_sex_s*")):
        rows = [json.loads(line) for line in (d / "curves.jsonl").read_text().splitlines()]
        out[d.name] = dict(
            gen=[r["gen"] for r in rows],
            fit=[round(r["fitness"], 3) for r in rows],
            cells=[round(r["n_cells"], 1) for r in rows],
            valid=[[r["gen"], round(r["valid"], 3)] for r in rows if r.get("valid") is not None],
            evals=[round(r["evals"]) for r in rows])
        res = json.loads((d / "results.jsonl").read_text().splitlines()[0])
        out[d.name]["final"] = dict(F=round(res["F"], 3), cells=round(res["n_cells"], 1),
                                    skill=res["evals_to_skill"] is not None)
    (OUT / "curves.json").write_text(json.dumps(out, separators=(",", ":")))


def one(name):
    org, preset = P.hand(name) if "@" in name else P.load(name)
    seeds = analysis.fresh_seeds(24, seed0=SEED0)
    F = org.run(seeds, threads=1, preset=preset)["F"]
    med = float(np.median(F))
    seed = int(seeds[int(np.argmin(np.abs(F - med)))])
    tr = P.trace(org, seed, preset)
    P.relabel(tr)
    c = tr.cells
    cells = [[int(r.cid), int(r.a), int(r.b), int(r.z), str(r.cls), round(float(r.t_birth), 2),
              -1 if math.isinf(r.t_death) else round(float(r.t_death), 2), int(r.n_spikes)] for r in c.itertuples()]
    s = tr.spikes
    t = tr.traj
    cl = tr.clicks
    st = tr.strokes
    data = dict(name=name, preset=preset, seed=seed, F=round(float(tr.F), 3), F_median24=round(med, 3),
                F_mean24=round(float(np.mean(F)), 3), captures=int(tr.ledger["captures"]),
                misses=int(tr.ledger["misses"]), T=int(len(t)), cells=cells,
                spikes=dict(t=[round(float(x), 3) for x in s.t], c=[int(x) for x in s.cid],
                            m=[int(x) for x in s["mask"]]),
                traj=dict(X=[round(float(x), 3) for x in t.X], Y=[round(float(x), 3) for x in t.Y],
                          tx=[round(float(x), 3) for x in t.tx], ty=[round(float(x), 3) for x in t.ty]),
                clicks=[[round(float(r.t), 2), str(r.outcome)] for r in cl.itertuples()],
                pulls=dict(t=[round(float(x), 2) for x in st.t[st.pulled]], c=[int(x) for x in st.cid[st.pulled]]))
    (OUT / f"life_{name.replace('@', '_at_')}.json").write_text(json.dumps(data, separators=(",", ":")))
    return name, seed, data["F"], med, len(cells), len(s), tr.meta.get("seconds")


if __name__ == "__main__":
    curves()
    with get_context("fork").Pool(4) as pool:
        for r in pool.imap_unordered(one, BODIES):
            print(r, flush=True)
