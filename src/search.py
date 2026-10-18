"""Shared multiworld search. All selection and archive bookkeeping is outside organism lives.

The legacy scalar loop remains in evolve.py. This opt-in loop uses freshly co-evaluated parents
and archive members, task-vector selection at both stages, and checkpointed RNG/archive state.
"""
from __future__ import annotations

import hashlib
import json
import os
import time
from dataclasses import replace
from pathlib import Path

import numpy as np
import torch

from src.evolve import (
    Lineage,
    fill,
    mask_bits,
    pooled,
    rank_desc,
    recheck_draw,
    recheck_plan,
    rows,
    sample_founders,
    seed_genome,
    setup,
)
from src.selection import epsilon_lexicase, pareto_order, unique_genome_indices

SELECT_SEED = 19_171_017
MODES = ("mean", "pareto", "epsilon_lexicase")


def load_population(path, layout, n: int) -> tuple[torch.Tensor, dict]:
    """Import every row of a saved population, without selecting a champion or making mutants."""
    path = Path(path)
    data = path.read_bytes()
    obj = json.loads(data)
    if obj.get("dims") != layout.dims.__dict__:
        raise ValueError("seed_population dimensions differ from the configured layout")
    genomes = obj.get("genomes", [])
    if len(genomes) != n:
        raise ValueError(f"seed_population must contain exactly mu={n} genomes")
    pop = torch.stack([layout.from_dict(g) for g in genomes])
    if pop.shape != (n, layout.size) or not torch.isfinite(pop).all():
        raise ValueError("seed_population contains invalid genomes")
    return pop, {"sampled": 0, "population_file": str(path), "population_sha256": hashlib.sha256(data).hexdigest(),
                 "source_ids": obj.get("ids"), "imported": n}


def concatenate(a, b):
    return type(a)(*[torch.cat([getattr(a, f), getattr(b, f)]) for f in a.__dataclass_fields__])


def objectives(result, draw):
    from src.life.evaluate import task_objectives

    return task_objectives(result, draw) if draw.tasks else result.fitness[:, None]


def select(values, fitness, k, mode, generator, epsilon):
    if mode == "mean":
        return rank_desc(fitness, generator)[:k]
    if mode == "pareto":
        return pareto_order(values, generator=generator)[:k]
    return epsilon_lexicase(values, k, generator=generator, replace=False, epsilon_multiplier=epsilon)


def archive_indices(genomes, values, current, size, generator):
    """Distinct rechecked alternatives only; no current genotype occupies an archive slot."""
    first = unique_genome_indices(torch.cat([genomes[current], genomes]))
    eligible = first[first >= len(current)] - len(current)
    if not size or not len(eligible):
        return torch.empty(0, dtype=torch.long)
    order = pareto_order(values[eligible], generator=generator)
    return eligible[order[:size]]


def _json(path: Path, payload):
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_suffix(path.suffix + ".tmp")
    temporary.write_text(json.dumps(payload, allow_nan=False) + "\n")
    os.replace(temporary, path)


def population_payload(layout, genomes, ids, breeds, origins, fitness=None):
    return {"dims": layout.dims.__dict__, "ids": ids.tolist(), "breeds": breeds.tolist(),
            "origins": origins.tolist(), "fitness": None if fitness is None else fitness.tolist(),
            "genomes": [layout.to_dict(g) for g in genomes]}


def capability_panel(ev, genomes, ids, generation, panel):
    """Report-only fixed lives. Their seed does not depend on run or generation, and scores never select parents."""
    from src.life.evaluate import life_seed

    draw = ev.draw_tasks("panel", 0, panel["tasks"], int(panel.get("lives", 16)))
    seed = int(panel.get("seed", 61_017_000))
    draw = replace(draw, seeds=tuple(life_seed(seed, "panel", 0, i) for i in range(draw.n)))
    col = ev.columns(ev.run(genomes, draw), len(genomes), draw)
    names = tuple(dict.fromkeys(draw.tasks))
    derived = dict(col, income_rate=col["income"] / col["window"],
                   cost_rate=(col["income"] - col["net"]) / col["window"] + col["extinct_charge"])
    metrics = ("F", "captures", "low_light_captures", "misses", "b2_clicks", "n_end", "n_H_end",
               "income_rate", "cost_rate", "invalid", "mismatch")
    metrics += tuple(k for k in col if k.startswith(("correct_choices_", "wrong_choices_", "choice_opportunities_")))
    entries = []
    for i, identity in enumerate(ids.tolist()):
        tasks = {}
        for name in names:
            mask = np.array([x == name for x in draw.tasks])
            n = int(mask.sum())
            tasks[name] = {key: {"mean": float(derived[key][i, mask].mean()),
                                 "se": float(derived[key][i, mask].std(ddof=1) / np.sqrt(n)) if n > 1 else None}
                           for key in metrics if key in derived}
        entries.append({"id": identity, "tasks": tasks})
    if col["invalid"].any():
        raise RuntimeError("invalid life in capability panel")
    return {"event": "capability_panel", "generation": generation, "seed": seed,
            "lives_per_task": int(panel.get("lives", 16)), "genomes": entries}, len(genomes) * draw.n


def panel_representatives(scores, top):
    """Task champions plus balanced mean-ranked rows; no panel result is involved in their choice."""
    chosen = []
    for j in range(scores.shape[1]):
        i = int(torch.argmax(scores[:, j]))
        if i not in chosen:
            chosen.append(i)
    for i in torch.argsort(scores.mean(1), descending=True, stable=True).tolist():
        if i not in chosen:
            chosen.append(i)
    return torch.tensor(chosen[:top], dtype=torch.long)


def evolve_family(cfg, log=print, out=None, *, resume=None, checkpoint=None, stop_after=None):
    """Task-vector (mu+lambda) search with a bounded, freshly rechecked reproducing archive.

    Archive genomes join the current population before mating and before offspring selection.
    Both shortlist and survival use the requested selection mode. The archive uses Pareto
    crowding among unique rechecked leftovers, up to its capacity; lower fronts may fill gaps.
    Selection uses ordinary per-task production F, including physical and extinction charges.
    """
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
    k_re, l_re, key_re = recheck_plan(e, mu, mu + lam + size)
    if size and (not k_re or k_re <= mu):
        raise ValueError("a breeding archive requires recheck_k > mu and positive recheck_lives")
    if ev.T_choices and ev.T not in ev.T_choices:
        raise ValueError("life.T must be in T_choices")
    generations = int(e.generations)
    every = int(cfg.logging.get("checkpoint_every", 25))
    if generations < 0 or every < 1 or (stop_after is not None and stop_after < 1):
        raise ValueError("invalid generation/checkpoint/stop schedule")
    generator = torch.Generator().manual_seed(int(cfg.seed))
    selector = torch.Generator().manual_seed(int(cfg.seed) + SELECT_SEED)
    G = layout.dims.genes_max
    mut_kw = dict(dup_rate=float(e.get("dup_rate", 0)), del_rate=float(e.get("del_rate", 0)),
                  split=bool(e.get("dup_split", False)), scale_n_mut=bool(e.get("n_mut_scale", True)))
    out = None if out is None else Path(out)
    lin = Lineage(out, str(cfg.logging.get("lineage", "survivors")), append=resume is not None)
    panel = lc.get("capability_panel")
    if panel:
        if int(panel.get("every", 25)) < 1 or int(panel.get("top", 8)) < 1 or int(panel.get("lives", 16)) < 1:
            raise ValueError("capability panel schedule, top and lives must be positive")
        # Validate panel worlds before spending any training compute.
        ev.draw_tasks("panel", 0, panel["tasks"], int(panel.get("lives", 16)))
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
        next_id, next_innov, start = mu, mu * G, 0
        curves, fitness, rc_lives, panel_lives = [], None, 0, 0
        info.update(selection=mode, archive_size=size)
        log({"event": "founders", **info})
        lin.write({"event": "founders", **info, "ids": ids.tolist(), "copies": []})
        last_objectives = torch.zeros((mu, max(1, len(ev.training_task_names))), dtype=torch.float64)
        archive_objectives = last_objectives[:0].clone()
    else:
        if resume.get("family_search_version") != 1:
            raise ValueError("checkpoint is not a shared family-search checkpoint")
        pop, ids, breeds, origins = (resume[k] for k in ("population", "ids", "breeds", "origins"))
        archive, archive_ids, archive_breeds, archive_origins, archive_fitness = (
            resume[k] for k in ("archive", "archive_ids", "archive_breeds", "archive_origins", "archive_fitness"))
        next_id, next_innov, start = (resume[k] for k in ("next_id", "next_innov", "generation"))
        curves, fitness, evals, rc_lives, panel_lives, info, last_objectives = (
            resume[k] for k in ("curves", "fitness", "evals", "rc_lives", "panel_lives", "founders", "objectives"))
        generator.set_state(resume["generator"])
        selector.set_state(resume["selection_generator"])
        archive_objectives = resume["archive_objectives"]
    end = generations if stop_after is None else min(generations, start + stop_after)

    def search_lives():
        sampled = int(info.get("sampled", 0))
        return (evals - sampled) * int(lc.lives) + sampled * int(lc.founder_lives) + rc_lives

    def snapshot(generation):
        return {"family_search_version": 1, "generation": generation, "population": pop, "ids": ids,
                "breeds": breeds, "origins": origins, "fitness": fitness, "objectives": last_objectives,
                "archive": archive, "archive_ids": archive_ids, "archive_breeds": archive_breeds,
                "archive_origins": archive_origins, "archive_fitness": archive_fitness,
                "archive_objectives": archive_objectives,
                "next_id": next_id, "next_innov": next_innov, "generator": generator.get_state(),
                "selection_generator": selector.get_state(), "evals": evals, "rc_lives": rc_lives,
                "panel_lives": panel_lives, "founders": info, "curves": curves, "valid": None, "heldout": None}

    def report(generation):
        nonlocal panel_lives
        if out is not None:
            payload = population_payload(layout, pop, ids, breeds, origins, fitness)
            payload["generation"] = generation
            payload["archive"] = population_payload(layout, archive, archive_ids, archive_breeds,
                                                      archive_origins, archive_fitness)
            _json(out / "populations" / f"g{generation:06d}.json", payload)
        if panel:
            candidates, candidate_ids = torch.cat([pop, archive]), torch.cat([ids, archive_ids])
            scores = torch.cat([last_objectives, archive_objectives])
            selected = panel_representatives(scores, min(len(candidates), int(panel.get("top", 8))))
            observation, used = capability_panel(ev, candidates[selected], candidate_ids[selected], generation, panel)
            panel_lives += used
            lin.write(observation)
            log({"event": "capability_panel", "generation": generation, "genomes": len(selected), "lives": used})

    if resume is None:
        report(0)
        if checkpoint is not None:
            checkpoint(snapshot(0))
    try:
        for g in range(start, end):
            began = time.perf_counter()
            draw = ev.draw("gen", g)
            # Dedup before mating so repeated copies do not multiply a genotype's chance to breed.
            parent_rows = unique_genome_indices(torch.cat([pop, archive]))
            if len(parent_rows) + lam < mu:
                parent_rows = torch.arange(mu + len(archive))
            parents = torch.cat([pop, archive])[parent_rows]
            parent_ids = torch.cat([ids, archive_ids])[parent_rows]
            parent_breeds = torch.cat([breeds, archive_breeds])[parent_rows]
            parent_origins = torch.cat([origins, archive_origins])[parent_rows]
            parent_eval = ev(parents, draw)
            if parent_eval.invalid.any():
                raise RuntimeError(f"invalid parent life at generation {g}")
            parent_scores = objectives(parent_eval, draw)

            def mates(scores=parent_scores, n=len(parents)):
                if mode == "epsilon_lexicase":
                    return epsilon_lexicase(scores, lam, generator=selector, replace=True,
                                            epsilon_multiplier=epsilon)
                return torch.randint(n, (lam,), generator=generator)

            ia = mates()
            ib = mates() if e.breeding == "sex" else None
            if ib is not None:
                kids, masks = layout.crossover(parents[ia], parents[ib], generator, masks=True)
                kid_origins = torch.where(masks[:, :G], parent_origins[ia], parent_origins[ib])
            else:
                kids, masks, kid_origins = parents[ia].clone(), None, parent_origins[ia].clone()
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
            all_breeds = torch.cat([parent_breeds, parent_breeds[ia]])
            all_origins = torch.cat([parent_origins, kid_origins])
            res = concatenate(parent_eval, ev(kids, draw))
            evals += len(everyone)
            if res.invalid.any():
                raise RuntimeError(f"invalid candidate life at generation {g}")
            values = objectives(res, draw)
            eligible = unique_genome_indices(everyone)
            # Degenerate tests/zero-mutation runs may have fewer unique genomes than mu.
            if len(eligible) < mu:
                eligible = torch.arange(len(everyone))
            short = eligible[select(values[eligible], res.fitness[eligible],
                                    min(k_re or mu, len(eligible)), mode, selector, epsilon)]
            selected_eval = rows(res, short)
            selected_values = values[short]
            selection_fitness = selected_eval.fitness
            recheck_seeds = []
            if k_re:
                redraw = recheck_draw(ev, g, draw.n, l_re)
                extra = ev(everyone[short], redraw)
                if extra.invalid.any():
                    raise RuntimeError(f"invalid recheck life at generation {g}")
                rc_lives += len(short) * redraw.n
                selected_eval = pooled(selected_eval, extra)
                combined = replace(draw, seeds=draw.seeds + redraw.seeds, worlds=draw.worlds + redraw.worlds,
                                   tasks=draw.tasks + redraw.tasks)
                selected_values = objectives(selected_eval, combined) if key_re == "all" else objectives(extra, redraw)
                selection_fitness = selected_eval.fitness if key_re == "all" else extra.fitness
                recheck_seeds = list(redraw.seeds)
            pick = select(selected_values, selection_fitness, mu, mode, selector, epsilon)
            # Reporting order only: membership was chosen above using the requested task policy.
            pick = pick[torch.argsort(selected_eval.fitness[pick], descending=True, stable=True)]
            apick = archive_indices(everyone[short], selected_values, pick, size, selector)
            current, archived = short[pick], short[apick]
            archive, archive_ids = everyone[archived], all_ids[archived]
            archive_breeds, archive_origins = all_breeds[archived], all_origins[archived]
            archive_fitness = selected_eval.fitness[apick]
            archive_objectives = selected_values[apick]
            pop, ids, breeds, origins = everyone[current], all_ids[current], all_breeds[current], all_origins[current]
            chosen = rows(selected_eval, pick)
            fitness, last_objectives = chosen.fitness, selected_values[pick]
            archive_mates = int((parent_rows[ia] >= mu).sum())
            if ib is not None:
                archive_mates += int((parent_rows[ib] >= mu).sum())
            row = {"gen": g, "evals": evals + rc_lives / int(lc.lives), "search_lives": search_lives(),
                   "selection": mode, "task_names": list(ev.training_task_names) or [str(lc.world)],
                   "task_mean_F": last_objectives.mean(0).tolist(),
                   "task_best_F": last_objectives.max(0).values.tolist(),
                   "archive_count": len(archive), "archive_parent_draws": archive_mates,
                   "unique_candidates": len(unique_genome_indices(everyone)), "panel_lives": panel_lives,
                   "mean_fitness": float(fitness.mean()), "best_id": int(ids[0]),
                   "pop_invalid": float(res.invalid.mean()), "pop_mismatch": float(res.mismatch.mean()),
                   **chosen.take(0, ev.catch), "t_gen": round(time.perf_counter() - began, 4)}
            curves.append(row)
            log(row)
            kept_ids = set(ids.tolist()) | set(archive_ids.tolist())
            logged = range(lam) if lin.mode == "all" else [j for j in range(lam) if int(kid_ids[j]) in kept_ids]
            lin.write({"gen": g, "seeds": list(draw.seeds), "tasks": list(draw.tasks),
                       "parent_ids": parent_ids.tolist(), "parent_task_F": parent_scores.tolist(),
                       "children": [{"id": int(kid_ids[j]), "pa": int(parent_ids[ia[j]]),
                                     "pb": None if ib is None else int(parent_ids[ib[j]]),
                                     "mask": None if masks is None else mask_bits(masks[j]), "ops": ops[j]}
                                    for j in logged],
                       "survivors": ids.tolist(), "fitness": fitness.tolist(), "task_F": last_objectives.tolist(),
                       "archive_ids": archive_ids.tolist(), "archive_task_F": selected_values[apick].tolist(),
                       "recheck": {"ids": all_ids[short].tolist(), "seeds": recheck_seeds, "key": key_re}})
            generation = g + 1
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
            "fitness": fitness, "complete": end == generations, "curves": curves,
            "evals": evals + rc_lives / int(lc.lives), "valid": None, "heldout": None,
            "rung": None, "founders": info, "lattice": None, "layout": layout, "task": None, "evaluator": ev,
            "family_search": True, "archive_count": len(archive), "panel_lives": panel_lives,
            "search_lives": search_lives()}
