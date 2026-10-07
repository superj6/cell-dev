"""Hand-built program-mode organisms for BELL-1 (docs/ONE_LIFE_DESIGN.md: Identity, Life tasks, PRE-REGISTERED GATES).

Each organism is a phenotype program (docs/LIFE_ABI.md 4.5 and 7.5): fixed decoded phenotype rows for a cell that is
alone, has contacts, is a juvenile or is the zygote, plus the division scalars. They are the references the gates
measure the engine against: the lone-cell optimum and the silent zygote (G1), the prototype ladder L0-L4, R25-v1 and
its ablations (G3, G4) and the doublet-bursting body B.

Provenance. The ladder, B and the ``/bell3`` variants copy the configurations of the prototype
(scratchpad task_bell/bell3.c, experiments e7 and e16) exactly, including its off-grid values: AOFF's b 1.2 and
t_ref 2.6, PACE8's b, and the low division rate 0.5 x 0.1 = 0.05 (program rows accept off-grid values). R25-v1 itself
is the design's on-grid version, whose flank gate switches p_div between 1/2 and 1/16 (both on the p_div grid).

``r25_genome`` writes R25-v1 as a raw 793-slot GRN genome (``GrnOrganism``), the form evolution searches; gate G9
compares it with the program. The gene network has no flank_best input (ABI 2, LIFE_ABI.md 15.32), so the genome's
rate gate reads the live-contact fraction n_view / D where the program's reads flank_best; placement keeps the flank
term (phi 2) in both.
"""
from __future__ import annotations

import itertools
import math
from dataclasses import dataclass, replace

import numpy as np

from src.life import build, spec

PROGRAM_MODE = spec.FLAGS["program_mode"]
BELL3_P_DIV_LO = 0.05  # the prototype's low division rate (q 0.5 x q1 0.1); off the p_div grid
JUV_TICKS = 10  # listen-before-talk: own ticks a newborn spends emitting nothing


def tonic_period(b: float, tau_m: float, t_ref: float) -> float:
    """Inter-spike interval of a lone tonic cell (b > 1): t_ref + tau_m ln(b / (b - 1))."""
    return t_ref + tau_m * math.log(b / (b - 1.0))


def tonic_drive(period: float, tau_m: float, t_ref: float) -> float:
    """The drive b that makes a lone cell fire with the given period (the prototype's ``osc``)."""
    return 1.0 / (1.0 - math.exp(-(period - t_ref) / tau_m))


def with_knobs(row, **knobs) -> np.ndarray:
    out = np.array(row, dtype=np.float64)
    for k, v in knobs.items():
        out[spec.K[k]] = float(v)
    return out


# ---------------------------------------------------------------------------------------------- phenotypes
SILENT = spec.theta()  # never fires, never divides: F = -c_live
LONE_PUMP = spec.theta(b=1.875, tau_m=8, t_ref=2, kappa=1)  # the design's "alone pump" (G1 as registered)
LONE_BEST = spec.theta(b=1.625, tau_m=4, t_ref=4, kappa=1)  # exhaustive best lone cell on the v1 grid (measured)
COUPLED = spec.theta(b=1.125, tau_m=1, t_ref=2.5, w0=-1, emit0=1, delta=2, kappa=1)  # R25 delayed mutual inhibition
AOFF = spec.theta(b=1.2, tau_m=1, t_ref=2.6, w0=-1, emit0=1, delta=2, kappa=1)  # the prototype's inhibitor (off-grid)
DOUBLET = spec.theta(b=2, tau_m=2, t_ref=0.5, w0=-1, emit0=1, delta=2, kappa=1)  # B: bursting delayed inhibition
PACE8 = spec.theta(b=tonic_drive(8.0, 4.0, 3.5), tau_m=4, t_ref=3.5, emit0=1, kappa=1)  # zygote pacemaker, period 8
RELAY = spec.theta(b=0, tau_m=2, t_ref=3.5, w0=1.5, emit0=1, kappa=1)  # excitable relay: fires on one arrival


@dataclass(frozen=True, eq=False)
class Organism:
    """A program-mode organism: the packed program (``spec.pack_program``) and the base flags it needs."""
    name: str
    program: np.ndarray  # float64 [119]
    flags: int = 0  # base world flags besides program_mode (L0: contacts_off)
    about: str = ""

    def world(self, preset: str = "bell_v1", **overrides) -> spec.World:
        w = spec.world(preset, **overrides)
        return replace(w, flags=w.flags | PROGRAM_MODE | self.flags)

    def run(self, seeds, *, cap: int = 0, threads: int = 1, init=None, raster_cap: int = 0, fate_cap: int = 0,
            **world) -> build.Lives:
        """Lives of this organism in BELL-1 (``cap`` is the oracle size cap, a measurement tool only)."""
        return build.run(self.world(oracle_cap=cap, **world), seeds, programs=self.program, init=init,
                         threads=threads, raster_cap=raster_cap, fate_cap=fate_cap)


def lone(row, name: str = "lone") -> Organism:
    """A cell that never divides: every program row is ``row``."""
    return Organism(name, spec.pack_program(row), about="one cell for life")


def grower(name: str, contact, alone=LONE_PUMP, *, lbt: bool = True, layered: bool = True, p_div: float = 0.5,
           p_div_lo: float = 1 / 16, zygote=None, flags: int = 0, about: str = "", placement: bool | None = None,
           gate: bool | None = None) -> Organism:
    """A growing body (LIFE_ABI.md 7.5). Every row divides with ``p_div`` per own tick.

    ``layered``: placement prefers the empty slot with the most live flanks (phi 2), and p drops to ``p_div_lo``
    when the best empty slot has fewer than 2 flanks (the prototype's dir 3). Otherwise placement is random (phi 0,
    dir 0). ``placement`` and ``gate`` (default: ``layered``) switch the two halves separately (gate G10, D4).
    ``lbt``: a newborn with contacts spends its first 10 own ticks as ``contact`` without emitting.
    ``zygote``: a row the zygote keeps for life (the prototype's pacemaker).
    """
    placement = layered if placement is None else placement
    gate = layered if gate is None else gate
    phi = 2.0 if placement else 0.0
    rows = dict(contact=with_knobs(contact, p_div=p_div, phi=phi), alone=with_knobs(alone, p_div=p_div, phi=phi))
    if lbt:
        rows["juvenile"] = with_knobs(rows["contact"], emit0=0, emit1=0)
    if zygote is not None:
        rows["zygote"] = with_knobs(zygote, p_div=p_div, phi=phi)
    sc = dict(juv_ticks=JUV_TICKS if lbt else 0, zyg_row=1 if zygote is not None else 0)
    if gate:
        sc.update(flank_gate=2, p_div_lo=p_div_lo)
    return Organism(name, spec.pack_program(**rows, **sc), flags=flags, about=about)


def r25_v1(p_div_lo: float = 1 / 16, lbt: bool = True, layered: bool = True, name: str = "R25-v1", contact=None,
           placement: bool | None = None, gate: bool | None = None) -> Organism:
    """R25-v1: delayed mutual inhibition with contacts, the lone pump when alone, layered growth and
    listen-before-talk. Without ``layered`` it is the prototype's naive growth (random placement, p 1/4).
    ``contact`` replaces the coupled phenotype (gate G10 sweeps, square8 re-tuning)."""
    contact = COUPLED if contact is None else contact
    return grower(name, contact, LONE_PUMP, lbt=lbt, layered=layered, p_div=0.5 if layered else 0.25,
                  p_div_lo=p_div_lo, about="hand-built reference (design: R25-v1)", placement=placement, gate=gate)


SILENT_ZYGOTE = lone(SILENT, "silent")
LONE_PUMP_CELL = lone(LONE_PUMP, "lone-pump")
LONE_BEST_CELL = lone(LONE_BEST, "lone-best")

R25_V1 = r25_v1()
R25_V1_BELL3 = r25_v1(BELL3_P_DIV_LO, name="R25-v1/bell3")  # task_bell e16 "R25_v1" exactly
# G4 ablations, one change each from R25-v1 (e16 ran them with the 0.05 low rate: r25_v1(BELL3_P_DIV_LO, ...))
R25_NO_LBT = r25_v1(lbt=False, name="R25-v1/no-LBT")
R25_NAIVE = r25_v1(lbt=False, layered=False, name="R25-v1/naive")  # e16 "R25_naive" exactly (no flank gate)

# the prototype's algorithm ladder (task_bell e7; design Environments, E1 "Measured ladder")
L0 = grower("L0", LONE_PUMP, LONE_PUMP, lbt=False, p_div_lo=BELL3_P_DIV_LO, flags=spec.FLAGS["contacts_off"],
            about="no messages: lone pumps that grow (G2)")
L1 = grower("L1", RELAY, PACE8, lbt=False, p_div_lo=BELL3_P_DIV_LO, zygote=PACE8,
            about="leader flood: a pacemaker zygote and excitable relays")
L2 = grower("L2", AOFF, LONE_PUMP, lbt=False, layered=False, p_div=0.25, about="delayed inhibition, naive growth")
L3 = grower("L3", AOFF, LONE_PUMP, lbt=False, p_div_lo=BELL3_P_DIV_LO, about="delayed inhibition, layered growth")
L4 = grower("L4", AOFF, LONE_PUMP, p_div_lo=BELL3_P_DIV_LO, about="delayed inhibition, layered, listen-before-talk")
B = grower("B", DOUBLET, LONE_PUMP, p_div_lo=BELL3_P_DIV_LO, about="bursting delayed inhibition, layered, LBT")

ORGANISMS = {o.name: o for o in (SILENT_ZYGOTE, LONE_PUMP_CELL, LONE_BEST_CELL, R25_V1, R25_V1_BELL3, R25_NO_LBT,
                                 R25_NAIVE, L0, L1, L2, L3, L4, B)}

# ---------------------------------------------------------------------------------------------- lone-cell grid
# The knobs that change a lone, non-dividing cell's F: drive, leak, refractory period and contractility. The
# others (weights, emission, delay, chemistry readouts, placement) have no effect without contacts, division or
# secretion, and are held at their neutral values (the G1 gate checks this on the best cell).
LONE_AXES = dict(b=spec.Q8_GRID, tau_m=spec.TAU_M, t_ref=spec.T_REF, kappa=spec.KAPPA)


def lone_grid() -> tuple[list[tuple[float, float, float, float]], np.ndarray]:
    """Every lone phenotype on the v1 knob grid: ``(b, tau_m, t_ref, kappa)`` combos and their programs [n, 119]."""
    combos = list(itertools.product(*LONE_AXES.values()))
    progs = np.stack([spec.pack_program(spec.theta(b=b, tau_m=t, t_ref=r, kappa=k)) for b, t, r, k in combos])
    return combos, progs


# ---------------------------------------------------------------------------------------------- GRN genomes
@dataclass(frozen=True, eq=False)
class GrnOrganism:
    """A GRN-mode organism: a raw float32 genome [793] (``spec.GENOME_FIELDS``), packed per lattice at run time."""
    name: str
    genome: np.ndarray  # float32 [793]
    flags: int = 0
    about: str = ""

    def world(self, preset: str = "bell_v1", **overrides) -> spec.World:
        w = spec.world(preset, **overrides)
        return replace(w, flags=w.flags | self.flags)

    def table(self, kind: str = "hex") -> np.ndarray:
        return spec.pack_genomes(self.genome[None], kind)

    def run(self, seeds, *, cap: int = 0, threads: int = 1, init=None, raster_cap: int = 0, fate_cap: int = 0,
            **world) -> build.Lives:
        w = self.world(oracle_cap=cap, **world)
        return build.run(w, seeds, genomes=self.table(w.lattice), init=init, threads=threads, raster_cap=raster_cap,
                         fate_cap=fate_cap)


# R25-v1 written as a GRN genome (gate G9). Genes (all others inactive):
GENE_CONTACT, GENE_JUVENILE, GENE_GATE, GENE_ECHO, GENE_RESET, GENE_TIMER = 0, 1, 2, 3, 4, 5
LAM_X = {2: -3.0, 16: 0.0, 128: 4.0}  # raw rate-class value for lambda = 1/2, 1/16, 1/128 (spec.decode_lambda)


def r25_genome(gate: str | None = "n_view", echo: bool = True, reset: bool = True, timer: float = 0.0, contact=None,
               D: int = 6, placement: bool = True) -> np.ndarray:
    """R25-v1 as a raw float32 GRN genome; gate G9 scores it against the program ``R25_V1``. The program gates
    division on flank_best (a program-mode feature, LIFE_ABI.md 7.5); this genome gates it on n_view (gene 2).

    Genes (lambda per own tick; Q is the division partition, daughter g + asym Q, mother g - asym Q, asym ~ 1):
    - 0 contact (1/2): target 1 iff n_view >= 1; Q -1, so a daughter starts alone, as the program's newborn does.
    - 3 contact echo (1/2): target 1 iff gene 0 > 1/4 at the previous tick; Q -1. The readout uses
      C = 2 g0 - g3, which steps from 0 to 1 at the first tick that sees a contact (a lambda-1/2 gene alone needs
      about 4 ticks to settle): g0 = 1 - 2^-(n+1) and g3 = 1 - 2^-n give C = 1 from n = 0 on. ``echo=False`` reads
      g0 alone (C = g0), the design's minimal form.
    - 1 juvenile (1/16): decays to 0; Q +1, so a daughter starts at 1 and a mother drops to 0. Emission needs
      C - g1 > 0.492, i.e. g1 < 0.508: (15/16)^10 = 0.524 and (15/16)^11 = 0.492, so a newborn stays silent for exactly
      its first 10 own ticks (the program's juv_ticks 10). The zygote starts at g1 = 1 too.
    - 2 gate (1/2): target 1 iff n_view >= D - 1, read from the live-contact fraction n_view / D; Q -1. With flank
      placement (phi 2) this layered growth scored as well as a flank_best-gated genome on hex (G10 under ABI 1: F*
      +0.754 vs +0.753), but not on square8 (D = 8: F* +1.015 vs +1.096, paired -0.05 at 81 and -0.17 at 169 cells,
      z -2.5 each; no n_view threshold closes the gap; LIFE_GATES.md S8). The gene network has had no flank_best
      input since ABI 2.
      p_div = 2^(round(4 + 3 g2) - 8): 1/16 closed, 1/2 open, 1/4 or 1/8 for the one or two ticks of a transition.
      ``gate=None``: always open (p_div 1/2).
    - 4 division reset (1/2), only if ``reset``: target 0; Q -1, so it is 1 in a mother after a claim, 0 in the
      daughter. The gate reads g2 - g4: Q -1 forces the mother's g2 to 1, and g4 cancels exactly that, so after a
      division the mother's gate behaves as if reset to closed (without it she divides at 1/4 at her next tick
      whatever her contacts, which the program never does).
    - 5 lineage timer (1/128), only if ``timer`` > 0: rises toward 1 and is inherited (Q 0); p_div steps down and
      reaches 0 once timer x g5 > 1.625 (uncapped size control, the design's optional gene).
    Readout (y = a0 + A g; decoded on the v1 grid): b 1.875 - 0.75 C, tau_m 8 -> 1 and t_ref 2 -> 2.5 (alone ->
    contact), w0 -C, delta 2 C (0 -> 2), kappa 1, phi 2, emit0 = [2C - 2 g1 - 0.984 > 0], asym sigma(12),
    sec 0.5 sigma(-30), no death, no polarity, chemistry rates at their minimum. ``contact`` (a decoded phenotype)
    replaces the coupled row's b, tau_m, t_ref, w0 and delta. ``D`` is the lattice degree the n_view weights assume.
    ``placement=False`` sets phi 0 (random placement among empty slots, the prototype's n_view-gated dir 4).
    """
    c = COUPLED if contact is None else np.asarray(contact, dtype=np.float64)
    g = np.zeros(spec.GENOME_SIZE, dtype=np.float64)
    W, b, lam, s0, Q, act = (spec.genome_view(g, n) for n in ("W", "b", "lam", "s0", "Q", "act"))
    A, a0, Dm, km = (spec.genome_view(g, n) for n in ("A", "a0", "Dm", "km"))
    Kc, Kj, Kg, Ke, Kr, Kt = GENE_CONTACT, GENE_JUVENILE, GENE_GATE, GENE_ECHO, GENE_RESET, GENE_TIMER
    X_NVIEW = spec.G_MAX + 5  # input n_view / D
    lam[:] = LAM_X[2]
    s0[:] = -12.0
    act[[Kc, Kj, Kg]] = 1.0
    W[Kc, X_NVIEW] = 20.0 * D  # the input is n_view / D: n_view >= 1 -> +10
    b[Kc] = -10.0
    Q[Kc] = -1.0
    b[Kj], lam[Kj], s0[Kj], Q[Kj] = -12.0, LAM_X[16], 12.0, 1.0
    if gate == "n_view":
        W[Kg, X_NVIEW], b[Kg] = 20.0 * D, 30.0 - 20.0 * D  # n_view D - 1 -> +10, D - 2 -> -10
    elif gate is None:
        b[Kg], s0[Kg] = 30.0, 12.0
    else:  # "flank" was the flank_best gate of ABI 1; that input no longer exists
        raise ValueError(f"unknown gate {gate!r} (the gene network has no flank_best input since ABI 2)")
    Q[Kg] = -1.0 if gate is not None else 0.0
    if echo:
        act[Ke] = 1.0
        W[Ke, Kc], b[Ke], Q[Ke] = 40.0, -10.0, -1.0
        cvec = {Kc: 2.0, Ke: -1.0}  # C = 2 g0 - g3
    else:
        cvec = {Kc: 1.0}
    K = spec.K
    alone = LONE_PUMP

    def readout(knob: str, base: float, per_c: float, extra=None):
        a0[K[knob]] = base
        for k, w in cvec.items():
            A[K[knob], k] = per_c * w
        for k, w in (extra or {}).items():
            A[K[knob], k] += w

    readout("b", alone[K["b"]], c[K["b"]] - alone[K["b"]])
    readout("w0", 0.0, c[K["w0"]])
    # tau_m: index rint(y + 2) of (1, 2, 4, 8, 16); alone 8 at y = 1, and the contact level sits mid-step
    ti = {v: i for i, v in enumerate(spec.TAU_M)}
    readout("tau_m", ti[alone[K["tau_m"]]] - 2.0, float(ti[c[K["tau_m"]]] - ti[alone[K["tau_m"]]]))
    # t_ref = 0.5 rint(2y + 4): y = t_ref - 2 is the centre of each step
    readout("t_ref", alone[K["t_ref"]] - 2.0, c[K["t_ref"]] - alone[K["t_ref"]])
    readout("delta", 0.0, {0.0: 0.0, 0.5: 0.5, 1.0: 1.0, 2.0: 2.0}[c[K["delta"]]])  # L(y) = rint(2y)
    a0[K["kappa"]] = 2.0
    a0[K["phi"]] = 2.0 if placement else 0.0
    readout("emit0", -0.984, 2.0, {Kj: -2.0})
    a0[K["emit1"]] = -1.0
    a0[K["p_div"]] = 1.0  # k = rint(4 y): 4 -> 1/16 closed, 7 -> 1/2 open
    A[K["p_div"], Kg] = 0.75
    if reset and gate is not None:
        act[Kr] = 1.0
        b[Kr], Q[Kr] = -12.0, -1.0
        A[K["p_div"], Kr] = -0.75
    if timer > 0:
        act[Kt] = 1.0
        b[Kt], lam[Kt], s0[Kt] = 12.0, LAM_X[128], -12.0
        A[K["p_div"], Kt] = -timer
    a0[K["asym"]] = 12.0
    a0[K["p_die"]] = -2.0
    a0[K["sec0"]] = a0[K["sec1"]] = -30.0
    Dm[:] = -30.0
    km[:] = -30.0
    return g.astype(np.float32)


R25_V1_GRN = GrnOrganism("R25-v1/GRN", r25_genome(),
                         about="R25-v1 written as a GRN genome (gate G9): n_view >= 5 rate gate, flank placement")


def constant_genome(row) -> np.ndarray:
    """A raw GRN genome with no active gene whose readout decodes exactly the phenotype ``row`` at every tick.

    Supports rows whose continuous knobs (asym, sec0, sec1) are 0, as in the lone-cell grid; asym decodes to 1/2,
    which only matters for a dividing cell. Used to check that the GRN layer adds nothing to a fixed phenotype.
    """
    row = np.asarray(row, dtype=np.float64)
    K = spec.K
    if row[K["sec0"]] != 0 or row[K["sec1"]] != 0 or row[K["asym"]] != 0:
        raise ValueError("constant_genome supports rows with asym = sec0 = sec1 = 0")
    g = np.zeros(spec.GENOME_SIZE, dtype=np.float64)
    a0 = spec.genome_view(g, "a0")
    for k in ("w0", "w1", "b", "a0", "a1", "chi"):
        a0[K[k]] = row[K[k]]
    a0[K["tau_m"]] = spec.TAU_M.index(row[K["tau_m"]]) - 2.0
    a0[K["t_ref"]] = row[K["t_ref"]] - 2.0
    for k in ("emit0", "emit1"):
        a0[K[k]] = 1.0 if row[K[k]] else -1.0
    for k, table in (("delta", spec.DELTA), ("kappa", spec.KAPPA), ("phi", spec.PHI)):
        a0[K[k]] = table.index(row[K[k]]) / 2.0
    for k in ("p_div", "p_die"):
        a0[K[k]] = spec.P_FATE.index(row[K[k]]) / 4.0
    for k in ("pol0", "pol1"):
        a0[K[k]] = math.atanh(row[K[k]] / 2.0) if abs(row[K[k]]) < 2 else math.copysign(20.0, row[K[k]])
    a0[K["tau_tr"]] = spec.TAU_TR.index(row[K["tau_tr"]]) - 1.5
    a0[K["sec0"]] = a0[K["sec1"]] = -800.0  # 0.5 sigma(-800) = 0 exactly in float64
    spec.genome_view(g, "Dm")[:] = -30.0
    out = g.astype(np.float32)
    th = spec.decode_knobs(spec.readout(spec.pack_genomes(out[None])[0], np.zeros(spec.G_MAX)))
    bad = [k for k in spec.KNOBS if k != "asym" and th[K[k]] != row[K[k]]]
    if bad:
        raise ValueError(f"row not representable as a constant readout: {bad}")
    return out


def r25_genome_states(organism: GrnOrganism | None = None, program: Organism | None = None) -> dict:
    """The R25-v1 genome's decoded phenotype in each settled gene state against the program row it stands for.

    States (contact, juvenile, gate, echo, reset genes): alone; juvenile or adult with the rate gate closed or open;
    the first tick that sees a contact (contact gene 1/2, echo still 0), where the echo makes the switch exact; and a
    mother right after her claim (gate and reset genes both forced to 1: closed).
    Knobs that program rows do not use (asym, sec0, sec1, tau_tr) are not compared. Returns, per state, the program
    row and the mismatching knobs as (genome, program) pairs (empty when the genome is exact).
    """
    organism = organism or R25_V1_GRN
    program = program or R25_V1
    gt = organism.table("hex")[0]
    prog = program.program
    rows = {k: prog[spec.PROGRAM_ROW[k] * spec.P:(spec.PROGRAM_ROW[k] + 1) * spec.P] for k in spec.PROGRAM_ROWS}
    lo = prog[spec.PROGRAM_SCALAR["p_div_lo"]]
    eps = spec.sigmoid(-10.0)  # a gene's settled level with target sigma(-10)
    states = dict(alone=((eps, 0.0, 0.0, eps), "alone", lo),
                  juvenile_closed=((1.0, 1.0, 0.0, 1.0), "juvenile", lo),
                  juvenile_open=((1.0, 1.0, 1.0, 1.0), "juvenile", None),
                  contact_closed=((1.0, 0.0, 0.0, 1.0), "contact", lo),
                  contact_open=((1.0, 0.0, 1.0, 1.0), "contact", None),
                  first_contact_tick=((0.5, 0.9, 0.0, eps), "juvenile", lo),
                  mother_after_claim=((1.0, 0.0, 1.0, 1.0, 1.0), "contact", lo))
    knobs = [k for k in spec.KNOBS if k not in ("asym", "sec0", "sec1", "tau_tr")]
    out = {}
    for name, (genes, rname, pdiv) in states.items():
        g = np.zeros(spec.G_MAX)
        for k, x in zip((GENE_CONTACT, GENE_JUVENILE, GENE_GATE, GENE_ECHO, GENE_RESET), genes):
            g[k] = x
        th = spec.phenotype(gt, g)
        want = rows[rname].copy()
        if pdiv is not None:
            want[spec.K["p_div"]] = pdiv
        out[name] = dict(row=rname, mismatches={k: (th[spec.K[k]], float(want[spec.K[k]])) for k in knobs
                                                if th[spec.K[k]] != want[spec.K[k]]})
    return out
