"""LEAKAGE TEST. C4's decisions must be a function of (ping stream, own clock, own actions) only.
1. Run C4 (its bitwise copy, id 1005) closed-loop in a life; log every ping (t, sense index) and every ctl_fire call
   (callback time, act cell, kappa, requested t, scheduled t).
2. Re-run C4 (id 1006) with real receptors switched off (F_RECEPTOR_OFF: the controller gets no world pings), driven
   only by the logged ping stream injected at the logged times, in
     A: the same life (same seed),
     B: a different life (different seed: different target path, placements, turns, timer),
     C: a different world (v_t 0.3, tau_turn 5, t_resp 10, R 4-9, sigma 1.2, lam_s 1; other seed),
   and require the fire log to be bitwise identical. If C4 read any hidden target state, B and C would diverge.
3. Control: C4 closed-loop on the other seed must give a different fire log (the test is sensitive).
"""
import ctypes, json, numpy as np, harness as H
from src.life import spec
from common import *
LIB = OUT + "/vk_fast.so"
lib = H.load(LIB)
lib.v4h_log_enable.argtypes = [ctypes.c_int]
lib.v4h_log_get.restype = ctypes.c_long
lib.v4h_log_get.argtypes = [ctypes.POINTER(ctypes.c_double), ctypes.c_long]
fp = H.footprint("hollow3")
RO = spec.V3.flags("receptor_off")
def run_log(cid, p, world, seed, extra=None):
    lib.v4h_log_enable(1)
    r = H.ctl_run(cid, p, fp, world, [seed], threads=1, lib=LIB, privileged=False, extra=extra)
    n = lib.v4h_log_get(None, 0) if False else None
    buf = np.zeros(1 << 24)
    m = lib.v4h_log_get(buf.ctypes.data_as(ctypes.POINTER(ctypes.c_double)), len(buf))
    lib.v4h_log_enable(0)
    assert m <= len(buf)
    L = buf[:m].reshape(-1, 6)
    return r, L[L[:, 0] == 0][:, 1:3], L[L[:, 0] >= 1]
out = {}
lives = H.seeds(8, 417)
others = H.seeds(6, 417, first=0)
others = [s + 500 for s in lives]  # still inside block 417
for w in ("base", "pool"):
    p = np.r_[H.bayes_params(w), np.zeros(6)]
    ws = H.world_spec(w)
    wA = ws.with_(w + "_ro", flags=RO)
    wC = ws.with_(w + "_ro_alien", flags=RO, v_t=0.3, tau_turn=5.0, t_resp=10.0, R_min=4.0, R_max=9.0, sigma=1.2, lam_s=1.0)
    rows = []
    for s, s2 in zip(lives, others):
        r0, pings, fires = run_log(1005, p, w, s)
        ex = np.r_[len(pings), pings.reshape(-1)]
        res = {"seed": s, "pings": int(len(pings)), "logged_actions": int(len(fires)), "strokes": int(r0.diag[0, 2]), "path": float(r0["path"][0]), "captures": float(r0["captures"][0])}
        for tag, world, seed in (("A_same_life", wA, s), ("B_other_life", wA, s2), ("C_other_world", wC, s2)):
            r1, p1, f1 = run_log(1006, p, world, seed, extra=ex)
            fpr0 = np.r_[r0.diag[0, 2:4], r0.diag[0, 12:14], r0["kappa_sum"], r0["path"], r0["X_end"], r0["Y_end"]]
            fpr1 = np.r_[r1.diag[0, 2:4], r1.diag[0, 12:14], r1["kappa_sum"], r1["path"], r1["X_end"], r1["Y_end"]]
            res[tag] = dict(identical=bool(f1.shape == fires.shape and np.array_equal(f1, fires) and np.array_equal(fpr0, fpr1)),
                            strokes=int(r1.diag[0, 2]), clicks_cmd=int(r1.diag[0, 3]), path=float(r1["path"][0]),
                            n_fires=int(len(f1)), real_pings_seen=int(r1.diag[0, 0]),
                            captures_in_that_world=float(r1["captures"][0]))
        rc, pc, fc = run_log(1005, p, w, s2)
        res["control_closed_loop_other_life_identical"] = bool(fc.shape == fires.shape and np.array_equal(fc, fires))
        rows.append(res)
        print(w, res, flush=True)
    out[w] = rows
out["all_identical"] = all(r[t]["identical"] for w in ("base", "pool") for r in out[w] for t in ("A_same_life", "B_other_life", "C_other_world"))
out["controls_differ"] = all(not r["control_closed_loop_other_life_identical"] for w in ("base", "pool") for r in out[w])
print("ALL IDENTICAL:", out["all_identical"], " controls differ:", out["controls_differ"])
json.dump(out, open(OUT + "/test_replay_leak.json", "w"), indent=1)
