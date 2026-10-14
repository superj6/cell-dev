"""Lean scoring of the memory worlds on fresh paired lives (2026-10-10, finishing the interrupted t6 plan).

Every row runs on the SAME n lives: H.seeds(n, block), default block 100 x 512 (fresh_seeds(n, 43_000_000 +
10_000 * block)). Blocks used for tuning / exploration by this study: 110 (C5 tuning), 116 / 117 (reflex re-tune
screen / hill), 119 (exploration, sanity). Block 100-109 were never touched by any tuning.

Stages (resumable: per-life F and the ledger summary of every row are kept in scores8/<world>_b<block>_F.npz /
scores8/<world>_b<block>.json, and stored rows are not re-run):
  core   reflex@hollow3 frozen + in-world re-tune 'rt-mem' (memory/reflex_knobs_mem.json, when present);
         C1 privileged pursuit (= M1 dark_mode 0) on hollow3; C5 on ring4 with the tuned knobs (tuned/<w>_ring4.json,
         tuning block 110; the t5_tune start knobs when that world was never tuned); the eight do-less reflex
         variants of t6_score.py; memory ablation B (C5 idles while it believes the target dark).
  big    bigger tissue bodies without central computation: router@ring4 (frozen SPECK knobs), reflex@ring4
         (reflex@hollow3's knobs on ring4) -- is C5's ring4 advantage just the bigger footprint?
  extra  memory ablation A (C5 without the dark model: silence = absence, same knobs); M1 dark policies 1-3
         (privileged: extrapolate / hold / idle in the dark); C5 on hollow3 with the same knobs.
usage: t8_score.py world1,world2 [--stage core,extra] [--n 512] [--block 100] [--threads 1]"""
import argparse

from mcommon import *
from src.life import handbuilt as hb

ap = argparse.ArgumentParser()
ap.add_argument("worlds")
ap.add_argument("--stage", default="core,extra,big")
ap.add_argument("--n", type=int, default=512)
ap.add_argument("--block", type=int, default=100)
ap.add_argument("--threads", type=int, default=1)
ap.add_argument("--queue", default="", help="claim tag: run as one worker of a shared queue")
a = ap.parse_args()
assert a.block not in (110, 111, 112, 113, 114, 115, 116, 117, 118, 119), "block used for tuning / exploration"
OUT = os.path.join(HERE, "scores8")
os.makedirs(OUT, exist_ok=True)
TB = dict(tau_eff=0.3, dt=0.453, gain=0.962, min_align=0.367, tol=0.058, q_tap=0.112)  # harness C4 tuned (blink20)
STARTS = {"base1": dict(tau_eff=0.338, dt=0.529, gain=1.033, min_align=0.536, tol=0.06, q_tap=0.157),
          "pool_blink20": dict(tau_eff=0.3, dt=0.661, gain=1.803, min_align=0.496, tol=0.154, q_tap=0.232)}


def c5_x(wn):
    """Tuned C5 knobs if a tuning file exists (complete or partial), else t5_tune.py's start knobs."""
    p = os.path.join(HERE, f"tuned/{wn}_ring4.json")
    if os.path.exists(p):
        d = json.load(open(p))
        done = [t["knob"] for t in d["trace"]]
        return np.array(d["x"]), f"tuned/{wn}_ring4.json (block 110 x 128; knobs searched: {','.join(done)}; " \
                                 f"F_tune {d['F_tune']:+.3f} from start {d['F_start']:+.3f})"
    w = WORLDS[wn]
    x = c5_params(w, **STARTS.get(wn, TB), h=0.25, W=7.0, vel=1.0, tau_v=12.0, sig_p=1.0, vel_gain=0.5, gate=1.5)
    if world_rules(w)["v_t"] == 0.0:
        x = pset(C5, x, vel=0.0, vel_gain=0.0)
    return x, "t5_tune start knobs (never tuned in this world: harness C4-tuned knobs" + \
              (f" for {wn})" if wn in STARTS else " for blink20)")


def score(wn, stages):
    w = WORLDS[wn]
    sd = H.seeds(a.n, a.block)
    kw = dict(threads=a.threads)
    pj, pz = os.path.join(OUT, f"{wn}_b{a.block}.json"), os.path.join(OUT, f"{wn}_b{a.block}_F.npz")
    out = json.load(open(pj)) if os.path.exists(pj) else {}
    out.update(world=wn, n=a.n, block=a.block, seeds=f"fresh_seeds({a.n}, 43_000_000 + 10_000 * {a.block})",
               rules=world_rules(w))
    out.setdefault("rows", {})
    Fs = dict(np.load(pz)) if os.path.exists(pz) else {}
    Ds = {k[5:]: v for k, v in Fs.items() if k.startswith("dark:")}
    Cs = {k[4:]: v for k, v in Fs.items() if k.startswith("cap:")}

    def save():
        jdump(out, pj)
        np.savez(pz, **{k: v for k, v in Fs.items() if ":" not in k}, **{f"dark:{k}": v for k, v in Ds.items()},
                 **{f"cap:{k}": v for k, v in Cs.items()})

    def row(lab, fn, meta=None):
        if lab in Fs and lab in out["rows"] and len(Fs[lab]) == a.n:
            return
        r = fn()
        Fs[lab] = H.F(r)
        Ds[lab] = np.asarray(r.ledger[:, 21], dtype=np.float64)
        Cs[lab] = np.asarray(r["captures"], dtype=np.float64)
        s = summ(r)
        if hasattr(r, "diag"):
            s["diag_mean"] = r.diag.mean(0).tolist()
        if meta:
            s.update(meta)
        out["rows"][lab] = s
        print(f"[{wn}] {lab:46s} n {a.n:4d} F {s['F']:+7.2f} cap {s['captures']:6.1f} dark {s['dark_caps']:5.1f} "
              f"miss {s['misses']:5.1f} cpu {s.get('cpu_per_life', 0):.3f}", flush=True)
        save()

    kn_path = os.path.join(HERE, "reflex_knobs_mem.json")
    rt = json.load(open(kn_path)).get(wn, {}).get("rt-mem") if os.path.exists(kn_path) else None
    x, xsrc = c5_x(wn)
    out["c5_params"], out["c5_source"] = pdict(C5, x), xsrc
    bk = rt["knobs"] if rt else hb.SPECK_TUNED["reflex@hollow3"]
    if "core" in stages:
        row("reflex@hollow3 frozen", lambda: trun(H.reflex("hollow3"), w, sd, **kw))
        if rt:
            row("reflex@hollow3 rt-mem", lambda: trun(H.reflex("hollow3", rt["knobs"]), w, sd, **kw),
                dict(knobs=rt["knobs"], source=rt["source"]))
        row("priv C1 truth", lambda: crun(M1, H.params(M1, dark_mode=0.0), "hollow3", w, sd, **kw))
        row("C5 ring4", lambda: crun(C5, x, "ring4", w, sd, **kw), dict(params_source=xsrc))
        dl = {"reflex@hollow2 frozen": lambda: H.reflex("hollow2"),
              "reflex@hollow2 hollow3 knobs": lambda: H.reflex("hollow2", bk, name="reflex@hollow2 bk"),
              "reflex@ring2 frozen": lambda: H.reflex("ring2"),
              "clicker (2 cells)": lambda: hb.CLICKER,
              "hollow3 K.w0 0.75 (higher tap threshold)":
                  lambda: H.reflex("hollow3", dict(bk, **{"K.w0": 0.75}), name="k075"),
              "hollow3 C.g_r 0.5 (fewer centre pings)":
                  lambda: H.reflex("hollow3", dict(bk, **{"C.g_r": 0.5}), name="cg05"),
              "hollow3 C.t_ref 4 + K.t_ref 4 (fewer clicks)":
                  lambda: H.reflex("hollow3", dict(bk, **{"C.t_ref": 4.0, "K.t_ref": 4.0}), name="slow"),
              "hollow3 M.kappa 0.5 (weaker steering)":
                  lambda: H.reflex("hollow3", dict(bk, **{"M.kappa": 0.5}), name="mk05")}
        for lab, b in dl.items():
            row(f"do-less {lab}", lambda b=b: trun(b(), w, sd, **kw))
        if world_rules(w)["blink_on"] > 0:
            row("C5 ring4 abl B idle while believed dark", lambda: crun(C5, pset(C5, x, idle_dark=0.5), "ring4", w, sd,
                                                                         **kw))
    if "extra" in stages:
        if world_rules(w)["blink_on"] > 0:
            row("C5 ring4 abl A no dark model", lambda: crun(C5, pset(C5, x, blink_on=0.0, blink_off=0.0, dark_amp=0.0),
                                                             "ring4", w, sd, **kw))
            for mode, lab in ((1, "M1 extrapolate"), (2, "M1 hold"), (3, "M1 idle-in-dark")):
                row(f"priv {lab}", lambda mode=mode: crun(M1, H.params(M1, dark_mode=float(mode)), "hollow3", w, sd,
                                                          **kw))
        row("C5 hollow3", lambda: crun(C5, x, "hollow3", w, sd, **kw), dict(params_source=xsrc))
    if "big" in stages:  # bigger tissue bodies with no central computation (ring4 = C5's footprint)
        row("big router@ring4 frozen", lambda: trun(H.router("ring4"), w, sd, **kw))
        row("big reflex@ring4 (hollow3 knobs)", lambda: trun(H.reflex("ring4"), w, sd, **kw))
    save()


if a.queue:  # work queue shared by several worker processes: claim (world, stage) with O_EXCL files
    os.makedirs(os.path.join(OUT, "claims"), exist_ok=True)
    for st in a.stage.split(","):
        for wn in a.worlds.split(","):
            try:
                os.close(os.open(os.path.join(OUT, f"claims/{a.queue}_{st}_{wn}_b{a.block}"), os.O_CREAT | os.O_EXCL))
            except FileExistsError:
                continue
            score(wn, [st])
else:
    for wn in a.worlds.split(","):
        score(wn, a.stage.split(","))
