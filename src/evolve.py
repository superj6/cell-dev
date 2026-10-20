"""Evolution: (mu+lambda) selection with two-parent crossover ("sex") or mutation only ("asex").

The population descends from a few founders (the fittest random genomes; sampling continues in batches until one of
them actually scores). Descendants of one founder share homologous gene slots; crossing different founders is
cross-breeding between lines. Every generation draws fresh trials; parents are re-evaluated on them with
the children. Every ``heldout_every`` generations the best genome is scored on fresh in-distribution trials ("valid")
and on held-out trials from wider ranges ("heldout": generalization). On the ladder the run moves up a rung once the
valid score reaches ``advance_at``; with ``immigrants`` > 0 that share of the population is then replaced by new
founders sampled on the new rung, so crossover can hybridize the old lineage with breeds that have a foothold there.

``mode: life`` (docs/ONE_LIFE_DESIGN.md) runs the same founder sampling, fill and (mu+lambda) loop on one-life
genomes (``LifeLayout``) scored by ``src.life.evaluate.LifeEvaluator``: every generation draws fresh life seeds shared
by the whole population (common random numbers), parents are re-evaluated with their children, and the run writes
lineage.jsonl (parents, unit masks, mutation ops, the slot registry) and counterfactual forks (clones.jsonl). With
two-stage selection (``evolve.recheck_k`` > 0 and ``evolve.recheck_lives`` > 0) the top ``recheck_k`` genomes on the
generation's lives live ``recheck_lives`` more fresh shared lives before the parents are chosen (``recheck``).
"""
from __future__ import annotations

import itertools
import json
import time
from collections import Counter
from dataclasses import dataclass, replace
from pathlib import Path

import numpy as np
import torch
from omegaconf import OmegaConf

from src.cells import decode_cells, run_cells
from src.develop import Tissue, develop
from src.genome import Dims, Layout, make_dims, make_layout
from src.lattice import Lattice, build_lattice
from src.tasks import Ladder, build_task
from src.tasks.base import Trials, direction_score


@dataclass
class Eval:
    fitness: torch.Tensor
    score: torch.Tensor
    energy: torch.Tensor
    n_cells: torch.Tensor
    spikes: torch.Tensor
    divisions: torch.Tensor
    trial_scores: torch.Tensor  # [B, E]

    def take(self, i: int) -> dict:
        return {k: float(getattr(self, k)[i]) for k in ("fitness", "score", "energy", "n_cells", "spikes", "divisions")}


class Evaluator:
    def __init__(self, cfg, lattice: Lattice, layout: Layout):
        self.cfg, self.lattice, self.layout = cfg, lattice, layout

    def develop(self, params: torch.Tensor, record: bool = False):
        d = self.cfg.develop
        if d.get("mode", "grow") == "fixed":  # baseline: a pre-made disk of one cell type; only the cell rule evolves
            B = params.shape[0]
            disk = (self.lattice.pos.norm(dim=1) <= float(d.fixed_radius) + 1e-3)[None].expand(B, -1).clone()
            return Tissue(alive=disk, g=torch.zeros(B, self.lattice.n, self.layout.dims.genes),
                          types=torch.zeros(B, self.lattice.n, dtype=torch.long), divisions=torch.zeros(B, dtype=torch.long),
                          history=[(disk, torch.zeros_like(disk, dtype=torch.long))] if record else [])
        return develop(self.lattice, self.layout, params, steps=d.steps, rate=d.rate, min_cycle=d.min_cycle,
                       substeps=d.substeps, secretion=d.secretion, jitter_seed=d.jitter_seed, record=record)

    @torch.inference_mode()
    def __call__(self, params: torch.Tensor, trials: Trials, messages: bool = True) -> Eval:
        parts = [self._eval(params[i: i + self.cfg.evolve.batch], trials, messages)
                 for i in range(0, params.shape[0], self.cfg.evolve.batch)]
        return Eval(*[torch.cat([getattr(p, f) for p in parts]) for f in Eval.__dataclass_fields__])

    def _eval(self, params, trials, messages) -> Eval:
        tissue = self.develop(params)
        rule = decode_cells(self.layout, params, self.cfg.cells.quantize)
        messages = messages and bool(self.cfg.cells.get("messages", True))
        act = run_cells(self.lattice, tissue.alive, tissue.types, rule, trials.stim, trials.window, messages=messages)
        s = direction_score(act.counts, self.lattice.pos, tissue.alive, trials.target, self.cfg.task.min_spikes,
                            self.cfg.task.score)
        c = self.cfg.costs
        n_cells = tissue.n_cells.float()
        energy = c.live * n_cells + c.spike * act.spikes + c.divide * tissue.divisions.float()
        score = s.mean(1)
        return Eval(fitness=score - energy, score=score, energy=energy, n_cells=n_cells, spikes=act.spikes,
                    divisions=tissue.divisions.float(), trial_scores=s)


def run_mode(cfg) -> str:
    """``trials`` (the legacy tick pipeline, the default) or ``life`` (one continuous life per genome)."""
    mode = str(cfg.get("mode", "trials"))
    if mode not in ("trials", "life"):
        raise ValueError(f"unknown mode {mode!r} (trials | life)")
    return mode


def setup(cfg):
    if run_mode(cfg) == "life":  # no lattice disk and no task: the world and the fabric live in the kernel
        from src.life.evaluate import LifeEvaluator

        dims = make_dims({**OmegaConf.to_container(cfg.genome.life, resolve=True), "kind": "life"})
        g = cfg.genome
        plain = {k: None if g.get(k) is None else OmegaConf.to_container(g[k]) for k in ("knob_init", "input_init",
                                                                                         "readout_std")}
        layout = make_layout(dims, **plain)
        return None, layout, None, LifeEvaluator(cfg, layout)
    lattice = build_lattice(cfg.lattice.kind, cfg.lattice.radius, cfg.lattice.contact)
    layout = Layout(Dims(**cfg.genome.dims))
    task = build_task(cfg.task.name, cfg.task.length, cfg.task.start, cfg.task.keep_earlier, cfg.task.get("rungs"))
    return lattice, layout, task, Evaluator(cfg, lattice, layout)


def sample_founders(cfg, ev: Evaluator, layout: Layout, sample, gen: torch.Generator,
                    collect: list | None = None) -> tuple[torch.Tensor, int, dict]:
    """Random genomes in batches until one of them actually scores (a dead single cell has nothing to climb from), up
    to ``max_init_samples``. Returns the fittest ``founders`` with scorers ranked first, the evaluations used, and a
    summary. ``sample(gen)`` draws the trials to score them on. ``evolve.founder_key`` picks what must reach
    ``min_founder_score``: ``score`` (default) or ``fitness`` (life mode: F >= 0.02). With ``evolve.founder_all``
    sampling never stops early: all ``max_init_samples`` are drawn and the founders are the fittest of them (scorers
    first), so one lucky genome cannot end the search (BODY-1, where founders are rare). ``collect`` receives every
    batch's evaluation (for the life census)."""
    e = cfg.evolve
    min_score = float(e.get("min_founder_score", 0.0))
    key = str(e.get("founder_key", "score"))
    sample_all = bool(e.get("founder_all", False))
    if sample_all and e.get("max_init_samples") is None:
        raise ValueError("evolve.founder_all needs evolve.max_init_samples")
    pool, fits, scores, evals = [], [], [], 0
    while True:
        cands = layout.random(int(e.init_samples), gen, float(cfg.genome.init_scale))
        res = ev(cands, sample(gen))
        if collect is not None:
            collect.append(res)
        pool.append(cands)
        fits.append(res.fitness)
        scores.append(getattr(res, key))
        evals += cands.shape[0]
        if evals >= int(e.get("max_init_samples", evals)) or (not sample_all and float(torch.cat(scores).max())
                                                                >= min_score):
            break
    pool, fits, scores = torch.cat(pool), torch.cat(fits), torch.cat(scores)
    order = fits.argsort(descending=True)
    scorer = scores[order] >= min_score
    ranked = torch.cat([order[scorer], order[~scorer]])  # scorers first (by fitness), then everything else
    founders = pool[ranked[: min(int(e.founders), len(ranked))]]
    info = {"sampled": evals, "best_fitness": float(fits.max()), "best_score": float(scores.max()),
            "scoring_founders": int(min(int(scorer.sum()), founders.shape[0]))}
    if key != "score":
        info["founder_key"] = key
    return founders, evals, info


def fill(founders: torch.Tensor, n: int, layout: Layout, gen: torch.Generator, e, ops: list | None = None) -> torch.Tensor:
    """n individuals: each founder once, then mutated copies of the founders in turn (``ops`` receives the life
    layout's mutation records of the copies)."""
    pop = founders[torch.arange(n) % founders.shape[0]].clone()
    kw = {} if ops is None else {"ops": ops}
    pop[founders.shape[0]:] = layout.mutate(pop[founders.shape[0]:], gen, int(e.n_mut), float(e.p_cell), **kw)
    return pop


def evolve(cfg, log=print, out: Path | None = None, *, resume: dict | None = None,
           checkpoint=None, stop_after: int | None = None) -> dict:
    if run_mode(cfg) == "life":
        return evolve_life(cfg, log, out, resume=resume, checkpoint=checkpoint, stop_after=stop_after)
    if resume is not None or checkpoint is not None or stop_after is not None:
        raise ValueError("checkpoint/resume is supported only in life mode")
    torch.set_num_threads(int(cfg.threads))
    gen = torch.Generator().manual_seed(int(cfg.seed))
    valid_gen = torch.Generator().manual_seed(int(cfg.seed) + 5_000)  # fresh trials from the training distribution
    held_gen = torch.Generator().manual_seed(int(cfg.seed) + 10_000)  # unseen directions, wider ranges
    lattice, layout, task, ev = setup(cfg)
    e, mu, lam = cfg.evolve, int(cfg.evolve.mu), int(cfg.evolve.lam)
    pos, n_trials = lattice.pos, int(cfg.task.trials)

    founders, evals, info = sample_founders(cfg, ev, layout, lambda g: task.sample(pos, n_trials, g), gen)
    pop = fill(founders, mu, layout, gen, e)
    log({"event": "founders", **info})

    curves, valid, heldout = [], None, None
    for g in range(int(e.generations)):
        trials = task.sample(pos, n_trials, gen)
        ia = torch.randint(mu, (lam,), generator=gen)
        if e.breeding == "sex":
            kids = layout.crossover(pop[ia], pop[torch.randint(mu, (lam,), generator=gen)], gen)
        else:
            kids = pop[ia].clone()
        kids = layout.mutate(kids, gen, int(e.n_mut), float(e.p_cell))
        everyone = torch.cat([pop, kids])
        res = ev(everyone, trials)
        evals += everyone.shape[0]
        order = res.fitness.argsort(descending=True)[:mu]
        pop = everyone[order]
        row = {"gen": g, "evals": evals, "rung": task.rung_id, **res.take(int(order[0])),
               "mean_score": float(res.score[order].mean())}
        if g % int(e.heldout_every) == 0 or g == int(e.generations) - 1:
            rung = task.rungs[task.rung] if isinstance(task, Ladder) else task
            valid = float(ev(pop[:1], rung.sample(pos, int(cfg.task.heldout_trials), valid_gen)).score[0])
            heldout = float(ev(pop[:1], rung.sample(pos, int(cfg.task.heldout_trials), held_gen, heldout=True)).score[0])
            row.update(valid=valid, heldout=heldout)
            final = g == int(e.generations) - 1  # never advance after the last generation: nothing trains on it
            if isinstance(task, Ladder) and not final and valid >= float(e.advance_at) and task.advance():
                row["advanced_to"] = task.rung_id
                share = float(e.get("immigrants", 0.0))
                if share > 0:  # new breeds with a foothold on the new rung replace part of the population
                    new_rung = task.rungs[task.rung]
                    imm, used, info = sample_founders(cfg, ev, layout, lambda g, r=new_rung: r.sample(pos, n_trials, g),
                                                      gen)
                    evals += used
                    k = int(round(mu * share))
                    pop = torch.cat([pop[: mu - k], fill(imm, k, layout, gen, e)])
                    row["immigrants"] = {**info, "replaced": k}
        curves.append(row)
        log(row)
    return {"best": pop[0], "population": pop, "curves": curves, "evals": evals, "valid": valid, "heldout": heldout,
            "rung": task.rung_id, "lattice": lattice, "layout": layout, "task": task, "evaluator": ev}


# ======================================================================================================== mode: life
class Lineage:
    """Writes lineage.jsonl: a founders row, then one row per generation.

    Each generation row holds the life seeds, the children kept by selection (``logging.lineage: survivors``, the
    default) or every child (``all``) with their parent ids, unit mask (bit u set = unit u from parent a; null under
    mutation only) and mutation ops, the surviving ids and fitness, the breeds (founder of each parent-a chain), the
    slot registry (per gene slot: how many survivors carry each innovation id there) and the mean pairwise genome
    distance. Under two-stage selection a ``recheck`` entry adds the recheck seeds, the key, the shortlist's ids with
    their F on the generation's lives and on the recheck lives, and how many parents the recheck changed; the
    survivors' fitness is then their mean over all their lives. ``clones`` rows go to clones.jsonl.
    """

    def __init__(self, out: Path | None, mode: str = "survivors", *, append: bool = False):
        if mode not in ("survivors", "all"):
            raise ValueError(f"logging.lineage must be survivors or all, got {mode!r}")
        self.mode = mode
        self.fh = open(out / "lineage.jsonl", "a" if append else "w") if out is not None else None
        self.clones_fh = open(out / "clones.jsonl", "a" if append else "w") if out is not None else None

    @staticmethod
    def _dump(fh, row: dict) -> None:
        if fh is not None:
            fh.write(json.dumps(row) + "\n")
            fh.flush()

    def write(self, row: dict) -> None:
        self._dump(self.fh, row)

    def clones(self, rows: list[dict]) -> None:
        for r in rows:
            self._dump(self.clones_fh, r)

    def close(self) -> None:
        for fh in (self.fh, self.clones_fh):
            if fh is not None:
                fh.close()


def mask_bits(row: torch.Tensor) -> int:
    """A unit mask row as an int (bit u = unit u came from parent a)."""
    return sum(1 << u for u, b in enumerate(row.tolist()) if b)


def registry(origins: torch.Tensor) -> dict:
    """Slot registry of a population: gene slot -> {innovation id: carriers} over active slots (origin >= 0)."""
    out = {}
    for k in range(origins.shape[1]):
        c = Counter(int(x) for x in origins[:, k].tolist() if x >= 0)
        if c:
            out[str(k)] = {str(i): n for i, n in sorted(c.items())}
    return out


def life_census(evals: list, min_F: float) -> dict:
    """Founder-sample census: share reaching the founder bar, lone non-dividing cells, extinct and guard-tripped lives,
    and quantiles of the final size and F."""
    F = torch.cat([r.fitness for r in evals])
    n = torch.cat([r.n_cells for r in evals])
    div = torch.cat([r.divisions for r in evals])
    q = torch.tensor([0.1, 0.5, 0.9], dtype=torch.float64)
    return {"census_F_ge_min": float((F >= min_F).double().mean()),
            "census_lone": float(((n == 1) & (div == 0)).double().mean()),
            "census_extinct": float(torch.cat([r.extinct for r in evals]).mean()),
            "census_guard": float(torch.cat([r.guard for r in evals]).mean()),
            "census_n_end_q": [float(x) for x in torch.quantile(n.double(), q)],
            "census_F_q": [float(x) for x in torch.quantile(F.double(), q)]}


def clone_targets(breeds: torch.Tensor, top: int) -> list[int]:
    """Ranks of a fitness-sorted population to fork: the top ``top`` and each other breed's best (design: the top 8
    genomes and each surviving breed's best)."""
    sel = list(range(min(top, len(breeds))))
    seen = {int(breeds[i]) for i in sel}
    for i, b in enumerate(breeds.tolist()):
        if b not in seen:
            seen.add(b)
            sel.append(i)
    return sel


def clone_summary(rows: list[dict]) -> dict:
    """Mean paired income-rate change per ``condition@fraction`` over the forked genomes (skipped forks left out)."""
    groups: dict[str, list[float]] = {}
    for r in rows:
        if "skipped" not in r:
            groups.setdefault(f"{r['condition']}@{r['frac']:g}", []).append(r["d_income"])
    return {k: sum(v) / len(v) for k, v in groups.items()}


RECHECK_KEYS = ("all", "recheck")
BODY_CELLS = 1.5  # a body: mean end size over the generation's lives >= 1.5 cells (the selection study's definition)


def recheck_plan(e, mu: int, n: int) -> tuple[int, int, str]:
    """Two-stage selection settings from ``evolve``: (shortlist size, recheck lives, key), with shortlist size 0 when
    ``recheck_k`` or ``recheck_lives`` is 0 (off). The shortlist is capped at the ``n`` genomes of a generation and
    must hold at least ``mu``. ``recheck_key``: ``all`` ranks the shortlist by the mean over the generation's lives and
    the recheck lives, ``recheck`` by the recheck lives only."""
    k, lives = int(e.get("recheck_k", 0) or 0), int(e.get("recheck_lives", 0) or 0)
    key = str(e.get("recheck_key", "all"))
    if key not in RECHECK_KEYS:
        raise ValueError(f"evolve.recheck_key must be one of {RECHECK_KEYS}, got {key!r}")
    if k < 0 or lives < 0:
        raise ValueError(f"evolve.recheck_k and recheck_lives must be >= 0, got {k} and {lives}")
    if k == 0 or lives == 0:
        return 0, 0, key
    if k < mu:
        raise ValueError(f"evolve.recheck_k = {k}: the shortlist must hold at least mu = {mu} genomes (or 0: off)")
    return min(k, n), lives, key


def recheck_draw(ev, g: int, base: int, lives: int):
    """The recheck lives of generation ``g``: lives ``base`` to ``base + lives - 1`` of the generation's own draw,
    whose first ``base`` lives every genome lived. So they are fresh every generation, shared by the shortlist
    (common random numbers), disjoint from the generation's lives and from every founder, valid, held-out, final and
    clone life (other purposes), and under the envelope control they get envelope physics like any selection life."""
    full = ev.draw("gen", g, lives=base + lives)
    extra = {"tasks": full.tasks[base:]} if getattr(full, "tasks", ()) else {}
    return replace(full, seeds=full.seeds[base:], worlds=full.worlds[base:], **extra)


def rows(e: Eval, idx: torch.Tensor) -> Eval:
    """The evaluation of genomes ``idx`` only, in that order (same class)."""
    return type(e)(*[getattr(e, f)[idx] for f in e.__dataclass_fields__])


def pooled(a: Eval, b: Eval) -> Eval:
    """One evaluation of the same genomes on the lives of ``a`` and then those of ``b``: ``trial_scores`` joined,
    fitness the mean of the per-life F (bitwise what a single evaluation on all those lives gives) and every other
    statistic the lives-weighted mean of the two. Per-life fields ``[B, L, D]`` (``life_columns``) are joined like
    ``trial_scores``."""
    La, Lb = a.trial_scores.shape[1], b.trial_scores.shape[1]
    ts = np.concatenate([a.trial_scores.numpy(), b.trial_scores.numpy()], axis=1)
    per_life = [f for f in a.__dataclass_fields__ if getattr(a, f).ndim == 3]
    out = {f: (La * getattr(a, f) + Lb * getattr(b, f)) / (La + Lb) for f in a.__dataclass_fields__
           if f not in ("trial_scores", "fitness", *per_life)}
    out.update({f: torch.cat([getattr(a, f), getattr(b, f)], dim=1) for f in per_life})
    return type(a)(**out, trial_scores=torch.from_numpy(ts), fitness=torch.from_numpy(ts.mean(axis=1)))


TIE_SEED = 7_919_001  # offset of the tie-breaking generator's seed from the run seed (its own stream)


def rank_desc(fitness: torch.Tensor, tie_gen: torch.Generator | None = None) -> torch.Tensor:
    """Indices by fitness, best first. Exact ties are broken by a random permutation drawn from ``tie_gen``, a stream of
    its own, so a generation without ties ranks exactly as before. Without a generator ties keep index order: the old
    rule, under which parents (listed first) always beat equal children and neutral drift stops on exact plateaus
    (RESULTS.md 2026-10-09: four v1 populations froze for 244-364 generations at the lone-cell value)."""
    if tie_gen is None:
        return fitness.argsort(descending=True, stable=True)
    perm = torch.randperm(fitness.shape[0], generator=tie_gen)
    return perm[fitness[perm].argsort(descending=True, stable=True)]


def recheck(ev, everyone: torch.Tensor, res: Eval, g: int, mu: int, k: int, lives: int, key: str,
            tie_gen: torch.Generator | None = None) -> dict:
    """Two-stage selection of generation ``g``. ``res`` holds every genome on the generation's lives; the top ``k`` by
    that mean (the shortlist) live ``lives`` more lives (``recheck_draw``), and the ``mu`` parents are the top of the
    shortlist by ``key`` (``all``: the mean over all its lives; ``recheck``: the recheck lives only). Exact ties are
    broken by ``tie_gen`` (``rank_desc``), or by index without it. Returns the parents' indices ``order``, their
    evaluation on all their lives ``chosen`` (rank order), the ``shortlist``, the recheck ``draw`` and its evaluation
    ``res`` (shortlist order), ``pick`` (the parents' places in the shortlist), ``changed`` (parents the generation's
    lives alone would not have chosen) and the kernel time ``t``."""
    ranked = rank_desc(res.fitness, tie_gen)
    short = ranked[:k]
    draw = recheck_draw(ev, g, res.trial_scores.shape[1], lives)
    t0 = time.perf_counter()
    rres = ev(everyone[short], draw)
    t = time.perf_counter() - t0
    both = pooled(rows(res, short), rres)
    pick = rank_desc(both.fitness if key == "all" else rres.fitness, tie_gen)[:mu]
    order = short[pick]
    changed = mu - len(set(order.tolist()) & set(ranked[:mu].tolist()))
    return dict(order=order, chosen=rows(both, pick), shortlist=short, draw=draw, res=rres, pick=pick, changed=changed,
                t=t)


def recheck_bodies(curves: list[dict]) -> dict:
    """What the recheck did to bodies over a run (``evolve_life`` rows), for its results row: the bodies among the
    chosen parents and among those one-stage selection would have chosen, summed over generations, and
    ``recheck_body_losses``, the generations where the recheck dropped every body one-stage selection would have
    kept. All None for a one-stage run."""
    rc = [c for c in curves if "recheck_bodies" in c]
    if not rc:
        return dict(recheck_bodies=None, recheck_bodies_onestage=None, recheck_body_losses=None)
    return dict(recheck_bodies=sum(c["recheck_bodies"] for c in rc),
                recheck_bodies_onestage=sum(c["recheck_bodies_onestage"] for c in rc),
                recheck_body_losses=sum(c["recheck_bodies_onestage"] > 0 and c["recheck_bodies"] == 0 for c in rc))


CATCH_SEED = "catch_reflex"  # BODY-1's seeded ancestor (BODY_DESIGN_PROPOSAL.md 7, arm b)


def seed_genome(cfg, layout) -> torch.Tensor:
    """The founder of a seeded run (``evolve.seed_genome``), as one raw genome ``[1, size]``: ``r25_v1`` (the hand-built
    R25-v1 written as a GRN genome, gate G9; uncapped it grows until the N_max guard), ``r25_v1_timer`` (the same with
    its lineage-timer gene at ``evolve.seed_timer``, default 1.125, a local stop rule), ``catch_reflex`` (BODY-1's
    seeded ancestor, the declared hedge of BODY_DESIGN_PROPOSAL.md 7: the smallest hand-written ABI-3 GRN that grows
    the 2-cell clicker from one zygote, ``handbuilt.catch_reflex_genome()`` or else the gates' column genome
    ``handbuilt.column_genome(rings=0)``), or the path of a saved genome (``best_genome.json``). Design control: "the
    population starts from the R25-v1 genome"; never the main result."""
    from src.life import handbuilt as hb
    from src.life import spec

    name = str(cfg.evolve.seed_genome)
    D = spec.V3.lattice_degree(str(cfg.lattice.kind))
    if name == CATCH_SEED:
        make = getattr(hb, "catch_reflex_genome", None)
        if make is None and hasattr(hb, "column_genome"):
            make = lambda: hb.column_genome(0)  # noqa: E731  (gate GB9's genome that grows the 2-cell clicker)
        if make is None:
            raise NotImplementedError("the seeded CATCH arm needs the hand GRN 2-cell clicker of gate GB9 "
                                      "(handbuilt.catch_reflex_genome or handbuilt.column_genome), which "
                                      "src/life/handbuilt.py does not provide yet")
        g = torch.as_tensor(np.asarray(make(), dtype=np.float32))
        if g.numel() != layout.size:
            raise ValueError(f"{name}: a genome of {g.numel()} slots for a layout of {layout.size}")
    elif name == "r25_v1":
        g = torch.from_numpy(hb.r25_genome(D=D))
    elif name == "r25_v1_timer":
        g = torch.from_numpy(hb.r25_genome(timer=float(cfg.evolve.get("seed_timer", 1.125)), D=D))
    else:
        saved_layout, g = Layout.load(name)
        if saved_layout.size != layout.size or getattr(saved_layout.dims, "kind", None) != "life":
            raise ValueError(f"{name}: not a life genome of this layout")
    return g.reshape(1, -1).to(torch.float32)


def evolve_life(cfg, log=print, out: Path | None = None, *, resume: dict | None = None,
                checkpoint=None, stop_after: int | None = None) -> dict:
    """(mu+lambda) evolution of one-life genomes (module docstring); the loop mirrors ``evolve``. With
    ``evolve.seed_genome`` the population descends from that one genome instead of sampled founders (seeded control).
    Each generation row carries its wall time ``t_gen``, the population's kernel time ``t_eval`` (seconds) and the
    population's shares of invalid lives and of ledger-check failures (``pop_invalid``, ``pop_mismatch``).

    Two-stage selection (``recheck``; off when ``evolve.recheck_k`` or ``recheck_lives`` is 0, which is the one-stage
    loop exactly): the parents are chosen from the shortlist on more lives, and their row statistics, lineage fitness
    and returned fitness are their means over all their lives (the population shares ``pop_*`` and the children's
    lineage fitness stay those of the generation's lives). The rows add ``recheck_k`` (shortlist size),
    ``recheck_changed``, ``recheck_F`` and ``recheck_F_base`` (the parents' mean F on the recheck lives and on the
    generation's lives), ``recheck_invalid`` and ``t_recheck``. ``evals`` counts genome evaluations on the
    generation's L lives, so a recheck of K genomes on L2 lives adds K * L2 / L. ``recheck_bodies`` and
    ``recheck_bodies_onestage`` count the bodies (``BODY_CELLS``) among the chosen parents and among the parents that
    one-stage selection would have chosen, both on the generation's lives: what the recheck did to multi-cell
    genomes, so a run that stays at 1-2 cells can tell whether the recheck dropped its bodies.

    Life-length draw (``life.T_choices``, gate GB11; ``LifeEvaluator.draw``): each generation's lives and its recheck
    lives last one length drawn from the list, so every genome of a generation is ranked on the same lives; the rows
    and lineage rows then record it (``T``). Fitness is per unit time on those lives. ``evals`` still counts genome
    evaluations, whatever their length. ``life.T`` must be one of the choices: it is the nominal length that valid,
    held-out, clone and final lives use, and a run that overrides it alone would select on other lengths."""
    if (cfg.evolve.get("selection") is not None or cfg.evolve.get("seed_population")
            or cfg.evolve.get("seed_archive") or cfg.evolve.get("allocation")):
        from src.search import evolve_family

        return evolve_family(cfg, log=log, out=out, resume=resume, checkpoint=checkpoint, stop_after=stop_after)

    from src.life import clones

    torch.set_num_threads(int(cfg.threads))
    gen = torch.Generator().manual_seed(int(cfg.seed))
    _, layout, _, ev = setup(cfg)
    e, lc, cc = cfg.evolve, cfg.life, cfg.get("clones") or {}
    # exact ties broken at random (evolve.random_ties, default on); false restores index order (parents win)
    tie_gen = torch.Generator().manual_seed(int(cfg.seed) + TIE_SEED) if e.get("random_ties", True) else None
    if getattr(ev, "T_choices", ()) and ev.T not in ev.T_choices:
        raise ValueError(f"life.T = {ev.T:g} is not one of life.T_choices {list(ev.T_choices)}: the nominal length "
                         "of the judged lives must be one of the selection lengths (override both, or T_choices=null)")
    mu, lam, G = int(e.mu), int(e.lam), layout.dims.genes_max
    k_re, l_re, key_re = recheck_plan(e, mu, mu + lam)
    lin = Lineage(out, str(cfg.logging.get("lineage", "survivors")), append=resume is not None)
    mut_kw = dict(dup_rate=float(e.get("dup_rate", 0.0)), del_rate=float(e.get("del_rate", 0.0)),
                  split=bool(e.get("dup_split", False)), scale_n_mut=bool(e.get("n_mut_scale", True)))

    if resume is None:
        if e.get("seed_genome"):
            founders, evals, info = seed_genome(cfg, layout), 0, {"sampled": 0, "seeded": str(e.seed_genome)}
        else:
            batches, sampled = itertools.count(), []
            def sample(g):
                return ev.draw("founders", next(batches), int(lc.founder_lives), float(lc.founder_T))
            founders, evals, info = sample_founders(cfg, ev, layout, sample, gen, collect=sampled)
            info.update(life_census(sampled, float(e.get("min_founder_score", 0.0))))
        nf = founders.shape[0]
        fill_ops = []
        pop = fill(founders, mu, layout, gen, e, ops=fill_ops)
        ids = torch.arange(mu)
        breeds = ids % nf
        slot = torch.arange(G)[None, :]
        origins = torch.where(layout.active(pop), breeds[:, None] * G + slot, torch.tensor(-1))  # innovation ids
        next_id, next_innov = mu, nf * G
        log({"event": "founders", **info})
        lin.write({"event": "founders", **info, "ids": list(range(nf)),
                   "copies": [{"id": int(i), "parent": int(i % nf), "ops": fill_ops[i - nf]} for i in range(nf, mu)]})

    heldout_list = list(lc.get("heldout") or [])
    clones_every = int(cc.get("every", 0) or 0)
    times = [float(x) for x in cc.get("times", [0.25, 0.5, 0.75])]
    conds = [str(x) for x in cc.get("conditions", clones.CONDITIONS)]
    curves, valid, heldout, chosen = [], None, None, None
    rc_lives = 0  # recheck lives so far: evals counts them as rc_lives / L genome evaluations
    T_drawn = bool(getattr(ev, "T_choices", ()))  # life.T_choices: the rows record each generation's life length

    def counted():
        return evals + rc_lives / int(lc.lives) if rc_lives else evals

    start = 0
    fitness = None
    if resume is not None:
        pop, ids, breeds, origins = (resume[k] for k in ("population", "ids", "breeds", "origins"))
        next_id, next_innov = resume["next_id"], resume["next_innov"]
        evals, rc_lives, info = resume["evals"], resume["rc_lives"], resume["founders"]
        curves, valid, heldout = resume["curves"], resume["valid"], resume["heldout"]
        fitness, start = resume["fitness"], resume["generation"]
        gen.set_state(resume["generator"])
        if tie_gen is not None:
            tie_gen.set_state(resume["tie_generator"])
    n_gen = int(e.generations)
    end = n_gen if stop_after is None else min(n_gen, start + stop_after)
    if stop_after is not None and stop_after < 1:
        raise ValueError("stop_after must be positive")
    every = int(cfg.logging.get("checkpoint_every", 25))
    if every < 1:
        raise ValueError("logging.checkpoint_every must be positive")

    def snapshot(generation):
        return {"generation": generation, "population": pop, "ids": ids, "breeds": breeds,
                "origins": origins, "next_id": next_id, "next_innov": next_innov,
                "generator": gen.get_state(), "tie_generator": None if tie_gen is None else tie_gen.get_state(),
                "evals": evals, "rc_lives": rc_lives, "founders": info, "curves": curves,
                "valid": valid, "heldout": heldout, "fitness": fitness}

    for g in range(start, end):
        t_start = time.perf_counter()
        draw = ev.draw("gen", g)
        ia = torch.randint(mu, (lam,), generator=gen)
        if e.breeding == "sex":
            ib = torch.randint(mu, (lam,), generator=gen)
            kids, masks = layout.crossover(pop[ia], pop[ib], gen, masks=True)
            kid_origins = torch.where(masks[:, :G], origins[ia], origins[ib])
        else:
            ib, masks = None, None
            kids, kid_origins = pop[ia].clone(), origins[ia].clone()
        ops = []
        kids = layout.mutate(kids, gen, int(e.n_mut), float(e.p_cell), ops=ops, slot_use=layout.active(pop).sum(0),
                             **mut_kw)
        for j, op in enumerate(ops):  # structural ops change the slot origins: a duplicate is a new innovation
            if "dup" in op:
                kid_origins[j, op["dup"][1]] = next_innov
                next_innov += 1
            if "del" in op:
                kid_origins[j, op["del"]] = -1
        kid_ids = torch.arange(next_id, next_id + lam)
        next_id += lam
        everyone = torch.cat([pop, kids])
        all_ids, all_breeds = torch.cat([ids, kid_ids]), torch.cat([breeds, breeds[ia]])
        all_origins = torch.cat([origins, kid_origins])
        t_ev = time.perf_counter()
        res = ev(everyone, draw)
        t_ev = time.perf_counter() - t_ev
        evals += everyone.shape[0]
        order = rank_desc(res.fitness, tie_gen)[:mu]
        chosen, rc, onestage = rows(res, order), None, order  # the parents' evaluation, in rank order
        if k_re:
            rc = recheck(ev, everyone, res, g, mu, k_re, l_re, key_re, tie_gen)
            order, chosen = rc["order"], rc["chosen"]
            rc_lives += len(rc["shortlist"]) * l_re
        pa_ids, pb_ids = ids[ia], (None if ib is None else ids[ib])
        pop, ids, breeds, origins = everyone[order], all_ids[order], all_breeds[order], all_origins[order]
        row = {"gen": g, "evals": counted(), **chosen.take(0, ev.catch), "mean_score": float(chosen.score.mean()),
               "mean_fitness": float(chosen.fitness.mean()), "median_n_cells": float(chosen.n_cells.median()),
               "best_id": int(ids[0]), "best_breed": int(breeds[0]), "breeds": int(breeds.unique().numel()),
               "pop_guard": float(res.guard.mean()), "pop_lone": float((res.n_peak <= 1).double().mean()),
               "pop_body": float(res.body.mean()), "pop_invalid": float(res.invalid.mean()),
               "pop_mismatch": float(res.mismatch.mean())}
        if row["pop_mismatch"] > 0:  # a kernel fault: the lives were scored as invalid, and the run says so
            log({"event": "ledger_mismatch", "generation": g,  # not "gen": curves.jsonl takes rows with "gen"
                 "lives": round(row["pop_mismatch"] * everyone.shape[0] * draw.n)})
        if rc is not None:
            rres = rc["res"]
            row.update(recheck_k=len(rc["shortlist"]), recheck_changed=rc["changed"],
                       recheck_F=float(rres.fitness[rc["pick"]].mean()),
                       recheck_F_base=float(res.fitness[order].mean()), recheck_invalid=float(rres.invalid.mean()),
                       recheck_bodies=int((res.n_cells[order] >= BODY_CELLS).sum()),
                       recheck_bodies_onestage=int((res.n_cells[onestage] >= BODY_CELLS).sum()))
            if rres.mismatch.sum() > 0:
                log({"event": "ledger_mismatch", "generation": g, "recheck": True,
                     "lives": round(float(rres.mismatch.sum()) * l_re)})
        final = g == n_gen - 1
        if g % int(e.heldout_every) == 0 or final:
            valid = float(ev(pop[:1], ev.draw("valid", g, lives=int(lc.valid_lives))).fitness[0])
            if heldout_list:
                hd = ev.draw("heldout", g, lives=int(lc.heldout_lives), overrides=heldout_list)
                heldout = float(ev(pop[:1], hd).fitness[0])
            row.update(valid=valid, heldout=heldout)
        if clones_every and (g % clones_every == 0 or final):
            sel = clone_targets(breeds, int(cc.get("top", 8)))
            seeds = ev.draw("clones", g, lives=int(cc.get("lives", 3))).seeds
            frows = clones.run_forks(ev.table(pop[sel]), ev.world(), seeds, times, conds, kind=ev.kind,
                                     threads=ev.threads, abi=ev.abi)
            for r in frows:
                r.update(gen=g, id=int(ids[sel[r["genome"]]]), breed=int(breeds[sel[r["genome"]]]),
                         rank=sel[r.pop("genome")])
            lin.clones(frows)
            row["clones"] = clone_summary(frows)
            row["msg_reliance_best"] = clones.reliance([r for r in frows if r["rank"] == 0],
                                                       clones.message_condition(conds))
            if clones.sense_condition(conds):
                row["sense_reliance_best"] = clones.reliance([r for r in frows if r["rank"] == 0], clones.SENSE)
        if T_drawn:  # GB11: the generation's life length (its recheck lives share it; judged lives keep life.T)
            row["T"] = draw.worlds[0].T
        row.update(t_gen=round(time.perf_counter() - t_start, 4), t_eval=round(t_ev, 4))
        if rc is not None:
            row["t_recheck"] = round(rc["t"], 4)
        curves.append(row)
        log(row)
        kept = [int(i) - mu for i in order.tolist() if int(i) >= mu]
        logged = range(lam) if lin.mode == "all" else kept
        lrow = {"gen": g, "seeds": [int(s) for s in draw.seeds], **({"T": draw.worlds[0].T} if T_drawn else {}),
                "children": [{"id": int(kid_ids[j]), "pa": int(pa_ids[j]),
                              "pb": None if pb_ids is None else int(pb_ids[j]),
                              "mask": None if masks is None else mask_bits(masks[j]), "ops": ops[j],
                              "fitness": float(res.fitness[mu + j]), "kept": j in kept} for j in logged],
                "survivors": [int(i) for i in ids.tolist()], "fitness": [float(x) for x in chosen.fitness],
                "breeds": {str(b): n for b, n in sorted(Counter(breeds.tolist()).items())},
                "registry": registry(origins), "n_active": float(layout.active(pop).sum(1).double().mean()),
                "distance": float(torch.pdist(pop.double()).mean()) if mu > 1 else 0.0}
        if rc is not None:  # children's fitness above is on the generation's lives; survivors' on all their lives
            short = rc["shortlist"]
            lrow["recheck"] = {"seeds": [int(s) for s in rc["draw"].seeds], "key": key_re,
                               "ids": [int(all_ids[i]) for i in short],
                               "F_base": [float(res.fitness[i]) for i in short],
                               "F_recheck": [float(x) for x in rc["res"].fitness], "changed": rc["changed"]}
        lin.write(lrow)
        fitness = chosen.fitness
        if checkpoint is not None and ((g + 1) % every == 0 or g + 1 == end):
            checkpoint(snapshot(g + 1))
    if checkpoint is not None and start == end:
        checkpoint(snapshot(end))
    lin.close()
    return {"best": pop[0], "population": pop, "ids": ids, "breeds": breeds, "origins": origins, "fitness": fitness,
            "complete": end == n_gen, "curves": curves, "evals": counted(), "valid": valid, "heldout": heldout,
            "rung": None, "founders": info,
            "lattice": None, "layout": layout, "task": None, "evaluator": ev}
