"""Validation of the central-controller harness (writes tests/validation.json and tests/validation.md).

Seed blocks (fresh_seeds(n, 43_000_000 + 10_000 * block)): 0 determinism / stream tests; 1 C0 vs reflex; 2 scoring of
C1 / C2 / C3 / best reflex; 5 C2 tuning (ES, 64 of 512 per generation); 6 C3 tuning; 7-8 reflex re-tunes
(retune_reflex.py). Tuning lives never score.
    python validate.py [parts]   parts: det,stream,replay,c0,tune,score,c3,timing (default: all)
"""
import json, os, sys, time
import numpy as np
import harness as H
sys.path.insert(0, os.path.join(H.HERE, "tests"))
import replay as RP

THREADS = int(os.environ.get("HR_THREADS", "6"))
OUT = os.path.join(H.HERE, "tests")
JS = os.path.join(OUT, "validation.json")
parts = sys.argv[1].split(",") if len(sys.argv) > 1 else ["det", "stream", "replay", "c0", "tune", "score", "c3",
                                                         "timing"]
R = json.load(open(JS)) if os.path.exists(JS) else {}
fp = H.footprint("hollow3")
SCORE_WORLDS = ["base", "base1", "pool", "blink20", "flip_mid", "lead"]


def log(*a):
    print(*a, flush=True)


def save():
    json.dump(R, open(JS, "w"), indent=1, default=float)


def stat(res):
    s = H.summary(res)
    return {k: round(v, 4) if isinstance(v, float) else v for k, v in s.items()}


# ------------------------------------------------------------------------------------------- determinism
if "det" in parts:
    sd = H.seeds(32, 0)
    out = {}
    for cid in (H.C0, H.C1, H.C2, H.C4):
        p = H.bayes_params("pool") if cid == H.C4 else H.default_params(cid)
        a = H.ctl_run(cid, p, fp, "pool", sd, threads=THREADS)
        b = H.ctl_run(cid, p, fp, "pool", sd, threads=1)
        c = H.ctl_run(cid, p, fp, "pool", sd, threads=THREADS, fast=False)
        d = H.ctl_run(cid, p, fp, "pool", sd, threads=3, fast=False)
        out[H.CONTROLLERS[cid].name] = dict(
            threads6_vs_1=bool(np.array_equal(a.ledger, b.ledger) and np.array_equal(a.diag, b.diag)),
            fast_vs_full_ledger=bool(np.array_equal(a.ledger, c.ledger)),
            full_twice_hashes=bool(np.array_equal(c.hashes, d.hashes) and np.array_equal(c.ledger, d.ledger)))
    # the scratch kernel's tissue path against the repo kernel (columns 21-22 are the scratch counters by design)
    from src.life import build, spec
    body = H.reflex("hollow3")
    for wn in ("base1", "pool"):
        ws = H.world_spec(wn)
        t1 = H.tissue_run(body, wn, sd, threads=THREADS, fast=False)
        t2 = build.run(body.world(ws.preset, **ws.over), sd, programs=body.program, init=list(body.cells),
                       threads=THREADS, abi=spec.V3)
        keep = [i for i in range(t1.ledger.shape[1]) if i not in (21, 22)]
        out[f"tissue scratch kernel == repo kernel ({wn})"] = dict(
            ledger_except_21_22=bool(np.array_equal(t1.ledger[:, keep], t2.ledger[:, keep])),
            hashes_spikes_fate_chem_world=bool(np.array_equal(t1.hashes[:, 1:], t2.hashes[:, 1:])))
    R["determinism"] = out
    log("determinism", json.dumps(out, indent=1))
    save()

# ------------------------------------------------------------------------------------------- stream equality
if "stream" in parts:
    sd = H.seeds(32, 0, first=0)
    cols = ("rec_cand", "rec_accept", "respawns", "samples", "dist_sum", "zone_samples", "path", "X_end", "Y_end",
            "captures", "clicks", "kills", "n_end", "beats", "P_int")
    out = {}
    for wn in H.WORLDS:
        for fpn in ("hollow3", "ring4"):
            f = H.footprint(fpn)
            a = H.ctl_run(H.NULL, [], f, wn, sd, threads=THREADS, fast=False, charge="none")
            b = H.tissue_run(f.inert_body(), wn, sd, threads=THREADS, fast=False)
            eq = {c: bool(np.array_equal(a[c], b[c])) for c in cols}
            eq["world_hash"] = bool(np.array_equal(a.hashes[:, 4], b.hashes[:, 4]))
            rel = np.abs(a["live_time"] - b["live_time"]) / b["live_time"]
            out[f"{wn}@{fpn}"] = dict(all_equal=all(eq.values()), mismatches=[k for k, v in eq.items() if not v],
                                      live_time_max_rel_diff=float(rel.max()),
                                      F_max_abs_diff=float(np.abs(a["F"] - b["F"]).max()),
                                      pings_delivered=float(a.diag[:, 0].mean()), rec_accept=float(a["rec_accept"].mean()))
            log("stream", wn, fpn, out[f"{wn}@{fpn}"])
    R["stream_equality"] = out
    save()

if "replay" in parts:
    out = {}
    for wn in H.WORLDS:
        eq, tis, rep = RP.run(wn, n=16, block=0, threads=THREADS)
        bad = [k for k, v in eq.items() if not v]
        out[wn] = dict(all_equal=not bad, mismatches=bad, captures=float(tis["captures"].mean()),
                       F_tissue=float(tis["F"].mean()), F_replay=float(rep["F"].mean()))
        log("replay", wn, out[wn])
    R["replay"] = out
    save()

# ------------------------------------------------------------------------------------------- C0 vs reflex
if "c0" in parts:
    sd = H.seeds(256, 1)
    out = {}
    for wn in ("base1", "base", "pool"):
        ref = H.tissue_run(H.reflex("hollow3"), wn, sd, threads=THREADS)
        c0 = H.ctl_run(H.C0, H.default_params(H.C0), fp, wn, sd, threads=THREADS)
        out[wn] = dict(reflex=stat(ref), C0=stat(c0), C0_minus_reflex=H.paired(c0, ref),
                       pings_per_life=float(c0.diag[:, 0].mean()), reflex_spikes=float(ref["spikes"].mean()),
                       C0_spikes=float(c0["spikes"].mean()))
        log("C0", wn, H.pfmt(out[wn]["C0_minus_reflex"]), out[wn]["reflex"]["F"], out[wn]["C0"]["F"])
    R["C0_vs_reflex"] = out
    save()

# ------------------------------------------------------------------------------------------- C2 light tuning
if "tune" in parts:
    tune = H.seeds(512, 5)
    x0 = np.load(os.path.join(OUT, "c2_base1_try.npy"))
    out = R.get("C2_tuned", {})
    for wn in SCORE_WORLDS:
        t = time.time()
        r = H.es_tune(H.C2, x0, fp, wn, tune, iters=15, popsize=16, lives_per_gen=64, threads=THREADS, seed=2,
                      log=None)
        out[wn] = dict(x=[float(v) for v in r["x"]], F_tune=r["F"], sec=time.time() - t)
        log("tuned C2", wn, round(r["F"], 3), f"{time.time() - t:.0f}s")
        R["C2_tuned"] = out
        save()
    # C4: light tuning of the decision knobs only (the world-model constants stay at the world's values)
    names = H.CONTROLLERS[H.C4].names
    mask = [names.index(k) for k in ("tau_eff", "dt", "gain", "min_align", "tol", "q_tap")]
    out4 = R.get("C4_tuned", {})
    for wn in SCORE_WORLDS:
        t = time.time()
        r = H.es_tune(H.C4, H.bayes_params(wn), fp, wn, tune, iters=8, popsize=12, lives_per_gen=48,
                      threads=THREADS, seed=5, mask=mask, log=None)
        out4[wn] = dict(x=[float(v) for v in r["x"]], F_tune=r["F"], sec=time.time() - t,
                        knobs={names[i]: float(r["x"][i]) for i in mask})
        log("tuned C4", wn, round(r["F"], 3), f"{time.time() - t:.0f}s", out4[wn]["knobs"])
        R["C4_tuned"] = out4
        save()

# ------------------------------------------------------------------------------------------- scoring
if "score" in parts:
    sd = H.seeds(256, 2)
    out = {}
    for wn in SCORE_WORLDS:
        best, ref, means = H.best_reflex(wn, sd, threads=THREADS)
        row = dict(best_reflex=best, reflex_candidates=means, reflex=stat(ref))
        runs = {"C1": (H.C1, H.default_params(H.C1)), "C2 default": (H.C2, H.default_params(H.C2))}
        if wn in R.get("C2_tuned", {}):
            runs["C2 tuned"] = (H.C2, np.array(R["C2_tuned"][wn]["x"]))
        runs["C4 default"] = (H.C4, H.bayes_params(wn))
        if wn in R.get("C4_tuned", {}):
            runs["C4 tuned"] = (H.C4, np.array(R["C4_tuned"][wn]["x"]))
        if wn.startswith("blink") or wn.startswith("flash"):
            runs["C1 use_dark=0"] = (H.C1, H.params(H.C1, use_dark=0.0))
            runs["C4 no blink model"] = (H.C4, H.bayes_params(wn, blink_on=0.0, blink_off=0.0))
        for nm, (cid, p) in runs.items():
            t = time.time()
            r = H.ctl_run(cid, p, fp, wn, sd, threads=THREADS)
            row[nm] = dict(stat(r), vs_best_reflex=H.paired(r, ref), cpu_s_per_life=(time.time() - t) * THREADS / len(sd),
                           strokes=float(r.diag[:, 2].mean()), dark_caps=float(r["beats"].mean()),
                           late_caps=float(r["P_int"].mean()))
            log(f"score {wn:9s} {nm:14s} F {row[nm]['F']:+7.2f}  vs best reflex ({best} {row['reflex']['F']:+.2f}) "
                f"{H.pfmt(row[nm]['vs_best_reflex'])}  caps {row[nm]['captures']:.1f} miss {row[nm]['misses']:.1f}")
        row["reflex"]["dark_caps"] = float(ref["beats"].mean()); row["reflex"]["late_caps"] = float(ref["P_int"].mean())
        out[wn] = row
        R["score"] = out
        save()

# ------------------------------------------------------------------------------------------- C3 RNN smoke + short ES
if "c3" in parts:
    rng = np.random.default_rng(3)
    nh = 4
    x0 = H.rnn_params(fp, nh, dt=0.5, thr=0.5, rng=rng, scale=0.2)
    nin = len(fp.sense) + 2
    off_bo = 3 + nh * nin + nh * nh + nh + len(fp.act) * nh
    x0[off_bo:] = -1.0  # output biases: quiet start
    mask = np.arange(3, len(x0))
    tune = H.seeds(256, 6)
    t = time.time()
    r = H.es_tune(H.C3, x0, fp, "base1", tune, iters=25, popsize=24, lives_per_gen=32, threads=THREADS, seed=4,
                  sigma0=0.3, lo=np.full(len(x0), -5.0), hi=np.full(len(x0), 5.0), mask=mask, log=None)
    r_lo = H.ctl_run(H.C3, x0, fp, "base1", H.seeds(256, 2), threads=THREADS)
    r_hi = H.ctl_run(H.C3, r["x"], fp, "base1", H.seeds(256, 2), threads=THREADS)
    R["C3"] = dict(n_params=len(x0), n_h=nh, F_start=stat(r_lo), F_tuned=stat(r_hi), tune_sec=time.time() - t,
                   tune_hist=[h["F_mean_cand"] for h in r["history"]],
                   vs_reflex_base1=R.get("score", {}).get("base1", {}).get("reflex", {}).get("F"))
    np.save(os.path.join(OUT, "c3_base1.npy"), r["x"])
    log("C3", R["C3"]["F_start"]["F"], "->", R["C3"]["F_tuned"]["F"])
    save()

# ------------------------------------------------------------------------------------------- timing
if "timing" in parts:
    sd = H.seeds(192, 0)
    out = {}
    for wn in ("base1", "pool"):
        for nm, fn in (("tissue reflex@hollow3", lambda: H.tissue_run(H.reflex("hollow3"), wn, sd, threads=THREADS)),
                       ("null", lambda: H.ctl_run(H.NULL, [], fp, wn, sd, threads=THREADS)),
                       ("C0", lambda: H.ctl_run(H.C0, H.default_params(H.C0), fp, wn, sd, threads=THREADS)),
                       ("C1", lambda: H.ctl_run(H.C1, H.default_params(H.C1), fp, wn, sd, threads=THREADS)),
                       ("C2", lambda: H.ctl_run(H.C2, H.default_params(H.C2), fp, wn, sd, threads=THREADS)),
                       ("C4", lambda: H.ctl_run(H.C4, H.bayes_params(wn), fp, wn, sd, threads=THREADS))):
            fn()
            t = time.time(); fn(); dt = time.time() - t
            out[f"{nm} | {wn}"] = dict(wall_s_per_life=dt / len(sd), cpu_s_per_life=dt * THREADS / len(sd))
            log("timing", nm, wn, out[f"{nm} | {wn}"])
    R["timing"] = out
    save()
