"""Counterfactual forks of a genome's life (docs/ONE_LIFE_DESIGN.md, EVALUATION PROTOCOL and COUNTERFACTUAL CLONES).

A fork at ``t_f`` under condition X is the same life (same seed, same world) replayed with ``t_fork = t_f``,
``fork_flags = X`` and the ledger opened at ``t_f`` (LIFE_ABI.md 12). Its unchanged twin is the same replay with no
fork flags. The kernel is deterministic, so the twin and the fork share every event before ``t_f``, and the paired
differences measure only what the condition removes from then on. Conditions (kernel flags):

- ``contacts_off``: spikes undelivered from t_f (no effect on v or traces; contact events are still charged);
- ``chem_off``: morphogen packets off (no transport; secretion and decay go on);
- ``apoptosis_off``, ``division_off``: no deaths, no claims;
- ``identity_clamp``: genes frozen (no gene update and no division partition: a newborn starts with her mother's g;
  the phenotype is still re-decoded);
- ``freeze``: genes, phenotype, division and death all frozen.

A world that already uses its fork slot (the freeze-after-growth control) can only be forked at its own fork time:
the kernel has one ``t_fork``. Other fork times are reported as skipped.
"""
from __future__ import annotations

import math
from dataclasses import replace

import numpy as np

from src.life import build, spec

CONDITIONS = ("contacts_off", "chem_off", "apoptosis_off", "division_off", "identity_clamp", "freeze")
COLUMNS = ("income", "F", "n_end", "spikes", "arrivals", "contact_events", "deaths", "births", "live_time")


def fork_world(base: spec.World, t_fork: float, condition: str | None) -> spec.World | None:
    """The fork of ``base`` at ``t_fork`` (relative to t0) under ``condition``, or its twin for ``None``; ``None`` if
    the world's single fork slot is taken by a control at another time."""
    flags = 0 if condition is None else spec.FLAGS[condition]
    if base.fork_flags:
        if t_fork != base.t_fork:
            return None
        flags |= base.fork_flags
    return replace(base, t_fork=float(t_fork), fork_flags=flags, t_open=max(base.t_open, float(t_fork)))


def _stats(x: np.ndarray) -> tuple[float, float]:
    x = np.asarray(x, dtype=np.float64)
    se = float(x.std(ddof=1) / math.sqrt(len(x))) if len(x) > 1 else 0.0
    return float(x.mean()), se


def run_forks(table: np.ndarray, base: spec.World, seeds, times, conditions=CONDITIONS, *, kind: str | None = None,
              threads: int = 1) -> list[dict]:
    """Forks of every genome (packed table rows ``[G, 809]``) at every time (fractions of T) under every condition,
    each paired with its twin on the same life seeds. All lives run in one kernel batch.

    Returns one row per (genome, time, condition): the twin's and the fork's mean income rate, income per cell
    (income / cell-time) and n_end, and the paired differences (fork - twin) of the income rate and of F, as
    mean and SE over the seeds. A fork the world cannot express is returned with ``skipped`` set.
    """
    table = np.atleast_2d(np.asarray(table, dtype=np.float64))
    seeds = [int(s) for s in seeds]
    kind = kind or base.lattice
    jobs, worlds, rows, life_seeds, skipped = [], [], [], [], []

    def add(w: spec.World, g: int) -> int:
        start = len(worlds)
        for s in seeds:
            worlds.append(w)
            rows.append(g)
            life_seeds.append(s)
        return start

    for g in range(len(table)):
        for frac in times:
            t_f = float(frac) * base.T
            twin, i_twin = fork_world(base, t_f, None), None
            for cond in conditions:
                fork = fork_world(base, t_f, cond)
                if twin is None or fork is None:
                    skipped.append(dict(genome=g, t_fork=t_f, frac=float(frac), condition=cond,
                                        skipped="the fork slot is taken by the control at another time"))
                    continue
                if i_twin is None:
                    i_twin = add(twin, g)  # one twin per genome and fork time, shared by its conditions
                jobs.append((g, float(frac), t_f, cond, i_twin, add(fork, g)))
    out = list(skipped)
    if not jobs:
        return out
    res = build.run(worlds, life_seeds, genomes=table, genome_of=np.array(rows), kind=kind, threads=threads)
    n = len(seeds)
    for g, frac, t_f, cond, i, j in jobs:
        tw, fk = res.ledger[i: i + n], res.ledger[j: j + n]
        window = base.T - max(base.t_open, t_f)
        col = {k: (tw[:, spec.L[k]], fk[:, spec.L[k]]) for k in COLUMNS}
        rate = (col["income"][0] / window, col["income"][1] / window)
        ipc = [c_i / np.maximum(c_l, 1e-300) for c_i, c_l in zip(col["income"], col["live_time"])]
        d_inc, d_inc_se = _stats(rate[1] - rate[0])
        d_F, d_F_se = _stats(col["F"][1] - col["F"][0])
        out.append(dict(genome=g, t_fork=t_f, frac=frac, condition=cond, lives=n, income_twin=float(rate[0].mean()),
                        income_fork=float(rate[1].mean()), d_income=d_inc, d_income_se=d_inc_se, d_F=d_F,
                        d_F_se=d_F_se, ipc_twin=float(ipc[0].mean()), ipc_fork=float(ipc[1].mean()),
                        n_end_twin=float(col["n_end"][0].mean()), n_end_fork=float(col["n_end"][1].mean()),
                        arrivals_twin=float(col["arrivals"][0].mean()), arrivals_fork=float(col["arrivals"][1].mean())))
    return out


def reliance(rows: list[dict], condition: str = "contacts_off") -> float | None:
    """Mean fractional income lost under ``condition`` over the given fork rows: 1 - income_fork / income_twin
    (1 = the income depends entirely on what the condition removes; 0 = not at all). None without income."""
    sel = [r for r in rows if r.get("condition") == condition and "skipped" not in r]
    twin = sum(r["income_twin"] for r in sel)
    if not sel or twin <= 0:
        return None
    return 1.0 - sum(r["income_fork"] for r in sel) / twin
