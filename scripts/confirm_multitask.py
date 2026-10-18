"""Select one generalist per saved stage, then confirm its unchanged genome on every task.

Configure confirmation.{stages,seed,development_lives,lives,reserved_tasks}. Selection
uses training-task production F only, ranked against the unique genotype union of
all stages. All choices are frozen before any training/reserved confirmation lives.
Completed raw blocks resume exactly; interrupted calls are never silently repeated.
"""
# ruff: noqa: E402 -- establish direct-script imports and CPU dispatch first.
from __future__ import annotations

import argparse
import json
import os
import sys
from dataclasses import replace
from pathlib import Path

os.environ.setdefault("ATEN_CPU_CAPABILITY", "avx2")
ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

import numpy as np
import torch
from omegaconf import OmegaConf

from scripts import confirm_flash_ladder as cache
from src import checkpoint
from src.common import load_config
from src.evolve import setup
from src.life import build, spec
from src.life.evaluate import life_seed
from src.life.readouts import ratio_of_means

RULE = "training_F_pooled_unique_average_tie_percentile_min_then_mean_then_F_then_ID"
CHUNK = 32


def settings(cfg):
    config = OmegaConf.to_container(cfg.confirmation, resolve=True)
    stages = config["stages"]
    if (len(stages) < 2 or any(type(g) is not int or g < 0 for g in stages)
            or stages != sorted(set(stages)) or stages[0] != 0 or stages[-1] != int(cfg.evolve.generations)):
        raise ValueError("confirmation stages must increase from zero to the configured final generation")
    if any(type(config[k]) is not int or config[k] < 2 for k in ("development_lives", "lives")):
        raise ValueError("development and confirmation need at least two lives per task")
    if type(config["seed"]) is not int or config["seed"] < 0:
        raise ValueError("confirmation seed must be a nonnegative integer")
    training = OmegaConf.to_container(cfg.life.training_tasks, resolve=True)
    reserved = config["reserved_tasks"]
    names = [task["name"] for task in training + reserved]
    if not training or len(names) != len(set(names)):
        raise ValueError("nonempty training tasks and globally unique training/reserved task names required")
    return config, training, reserved


def cohort(payloads, layout, mu, archive_size):
    """One exact-byte genotype row across stages; retain every stage/ID/source membership."""
    genomes, rows, by_stage, lookup, identities = [], [], {}, {}, {}
    for generation, payload in payloads.items():
        if payload["generation"] != generation:
            raise ValueError("snapshot generation differs")
        candidates = []
        for source, group in (("current", payload), ("archive", payload["archive"])):
            n = len(group["ids"])
            if (group["dims"] != layout.dims.__dict__ or n != len(group["genomes"])
                    or (source == "current" and n != mu) or (source == "archive" and n > archive_size)):
                raise ValueError("snapshot dimensions or population/archive capacity differs")
            for identity, obj in zip(group["ids"], group["genomes"]):
                if type(identity) is not int or identity < 0:
                    raise ValueError("native IDs must be nonnegative integers")
                genome = layout.from_dict(obj)
                if not torch.isfinite(genome).all():
                    raise ValueError("nonfinite genome")
                key = genome.numpy().tobytes()
                if identity in identities and identities[identity] != key:
                    raise ValueError("one native ID changed genotype across snapshots")
                identities[identity] = key
                if key not in lookup:
                    lookup[key] = len(genomes)
                    genomes.append(genome)
                    rows.append({"genome_sha256": cache.digest(key), "memberships": []})
                i = lookup[key]
                member = {"generation": generation, "id": identity, "source": source, "cohort_index": i}
                rows[i]["memberships"].append(member)
                candidates.append(member)
        if len({r["id"] for r in candidates}) != len(candidates):
            raise ValueError("snapshot repeats a native ID")
        unique = {}
        for row in sorted(candidates, key=lambda r: r["id"]):
            unique.setdefault(row["cohort_index"], row)
        by_stage[generation] = list(unique.values())
    return torch.stack(genomes), rows, by_stage


def percentile_ranks(scores):
    """Average-tie ranks on [0,1], shared across all stages; a constant task ranks everyone at0.5."""
    scores = np.asarray(scores, dtype=np.float64)
    if scores.ndim != 2 or min(scores.shape) < 1 or not np.isfinite(scores).all():
        raise ValueError("finite nonempty genotype-by-task scores required")
    n, tasks = scores.shape
    ranks = np.full(scores.shape, .5)
    if n > 1:
        for j in range(tasks):
            order = np.argsort(scores[:, j], kind="stable")
            values = scores[order, j]
            starts = np.r_[0, np.flatnonzero(values[1:] != values[:-1]) + 1]
            stops = np.r_[starts[1:], n]
            for start, stop in zip(starts, stops):
                ranks[order[start:stop], j] = (start + stop - 1) / (2 * (n - 1))
    return ranks


def choose(scores, ranks, candidates):
    return min(candidates, key=lambda r: (-float(ranks[r["cohort_index"]].min()),
                -float(ranks[r["cohort_index"]].mean()), -float(scores[r["cohort_index"]].mean()), r["id"]))


def panel(ev, tasks, config, index, count):
    draw = ev.draw_tasks("confirm", index, tasks, count)
    return replace(draw, seeds=tuple(life_seed(config["seed"], "confirm", index, i) for i in range(draw.n)))


def describe(values):
    values = np.asarray(values, dtype=np.float64)
    return {"mean": float(values.mean()), "se": float(values.std(ddof=1) / np.sqrt(values.size)), "n": values.size}


def metrics(col, draw):
    """Per-life behavior, provenance and additive production-F contributions; retain guards/extinction."""
    names = ("captures", "low_light_captures", "misses", "clicks", "b2_clicks", "F", "F_kernel", "income",
             "cost", "guard_charge", "extinct_charge", "guard", "extinct", "n_end", "live_time",
             "n_S_end", "n_M_end", "n_H_end", "spikes", "contact_events", "claims", "rec_gain")
    names += spec.TASK_LEDGER + spec.PATCH_LEDGER + spec.CONTACT_LEDGER
    out = {key: np.asarray(col[key][0], dtype=np.float64) for key in names if key in col}
    window = col["window"][0]
    out.update(mean_cells=col["live_time"][0] / window, income_F=col["income"][0] / window,
               physical_cost_F=-col["cost"][0] / window, guard_F=-col["guard_charge"][0] / window,
               extinction_F=-col["extinct_charge"][0])
    for name, price, field in (("maintenance", "c_live", "live_time"), ("spikes", "c_spike", "spikes"),
            ("twitch", "c_tw", "kappa_sum"), ("messages", "c_msg", "contact_events"),
            ("division", "c_div", "claims"), ("secretion", "c_sec", "sec_int"),
            ("misses", "c_miss", "misses"), ("receptors", "c_rec", "rec_gain")):
        out[f"cost_{name}_F"] = -np.array([getattr(w, price) for w in draw.worlds]) * col[field][0] / window
    wrong = col.get("wrong_choices_narrow", np.zeros_like(col["F"])) + col.get(
        "wrong_choices_broad", np.zeros_like(col["F"]))
    charged = np.where([w.task_mode for w in draw.worlds], wrong[0], col["b2_clicks"][0])
    out["cost_wrong_or_decoy_F"] = -np.array([max(0., -w.b2_value) for w in draw.worlds]) * charged / window
    for name in ("stock_open", "source", "supply", "spill", "harvest", "empty", "stock_end",
                 "initial_harvest", "refill_harvest"):
        keys = [f"patch_{name}_{i}" for i in range(spec.PATCH_SLOTS)]
        if all(key in out for key in keys):
            out[f"patch_total_{name}"] = sum(out[key] for key in keys)
    for name in spec.CONTACT_METRICS:
        keys = [f"patch_contact_{name}_{i}" for i in range(spec.PATCH_SLOTS)]
        if all(key in out for key in keys):
            out[f"contact_total_{name}"] = sum(out[key] for key in keys)
    if "contact_total_harvest" in out:
        out["passive_refill_harvest"] = out["patch_total_refill_harvest"] - out["contact_total_harvest"]
        reward = np.array([w.R_cap for w in draw.worlds]) / window
        for name, key in (("initial", "patch_total_initial_harvest"), ("passive", "passive_refill_harvest"),
                          ("contact", "contact_total_harvest")):
            out[f"patch_{name}_food_F"] = reward * out[key]
    return out


def summarize(observations, draw, stages, training_names):
    masks = {n: np.array(draw.tasks) == n for n in dict.fromkeys(draw.tasks)}
    results = {str(g): {n: {k: describe(v[m]) for k, v in observations[g].items()}
                       for n, m in masks.items()} for g in stages}
    pairs = list(dict.fromkeys([(g, stages[0]) for g in stages[1:]] + list(zip(stages[1:], stages[:-1]))))
    paired = {f"g{a}_minus_g{b}": {n: {k: describe((v - observations[b][k])[m])
                                     for k, v in observations[a].items()} for n, m in masks.items()} for a, b in pairs}
    matching = {}
    for g in stages:
        matching[str(g)] = {}
        for n, mask in masks.items():
            classes = {}
            for label in ("narrow", "broad"):
                key = f"choice_opportunities_{label}"
                if key not in observations[g]:
                    continue
                def at(metric, c=label, data=observations[g], selected=mask):
                    return data[f"{metric}_{c}"][selected]
                opportunities = at("choice_opportunities") + at("choice_carry_in")
                completed = at("correct_choices") + at("wrong_choices")
                classes[label] = {"correct_per_opportunity": ratio_of_means(at("correct_choices"), opportunities),
                                  "completion_coverage": ratio_of_means(completed, opportunities),
                                  "completed_accuracy": ratio_of_means(at("correct_choices"), completed)}
            matching[str(g)][n] = classes
    return {"results": results, "paired": paired, "matching_ratios": matching,
            "training_tasks": training_names, "reserved_tasks": [n for n in masks if n not in training_names],
            "interpretation": ("One unchanged genome per stage across every task; "
                               "portfolios and costs are separate evidence.")}


def fixed_json(path, payload):
    if path.exists() and json.loads(path.read_bytes()) != payload:
        raise ValueError(f"frozen saved evidence differs: {path}")
    if not path.exists():
        cache.write_json(path, payload)


def verify_kernel(identity, fast):
    path = build.library_path(fast=fast)
    if not path.exists():
        path = build.build(fast=fast)
    if cache.digest(path.read_bytes()) != identity["kernels"][str(bool(fast))]:
        raise ValueError("confirmation native library differs from training")


def confirm(cfg, layout, ev, binding):
    config, training, reserved = settings(cfg)
    stages = config["stages"]
    out = Path(cfg.logging.output_dir) / "confirmation"
    out.mkdir(parents=True, exist_ok=True)
    snapshots = {g: out.parent / "populations" / f"g{g:06d}.json" for g in stages}
    binding = dict(binding, snapshots={str(g): cache.digest(p.read_bytes()) for g, p in snapshots.items()},
                   script_sha256=cache.digest(Path(__file__).read_bytes()),
                   cache_helpers_sha256=cache.digest(Path(cache.__file__).read_bytes()), confirmation=config)
    genomes, candidates, stage_rows = cohort({g: json.loads(p.read_bytes()) for g, p in snapshots.items()}, layout,
                                            int(cfg.evolve.mu), int(cfg.evolve.archive_size))
    dev = panel(ev, training, config, 100, config["development_lives"])
    judged = panel(ev, training + reserved, config, 200, config["lives"])
    names = list(dict.fromkeys(dev.tasks))
    scores, errors, raw = [], [], []
    for start in range(0, len(genomes), CHUNK):
        dest = out / f"development_{start:06d}.npz"
        batch = genomes[start:start + CHUNK]
        col = cache.cached_lives(dest, ev, batch, dev, binding)
        scores.extend(np.stack([col["F"][:, np.array(dev.tasks) == n].mean(1) for n in names], axis=1))
        errors.extend(np.stack([col["F"][:, np.array(dev.tasks) == n].std(1, ddof=1)
                                / np.sqrt(config["development_lives"]) for n in names], axis=1))
        raw.append({"path": dest.name, "sha256": cache.digest(dest.read_bytes()), "lives": len(batch) * dev.n})
    scores = np.array(scores)
    ranks = percentile_ranks(scores)
    development = {"binding": binding, "tasks": names, "rule": RULE, "candidates": candidates,
                   "F_means": scores.tolist(), "F_se": np.array(errors).tolist(), "percentile_ranks": ranks.tolist(),
                   "stage_candidates": {str(g): rows for g, rows in stage_rows.items()}, "raw": list(raw)}
    fixed_json(out / "development.json", development)
    frozen = {"binding": binding, "rule": RULE,
              "development_sha256": cache.digest((out / "development.json").read_bytes()),
              "choices": {}}
    selected = {}
    for g in stages:
        row = choose(scores, ranks, stage_rows[g])
        i = row["cohort_index"]
        selected[g] = genomes[i:i + 1]
        frozen["choices"][str(g)] = dict(row, genome_sha256=candidates[i]["genome_sha256"],
            genome=layout.to_dict(genomes[i]), F_means=scores[i].tolist(), ranks=ranks[i].tolist(),
            worst_rank=float(ranks[i].min()), mean_rank=float(ranks[i].mean()), mean_F=float(scores[i].mean()))
    fixed_json(out / "selection.json", frozen)  # Every stage fixed before any confirmation, including reserved tasks.
    observations = {}
    for g, genes in selected.items():
        dest = out / f"confirmation_g{g:06d}.npz"
        col = cache.cached_lives(dest, ev, genes, judged,
                                dict(binding, selection_sha256=cache.digest((out / "selection.json").read_bytes())))
        observations[g] = metrics(col, judged)
        raw.append({"path": dest.name, "sha256": cache.digest(dest.read_bytes()), "lives": judged.n})
    report = dict(summarize(observations, judged, stages, names), status="complete", binding=binding, raw=raw,
                  selection_sha256=cache.digest((out / "selection.json").read_bytes()),
                  development_genotypes=len(genomes), lives=sum(row["lives"] for row in raw))
    cache.write_json(out / "summary.json", report)
    return report


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--config", required=True)
    parser.add_argument("--train", action="store_true")
    resume = parser.add_mutually_exclusive_group()
    resume.add_argument("--resume", action="store_true")
    resume.add_argument("--resume-if-present", action="store_true")
    args = parser.parse_args()
    cfg = load_config(args.config)
    config, training, reserved = settings(cfg)
    _, layout, _, ev = setup(cfg)
    panel(ev, training + reserved, config, 200, config["lives"])  # Validate held-out world definitions before training.
    final_generation = config["stages"][-1]
    path = Path(cfg.logging.output_dir) / "checkpoint.pt"
    saved = checkpoint.load(path) if path.exists() else None
    if (args.resume or args.resume_if_present) and not args.train:
        parser.error("training resume flags require --train")
    if args.train and (saved is None or saved["state"]["generation"] != final_generation):
        from src.run import main as train

        train(cfg, resume=args.resume or (args.resume_if_present and saved is not None))
        saved = checkpoint.load(path)
    if saved is None or saved["state"]["generation"] != final_generation:
        raise ValueError("confirmation requires the complete configured checkpoint")
    if saved["config"] != checkpoint.config_identity(cfg):
        raise ValueError("confirmation configuration differs from training")
    identity = saved["identity"]
    for name, expected in identity["sources"].items():
        if cache.digest((ROOT / name).read_bytes()) != expected:
            raise ValueError(f"training source changed: {name}")
    if (identity["torch"] != str(torch.__version__) or identity["numpy"] != np.__version__
            or identity["torch_cpu_capability"] != torch.backends.cpu.get_cpu_capability()
            or identity["torch_build"] != cache.digest(torch.__config__.show().encode())
            or identity["libm"] != checkpoint.libm_identity()):
        raise ValueError("training numerical implementation changed")
    torch.set_num_threads(int(cfg.threads))
    final = json.loads((path.parent / "populations" / f"g{final_generation:06d}.json").read_bytes())
    cache.verify_final_snapshot(final, layout, saved["state"])
    verify_kernel(identity, ev.fast)
    report = confirm(cfg, layout, ev, {"config": checkpoint.config_identity(cfg),
                                     "checkpoint_sha256": cache.digest(path.read_bytes()), "identity": identity})
    print(json.dumps({"status": report["status"], "lives": report["lives"],
                      "development_genotypes": report["development_genotypes"]}))


if __name__ == "__main__":
    main()
