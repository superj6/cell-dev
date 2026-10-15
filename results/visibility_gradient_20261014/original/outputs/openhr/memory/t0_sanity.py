"""Sanity: C5 with C4's settings equals C4 bitwise (ledger); M1 dark_mode 0 equals C1; disk4x4 vs ring4; timing.
Spare block 119 (never used for scoring or tuning records)."""
from mcommon import *
sd = H.seeds(16, 119)
fp = H.footprint("hollow3")
print("registered:", H.registered(LIB))
for wn in ("blink20", "base1", "pool_blink20", "flash5_dim25"):
    w = WORLDS[wn]
    p4 = H.bayes_params(w)
    a = crun(H.C4, p4, fp, w, sd)
    p5 = c5_params(w)
    p5[:21] = p4
    b = crun(C5, p5, fp, w, sd)
    print(wn, "C4==C5 ledger:", np.array_equal(a.ledger, b.ledger), "F", round(a["F"].mean(), 3), round(b["F"].mean(), 3),
          "cpu/life", round(a.cpu_per_life, 3), round(b.cpu_per_life, 3), flush=True)
    c = crun(H.C1, H.default_params(H.C1), fp, w, sd)
    d = crun(M1, H.params(M1), fp, w, sd)
    print(wn, "C1==M1 ledger:", np.array_equal(c.ledger, d.ledger), round(c["F"].mean(), 3), round(d["F"].mean(), 3), flush=True)
w = WORLDS["blink20"]
p = c5_params(w, tau_eff=0.3, dt=0.453, gain=0.962, min_align=0.367, tol=0.058, q_tap=0.112, h=0.25, W=7.0)
r4 = crun(C5, p, "ring4", w, sd); d4 = crun(C5, p, "disk4x4", w, sd)
print("ring4 F", r4["F"].mean(), "disk4x4 F", d4["F"].mean(), "diff per life", np.unique(np.round(H.F(r4) - H.F(d4), 6)),
      "captures equal", np.array_equal(r4["captures"], d4["captures"]), "cpu", r4.cpu_per_life)
