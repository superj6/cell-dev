"""Pre-registered gates of the one-life engine on hex with Q10 (docs/ONE_LIFE_DESIGN.md, PRE-REGISTERED GATES;
results and plain-language verdicts in docs/LIFE_GATES.md): G1-G10, and the square8 size curve (S8).

    python scripts/life_gates.py [--gates G1,G2,...] [--threads 4] [--out outputs/life_gates/gates.json]

Re-registration (migration step 3). The registered G1, G3 and G4 values were measured by the prototype on 36 lives
per point whose frozen physics was keyed to the seed, so every organism registered at 91 cells shared the same 36
favourable bodies (F(91) = +0.928 is a high draw). Every gate here measures on fresh lives, seeds
``analysis.FRESH_SEED0 + s`` (at least 144 per point for G1, G3 and G4), shared by every size, organism and
condition, so differences are paired. Screens that choose candidates use ``analysis.SCREEN_SEED0 + s`` and the chosen
candidates are then measured on the fresh lives. The old registered values are kept in each gate's ``registered``.

Each gate measures first and judges second: ``gate_gN`` returns the measurements, and ``judge_gN`` turns them into
``checks`` and ``passed``, so tests can re-judge the stored numbers. Lives are deterministic given their seeds and
independent of thread count, so a rerun on the same kernel library reproduces gates.json exactly.
"""
from __future__ import annotations

import argparse
import hashlib
import itertools
import json
import math
import platform
import sys
import time
from dataclasses import replace
from datetime import datetime, timezone
from pathlib import Path

import numpy as np

repo_root = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(repo_root))

from src.life import analysis, build, spec  # noqa: E402
from src.life import handbuilt as hb  # noqa: E402

# ------------------------------------------------------------------------------------------------ registered
# docs/ONE_LIFE_DESIGN.md (PRE-REGISTERED GATES) and scratchpad bounded_task.json (task_bell e7, e8, e15, e16; 36 lives
# per point unless stated). Kept for the record; the gates below re-measure them on fresh lives.
REGISTERED = dict(
    G1=dict(F=0.0326, phenotype=(1.875, 8.0, 2.0, 1.0)),
    G2=dict(lives=36, L0={2: (-0.004, 0.002), 3: (-0.035, 0.002), 7: (-0.137, 0.001)}, zero_income_from=19,
            ga="A 50-generation GA with messages off stays a lone cell (evolution side, not run here)."),
    G3=dict(lives=36, n_star=91, resolution=1e-3, curve={
        1: (0.033, 0.0), 2: (0.041, 0.001), 3: (0.072, 0.001), 7: (0.148, 0.003), 19: (0.346, 0.008),
        37: (0.558, 0.017), 61: (0.730, 0.034), 91: (0.928, 0.058), 127: (0.465, 0.151), 169: (-0.062, 0.219),
        217: (-0.625, 0.245), 271: (-2.442, 0.285), 331: (-3.399, 0.325)}),
    G4=dict(lives=36, chain={"R25-v1": (91, 0.928), "R25-v1/no-LBT": (61, 0.573), "R25-v1/naive": (37, 0.384),
                             "L1": (3, 0.046), "L0": (1, 0.033)},
            ladder={"L4": (91, 0.905), "L3": (91, 0.745), "L2": (37, 0.434), "L1": (3, 0.046), "L0": (1, 0.033)}),
    G5=dict(lives=12, organism="L4", no_frozen={91: 1.707, 169: 2.923, 271: 2.69, 397: 5.936, 547: 5.239},
            default={91: 0.90, 169: 0.53, 271: -2.67, 397: -4.87, 547: -7.79}),
    G6=dict(income_per_cell_e3=(35.0, 1.0)),
    G7=dict(lone_rate_e3=54.0),
    G8=dict(max_rel=1e-3, prototype_rel=(3e-4, 8e-4)),
    G9=dict(lives=36, cap=91, z=2.0),
    G10=dict(d4_nview_weaker=0.23, d5={"old grid best (t_ref 2)": 0.693, "R25-v1 (t_ref 2.5)": 0.928}),
    S8=dict(note="nothing registered: G10 asks only that the square8 size curve be measured before any square8 run"),
)

# The prototype re-measured on 2026-10-07 (task_bell/bell3.c with b3.py, unchanged).
# G1: every lone phenotype with b > 1 and kappa > 0, 64 lives (seeds 0..63); the 10 best and the registered pump.
# G3: R25-v1 exactly as task_bell e16 (low rate 0.05), 1152 lives per size, seeds 400000 + 91 N + s.
PROTOTYPE = dict(
    G1=dict(lives=64, top=[
        ((1.625, 4.0, 4.0, 1.0), 0.032795, 1.2e-05), ((1.5, 4.0, 3.5, 1.0), 0.032793, 1.2e-05),
        ((1.125, 2.0, 3.5, 1.0), 0.032793, 1.2e-05), ((1.375, 4.0, 2.5, 1.0), 0.032702, 1.2e-05),
        ((1.75, 4.0, 4.0, 1.0), 0.032692, 1.2e-05), ((2.0, 8.0, 2.5, 1.0), 0.032644, 1.5e-05),
        ((1.75, 8.0, 1.0, 1.0), 0.032640, 1.3e-05), ((1.375, 4.0, 3.0, 1.0), 0.032636, 1.6e-05),
        ((1.875, 8.0, 2.0, 1.0), 0.032633, 1.9e-05), ((1.25, 4.0, 1.5, 1.0), 0.032629, 1.5e-05)]),
    G3=dict(lives=1152, seed0=400000, resolution=1e-4, curve={
        1: (0.0326, 0.0), 2: (0.0396, 0.0003), 3: (0.0715, 0.0002), 7: (0.1436, 0.0006), 19: (0.3464, 0.0012),
        37: (0.5591, 0.0038), 61: (0.7202, 0.0081), 91: (0.7645, 0.0149), 127: (0.4891, 0.0272),
        169: (-0.1045, 0.0396), 217: (-0.8088, 0.0497), 271: (-1.7362, 0.0599), 331: (-2.8461, 0.0667)}),
    # The G3 port reference (review fix, 2026-10-07): the 1152-life curve above is itself a ~2.3 SE draw at 91 and
    # 169, and bell3 draws Gaussian frozen normals where the kernel draws Irwin-Hall(12) ones (LIFE_ABI.md 15.13).
    # Pooled reference: bell3.c, rule unchanged, with Irwin-Hall(12) frozen normals (the milestone-1 harness
    # gates/b3q.py, ih=1, Q10 off), 4608 lives per size on fresh prototype seeds 9,000,000 + s. The Gaussian run on
    # the same seeds is kept for the record: Irwin-Hall minus Gaussian is +0.0007 +- 0.0024 (37), +0.0060 +- 0.0111
    # (91) and +0.0278 +- 0.0275 (169), unpaired.
    G3_port=dict(lives=4608, seeds="9,000,000 + s", normals="Irwin-Hall(12)", resolution=1e-6, curve={
        37: (0.562913, 0.001651), 91: (0.732366, 0.007786), 169: (0.025079, 0.019358)},
        gaussian={37: (0.562211, 0.001772), 91: (0.726345, 0.007904), 169: (-0.002715, 0.019520)}),
)

# ABI 1 (kernel life_6ed6129a0071cbfe.so, gates.json of 2026-10-07): the gene network had a flank_best / 2 input and
# R25-v1's genome gated division on it (flank_best = 2). ABI 2 removed that input (LIFE_ABI.md 15.32), so these GRN
# measurements cannot be rerun; they are kept as the evidence for the removal. Same fresh lives as every gate.
ABI1 = dict(
    kernel="life_6ed6129a0071cbfe.so",
    G9=dict(lives=288, gate="flank_best = 2", points={  # (GRN mean, SE, z against the program)
        37: (0.563413, 0.007876, -0.224), 91: (0.698449, 0.030079, 0.036), 169: (-0.174481, 0.082596, 0.373)},
        minimal_91=(0.667873, 0.054242, -0.592)),
    G10=dict(lives=144, d4_grn={  # F* (over 61-127), its SE, n*, and the paired step from the flank-gate genome
        "flank gate, flank placement": (0.752900, 0.040351, 91, None),
        "n_view gate, random placement": (0.638136, 0.029417, 61, (0.114765, 0.039875, 2.878)),
        "n_view gate, flank placement": (0.754151, 0.042269, 91, (-0.001250, 0.012737, -0.098))}),
    S8=dict(lives=144, N=121, grn=(1.109347, 0.067881, -0.452)),
    G6=dict(income_per_cell_e3=(32.570, 1.358), ratio=0.0417),
)

# ------------------------------------------------------------------------------------------------ protocol
LIVES = 144  # fresh lives per point (the re-registration rule: at least 144)
LIVES_R25 = 288  # the reference curve R25-v1 (G3), and G9 against it
LIVES_G5 = 48  # G5 conditions (bodies up to 547 cells; the effect is many SE)
SCREEN_LIVES = 16  # D5 and square8 screens (screen seeds)
G2_SCREEN_LIVES = 8
Z = 2.0  # "within 2 SE" / "separated by more than 2 SE"

SIZES_R25 = (1, 2, 3, 7, 19, 37, 61, 91, 127, 169, 217, 271, 331)  # complete hexagons; the registered grid
SIZES_ABL = (1, 2, 3, 7, 19, 37, 61, 91, 127, 169)  # G4 ablations and the L2-L4 ladder
SIZES_SMALL = (1, 2, 3, 7, 19, 37)  # L0, L1 (registered n* 1 and 3)
SIZES_G2 = (2, 3, 7, 19)
SIZES_G5 = (91, 169, 271, 397, 547)
SIZES_D4 = (37, 61, 91, 127)
SIZES_D5 = (61, 91, 127)
SIZES_S8 = (1, 9, 25, 49, 81, 121, 169, 225, 289)  # complete squares (2r + 1)^2 on square8
S8_SCREEN_N = 121

G1_VALUE_TOL = 0.02  # relative tolerance on the best lone cell's F
G1_PORT_TOL = 1e-4  # |F_kernel - F_prototype| per lone phenotype (largest measured gap among them: 5e-5)
G3_SIZES = (37, 91, 169)  # registration-seed check: rising side, registered optimum, falling side
G3_REG_Z = 2.0
G3_PORT_Z = Z  # the repo's 2 SE rule (it was 3 SE against the noisier 1152-life reference)
G3_PORT_LIVES = 576
G6_COLLAPSE = 0.1  # spikes undelivered: income per cell at most 10% of the intact twin's
G2_ZERO_INCOME_E3 = 1.0  # "zero income" for messages-off bodies of 19 cells or more: below 1e-3 per cell-unit
G8_CASES = ((1, 300.0), (37, 300.0), (91, 400.0))  # (oracle cap, T), as in the prototype's audit.py
G8_SEEDS = (11, 12)

CONTACTS_OFF = spec.FLAGS["contacts_off"]
LOCKSTEP = spec.FLAGS["lockstep"]
T_HALF = 512.0

_THREADS = [4]  # thread count for the cached runs (results never depend on it)


def _threads() -> int:
    return _THREADS[0]


# ------------------------------------------------------------------------------------------------ cached lives
KEEP = ("F", "income", "live_time", "n_end", "last_birth", "claims", "spikes", "contact_events", "status", "births")
_CACHE: dict = {}


def _blob(org) -> bytes:
    a = org.program if isinstance(org, hb.Organism) else org.genome
    return hashlib.sha1(np.ascontiguousarray(a).tobytes()).digest()


def lives(org, N: int, n: int, *, seed0: int = analysis.FRESH_SEED0, **world) -> dict:
    """Per-life ledger columns of ``n`` lives of ``org`` under oracle cap ``N`` (0 = none), seeds seed0 + s.

    Runs are cached by (table, flags, cap, world, seed0); asking for more lives runs only the missing seeds, so
    every gate that uses a point sees the same lives, and organisms with identical tables share them.
    """
    key = (type(org).__name__, _blob(org), int(org.flags), int(N), seed0, tuple(sorted(world.items())))
    have = _CACHE.get(key)
    m = 0 if have is None else len(have["F"])
    if m < n:
        res = org.run(analysis.fresh_seeds(n, seed0, first=m), cap=N, threads=_threads(), **world)
        new = {k: np.array(res[k]) for k in KEEP}
        have = new if have is None else {k: np.concatenate([have[k], new[k]]) for k in KEEP}
        _CACHE[key] = have
    return {k: v[:n] for k, v in have.items()}


def curve(org, sizes, n: int, **world) -> dict[int, dict]:
    return {int(N): lives(org, N, n, **world) for N in sizes}


def points(cur: dict[int, dict]) -> dict[int, dict]:
    return {N: analysis.point(r) for N, r in cur.items()}


def best(cur: dict[int, dict]) -> dict:
    return analysis.best_size({N: r["F"] for N, r in cur.items()})


def _at(d: dict, N):
    """``d[N]`` for a size key that may be an int (in memory) or a str (after a JSON round trip)."""
    return d[N] if N in d else d[str(N)]


def _pheno(c) -> dict:
    return dict(zip(hb.LONE_AXES, (float(x) for x in c)))


def _zref(rec: dict, ref: tuple, resolution: float) -> float:
    # references are rounded to ``resolution``; the rounding error (sd resolution / sqrt 12) joins their SE
    return analysis.z_diff(rec, dict(mean=ref[0], se=math.hypot(ref[1], resolution / math.sqrt(12.0))))


# ------------------------------------------------------------------------------------------------------- G1
_LONE: dict = {}


def lone_fresh(n: int = LIVES) -> dict:
    """Every lone phenotype with b >= 1 and kappa > 0 on ``n`` fresh lives (the others are inert: b < 1 never fires
    and kappa = 0 earns nothing, which G1's registration screen checks on every phenotype)."""
    if n not in _LONE:
        combos, progs = hb.lone_grid()
        idx = [i for i, c in enumerate(combos) if c[0] >= 1.0 and c[3] > 0.0]
        seeds = [s for _ in idx for s in analysis.fresh_seeds(n)]
        res = build.run(spec.world(flags=hb.PROGRAM_MODE), seeds, programs=progs[idx],
                        genome_of=np.repeat(np.arange(len(idx)), n), threads=_threads())
        _LONE[n] = dict(combos=[combos[i] for i in idx], F=res["F"].reshape(len(idx), n),
                        rate=analysis.income_rate(res).reshape(len(idx), n))
    return _LONE[n]


def lone_reference() -> dict:
    """The re-registered lone cell: the best fresh mean F, its lives, and the lone income-rate bounds (G2, G7)."""
    L = lone_fresh()
    mean = L["F"].mean(axis=1)
    i = int(np.argmax(mean))
    rates = L["rate"].mean(axis=1)
    return dict(F=float(mean[i]), lives=L["F"][i], phenotype=L["combos"][i], rate_best=float(rates[i]),
                rate_max_phenotype=float(rates.max()), rate_max_life=float(L["rate"].max()),
                rate_argmax=L["combos"][int(np.argmax(rates))])


def gate_g1(threads: int = 4, lives: int = 64, fresh_lives: int = LIVES) -> dict:
    """Best lone cell, exhaustive over the knobs that matter for a lone cell (b, tau_m, t_ref, kappa): the
    registration screen (all 5280 phenotypes, seeds 0..63) and the re-registration on fresh lives."""
    _THREADS[0] = threads
    combos, progs = hb.lone_grid()
    seeds = [s for _ in combos for s in range(lives)]
    res = build.run(spec.world(flags=hb.PROGRAM_MODE), seeds, programs=progs,
                    genome_of=np.repeat(np.arange(len(combos)), lives), threads=threads)
    F = res["F"].reshape(len(combos), lives)
    mean = F.mean(axis=1)
    se = F.std(axis=1, ddof=1) / math.sqrt(lives)
    order = np.argsort(-mean, kind="stable")
    index = {c: i for i, c in enumerate(combos)}
    best_i = int(order[0])
    reg = REGISTERED["G1"]
    pump = index[reg["phenotype"]]

    def entry(i):
        return dict(phenotype=_pheno(combos[i]), F=float(mean[i]), se=float(se[i]),
                    rank=int(np.nonzero(order == i)[0][0]) + 1)

    # knobs held neutral in the grid must not change a lone cell's life at all
    row = spec.theta(**_pheno(combos[best_i]))
    busy = hb.with_knobs(row, w0=-1, w1=1, emit0=1, emit1=1, delta=2, tau_tr=16, phi=2, pol0=1, pol1=-1, a0=1, a1=1,
                         chi=1, asym=0.9)
    plain = hb.lone(row).run(list(range(4)))
    other = hb.lone(busy).run(list(range(4)))
    neutral = bool(np.array_equal(plain.ledger.view(np.uint64), other.ledger.view(np.uint64))
                   and np.array_equal(plain.hashes, other.hashes))
    led = {k: res[k].reshape(len(combos), lives) for k in ("income", "live_time", "spikes")}
    groups = dict(sub_threshold=[i for i, c in enumerate(combos) if c[0] < 1.0],
                  b_equal_1=[i for i, c in enumerate(combos) if c[0] == 1.0],
                  no_contraction=[i for i, c in enumerate(combos) if c[3] == 0.0])
    inert = {k: dict(phenotypes=len(v), max_F=float(mean[v].max()), max_spikes=float(led["spikes"][v].max()),
                     max_income=float(led["income"][v].max())) for k, v in groups.items()}
    port = []
    for c, f, _se in PROTOTYPE["G1"]["top"]:
        i = index[c]
        port.append(dict(phenotype=_pheno(c), kernel=float(mean[i]), prototype=f, diff=float(mean[i] - f),
                         ok=bool(abs(mean[i] - f) <= G1_PORT_TOL)))
    # re-registration on fresh lives
    L = lone_fresh(fresh_lives)
    fm = L["F"].mean(axis=1)
    fse = L["F"].std(axis=1, ddof=1) / math.sqrt(fresh_lives)
    ford = np.argsort(-fm, kind="stable")
    fidx = {c: i for i, c in enumerate(L["combos"])}
    fb = int(ford[0])

    def fentry(i):
        return dict(phenotype=_pheno(L["combos"][i]), F=float(fm[i]), se=float(fse[i]),
                    rank=int(np.nonzero(ford == i)[0][0]) + 1)

    flat = [i for i in range(len(fm)) if analysis.paired(L["F"][fb], L["F"][i])["z"] <= Z]
    near = int(np.sum(fm >= 0.99 * fm[fb]))
    ref = lone_reference()
    out = dict(
        registered=dict(F=reg["F"], phenotype=_pheno(reg["phenotype"])),
        criteria=(f"value: |F_best - {reg['F']}| <= {G1_VALUE_TOL:.0%} on the registration screen and on fresh lives; "
                  f"port: |F_kernel - F_prototype| <= {G1_PORT_TOL:g} for the prototype's 10 best lone phenotypes; "
                  "neutral_knobs: knobs outside the grid leave the best cell's life bitwise unchanged; "
                  "inert_cells_earn_nothing: b < 1 costs exactly c_live and kappa = 0 earns no income. The argmax is "
                  "reported, not gated (the top is flat)."),
        grid=dict(axes={k: [float(x) for x in v] for k, v in hb.LONE_AXES.items()}, phenotypes=len(combos),
                  lives=lives, seeds=f"0..{lives - 1}"),
        best=entry(best_i), registered_phenotype=entry(pump), top=[entry(int(i)) for i in order[:10]],
        inert=inert, income_rate_best=float(np.mean(led["income"][best_i] / led["live_time"][best_i])),
        port=port, neutral_knobs=neutral,
        reregistered=dict(
            lives=fresh_lives, seeds=f"{analysis.FRESH_SEED0} + s, s < {fresh_lives}",
            phenotypes=len(L["combos"]), phenotype_set="b >= 1 and kappa > 0 (all others are inert)",
            best=fentry(fb), registered_phenotype=fentry(fidx[reg["phenotype"]]),
            top=[fentry(int(i)) for i in ford[:10]], flat_top_phenotypes=len(flat), within_1pct_phenotypes=near,
            income_rate_best_e3=1e3 * ref["rate_best"], income_rate_max_phenotype_e3=1e3 * ref["rate_max_phenotype"],
            income_rate_max_phenotype=_pheno(ref["rate_argmax"]), income_rate_max_life_e3=1e3 * ref["rate_max_life"]),
        notes=[
            "The grid optimum is flat in value (within_1pct_phenotypes lie within 1% of the best) but resolved: lone "
            "lives share their frozen physics across phenotypes, so paired differences are tiny and only "
            "flat_top_phenotypes lie within 2 paired SE of the best.",
            "The prototype bell3.c, re-measured on the same v1 grid, has the same argmax (b 1.625, tau_m 4, t_ref 4) "
            "at +0.03280 and ranks the registered pump 9th at +0.03263: the registered +0.0326 is the pump's F.",
            "Over all 960 lone phenotypes with b > 1 and kappa > 0, kernel minus prototype has RMS z 0.38 and a "
            "largest gap of 1.8e-4 (64 lives each; measured 2026-10-07): no port error at the lone-cell level.",
            "b = 1 exactly is not silent: the Q10 re-anchor at the cell's own tick rounds a value in [1 - 2^-11, 1) "
            "up to 1, which fires (LIFE_ABI.md 15.6), so 'tonic iff b > 1' holds only for b != 1.",
        ],
    )
    return judge_g1(out)


def judge_g1(g: dict) -> dict:
    reg = g["registered"]["F"]
    fresh = g["reregistered"]["best"]["F"]
    g["checks"] = dict(value=bool(abs(g["best"]["F"] - reg) <= G1_VALUE_TOL * reg),
                       fresh_value=bool(abs(fresh - reg) <= G1_VALUE_TOL * reg),
                       port=all(p["ok"] for p in g["port"]), neutral_knobs=bool(g["neutral_knobs"]),
                       registered_phenotype_within_1pct=bool(g["reregistered"]["registered_phenotype"]["F"]
                                                             >= 0.99 * fresh),
                       argmax_matches_registration=g["best"]["phenotype"] == g["registered"]["phenotype"],
                       inert_cells_earn_nothing=bool(g["inert"]["sub_threshold"]["max_F"] == -spec.COSTS["c_live"]
                                                     and g["inert"]["no_contraction"]["max_income"] == 0.0))
    c = g["checks"]
    g["passed"] = bool(c["value"] and c["fresh_value"] and c["port"] and c["neutral_knobs"]
                       and c["inert_cells_earn_nothing"])
    return g


# ------------------------------------------------------------------------------------------------------- G2
def mo_body(row, name: str) -> hb.Organism:
    """A messages-off body: one phenotype in every row, layered growth, spikes never delivered (contacts_off)."""
    return hb.grower(name, row, row, lbt=False, layered=True, p_div=0.5, p_div_lo=1 / 16, flags=CONTACTS_OFF,
                     about="messages-off search (G2)")


_G2: dict = {}


def g2_candidates(per_size: int = 3) -> dict:
    """Screen every homogeneous lone-capable phenotype (b > 1, kappa > 0) as a messages-off body at 2, 3 and 7 cells
    (screen seeds); return the ``per_size`` best at each size."""
    if "out" not in _G2:
        combos = [c for c in itertools.product(*hb.LONE_AXES.values()) if c[0] > 1.0 and c[3] > 0.0]
        progs = np.stack([mo_body(spec.theta(b=b, tau_m=t, t_ref=r, kappa=k), "x").program for b, t, r, k in combos])
        sizes = (2, 3, 7)
        seeds = analysis.fresh_seeds(G2_SCREEN_LIVES, analysis.SCREEN_SEED0)
        ws, gof, ss = [], [], []
        for i in range(len(combos)):
            for N in sizes:
                for s in seeds:
                    ws.append(N)
                    gof.append(i)
                    ss.append(s)
        base = spec.world(flags=hb.PROGRAM_MODE | CONTACTS_OFF)
        worlds = [replace(base, oracle_cap=N) for N in ws]
        res = build.run(worlds, ss, programs=progs, genome_of=gof, threads=_threads())
        F = res["F"].reshape(len(combos), len(sizes), len(seeds)).mean(axis=2)
        chosen, screen = [], {}
        for j, N in enumerate(sizes):
            order = np.argsort(-F[:, j], kind="stable")[:per_size]
            screen[N] = [dict(phenotype=_pheno(combos[i]), F_screen=float(F[i, j])) for i in order]
            chosen += [combos[i] for i in order if combos[i] not in chosen]
        _G2["out"] = dict(screened=len(combos), sizes=list(sizes), lives=len(seeds), top=screen,
                          chosen=[_pheno(c) for c in chosen],
                          organisms=[mo_body(spec.theta(b=b, tau_m=t, t_ref=r, kappa=k),
                                             f"msg-off b={b} tau={t} tref={r} k={k}") for b, t, r, k in chosen])
    return _G2["out"]


def g2_plan() -> list[tuple]:
    cand = g2_candidates()
    lone_best_body = mo_body(spec.theta(**_pheno(lone_reference()["phenotype"])), "msg-off lone-best body")
    plan = [(hb.L0, SIZES_SMALL[1:]), (lone_best_body, SIZES_SMALL[1:])]
    plan += [(o, SIZES_G2) for o in cand["organisms"]]
    return plan


def gate_g2(threads: int = 4) -> dict:
    """The best messages-off body is no better than a lone cell at every N >= 2."""
    _THREADS[0] = threads
    ref = lone_reference()
    cand = g2_candidates()
    bodies = {}
    for org, sizes in g2_plan():
        bodies[org.name] = points(curve(org, sizes, LIVES))
    best_by_N = {}
    for N in sorted({N for p in bodies.values() for N in p}):
        name = max((k for k in bodies if N in bodies[k]), key=lambda k: bodies[k][N]["mean"])
        rec = bodies[name][N]
        best_by_N[N] = dict(organism=name, mean=rec["mean"], se=rec["se"],
                            income_per_cell_e3=rec["income_per_cell_e3"],
                            z_vs_lone=analysis.z_diff(rec, dict(mean=ref["F"], se=0.0)))
    reg = REGISTERED["G2"]
    l0 = {N: dict(mean=bodies[hb.L0.name][N]["mean"], se=bodies[hb.L0.name][N]["se"], registered=m,
                  z=_zref(bodies[hb.L0.name][N], (m, s), 1e-3)) for N, (m, s) in reg["L0"].items()}
    out = dict(registered=reg, lone=dict(F=ref["F"], phenotype=_pheno(ref["phenotype"])),
               criteria=("below_lone: at every N >= 2, the best fresh mean F over all messages-off bodies (L0, the "
                         "best lone cell grown, and the screen's best) is at most the re-registered lone cell's F; "
                         f"zero_income: L0 earns below {G2_ZERO_INCOME_E3:g}e-3 per cell-unit at N >= 19. "
                         "L0_registered (|z| <= 3 against the registered L0 points) is reported."),
               screen={k: v for k, v in cand.items() if k != "organisms"}, lives=LIVES, bodies=bodies,
               best_by_N=best_by_N, L0_vs_registered=l0,
               notes=["Messages off = contacts_off from birth: spikes are never delivered (no effect on v or traces), "
                      "contact notices still arrive, so cells still know n_view. Program-mode cells cannot read "
                      "morphogens, so chemistry cannot couple them either.",
                      "The screen covers every homogeneous phenotype that can pump alone (b > 1, kappa > 0: 960), "
                      "grown by layered growth; its best 3 at each of 2, 3 and 7 cells are re-measured on fresh lives "
                      "at 2, 3, 7 and 19 cells. The registered GA control belongs to the evolution side.",
                      "Scope: program mode only. GRN-mode bodies under contacts_off keep one coupling channel, "
                      "chemistry (the messages_off control evolves there), and it can carry spike timing: a 2-cell "
                      "body whose cells secrete after their own spikes and read their morphogen level raises "
                      "Kuramoto R from 0.658 (chem_off) to 0.714 on the same lives, at F about -0.0001 (review "
                      "check). This gate does not test whether such bodies can beat a lone cell."])
    return judge_g2(out)


def judge_g2(g: dict) -> dict:
    lone = g["lone"]["F"]
    l0 = g["bodies"][hb.L0.name]
    g["checks"] = dict(
        below_lone=all(v["mean"] <= lone for N, v in g["best_by_N"].items() if int(N) >= 2),
        zero_income=all(v["income_per_cell_e3"] < G2_ZERO_INCOME_E3 for N, v in l0.items() if int(N) >= 19),
        L0_registered=all(abs(v["z"]) <= 3.0 for v in g["L0_vs_registered"].values()))
    g["passed"] = bool(g["checks"]["below_lone"] and g["checks"]["zero_income"])
    return g


# ------------------------------------------------------------------------------------------------------- G3
def _curve_entry(rec: dict, ref: tuple, z_max: float, resolution: float) -> dict:
    ref_s = dict(mean=ref[0], se=math.hypot(ref[1], resolution / math.sqrt(12.0)))
    z = analysis.z_diff(rec, ref_s)
    keep = ("mean", "se", "median", "frac_pos", "n", "n_end", "last_birth", "income_per_cell_e3")
    return dict({k: rec[k] for k in keep if k in rec}, reference=ref_s, z=z, ok=bool(abs(z) <= z_max))


def r25_curve(n: int = LIVES_R25, sizes=SIZES_R25) -> dict[int, dict]:
    return curve(hb.R25_V1, sizes, n)


def gate_g3(threads: int = 4, sizes=G3_SIZES, lives: int = 36, port_lives: int = G3_PORT_LIVES,
            fresh_lives: int = LIVES_R25) -> dict:
    """R25-v1 size curve under the oracle cap: re-registered on fresh lives; plus, for the record, the kernel on the
    registration seeds (36 lives at 37, 91, 169) and the port check against the re-measured prototype."""
    _THREADS[0] = threads
    reg = REGISTERED["G3"]
    proto = PROTOTYPE["G3"]
    out = dict(registered=dict(lives=reg["lives"], n_star=reg["n_star"],
                               curve={N: dict(mean=m, se=s) for N, (m, s) in reg["curve"].items()}))
    # re-registration
    cur = r25_curve(fresh_lives)
    pts = points(cur)
    for N, p in pts.items():
        p["z_vs_registered"] = _zref(p, reg["curve"][N], reg["resolution"])
    b = best(cur)
    steps = {f"{a}->{c}": analysis.paired(cur[c]["F"], cur[a]["F"]) for a, c in zip(SIZES_R25, SIZES_R25[1:])}
    out["reregistered"] = dict(organism=hb.R25_V1.name, lives=fresh_lives,
                               seeds=f"{analysis.FRESH_SEED0} + s, s < {fresh_lives}, the same at every size",
                               curve=pts, **b, steps=steps,
                               lone_F=lone_reference()["F"],
                               differs_from_registration=[N for N, p in pts.items() if abs(p["z_vs_registered"]) > Z])
    # the kernel on the registration seeds, and the port check (milestone 1)
    regchk = {}
    for org in (hb.R25_V1, hb.R25_V1_BELL3):
        c = analysis.size_curve(org, sizes, lives=lives, threads=threads)
        p = {N: _curve_entry(c[N], reg["curve"][N], G3_REG_Z, reg["resolution"]) for N in sizes}
        n_star = max(sizes, key=lambda N: c[N]["mean"])
        regchk[org.name] = dict(points=p, n_star=n_star,
                                ok=bool(all(x["ok"] for x in p.values()) and n_star == reg["n_star"]))
    out["registered_check"] = regchk
    port = analysis.size_curve(hb.R25_V1_BELL3, sizes, lives=port_lives, seed0=proto["seed0"], threads=threads)
    pref = PROTOTYPE["G3_port"]
    out["port_check"] = dict(organism=hb.R25_V1_BELL3.name, lives=port_lives, prototype_lives=pref["lives"],
                             seeds=f"{proto['seed0']} + 91 N + s", prototype_seeds=pref["seeds"],
                             prototype_normals=pref["normals"],
                             points={N: _curve_entry(port[N], pref["curve"][N], G3_PORT_Z, pref["resolution"])
                                     for N in sizes})
    out["port_check"]["ok"] = all(p["ok"] for p in out["port_check"]["points"].values())
    out["criteria"] = ("re-registered on fresh lives: rises (F increases at every size up to n*, by more than "
                       f"{Z:g} paired SE at every step below the flat top), bounded (n* is interior and "
                       f"F({SIZES_R25[-1]}) < 0), beats_lone "
                       "(F* > 10 x the lone cell); port: R25-v1/bell3 (the prototype's exact rule) within "
                       f"{G3_PORT_Z:g} combined SE of the re-measured prototype (bell3.c with Irwin-Hall(12) "
                       f"frozen normals, {PROTOTYPE['G3_port']['lives']} lives per size) at "
                       f"{', '.join(map(str, sizes))}. "
                       f"registration_seeds (the kernel on the 36 registration seeds within {G3_REG_Z:g} SE of the "
                       "registered points, with n* = 91 among the three sizes) is reported.")
    out["notes"] = [  # measured once on 2026-10-07 (kernel and bell3.c); not recomputed by this script
        "The registered F(91) = +0.928 is a high draw of the prototype itself. bell3.c, unchanged, reproduces it "
        "on the registration seeds (91 N + s) but gives +0.726 +- 0.008 on 4608 fresh lives (seeds 9,000,000 + s; "
        "+0.732 +- 0.008 with the kernel's Irwin-Hall normals). The prototype draws a life's frozen physics from its "
        "seed, so every organism registered at 91 cells shared the same 36 favourable bodies (L3 +0.745 there vs "
        "+0.475 +- 0.023 fresh, L4 +0.905 vs +0.779 +- 0.013).",
        "The port reference is bell3.c with Irwin-Hall(12) frozen normals, as the kernel draws them (LIFE_ABI.md "
        "15.13), on 4608 lives per size: +0.5629 +- 0.0017 (37), +0.7324 +- 0.0078 (91), +0.0251 +- 0.0194 (169). "
        "It replaces the 1152-life Gaussian curve (+0.7645 at 91, -0.1045 at 169), which was itself about 2.3 SE "
        "high at 91 and low at 169, and was judged at 3 SE. Irwin-Hall minus Gaussian on the same prototype seeds: "
        "+0.0007 +- 0.0024, +0.0060 +- 0.0111 and +0.0278 +- 0.0275 (unpaired), a lift at large sizes that 4608 "
        "lives do not resolve. Adding Q10 rounding to bell3 changes nothing (milestone 1).",
        "The kernel's seeds 91 N + s are not the prototype's bodies (the kernel keys physics by hash), so the "
        "registration-seed check is a record of milestone 1, not a reproduction of the lucky draw.",
    ]
    return judge_g3(out)


def judge_g3(g: dict) -> dict:
    rr = g["reregistered"]
    sizes = sorted(int(N) for N in rr["curve"])
    up = [N for N in sizes if N <= rr["n_star"]]
    low = [N for N in sizes if N <= min(rr["flat_top"])]
    steps = rr["steps"]
    rises = (all(steps[f"{a}->{c}"]["mean"] > 0 for a, c in zip(up, up[1:]))
             and all(steps[f"{a}->{c}"]["z"] > Z for a, c in zip(low, low[1:])))
    curve_ = {int(N): v for N, v in rr["curve"].items()}
    g["checks"] = dict(rises=bool(rises), bounded=bool(not rr["edge"] and curve_[sizes[-1]]["mean"] < 0),
                       beats_lone=bool(rr["F_star"] > 10 * rr["lone_F"]), port=bool(g["port_check"]["ok"]),
                       registration_seeds=bool(g["registered_check"][hb.R25_V1.name]["ok"]))
    c = g["checks"]
    g["passed"] = bool(c["rises"] and c["bounded"] and c["beats_lone"] and c["port"])
    return g


# ------------------------------------------------------------------------------------------------------- G4
CHAIN = (hb.R25_V1, hb.R25_NO_LBT, hb.R25_NAIVE, hb.L1, hb.L0)
LADDER = (hb.L4, hb.L3, hb.L2, hb.L1, hb.L0)


def g4_sizes(org) -> tuple:
    return SIZES_SMALL if org in (hb.L0, hb.L1) else SIZES_ABL


def gate_g4(threads: int = 4, n: int = LIVES) -> dict:
    """Ablation order of the hand-built ladder, as [n*, F*], re-registered on fresh lives."""
    _THREADS[0] = threads
    orgs = {o.name: o for o in CHAIN + LADDER}
    curves = {k: curve(o, g4_sizes(o), n) for k, o in orgs.items()}
    out = dict(registered=REGISTERED["G4"], lives=n, seeds=f"{analysis.FRESH_SEED0} + s, s < {n}",
               organisms={k: dict(about=o.about, sizes=list(g4_sizes(o)), curve=points(curves[k]), **best(curves[k]))
                          for k, o in orgs.items()})

    def chain(names):
        rows = []
        for a, c in zip(names, names[1:]):
            A, C = out["organisms"][a], out["organisms"][c]
            d = analysis.paired(curves[a][A["n_star"]]["F"], curves[c][C["n_star"]]["F"])
            rows.append(dict(pair=f"{a} > {c}", dF=d["mean"], se=d["se"], z=d["z"], n_star=(A["n_star"], C["n_star"])))
        return rows

    out["chain"] = chain([o.name for o in CHAIN])
    out["ladder"] = chain([o.name for o in LADDER])
    out["criteria"] = (f"F*: each organism's F* exceeds the next one's by more than {Z:g} paired SE (lives matched "
                       "by seed, each at its own n*); n*: non-increasing along the chain; no n* at the largest size "
                       "measured. Both the design's chain (R25-v1 > no-LBT > naive > flood > no messages) and the "
                       "prototype ladder (L4 > L3 > L2 > L1 > L0) are gated.")
    out["notes"] = ["n* is resolved only to the flat top (sizes within 2 paired SE of n* are listed per organism).",
                    "L0-L4 copy the prototype exactly (off-grid AOFF b 1.2, t_ref 2.6; low rate 0.05); R25-v1 and its "
                    "ablations are the design's on-grid organisms."]
    return judge_g4(out)


def judge_g4(g: dict) -> dict:
    def ok(rows):
        return (all(r["z"] > Z for r in rows), all(r["n_star"][0] >= r["n_star"][1] for r in rows))

    cf, cn = ok(g["chain"])
    lf, ln = ok(g["ladder"])
    g["checks"] = dict(chain_F=bool(cf), chain_n=bool(cn), ladder_F=bool(lf), ladder_n=bool(ln),
                       no_edge=not any(o["edge"] for o in g["organisms"].values()))
    g["passed"] = bool(all(g["checks"].values()))
    return g


# ------------------------------------------------------------------------------------------------------- G5
G5_CONDITIONS = dict(default={}, no_frozen=dict(delay_sd=0.0, tau_mis=0.0), lockstep=dict(flags=LOCKSTEP))


def g5_world(cond: str) -> dict:
    return dict(G5_CONDITIONS[cond])  # Organism.world adds program_mode to any flags given here


def gate_g5(threads: int = 4, n: int = LIVES_G5) -> dict:
    """Removing frozen heterogeneity (contact-delay spread and tau mismatch) removes the size bound."""
    _THREADS[0] = threads
    curves = {c: curve(hb.R25_V1, SIZES_G5, n, **g5_world(c)) for c in G5_CONDITIONS}
    out = dict(registered=REGISTERED["G5"], organism=hb.R25_V1.name, lives=n, sizes=list(SIZES_G5),
               conditions={c: dict(world=G5_CONDITIONS[c], curve=points(cur), **best(cur),
                                   largest_vs_91=analysis.paired(cur[SIZES_G5[-1]]["F"], cur[SIZES_G5[0]]["F"]))
                           for c, cur in curves.items()},
               criteria=(f"no_frozen_unbounded: with delay_sd = tau_mis = 0, n* is {SIZES_G5[-2]} or more and "
                         f"F({SIZES_G5[-1]}) exceeds F({SIZES_G5[0]}) by more than {Z:g} paired SE; default_bounded: "
                         f"with the v1 physics n* <= 169 and F({SIZES_G5[-1]}) < 0. The lockstep control (every d_c "
                         "= 1, no jitter, no mismatch, clocks in phase) is reported."),
               notes=["The registration measured L4 (12 lives); this gate measures R25-v1, the design's reference.",
                      "clock_sd stays 0.05 in no_frozen (as in the prototype): clocks set ticks, not the beat.",
                      "Lockstep bodies can end a few cells above their cap (LIFE_ABI.md 11.3)."])
    return judge_g5(out)


def judge_g5(g: dict) -> dict:
    nf, de = g["conditions"]["no_frozen"], g["conditions"]["default"]
    g["checks"] = dict(no_frozen_unbounded=bool(nf["n_star"] >= SIZES_G5[-2] and nf["largest_vs_91"]["z"] > Z),
                       default_bounded=bool(de["n_star"] <= 169 and _at(de["curve"], SIZES_G5[-1])["mean"] < 0),
                       lockstep_unbounded=bool(g["conditions"]["lockstep"]["n_star"] >= SIZES_G5[-2]))
    g["passed"] = bool(g["checks"]["no_frozen_unbounded"] and g["checks"]["default_bounded"])
    return g


# ------------------------------------------------------------------------------------------------------- G6
G6_TWIN = dict(t_open=T_HALF)
G6_FORK = dict(t_open=T_HALF, t_fork=T_HALF, fork_flags=CONTACTS_OFF)


def gate_g6(threads: int = 4, n: int = LIVES, cap: int = 91) -> dict:
    """Spikes undelivered from T/2 (a contacts_off fork) collapse income per cell."""
    _THREADS[0] = threads
    rows = {}
    for org in (hb.R25_V1, hb.R25_V1_GRN):
        twin, fork = lives(org, cap, n, **G6_TWIN), lives(org, cap, n, **G6_FORK)
        pt, pf = analysis.point(twin), analysis.point(fork)
        rows[org.name] = dict(twin=pt, fork=pf, ratio=pf["income_per_cell_e3"] / pt["income_per_cell_e3"],
                              dF=analysis.paired(fork["F"], twin["F"]))
    out = dict(registered=REGISTERED["G6"], cap=cap, lives=n, window=[T_HALF, 1024.0], organisms=rows,
               criteria=(f"collapse: in the window [T/2, T], income per cell of the contacts_off fork is at most "
                         f"{G6_COLLAPSE:g} x the intact twin's, for R25-v1 and for its GRN genome."),
               notes=["Forks are replays (LIFE_ABI.md 12): the same life with fork_flags = contacts_off from T/2 and "
                      "t_open = T/2; the twin has t_open = T/2 only. Costs are still charged in the fork.",
                      "The GRN genome is the n_view-gated one of ABI 2 (G9); abi1 keeps the flank_best-gated "
                      "genome's numbers."], abi1=ABI1["G6"])
    return judge_g6(out)


def judge_g6(g: dict) -> dict:
    g["checks"] = {f"collapse_{k}": bool(v["ratio"] <= G6_COLLAPSE) for k, v in g["organisms"].items()}
    g["passed"] = bool(all(g["checks"].values()))
    return g


# ------------------------------------------------------------------------------------------------------- G9
def g9_minimal() -> hb.GrnOrganism:
    return hb.GrnOrganism("R25-v1/GRN minimal", hb.r25_genome(echo=False, reset=False),
                          about="the design's minimal form: contact, juvenile and gate genes only (no echo, no reset)")


G9_SIZES = (37, 91, 169)


def gate_g9(threads: int = 4, n: int = LIVES_R25) -> dict:
    """R25-v1 written as a GRN genome, through the real 793-slot path (spec.pack_genomes), against the program."""
    _THREADS[0] = threads
    prog = curve(hb.R25_V1, G9_SIZES, n)
    grn = curve(hb.R25_V1_GRN, G9_SIZES, n)
    pts = {}
    for N in G9_SIZES:
        p, q = analysis.point(prog[N]), analysis.point(grn[N])
        pts[N] = dict(program=p, grn=q, z=analysis.z_diff(q, p), paired=analysis.paired(grn[N]["F"], prog[N]["F"]))
    mini, prog91 = lives(g9_minimal(), 91, LIVES), lives(hb.R25_V1, 91, LIVES)
    gt = hb.R25_V1_GRN.table("hex")[0]
    act = [int(k) for k in np.nonzero(spec.genome_view(gt, "act"))[0]]
    out = dict(registered=REGISTERED["G9"], lives=n, sizes=list(G9_SIZES), points=pts,
               genome=dict(slots=int(hb.R25_V1_GRN.genome.size), active_genes=act,
                           genes={hb.GENE_CONTACT: "contact", hb.GENE_JUVENILE: "juvenile", hb.GENE_GATE: "rim gate",
                                  hb.GENE_ECHO: "contact echo", hb.GENE_RESET: "division reset"},
                           path="handbuilt.r25_genome -> spec.pack_genomes -> build.run (GRN mode)"),
               minimal=dict(about=g9_minimal().about, lives=LIVES, at_91=analysis.point(mini),
                            z_vs_program=analysis.z_diff(analysis.point(mini), analysis.point(prog91)),
                            paired=analysis.paired(mini["F"], prog91["F"])),
               phenotypes=hb.r25_genome_states(), abi1=ABI1["G9"],
               criteria=(f"within_2se: at the oracle cap 91, |F_GRN - F_program| <= {Z:g} combined SE over {n} fresh "
                         "lives (the design asks 36); phenotypes: in every settled gene state the genome decodes "
                         "exactly the program row on every knob a program row uses (p_div after the rate gate). "
                         "37 and 169 cells are reported (G10 uses them)."),
               notes=["ABI 2 (LIFE_ABI.md 15.32): the gene network has no flank_best input, so the genome's rate "
                      "gate (gene 2) opens at n_view >= 5 (from the live-contact fraction), where the program's opens "
                      "at flank_best = 2; both place daughters by flank (phi 2). G10 measured this n_view gate as "
                      "good as a flank_best gate in GRN mode under ABI 1, on hex; on square8 it is weaker (S8 notes). "
                      "The ABI-1 genome (flank_best gate) is kept in abi1.",
                      "Genes beyond the design's sketch (contact, juvenile, rate gate): a contact echo makes the "
                      "alone-to-contact switch exact at the first tick that sees a contact, and a division reset "
                      "undoes the gate gene's forced opening in a mother (partition Q -1). Both were chosen on "
                      "exploration seeds 8.2e6 + s, not on the gate's lives.",
                      "Transitions are not instantaneous: a lambda-1/2 gate gene takes one or two ticks to open or "
                      "close (p_div 1/4 or 1/8 meanwhile), and a juvenile mother becomes an adult at her first division "
                      "(Q +1, as the design specifies), whereas the program keeps her silent until her own tick 10.",
                      "The 'minimal' genome is the design's sketch (no echo, no reset): its alone-to-contact switch "
                      "takes about 4 ticks (b passes 1.5, 1.25 on the way) and its mothers divide at 1/4 at the tick "
                      "after a claim."])
    return judge_g9(out)


def judge_g9(g: dict) -> dict:
    pts = {int(N): v for N, v in g["points"].items()}
    g["checks"] = dict(within_2se=bool(abs(pts[91]["z"]) <= Z),
                       within_2se_all_sizes=bool(all(abs(v["z"]) <= Z for v in pts.values())),
                       phenotypes=bool(all(not v["mismatches"] for v in g["phenotypes"].values())))
    g["passed"] = bool(g["checks"]["within_2se"] and g["checks"]["phenotypes"])
    return g


# ------------------------------------------------------------------------------------------------------ G10
def d4_variants() -> dict[str, hb.Organism]:
    return {"layered (placement + gate)": hb.R25_V1,
            "placement only": hb.r25_v1(gate=False, name="R25-v1/placement-only"),
            "gate only": hb.r25_v1(placement=False, name="R25-v1/gate-only"),
            "neither": hb.r25_v1(gate=False, placement=False, name="R25-v1/random-p1/2")}


def d4_grn() -> dict[str, hb.GrnOrganism]:
    """GRN-mode D4 (ABI 2): R25-v1's genome (n_view gate, flank placement) and the registered alternative (n_view
    gate, random placement: the prototype's dir 4). The flank_best-gated genome of ABI 1 is in ``ABI1``."""
    return {"n_view gate, flank placement": hb.R25_V1_GRN,
            "n_view gate, random placement": hb.GrnOrganism(
                "R25-v1/GRN n_view-gate random", hb.r25_genome(placement=False),
                about="gate opens at n_view >= 5, phi 0: the prototype's dir 4, as registered for D4")}


def contact_row(b: float, tau_m: float, t_ref: float, w0: float, delta: float = 2.0) -> np.ndarray:
    return spec.theta(b=b, tau_m=tau_m, t_ref=t_ref, w0=w0, emit0=1, delta=delta, kappa=1)


OLD_TREF = (0.5, 1.0, 2.0, 4.0)  # the design grid before D5
C1 = contact_row(1.125, 1.0, 2.0, -0.75)  # the registered best design-grid phenotype (task_bell e7 C1_lbt)
_D5: dict = {}


def d5_screen() -> dict:
    """R25-v1 with other coupled rows at 91 cells (screen seeds): b, tau_m, w0 and every t_ref on the v1 grid."""
    if "out" not in _D5:
        grid = list(itertools.product((1.125, 1.25), (1.0, 2.0), (-0.75, -1.0, -1.5), spec.T_REF))
        orgs = [hb.r25_v1(contact=contact_row(b, t, r, w), name=f"R25 b={b} tau={t} w0={w} tref={r}")
                for b, t, w, r in grid]
        seeds = analysis.fresh_seeds(SCREEN_LIVES, analysis.SCREEN_SEED0)
        res = build.run(hb.R25_V1.world(oracle_cap=91), [s for _ in orgs for s in seeds],
                        programs=np.stack([o.program for o in orgs]),
                        genome_of=np.repeat(np.arange(len(orgs)), len(seeds)), threads=_threads())
        F = res["F"].reshape(len(orgs), len(seeds)).mean(axis=1)
        rows = [dict(b=b, tau_m=t, w0=w, t_ref=r, F_screen=float(f)) for (b, t, w, r), f in zip(grid, F)]
        old = max((i for i, x in enumerate(rows) if x["t_ref"] in OLD_TREF), key=lambda i: rows[i]["F_screen"])
        new = max((i for i, x in enumerate(rows) if x["t_ref"] not in OLD_TREF), key=lambda i: rows[i]["F_screen"])
        _D5["out"] = dict(screened=len(rows), N=91, lives=len(seeds),
                          top=sorted(rows, key=lambda x: -x["F_screen"])[:10], best_old=rows[old], best_refined=rows[new],
                          organisms={"best old grid": orgs[old], "best refined": orgs[new]})
    return _D5["out"]


def d5_variants() -> dict:
    scr = d5_screen()
    v = {"R25-v1 (t_ref 2.5)": hb.R25_V1, "C1 (registered old-grid best, t_ref 2)":
         hb.r25_v1(contact=C1, name="R25/C1")}
    v.update({f"screen {k}": o for k, o in scr["organisms"].items()})
    return v


def tref_sweep() -> dict[float, hb.Organism]:
    return {r: (hb.R25_V1 if r == 2.5 else
                hb.r25_v1(contact=hb.with_knobs(hb.COUPLED, t_ref=r), name=f"R25-v1/t_ref {r}")) for r in spec.T_REF}


def g10_plan() -> list[tuple]:
    plan = [(o, SIZES_D4, LIVES) for o in d4_variants().values()]
    plan += [(o, SIZES_D5, LIVES) for o in d4_grn().values()]
    plan += [(o, SIZES_D5, LIVES) for o in d5_variants().values()]
    plan += [(o, (91,), LIVES) for o in tref_sweep().values()]
    return plan


def gate_g10(threads: int = 4, n: int = LIVES) -> dict:
    """D4 (flank placement and gate) and D5 (refined t_ref grid) re-measured on fresh lives, plus the GRN layer."""
    _THREADS[0] = threads

    def block(variants, sizes):
        cur = {k: curve(o, sizes, n) for k, o in variants.items()}
        rows = {k: dict(organism=variants[k].name, curve=points(c), **best(c)) for k, c in cur.items()}
        first = next(iter(cur))
        for k in rows:
            if k != first:  # the first variant's F* minus this one's, lives matched by seed
                rows[k]["vs_first"] = analysis.paired(cur[first][rows[first]["n_star"]]["F"],
                                                      cur[k][rows[k]["n_star"]]["F"])
        return rows

    d4 = block(d4_variants(), SIZES_D4)
    d4g = block(d4_grn(), SIZES_D5)
    ref, nv = d4g["n_view gate, flank placement"], d4g["n_view gate, random placement"]
    d5 = block(d5_variants(), SIZES_D5)
    sweep = {r: analysis.point(lives(o, 91, n)) for r, o in tref_sweep().items()}
    # GRN layer: a lone cell in GRN mode (constant readout) is bitwise the program-mode lone cell
    row = spec.theta(**_pheno(lone_reference()["phenotype"]))
    seeds = analysis.fresh_seeds(16)
    rp = hb.lone(row).run(seeds)
    rg = hb.GrnOrganism("lone/GRN", hb.constant_genome(row)).run(seeds)
    lone_bitwise = bool(np.array_equal(rp.ledger.view(np.uint64), rg.ledger.view(np.uint64))
                        and np.array_equal(rp.hashes, rg.hashes))
    g9pts = {N: dict(z=analysis.z_diff(analysis.point(lives(hb.R25_V1_GRN, N, LIVES_R25)),
                                       analysis.point(lives(hb.R25_V1, N, LIVES_R25)))) for N in G9_SIZES}
    out = dict(registered=REGISTERED["G10"], lives=n,
               d4_program=d4, d4_grn=dict(rows=d4g, random_placement_shortfall=1.0 - nv["F_star"] / ref["F_star"],
                                          abi1=ABI1["G10"]),
               d5=dict(screen={k: v for k, v in d5_screen().items() if k != "organisms"}, variants=d5,
                       t_ref_sweep_91=sweep),
               grn_layer=dict(lone_grn_bitwise_program=lone_bitwise, g3_grn_z=g9pts),
               criteria=(f"d4_layered: R25-v1's layered growth (flank placement + flank gate) beats placement only, "
                         f"gate only and neither by more than {Z:g} paired SE in F* (program mode); d4_grn_placement: "
                         "in GRN mode R25-v1's genome (n_view >= 5 gate, flank placement) beats the registered "
                         "alternative, the same gate with random placement (the prototype's dir 4), by more than 2 "
                         "paired SE (since ABI 2 the gene network has no flank_best input, so the two differ only in "
                         "the placement term); "
                         "d5_refined: R25-v1 (t_ref 2.5) beats the best old-grid phenotype (t_ref in 0.5, 1, 2, 4; "
                         "chosen by a screen at 91 cells on screen seeds) by more than 2 paired SE in F*; grn_layer: a "
                         "lone GRN cell is bitwise the program lone cell (G1), and R25-v1's GRN genome is within 2 SE "
                         "of the program at 37, 91 and 169 cells (G9's lives; the G3 curve). G2 and G4 are not run in "
                         "GRN mode."),
               notes=["D4's registered '23% weaker' is task_bell e5: AOFF dir 4 (n_view < 5 slows division, random "
                      "placement) +0.699 vs dir 3 (flank gate and flank placement) +0.905 at 91 cells, on the lucky "
                      "registration lives. Under ABI 1 the comparison ran through genes against a flank_best-gated "
                      "genome (+0.753): dir 4 was 15% weaker (z 2.9), but an n_view gate with flank placement was as "
                      "good on hex (+0.754, paired -0.001 +- 0.013; on square8 it is not: S8 notes). ABI 2 therefore "
                      "removed the flank_best input "
                      "(LIFE_ABI.md 15.32), made the n_view-gated genome R25-v1's genome, and kept the phi flank(e) "
                      "placement term; abi1 keeps those measurements. Under ABI 2 the comparison isolates placement "
                      "(random_placement_shortfall).",
                      "D5's registered 0.693 vs 0.928 were both measured on the lucky 91-cell registration lives."])
    return judge_g10(out)


def judge_g10(g: dict) -> dict:
    d4 = g["d4_program"]
    first = next(iter(d4))
    d5 = g["d5"]["variants"]
    old = d5["screen best old grid"]
    g["checks"] = dict(
        d4_layered=bool(all(v["vs_first"]["z"] > Z for k, v in d4.items() if k != first)),
        d4_grn_placement=bool(g["d4_grn"]["rows"]["n_view gate, random placement"]["vs_first"]["z"] > Z),
        d5_refined=bool(old["vs_first"]["z"] > Z),
        grn_layer=bool(g["grn_layer"]["lone_grn_bitwise_program"]
                       and all(abs(v["z"]) <= Z for v in g["grn_layer"]["g3_grn_z"].values())))
    g["passed"] = bool(all(g["checks"].values()))
    return g


# ------------------------------------------------------------------------------------------------------- S8
S8 = dict(lattice="square8")
_S8: dict = {}


def s8_screen() -> dict:
    """R25-v1 variants on square8 at 121 cells (screen seeds): coupled row and flank gate re-tuned for 8 contacts."""
    if "out" not in _S8:
        grid = list(itertools.product((1.125, 1.25), (-0.5, -0.75, -1.0), (1.0, 2.0), (2.0, 2.5, 3.0), (True, False)))
        orgs = [hb.r25_v1(contact=contact_row(b, 1.0, r, w, d), gate=gate,
                          name=f"R25/sq8 b={b} w0={w} delta={d} tref={r} gate={int(gate)}")
                for b, w, d, r, gate in grid]
        seeds = analysis.fresh_seeds(SCREEN_LIVES, analysis.SCREEN_SEED0)
        res = build.run(hb.R25_V1.world(oracle_cap=S8_SCREEN_N, **S8), [s for _ in orgs for s in seeds],
                        programs=np.stack([o.program for o in orgs]),
                        genome_of=np.repeat(np.arange(len(orgs)), len(seeds)), threads=_threads())
        F = res["F"].reshape(len(orgs), len(seeds)).mean(axis=1)
        rows = [dict(b=b, w0=w, delta=d, t_ref=r, flank_gate=bool(gate), F_screen=float(f))
                for (b, w, d, r, gate), f in zip(grid, F)]
        i = int(np.argmax(F))
        _S8["out"] = dict(screened=len(rows), N=S8_SCREEN_N, lives=len(seeds),
                          top=sorted(rows, key=lambda x: -x["F_screen"])[:10], best=rows[i], organism=orgs[i])
    return _S8["out"]


def s8_plan() -> list[tuple]:
    return [(hb.R25_V1, SIZES_S8, LIVES), (s8_screen()["organism"], SIZES_S8, LIVES)]


def gate_s8(threads: int = 4, n: int = LIVES) -> dict:
    """The square8 size curve of R25-v1 (measured before any square8 run), and what re-tuning for 8 contacts buys."""
    _THREADS[0] = threads
    cur = curve(hb.R25_V1, SIZES_S8, n, **S8)
    scr = s8_screen()
    tuned = curve(scr["organism"], SIZES_S8, n, **S8)
    b0, b1 = best(cur), best(tuned)
    hexb = best(r25_curve())
    sq_grn = hb.GrnOrganism("R25-v1/GRN sq8", hb.r25_genome(D=8),
                            about="R25-v1 genome with n_view weights for D 8 (rate gate at n_view >= 7)")
    g_at = lives(sq_grn, b0["n_star"], n, **S8)
    out = dict(registered=REGISTERED["S8"], lattice="square8", lives=n, sizes=list(SIZES_S8),
               r25_v1=dict(curve=points(cur), **b0),
               retuned=dict(screen={k: v for k, v in scr.items() if k != "organism"}, organism=scr["organism"].name,
                            curve=points(tuned), **b1,
                            vs_r25_v1=analysis.paired(tuned[b1["n_star"]]["F"], cur[b0["n_star"]]["F"])),
               hex_r25_v1=dict(n_star=hexb["n_star"], F_star=hexb["F_star"], se=hexb["se"]),
               grn_at_n_star=dict(organism=sq_grn.name, about=sq_grn.about, N=b0["n_star"], abi1=ABI1["S8"],
                                  point=analysis.point(g_at),
                                  z_vs_program=analysis.z_diff(analysis.point(g_at),
                                                               analysis.point(cur[b0["n_star"]]))),
               criteria=("bounded: R25-v1 as built for hex has an interior n* on square8 (not the largest size, and "
                         "F at the largest size below F*). The re-tuned organism and the GRN genome are reported."),
               notes=["On square8 a cell has 8 contacts (4 edge, 4 diagonal), cyclic flanks are the angular "
                      "neighbours, and complete bodies are squares (2r + 1)^2.",
                      "The screen varies b, w0, delta and t_ref of the coupled row and the flank gate at 121 cells on "
                      "16 screen lives; the best is then measured on the fresh lives.",
                      "The GRN genome against its ABI-1 twin gated on flank_best (paired, 288 fresh lives per size, "
                      "results/flank_square8/): n_view gate minus flank_best gate -0.013 +- 0.010, -0.051 +- 0.020, "
                      "-0.081 +- 0.052 and -0.165 +- 0.065 at 49, 81, 121 and 169 cells (z -1.3, -2.5, -1.6, -2.5); "
                      "F* +1.015 vs +1.096 (-7%). No n_view threshold (>= 5, 6, 7) closes the gap. On hex the same "
                      "pair is equal (G10). So on square8 the removed input cost the hand-built genome F."])
    return judge_s8(out)


def judge_s8(g: dict) -> dict:
    r = g["r25_v1"]
    curve_ = {int(N): v for N, v in r["curve"].items()}
    g["checks"] = dict(bounded=bool(not r["edge"] and curve_[max(curve_)]["mean"] < r["F_star"]),
                       retuned_better=bool(g["retuned"]["vs_r25_v1"]["z"] > Z),
                       grn_within_2se=bool(abs(g["grn_at_n_star"]["z_vs_program"]) <= Z))
    g["passed"] = bool(g["checks"]["bounded"])
    return g


# ------------------------------------------------------------------------------------------------------- G7
def g7_plan() -> list[tuple]:
    """Every body the gates measure (organism, sizes, lives, world), plus the bursting body B."""
    plan = [(o, s, LIVES, {}) for o, s in g2_plan()]
    plan += [(hb.R25_V1, SIZES_R25, LIVES_R25, {})]
    plan += [(o, g4_sizes(o), LIVES, {}) for o in CHAIN + LADDER]
    plan += [(hb.R25_V1, SIZES_G5, LIVES_G5, g5_world(c)) for c in G5_CONDITIONS]
    plan += [(o, (91,), LIVES, w) for o in (hb.R25_V1, hb.R25_V1_GRN) for w in (G6_TWIN, G6_FORK)]
    plan += [(hb.R25_V1_GRN, G9_SIZES, LIVES_R25, {}), (g9_minimal(), (91,), LIVES, {})]
    plan += [(o, s, k, {}) for o, s, k in g10_plan()]
    plan += [(o, s, k, S8) for o, s, k in s8_plan()]
    plan += [(hb.B, (37, 91, 169), LIVES_G5, {})]
    return plan


def gate_g7(threads: int = 4) -> dict:
    """Income per cell never exceeds the lone-cell rate, in any body any gate measures."""
    _THREADS[0] = threads
    ref = lone_reference()
    rows = []
    for org, sizes, n, w in g7_plan():
        for N in sizes:
            r = lives(org, N, n, **w)
            rate = analysis.income_rate(r)
            i = int(np.argmax(rate))
            rows.append(dict(organism=org.name, N=int(N), world={k: v for k, v in w.items()}, lives=n,
                             mean_e3=float(1e3 * rate.mean()), max_e3=float(1e3 * rate[i]), life=i))
    body = [x for x in rows if x["N"] != 1]  # cap 1 is a lone cell
    top = sorted(body, key=lambda x: -x["max_e3"])[:8]
    out = dict(registered=REGISTERED["G7"],
               lone=dict(best_phenotype=_pheno(ref["phenotype"]), rate_best_e3=1e3 * ref["rate_best"],
                         rate_max_phenotype_e3=1e3 * ref["rate_max_phenotype"],
                         rate_max_life_e3=1e3 * ref["rate_max_life"]),
               points=len(body), lives=int(sum(x["lives"] for x in body)),
               body_max_e3=top[0]["max_e3"], body_mean_max_e3=max(x["mean_e3"] for x in body), top=top,
               by_organism={o: max(x["max_e3"] for x in body if x["organism"] == o)
                            for o in sorted({x["organism"] for x in body})},
               criteria=("every body life (excluding single cells) earns at most the largest income per cell-unit "
                         "any lone cell earned on G1's fresh lives (rate_max_life_e3), and every point's mean at most "
                         "the best lone phenotype's mean rate (rate_max_phenotype_e3)."),
               notes=["Points at cap 1 are lone cells and are excluded; G6's windows [T/2, T] are included. "
                      "Uncapped points (cap 0) do not occur."])
    return judge_g7(out)


def judge_g7(g: dict) -> dict:
    g["checks"] = dict(lives_below_lone=bool(g["body_max_e3"] <= g["lone"]["rate_max_life_e3"]),
                       means_below_lone=bool(g["body_mean_max_e3"] <= g["lone"]["rate_max_phenotype_e3"]))
    g["passed"] = bool(all(g["checks"].values()))
    return g


# ------------------------------------------------------------------------------------------------------- G8
def identical(a: build.Lives, b: build.Lives) -> bool:
    """Bitwise equality of two batches: ledger, hashes, raster and fate log (when recorded)."""
    if not (np.array_equal(a.ledger.view(np.uint64), b.ledger.view(np.uint64)) and np.array_equal(a.hashes, b.hashes)):
        return False
    for x, y in ((a.raster_t, b.raster_t), (a.raster_uid, b.raster_uid), (a.raster_n, b.raster_n),
                 (a.fate_i, b.fate_i), (a.fate_f, b.fate_f), (a.fate_n, b.fate_n)):
        if (x is None) != (y is None) or (x is not None and not np.array_equal(np.asarray(x).view(np.uint8),
                                                                              np.asarray(y).view(np.uint8))):
            return False
    return True


def gate_g8(threads: int = 4) -> dict:
    """Closed-form lumen vs explicit Euler (dt 1e-3, and 5e-4 for convergence) on growing R25-v1 bodies, plus
    bitwise invariance of the same lives under thread count and of uncapped lives under the window scheduler."""
    org = hb.R25_V1
    cases = [(N, T, s) for N, T in G8_CASES for s in G8_SEEDS]
    worlds = [org.world(oracle_cap=N, T=T) for N, T, _ in cases]
    seeds = [s for _, _, s in cases]
    kw = dict(programs=org.program, raster_cap=1 << 20, fate_cap=1 << 13)
    one = build.run(worlds, seeds, threads=1, **kw)
    many = build.run(worlds, seeds, threads=threads, **kw)
    lives_ = []
    for i, ((N, T, s), w) in enumerate(zip(cases, worlds)):
        t, u = one.spikes(i)
        spans = analysis.lifespans(*one.fates(i))
        closed = float(one["income"][i])
        rel = [(analysis.euler_income(t, u, spans, w, dt) - closed) / closed for dt in (1e-3, 5e-4)]
        lives_.append(dict(cap=N, T=T, seed=s, cells=len(spans), spikes=len(t), income_closed=closed,
                           rel_err_dt_1e3=rel[0], rel_err_dt_5e4=rel[1], halving_ratio=rel[1] / rel[0],
                           ok=bool(abs(rel[0]) <= REGISTERED["G8"]["max_rel"])))
    wh = org.world(T=160.0)
    base = build.run(wh, [[s, 0, 0, 0] for s in G8_SEEDS], programs=org.program, raster_cap=1 << 16, fate_cap=1 << 12)
    windows = {}
    for h in (0.5, 0.125):
        win = build.run(replace(wh, window_h=h), [[s, 0, 7 + s, 0] for s in G8_SEEDS], programs=org.program,
                        raster_cap=1 << 16, fate_cap=1 << 12)
        windows[str(h)] = identical(base, win)
    checks = dict(lumen=all(x["ok"] for x in lives_),
                  euler_converges=all(0.3 <= x["halving_ratio"] <= 0.7 for x in lives_),
                  threads_bitwise=identical(one, many), window_bitwise=all(windows.values()))
    return dict(
        registered=REGISTERED["G8"],
        criteria=("lumen: |income_Euler(dt 1e-3) - income_closed| / income_closed <= 0.1% for every life; "
                  "euler_converges: halving dt halves the error (ratio in [0.3, 0.7]); threads_bitwise: the same "
                  f"lives with 1 and {threads} threads are bitwise equal; window_bitwise: uncapped R25-v1 lives "
                  "(T 160) under the window scheduler at h 1/2 and 1/8 equal the heap bitwise."),
        organism=org.name, lives=lives_, max_abs_rel_err=max(abs(x["rel_err_dt_1e3"]) for x in lives_),
        window=dict(T=160.0, n_end=[float(x) for x in base["n_end"]], equal=windows),
        checks=checks, passed=bool(all(checks.values())),
        notes=["The Euler sum rebuilds P from the raster and the fate log (kappa = 1 in every R25-v1 row). The "
               "residual is Euler's first-order error: it halves with dt.",
               "Tests T1-T5, T11 and T12 run in tests/test_life_time.py; T6-T10 are not implemented yet "
               "(integer twin, statistical and evolved-organism tests)."],
    )


# ------------------------------------------------------------------------------------------------------ main
GATES = dict(G1=gate_g1, G2=gate_g2, G3=gate_g3, G4=gate_g4, G5=gate_g5, G6=gate_g6, G8=gate_g8, G9=gate_g9,
             G10=gate_g10, S8=gate_s8, G7=gate_g7)  # G7 last: it scans the bodies the others measured
JUDGES = dict(G1=judge_g1, G2=judge_g2, G3=judge_g3, G4=judge_g4, G5=judge_g5, G6=judge_g6, G7=judge_g7,
              G9=judge_g9, G10=judge_g10, S8=judge_s8)


def _jsonable(x):
    if isinstance(x, dict):
        return {str(k): _jsonable(v) for k, v in x.items()}
    if isinstance(x, (list, tuple)):
        return [_jsonable(v) for v in x]
    if isinstance(x, (np.floating, np.integer, np.bool_)):
        return x.item()
    if isinstance(x, np.ndarray):
        return _jsonable(x.tolist())
    if isinstance(x, float) and not math.isfinite(x):
        return str(x)
    return x


def main(argv=None) -> int:
    p = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    p.add_argument("--gates", default=",".join(GATES))
    p.add_argument("--threads", type=int, default=4)
    p.add_argument("--out", default=str(repo_root / "outputs" / "life_gates" / "gates.json"))
    args = p.parse_args(argv)
    names = [g.strip().upper() for g in args.gates.split(",") if g.strip()]
    bad = set(names) - set(GATES)
    if bad:
        p.error(f"unknown gates {sorted(bad)}; known: {sorted(GATES)}")
    names = [g for g in GATES if g in names]  # canonical order
    threads = max(1, min(args.threads, 4))
    _THREADS[0] = threads
    out = dict(meta=dict(date=datetime.now(timezone.utc).isoformat(timespec="seconds"), abi=spec.ABI_VERSION,
                         kernel=build.library_path().name, threads=threads, python=platform.python_version(),
                         command=" ".join([Path(sys.argv[0]).name, *(argv if argv is not None else sys.argv[1:])]),
                         fresh_seed0=analysis.FRESH_SEED0, screen_seed0=analysis.SCREEN_SEED0),
               gates={})
    t_all = time.time()
    for name in names:
        t0 = time.time()
        res = GATES[name](threads=threads)
        res["seconds"] = round(time.time() - t0, 1)
        out["gates"][name] = _jsonable(res)
        print(f"{name}: {'PASS' if res['passed'] else 'FAIL'}  checks {res['checks']}  ({res['seconds']} s)", flush=True)
    out["meta"]["seconds"] = round(time.time() - t_all, 1)
    out["passed"] = all(g["passed"] for g in out["gates"].values())
    path = Path(args.out)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(_jsonable(out), indent=1) + "\n")
    print(f"wrote {path} ({out['meta']['seconds']} s)")
    return 0 if out["passed"] else 1


if __name__ == "__main__":
    sys.exit(main())
