"""Fresh development selection and paired confirmation for the four-founder flash study.

All six choices are frozen before confirmation. g0 is the selected initial-population
baseline, not necessarily the original founding genome. Results measure performance,
not a memory mechanism. Run as a queue tail with --train [--resume], or confirm an
already complete checkpoint directly. Queue jobs can explicitly opt into --resume-if-present.
Interrupted confirmation calls without saved raw data stop.
"""
# ruff: noqa: E402 -- pin CPU dispatch and enable direct script invocation before project imports.
from __future__ import annotations

import argparse
import hashlib
import json
import os
import sys
from dataclasses import asdict
from pathlib import Path

os.environ.setdefault("ATEN_CPU_CAPABILITY", "avx2")
ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

import numpy as np
import torch

from src import checkpoint
from src.common import load_config
from src.evolve import setup
from src.life import build
from src.selection import unique_genome_indices

STAGES = (0, 60, 120)
ROLES = ("balanced", "dark_specialist")
STUDY_SEED = 61_017_901
DEVELOPMENT, CONFIRMATION = 32, 512


def digest(data):
    return hashlib.sha256(data).hexdigest()


def encoded(obj):
    return json.dumps(obj, sort_keys=True, allow_nan=False, separators=(",", ":")).encode()


def write_json(path, obj):
    temporary = path.with_suffix(".tmp")
    temporary.write_bytes(encoded(obj) + b"\n")
    os.replace(temporary, path)


def population(payload, layout):
    """Current rows then archive rows, exact-byte deduplication; preserve source IDs."""
    genomes, rows = [], []
    for source, group in (("current", payload), ("archive", payload["archive"])):
        if group["dims"] != layout.dims.__dict__ or len(group["ids"]) != len(group["genomes"]):
            raise ValueError("snapshot dimensions or row identities differ")
        if (source == "current" and len(group["ids"]) != 32) or len(group["ids"]) > 32:
            raise ValueError("expected 32 current rows and at most 32 archive rows")
        for identity, obj in zip(group["ids"], group["genomes"]):
            genome = layout.from_dict(obj)
            genomes.append(genome)
            rows.append({"id": int(identity), "source": source, "genome_sha256": digest(genome.numpy().tobytes())})
    if len({r["id"] for r in rows}) != len(rows):
        raise ValueError("snapshot repeats a native ID")
    genomes = torch.stack(genomes)
    # Keep the lowest ID representative of an identical genotype, independent of archive membership.
    ordered = torch.tensor(sorted(range(len(rows)), key=lambda i: rows[i]["id"]))
    keep = sorted(ordered[unique_genome_indices(genomes[ordered])].tolist())
    return genomes[keep], [rows[i] for i in keep]


def panel(ev, tasks, index, lives):
    # The study seed enters draw_tasks itself, so per-life worlds (LifeEvaluator._life_world) see the final seeds.
    return ev.draw_tasks("confirm", index, tasks, lives, seed=STUDY_SEED)


def verify_final_snapshot(payload, layout, state):
    for group, prefix in ((payload, ""), (payload["archive"], "archive_")):
        expected = state["population" if not prefix else "archive"]
        actual = torch.stack([layout.from_dict(g) for g in group["genomes"]]) if group["genomes"] else expected[:0]
        if (group["ids"] != state[prefix + "ids"].tolist() or actual.shape != expected.shape
                or actual.numpy().tobytes() != expected.numpy().tobytes()):
            raise ValueError("final snapshot differs from completed checkpoint")


def choose(col, draw, rows):
    names = tuple(dict.fromkeys(draw.tasks))
    brightness = {name: draw.worlds[draw.tasks.index(name)].visibility_low for name in names}
    if len(names) != 4 or sorted(brightness.values()) != [0., .1, .25, .5]:
        raise ValueError("expected the fixed four flash rungs")
    hard = np.array([brightness[name] in (.1, 0.) for name in draw.tasks])
    fitness, dark = col["F"].mean(1), col["low_light_captures"][:, hard].mean(1)
    ids = np.array([row["id"] for row in rows])
    return {"balanced": int(np.lexsort((ids, -fitness))[0]),
            "dark_specialist": int(np.lexsort((ids, -fitness, -dark))[0])}


def cached_lives(path, ev, genomes, draw, binding):
    """Raw outputs precede diagnostics. A completed matching block never runs twice."""
    names = tuple(dict.fromkeys(draw.tasks))
    meta = encoded({"binding": binding, "genomes": digest(genomes.numpy().tobytes()), "shape": list(genomes.shape),
                    "seeds": list(draw.seeds), "tasks": list(draw.tasks),
                    "worlds": {n: asdict(draw.worlds[draw.tasks.index(n)]) for n in names}}).decode()
    pending = path.with_suffix(".pending.json")
    if path.exists():
        with np.load(path, allow_pickle=False) as saved:
            if str(saved["metadata"]) != meta:
                raise ValueError(f"cached input metadata differs: {path}")
            result = build.Lives(saved["ledger"].copy(), saved["hashes"].copy(), abi=ev.abi)
    else:
        if pending.exists():
            raise RuntimeError(f"interrupted call needs explicit reconciliation, not automatic retry: {pending}")
        write_json(pending, {"metadata_sha256": digest(meta.encode()), "expected_lives": len(genomes) * draw.n})
        result = ev.run(genomes, draw)
        temporary = path.with_suffix(".tmp")
        with temporary.open("wb") as fh:
            np.savez_compressed(fh, ledger=result.ledger, hashes=result.hashes, metadata=np.array(meta))
        os.replace(temporary, path)
    pending.unlink(missing_ok=True)
    if (result.ledger.shape != (len(genomes) * draw.n, ev.abi.LEDGER_SIZE)
            or result.hashes.shape != (len(genomes) * draw.n, ev.abi.HASH_SIZE)
            or not np.isfinite(result.ledger).all()):
        raise ValueError(f"invalid raw arrays retained: {path}")
    col = ev.columns(result, len(genomes), draw)
    if col["invalid"].any() or not np.isfinite(col["F"]).all():
        raise ValueError(f"invalid lives retained: {path}")
    return col


def describe(values):
    values = np.asarray(values, dtype=np.float64)
    return {"mean": float(values.mean()), "se": float(values.std(ddof=1) / np.sqrt(values.size)), "n": values.size}


def metrics(col):
    out = {key: np.asarray(col[key][0], dtype=np.float64)
           for key in ("captures", "low_light_captures", "misses", "F", "income", "cost",
                       "n_end", "extinct_charge", "guard", "extinct")}
    out["mean_cells"] = col["live_time"][0] / col["window"][0]
    return out


def summarize(observations, draw):
    names = tuple(dict.fromkeys(draw.tasks))
    masks = {name: np.array(draw.tasks) == name for name in names}
    results, paired = {}, {}
    for role in ROLES:
        results[role] = {str(g): {n: {k: describe(v[m]) for k, v in observations[g, role].items()}
                                 for n, m in masks.items()} for g in STAGES}
        paired[role] = {f"g{a}_minus_g{b}": {
            n: {k: describe((v - observations[b, role][k])[m]) for k, v in observations[a, role].items()}
            for n, m in masks.items()} for a, b in ((60, 0), (120, 0), (120, 60))}
    hard = [n for n in names if draw.worlds[draw.tasks.index(n)].visibility_low in (.1, 0.)]
    gains = [paired["dark_specialist"]["g120_minus_g0"][n]["low_light_captures"] for n in hard]
    return {"results": results, "paired": paired,
            "primary_founder_pass": len(gains) == 2 and all(g["mean"] > 3 * g["se"] for g in gains),
            "primary_study_rule": ("At least 2 of 4 founders pass both hard-rung dark-specialist contrasts; "
                                   "performance only."),
            "baseline": "g0 selected initial population (archive empty); not necessarily the original ancestor",
            "cost_units": "income/cost are native whole-life totals; F is production rate including extinction charge"}


def confirm(cfg, layout, ev, binding):
    out = Path(cfg.logging.output_dir) / "confirmation"
    out.mkdir(parents=True, exist_ok=True)
    snapshots = {g: Path(cfg.logging.output_dir) / "populations" / f"g{g:06d}.json" for g in STAGES}
    binding = dict(binding, snapshots={str(g): digest(p.read_bytes()) for g, p in snapshots.items()},
                   script_sha256=digest(Path(__file__).read_bytes()))
    dev = panel(ev, cfg.life.training_tasks, 100, DEVELOPMENT)
    judged = panel(ev, cfg.life.training_tasks, 200, CONFIRMATION)
    frozen, selected, raw = {"binding": binding, "choices": {}}, {}, []
    for g, path in snapshots.items():
        payload = json.loads(path.read_bytes())
        if payload["generation"] != g or (g == 0 and payload["archive"]["ids"]):
            raise ValueError("stage or initial archive differs")
        genomes, rows = population(payload, layout)
        dest = out / f"development_g{g:03d}.npz"
        col = cached_lives(dest, ev, genomes, dev, binding)
        raw.append({"path": dest.name, "sha256": digest(dest.read_bytes()), "lives": len(genomes) * dev.n})
        frozen["choices"][str(g)] = {}
        for role, i in choose(col, dev, rows).items():
            selected[g, role] = genomes[i:i + 1]
            frozen["choices"][str(g)][role] = dict(rows[i], genome=layout.to_dict(genomes[i]),
                                                 development_mean_F=float(col["F"][i].mean()))
    frozen["development_raw"] = list(raw)
    choice_path = out / "selection.json"
    if choice_path.exists() and json.loads(choice_path.read_bytes()) != frozen:
        raise ValueError("frozen choices or development evidence changed")
    if not choice_path.exists():
        write_json(choice_path, frozen)  # Every stage and both roles committed before the first confirmation call.
    observations = {}
    for (g, role), genome in selected.items():
        dest = out / f"confirmation_g{g:03d}_{role}.npz"
        col = cached_lives(dest, ev, genome, judged, dict(binding, selection_sha256=digest(choice_path.read_bytes())))
        observations[g, role] = metrics(col)
        raw.append({"path": dest.name, "sha256": digest(dest.read_bytes()), "lives": judged.n})
    summary = dict(summarize(observations, judged), status="complete", binding=binding, raw=raw,
                   selection_sha256=digest(choice_path.read_bytes()), lives=sum(r["lives"] for r in raw),
                   study_seed=STUDY_SEED, development_per_rung=DEVELOPMENT, confirmation_per_rung=CONFIRMATION)
    write_json(out / "summary.json", summary)
    return summary


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--config", required=True)
    parser.add_argument("--train", action="store_true")
    continuation = parser.add_mutually_exclusive_group()
    continuation.add_argument("--resume", action="store_true", help="resume training from an existing checkpoint")
    continuation.add_argument("--resume-if-present", action="store_true",
                              help="queue opt-in: resume if a checkpoint exists")
    args = parser.parse_args()
    cfg = load_config(args.config)
    path = Path(cfg.logging.output_dir) / "checkpoint.pt"
    saved = checkpoint.load(path) if path.exists() else None
    if (args.resume or args.resume_if_present) and not args.train:
        parser.error("training resume flags apply only to --train")
    if args.train and (saved is None or saved["state"]["generation"] != 120):
        from src.run import main as train

        train(cfg, resume=args.resume or (args.resume_if_present and saved is not None))
        saved = checkpoint.load(path)
    if saved is None or saved["state"]["generation"] != 120 or cfg.evolve.generations != 120:
        raise ValueError("confirmation requires the complete 120-generation checkpoint")
    if saved["config"] != checkpoint.config_identity(cfg):
        raise ValueError("confirmation configuration differs from training")
    identity = saved["identity"]
    for name, expected in identity["sources"].items():
        if digest((ROOT / name).read_bytes()) != expected:
            raise ValueError(f"training source changed: {name}")
    if identity["torch"] != str(torch.__version__) or identity["numpy"] != np.__version__:
        raise ValueError("training numerical dependencies changed")
    if (identity["torch_cpu_capability"] != torch.backends.cpu.get_cpu_capability()
            or identity["torch_build"] != digest(torch.__config__.show().encode())):
        raise ValueError("training CPU implementation changed")
    if identity["libm"] != checkpoint.libm_identity():
        raise ValueError("training libm changed")
    torch.set_num_threads(int(cfg.threads))
    _, layout, _, ev = setup(cfg)
    final = json.loads((path.parent / "populations" / "g000120.json").read_bytes())
    verify_final_snapshot(final, layout, saved["state"])
    summary = confirm(cfg, layout, ev, {"config": checkpoint.config_identity(cfg),
                                      "checkpoint_sha256": digest(path.read_bytes()), "identity": identity})
    print(json.dumps({"status": summary["status"], "lives": summary["lives"],
                      "primary_founder_pass": summary["primary_founder_pass"]}))


if __name__ == "__main__":
    main()
