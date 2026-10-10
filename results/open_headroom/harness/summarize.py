"""validation.json -> tests/validation.md (the tables quoted in README.md)."""
import json, os
HERE = os.path.dirname(os.path.abspath(__file__))
R = json.load(open(os.path.join(HERE, "tests", "validation.json")))
L = []
P = lambda d: f"{d['mean']:+.2f} ± {d['se']:.2f}"  # noqa: E731

if "determinism" in R:
    L += ["## Determinism", "", "| check | result |", "|---|---|"]
    for k, v in R["determinism"].items():
        L.append(f"| {k} | " + ", ".join(f"{a}: {'PASS' if b else 'FAIL'}" for a, b in v.items()) + " |")
    L.append("")
if "stream_equality" in R:
    se = R["stream_equality"]
    ok = sum(v["all_equal"] for v in se.values())
    L += ["## Stream equality (null controller vs inert program body, same footprint, 32 lives each)", "",
          f"{ok} / {len(se)} world x footprint cells bitwise equal on the world hash and every comparable column "
          "(rec_cand, rec_accept, respawns, samples, dist_sum, zone_samples, path, X_end, Y_end, captures, clicks, kills, "
          "n_end, dark/late captures).", "",
          f"live_time differs only by summation order: max relative difference "
          f"{max(v['live_time_max_rel_diff'] for v in se.values()):.1e}; max |dF| "
          f"{max(v['F_max_abs_diff'] for v in se.values()):.1e}.", ""]
    bad = [k for k, v in se.items() if not v["all_equal"]]
    if bad:
        L += [f"Mismatches: {bad}", ""]
if "replay" in R:
    rp = R["replay"]
    ok = sum(v["all_equal"] for v in rp.values())
    L += ["## Replay (tissue reflex@hollow3 act-plane raster replayed by the controller, 16 lives per world)", "",
          f"{ok} / {len(rp)} worlds bitwise equal on the world hash, captures, misses, clicks, b2 clicks, nudges, path, "
          "dot end position, receptor columns, dark / late captures, kills and income.", "",
          "| world | captures | F tissue | F replay (sense spikes not charged as the tissue's) |", "|---|---|---|---|"]
    for w, v in rp.items():
        L.append(f"| {w} | {v['captures']:.1f} | {v['F_tissue']:+.2f} | {v['F_replay']:+.2f} |")
    L.append("")
if "C0_vs_reflex" in R:
    L += ["## C0 central reflex vs tissue reflex@hollow3 (256 lives, block 1)", "",
          "| world | reflex F | C0 F | C0 - reflex | captures reflex / C0 | misses reflex / C0 |", "|---|---|---|---|---|---|"]
    for w, v in R["C0_vs_reflex"].items():
        L.append(f"| {w} | {v['reflex']['F']:+.2f} | {v['C0']['F']:+.2f} | {P(v['C0_minus_reflex'])} | "
                 f"{v['reflex']['captures']:.1f} / {v['C0']['captures']:.1f} | {v['reflex']['misses']:.1f} / {v['C0']['misses']:.1f} |")
    L.append("")
if "score" in R:
    L += ["## First look: controllers vs the best reflex (256 fresh lives per world, block 2; paired per-life differences)", "",
          "| world | best reflex (F) | controller | F | − best reflex | captures | misses | CPU s/life |",
          "|---|---|---|---|---|---|---|---|"]
    for w, row in R["score"].items():
        first = True
        for nm, v in row.items():
            if nm in ("best_reflex", "reflex_candidates", "reflex"):
                continue
            lead = f"{w} | {row['best_reflex']} ({row['reflex']['F']:+.2f})" if first else " | "
            first = False
            L.append(f"| {lead} | {nm} | {v['F']:+.2f} | {P(v['vs_best_reflex'])} | {v['captures']:.1f} | "
                     f"{v['misses']:.1f} | {v['cpu_s_per_life']:.3f} |")
    L += ["", "Reflex candidates per world (mean F on the scoring lives; the best is the reference):", ""]
    for w, row in R["score"].items():
        L.append(f"- {w}: " + ", ".join(f"{k} {v:+.2f}" for k, v in row["reflex_candidates"].items()))
    L.append("")
if "C3" in R:
    c = R["C3"]
    L += ["## C3 tiny RNN (hollow3, n_h 4, base1)", "",
          f"{c['n_params']} parameters. Random start (output biases -1): F {c['F_start']['F']:+.2f}; after a short "
          f"separable-CMA run (25 generations x 24 candidates x 32 lives, block 6): F {c['F_tuned']['F']:+.2f} on 256 "
          f"scoring lives (captures {c['F_tuned']['captures']:.1f}, misses {c['F_tuned']['misses']:.1f}). "
          f"Tuning took {c['tune_sec']:.0f} s.", ""]
if "timing" in R:
    L += ["## Seconds per life (192 lives, 6 threads; CPU-s = wall x threads / lives)", "", "| run | CPU s / life |",
          "|---|---|"]
    for k, v in R["timing"].items():
        L.append(f"| {k.replace(' | ', ' in ')} | {v['cpu_s_per_life']:.3f} |")
    L.append("")
for key in ("C2_tuned", "C4_tuned"):
    if key in R:
        L += [f"## {key} (tuning block 5; F on the 512 tuning lives)", ""]
        for w, v in R[key].items():
            L.append(f"- {w}: F_tune {v['F_tune']:+.2f}" + (f", knobs {json.dumps({k: round(x, 3) for k, x in v['knobs'].items()})}" if "knobs" in v else ""))
        L.append("")
open(os.path.join(HERE, "tests", "validation.md"), "w").write("\n".join(L))
print("\n".join(L))
