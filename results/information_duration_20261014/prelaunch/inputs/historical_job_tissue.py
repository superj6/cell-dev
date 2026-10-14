"""Job A: tissue bodies on the 1024 scoring lives (base, pool): frozen reflex, in-world re-tuned reflex
(knobs written HERE, not to harness/reflex_knobs.json), pilot SPECK bests s5/s7, router@ring4 and the grown router."""
import json, sys, time, os
import numpy as np
import harness as H
from src.life import analysis, handbuilt as hb, probe
from common import *
TH = int(sys.argv[1]) if len(sys.argv) > 1 else 2
knobs_path = os.path.join(OUT, "reflex_knobs_verify.json")
kn = json.load(open(knobs_path)) if os.path.exists(knobs_path) else {}
for w in ("base", "pool"):
    if w not in kn:
        t = time.time()
        start = hb.full_knobs(hb.SPECK_TUNED["reflex@hollow3"], hb.REFLEX_GRID)
        def ev(k, stage):
            return float(H.tissue_run(H.reflex("hollow3", k), w, RT_SCREEN if stage == "screen" else RT_HILL,
                                      threads=TH)["F"].mean())
        res = analysis.tune_knobs(ev, start, hb.REFLEX_GRID, n_rand=40, budget=100, top=4, seed=1)
        f0 = ev(start, "hill")
        kn[w] = dict(knobs=res["knobs"], hill_F=res["F"], frozen_hill_F=f0, sec=time.time() - t,
                     source="verify_headline job_tissue.py: tune_knobs n_rand 40 budget 100, screen block 410 x48, hill block 411 x128")
        json.dump(kn, open(knobs_path, "w"), indent=1)
        print(f"{w}: retune hill F {res['F']:+.3f} (frozen {f0:+.3f}) {time.time() - t:.0f}s", flush=True)
bodies = {}
for run in ("speck_lmax4_hexprism_sex_s5", "speck_lmax4_hexprism_sex_s7"):
    org, preset = probe.load(run)
    assert preset == "catch_speck_l4", preset
    bodies[run.split("_")[-1]] = org
bodies["router@ring4"] = H.router("ring4")
rk = dict(hb.SPECK_TUNED["router@ring4"], **hb.ROUTER_FIXED)
bodies["router_grn"] = hb.GrnBody("router/GRN window 0.2", hb.router_genome(rk, 0.2))
for w in ("base", "pool"):
    t = time.time()
    name, ref, means = H.best_reflex(w, EVAL, threads=TH, extra_candidates={"rt-verify": kn[w]["knobs"]})
    print(w, "best reflex", name, means, f"{time.time() - t:.0f}s", flush=True)
    for nm in means:
        r = ref if nm == name else H.tissue_run(H.reflex("hollow3", None if nm == "reflex@hollow3" else kn[w]["knobs"]), w, EVAL, threads=TH)
        save(f"{w}_reflex_{'frozen' if nm == 'reflex@hollow3' else 'rt'}", r)
    for bn, org in bodies.items():
        t = time.time()
        r = H.tissue_run(org, w, EVAL, threads=TH)
        save(f"{w}_{bn}", r)
        print(w, bn, f"F {r['F'].mean():+.3f} vs best reflex {H.pfmt(H.paired(r, ref))} n_end {r['n_end'].mean():.1f} {time.time() - t:.0f}s", flush=True)
print("done")
