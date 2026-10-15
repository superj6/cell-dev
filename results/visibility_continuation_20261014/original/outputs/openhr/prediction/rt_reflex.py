"""In-world re-tune of the reflex (analysis.tune_knobs on hb.REFLEX_GRID), per prediction world:
  rt-pred@hollow3: start = frozen reflex@hollow3 knobs, n_rand 24, budget 48 (the first world, v0.3_tau200, used
                   n_rand 40, budget 80; the 'best reflex' candidate; the harness
                   retune_reflex.py logic: analysis.tune_knobs random screen + hill climb on hb.REFLEX_GRID);
  rt-pred@hollow2: start = frozen reflex@hollow2 knobs, n_rand 16, budget 32 (a 'do-less' candidate: smaller body);
  rt-pred@ring2:   start = frozen reflex@ring2 knobs, n_rand 12, budget 24 (do-less: the prior niche map's re-tuned
                   reflex picked ring2 at v_t 0.3 + d0 0.5).
Screen lives: block 120 (48); hill lives: block 121 (96). Output: out/reflex_rt.json (merged per world).
usage: rt_reflex.py world1,world2,... [shapes=hollow3,hollow2]"""
import sys
import time

from pcommon import *  # noqa: F401,F403
from src.life import analysis

worlds = sys.argv[1].split(",")
shapes = sys.argv[2].split(",") if len(sys.argv) > 2 else ["hollow3"]
scr, hill = seeds(48, B_RT_SCREEN), seeds(96, B_RT_HILL)
OUTP = f"{HERE}/out/reflex_rt.json"
CFG = {"hollow3": (24, 48), "hollow2": (16, 32), "ring2": (12, 24)}
for w in worlds:
    for shape in shapes:
        t = time.time()
        n_rand, budget = CFG[shape]
        start = hb.full_knobs(hb.SPECK_TUNED[f"reflex@{shape}"], hb.REFLEX_GRID)

        def ev(k, stage, shape=shape, w=w):
            return float(Fv(tissue(H.reflex(shape, k), w, scr if stage == "screen" else hill)).mean())

        res = analysis.tune_knobs(ev, start, hb.REFLEX_GRID, n_rand=n_rand, budget=budget, top=4, seed=1)
        cpu = (time.time() - t) * THREADS
        print(f"{w} {shape}: hill F {res['F']:+.3f} (start {ev(start, 'hill'):+.3f}) {cpu:.0f} CPU-s", flush=True)
        d = jload(OUTP, {})
        d.setdefault(w, {})[f"rt-pred@{shape}"] = dict(knobs=res["knobs"], hill_F=res["F"], cpu_s=cpu,
                                                       source=f"rt_reflex.py n_rand {n_rand} budget {budget}, "
                                                              f"screen block {B_RT_SCREEN} x48, hill block {B_RT_HILL} x96")
        jdump(d, OUTP)
