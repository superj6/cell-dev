"""Score one memory world on fresh SCORING lives (block 100; every body / controller on the SAME lives, paired).

  best reflex   the better, on these lives, of the frozen reflex@hollow3 and the reflex re-tuned in this world
                (memory/reflex_knobs_mem.json 'rt-mem'; screen block 116, hill block 117)
  do-less       quieter / smaller reflex variants (hollow2, ring2, the 2-cell clicker, higher tap threshold, fewer
                centre pings, slower clicks, weaker steering); the best of them minus the best reflex
  ceiling       C1 (privileged truth) and the M1 dark-policy decomposition (memory value given perfect sensing)
  info-matched  C5 tuned on ring4 (tuned/<world>_ring4.json, tuning block 110); the same knobs on hollow3, ring5
                (disk 5) and disk4x4 (the L4 disk: hidden planes are inert, cost only); hollow3 also with the harness's
                C4-on-hollow3 start knobs
  memory ablations (ring4, same lives): A no dark model (silence = absence; re-tuned q_tap/gain when
                tuned/<world>_ring4_nodark.json exists), B idle while it believes the target dark, V velocity off
Resumable: per-life F of every finished row is kept in scores/<world>_F.npz; scores/<world>.json is rewritten after
every row.  usage: t6_score.py world [--n 1024] [--n2 512] [--threads 1]"""
import argparse
from mcommon import *
from src.life import handbuilt as hb

ap = argparse.ArgumentParser()
ap.add_argument("world")
ap.add_argument("--n", type=int, default=1024)     # main rows
ap.add_argument("--n2", type=int, default=512)     # secondary rows (first n2 of the same lives)
ap.add_argument("--threads", type=int, default=THREADS)
ap.add_argument("--block", type=int, default=SCORE_BLOCKS[0])
a = ap.parse_args()
wn, n, n2, kw = a.world, a.n, a.n2, dict(threads=a.threads)
w = WORLDS[wn]
sd = H.seeds(n, a.block)
sd2 = sd[:n2]
os.makedirs(os.path.join(HERE, "scores"), exist_ok=True)
tag = "" if a.block == SCORE_BLOCKS[0] else f"_b{a.block}"
pj, pz = os.path.join(HERE, f"scores/{wn}{tag}.json"), os.path.join(HERE, f"scores/{wn}{tag}_F.npz")
out = json.load(open(pj)) if os.path.exists(pj) else {}
out.update(world=wn, n=n, n2=n2, seeds=f"fresh_seeds(n, 43_000_000 + 10_000 * {a.block})", rules=world_rules(w))
out.setdefault("rows", {})
Fs = dict(np.load(pz)) if os.path.exists(pz) else {}


def save():
    jdump(out, pj)
    np.savez(pz, **Fs)


def row(lab, fn, nn):
    """Run fn() (-> Lives) unless the row is already stored; record summary + per-life F."""
    if lab in Fs and lab in out["rows"] and len(Fs[lab]) == nn:
        return Fs[lab]
    r = fn()
    Fs[lab] = H.F(r)
    s = summ(r)
    if hasattr(r, "diag"):
        s["diag_mean"] = r.diag.mean(0).tolist()
    out["rows"][lab] = s
    print(f"[{wn}] {lab:44s} n {nn:5d} F {s['F']:+7.2f} cap {s['captures']:6.1f} dark {s['dark_caps']:5.1f} "
          f"miss {s['misses']:5.1f} cpu {s.get('cpu_per_life', 0):.3f}", flush=True)
    save()
    return Fs[lab]


def gap(lab, ref_lab):
    fa, fb = Fs[lab], Fs[ref_lab][:len(Fs[lab])]
    return pair(fa, fb)


# ---------------------------------------------------------------- reflex candidates and the best reflex
kn_path = os.path.join(HERE, "reflex_knobs_mem.json")
rt = json.load(open(kn_path)).get(wn, {}).get("rt-mem") if os.path.exists(kn_path) else None
cands = {"reflex@hollow3 frozen": None}
if rt:
    cands["reflex@hollow3 rt-mem"] = rt["knobs"]
else:
    print(f"[{wn}] WARNING: no in-world re-tuned reflex yet (memory/reflex_knobs_mem.json)", flush=True)
for lab, kn in cands.items():
    row(lab, lambda kn=kn: trun(H.reflex("hollow3", kn), w, sd, **kw), n)
best_lab = max(cands, key=lambda k: Fs[k].mean())
ref = Fs[best_lab]
out["best_reflex"] = dict(name=best_lab, F=float(ref.mean()), se=float(ref.std(ddof=1) / np.sqrt(n)),
                          knobs=cands[best_lab], cpu_per_life=out["rows"][best_lab].get("cpu_per_life"),
                          candidates={k: float(Fs[k].mean()) for k in cands},
                          rt_minus_frozen=gap("reflex@hollow3 rt-mem", "reflex@hollow3 frozen") if rt else None)
save()
print(f"[{wn}] BEST REFLEX {best_lab} F {ref.mean():+.3f}", flush=True)

# ---------------------------------------------------------------- privileged ceiling (+ memory decomposition)
for mode, lab in ((0, "C1 truth"), (1, "M1 extrapolate"), (2, "M1 hold"), (3, "M1 idle-in-dark")):
    row(f"priv {lab}", lambda mode=mode: crun(M1, H.params(M1, dark_mode=float(mode)), "hollow3", w, sd, **kw), n)
pv = {lab: dict(F=float(Fs[f"priv {lab}"].mean()), vs_best_reflex=gap(f"priv {lab}", best_lab))
      for lab in ("C1 truth", "M1 extrapolate", "M1 hold", "M1 idle-in-dark")}
pv["memory_value(extrapolate-idle)"] = pair(Fs["priv M1 extrapolate"], Fs["priv M1 idle-in-dark"])
pv["velocity_value(extrapolate-hold)"] = pair(Fs["priv M1 extrapolate"], Fs["priv M1 hold"])
pv["knowing_in_dark(truth-extrapolate)"] = pair(Fs["priv C1 truth"], Fs["priv M1 extrapolate"])
out["privileged"] = pv
save()

# ---------------------------------------------------------------- information-matched C5
tj = os.path.join(HERE, f"tuned/{wn}_ring4.json")
assert os.path.exists(tj), f"no tuned C5 for {wn}"
x = np.array(json.load(open(tj))["x"])
out["c5_params"] = pdict(C5, x)
row("C5 ring4 tuned", lambda: crun(C5, x, "ring4", w, sd, **kw), n)
# disk4x4 = ring4 + two inert hidden planes (61 x 2 cells): same actions, c_live cost only. Verified on n_chk lives.
n_chk = 64
row("C5 disk4x4 check", lambda: crun(C5, x, "disk4x4", w, sd[:n_chk], **kw), n_chk)
off = Fs["C5 ring4 tuned"][:n_chk] - Fs["C5 disk4x4 check"]
out["disk4x4_offset"] = dict(min=float(off.min()), max=float(off.max()), n=n_chk)
if off.max() - off.min() < 1e-6:
    Fs["C5 disk4x4 (ring4 - const)"] = Fs["C5 ring4 tuned"] - float(off.mean())
    out["rows"]["C5 disk4x4 (ring4 - const)"] = dict(F=float(Fs["C5 disk4x4 (ring4 - const)"].mean()), n=n,
                                                     derived=f"ring4 per-life F - {off.mean():.4f}",
                                                     cpu_per_life=out["rows"]["C5 ring4 tuned"].get("cpu_per_life"))
save()
row("C5 ring5 same knobs", lambda: crun(C5, x, "ring5", w, sd2, **kw), n2)
row("C5 hollow3 same knobs", lambda: crun(C5, x, "hollow3", w, sd2, **kw), n2)
TB = dict(tau_eff=0.3, dt=0.453, gain=0.962, min_align=0.367, tol=0.058, q_tap=0.112)
STARTS = {"base1": dict(tau_eff=0.338, dt=0.529, gain=1.033, min_align=0.536, tol=0.06, q_tap=0.157),
          "pool_blink20": dict(tau_eff=0.3, dt=0.661, gain=1.803, min_align=0.496, tol=0.154, q_tap=0.232)}
xh = pset(C5, x, **STARTS.get(wn, TB))
row("C5 hollow3 C4-hollow3 knobs", lambda: crun(C5, xh, "hollow3", w, sd2, **kw), n2)

# ---------------------------------------------------------------- do-less variants (first n2 lives)
bk = cands[best_lab] or hb.SPECK_TUNED["reflex@hollow3"]
dl = {"reflex@hollow2 frozen": lambda: H.reflex("hollow2"),
      "reflex@hollow2 best knobs": lambda: H.reflex("hollow2", bk, name="reflex@hollow2 bk"),
      "reflex@ring2 frozen": lambda: H.reflex("ring2"),
      "clicker (2 cells)": lambda: hb.CLICKER,
      "hollow3 K.w0 0.75 (higher tap threshold)": lambda: H.reflex("hollow3", dict(bk, **{"K.w0": 0.75}), name="k075"),
      "hollow3 C.g_r 0.5 (fewer centre pings)": lambda: H.reflex("hollow3", dict(bk, **{"C.g_r": 0.5}), name="cg05"),
      "hollow3 C.t_ref 4 + K.t_ref 4 (fewer clicks)": lambda: H.reflex("hollow3", dict(bk, **{"C.t_ref": 4.0, "K.t_ref": 4.0}), name="slow"),
      "hollow3 M.kappa 0.5 (weaker steering)": lambda: H.reflex("hollow3", dict(bk, **{"M.kappa": 0.5}), name="mk05")}
out["do_less_rows"] = {}
for lab, b in dl.items():
    row(f"do-less {lab}", lambda b=b: trun(b(), w, sd2, **kw), n2)
    out["do_less_rows"][lab] = gap(f"do-less {lab}", best_lab)
dbest = max(dl, key=lambda k: Fs[f"do-less {k}"].mean())
out["do_less"] = dict(best=dbest, gap=gap(f"do-less {dbest}", best_lab))
save()

# ---------------------------------------------------------------- memory ablations (ring4, first n2 lives)
abl = {}
r_ = world_rules(w)
if r_["blink_on"] > 0:
    tn = os.path.join(HERE, f"tuned/{wn}_ring4_nodark.json")
    xa = np.array(json.load(open(tn))["x"]) if os.path.exists(tn) else pset(C5, x, blink_on=0.0, blink_off=0.0, dark_amp=0.0)
    abl["A no dark model (silence = absence)" + (" re-tuned" if os.path.exists(tn) else "")] = xa
    abl["B idle while it believes the target dark"] = pset(C5, x, idle_dark=0.5)
if r_["v_t"] > 0 and x[C5_NAMES.index("vel")] > 0 and x[C5_NAMES.index("vel_gain")] > 0:
    abl["V velocity memory off"] = pset(C5, x, vel_gain=0.0)
out["ablations"] = {}
for lab, p in abl.items():
    row(f"C5 ring4 ablation {lab}", lambda p=p: crun(C5, p, "ring4", w, sd2, **kw), n2)
    out["ablations"][lab] = dict(full_minus_ablation=pair(Fs["C5 ring4 tuned"][:n2], Fs[f"C5 ring4 ablation {lab}"]),
                                 F=float(Fs[f"C5 ring4 ablation {lab}"].mean()),
                                 ablation_vs_best_reflex=gap(f"C5 ring4 ablation {lab}", best_lab))
save()

# ---------------------------------------------------------------- gaps of every info-matched row; the best
for lab in list(out["rows"]):
    if lab.startswith(("C5 ", "do-less", "priv", "reflex")) and lab in Fs and lab != best_lab:
        out["rows"][lab]["vs_best_reflex"] = gap(lab, best_lab)
info_rows = [k for k in out["rows"] if k.startswith("C5 ") and "ablation" not in k and "check" not in k]
# choose the footprint on the first n2 lives (every row has them), report its gap on all its lives
best_info = max(info_rows, key=lambda k: Fs[k][:n2].mean())
g = out["rows"][best_info]["vs_best_reflex"]
cpu_c = out["rows"][best_info].get("cpu_per_life") or out["rows"]["C5 ring4 tuned"]["cpu_per_life"]
cpu_r = out["rows"][best_lab].get("cpu_per_life")
out["best_info"] = dict(name=best_info, gap=g, cpu_per_life_controller=cpu_c, cpu_per_life_reflex=cpu_r,
                        z2_per_life=(g["mean"] / g["sd"]) ** 2,
                        sel_info_per_cpu_s_tissue=(g["mean"] / g["sd"]) ** 2 / cpu_r,
                        sel_info_per_cpu_s_controller=(g["mean"] / g["sd"]) ** 2 / cpu_c)
save()
print(f"[{wn}] best info {best_info} gap {fmt(g)}; ceiling {fmt(pv['C1 truth']['vs_best_reflex'])}; "
      f"do-less {dbest} {fmt(out['do_less']['gap'])}", flush=True)
print(f"[{wn}] saved", flush=True)
