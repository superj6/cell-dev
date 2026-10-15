"""Prediction-family study: worlds, controller parameter builders, seed blocks, helpers (scratch; no repo edits).

Seed blocks (this agent owns 120-139; fresh_seeds(n, 43_000_000 + 10_000 * block)):
  120 reflex re-tune screen lives, 121 reflex re-tune hill lives,
  122 controller ES tuning lives (subsets per generation), 123 controller tuning check lives,
  124 do-less variant tuning lives, 125 C3 ES lives,
  130 scoring lives (first 512), 131 extra scoring lives (if the SE of a gap exceeds 0.15), 135+ spare / verifier.
Worlds: v{0.2,0.3}_tau{200,5}, v0.4_tau{200,20} on catch_speck_l4 (today's d0 1 / d_min 0.5, as the prior study), the
same six on POOL (sigma 0.4, lam_s 4, d0 0.5, d_min 0.25), and the references base1 and pool (v_t 0.1, tau_turn 20).
"""
from __future__ import annotations

import json
import os
import sys
import time

import numpy as np

HERE = os.path.dirname(os.path.abspath(__file__))
HARNESS = os.path.join(os.path.dirname(HERE), "harness")
for p in (HARNESS, HERE):
    if p not in sys.path:
        sys.path.insert(0, p)
import harness as H  # noqa: E402
from src.life import spec  # noqa: E402
from src.life import handbuilt as hb  # noqa: E402

LIB = os.path.join(HERE, "pk_fast.so")
PF = 1201
THREADS = int(os.environ.get("PRED_THREADS", "2"))

B_RT_SCREEN, B_RT_HILL, B_TUNE, B_TCHECK, B_DOLESS, B_C3 = 120, 121, 122, 123, 124, 125
B_SCORE, B_SCORE2 = 130, 131

FAST = dict(d0=0.5, d_min=0.25)
POOLK = dict(FAST, sigma=0.4, lam_s=4.0)


def _w(name, base, v, tau):
    over = dict(base)
    if v is not None:
        over.update(v_t=v, tau_turn=tau)
    return H.WorldSpec(name, over=over)


WORLDS = {}
for v, tau in ((0.2, 200.0), (0.2, 5.0), (0.3, 200.0), (0.3, 5.0), (0.4, 200.0), (0.4, 20.0)):
    WORLDS[f"v{v}_tau{tau:g}"] = _w(f"v{v}_tau{tau:g}", {}, v, tau)
    WORLDS[f"pool_v{v}_tau{tau:g}"] = _w(f"pool_v{v}_tau{tau:g}", POOLK, v, tau)
WORLDS["base1"] = H.WORLDS["base1"]
WORLDS["pool"] = H.WORLDS["pool"]
MAIN = [k for k in WORLDS if k.startswith("v")] + [k for k in WORLDS if k.startswith("pool_v")]
REFS = ["base1", "pool"]

# Re-tuned reflex@hollow3 knob sets of earlier studies (harness reflex_knobs.json was lost in the reboot; these were
# printed in the previous attempt's transcript, see reflex_knobs_recovered.json). They were tuned on other studies'
# lives, never on this study's blocks; they only ADD candidates to the best-reflex max (conservative for the gaps).
RECOVERED = json.load(open(os.path.join(HERE, "reflex_knobs_recovered.json"))) \
    if os.path.exists(os.path.join(HERE, "reflex_knobs_recovered.json")) else {}
RECOVERED_FOR = {"base1": ["base1"], "pool": ["pool"]}
for _w_ in MAIN:
    RECOVERED_FOR[_w_] = ["pool"] if _w_.startswith("pool_") else ["lead", "base1"]


def reflex_candidates(world) -> dict:
    """{name: knobs} extra reflex@hollow3 candidates for H.best_reflex: this study's in-world re-tune (out/reflex_rt.json)
    plus the recovered sets of related worlds (duplicates removed)."""
    out, seen = {}, set()
    rt = jload(f"{HERE}/out/reflex_rt.json", {}).get(world, {})
    if "rt-pred@hollow3" in rt:
        out["rt-pred@hollow3"] = rt["rt-pred@hollow3"]["knobs"]
    seen.add(tuple(sorted(hb.full_knobs(hb.SPECK_TUNED["reflex@hollow3"], hb.REFLEX_GRID).items())))
    for k in out.values():
        seen.add(tuple(sorted(k.items())))
    for src in RECOVERED_FOR.get(world, []):
        for name, v in RECOVERED.get(src, {}).items():
            key = tuple(sorted(v["knobs"].items()))
            if key in seen:
                continue
            seen.add(key)
            out[f"rec:{src}:{name}"] = v["knobs"]
    return out


def best_reflex(world, sd, threads=None):
    """H.best_reflex on these lives with this study's candidates: (name, lives, {name: mean F}, {name: lives})."""
    th = threads or THREADS
    cands = reflex_candidates(world)
    t = time.time()
    name, ref, means = H.best_reflex(WORLDS.get(world, world), sd, threads=th, extra_candidates=cands)
    ref.cpu_per_life = (time.time() - t) * th / len(sd) / max(1, len(means))
    return name, ref, means, cands


def world_obj(name):
    ws = WORLDS[name] if isinstance(name, str) else name
    return spec.world(ws.preset, **ws.over)


# ------------------------------------------------------------------------------------------- PF controller
PF_NAMES = ("sigma", "lam_s", "lam_bg", "v_m", "tau_turn", "R_min", "R_max", "t_resp", "rho_c", "N", "dt", "q_pos",
            "lead", "gain", "kmax", "min_align", "tol", "q_tap", "tap_kappa", "r_box", "steer_min", "b_min",
            "tb_min", "ess_thr", "rough_xy", "rough_th", "seed", "tap_on_ping", "v_follow", "intercept")
PF_DEFAULT = dict(N=1000, dt=0.5, q_pos=0.0, lead=2.0, gain=1.0, kmax=1.0, min_align=0.5, tol=0.15, q_tap=0.4,
                  tap_kappa=1.0, r_box=1.0, steer_min=0.0, b_min=0.01, tb_min=0.01, ess_thr=0.5, rough_xy=0.05,
                  rough_th=0.05, seed=1.0, tap_on_ping=0.0, v_follow=0.0, intercept=1.0)
PF_LO = dict(q_pos=0.0, lead=-1.0, gain=0.2, kmax=0.2, min_align=0.0, tol=0.0, q_tap=0.01, tap_kappa=0.6, r_box=0.3,
             steer_min=0.0, b_min=0.0, tb_min=0.0, ess_thr=0.1, rough_xy=0.0, rough_th=0.0, v_follow=0.0,
             intercept=0.0, dt=0.1)
PF_HI = dict(q_pos=0.5, lead=8.0, gain=2.0, kmax=1.0, min_align=0.95, tol=1.0, q_tap=0.9, tap_kappa=1.0, r_box=2.5,
             steer_min=0.5, b_min=0.1, tb_min=0.1, ess_thr=0.9, rough_xy=0.3, rough_th=0.5, v_follow=1.5,
             intercept=1.0, dt=1.0)


def pf_params(world, velocity=True, **kw) -> np.ndarray:
    """PF parameters with the world's fixed rules filled in. velocity=False: the ablation (v_m 0: no velocity state,
    motion = position diffusion q_pos only; no tumbles)."""
    w = world_obj(world)
    d = dict(sigma=w.sigma, lam_s=w.lam_s, lam_bg=w.lam_bg, v_m=w.v_t if velocity else 0.0,
             tau_turn=w.tau_turn if velocity else 0.0, R_min=w.R_min, R_max=w.R_max, t_resp=w.t_resp, rho_c=w.rho_c)
    d.update(PF_DEFAULT)
    if not velocity:
        d["q_pos"] = max(0.05, float(w.v_t))
    d.update(kw)
    return np.array([float(d[k]) for k in PF_NAMES])


def pf_bounds(x0, names):
    lo = x0.copy(); hi = x0.copy()
    for n in names:
        i = PF_NAMES.index(n)
        lo[i], hi[i] = PF_LO[n], PF_HI[n]
    return lo, hi


def pf_dict(x):
    return {k: float(v) for k, v in zip(PF_NAMES, x)}


H.register(H.CtlSpec(PF, "PF interceptor", False, PF_NAMES, tuple(pf_params("base1"))))


# ------------------------------------------------------------------------------------------- runs and stats
def seeds(n, block, first=0):
    return H.seeds(n, block, first)


def ctl(cid, p, fp, world, sd, **kw):
    kw.setdefault("threads", THREADS)
    kw.setdefault("lib", LIB)
    t = time.time()
    r = H.ctl_run(cid, p, H.footprint(fp) if isinstance(fp, str) else fp, WORLDS.get(world, world), sd, **kw)
    r.cpu_per_life = (time.time() - t) * kw["threads"] / len(sd)
    return r


def tissue(body, world, sd, **kw):
    kw.setdefault("threads", THREADS)
    kw.setdefault("lib", LIB)
    t = time.time()
    r = H.tissue_run(body, WORLDS.get(world, world), sd, **kw)
    r.cpu_per_life = (time.time() - t) * kw["threads"] / len(sd)
    return r


def Fv(r):
    return np.asarray(r["F"], dtype=np.float64)


def paired(a, b):
    fa = Fv(a) if hasattr(a, "ledger") else np.asarray(a)
    fb = Fv(b) if hasattr(b, "ledger") else np.asarray(b)
    d = fa - fb
    n = len(d)
    sd = float(d.std(ddof=1))
    return dict(mean=float(d.mean()), se=sd / np.sqrt(n), sd=sd, z=float(d.mean() / (sd / np.sqrt(n))) if sd > 0 else 0.0,
                n=n)


def summ(r):
    out = {k: float(np.mean(r[k])) for k in ("F", "captures", "misses", "clicks", "spikes", "cost", "income")}
    out["F_se"] = float(Fv(r).std(ddof=1) / np.sqrt(len(Fv(r))))
    out["cpu_per_life"] = float(getattr(r, "cpu_per_life", float("nan")))
    return out


def fmt(d):
    return f"{d['mean']:+.2f} +- {d['se']:.2f}"


def jdump(obj, path):
    tmp = path + ".tmp"
    with open(tmp, "w") as f:
        json.dump(obj, f, indent=1, default=lambda o: o.tolist() if isinstance(o, np.ndarray) else float(o))
    os.replace(tmp, path)


def jload(path, default=None):
    if os.path.exists(path):
        with open(path) as f:
            return json.load(f)
    return default
