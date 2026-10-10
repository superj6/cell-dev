"""In-world re-tune of reflex@hollow3 (analysis.tune_knobs: random screen + hill climb on the REFLEX_GRID) for the
harness worlds that lack one. Screen lives: block 7 (48); hill lives: block 8 (128). Adds 'rt-harness' entries to
reflex_knobs.json."""
import json, sys, time
import harness as H
from src.life import analysis, handbuilt as hb
THREADS = 6
worlds = sys.argv[1].split(",")
budget = int(sys.argv[2]) if len(sys.argv) > 2 else 100
scr, hill = H.seeds(48, 7), H.seeds(128, 8)
start = hb.full_knobs(hb.SPECK_TUNED["reflex@hollow3"], hb.REFLEX_GRID)
p = f"{H.HERE}/reflex_knobs.json"
for w in worlds:
    t = time.time()
    def ev(k, stage):
        return float(H.tissue_run(H.reflex("hollow3", k), w, scr if stage == "screen" else hill, threads=THREADS)["F"].mean())
    res = analysis.tune_knobs(ev, start, hb.REFLEX_GRID, n_rand=40, budget=budget, top=4, seed=1)
    print(f"{w}: hill F {res['F']:+.3f} ({res.get('hill_evaluations')} hill evals, {time.time() - t:.0f}s)", flush=True)
    d = json.load(open(p))
    d.setdefault(w, {})["rt-harness"] = dict(knobs=res["knobs"], source=f"harness retune_reflex.py budget {budget} "
                                             f"(screen block 7 x48, hill block 8 x128), hill F {res['F']:.3f}")
    json.dump(d, open(p, "w"), indent=1)
