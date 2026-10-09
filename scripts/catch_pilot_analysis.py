"""BODY-1 pilot analysis: the pre-registered criteria of RESULTS.md (Pre-pilot, part 10) and measurement-only
diagnostics of the final best genomes.

Sections (``--only`` picks a comma-separated subset; the default runs all of them):
- ``criteria``: per arm, from the results rows. S0 (v1 L4) succeeds if >= 5 of 10 seeds reach F >= +2.0 (``skill_at``,
  ``evals_to_skill``) and is killed if >= 8 of 10 sit at <= 4 cells; S1 start (SPECK L4) likewise at +4.0. GB11's
  ``n_half`` and ``growing`` are reported, not judged.
- ``dynamics``: selection from lineage.jsonl (children kept per generation, frozen generations, breed collapse,
  genome distance, the shortlist's 3-life against 4-life rank agreement). No lives.
- ``routing``: S1 routing. Each SPECK L4 final best on 1024 fresh lives at T 1024 against the best tuned reflex
  (``reflex@hollow3``, frozen ``handbuilt.SPECK_TUNED``) on the same lives: a seed counts if the genome beats it by more
  than 3 paired SE and loses at least half of that lead under lateral_off from birth.
- ``slit``: the end-of-life bodies of every grown final best (32 lives each): filled footprint against the radius-1
  closing and the per-piece hull (LIFE_ABI.md 15.61). The F a body gains from its footprint's discount is estimated
  from finding 2's measured slit gain (+0.223 F in catch_v1, +0.177 in SPECK for sqrt(37 / 29) of speed), scaled by
  log(n_closing / n_fill); a body over +0.1 F reopens the law (pre-registered).
- ``knockouts``: genome surgery on every grown final best, paired on 256 fresh lives: a knob family's readout row set to
  its neutral value in every gene state (``KNOB_KO``), or a gene input's W column zeroed (``INPUT_KO``).
- ``fast``: the same bests and the tuned SPECK reflex and router at d0 0.5, d_min 0.25 (every contact, notice, packet
  and receptor latency halved), paired on the knockouts' 256 lives.

Every life is seeded ``PILOT_SEED0 + s``: disjoint from every gate's seed range (5M-19M, 41M) and from evolution's
hashed 64-bit life seeds. Nothing here feeds back into a run. Writes results/catch_pilot/analysis.json and
analysis.md; the per-life F arrays go to ``--lives`` (outputs/catch_pilot_analysis/lives.npz; ``--reuse`` reads them
back).

    .venv/bin/python scripts/catch_pilot_analysis.py --threads 8
    .venv/bin/python scripts/catch_pilot_analysis.py --only criteria,dynamics
"""
from __future__ import annotations

import argparse
import json
import math
import sys
import time
from pathlib import Path

import numpy as np

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from src import lattice  # noqa: E402
from src.genome import Layout  # noqa: E402
from src.life import analysis, spec  # noqa: E402
from src.life import handbuilt as hb  # noqa: E402

V3 = spec.V3
LF = V3.L["F"]
G_MAX = 16
PILOT_SEED0 = 23_000_000
ROUTE_LIVES, SLIT_LIVES, KO_LIVES = 1024, 32, 256
Z = 3.0
ARMS = {"lmax4": "v1 L4", "lmax2": "v1 L2", "seeded": "v1 seeded", "speck_lmax4": "SPECK L4",
        "speck_seeded": "SPECK seeded"}
MAIN = {"lmax4": "S0", "speck_lmax4": "S1 start"}  # the arms with pre-registered success and kill rules
SLIT_REF = {"catch_v1": 0.223, "catch_speck": 0.177}  # finding 2 (RESULTS.md, Pre-pilot part 6): F of 37 vs 29 tiles
FAST = dict(d0=0.5, d_min=0.25)

# knob families: readout value y that decodes to the neutral setting (LIFE_ABI.md section 8) in every gene state
KNOB_KO = {
    "chi": {"chi": 0.0},  # no chiral twist
    "tau_tr": {"tau_tr": 0.5},  # traces at 8, the middle of the grid
    "delta": {"delta": 0.0},  # no extra output delay
    "phi": {"phi": 0.0},  # no preference for enclosed sites
    "zeta": {"zeta": 0.0},  # no up/down bias
    "asym": {"asym": -800.0},  # symmetric divisions (sigma(-800) = 0 exactly)
    "a_gain": {"a0": 0.0, "a1": 0.0},  # isotropic input weights (placement keeps its polarity)
    "pol": {"pol0": 0.0, "pol1": 0.0},  # no morphogen direction at all (weights and placement)
    "secretion": {"sec0": -800.0, "sec1": -800.0},  # no morphogen (0.5 sigma(-800) = 0 exactly)
    "p_die": {"p_die": -2.0},  # no apoptosis
    "emit1": {"emit1": -1.0},  # channel 1 silent
}
INPUT_KO = {  # gene inputs (LIFE_ABI.md 7.4 step 3) whose W column is zeroed in every active row
    "in_chem": ("m0", "m1"),
    "in_spikes": ("f", "r0", "r1"),
    "in_n_view": ("n_view",),
    "in_rho": ("rho",),
    "in_planes": ("is_S", "is_M"),
}


def knock(genome: np.ndarray, knobs: dict | None = None, inputs: tuple = ()) -> np.ndarray:
    """A copy of a raw ABI-3 genome with each knob's readout row fixed (A row 0, a0 = y) and each input's W column 0."""
    g = np.array(genome, dtype=np.float32, copy=True)
    if g.shape != (V3.GENOME_SIZE,):
        raise ValueError(f"an ABI-3 genome has {V3.GENOME_SIZE} slots, not {g.shape}")
    sl = V3.GENOME_SLICES
    A = g[sl["A"][0]:sl["A"][1]].reshape(V3.P, G_MAX)
    a0 = g[sl["a0"][0]:sl["a0"][1]]
    for name, y in (knobs or {}).items():
        A[V3.K[name], :] = 0.0
        a0[V3.K[name]] = y
    W = g[sl["W"][0]:sl["W"][1]].reshape(G_MAX, V3.NIN)
    for name in inputs:
        W[:, V3.INPUTS.index(name)] = 0.0
    return g


# ------------------------------------------------------------------------------------------------------- runs
def runs(root: Path) -> list[dict]:
    out = []
    for d in sorted(root.glob("*_hexprism_sex_s*")):
        res = d / "results.jsonl"
        if not res.exists():
            continue
        row = json.loads(res.read_text().splitlines()[0])
        cfg = (d / "config.yaml").read_text()
        world = next(line.split(":", 1)[1].strip() for line in cfg.splitlines() if line.strip().startswith("world: ")
                     and line.split(":", 1)[1].strip() not in ("{}", ""))
        skill = float(next(line.split(":", 1)[1] for line in cfg.splitlines() if line.strip().startswith("skill_at:")))
        out.append(dict(dir=d, name=d.name, control=row["control"], seed=int(row["seed"]), row=row, world=world,
                        skill_at=skill, grown=bool(row["n_cells"] > 4)))
    return out


def genome_of(run: dict) -> np.ndarray:
    _, g = Layout.load(run["dir"] / "best_genome.json")
    return np.asarray(g, dtype=np.float32).reshape(-1)


def body_of(run: dict, genome: np.ndarray | None = None, tag: str = "") -> hb.GrnBody:
    return hb.GrnBody(f"{run['name']}{tag}", genome_of(run) if genome is None else genome)


def ref_preset(world: str) -> str:
    return "catch_speck" if world.startswith("catch_speck") else "catch_v1"


# --------------------------------------------------------------------------------------------------- criteria
def criteria(rs: list[dict]) -> dict:
    out = {}
    for ctl, label in ARMS.items():
        arm = sorted((r for r in rs if r["control"] == ctl), key=lambda r: r["seed"])
        if not arm:
            continue
        F = [r["row"]["F"] for r in arm]
        n = [r["row"]["n_cells"] for r in arm]
        rec = dict(
            label=label, seeds=[r["seed"] for r in arm], world=arm[0]["world"], skill_at=arm[0]["skill_at"],
            F=F, F_se=[r["row"]["F_se"] for r in arm], n_cells=n, n_half=[r["row"]["n_half"] for r in arm],
            growing=[r["row"]["growing"] for r in arm], n_H=[r["row"]["n_H"] for r in arm],
            deaths_per_life=[r["row"].get("deaths_per_life") for r in arm],
            reached=[r["row"]["evals_to_skill"] is not None for r in arm],
            F_final_ge_skill=[f >= arm[0]["skill_at"] for f in F], le4=[c <= 4 for c in n],
            wall_h=[r["row"]["wall_s"] / 3600 for r in arm])
        rec.update(n_reached=sum(rec["reached"]), n_le4=sum(rec["le4"]), F_median=float(np.median(F)),
                   F_mean=float(np.mean(F)))
        if ctl in MAIN:
            rec.update(stage=MAIN[ctl], success=rec["n_reached"] >= 5, kill=rec["n_le4"] >= 8,
                       rule="success: >= 5 of 10 reach skill_at within 500 generations; kill: >= 8 of 10 at <= 4 "
                            "cells")
        out[ctl] = rec
    return out


# --------------------------------------------------------------------------------------------------- dynamics
def dynamics(run: dict) -> dict:
    gens = [json.loads(line) for line in (run["dir"] / "lineage.jsonl").open() if line.startswith('{"gen"')]
    kept = [sum(1 for c in g["children"] if c.get("kept", True)) for g in gens]
    streak = best = 0
    for k in kept:
        streak = streak + 1 if k == 0 else 0
        best = max(best, streak)
    collapse = next((g["gen"] for g in gens if len(g["breeds"]) <= 1), None)
    corr = []
    for g in gens:
        rc = g.get("recheck") or {}
        a, b = np.asarray(rc.get("F_base", []), float), np.asarray(rc.get("F_recheck", []), float)
        if len(a) > 2 and a.std() > 0 and b.std() > 0:
            corr.append(float(np.corrcoef(a, b)[0, 1]))
    dist = {g["gen"]: g["distance"] for g in gens if g["gen"] in (0, 50, len(gens) - 1)}
    return dict(generations=len(gens), kids_kept_mean=float(np.mean(kept)),
                frozen_generations=sum(k == 0 for k in kept),
                longest_frozen=best, one_breed_at=collapse, distance=dist,
                recheck_corr_median=float(np.median(corr)) if corr else None, recheck_corr_gens=len(corr),
                n_active=gens[-1].get("n_active"))


# ---------------------------------------------------------------------------------------------------- lives
class Lives:
    """Per-life F arrays keyed by (body tag, preset, world overrides, n), cached in an npz across invocations."""

    def __init__(self, path: Path, threads: int, reuse: bool):
        self.path, self.threads = path, threads
        self.F = dict(np.load(path)) if reuse and path.exists() else {}

    def __call__(self, org, n: int, preset: str, tag: str | None = None, cells: bool = False, **world) -> np.ndarray:
        """F of each life (``cells``: also the cells alive at the end, as a second column)."""
        key = "|".join([tag or org.name, preset, json.dumps(world, sort_keys=True), str(n)])
        if key not in self.F:
            res = org.run(analysis.fresh_seeds(n, PILOT_SEED0), threads=self.threads, preset=preset, **world)
            self.F[key] = res.ledger[:, [LF, V3.L["n_end"]]].copy()
        return self.F[key] if cells else self.F[key][:, 0]

    def save(self):
        self.path.parent.mkdir(parents=True, exist_ok=True)
        np.savez(self.path, **self.F)


def pt(F) -> dict:
    s = analysis.summary(F)
    return dict(mean=s["mean"], se=s["se"])


def routing(rs: list[dict], lives: Lives) -> dict:
    arm = sorted((r for r in rs if r["control"] == "speck_lmax4"), key=lambda r: r["seed"])
    if not arm:
        return {}
    preset = arm[0]["world"]
    reflex, router = hb.speck_body("reflex@hollow3"), hb.speck_body("router@ring4")
    FR = lives(reflex, ROUTE_LIVES, preset)
    out = dict(lives=ROUTE_LIVES, seeds=f"{PILOT_SEED0} + s", world=preset, reflex=pt(FR),
               router=pt(lives(router, ROUTE_LIVES, preset)), router_minus_reflex=analysis.paired(
                   lives(router, ROUTE_LIVES, preset), FR), seeds_rows={})
    lat = V3.flags("lateral_off")
    for r in arm:
        org = body_of(r)
        Fg = lives(org, ROUTE_LIVES, preset)
        Fl = lives(org, ROUTE_LIVES, preset, tag=org.name + "+lateral_off", flags=lat)
        lead, lead_lat = analysis.paired(Fg, FR), analysis.paired(Fl, FR)
        beats = lead["mean"] > Z * lead["se"]
        removed = (lead["mean"] - lead_lat["mean"]) / lead["mean"] if lead["mean"] > 0 else None
        out["seeds_rows"][r["seed"]] = dict(F=pt(Fg), lateral_off=pt(Fl), lead=lead, lead_lateral_off=lead_lat,
                                            beats_reflex=bool(beats), lead_removed=removed,
                                            router=bool(beats and removed is not None and removed >= 0.5))
    out["n_router"] = sum(v["router"] for v in out["seeds_rows"].values())
    out["n_beats_reflex"] = sum(v["beats_reflex"] for v in out["seeds_rows"].values())
    return out


# ------------------------------------------------------------------------------------------------------ slit
NB = lattice.offsets("hex")
D1 = [(0, 0)] + NB


def closing1(P) -> set:
    """Morphological closing of the columns P by the radius-1 hex disk (P kept)."""
    P = set(P)
    dil = {(a + da, b + db) for a, b in P for da, db in D1}
    return {s for s in dil if all((s[0] + da, s[1] + db) in dil for da, db in D1)} | P


def _pieces(P) -> list[set]:
    P, out = set(P), []
    while P:
        s = P.pop()
        comp, todo = {s}, [s]
        while todo:
            a, b = todo.pop()
            for da, db in NB:
                x = (a + da, b + db)
                if x in P:
                    P.remove(x)
                    comp.add(x)
                    todo.append(x)
        out.append(comp)
    return out


def _hull_tiles(comp: set) -> set:
    pts = sorted({lattice.to_xy("hex", a, b) for a, b in comp})
    if len(pts) <= 2:
        return set(comp)

    def cross(o, a, b):
        return (a[0] - o[0]) * (b[1] - o[1]) - (a[1] - o[1]) * (b[0] - o[0])

    lo, up = [], []
    for p in pts:
        while len(lo) >= 2 and cross(lo[-2], lo[-1], p) <= 1e-9:
            lo.pop()
        lo.append(p)
    for p in reversed(pts):
        while len(up) >= 2 and cross(up[-2], up[-1], p) <= 1e-9:
            up.pop()
        up.append(p)
    H = lo[:-1] + up[:-1]
    A, B = [a for a, _ in comp], [b for _, b in comp]
    out, span = set(comp), 2 * (max(B) - min(B)) + 2
    if len(H) < 3:
        return out
    for a in range(min(A) - span, max(A) + span + 1):
        for b in range(min(B), max(B) + 1):
            x = lattice.to_xy("hex", a, b)
            if all(cross(H[i], H[(i + 1) % len(H)], x) >= -1e-9 for i in range(len(H))):
                out.add((a, b))
    return out


def footprints(P) -> tuple[int, int, int, int]:
    """(columns, filled footprint, closing then fill, per-piece hull then fill) of the column set P."""
    P = set(P)
    hull = set().union(*[_hull_tiles(c) for c in _pieces(P)]) if P else set()
    return len(P), spec.filled_footprint(P), spec.filled_footprint(closing1(P)), spec.filled_footprint(hull)


def slit(rs: list[dict], threads: int) -> dict:
    out = {}
    for r in (r for r in rs if r["grown"]):
        org = body_of(r)
        res = org.run(analysis.fresh_seeds(SLIT_LIVES, PILOT_SEED0), threads=threads, fate_cap=1 << 13,
                      preset=r["world"])
        fp = []
        for i in range(SLIT_LIVES):
            cells = analysis.final_cells(res.fates(i)[0])
            if cells:
                fp.append(footprints({(a, b) for a, b, z in cells}))
        ref = SLIT_REF[ref_preset(r["world"])]
        k = ref / math.log(math.sqrt(37 / 29))
        gain = [k * 0.5 * math.log(c / f) for _, f, c, _ in fp]  # F the filled law's discount buys over the closing
        out[r["name"]] = dict(lives=len(fp), encloses=sum(f != n for n, f, _, _ in fp),
                              closing_changes=sum(c != f for _, f, c, _ in fp),
                              hull_changes=sum(h != f for _, f, _, h in fp),
                              mean=[float(np.mean([x[j] for x in fp])) for j in range(4)],
                              gain_est_mean=float(np.mean(gain)), gain_est_max=float(np.max(gain)),
                              reopens=bool(np.mean(gain) > 0.1))
    return out


# ----------------------------------------------------------------------------------------- knockouts and fast
def knockouts(rs: list[dict], lives: Lives) -> dict:
    out = {}
    for r in (r for r in rs if r["grown"]):
        g = genome_of(r)
        base = lives(body_of(r, g), KO_LIVES, r["world"], cells=True)
        rec = dict(intact=dict(pt(base[:, 0]), n_end=float(base[:, 1].mean())))
        variants = [(k, dict(knobs=v)) for k, v in KNOB_KO.items()] + [(k, dict(inputs=v)) for k, v in INPUT_KO.items()]
        for name, kw in variants:
            F = lives(body_of(r, knock(g, **kw), f"-{name}"), KO_LIVES, r["world"], cells=True)
            rec[name] = dict(analysis.paired(F[:, 0], base[:, 0]), n_end=float(F[:, 1].mean()))
        out[r["name"]] = rec
    return out


def fast(rs: list[dict], lives: Lives) -> dict:
    out = {}
    for ref in ("reflex@hollow3", "router@ring4"):
        org = hb.speck_body(ref)
        base = lives(org, KO_LIVES, "catch_speck_l4")
        out[ref] = dict(base=pt(base), fast=analysis.paired(lives(org, KO_LIVES, "catch_speck_l4", **FAST), base))
    for r in (r for r in rs if r["grown"]):
        org = body_of(r)
        base = lives(org, KO_LIVES, r["world"])
        out[r["name"]] = dict(base=pt(base), fast=analysis.paired(lives(org, KO_LIVES, r["world"], **FAST), base))
    return out


# --------------------------------------------------------------------------------------------------- report
def _f(x, nd=2) -> str:
    return "-" if x is None else f"{x:+.{nd}f}"


def report(res: dict) -> str:
    md = ["# BODY-1 pilot analysis", "", f"Generated {res['time']} from `{res['root']}` (git {res['git']}).", ""]
    if "criteria" in res:
        md += ["## Criteria (pre-registered, RESULTS.md Pre-pilot part 10)", "",
               "| arm | seeds | final F by seed | reached skill | <= 4 cells | median F | verdict |",
               "|---|---|---|---|---|---|---|"]
        for _ctl, c in res["criteria"].items():
            v = "-"
            if "stage" in c:
                v = ("SUCCESS" if c["success"] else "no success") + (", KILL" if c["kill"] else ", not killed")
            md.append(f"| {c['label']} | {len(c['seeds'])} | {' '.join(f'{x:+.2f}' for x in c['F'])} | "
                      f"{c['n_reached']} (skill {c['skill_at']:g}) | {c['n_le4']} | {c['F_median']:+.2f} | {v} |")
        md += ["", "GB11 (reported): n_half / n_cells (final best, T 1024) and the share still growing:", ""]
        for _ctl, c in res["criteria"].items():
            md.append(f"- {c['label']}: " + "; ".join(
                f"s{s} {h:.0f}/{n:.0f} ({g:.2f})" for s, h, n, g in zip(c["seeds"], c["n_half"], c["n_cells"],
                                                                         c["growing"])))
    if "dynamics" in res:
        md += ["", "## Selection dynamics", "", "| run | kids kept / gen | frozen gens (longest) | one breed at | "
               "distance g0 / g50 / end | 3- vs 4-life rank corr (median) |", "|---|---|---|---|---|---|"]
        for name, d in res["dynamics"].items():
            dist = " / ".join(f"{v:.1f}" for v in d["distance"].values())
            md.append(f"| {name} | {d['kids_kept_mean']:.1f} | {d['frozen_generations']} ({d['longest_frozen']}) | "
                      f"{d['one_breed_at']} | {dist} | {_f(d['recheck_corr_median'])} |")
    if res.get("routing"):
        ro = res["routing"]
        md += ["", "## S1 routing (pre-registered)", "",
               f"{ro['lives']} fresh lives ({ro['seeds']}), {ro['world']}: reflex@hollow3 {ro['reflex']['mean']:+.3f} "
               f"+- {ro['reflex']['se']:.3f}; router@ring4 {ro['router']['mean']:+.3f} +- {ro['router']['se']:.3f}.",
               "", "| seed | F | lead over reflex (z) | lateral_off F | lead removed | router |",
               "|---|---|---|---|---|---|"]
        for s, v in ro["seeds_rows"].items():
            md.append(f"| {s} | {v['F']['mean']:+.3f} | {v['lead']['mean']:+.3f} ({v['lead']['z']:+.1f}) | "
                      f"{v['lateral_off']['mean']:+.3f} | {_f(v['lead_removed'])} | {v['router']} |")
        md.append(f"\nEvolved routers: {ro['n_router']} of {len(ro['seeds_rows'])} "
                  f"(beat the reflex: {ro['n_beats_reflex']}).")
    if res.get("slit"):
        md += ["", "## Slit check (pre-registered)", "",
               "| run | lives | enclose | closing / hull change | mean cols / "
               "fill / closing / hull | est. gain mean (max) | reopens |", "|---|---|---|---|---|---|---|"]
        for name, s in res["slit"].items():
            md.append(f"| {name} | {s['lives']} | {s['encloses']} | {s['closing_changes']} / {s['hull_changes']} | "
                      f"{' / '.join(f'{m:.1f}' for m in s['mean'])} | {s['gain_est_mean']:+.3f} "
                      f"({s['gain_est_max']:+.3f}) | {s['reopens']} |")
    if res.get("knockouts"):
        names = list(KNOB_KO) + list(INPUT_KO)
        md += ["", f"## Knockouts (paired dF on {KO_LIVES} lives; z in brackets when |z| >= 3; cells at the end "
               "after /)",
               "",
               "| run | intact | " + " | ".join(names) + " |", "|---|---|" + "---|" * len(names)]
        for run, k in res["knockouts"].items():
            cells = [f"{k[n]['mean']:+.2f}" + (f" ({k[n]['z']:+.0f})" if abs(k[n]["z"]) >= 3 else "")
                     + f" /{k[n]['n_end']:.0f}" for n in names]
            md.append(f"| {run} | {k['intact']['mean']:+.2f} /{k['intact']['n_end']:.0f} | " + " | ".join(cells) + " |")
    if res.get("fast"):
        md += ["", f"## Faster conduction ({FAST}; paired dF on {KO_LIVES} lives)", "", "| body | F | dF fast (z) |",
               "|---|---|---|"]
        for name, v in res["fast"].items():
            md.append(f"| {name} | {v['base']['mean']:+.3f} | {v['fast']['mean']:+.3f} ({v['fast']['z']:+.1f}) |")
    return "\n".join(md) + "\n"


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    ap.add_argument("--root", default="outputs/catch_pilot")
    ap.add_argument("--out", default="results/catch_pilot")
    ap.add_argument("--threads", type=int, default=8)
    ap.add_argument("--only", default="criteria,dynamics,routing,slit,knockouts,fast")
    ap.add_argument("--lives", default="outputs/catch_pilot_analysis/lives.npz", help="per-life F cache")
    ap.add_argument("--reuse", action="store_true", help="read cached per-life F arrays back")
    a = ap.parse_args(argv)
    import subprocess
    git = subprocess.run(["git", "rev-parse", "--short", "HEAD"], capture_output=True, text=True).stdout.strip()
    only = set(a.only.split(","))
    rs = runs(Path(a.root))
    out_dir = Path(a.out)
    out_dir.mkdir(parents=True, exist_ok=True)
    jpath = out_dir / "analysis.json"
    res = json.loads(jpath.read_text()) if jpath.exists() else {}
    res.update(time=time.strftime("%Y-%m-%d %H:%M"), root=a.root, git=git, runs=len(rs))
    lives = Lives(Path(a.lives), a.threads, a.reuse)
    steps = dict(criteria=lambda: criteria(rs), dynamics=lambda: {r["name"]: dynamics(r) for r in rs},
                 routing=lambda: routing(rs, lives), slit=lambda: slit(rs, a.threads),
                 knockouts=lambda: knockouts(rs, lives), fast=lambda: fast(rs, lives))
    for name, fn in steps.items():
        if name in only:
            t = time.time()
            res[name] = fn()
            lives.save()
            jpath.write_text(json.dumps(res, indent=1, default=str))
            print(f"{name}: {time.time() - t:.0f} s", flush=True)
    (out_dir / "analysis.md").write_text(report(res))
    print(f"wrote {jpath} and {out_dir / 'analysis.md'}")


if __name__ == "__main__":
    main()
