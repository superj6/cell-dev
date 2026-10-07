"""Evolution: (mu+lambda) selection with two-parent crossover ("sex") or mutation only ("asex").

The population descends from a few founders (the fittest random genomes; sampling continues in batches until one of
them actually scores). Descendants of one founder share homologous gene slots; crossing different founders is
cross-breeding between lines. Every generation draws fresh trials; parents are re-evaluated on them with
the children. Every ``heldout_every`` generations the best genome is scored on fresh in-distribution trials ("valid")
and on held-out trials from wider ranges ("heldout": generalization). On the ladder the run moves up a rung once the
valid score reaches ``advance_at``; with ``immigrants`` > 0 that share of the population is then replaced by new
founders sampled on the new rung, so crossover can hybridize the old lineage with breeds that have a foothold there.
"""
from __future__ import annotations

from dataclasses import dataclass

import torch

from src.cells import decode_cells, run_cells
from src.develop import Tissue, develop
from src.genome import Dims, Layout
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


def setup(cfg):
    lattice = build_lattice(cfg.lattice.kind, cfg.lattice.radius, cfg.lattice.contact)
    layout = Layout(Dims(**cfg.genome.dims))
    task = build_task(cfg.task.name, cfg.task.length, cfg.task.start, cfg.task.keep_earlier, cfg.task.get("rungs"))
    return lattice, layout, task, Evaluator(cfg, lattice, layout)


def sample_founders(cfg, ev: Evaluator, layout: Layout, sample, gen: torch.Generator) -> tuple[torch.Tensor, int, dict]:
    """Random genomes in batches until one of them actually scores (a dead single cell has nothing to climb from), up
    to ``max_init_samples``. Returns the fittest ``founders`` with scorers ranked first, the evaluations used, and a
    summary. ``sample(gen)`` draws the trials to score them on."""
    e = cfg.evolve
    min_score = float(e.get("min_founder_score", 0.0))
    pool, fits, scores, evals = [], [], [], 0
    while True:
        cands = layout.random(int(e.init_samples), gen, float(cfg.genome.init_scale))
        res = ev(cands, sample(gen))
        pool.append(cands)
        fits.append(res.fitness)
        scores.append(res.score)
        evals += cands.shape[0]
        if float(torch.cat(scores).max()) >= min_score or evals >= int(e.get("max_init_samples", evals)):
            break
    pool, fits, scores = torch.cat(pool), torch.cat(fits), torch.cat(scores)
    order = fits.argsort(descending=True)
    scorer = scores[order] >= min_score
    ranked = torch.cat([order[scorer], order[~scorer]])  # scorers first (by fitness), then everything else
    founders = pool[ranked[: min(int(e.founders), len(ranked))]]
    info = {"sampled": evals, "best_fitness": float(fits.max()), "best_score": float(scores.max()),
            "scoring_founders": int(min(int(scorer.sum()), founders.shape[0]))}
    return founders, evals, info


def fill(founders: torch.Tensor, n: int, layout: Layout, gen: torch.Generator, e) -> torch.Tensor:
    """n individuals: each founder once, then mutated copies of the founders in turn."""
    pop = founders[torch.arange(n) % founders.shape[0]].clone()
    pop[founders.shape[0]:] = layout.mutate(pop[founders.shape[0]:], gen, int(e.n_mut), float(e.p_cell))
    return pop


def evolve(cfg, log=print) -> dict:
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
