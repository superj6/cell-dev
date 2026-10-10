"""Score the SWITCHING worlds on fresh paired lives. It never tunes: it reads params/. It is also the re-score command:

    cd /home/jgon/project/ml/cell-dev
    PYTHONPATH=.:outputs/openhr/harness:outputs/openhr/switching .venv/bin/python \
        outputs/openhr/switching/score2.py --worlds flip_mid,flip_mix --block 158 --n 1024 --tag rescore

Every run of a world uses the SAME lives (common random numbers). Core runs use n lives, secondary runs the first n2.
  R   reflex candidates (tissue): frozen reflex@hollow3, every recorded harness re-tune for the world (none since the
      reboot) and this study's in-world re-tune (params/reflex_rt.json). Best = max mean F on these lives.
  C1  privileged pursuit (reads the truth): the ceiling.
  SW0 / SW1 / SW2: the two-hypothesis Bayes grid tracker (sw_ctl.c) with no switch / the Bayes law detector /
      the privileged law (reads only the true motor law), on the best footprint (--fp, chosen on tuning lives) and
      hollow3. SW1 is the information-matched controller of record. SW3 (secondary, flip_mid / flip_mix): the same
      tracker switching its law by the CLOCK at t - t0 = 512 (no sensing; sw3_fast.so), to separate sensed switching
      from a blind schedule.
  reflex-style (the act rule is C0's reflex, only the motor MAPPING changes; isolates switching from tracking):
      C0 (= S0: never switches), S1 (Bayes detector), S2 (privileged law), CU1 (CUSUM detector, cu_ctl.c),
      CUclk (clock switch at t - t0 = 512, no sensing), C0M map1 (always mirrored).
  D   do-less variants (secondary): reflex@hollow2 / @ring2 (frozen), the best reflex with fewer taps (C.g_r 0.5 /
      0.25) or weaker / sparser strokes (M.kappa 0.25 / M.w0 0.5), the null controller, tap-only and quiet-tap C0.
  X   references (secondary; --skip-x drops them): C4 (flip_mid knobs), SW1 flat hazard (no timing window), frozen
      reflex@ring4.
The record (results.json) is produced by score_all.sh.
Writes data/<world>_<tag>.npz (per-life F of every run, membership, seeds, diag of detector runs) and
data/<world>_<tag>.json, both rewritten after every run."""
import argparse, json, os, time
from swlib import *

ap = argparse.ArgumentParser()
ap.add_argument("--worlds", default="flip_mix,flip_mid,flip_from0,flip_tele200")
ap.add_argument("--block", type=int, default=None, help="one block for every world (default: per-world blocks)")
ap.add_argument("--n", type=int, default=1024)
ap.add_argument("--n2", type=int, default=512, help="lives for the secondary runs")
ap.add_argument("--tag", default="score")
ap.add_argument("--fp", default=None, help="best footprint for SW (default: params/best_fp.json)")
ap.add_argument("--knobs-dir", default=None, help="directory of the tuned params (default params/)")
ap.add_argument("--core-only", action="store_true")
ap.add_argument("--skip-x", action="store_true", help="skip the X reference runs (C4, SW1 flat hazard, reflex@ring4)")
a = ap.parse_args()

BLOCKS = dict(flip_mid=150, flip_mix=151, flip_from0=152, flip_cue=153, flip_family=154, cue_only=155,
              flip_tele200=156, flip_tele100=157)
KINDS = ("none", "from0", "mid", "tele")
CLOCK_WORLDS = ("flip_mid", "flip_mix")  # one-way midlife-window worlds: SW3 = the tracker with a clock switch at 512
PD = a.knobs_dir or f"{HERE}/params"
FP = a.fp or json.load(open(f"{PD}/best_fp.json"))["fp"]


def sw_knobs(fp):
    p = f"{PD}/sw_flip_mix_{fp}.json"
    if not os.path.exists(p):
        p = f"{PD}/sw_flip_mix_hollow3.json"
    return json.load(open(p))["knobs"], p


def cu_knobs(wn):
    two = CU_RULES.get(wn, {}).get("two_way", 0.0) > 0
    p = f"{PD}/cu_{'flip_tele200' if two else 'flip_mix'}.json"
    return json.load(open(p))["knobs"], p


def timed(fn, *args, **kw):
    c0, t0 = time.process_time(), time.time()
    r = fn(*args, **kw)
    return r, time.process_time() - c0, time.time() - t0


# detector diagnostics: (first switch, time in flipped mapping, last switch, final state flipped) columns per type
DIAG = {"SW": dict(first=5, tflip=6, last=10, final=lambda d: d[:, 11] > 0.5, early=12, late_norm=14, changes=8),
        "CU": dict(first=5, tflip=6, last=11, final=lambda d: d[:, 8] > 0.5, early=12, late_norm=14, changes=7)}


def det_diag(typ, dg, masks, tflip):
    c = DIAG[typ]
    out = {}
    fin = c["final"](dg)
    for k, mm in masks.items():
        if not mm.any():
            continue
        e = dict(n=int(mm.sum()), time_flipped=float(dg[mm, c["tflip"]].mean()),
                 frac_ever_switched=float((dg[mm, c["first"]] >= 0).mean()),
                 frac_flipped_gt10=float((dg[mm, c["tflip"]] > 10).mean()),
                 frac_flipped_gt50=float((dg[mm, c["tflip"]] > 50).mean()),
                 law_changes=float(dg[mm, c["changes"]].mean()), frac_final_flipped=float(fin[mm].mean()))
        if k == "mid":
            tf = tflip[mm]
            last = dg[mm, c["last"]]
            ok = fin[mm] & (last >= 0)
            dl = np.maximum(last[ok] - tf[ok], 0.0)
            e["frac_detected_by_end"] = float(ok.mean())
            e["detect_delay_median"] = float(np.median(dl)) if ok.any() else None
            e["detect_delay_q90"] = float(np.quantile(dl, 0.9)) if ok.any() else None
            first = dg[mm, c["first"]]
            e["frac_switched_before_flip"] = float(((first >= 0) & (first < tf)).mean())
            e["time_flipped_before_256"] = float(dg[mm, c["early"]].mean())
            e["time_normal_after_768"] = float(dg[mm, c["late_norm"]].mean())
        out[k] = e
    return out


def main():
    rt_prior = H.retuned_reflex_knobs()
    pr = f"{PD}/reflex_rt.json"
    rt_mine = json.load(open(pr)) if os.path.exists(pr) else {}
    os.makedirs(f"{HERE}/data", exist_ok=True)
    for wn in a.worlds.split(","):
        blk = a.block if a.block is not None else BLOCKS[wn]
        sd = seeds(a.n, blk)
        n2 = min(a.n2, len(sd))
        sd2 = sd[:n2]
        kinds, tflip = membership(world(wn), sd)
        masks = {k: kinds == k for k in KINDS if (kinds == k).any()}
        runs, cpu, lives_of, diags = {}, {}, {}, {}
        kn = {fp: sw_knobs(fp) for fp in dict.fromkeys((FP, "hollow3"))}
        ck, ckp = cu_knobs(wn)
        meta = dict(world=wn, block=blk, n=len(sd), n2=n2, fp=FP, sw_knobs={f: dict(knobs=v[0], file=v[1]) for f, v in kn.items()},
                    cu_knobs=dict(knobs=ck, file=ckp), kinds={k: int(m.sum()) for k, m in masks.items()})

        def save():
            np.savez(f"{HERE}/data/{wn}_{a.tag}.npz", kinds=kinds, tflip=tflip, seeds=np.array(sd),
                     **{"F__" + n: Fv(r) for n, r in runs.items()},
                     **{"diag__" + n: d for n, d in diags.items()})
            dump(dict(meta, partial={n: dict(F=float(Fv(r).mean()), lives=lives_of[n], cpu_per_life=cpu[n])
                                     for n, r in runs.items()}), f"{HERE}/data/{wn}_{a.tag}.partial.json")

        def rec(name, fn, *args, secondary=False, det=None, **kw):
            s = sd2 if secondary else sd
            r, c, w = timed(fn, *args, s, **kw)
            runs[name] = r; cpu[name] = c / len(s); lives_of[name] = len(s)
            if det:
                diags[name] = np.asarray(r.diag)
            print(f"  {wn:12s} {name:40s} F {Fv(r).mean():+7.2f} caps {np.asarray(r['captures']).mean():6.1f} "
                  f"miss {np.asarray(r['misses']).mean():6.1f} cpu/life {c / len(s):.3f} ({w:.0f}s)", flush=True)
            save()
            return r

        # ---------------- core
        cands = {"reflex@hollow3": None}
        for k, v in rt_prior.get(wn, {}).items():
            cands[k] = v["knobs"]
        if wn in rt_mine:
            cands["rt-switching"] = rt_mine[wn]["knobs"]
        for k, v in cands.items():
            rec(f"R {k}", run_tissue, H.reflex("hollow3", v), wn)
        rnames = [f"R {k}" for k in cands]
        meta["reflex_rt_source"] = {k: rt_mine[wn].get("source") for k in ("rt-switching",) if wn in rt_mine}
        best = max(rnames, key=lambda n: Fv(runs[n]).mean())
        bk = hb.full_knobs(cands[best[2:]] or hb.SPECK_TUNED["reflex@hollow3"], hb.REFLEX_GRID)
        rec("C1 priv pursuit", run_ctl, H.C1, H.default_params(H.C1), wn, privileged=True)
        rec("C0 central reflex (=S0)", run_ctl, H.C0, H.default_params(H.C0), wn, privileged=False)
        rec("CU1 cusum @hollow3", run_ctl, CU, cu_params(wn, **ck), wn, privileged=False, det="CU")
        rec("C0M map1 mirrored", run_ctl, C0M, H.params(C0M, map=1.0), wn, privileged=False)
        if CU_RULES.get(wn, {}).get("two_way", 0.0) == 0 and wn != "flip_from0":
            rec("CUclk clock switch t512", run_ctl, CU, cu_params(wn, kdrift=-1e6, h=0.0, t_min=512.0, t_max=1e9),
                wn, privileged=False, det="CU")
        k3 = kn["hollow3"][0]
        from0 = wn == "flip_from0"  # every life flipped from t0: S1 = S2 = C0M map1 and SW2 = SW1 by construction
        if not from0:
            rec("S1 reflex-style Bayes detect @hollow3", run_sw, sw_params(wn, 1, act_style=1, **k3), wn, det="SW")
            rec("S2 reflex-style priv law @hollow3", run_sw_priv, sw_params(wn, 2, act_style=1, **k3), wn, det="SW")
        # core: SW1 / SW0 on the best footprint; secondary: SW2 there, and the hollow3 SW runs
        for fp in dict.fromkeys((FP, "hollow3")):
            k_ = kn[fp][0]
            sec = fp != FP
            if sec and a.core_only:
                continue
            rec(f"SW1 detect @{fp}", run_sw, sw_params(wn, 1, **k_), wn, fp=fp, det="SW", secondary=sec)
            rec(f"SW0 no-switch @{fp}", run_sw, sw_params(wn, 0, **k_), wn, fp=fp, secondary=sec)
            if not from0 and not a.core_only and fp == FP:
                rec(f"SW2 priv law @{fp}", run_sw_priv, sw_params(wn, 2, **k_), wn, fp=fp, det="SW", secondary=True)
            if wn in CLOCK_WORLDS and not a.core_only and fp == FP:
                rec(f"SW3 clock switch @{fp}", run_sw_clock, sw_params(wn, 3, **k_), wn, fp=fp, det="SW", secondary=True)
        if not a.core_only:
            # ---------------- secondary
            for nm, org in (("D reflex@hollow2", H.reflex("hollow2")), ("D reflex@ring2", H.reflex("ring2")),
                            ("D best C.g_r 0.5", H.reflex("hollow3", dict(bk, **{"C.g_r": 0.5}))),
                            ("D best C.g_r 0.25", H.reflex("hollow3", dict(bk, **{"C.g_r": 0.25}))),
                            ("D best M.kappa 0.25", H.reflex("hollow3", dict(bk, **{"M.kappa": 0.25}))),
                            ("D best M.w0 0.5", H.reflex("hollow3", dict(bk, **{"M.w0": 0.5})))):
                rec(nm, run_tissue, org, wn, secondary=True)
            rec("D null", run_ctl, H.NULL, np.zeros(1), wn, privileged=False, secondary=True)
            rec("D C0M tap-only", run_ctl, C0M, H.params(C0M, motors=0.0), wn, privileged=False, secondary=True)
            rec("D C0 quiet taps", run_ctl, H.C0, H.params(H.C0, n_coinc=2.0), wn, privileged=False, secondary=True)
            if not a.skip_x:
                rec("X reflex@ring4 frozen", run_tissue, H.reflex("ring4"), wn, secondary=True)
                rec("X C4 (flip_mid knobs) @hollow3", run_ctl, H.C4,
                    H.bayes_params("flip_mid", tau_eff=0.402, dt=0.531, gain=1.082, min_align=0.561, tol=0.146, q_tap=0.282),
                    wn, privileged=False, secondary=True)
                if PRIORS.get(wn, {}).get("p_mid", 0) > 0 and wn in ("flip_mix", "flip_mid"):
                    rec(f"X SW1 flat hazard (no window) @{FP}", run_sw,
                        sw_params(wn, 1, **dict(kn[FP][0], p_mid=0.0, haz_floor=1.0 / 1024.0)), wn, fp=FP, det="SW",
                        secondary=True)
        # ---------------- summary
        bF = Fv(runs[best])
        out = dict(meta, best_reflex=best, best_reflex_F=float(bF.mean()),
                   reflex_candidates={n: float(Fv(runs[n]).mean()) for n in rnames}, runs={})
        for name, r in runs.items():
            n_ = lives_of[name]
            f = Fv(r)
            ent = dict(lives=n_, F=float(f.mean()), F_se=float(f.std(ddof=1) / math.sqrt(n_)),
                       vs_best_reflex=paired(f, bF[:n_]), cpu_per_life=cpu[name], stats=stats(r))
            ent["by_kind"] = {k: dict(n=int(m[:n_].sum()), F=float(f[m[:n_]].mean()),
                                      vs_best_reflex=paired(f, bF[:n_], m[:n_]),
                                      late_caps=float(r.ledger[m[:n_], 22].mean()))
                              for k, m in masks.items() if m[:n_].any()}
            if name in diags:
                typ = "CU" if name.startswith("CU") else "SW"
                ent["detector_diag"] = det_diag(typ, diags[name], {k: m[:n_] for k, m in masks.items()}, tflip[:n_])
            out["runs"][name] = ent
        comp = {}
        pairs = [(f"SW1 detect @{fp}", f"SW0 no-switch @{fp}") for fp in dict.fromkeys((FP, "hollow3"))]
        pairs += [(f"SW2 priv law @{fp}", f"SW0 no-switch @{fp}") for fp in dict.fromkeys((FP, "hollow3"))]
        pairs += [(f"SW1 detect @{fp}", f"SW2 priv law @{fp}") for fp in dict.fromkeys((FP, "hollow3"))]
        pairs += [(f"SW1 detect @{FP}", f"SW3 clock switch @{FP}"), (f"SW3 clock switch @{FP}", f"SW0 no-switch @{FP}")]
        pairs += [("S1 reflex-style Bayes detect @hollow3", "C0 central reflex (=S0)"),
                  ("S2 reflex-style priv law @hollow3", "C0 central reflex (=S0)"),
                  ("S1 reflex-style Bayes detect @hollow3", "S2 reflex-style priv law @hollow3"),
                  ("CU1 cusum @hollow3", "C0 central reflex (=S0)"),
                  ("CU1 cusum @hollow3", "S2 reflex-style priv law @hollow3"),
                  ("CU1 cusum @hollow3", "S1 reflex-style Bayes detect @hollow3"),
                  ("C0 central reflex (=S0)", best)]
        if "CUclk clock switch t512" in runs:
            pairs += [("CUclk clock switch t512", "C0 central reflex (=S0)"),
                      ("CU1 cusum @hollow3", "CUclk clock switch t512")]
        for x, y in pairs:
            if x not in runs or y not in runs or x == y:
                continue
            n_ = min(lives_of[x], lives_of[y])
            fx, fy = Fv(runs[x])[:n_], Fv(runs[y])[:n_]
            comp[f"{x} - {y}"] = dict(all=paired(fx, fy), **{k: paired(fx, fy, m[:n_]) for k, m in masks.items()
                                                             if m[:n_].any()})
        out["comparisons"] = comp
        dl = [n for n in runs if n.startswith("D ")]
        if dl:
            bd = max(dl, key=lambda n: Fv(runs[n]).mean())
            out["do_less_best"] = bd
            out["do_less_gap"] = paired(Fv(runs[bd]), bF[:lives_of[bd]])
        save()
        dump(out, f"{HERE}/data/{wn}_{a.tag}.json")
        c = {k: v["all"] for k, v in comp.items()}
        g = lambda k: pf(c[k]) if k in c else "n/a"  # noqa: E731
        print(f"== {wn}: best reflex {best} {bF.mean():+.2f} | SW1@{FP} - best {pf(paired(runs[f'SW1 detect @{FP}'], bF))}"
              f" | SW1-SW0 @{FP} {g(f'SW1 detect @{FP} - SW0 no-switch @{FP}')}"
              f" | S1-C0 {g('S1 reflex-style Bayes detect @hollow3 - C0 central reflex (=S0)')}"
              f" | CU1-C0 {g('CU1 cusum @hollow3 - C0 central reflex (=S0)')}", flush=True)


if __name__ == "__main__":
    main()
