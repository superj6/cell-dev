"""Exploration on the spare block 119 (never used for scoring or tuning records): C5 on ring4 with the start knobs,
memory model on / off, velocity memory on / off, vs the frozen reflex@hollow3 on the same lives.
usage: t2_explore.py n worlds"""
import sys
from mcommon import *
n = int(sys.argv[1]) if len(sys.argv) > 1 else 64
worlds = sys.argv[2].split(",") if len(sys.argv) > 2 else MEMORY_WORLDS
sd = H.seeds(n, 119)
TB = dict(tau_eff=0.3, dt=0.453, gain=0.962, min_align=0.367, tol=0.058, q_tap=0.112)
STARTS = {"base1": dict(tau_eff=0.338, dt=0.529, gain=1.033, min_align=0.536, tol=0.06, q_tap=0.157),
          "pool_blink20": dict(tau_eff=0.3, dt=0.661, gain=1.803, min_align=0.496, tol=0.154, q_tap=0.232)}
for wn in worlds:
    w = WORLDS[wn]
    ref = trun(H.reflex("hollow3"), w, sd)
    base = c5_params(w, **STARTS.get(wn, TB), h=0.25, W=7.0, vel=1.0, tau_v=12.0, sig_p=1.0, vel_gain=0.5, gate=1.5)
    var = {"C5 start (mem+vel)": base,
           "no vel": pset(C5, base, vel=0.0),
           "no dark model": pset(C5, base, blink_on=0.0, blink_off=0.0, dark_amp=0.0),
           "idle while dark": pset(C5, base, idle_dark=0.5)}
    print(f"{wn}: reflex F {ref['F'].mean():+.2f} cap {ref['captures'].mean():.1f} dark {ref.ledger[:,21].mean():.1f} "
          f"miss {ref['misses'].mean():.1f} cpu {ref.cpu_per_life:.3f}", flush=True)
    R = {}
    for lab, p in var.items():
        r = crun(C5, p, "ring4", w, sd)
        R[lab] = r
        s = summ(r)
        print(f"  {lab:20s} F {s['F']:+.2f} cap {s['captures']:.1f} dark {s['dark_caps']:.1f} miss {s['misses']:.1f} "
              f"vs reflex {fmt(pair(r, ref))} vs start {fmt(pair(R['C5 start (mem+vel)'], r))} cpu {s['cpu_per_life']:.3f}",
              flush=True)
