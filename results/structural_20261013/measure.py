"""Fixed neutrality validation or six-genotype confirmation for G; no work without an explicit mode."""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import sys
import time
from dataclasses import asdict
from pathlib import Path

os.environ.setdefault("ATEN_CPU_CAPABILITY", "avx2")
ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))
STUDY = ROOT / "outputs/autonomous_structural_20261013"


def frozen(path, value):
    if path.exists() and json.loads(path.read_text()) != value:
        raise ValueError("frozen measurement input differs: " + str(path))
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_suffix(".tmp")
    tmp.write_text(json.dumps(value, indent=2, allow_nan=False) + "\n")
    tmp.replace(path)


def identical(left, right):
    return left.shape == right.shape and left.dtype == right.dtype and left.tobytes() == right.tobytes()


def neutral_equal(base, copy, src, dst):
    """Compare actual arrays, allowing only the additional gene's own fate-state column."""
    import numpy as np

    if not identical(base.ledger, copy.ledger) or not identical(base.hashes, copy.hashes):
        raise ValueError("silent duplication changed ledger or event hashes")
    for name in ("raster_n", "fate_n"):
        if not identical(getattr(base, name), getattr(copy, name)):
            raise ValueError("silent duplication changed recorded event counts")
    for i in range(len(base.ledger)):
        for original, changed in zip(base.spikes(i), copy.spikes(i)):
            if not identical(original, changed):
                raise ValueError("silent duplication changed spike times or UIDs")
        integers, floats = base.fates(i)
        duplicate_integers, duplicate_floats = copy.fates(i)
        if not identical(integers, duplicate_integers):
            raise ValueError("silent duplication changed fate events")
        keep = np.arange(floats.shape[1]) != 2 + dst
        if not identical(floats[:, keep], duplicate_floats[:, keep]):
            raise ValueError("silent duplication changed original fate-state columns")
        if not identical(duplicate_floats[:, 2 + dst], duplicate_floats[:, 2 + src]):
            raise ValueError("silent duplicate does not track its source gene")


def validate_neutral_logs(value, world, plan):
    import numpy as np

    from src.life import spec

    forbidden = sum(
        spec.STATUS[key]
        for key in (
            "extinct",
            "guard_cells",
            "guard_events",
            "raster_overflow",
            "fate_overflow",
            "ledger_mismatch",
            "capacity",
        )
    )
    if np.any(value["status"].astype(np.int64) & forbidden) or np.any(value["t_end"] != world.T):
        raise ValueError("neutrality check requires full lives without guards, invalidity or log overflow")
    if np.any(value.raster_n > plan["raster_cap"]) or np.any(value.fate_n > plan["fate_cap"]):
        raise ValueError("neutrality log capacity exceeded")


def neutrality():
    import numpy as np
    import torch
    from run_budgeted import check_protocol, check_ready, save, sha

    from scripts.taskvar_confirm import atomic_npz
    from src.genome import Layout
    from src.life import build, spec

    protocol, ready = check_protocol(), check_ready()
    plan = protocol["neutrality_validation"]
    start = time.process_time()
    torch.set_num_threads(1)
    layout, founder = Layout.load(ROOT / protocol["founder_file"])
    genomes = [founder] + [
        layout.duplicate(founder, src, plan["destination_slot"], split=False) for src in plan["active_source_slots"]
    ]
    world = spec.world("catch_speck_l4", T=plan["T"], d0=0.5, d_min=0.25, sigma=0.4, lam_s=4)
    out = STUDY / "neutrality"
    if out.exists() and any(out.iterdir()):
        raise ValueError("neutrality validation already has artifacts; do not repeat lives")
    out.mkdir(parents=True, exist_ok=True)
    frozen(
        out / "manifest.json",
        {
            "protocol_sha256": sha(STUDY / "protocol.json"),
            "ready": ready,
            "world": asdict(world),
            "seeds": plan["seeds"],
            "source_slots": plan["active_source_slots"],
            "destination_slot": plan["destination_slot"],
            "kernel": "full",
            "planned_genome_lives": 18,
            "validation_only": True,
            "raster_cap": plan["raster_cap"],
            "fate_cap": plan["fate_cap"],
        },
    )
    atomic_npz(out / "genotypes.npz", genomes=np.stack([genome.numpy() for genome in genomes]))
    rows = []
    base = None
    for index, genome in enumerate(genomes):
        if time.process_time() - start >= 26:
            raise ValueError("neutrality CPU reserve reached before next row")
        value = build.run(
            world,
            plan["seeds"],
            genomes=layout.pack(genome[None], "hexprism"),
            abi=spec.V3,
            threads=1,
            fast=False,
            raster_cap=plan["raster_cap"],
            fate_cap=plan["fate_cap"],
        )
        arrays = {"ledger": value.ledger, "hashes": value.hashes, "raster_n": value.raster_n, "fate_n": value.fate_n}
        for i in range(2):
            arrays[f"spike_t_{i}"], arrays[f"spike_uid_{i}"] = value.spikes(i)
            arrays[f"fate_i_{i}"], arrays[f"fate_f_{i}"] = value.fates(i)
        atomic_npz(out / f"row_{index:02d}.npz", **arrays)
        rows.append(
            {
                "row": index,
                "genome_sha256": hashlib.sha256(genome.numpy().tobytes()).hexdigest(),
                "raw_sha256": sha(out / f"row_{index:02d}.npz"),
                "spikes": value.raster_n.tolist(),
                "fates": value.fate_n.tolist(),
            }
        )
        try:
            validate_neutral_logs(value, world, plan)
            if base is None:
                base = value
            else:
                neutral_equal(base, value, plan["active_source_slots"][index - 1], plan["destination_slot"])
        except ValueError as error:
            save(
                out / "report.json",
                {
                    "status": "failed",
                    "genome_lives": 2 * len(rows),
                    "rows": rows,
                    "cpu_seconds": time.process_time() - start,
                    "validation_only": True,
                    "error": str(error),
                },
            )
            raise
        save(
            out / "report.json",
            {
                "status": "incomplete",
                "genome_lives": 2 * len(rows),
                "rows": rows,
                "cpu_seconds": time.process_time() - start,
                "validation_only": True,
            },
        )
    save(
        out / "report.json",
        {
            "status": "complete",
            "genome_lives": 18,
            "rows": rows,
            "cpu_seconds": time.process_time() - start,
            "validation_only": True,
            "comparison": ("All ledger/hash/spike/fate outputs exact except the added gene state, "
                           "which tracks its source."),
        },
    )


def mixture(rows, candidate, reference):
    import numpy as np

    if set(rows) != {"768", "1024", "1536"}:
        raise ValueError("require all three fixed durations")
    arrays = np.stack(
        [np.asarray(rows[str(t)][candidate]["F"]) - np.asarray(rows[str(t)][reference]["F"]) for t in (768, 1024, 1536)]
    )
    if arrays.ndim != 2 or arrays.shape[1] < 2 or not np.isfinite(arrays).all():
        raise ValueError("require finite paired life arrays")
    return arrays.mean(axis=0)


def endpoint(folder, cfg, identity, generation=16):
    import numpy as np

    from src import checkpoint
    from src.genome import Layout

    saved = checkpoint.load(folder / "checkpoint.pt")
    checkpoint.validate(saved, cfg, identity)
    if saved["state"]["generation"] != generation:
        raise ValueError("cannot measure an incomplete search endpoint")
    curves = saved["state"]["curves"]
    if [row["gen"] for row in curves] != list(range(generation)):
        raise ValueError("incomplete search history")
    health = {key: max(float(row[key]) for row in curves) for key in ("pop_invalid", "pop_mismatch", "recheck_invalid")}
    if any(health.values()):
        raise ValueError("invalid/mismatched search lives block confirmation")
    layout, genome = Layout.load(folder / "best_genome.json")
    if genome.numpy().tobytes() != saved["state"]["population"][0].numpy().tobytes():
        raise ValueError("best file differs from fixed final population rank0")
    active = layout.active(genome).numpy()
    origins = saved["state"]["origins"][0].numpy()
    duplicate = np.flatnonzero(active & (origins >= layout.dims.genes_max))
    return genome, {
        "health": health,
        "checkpoint_sha256": __import__("run_budgeted").sha(folder / "checkpoint.pt"),
        "active_genes": int(active.sum()),
        "duplicate_derived_slots": duplicate.tolist(),
        "duplicate_origin_ids": origins[duplicate].tolist(),
        "interpretation": "Active counts and duplicate ancestry do not establish functional use.",
    }


def confirm():
    import numpy as np
    from omegaconf import OmegaConf
    from run_budgeted import check_protocol, check_ready, save, sha

    from scripts.taskvar_confirm import COLS, atomic_npz, compare_rows, score_row
    from scripts.taskvar_gates import paired
    from src import checkpoint
    from src.genome import Layout
    from src.life import spec
    from src.life.evaluate import LifeEvaluator

    protocol, ready = check_protocol(), check_ready()
    identity = checkpoint.numerical_identity()
    if identity != protocol["expected_numerical_identity"]:
        raise ValueError("confirmation numerical identity differs")
    labels = protocol["confirmation"]["labels"]
    layout, pilot = Layout.load(ROOT / protocol["pilot_file"])
    _, founder = Layout.load(ROOT / protocol["founder_file"])
    genomes = [pilot, founder]
    audits = {}
    for group, study in (("D", ROOT / protocol["D_study"]), ("G", STUDY)):
        source_protocol = json.loads((study / "protocol.json").read_text())
        if group == "D" and json.loads((study / "budget.json").read_text())["status"] != "complete":
            raise ValueError("D must complete regardless of its fitness outcome")
        audits[group] = {}
        for seed in protocol["runs"]:
            cfg = OmegaConf.load(ROOT / source_protocol["configs"][str(seed)]["path"])
            genome, audit = endpoint(study / f"runs/s{seed}", cfg, identity)
            genomes.append(genome)
            audits[group][str(seed)] = audit
    genomes = np.stack([genome.numpy() for genome in genomes])
    seeds = protocol["confirmation"]["seeds"]
    settings = {
        str(t): spec.world("catch_speck_l4", T=t, d0=0.5, d_min=0.25, sigma=0.4, lam_s=4) for t in (768, 1024, 1536)
    }
    manifest = {
        "labels": labels,
        "seeds": seeds,
        "seed_block": 93,
        "worlds": {k: asdict(v) for k, v in settings.items()},
        "genotype_sha256": {label: hashlib.sha256(g.tobytes()).hexdigest() for label, g in zip(labels, genomes)},
        "endpoint_audits": audits,
        "numerical_identity": identity,
        "protocol_sha256": sha(STUDY / "protocol.json"),
        "ready": ready,
        "selection": "All four endpoints are final population rank0 at16generations, frozen before confirmation.",
    }
    out = STUDY / "confirmation"
    if not (out / "manifest.json").exists() and out.exists() and any(out.rglob("*.npz")):
        raise ValueError("cached rows have no frozen manifest")
    frozen(out / "manifest.json", manifest)
    atomic_npz(out / "genotypes.npz", genomes=genomes, labels=np.asarray(labels))
    index_path = out / "row_index.json"
    row_index = json.loads(index_path.read_text()) if index_path.exists() else {}
    for relative, expected in row_index.items():
        if sha(out / relative) != expected:
            raise ValueError("cached row differs from frozen hash")
    cfg = OmegaConf.load(ROOT / protocol["configs"][str(protocol["runs"][0])]["path"])
    evaluator = LifeEvaluator(cfg, layout)
    all_rows = {}
    pairs = protocol["confirmation"]["primary_pairs"] + protocol["confirmation"]["secondary_pairs"]
    report = {
        "status": "incomplete",
        "report_only": True,
        "worlds": {},
        "primary": {},
        "secondary": {},
        "endpoint_audits": audits,
    }
    for name, world in settings.items():
        rows = {}
        for i in range(6):
            rows[i] = score_row(out / name, i, genomes, world, seeds, evaluator, 2)
            relative = f"{name}/row_{i:04d}.npz"
            row_index[relative] = sha(out / relative)
            save(index_path, row_index)
        atomic_npz(
            out / name / "scores.npz",
            seeds=np.asarray(seeds, dtype=np.uint64),
            genome_indices=np.arange(6),
            **{key: np.stack([rows[i][key] for i in range(6)]) for key in COLS},
        )
        all_rows[name] = rows
        report["worlds"][name] = {
            labels[a] + "__vs__" + labels[b]: compare_rows(rows[a], rows[b], world) for a, b in pairs
        }
        save(out / "report.json", report)
    contrasts = {"seeds": np.asarray(seeds, dtype=np.uint64)}
    for group, key in (("primary", "primary_pairs"), ("secondary", "secondary_pairs")):
        for a, b in protocol["confirmation"][key]:
            name = labels[a] + "__vs__" + labels[b]
            values = mixture(all_rows, a, b)
            estimate = paired(values, np.zeros_like(values))
            report[group][name] = {
                **estimate,
                "above_3se": estimate["mean"] > 3 * estimate["se"],
                "at_least_0p5": estimate["mean"] >= 0.5,
            }
            contrasts[name] = values
    atomic_npz(out / "contrasts.npz", **contrasts)
    report.update(
        status="complete",
        genome_lives=4608,
        independent_search_replicates=2,
        limitations=[
            "Two paired run seeds cannot establish general operator superiority.",
            "The intervention combines duplication, deletion and the existing "
            "active-gene-scaled point mutation policy.",
            "Same run seeds preserve initial populations and worlds, "
            "but structural RNG draws alter later search paths.",
            "Life-level SE describes these fixed endpoints, not between-search uncertainty.",
            "Duplicate count or ancestry alone does not prove functional gene use.",
        ],
    )
    save(out / "report.json", report)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--mode", choices=["neutrality", "confirm"])
    args = parser.parse_args()
    if args.mode is None:
        print(
            json.dumps({"status": "dry_run", "neutrality_lives": 18, "confirmation_lives": 4608, "simulated_lives": 0})
        )
    elif args.mode == "neutrality":
        neutrality()
    else:
        confirm()


if __name__ == "__main__":
    main()
