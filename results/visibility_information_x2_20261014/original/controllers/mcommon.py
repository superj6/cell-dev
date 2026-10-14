"""Memory-family study: shared definitions (worlds, seed blocks, controller parameters, timing).

Run with cwd /home/jgon/project/ml/cell-dev and PYTHONPATH=/home/jgon/project/ml/cell-dev:<harness>:<this dir>.
Seed blocks (fresh_seeds(n, 43_000_000 + 10_000 * block)): 100-101 scoring (every body / controller on the SAME lives),
110-115 controller tuning, 116-117 reflex re-tune (screen / hill), 118 C3 ES, 119 spare. Tuning never touches 100-101.
"""
from __future__ import annotations

import json
import os
import resource
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

LIB = os.path.join(HERE, "mk_fast.so")
THREADS = int(os.environ.get("MEM_THREADS", "2"))
SCORE_BLOCKS = (100, 101)
TUNE_BLOCKS = (110, 111, 112, 113, 114, 115)
RT_SCREEN, RT_HILL = 116, 117
C3_BLOCK = 118

M1, C5 = 1101, 1102
FAST = dict(d0=0.5, d_min=0.25)
WS = H.WorldSpec
WORLDS = {w.name: w for w in (
    WS("base1"),                                                                       # control: no blink
    WS("blink20_10", x=dict(blink_on=20.0, blink_off=10.0)),
    WS("blink20", x=dict(blink_on=20.0, blink_off=20.0)),                              # = harness blink20 (20/20)
    WS("blink10_30", x=dict(blink_on=10.0, blink_off=30.0)),
    WS("blink5_5", x=dict(blink_on=5.0, blink_off=5.0)),
    WS("flash5_dim25", x=dict(blink_on=5.0, blink_off=-1.0, dim_flag=777.0, dark_amp=0.25)),
    WS("pool_blink20", over=dict(FAST, sigma=0.4, lam_s=4.0), x=dict(blink_on=20.0, blink_off=20.0)),
    WS("still_blink5_20", over=dict(v_t=0.0), x=dict(blink_on=5.0, blink_off=20.0)),
    WS("still_blink10_10", over=dict(v_t=0.0), x=dict(blink_on=10.0, blink_off=10.0)),
)}
MEMORY_WORLDS = [w for w in WORLDS if w != "base1"]

# ------------------------------------------------------------------------------------------- controller params
M1_NAMES = H.CONTROLLERS[H.C1].names + ("dark_mode", "dark_taps")
H.register(H.CtlSpec(M1, "M1 privileged pursuit, dark policy", True, M1_NAMES,
                     H.CONTROLLERS[H.C1].default + (0.0, 2.0)))
C5_NAMES = H.C4_NAMES + ("dark_amp", "vel", "tau_turn", "tau_v", "conf_v", "idle_dark", "sig_p", "vel_gain", "gate")
_c4 = H.CONTROLLERS[H.C4]
H.register(H.CtlSpec(C5, "C5 Bayes memory tracker", False, C5_NAMES,
                     _c4.default + (0.0, 0.0, 20.0, 8.0, 0.5, 0.0, 0.7, 1.0, 1.5),
                     _c4.lo + (0.0, 0.0, 1.0, 1.0, 0.05, 0.0, 0.1, 0.0, 0.5),
                     _c4.hi + (1.0, 1.0, 400.0, 40.0, 0.95, 1.0, 3.0, 1.5, 3.0)))


def world_rules(world) -> dict:
    """The world's fixed RULES (same in every life of the world): what an information-matched model may know."""
    ws = H.world_spec(world)
    w = spec.world(ws.preset, **ws.over)
    r = {k: float(getattr(w, k)) for k in ("sigma", "lam_s", "lam_bg", "v_t", "R_min", "R_max", "t_resp", "rho_c",
                                            "tau_turn", "d0", "d_min")}
    r["blink_on"] = float(ws.x.get("blink_on", 0.0))
    r["blink_off"] = float(ws.x.get("blink_off", 0.0))
    r["dark_amp"] = float(ws.x.get("dark_amp", 0.0)) if ws.x.get("dim_flag", 0.0) == 777.0 else 0.0
    return r


def c5_params(world, **kw) -> np.ndarray:
    """C5 parameters: world rules filled in, then overrides (C4's tuned-style defaults for the rest)."""
    r = world_rules(world)
    p = H.params(C5)
    names = C5_NAMES
    for k in ("sigma", "lam_s", "lam_bg", "v_t", "R_min", "R_max", "t_resp", "rho_c", "blink_on", "blink_off",
              "dark_amp", "tau_turn"):
        p[names.index(k)] = r[k]
    tt = r["tau_turn"]
    p[names.index("tau_eff")] = min(tt, 5.0) if tt > 0 else 5.0
    if p[names.index("tau_turn")] <= 0:
        p[names.index("tau_turn")] = 1e9
    for k, v in kw.items():
        p[names.index(k)] = v
    return p


def pset(cid, p: np.ndarray, **kw) -> np.ndarray:
    p = np.array(p, dtype=np.float64).copy()
    names = H.CONTROLLERS[cid].names
    for k, v in kw.items():
        p[names.index(k)] = v
    return p


def pdict(cid, p) -> dict:
    return {n: float(v) for n, v in zip(H.CONTROLLERS[cid].names, p)}


# ------------------------------------------------------------------------------------------- runs with CPU timing
def cpu_now() -> float:
    r = resource.getrusage(resource.RUSAGE_SELF)
    return r.ru_utime + r.ru_stime


def timed(fn, *a, **kw):
    c0, w0 = cpu_now(), time.time()
    out = fn(*a, **kw)
    return out, cpu_now() - c0, time.time() - w0


def crun(cid, p, fp, world, sd, **kw):
    kw.setdefault("threads", THREADS)
    kw.setdefault("lib", LIB)
    res, cpu, wall = timed(H.ctl_run, cid, p, H.footprint(fp) if isinstance(fp, str) else fp, world, sd, **kw)
    res.cpu_per_life = cpu / len(sd)
    return res


def trun(body, world, sd, **kw):
    kw.setdefault("threads", THREADS)
    kw.setdefault("lib", LIB)
    res, cpu, wall = timed(H.tissue_run, body, world, sd, **kw)
    res.cpu_per_life = cpu / len(sd)
    return res


def score_seeds(n: int = 512):
    """The scoring lives: the first n of block 100, then block 101."""
    if n <= 4096:
        return H.seeds(n, SCORE_BLOCKS[0])
    return H.seeds(4096, SCORE_BLOCKS[0]) + H.seeds(n - 4096, SCORE_BLOCKS[1])


def summ(res) -> dict:
    s = H.summary(res)
    s["dark_caps"] = float(res.ledger[:, 21].mean())
    if hasattr(res, "cpu_per_life"):
        s["cpu_per_life"] = float(res.cpu_per_life)
    return s


def pair(a, b) -> dict:
    """mean +- SE of the per-life F difference, its per-life SD, and z."""
    fa, fb = H.F(a) if hasattr(a, "ledger") else np.asarray(a), H.F(b) if hasattr(b, "ledger") else np.asarray(b)
    d = fa - fb
    n = len(d)
    sd = float(d.std(ddof=1))
    return dict(mean=float(d.mean()), se=sd / np.sqrt(n), sd=sd, z=float(d.mean() / (sd / np.sqrt(n))) if sd > 0 else 0.0,
                n=n)


def fmt(d: dict) -> str:
    return f"{d['mean']:+.2f} +- {d['se']:.2f}"


def jdump(obj, path):
    def conv(o):
        if isinstance(o, (np.floating, np.integer)):
            return o.item()
        if isinstance(o, np.ndarray):
            return o.tolist()
        raise TypeError(type(o))
    json.dump(obj, open(path, "w"), indent=1, default=conv)
