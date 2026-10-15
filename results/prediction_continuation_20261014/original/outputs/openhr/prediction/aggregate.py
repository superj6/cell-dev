"""Aggregate out/score_WORLD__TAG.{json,npz} into results.json (per-world gaps, verdicts).

usage: aggregate.py [TAGS=main,ext] [OUT=results.json]
Per world, the per-life F of every run is concatenated over the TAGS that exist for it (same run names; e.g. block
130 'main' + block 131 'ext'); the best reflex is re-picked as the best reflex candidate on the combined lives; every
gap is the paired mean +- SE of the per-life difference vs that best reflex on the combined lives.
  ceiling     : the better of C1@hollow3 and C1@ring4 (privileged pursuit; a lower bound on the true ceiling)
  info        : the best PF-full run (ring4 params on ring4 / hollow3; disk4x4 = ring4 minus the hidden cells' c_live)
  do-less     : the best of the do-less variants (smaller / quieter / motionless reflex bodies)
Verdict rule (task spec):
  NO_HEADROOM ceiling gap < 3 F
  ADMIT       info-matched gap > 3 SE and >= 1 F, and the do-less gap clearly smaller (< 1/3 of the info gap)
  FIX_WORLD   ceiling large but the reward pays mostly for doing less (do-less gap >= 1/3 of the info gap)
  UNCLEAR     otherwise
Also reported (not part of the verdict): the info gap against the best SIMPLE body of any size (max over reflex
candidates and do-less variants on the same lives), and the capability-specific check 'prediction increment' = best
PF-full minus PF-abl (the same filter without a velocity state, tuned with the same budget)."""
import sys

from pcommon import *  # noqa: F401,F403

TAGS = (sys.argv[1] if len(sys.argv) > 1 else "main,ext").split(",")
OUT = sys.argv[2] if len(sys.argv) > 2 else f"{HERE}/results.json"
PRIOR_HAND = {  # prior study (t12_lead.py, 256 lives, block 14 of the capability study): hand-built bodies vs reflex
    "v0.2_tau200": "router@ring4 +0.55 +- 0.16; grn-router -1.66; memory bodies -0.83",
    "v0.2_tau5": "router@ring4 +0.97 +- 0.18; grn-router -0.76",
    "v0.3_tau200": "router@ring4 -0.33 +- 0.12; grn-router -2.00; motionless hold twin +1.20 over the grn-router",
    "v0.3_tau5": "router@ring4 -0.16 +- 0.17; grn-router -1.48",
    "v0.4_tau200": "no interceptor built; v_t 0.4 tau_turn 0 (straight): router -1.49 vs reflex (128 lives, unpaired)",
    "v0.4_tau20": "no interceptor built; router -1.16; 2-cell clicker ties the reflex (+0.61 vs +0.67)",
    "base1": "router@ring4 +2.04 +- 0.22 (prior base world)",
}
key = lambda n: n.replace("@", "_at_").replace(" ", "_").replace(":", "_").replace("(", "").replace(")", "")  # noqa


def g(d):
    return f"{d['mean']:+.2f} +- {d['se']:.2f}"


def load_world(w):
    parts = []
    for t in TAGS:
        p = f"{HERE}/out/score_{w}__{t}.json"
        if os.path.exists(p):
            parts.append((t, jload(p), np.load(p.replace(".json", ".npz"))))
    if not parts:
        return None
    S0 = parts[0][1]
    names = [n for n in S0["runs"] if all(key(n) in Z.files for _, _, Z in parts)]
    F = {n: np.concatenate([Z[key(n)] for _, _, Z in parts]) for n in names}
    seeds_ = np.concatenate([Z["seeds"] for _, _, Z in parts])
    assert len(set(seeds_.tolist())) == len(seeds_), "overlapping lives across tags"
    runs = {n: dict(S0["runs"][n]) for n in names}
    for n in names:
        runs[n]["F"] = float(F[n].mean())
        runs[n]["F_se"] = float(F[n].std(ddof=1) / np.sqrt(len(F[n])))
    return dict(S0=S0, parts=parts, F=F, runs=runs, n=len(seeds_), blocks=[S["block"] for _, S, _ in parts],
                tags=[t for t, _, _ in parts])


rows = []
robust = jload(f"{HERE}/out/robust.json", {})
c3 = jload(f"{HERE}/out/c3.json", {})
for w in [*MAIN, *REFS]:
    D = load_world(w)
    if D is None:
        continue
    runs, F = D["runs"], D["F"]
    kinds = {n: r["kind"] for n, r in runs.items()}
    pick = lambda kind: max((n for n in runs if kinds[n] == kind), key=lambda n: runs[n]["F"], default=None)  # noqa
    best = pick("reflex")
    gaps = {n: paired(F[n], F[best]) for n in runs}
    ceil_n, info_n, dl_n, hand_n, nov_n = pick("ceiling"), pick("info"), pick("doless"), pick("hand"), pick("info_novel")
    ws = WORLDS[w]
    row = dict(name=w, keys=", ".join(f"{k} {v}" for k, v in ws.over.items()) or "catch_speck_l4 defaults (base1)",
               lives=D["n"], blocks=D["blocks"], best_reflex_F=f"{runs[best]['F']:+.2f} +- {runs[best]['F_se']:.2f}",
               best_reflex_source=best + (" (frozen)" if best == "reflex@hollow3" else
                                          " (re-tuned in this world, this study)" if best == "rt-pred@hollow3" else
                                          " (recovered re-tune of a related world)"))
    row["ceiling_gap"] = g(gaps[ceil_n]) + f" ({ceil_n})" if ceil_n else "n/a"
    row["info_gap"] = g(gaps[info_n]) if info_n else "n/a"
    row["info_controller"] = (f"{info_n}: PF interceptor (particle filter over target position + heading, world rules as "
                              f"parameters, ES-tuned on block 122)") if info_n else "n/a"
    row["do_less_gap"] = (g(gaps[dl_n]) + f" ({dl_n})") if dl_n else "n/a"
    row["hand_tissue_gap"] = ((g(gaps[hand_n]) + f" ({hand_n}, these lives); ") if hand_n else "") + \
        "prior study: " + PRIOR_HAND.get(w.replace("pool_", ""), "n/a") + \
        (" [prior numbers are for the non-POOL world]" if w.startswith("pool_") else "")
    row["learned_gap"] = c3.get(w, {}).get("gap", "n/a (the designed controller passed; C3 not needed)")
    if info_n:
        gi = gaps[info_n]
        cpu_t = runs[best]["cpu_per_life"]
        cpu_c = runs[info_n]["cpu_per_life"]
        z2 = (gi["mean"] / gi["sd"]) ** 2
        row["sel_info_per_cpu_s"] = (f"{z2 / cpu_t:.0f} per tissue-life CPU-s (best reflex {cpu_t:.3f} CPU-s/life); "
                                     f"{z2 / cpu_c:.1f} per controller-life CPU-s ({cpu_c:.3f}); (gap/SD)^2 = {z2:.2f}")
        row["cpu_per_life"] = dict(best_reflex=cpu_t, info_controller=cpu_c,
                                   ceiling=runs[ceil_n]["cpu_per_life"] if ceil_n else None)
    cg = gaps[ceil_n]["mean"] if ceil_n else np.nan
    ig = gaps[info_n] if info_n else None
    dg = gaps[dl_n]["mean"] if dl_n else 0.0
    if not np.isnan(cg) and cg < 3.0:
        verdict = "NO_HEADROOM"
    elif ig and ig["mean"] > 3 * ig["se"] and ig["mean"] >= 1.0 and dg < ig["mean"] / 3:
        verdict = "ADMIT"
    elif ig and dg >= max(ig["mean"], 0.0) / 3 and dg > 0:
        verdict = "FIX_WORLD"
    else:
        verdict = "UNCLEAR"
    row["verdict"] = verdict
    notes = []
    if info_n:
        se_big = [n for n in (info_n, ceil_n, dl_n) if n and gaps[n]["se"] > 0.15]
        if se_big:
            notes.append(f"SE > 0.15 for {', '.join(se_big)} at {D['n']} lives")
    pi = None
    full = [n for n in runs if kinds[n] == "info"]
    abl = [n for n in runs if n.startswith("PF-abl")]
    if full and abl:
        bf = max(full, key=lambda n: runs[n]["F"]); ba = max(abl, key=lambda n: runs[n]["F"])
        pi = dict(full=bf, abl=ba, **paired(F[bf], F[ba]))
        cap = pi["mean"] > 3 * pi["se"] and pi["mean"] >= 1.0
        notes.append(f"prediction increment {bf} - {ba} = {g(pi)} "
                     f"({'velocity state pays' if cap else 'velocity state does not clearly pay'})")
        notes.append(f"velocity-free PF-abl vs best reflex {g(gaps[ba])}")
    simple = [n for n in runs if kinds[n] in ("reflex", "doless")]
    bs = max(simple, key=lambda n: runs[n]["F"])
    if info_n:
        gs = paired(F[info_n], F[bs])
        row["info_gap_vs_best_simple_body"] = f"{g(gs)} (vs {bs}, F {runs[bs]['F']:+.2f})"
        notes.append(f"info gap vs the best simple body of any size ({bs}): {g(gs)}")
    if "PF-full@hollow3 (ring4 params)" in runs:
        notes.append(f"PF-full@hollow3 (ring4 params, the reflex's own footprint) {g(gaps['PF-full@hollow3 (ring4 params)'])}")
    if "PF-full@disk4x4" in runs:
        notes.append(f"PF-full@disk4x4 (pays for two hidden planes) {g(gaps['PF-full@disk4x4'])}")
    if nov_n:
        notes.append(f"C2 generic tracker (default) {g(gaps['C2@hollow3'])}" if "C2@hollow3" in runs else "")
    rb = robust.get(w, {})
    for k_, v_ in rb.items():
        if isinstance(v_, dict) and "gap_vs_best_reflex" in v_:
            notes.append(f"robust {k_}: F {v_['F']:+.2f}, gap {g(v_['gap_vs_best_reflex'])} ({rb.get('n', '?')} lives)")
        elif isinstance(v_, dict) and "mean" in v_:
            notes.append(f"robust {k_}: {g(v_)}")
    for n in runs:
        if n.startswith("PF") or n.startswith("C"):
            notes.append(f"{n}: F {runs[n]['F']:+.2f}, cap {runs[n]['captures']:.1f}, miss {runs[n]['misses']:.1f}, "
                         f"cpu {runs[n]['cpu_per_life']:.3f}")
    notes.append("do-less variants: " + "; ".join(f"{n} {g(gaps[n])}" for n in runs if kinds[n] == "doless"))
    notes.append("reflex candidates (F): " + "; ".join(f"{n} {runs[n]['F']:+.2f}" for n in runs if kinds[n] == "reflex"))
    row["notes"] = " | ".join(x for x in notes if x)
    row["_raw"] = dict(gaps=gaps, runs=runs, prediction_increment=pi, best_reflex_knobs=D["S0"].get("best_reflex_knobs"))
    rows.append(row)
jdump(dict(tags=TAGS, worlds=rows, generated=time.strftime("%Y-%m-%d %H:%M")), OUT)
for r in rows:
    print(f"{r['name']:18s} n {r['lives']:5d} reflex {r['best_reflex_F']:>14s} ceiling {r['ceiling_gap'].split(' (')[0]:>15s} "
          f"info {r['info_gap']:>15s} do-less {r['do_less_gap']}  -> {r['verdict']}")
    print("    " + r["notes"].split(" | ")[0][:200])
