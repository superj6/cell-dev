"""Re-score the SAVED controllers (no re-tuning) on any seed block, for verification.

    cd /home/jgon/project/ml/cell-dev && PYTHONPATH=.:<memory dir> .venv/bin/python <memory dir>/rescore.py \
        --block 119 --n 256 [--worlds blink20,blink5_5] [--threads 2]

For each world it runs, on fresh_seeds(n, 43_000_000 + 10_000 * block):
  - every reflex candidate (frozen reflex@hollow3, harness re-tunes, memory/reflex_knobs_mem.json) -> best reflex;
  - C1 (privileged ceiling) and M1 extrapolate / idle-in-dark (memory value given perfect sensing);
  - C5 ring4 with tuned/<world>_ring4.json (the information-matched controller) and its ablations;
  - the best do-less variant recorded in scores/<world>.json.
and prints the paired gaps (mean +- SE of the per-life difference). Writes rescore_b<block>_n<n>.json.
"""
import argparse
import json
from mcommon import *
from src.life import handbuilt as hb

ap = argparse.ArgumentParser()
ap.add_argument("--block", type=int, required=True)
ap.add_argument("--n", type=int, default=256)
ap.add_argument("--worlds", default=",".join(WORLDS))
ap.add_argument("--threads", type=int, default=THREADS)
a = ap.parse_args()
sd = H.seeds(a.n, a.block)
kw = dict(threads=a.threads)
res = {}
for wn in a.worlds.split(","):
    w = WORLDS[wn]
    sc = json.load(open(os.path.join(HERE, f"scores/{wn}.json"))) if os.path.exists(os.path.join(HERE, f"scores/{wn}.json")) else {}
    cands = {"reflex@hollow3": None}
    hk = H.retuned_reflex_knobs()
    related = {"pool_blink20": ["pool"], "base1": [], "flash5_dim25": ["blink20"]}
    for name in [wn] + related.get(wn, ["blink20"] if wn != "base1" else []):
        for k, v in hk.get(name, {}).items():
            cands[f"{k}({name})"] = v["knobs"]
    p = os.path.join(HERE, "reflex_knobs_mem.json")
    if os.path.exists(p):
        for k, v in json.load(open(p)).get(wn, {}).items():
            cands[k] = v["knobs"]
    refl = {k: trun(H.reflex("hollow3", v), w, sd, **kw) for k, v in cands.items()}
    best = max(refl, key=lambda k: H.F(refl[k]).mean())
    ref = refl[best]
    row = dict(best_reflex=best, best_reflex_F=float(H.F(ref).mean()),
               reflex_candidates={k: float(H.F(v).mean()) for k, v in refl.items()})
    c1 = crun(H.C1, H.default_params(H.C1), "hollow3", w, sd, **kw)
    row["C1_gap"] = pair(c1, ref)
    me = crun(M1, H.params(M1, dark_mode=1.0), "hollow3", w, sd, **kw)
    mi = crun(M1, H.params(M1, dark_mode=3.0), "hollow3", w, sd, **kw)
    row["M1_extrapolate_minus_idle"] = pair(me, mi)
    tj = os.path.join(HERE, f"tuned/{wn}_ring4.json")
    if os.path.exists(tj):
        x = np.array(json.load(open(tj))["x"])
        full = crun(C5, x, "ring4", w, sd, **kw)
        row["C5_ring4_F"] = float(H.F(full).mean())
        row["C5_ring4_gap"] = pair(full, ref)
        row["C5_cpu_per_life"] = full.cpu_per_life
        if world_rules(w)["blink_on"] > 0:
            ra = crun(C5, pset(C5, x, blink_on=0.0, blink_off=0.0, dark_amp=0.0), "ring4", w, sd, **kw)
            rb = crun(C5, pset(C5, x, idle_dark=0.5), "ring4", w, sd, **kw)
            row["C5_full_minus_no_dark_model"] = pair(full, ra)
            row["C5_full_minus_idle_in_dark"] = pair(full, rb)
    dl = sc.get("do_less", {}).get("best")
    if dl:
        bk = cands[best] or hb.SPECK_TUNED["reflex@hollow3"]
        bodies = {"reflex@hollow2 frozen": lambda: H.reflex("hollow2"),
                  "reflex@hollow2 best knobs": lambda: H.reflex("hollow2", bk, name="h2bk"),
                  "reflex@ring2 frozen": lambda: H.reflex("ring2"),
                  "clicker (2 cells)": lambda: hb.CLICKER,
                  "hollow3 K.w0 0.75 (higher tap threshold)": lambda: H.reflex("hollow3", dict(bk, **{"K.w0": 0.75}), name="k"),
                  "hollow3 C.g_r 0.5 (fewer centre pings -> fewer taps)": lambda: H.reflex("hollow3", dict(bk, **{"C.g_r": 0.5}), name="c"),
                  "hollow3 C.t_ref 4 + K.t_ref 4 (fewer clicks)": lambda: H.reflex("hollow3", dict(bk, **{"C.t_ref": 4.0, "K.t_ref": 4.0}), name="s"),
                  "hollow3 M.kappa 0.5 (weaker steering)": lambda: H.reflex("hollow3", dict(bk, **{"M.kappa": 0.5}), name="m")}
        r = trun(bodies[dl](), w, sd, **kw)
        row["do_less"] = dict(name=dl, gap=pair(r, ref))
    res[wn] = row
    print(f"{wn:18s} best reflex {best} {row['best_reflex_F']:+.2f} | C1 {fmt(row['C1_gap'])} | M1 memory {fmt(row['M1_extrapolate_minus_idle'])}"
          + (f" | C5 ring4 {fmt(row['C5_ring4_gap'])}" if "C5_ring4_gap" in row else "")
          + (f" | -dark model {fmt(row['C5_full_minus_no_dark_model'])} | -idle {fmt(row['C5_full_minus_idle_in_dark'])}" if "C5_full_minus_no_dark_model" in row else "")
          + (f" | do-less {fmt(row['do_less']['gap'])}" if "do_less" in row else ""), flush=True)
    jdump(res, os.path.join(HERE, f"rescore_b{a.block}_n{a.n}.json"))
