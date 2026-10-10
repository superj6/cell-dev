import sys, time, numpy as np
import harness as H
n = int(sys.argv[1]); worlds = sys.argv[2].split(","); cids = [int(x) for x in sys.argv[3].split(",")]
sd = H.seeds(n, 5)   # tuning block
fp = H.footprint("hollow3")
for wn in worlds:
    ref = H.tissue_run(H.reflex("hollow3"), wn, sd, threads=6)
    for cid in cids:
        t=time.time(); r = H.ctl_run(cid, H.default_params(cid), fp, wn, sd, threads=6); tc=time.time()-t
        s = H.summary(r)
        print(f"{wn:8s} {H.CONTROLLERS[cid].name:22s} F {s['F']:+.3f}±{s['F_se']:.3f} cap {s['captures']:.2f} miss {s['misses']:.2f} b2 {s['b2_clicks']:.1f} clicks {s['clicks']:.1f} spikes {s['spikes']:.0f} path {s['path']:.1f} diag {r.diag.mean(0)[:5].round(1)} vs reflex {H.pfmt(H.paired(r, ref))} (reflex {ref['F'].mean():+.2f}) t {tc/n*6:.3f}", flush=True)
