"""Job B: C4 default and lightly tuned (decision knobs, blocks 412-415) on the 1024 scoring lives."""
import json, sys, time, os
import numpy as np
import harness as H
from common import *
TH = int(sys.argv[1]) if len(sys.argv) > 1 else 2
fp = H.footprint("hollow3")
tp = os.path.join(OUT, "c4_tuned.json")
tuned = json.load(open(tp)) if os.path.exists(tp) else {}
for w in ("base", "pool"):
    if os.path.exists(os.path.join(RAW, f"{w}_c4_default.npz")):
        continue
    t = time.time()
    r = H.ctl_run(H.C4, H.bayes_params(w), fp, w, EVAL, threads=TH)
    save(f"{w}_c4_default", r)
    print(w, "C4 default", f"F {r['F'].mean():+.3f} {time.time() - t:.0f}s", flush=True)
TUNE = C4_TUNE[:128]  # blocks 412-413
for w in ("base", "pool"):
    if w not in tuned:
        t = time.time()
        x0 = H.bayes_params(w)
        mask = [H.C4_NAMES.index(k) for k in ("gain", "kmax", "min_align", "tol", "q_tap", "steer_min")]
        res = H.es_tune(H.C4, x0, fp, w, TUNE, iters=5, popsize=8, lives_per_gen=48, threads=TH, seed=7,
                        mask=mask, log=lambda s: print(w, s, flush=True))
        f0 = float(H.ctl_run(H.C4, x0, fp, w, TUNE, threads=TH)["F"].mean())
        tuned[w] = dict(x=list(map(float, res["x"])), names=list(H.C4_NAMES), F_tune=res["F"], F_default_tune=f0,
                        sec=time.time() - t, how="es_tune iters 5 popsize 8 lives_per_gen 48 on blocks 412-413 (128), mask gain kmax min_align tol q_tap steer_min, seed 7")
        json.dump(tuned, open(tp, "w"), indent=1)
        print(w, f"tuned F_tune {res['F']:+.3f} (default {f0:+.3f})", {k: round(v, 3) for k, v in zip(H.C4_NAMES, res['x'])}, flush=True)
    t = time.time()
    r = H.ctl_run(H.C4, np.array(tuned[w]["x"]), fp, w, EVAL, threads=TH)
    save(f"{w}_c4_tuned", r)
    print(w, "C4 tuned", f"F {r['F'].mean():+.3f} {time.time() - t:.0f}s", flush=True)
print("done")
