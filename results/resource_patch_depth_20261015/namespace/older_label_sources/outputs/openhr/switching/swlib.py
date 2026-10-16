"""SWITCHING family on the central-controller harness (scratch; never edits the repo).

Worlds (all d0 1 like the prior study unless the name ends in 'f'):
  flip_mid    every life flips at t_flip ~ U[256, 768] (the harness's WORLDS['flip_mid'] draw)
  flip_mix    50/50 (per-life draw from the life seed): unflipped, or flipped at U[256, 768] (same t_flip draw)
  flip_from0  every life flipped from t0 (t_flip = 2^-20)
  flip_cue    50/50: normal lives (lam_bg 0.05), or flipped-from-t0 lives with lam_bg 0.2 (headroom/v6_flipcue.py)
  flip_family 50% unflipped, 25% from t0, 25% midlife (headroom/v4_flip.py's family)
  cue_only    lam_bg 0.2 in 50% of lives but nobody flips (control for the cue controller)
Membership is a per-life draw keyed by (life seed, 'flipmix'), so every body/controller sees the same lives.

Controllers (sw_ctl.c, built into sw_fast.so):
  1001 SW   two-hypothesis Bayes grid tracker (mode 0 no-switch twin, 1 Bayes detection, 2 privileged flip bit)
  1002 C0M  central reflex with selectable motor mapping (map 1 = mirrored, the flipped-law reflex)
"""
from __future__ import annotations

import json
import math
import os
import sys
from dataclasses import dataclass, field

import numpy as np

HERE = os.path.dirname(os.path.abspath(__file__))
HARN = os.path.join(os.path.dirname(HERE), "harness")
REPO = "/home/jgon/project/ml/cell-dev"
for p in (REPO, HARN, HERE):
    if p not in sys.path:
        sys.path.insert(0, p)
import harness as H  # noqa: E402
from src.life import analysis, build, spec  # noqa: E402
from src.life import handbuilt as hb  # noqa: E402

LIB = os.path.join(HERE, "sw2_fast.so")          # one-way flip worlds (make_swkernel.py)
LIB_TELE = os.path.join(HERE, "sw_tele_fast.so")  # + telegraph motor law (make_swkernel.py --tele)
# sw3_fast.so: one-way worlds, sw_ctl.c with mode 3 (clock switch). Modes 0-2 are bitwise those of sw2_fast.so
# (logs/check_sw3.log); kept as a separate file so the library that produced the scores is never replaced.
LIB3 = os.path.join(HERE, "sw3_fast.so")
SW, C0M, CU = 1001, 1002, 1003
THREADS = int(os.environ.get("SW_THREADS", "2"))

SW_NAMES = ("sigma", "lam_s", "lbg0", "lbg1", "v_t", "tau_eff", "R_min", "R_max", "t_resp", "rho_c",
            "p0", "p_mid", "fa", "fb", "mode", "dt", "h", "W", "blur_every", "gain", "kmax",
            "min_align", "tol", "q_tap", "q_switch", "hyst", "q_latch", "haz_mult", "haz_floor", "steer_min", "haz_back", "act_style")
SW_DEF = (0.6, 2.0, 0.05, 0.05, 0.1, 0.402, 2.0, 6.0, 50.0, 1.0,
          0.0, 0.0, 256.0, 768.0, 1.0, 0.531, 0.25, 6.5, 2.0, 1.082, 1.0,
          0.561, 0.146, 0.282, 0.5, 0.0, 2.0, 1.0, 0.0, 0.0, 0.0, 0.0)
SW_LO = (0.2, 0.1, 0.001, 0.001, 0.0, 0.05, 0.0, 0.5, 5.0, 0.3,
         0.0, 0.0, 0.0, 0.0, 0.0, 0.2, 0.1, 4.0, 0.25, 0.1, 0.1,
         0.0, 0.0, 0.02, 0.05, 0.0, 0.3, 0.01, 0.0, 0.0, 0.0, 0.0)
SW_HI = (2.0, 8.0, 0.5, 0.5, 1.0, 50.0, 6.0, 12.0, 400.0, 1.5,
         1.0, 1.0, 1024.0, 1024.0, 2.0, 1.0, 0.4, 10.0, 4.0, 2.0, 1.0,
         0.95, 1.0, 0.95, 0.99, 0.45, 2.0, 20.0, 0.05, 0.5, 0.1, 1.0)
H.register(H.CtlSpec(SW, "SW two-hypothesis switch tracker", False, SW_NAMES, SW_DEF, SW_LO, SW_HI))
# 1003 CU: reflex + CUSUM law detector (cu_ctl.c)
CU_NAMES = ("a", "b", "kdrift", "h", "tw", "dmax", "two_way", "t_min", "t_max", "refr_tap", "refr_m", "dt_sample",
            "start_map", "dmin_move", "kappa_m")
CU_DEF = (1.0, 1.0, 0.1, 5.0, 3.0, 2.5, 0.0, 0.0, 1e9, 4.0, 0.5, 0.25, 0.0, 0.05, 1.0)
CU_LO = (0.0, 0.0, 0.0, 0.2, 0.5, 0.5, 0.0, 0.0, 0.0, 0.5, 0.0, 0.1, 0.0, 0.0, 0.05)
CU_HI = (6.0, 6.0, 3.0, 40.0, 12.0, 8.0, 1.0, 1024.0, 1e9, 8.0, 4.0, 1.0, 1.0, 1.0, 1.0)
H.register(H.CtlSpec(CU, "CU reflex + CUSUM law detector", False, CU_NAMES, CU_DEF, CU_LO, CU_HI))
# world rules a CU may use (fixed across a world's lives): the flip window, one-way vs two-way, the start law
CU_RULES = {
    "flip_mid": dict(two_way=0.0, t_min=256.0), "flip_mix": dict(two_way=0.0, t_min=256.0),
    "flip_mixf": dict(two_way=0.0, t_min=256.0), "flip_family": dict(two_way=0.0, t_min=0.0),
    "flip_from0": dict(two_way=0.0, t_min=1e9, start_map=1.0), "flip_tele200": dict(two_way=1.0, t_min=0.0),
    "flip_tele100": dict(two_way=1.0, t_min=0.0), "base1": dict(two_way=0.0, t_min=1e9),
}


def cu_params(wname: str, **kw) -> np.ndarray:
    ws = H.world_spec(world(wname))
    p = np.array(CU_DEF, dtype=np.float64)
    for k, v in dict(CU_RULES.get(ws.name, {}), **kw).items():
        p[CU_NAMES.index(k)] = v
    return p


def cu_idx(*names):
    return [CU_NAMES.index(n) for n in names]


H.register(H.CtlSpec(C0M, "C0M central reflex (mapping)", False,
                     ("kappa_m", "refr_m", "kappa_tap", "refr_tap", "map", "motors"),
                     (1.0, 0.5, 1.0, 4.0, 0.0, 1.0), (0.05, 0.0, 0.6, 0.5, 0.0, 0.0), (1.0, 4.0, 1.0, 8.0, 1.0, 1.0)))


# ----------------------------------------------------------------------------------------------- worlds
@dataclass(frozen=True)
class MixWorld(H.WorldSpec):
    """Per-life mixture: kind 'none' (no flip), 'from0' (flip at t0 + 2^-20) or 'mid' (t_flip ~ U[lo, hi] drawn as
    the harness's WORLDS draws do). cue: repo-key overrides applied in flipped lives (or in 'cue' lives of cue_only)."""
    p_none: float = 0.0
    p_from0: float = 0.0
    mid: tuple = (256.0, 768.0)
    cue: dict = field(default_factory=dict)
    cue_without_flip: bool = False  # cue_only control: lives drawn as 'flipped' get the cue but no flip


_KEY_IDX: dict = {}


def key_index(key: str) -> int:
    if key not in _KEY_IDX:
        b = spec.world("catch_speck_l4")
        v0 = H.KERNEL.pack_world(b)
        v1 = H.KERNEL.pack_world(spec.world("catch_speck_l4", **{key: float(getattr(b, key)) + 0.123}))
        d = np.flatnonzero(v0 != v1)
        assert len(d) == 1, (key, d)
        _KEY_IDX[key] = int(d[0])
    return _KEY_IDX[key]


def membership(w, seed_rows) -> tuple[np.ndarray, np.ndarray]:
    """(kind per life: 'none' / 'from0' / 'mid', t_flip relative to t0: 0 = never)."""
    ws = H.world_spec(w)
    sd = build._seeds(seed_rows)
    n = len(sd)
    if not isinstance(ws, MixWorld):
        if "t_flip" in ws.draws:
            lo, hi = ws.draws["t_flip"]
            return np.array(["mid"] * n), np.array([H.life_draw(int(s[0]), "t_flip", lo, hi) for s in sd])
        tf = float(ws.x.get("t_flip", 0.0))
        kind = "tele" if tf < 0 else ("none" if tf == 0 else ("from0" if tf < 1e-3 else "mid"))
        return np.array([kind] * n), np.full(n, tf)
    kinds, tf = [], []
    for s in sd:
        u = H.life_draw(int(s[0]), "flipmix", 0.0, 1.0)
        if u < ws.p_none:
            kinds.append("none"); tf.append(0.0)
        elif u < ws.p_none + ws.p_from0:
            kinds.append("from0"); tf.append(2.0 ** -20)
        else:
            kinds.append("mid"); tf.append(H.life_draw(int(s[0]), "t_flip", *ws.mid))
    return np.array(kinds), np.array(tf)


_orig_world_vectors = H.world_vectors


def world_vectors(w, seed_rows, flags: int = 0):
    out, base = _orig_world_vectors(w, seed_rows, flags)
    ws = H.world_spec(w)
    if isinstance(ws, MixWorld):
        kinds, tf = membership(ws, seed_rows)
        flipped = kinds != "none"
        out[:, H.XSLOT["t_flip"]] = 0.0 if ws.cue_without_flip else tf
        for k, v in ws.cue.items():
            out[flipped, key_index(k)] = v
    return np.ascontiguousarray(out), base


H.world_vectors = world_vectors  # ctl_run / tissue_run look it up as a module global

FAST = dict(d0=0.5, d_min=0.25)
CUE = dict(lam_bg=0.2)
WORLDS = {
    "flip_mid": H.WORLDS["flip_mid"],
    "flip_mix": MixWorld("flip_mix", p_none=0.5),
    "flip_from0": H.WorldSpec("flip_from0", x=dict(t_flip=2.0 ** -20)),
    "flip_cue": MixWorld("flip_cue", p_none=0.5, p_from0=0.5, cue=dict(CUE)),
    "flip_family": MixWorld("flip_family", p_none=0.5, p_from0=0.25),
    "cue_only": MixWorld("cue_only", p_none=0.5, p_from0=0.5, cue=dict(CUE), cue_without_flip=True),
    "flip_mixf": MixWorld("flip_mixf", over=dict(FAST), p_none=0.5),
    "base1": H.WORLDS["base1"],
    # telegraph motor law (sw_tele_fast.so): switches at Poisson times, mean dwell 200 / 100, stationary start
    "flip_tele200": H.WorldSpec("flip_tele200", x=dict(t_flip=-200.0)),
    "flip_tele100": H.WorldSpec("flip_tele100", x=dict(t_flip=-100.0)),
}
# the per-world flip prior (fixed world rules, never per-life state): p0, p_mid, (fa, fb), lbg under 'flipped'
PRIORS = {
    "flip_mid": dict(p0=0.0, p_mid=1.0, lbg1=0.05),
    "flip_mix": dict(p0=0.0, p_mid=0.5, lbg1=0.05),
    "flip_mixf": dict(p0=0.0, p_mid=0.5, lbg1=0.05),
    "flip_from0": dict(p0=1.0, p_mid=0.0, lbg1=0.05),
    "flip_cue": dict(p0=0.5, p_mid=0.0, lbg1=0.2),
    "flip_family": dict(p0=1.0 / 3.0, p_mid=0.5, lbg1=0.05),  # P(from0) = 0.25; given not from0, P(mid) = 1/3...
    "cue_only": dict(p0=0.5, p_mid=0.0, lbg1=0.2),
    "base1": dict(p0=0.0, p_mid=0.0, lbg1=0.05),
}
# flip_family: P(from0) = 0.25, so p0 = 0.25; given not from0 (prob 0.75), a midlife flip has prob 0.25 / 0.75 = 1/3
PRIORS["flip_family"] = dict(p0=0.25, p_mid=1.0 / 3.0, lbg1=0.05)
PRIORS["flip_tele200"] = dict(p0=0.5, p_mid=0.0, lbg1=0.05, haz_floor=1 / 200.0, haz_back=1 / 200.0, q_latch=2.0)
PRIORS["flip_tele100"] = dict(p0=0.5, p_mid=0.0, lbg1=0.05, haz_floor=1 / 100.0, haz_back=1 / 100.0, q_latch=2.0)


def world(name):
    return WORLDS[name] if isinstance(name, str) else name


def sw_params(wname: str, mode: int = 1, **kw) -> np.ndarray:
    """SW parameters: the world's fixed rules from its spec, the per-world flip prior, the C4 flip_mid-tuned knobs."""
    ws = H.world_spec(world(wname))
    w = spec.world(ws.preset, **ws.over)
    p = np.array(SW_DEF, dtype=np.float64)
    nm = SW_NAMES
    for k in ("sigma", "lam_s", "v_t", "R_min", "R_max", "t_resp", "rho_c"):
        p[nm.index(k)] = float(getattr(w, k))
    p[nm.index("lbg0")] = float(w.lam_bg)
    pr = PRIORS.get(ws.name, dict(p0=0.0, p_mid=0.0, lbg1=float(w.lam_bg)))
    p[nm.index("p0")] = pr["p0"]
    p[nm.index("p_mid")] = pr["p_mid"]
    p[nm.index("lbg1")] = pr["lbg1"]
    p[nm.index("mode")] = mode
    for k, v in kw.items():
        p[nm.index(k)] = v
    for k in ("haz_floor", "haz_back", "q_latch"):  # world rules of the telegraph worlds win over tuned knobs
        if k in pr:
            p[nm.index(k)] = pr[k]
    return p


def lib_for(wname) -> str:
    ws = H.world_spec(world(wname))
    return LIB_TELE if float(ws.x.get("t_flip", 0.0)) < 0 else LIB


def idx(*names):
    return [SW_NAMES.index(n) for n in names]


# ----------------------------------------------------------------------------------------------- runs
def seeds(n: int, block: int, first: int = 0):
    assert 140 <= block <= 159 or os.environ.get("SW_ANY_BLOCK"), "this study owns blocks 140-159 (SW_ANY_BLOCK=1 overrides)"
    return H.seeds(n, block, first)


def run_sw(p, wname, sd, fp="hollow3", threads=THREADS, **kw):
    return H.ctl_run(SW, p, H.footprint(fp), world(wname), sd, threads=threads, lib=lib_for(wname), privileged=False, **kw)


def run_sw_priv(p, wname, sd, fp="hollow3", threads=THREADS, **kw):
    p = np.array(p, dtype=np.float64).copy()
    p[SW_NAMES.index("mode")] = 2
    return H.ctl_run(SW, p, H.footprint(fp), world(wname), sd, threads=threads, lib=lib_for(wname), privileged=True, **kw)


def run_sw_clock(p, wname, sd, fp="hollow3", threads=THREADS, **kw):
    """SW mode 3: the same tracker, switching its law by the clock at t - t0 = (fa + fb) / 2 (no sensing)."""
    p = np.array(p, dtype=np.float64).copy()
    p[SW_NAMES.index("mode")] = 3
    assert lib_for(wname) == LIB, "the clock switch is built for one-way worlds only"
    return H.ctl_run(SW, p, H.footprint(fp), world(wname), sd, threads=threads, lib=LIB3, privileged=False, **kw)


def run_ctl(cid, p, wname, sd, fp="hollow3", threads=THREADS, **kw):
    return H.ctl_run(cid, p, H.footprint(fp), world(wname), sd, threads=threads, lib=lib_for(wname), **kw)


def run_tissue(org, wname, sd, threads=THREADS, **kw):
    return H.tissue_run(org, world(wname), sd, threads=threads, lib=lib_for(wname), **kw)


def Fv(r):
    return np.asarray(r["F"], dtype=np.float64)


def paired(a, b, mask=None):
    fa = Fv(a) if hasattr(a, "ledger") else np.asarray(a)
    fb = Fv(b) if hasattr(b, "ledger") else np.asarray(b)
    if mask is not None:
        fa, fb = fa[mask], fb[mask]
    d = fa - fb
    n = len(d)
    m = float(d.mean())
    sd_ = float(d.std(ddof=1)) if n > 1 else 0.0
    se = sd_ / math.sqrt(n) if n > 1 else 0.0
    return dict(mean=m, se=se, sd=sd_, z=m / se if se > 0 else 0.0, n=n)


def pf(d):
    return f"{d['mean']:+.2f} +- {d['se']:.2f}"


def stats(r, mask=None):
    sl = slice(None) if mask is None else mask
    out = {k: float(np.asarray(r[k])[sl].mean()) for k in ("F", "captures", "misses", "clicks", "spikes", "cost")}
    out["late_caps"] = float(r.ledger[sl, 22].mean())
    return out


def dump(obj, path):
    def conv(o):
        if isinstance(o, (np.floating,)):
            return float(o)
        if isinstance(o, (np.integer,)):
            return int(o)
        if isinstance(o, np.ndarray):
            return o.tolist()
        raise TypeError(type(o))
    json.dump(obj, open(path, "w"), indent=1, default=conv)
