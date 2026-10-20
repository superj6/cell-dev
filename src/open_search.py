"""Open-world family search: allocation-aware lives, racing and behaviour grids (docs/SEARCH.md; OPEN_WORLDS.md 6).

Opt-in with ``evolve.allocation``; every existing configuration keeps ``src.search.evolve_family`` unchanged. All of
this is training bookkeeping outside the organism: no task name, allocation, score or grid reaches a life.

One generation:

1. Allocation (``src.allocate``): lives per task, fixed within each ``period``-generation block.
2. Shared lives keyed by (task, replicate) (``LifeEvaluator.draw_allocated``); parents (current plus Pareto archive,
   deduplicated) and children all live them. Objectives are per-task means, and the scalar fitness used by mean
   selection and reports is the mean of the per-task means (never weighted by the allocation).
3. Mating as in ``evolve_family``; with behaviour grids, ``parent_share`` of the children take parent A from a
   uniformly random filled cell (own RNG stream).
4. Racing: the top ``race_k`` by the selection mode, plus up to ``novel_k`` behaviourally novel candidates (best of
   each empty, unrepresented grid cell), live ``race_lives`` more lives on the same allocation (shared seeds of the
   purpose ``race``), pooled per task. Survivors and the Pareto archive come from the raced set.
5. Behaviour grids (``src.elites``): incumbents relive the generation's lives of their task; per cell the best
   candidate fills or challenges (paired, >= ``admit_z`` SE); new cells at or above the median are confirmed on
   ``confirm_lives`` fresh paired lives.
6. Every ``period`` generations a fixed-seed probe (top ``probe_top`` survivors/archive genomes per task on
   ``probe_lives`` lives) gives the learning-progress slope for the next block.

Actual lives are counted by kind (founders, gen, race, elite, confirm, probe); ``search_lives`` is their sum.
Checkpoints add the allocator state, grids, confirmed events and the elite RNG, so resume is exact.
"""
from __future__ import annotations

import copy
import math
import time
from dataclasses import replace
from pathlib import Path

import numpy as np
import torch
from omegaconf import OmegaConf

from src.allocate import Allocator, residual_variance
from src.elites import Elites, contest, novel
from src.evolve import Lineage, fill, mask_bits, pooled, rows, sample_founders, seed_genome, setup
from src.selection import epsilon_lexicase, unique_genome_indices

ELITE_SEED = 29_010_019  # offset of the elite-parent generator's seed from the run seed (its own stream)
VERSION = 2
LIFE_KINDS = ("founders", "gen", "race", "elite", "confirm", "probe")


def _plain(x) -> dict:
    if x is None:
        return {}
    return dict(OmegaConf.to_container(x, resolve=True)) if OmegaConf.is_config(x) else dict(x)


def _count(e, key) -> int:
    value = e.get(key, 0) or 0
    if isinstance(value, bool) or not isinstance(value, int) or value < 0:
        raise ValueError(f"evolve.{key} must be a nonnegative integer")
    return int(value)


def plan(cfg, ev, layout):
    """Validate the open-search settings before any native call: (allocator, elites or None, race_k, race_lives,
    novel_k)."""
    e = cfg.evolve
    names = ev.training_task_names
    alloc = Allocator(_plain(e.allocation), names)
    if _count(e, "recheck_k") or _count(e, "recheck_lives"):
        raise ValueError("evolve.allocation races instead of rechecking: set recheck_k/recheck_lives to 0 and use "
                         "race_k/race_lives")
    race_k, race_lives, novel_k = _count(e, "race_k"), _count(e, "race_lives"), _count(e, "novel_k")
    mu, size = int(e.mu), int(e.get("archive_size", 0))
    if bool(race_k) != bool(race_lives):
        raise ValueError("racing needs both race_k and race_lives (or neither)")
    if race_k and race_k < mu:
        raise ValueError(f"evolve.race_k = {race_k}: the raced set must hold at least mu = {mu} genomes")
    if size and (not race_k or race_k <= mu):
        raise ValueError("a breeding archive requires race_k > mu and positive race_lives")
    elites = Elites(_plain(e.elites), names, layout.size, layout.dims.genes_max) if e.get("elites") else None
    if novel_k and (elites is None or not race_k):
        raise ValueError("evolve.novel_k needs evolve.elites (behaviour cells) and racing")
    if elites is not None:
        ev.request_columns(elites.columns)
    return alloc, elites, race_k, race_lives, novel_k


def evolve_open(cfg, log=print, out=None, *, resume=None, checkpoint=None, stop_after=None):
    from src.life.evaluate import task_objectives
    from src.search import (
        MODES,
        SELECT_SEED,
        _json,
        archive_indices,
        capability_panel,
        concatenate,
        load_population,
        panel_representatives,
        population_payload,
        select,
    )

    torch.set_num_threads(int(cfg.threads))
    _, layout, _, ev = setup(cfg)
    e, lc = cfg.evolve, cfg.life
    mode = str(e.get("selection", "mean"))
    if mode not in MODES:
        raise ValueError(f"evolve.selection must be one of {MODES}")
    if e.breeding not in ("sex", "asex"):
        raise ValueError("evolve.breeding must be sex or asex")
    mu, lam, size = int(e.mu), int(e.lam), int(e.get("archive_size", 0))
    epsilon = float(e.get("epsilon_multiplier", 1.0))
    if mu < 1 or lam < 1 or size < 0 or not np.isfinite(epsilon) or epsilon < 0:
        raise ValueError("positive mu/lam, nonnegative archive_size and epsilon_multiplier required")
    if cfg.get("clones", {}).get("every", 0):
        raise ValueError("family search uses capability_panel; set clones.every=0")
    if e.get("seed_population") and e.get("seed_genome"):
        raise ValueError("choose seed_population or seed_genome, not both")
    if e.get("seed_archive") and (not size or not e.get("seed_population")):
        raise ValueError("seed_archive requires a positive archive_size and seed_population")
    if ev.T_choices and ev.T not in ev.T_choices:
        raise ValueError("life.T must be in T_choices")
    alloc, elites, race_k, race_lives, novel_k = plan(cfg, ev, layout)
    names = ev.training_task_names
    K = len(names)
    generations = int(e.generations)
    every = int(cfg.logging.get("checkpoint_every", 25))
    if generations < 0 or every < 1 or (stop_after is not None and stop_after < 1):
        raise ValueError("invalid generation/checkpoint/stop schedule")
    generator = torch.Generator().manual_seed(int(cfg.seed))
    selector = torch.Generator().manual_seed(int(cfg.seed) + SELECT_SEED)
    elite_gen = torch.Generator().manual_seed(int(cfg.seed) + ELITE_SEED)
    sel_env = bool(ev.envelope.get("enabled", False))  # selection physics for race/elite/confirm/probe lives
    probe_seed = int(cfg.seed) if alloc.probe_seed is None else alloc.probe_seed
    G = layout.dims.genes_max
    mut_kw = dict(dup_rate=float(e.get("dup_rate", 0)), del_rate=float(e.get("del_rate", 0)),
                  split=bool(e.get("dup_split", False)), scale_n_mut=bool(e.get("n_mut_scale", True)))
    out = None if out is None else Path(out)
    lin = Lineage(out, str(cfg.logging.get("lineage", "survivors")), append=resume is not None)
    panel = lc.get("capability_panel")
    if panel:
        if int(panel.get("every", 25)) < 1 or int(panel.get("top", 8)) < 1 or int(panel.get("lives", 16)) < 1:
            raise ValueError("capability panel schedule, top and lives must be positive")
        ev.draw_tasks("panel", 0, panel["tasks"], int(panel.get("lives", 16)), keyed=True)
    if resume is None:
        if e.get("seed_population"):
            pop, info = load_population(e.seed_population, layout, mu)
            evals = 0
        else:
            if e.get("seed_genome"):
                founders, evals, info = seed_genome(cfg, layout), 0, {"sampled": 0, "seeded": str(e.seed_genome)}
            else:
                index = iter(range(int(e.get("max_init_samples", 8192)) + 1))
                founders, evals, info = sample_founders(
                    cfg, ev, layout,
                    lambda _: ev.draw("founders", next(index), int(lc.founder_lives), float(lc.founder_T)), generator)
            pop = fill(founders, mu, layout, generator, e)
        ids = torch.arange(mu)
        breeds = ids.clone()
        origins = torch.where(layout.active(pop), ids[:, None] * G + torch.arange(G)[None, :], -1)
        archive, archive_ids = pop[:0].clone(), ids[:0].clone()
        archive_breeds, archive_origins = breeds[:0].clone(), origins[:0].clone()
        archive_fitness = torch.empty(0, dtype=torch.float64)
        if e.get("seed_archive"):
            archive, archive_info = load_population(e.seed_archive, layout, size, label="seed_archive")
            archive_ids = torch.arange(mu, mu + size)
            archive_breeds = archive_ids.clone()
            archive_origins = torch.where(layout.active(archive),
                                          archive_ids[:, None] * G + torch.arange(G)[None, :], -1)
            archive_fitness = None
            archive_info["ids"] = archive_ids.tolist()
            info["seed_archive"] = archive_info
        next_id, next_innov, start = mu + len(archive), (mu + len(archive)) * G, 0
        curves, fitness, panel_lives = [], None, 0
        lives = dict.fromkeys(LIFE_KINDS, 0)
        lives["founders"] = int(info.get("sampled", 0)) * int(lc.founder_lives)
        info.update(selection=mode, archive_size=size, allocation=alloc.mode)
        log({"event": "founders", **info})
        lin.write({"event": "founders", **info, "ids": ids.tolist(), "copies": []})
        last_objectives = torch.zeros((mu, K), dtype=torch.float64)
        archive_objectives = torch.zeros((len(archive), K), dtype=torch.float64)
    else:
        if resume.get("family_search_version") != VERSION:
            raise ValueError("checkpoint is not an open-world family-search checkpoint")
        pop, ids, breeds, origins = (resume[k] for k in ("population", "ids", "breeds", "origins"))
        archive, archive_ids, archive_breeds, archive_origins, archive_fitness = (
            resume[k] for k in ("archive", "archive_ids", "archive_breeds", "archive_origins", "archive_fitness"))
        next_id, next_innov, start = (resume[k] for k in ("next_id", "next_innov", "generation"))
        curves, fitness, evals, panel_lives, info, last_objectives = (
            resume[k] for k in ("curves", "fitness", "evals", "panel_lives", "founders", "objectives"))
        lives = dict(resume["lives"])
        generator.set_state(resume["generator"])
        selector.set_state(resume["selection_generator"])
        elite_gen.set_state(resume["elite_generator"])
        archive_objectives = resume["archive_objectives"]
        alloc.load(copy.deepcopy(resume["allocator"]))
        if elites is not None:
            elites.load(resume["elites"])
    end = generations if stop_after is None else min(generations, start + stop_after)

    def search_lives():
        return int(sum(lives.values()))

    def snapshot(generation):
        return {"family_search_version": VERSION, "generation": generation, "population": pop, "ids": ids,
                "breeds": breeds, "origins": origins, "fitness": fitness, "objectives": last_objectives,
                "archive": archive, "archive_ids": archive_ids, "archive_breeds": archive_breeds,
                "archive_origins": archive_origins, "archive_fitness": archive_fitness,
                "archive_objectives": archive_objectives,
                "next_id": next_id, "next_innov": next_innov, "generator": generator.get_state(),
                "selection_generator": selector.get_state(), "elite_generator": elite_gen.get_state(),
                "evals": evals, "lives": dict(lives), "panel_lives": panel_lives, "founders": info,
                "curves": curves, "allocator": copy.deepcopy(alloc.state),
                "elites": None if elites is None else elites.state(), "valid": None, "heldout": None}

    def report(generation):
        nonlocal panel_lives
        if out is not None:
            payload = population_payload(layout, pop, ids, breeds, origins, fitness)
            payload["generation"] = generation
            payload["archive"] = population_payload(layout, archive, archive_ids, archive_breeds,
                                                      archive_origins, archive_fitness)
            payload["allocation"] = {"tasks": list(names), "lives": alloc.state["allocation"]}
            if elites is not None:
                payload["elites"] = elites.payload(layout)
            _json(out / "populations" / f"g{generation:06d}.json", payload)
        if panel:
            candidates, candidate_ids = torch.cat([pop, archive]), torch.cat([ids, archive_ids])
            scores = torch.cat([last_objectives, archive_objectives])
            selected = panel_representatives(scores, min(len(candidates), int(panel.get("top", 8))))
            observation, used = capability_panel(ev, candidates[selected], candidate_ids[selected], generation,
                                                 panel, keyed=True)
            panel_lives += used
            lin.write(observation)
            log({"event": "capability_panel", "generation": generation, "genomes": len(selected), "lives": used})

    def evaluate(genomes, draw, what, kind):
        result = ev(genomes, draw)
        if result.invalid.any():
            raise RuntimeError(f"invalid {what} life at generation {g}")
        lives[kind] += len(genomes) * draw.n
        return result

    if resume is None:
        report(0)
        if checkpoint is not None:
            checkpoint(snapshot(0))
    try:
        for g in range(start, end):
            began = time.perf_counter()
            novelty = elites.novelty_counts(g, alloc.novelty_window) if elites is not None else [0] * K
            block = alloc.begin(g, novelty)
            L = alloc.lives
            T = ev.generation_T(g)
            draw = ev.draw_allocated("gen", g, L, T=T)
            labels = np.array(draw.tasks)
            task_lives = [np.flatnonzero(labels == name) for name in names]
            parent_rows = unique_genome_indices(torch.cat([pop, archive]))
            if len(parent_rows) + lam < mu:
                parent_rows = torch.arange(mu + len(archive))
            parents = torch.cat([pop, archive])[parent_rows]
            parent_ids = torch.cat([ids, archive_ids])[parent_rows]
            parent_breeds = torch.cat([breeds, archive_breeds])[parent_rows]
            parent_origins = torch.cat([origins, archive_origins])[parent_rows]
            parent_eval = evaluate(parents, draw, "parent", "gen")
            parent_scores = task_objectives(parent_eval, draw, names)

            def mates(scores=parent_scores, n=len(parents)):
                if mode == "epsilon_lexicase":
                    return epsilon_lexicase(scores, lam, generator=selector, replace=True,
                                            epsilon_multiplier=epsilon)
                return torch.randint(n, (lam,), generator=generator)

            ia = mates()
            ib = mates() if e.breeding == "sex" else None
            pa, pa_ids = parents[ia].clone(), parent_ids[ia].clone()
            pa_breeds, pa_origins = parent_breeds[ia].clone(), parent_origins[ia].clone()
            elite_tags = [None] * lam
            filled = elites.filled() if elites is not None else []
            n_elite = int(math.floor(elites.parent_share * lam + 0.5)) if filled else 0
            if n_elite:
                for j, p in enumerate(torch.randint(len(filled), (n_elite,), generator=elite_gen).tolist()):
                    gi, cell = filled[p]
                    grid = elites.grids[gi]
                    pa[j], pa_ids[j], pa_breeds[j] = grid.genomes[cell], grid.ids[cell], grid.breeds[cell]
                    pa_origins[j] = grid.origins[cell]
                    elite_tags[j] = [grid.task, cell]
            if ib is not None:
                kids, masks = layout.crossover(pa, parents[ib], generator, masks=True)
                kid_origins = torch.where(masks[:, :G], pa_origins, parent_origins[ib])
            else:
                kids, masks, kid_origins = pa.clone(), None, pa_origins.clone()
            ops = []
            kids = layout.mutate(kids, generator, int(e.n_mut), float(e.p_cell), ops=ops,
                                 slot_use=layout.active(parents).sum(0), **mut_kw)
            for j, op in enumerate(ops):
                if "dup" in op:
                    kid_origins[j, op["dup"][1]] = next_innov
                    next_innov += 1
                if "del" in op:
                    kid_origins[j, op["del"]] = -1
            kid_ids = torch.arange(next_id, next_id + lam)
            next_id += lam
            everyone = torch.cat([parents, kids])
            all_ids = torch.cat([parent_ids, kid_ids])
            all_breeds = torch.cat([parent_breeds, pa_breeds])
            all_origins = torch.cat([parent_origins, kid_origins])
            res = concatenate(parent_eval, evaluate(kids, draw, "candidate", "gen"))
            evals += len(everyone)
            values = task_objectives(res, draw, names)
            res = replace(res, fitness=values.mean(1))  # equal-weight objectives, not allocation-weighted
            eligible = unique_genome_indices(everyone)
            if len(eligible) < mu:
                eligible = torch.arange(len(everyone))
            scores_u = res.trial_scores.numpy()[eligible.numpy()]
            alloc.observe_noise(g, [residual_variance(scores_u[:, idx]) for idx in task_lives])

            described = None
            if elites is not None:  # every eligible candidate's cell per grid, on the generation's lives
                described = []
                columns_u = res.life_columns.numpy()[eligible.numpy()]
                for grid in elites.grids:
                    idx = task_lives[names.index(grid.task)]
                    desc = elites.describe(grid, columns_u[:, idx, :])
                    described.append((grid.cells(desc), scores_u[:, idx].mean(axis=1)))
            novel_rows, race_vec, redraw, extra = [], None, None, None
            if race_k:
                top = eligible[select(values[eligible], res.fitness[eligible], min(race_k, len(eligible)), mode,
                                      selector, epsilon)]
                if novel_k:
                    position = {int(r): i for i, r in enumerate(eligible.tolist())}
                    picked = novel([c for c, _ in described], [s for _, s in described],
                                   [grid.filled.numpy() for grid in elites.grids],
                                   [position[int(r)] for r in top.tolist()], novel_k)
                    novel_rows = [int(eligible[i]) for i in picked]
                short = torch.cat([top, torch.tensor(novel_rows, dtype=torch.long)])
                race_vec = alloc.race(race_lives)
                redraw = ev.draw_allocated("race", g, race_vec, T=T, envelope=sel_env)
                extra = evaluate(everyone[short], redraw, "race", "race")
                pool_eval = pooled(rows(res, short), extra)
                pool_values = task_objectives(pool_eval, draw + redraw, names)
                pool_eval = replace(pool_eval, fitness=pool_values.mean(1))
            else:
                short = eligible
                pool_eval, pool_values = rows(res, short), values[short]
            pick = select(pool_values, pool_eval.fitness, mu, mode, selector, epsilon)
            pick = pick[torch.argsort(pool_eval.fitness[pick], descending=True, stable=True)]
            apick = archive_indices(everyone[short], pool_values, pick, size, selector)
            current, archived = short[pick], short[apick]
            archive, archive_ids = everyone[archived], all_ids[archived]
            archive_breeds, archive_origins = all_breeds[archived], all_origins[archived]
            archive_fitness = pool_eval.fitness[apick]
            archive_objectives = pool_values[apick]
            pop, ids, breeds, origins = everyone[current], all_ids[current], all_breeds[current], all_origins[current]
            chosen = rows(pool_eval, pick)
            fitness, last_objectives = chosen.fitness, pool_values[pick]

            elite_log = None
            if elites is not None:
                elite_log = update_elites(ev, elites, g, T, sel_env, everyone, all_ids, all_breeds, all_origins, res,
                                          draw, task_lives, eligible, described, short if race_k else None, extra,
                                          redraw, evaluate)
            generation = g + 1
            probe = None
            if alloc.probe_due(generation):
                probe = run_probe(ev, alloc, names, torch.cat([pop, archive]),
                                  torch.cat([last_objectives, archive_objectives]), probe_seed, sel_env, evaluate)
                alloc.add_probe(generation, probe)
            archive_mates = sum(int(parent_rows[ia[j]]) >= mu for j in range(lam) if elite_tags[j] is None)
            if ib is not None:
                archive_mates += int((parent_rows[ib] >= mu).sum())
            row = {"gen": g, "evals": evals, "search_lives": search_lives(), "lives": dict(lives),
                   "selection": mode, "task_names": list(names), "allocation": L,
                   "task_mean_F": last_objectives.mean(0).tolist(),
                   "task_best_F": last_objectives.max(0).values.tolist(),
                   "archive_count": len(archive), "archive_parent_draws": archive_mates,
                   "elite_parent_draws": n_elite, "unique_candidates": len(unique_genome_indices(everyone)),
                   "panel_lives": panel_lives, "mean_fitness": float(fitness.mean()), "best_id": int(ids[0]),
                   "pop_invalid": float(res.invalid.mean()), "pop_mismatch": float(res.mismatch.mean()),
                   **chosen.take(0, ev.catch)}
            if ev.T_choices:
                row["T"] = T
            if race_k:
                row.update(raced=len(short), novel_raced=len(novel_rows), race_allocation=race_vec)
            if block is not None:
                row["allocator"] = block
            if probe is not None:
                row["probe"] = {"generation": generation, "scores": probe}
            if elite_log is not None:
                row.update(elites_filled=[int(grid.filled.sum()) for grid in elites.grids],
                           elite_tasks=[grid.task for grid in elites.grids],
                           elite_admissions=len(elite_log["admissions"]),
                           elite_events=sum(x["confirmed"] for x in elite_log["events"]))
            row["t_gen"] = round(time.perf_counter() - began, 4)
            curves.append(row)
            log(row)
            kept_ids = set(ids.tolist()) | set(archive_ids.tolist())
            logged = range(lam) if lin.mode == "all" else [j for j in range(lam) if int(kid_ids[j]) in kept_ids]
            lrow = {"gen": g, "allocation": L, "seeds": list(draw.seeds), "tasks": list(draw.tasks),
                    "parent_ids": parent_ids.tolist(), "parent_task_F": parent_scores.tolist(),
                    "children": [{"id": int(kid_ids[j]), "pa": int(pa_ids[j]),
                                  "pb": None if ib is None else int(parent_ids[ib[j]]),
                                  "mask": None if masks is None else mask_bits(masks[j]), "ops": ops[j],
                                  **({"pa_elite": elite_tags[j]} if elite_tags[j] is not None else {})}
                                 for j in logged],
                    "survivors": ids.tolist(), "fitness": fitness.tolist(), "task_F": last_objectives.tolist(),
                    "archive_ids": archive_ids.tolist(), "archive_task_F": archive_objectives.tolist()}
            if race_k:
                lrow["race"] = {"ids": all_ids[short].tolist(), "novel_ids": [int(all_ids[r]) for r in novel_rows],
                                "allocation": race_vec, "seeds": list(redraw.seeds), "tasks": list(redraw.tasks)}
            if elite_log is not None:
                lrow["elites"] = elite_log
            if probe is not None:
                lrow["probe"] = {"generation": generation, "scores": probe}
            lin.write(lrow)
            report_due = panel and (generation % int(panel.get("every", 25)) == 0
                                   or generation in list(panel.get("at", [])))
            if report_due or generation == generations:
                report(generation)
            if checkpoint is not None and (generation % every == 0 or generation == end):
                checkpoint(snapshot(generation))
        if checkpoint is not None and start == end:
            checkpoint(snapshot(end))
    finally:
        lin.close()
    return {"best": pop[0], "population": pop, "ids": ids, "breeds": breeds, "origins": origins,
            "fitness": fitness, "complete": end == generations, "curves": curves, "evals": evals, "valid": None,
            "heldout": None, "rung": None, "founders": info, "lattice": None, "layout": layout, "task": None,
            "evaluator": ev, "family_search": True, "archive_count": len(archive), "panel_lives": panel_lives,
            "search_lives": search_lives(), "lives": dict(lives)}


def run_probe(ev, alloc, names, genomes, objectives, seed, envelope, evaluate) -> list[float]:
    """Fixed-seed probe: per task, the top ``probe_top`` distinct survivors/archive genomes by their task objective,
    on ``probe_lives`` lives of that task whose seeds never change (purpose probe, index 0, the probe seed) at
    life.T. The task's score is the mean over those genomes and lives."""
    scores = []
    for t in range(len(names)):
        order = torch.argsort(objectives[:, t], descending=True, stable=True)
        unique = order[unique_genome_indices(genomes[order])][:alloc.probe_top]
        vec = [alloc.probe_lives if j == t else 0 for j in range(len(names))]
        draw = ev.draw_allocated("probe", 0, vec, T=ev.T, envelope=envelope, seed=seed)
        scores.append(float(evaluate(genomes[unique], draw, "probe", "probe").trial_scores.mean()))
    return scores


def update_elites(ev, elites, g, T, envelope, everyone, all_ids, all_breeds, all_origins, res, draw, task_lives,
                  eligible, described, raced, extra, redraw, evaluate) -> dict:
    """One generation of the behaviour grids (module docstring of ``src.elites``). ``res`` holds every candidate on
    the generation's lives ``draw``; ``raced``/``extra``/``redraw`` the race (or None). Returns the lineage record:
    admissions and new-ability checks."""
    names = ev.training_task_names
    first_row = {}
    for i in range(len(everyone)):
        first_row.setdefault(everyone[i].numpy().tobytes(), i)
    race_pos = {} if raced is None else {int(r): i for i, r in enumerate(raced.tolist())}
    race_labels = np.array(redraw.tasks) if redraw is not None else np.array([])
    race_scores = None if extra is None else extra.trial_scores.numpy()
    all_scores = res.trial_scores.numpy()
    shared_all = all_scores[eligible.numpy()]
    log = {"admissions": [], "events": []}
    for gi, grid in enumerate(elites.grids):
        ti = names.index(grid.task)
        idx = task_lives[ti]
        sub = draw.select(idx)
        # 1. incumbents relive this generation's lives of their task (reused when the genome is a candidate)
        before = torch.nonzero(grid.filled)[:, 0].tolist()
        shared_inc = {}
        missing = [c for c in before if grid.genomes[c].numpy().tobytes() not in first_row]
        if missing:
            again = evaluate(grid.genomes[missing], sub, "elite", "elite").trial_scores.numpy()
            shared_inc.update({c: again[k] for k, c in enumerate(missing)})
        for c in before:
            if c not in shared_inc:
                shared_inc[c] = all_scores[first_row[grid.genomes[c].numpy().tobytes()], idx]
            grid.observe(c, shared_inc[c], elites.cap)
        filled_before = grid.filled.numpy().copy()
        ranked = sorted(before, key=lambda c: (float(grid.value[c]), c))
        median = float(np.median([float(grid.value[c]) for c in before])) if before else None
        ref = ranked[(len(ranked) - 1) // 2] if ranked else None
        ref_genome = None if ref is None else (grid.genomes[ref].clone(), int(grid.ids[ref]))
        # 2. challengers: every distinct candidate, at its cell on the shared lives
        cells, _ = described[gi]
        incumbents = {grid.genomes[c].numpy().tobytes() for c in before}
        skip = [i for i, r in enumerate(eligible.tolist()) if everyone[r].numpy().tobytes() in incumbents]
        shared = shared_all[:, idx]
        won = contest(cells, shared, filled_before, shared_inc, elites.admit_z, skip)
        fresh = []
        for a in won:
            r = int(eligible[a["row"]])
            own = shared[a["row"]]
            if r in race_pos:  # every own-task life it lived this generation counts toward its value
                own = np.concatenate([own, race_scores[race_pos[r], race_labels == grid.task]])
            old = int(grid.ids[a["cell"]]) if a["replaced"] else None
            grid.place(a["cell"], everyone[r], all_ids[r], all_breeds[r], all_origins[r], own, g, elites.cap)
            log["admissions"].append({"task": grid.task, "cell": a["cell"], "id": int(all_ids[r]), "replaced": old,
                                      "d": a["d"], "se": a["se"], "value": float(grid.value[a["cell"]])})
            if not a["replaced"] and median is not None and float(grid.value[a["cell"]]) >= median:
                fresh.append(a["cell"])
        # 3. new abilities: confirmed on fresh paired lives against the median elite
        if fresh and elites.confirm_lives:
            vec = [elites.confirm_lives if j == ti else 0 for j in range(len(names))]
            cdraw = ev.draw_allocated("elite_confirm", g, vec, T=T, envelope=envelope)
            genomes = torch.stack([ref_genome[0]] + [grid.genomes[c] for c in fresh])
            scores = evaluate(genomes, cdraw, "elite confirmation", "confirm").trial_scores.numpy()
            if int(grid.ids[ref]) == ref_genome[1] and bool(grid.filled[ref]):
                grid.observe(ref, scores[0], elites.cap)
            for k, c in enumerate(fresh, start=1):
                d = float((scores[k] - scores[0]).mean())
                confirmed = d >= 0
                grid.observe(c, scores[k], elites.cap)
                if confirmed:
                    elites.events.append([int(g), int(ti), int(c), int(grid.ids[c])])
                log["events"].append({"task": grid.task, "cell": c, "id": int(grid.ids[c]), "reference": ref_genome[1],
                                      "median": median, "d": d, "confirmed": bool(confirmed)})
    return log
