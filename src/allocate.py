"""Lives per training task: a fixed floor plus learning-progress allocation (docs/OPEN_WORLDS.md 6.2-6.3).

Training bookkeeping outside the organism. Nothing here enters a life's inputs; it only decides how many of a
generation's shared lives each task receives. All arithmetic that decides an allocation is exact (rationals) or
plain float64 on checkpointed inputs, so a resumed run recomputes the same integers.

Rule (``evolve.allocation``, recomputed every ``period`` generations and fixed within each block):

- ``w_t = mix / K + (1 - mix) * (a_t + nu_t) / sum(a + nu)``, uniform when every term is zero;
- ``a_t = max(0, |beta_t| / SE(beta_t) - 1)``: ``beta_t`` is the least-squares slope of task t's fixed-seed probe
  score over the last ``window`` generations (at least three probe points, else 0);
- ``nu_t = novelty_weight * min(novelty_cap, confirmed new behaviour cells of task t in the last
  novelty_window generations)`` (0 without a behaviour grid);
- ``L_t = floor + Neyman share of the budget - K * floor lives in proportion to w_t * sigma_t``, largest remainder,
  at most ``cap``. ``sigma_t`` is the residual (genome x life interaction) noise of task t's shared lives, from a
  two-way ANOVA of the previous block's generations (1 before any estimate).

``mode: uniform`` keeps the equal split ``apportion(budget, 1, floor, cap)`` (the control arm) but still runs and
logs the probe, so arms compare on the same measurement.
"""
from __future__ import annotations

import math
from fractions import Fraction
from numbers import Integral

import numpy as np

MODES = ("uniform", "lp")
DEFAULTS = dict(mode="uniform", budget=24, floor=2, cap=8, mix=0.2, period=5, window=30, probe_top=4,
                probe_lives=8, probe_seed=None, novelty_weight=1.0, novelty_window=10, novelty_cap=3)


def _integer(name, value, low):
    if isinstance(value, bool) or not isinstance(value, Integral) or value < low:
        raise ValueError(f"evolve.allocation.{name} must be an integer >= {low}")
    return int(value)


def _real(name, value, low=0.0, high=math.inf):
    if isinstance(value, bool) or not isinstance(value, (int, float)) or not low <= float(value) <= high:
        raise ValueError(f"evolve.allocation.{name} must be a number in [{low}, {high}]")
    return float(value)


def apportion(total: int, weights, floor: int, cap: int) -> list[int]:
    """Integers ``floor <= L_t <= cap`` summing to ``total``: ``floor`` each, then the rest in proportion to
    ``weights`` by largest remainder. A task whose quota reaches ``cap`` is fixed at ``cap`` and its excess is
    shared among the others (repeated until no quota exceeds a cap). Remainder ties go to the earlier task. Zero
    total weight shares equally. Exact rational arithmetic, so the result never depends on float rounding."""
    raw = [float(x) for x in weights]
    if any(not math.isfinite(x) or x < 0 for x in raw):
        raise ValueError("apportion weights must be finite and nonnegative")
    w = [Fraction(x) for x in raw]
    K = len(w)
    for name, value in (("total", total), ("floor", floor), ("cap", cap)):
        if isinstance(value, bool) or not isinstance(value, Integral):
            raise ValueError(f"apportion {name} must be an integer")
    if not K or floor < 0 or cap < floor or not K * floor <= total <= K * cap:
        raise ValueError("apportion needs at least one task and tasks * floor <= total <= tasks * cap")
    lives = [int(floor)] * K
    left = int(total) - K * int(floor)
    open_ = [t for t in range(K) if lives[t] < cap]
    while left > 0:
        mass = sum((w[t] for t in open_), Fraction(0))
        quota = {t: left * (w[t] / mass if mass > 0 else Fraction(1, len(open_))) for t in open_}
        full = [t for t in open_ if lives[t] + quota[t] >= cap]
        if full:
            for t in full:
                left -= cap - lives[t]
                lives[t] = int(cap)
            open_ = [t for t in open_ if t not in full]
            continue
        base = {t: math.floor(quota[t]) for t in open_}
        for t in open_:
            lives[t] += base[t]
        rest = left - sum(base.values())
        for t in sorted(open_, key=lambda t: (-(quota[t] - base[t]), t))[:rest]:
            lives[t] += 1
        left = 0
    return lives


def slope(points) -> tuple[float, float]:
    """Least-squares slope of ``[(generation, score), ...]`` and its standard error (inf below three points or
    without spread in generation)."""
    if len(points) < 3:
        return 0.0, math.inf
    x = np.array([float(p[0]) for p in points], dtype=np.float64)
    y = np.array([float(p[1]) for p in points], dtype=np.float64)
    dx = x - x.mean()
    sxx = float(np.dot(dx, dx))
    if sxx == 0:
        return 0.0, math.inf
    beta = float(np.dot(dx, y - y.mean())) / sxx
    resid = y - y.mean() - beta * dx
    se = math.sqrt(float(np.dot(resid, resid)) / (len(x) - 2) / sxx)
    return beta, se


def progress(points) -> float:
    """``a = max(0, |beta| / SE - 1)``: absolute learning progress in standard errors beyond one. A perfectly
    linear nonflat series (SE 0) is infinite progress; a flat one is none."""
    beta, se = slope(points)
    if se == 0:
        return math.inf if beta != 0 else 0.0
    return max(0.0, abs(beta) / se - 1.0)


def lp_weights(a, nu, mix: float) -> list[float]:
    """``w_t = mix / K + (1 - mix) * s_t / sum(s)`` with ``s = a + nu``; uniform if every term is zero, and tasks
    with infinite progress share the ``1 - mix`` part equally."""
    s = [float(x) + float(y) for x, y in zip(a, nu)]
    K = len(s)
    infinite = [t for t in range(K) if math.isinf(s[t])]
    if infinite:
        share = [1.0 / len(infinite) if t in infinite else 0.0 for t in range(K)]
    else:
        total = math.fsum(s)
        share = [x / total for x in s] if total > 0 else [1.0 / K] * K
    return [mix / K + (1.0 - mix) * x for x in share]


def residual_variance(scores) -> float | None:
    """Two-way ANOVA (genome x life, one observation per cell) residual variance of ``[genomes, lives]`` scores:
    the noise left after each genome's mean and each shared life's mean, which is what ranking on common lives
    must overcome. None below two genomes or two lives."""
    x = np.asarray(scores, dtype=np.float64)
    if x.ndim != 2 or x.shape[0] < 2 or x.shape[1] < 2:
        return None
    r = x - x.mean(axis=1, keepdims=True) - x.mean(axis=0, keepdims=True) + x.mean()
    return float((r * r).sum() / ((x.shape[0] - 1) * (x.shape[1] - 1)))


class Allocator:
    """Lives per task for each generation; ``state`` is plain data for checkpoints (``load`` restores it)."""

    def __init__(self, conf, tasks):
        raw = dict(conf or {})
        unknown = set(raw) - set(DEFAULTS)
        if unknown:
            raise ValueError(f"unknown evolve.allocation keys {sorted(unknown)}")
        c = {**DEFAULTS, **raw}
        self.tasks = tuple(tasks)
        K = len(self.tasks)
        if not K:
            raise ValueError("evolve.allocation needs life.training_tasks")
        if c["mode"] not in MODES:
            raise ValueError(f"evolve.allocation.mode must be one of {MODES}")
        self.mode = str(c["mode"])
        self.budget = _integer("budget", c["budget"], 1)
        self.floor = _integer("floor", c["floor"], 1)  # never drop a task: every task keeps at least one life
        self.cap = _integer("cap", c["cap"], self.floor)
        if not K * self.floor <= self.budget <= K * self.cap:
            raise ValueError(f"evolve.allocation needs tasks * floor <= budget <= tasks * cap ({K} tasks)")
        self.mix = _real("mix", c["mix"], 0.0, 1.0)
        self.period = _integer("period", c["period"], 1)
        self.window = _integer("window", c["window"], 1)
        self.probe_top = _integer("probe_top", c["probe_top"], 1)
        self.probe_lives = _integer("probe_lives", c["probe_lives"], 0)
        if self.mode == "lp" and not self.probe_lives:
            raise ValueError("evolve.allocation.mode lp needs probe_lives > 0")
        self.probe_seed = None if c["probe_seed"] is None else _integer("probe_seed", c["probe_seed"], 0)
        self.novelty_weight = _real("novelty_weight", c["novelty_weight"])
        self.novelty_window = _integer("novelty_window", c["novelty_window"], 1)
        self.novelty_cap = _integer("novelty_cap", c["novelty_cap"], 0)
        self.state = {"allocation": None, "block_start": None, "probes": [], "noise": [], "block": None}

    def load(self, state: dict) -> None:
        self.state = {k: state[k] for k in ("allocation", "block_start", "probes", "noise", "block")}

    @property
    def lives(self) -> list[int]:
        return list(self.state["allocation"])

    def begin(self, g: int, novelty_counts) -> dict | None:
        """The allocation of generation ``g``: recomputed at the first call and at each block start (``g`` a
        multiple of ``period``), else unchanged. Returns the recompute record (also kept in ``state['block']``)
        or None. ``novelty_counts`` are confirmed new cells per task in the last ``novelty_window``
        generations."""
        if self.state["allocation"] is not None and g % self.period:
            return None
        K = len(self.tasks)
        probes = [p for p in self.state["probes"] if g - self.window < p[0] <= g]
        a = [progress([(p[0], p[1][t]) for p in probes]) for t in range(K)]
        nu = [self.novelty_weight * min(self.novelty_cap, int(n)) for n in novelty_counts]
        noise = [n for n in self.state["noise"] if g - self.period <= n[0] < g]
        sigma = []
        for t in range(K):
            values = [n[1][t] for n in noise if n[1][t] is not None]
            sigma.append(math.sqrt(math.fsum(values) / len(values)) if values else 1.0)
        if self.mode == "uniform":
            w = [1.0 / K] * K
            lives = apportion(self.budget, [1.0] * K, self.floor, self.cap)
        else:
            w = lp_weights(a, nu, self.mix)
            lives = apportion(self.budget, [x * s for x, s in zip(w, sigma)], self.floor, self.cap)
        record = {"generation": int(g), "mode": self.mode, "lives": lives,
                  "a": [None if math.isinf(x) else x for x in a], "a_infinite": [math.isinf(x) for x in a],
                  "nu": nu, "w": w, "sigma": sigma, "probe_points": len(probes), "noise_generations": len(noise)}
        self.state.update(allocation=lives, block_start=int(g), block=record,
                          probes=[p for p in self.state["probes"] if p[0] > g - self.window],
                          noise=[n for n in self.state["noise"] if n[0] >= g - self.period])
        return record

    def race(self, total: int) -> list[int]:
        """Race lives per task "on the same allocation": the generation's own vector when ``total`` equals the
        budget, else ``total`` apportioned in proportion to it (tasks may then get zero race lives)."""
        lives = self.lives
        if total == sum(lives):
            return lives
        return apportion(total, lives, 0, total)

    def observe_noise(self, g: int, variances) -> None:
        self.state["noise"].append([int(g), [None if v is None else float(v) for v in variances]])

    def probe_due(self, generation: int) -> bool:
        """A probe is measured at generation ``generation`` (after generation ``generation - 1``), every
        ``period`` generations, so each block start sees the latest point."""
        return bool(self.probe_lives) and generation > 0 and generation % self.period == 0

    def add_probe(self, generation: int, scores) -> None:
        self.state["probes"].append([int(generation), [float(x) for x in scores]])
