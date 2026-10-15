"""In-world re-tune of reflex@hollow3 for the memory worlds (the logic of harness/retune_reflex.py:
analysis.tune_knobs, random screen + hill climb on hb.REFLEX_GRID, n_rand 40, budget 100, top 4, seed 1).
Screen lives: block 116 (48); hill lives: block 117 (128). Never touches the scoring blocks.
Writes memory/reflex_knobs_mem.json {world: {"rt-mem": {knobs, F_hill, source, cpu_s}}} after each world
(the shared harness/reflex_knobs.json is never written).
usage: retune_reflex_mem.py world1,world2 [budget 100] [threads 1]"""
import json, os, sys, time
from mcommon import *
from src.life import analysis, handbuilt as hb
worlds = sys.argv[1].split(",")
budget = int(sys.argv[2]) if len(sys.argv) > 2 else 100
thr = int(sys.argv[3]) if len(sys.argv) > 3 else 1
scr, hill = H.seeds(48, RT_SCREEN), H.seeds(128, RT_HILL)
start = hb.full_knobs(hb.SPECK_TUNED["reflex@hollow3"], hb.REFLEX_GRID)
p = os.path.join(HERE, "reflex_knobs_mem.json")
for wn in worlds:
    d = json.load(open(p)) if os.path.exists(p) else {}
    if "rt-mem" in d.get(wn, {}):
        print(f"{wn}: already re-tuned, skipping", flush=True)
        continue
    w = WORLDS[wn]
    t, c0 = time.time(), cpu_now()

    def ev(k, stage):
        return float(H.tissue_run(H.reflex("hollow3", k), w, scr if stage == "screen" else hill, threads=thr,
                                  lib=LIB)["F"].mean())
    res = analysis.tune_knobs(ev, start, hb.REFLEX_GRID, n_rand=40, budget=budget, top=4, seed=1)
    F_start = ev(start, "hill")
    print(f"{wn}: hill F {res['F']:+.3f} (frozen start {F_start:+.3f}; {res.get('hill_evaluations')} hill evals, "
          f"{time.time() - t:.0f}s wall, {cpu_now() - c0:.0f} CPU-s)", flush=True)
    d = json.load(open(p)) if os.path.exists(p) else {}
    d.setdefault(wn, {})["rt-mem"] = dict(knobs=res["knobs"], F_hill=res["F"], F_hill_frozen=F_start,
                                          cpu_s=cpu_now() - c0,
                                          source=f"memory/retune_reflex_mem.py budget {budget} (screen block "
                                                 f"{RT_SCREEN} x48, hill block {RT_HILL} x128)")
    json.dump(d, open(p, "w"), indent=1)
