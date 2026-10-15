"""Study-local ABI4 adaptation of taskvar_confirm.score_row and second_step.RowStore.

Importing this module does not build a kernel or run a life. Only score_row calls
the production engine. Mutation, physical rules and production fitness are unchanged.
"""
from __future__ import annotations

import hashlib
import json
import time
from pathlib import Path

import numpy as np

from scripts.taskvar_confirm import atomic_json, atomic_npz, compare_rows, sha
from scripts.taskvar_gates import paired, validate_lives
from src.life import build, spec
from src.life.evaluate import LifeDraw

ABI = spec.V4
COLS = ABI.LEDGER + ("F_kernel", "extinct_charge", "window")
THREADS = 2


def raw_sha(value):
    return hashlib.sha256(np.asarray(value).tobytes()).hexdigest()


def columns_from_ledger(ledger, world, seeds, evaluator):
    """Reproduce all production columns, retaining natural death and paid guards."""
    ledger = np.asarray(ledger)
    if ledger.dtype != np.float64 or ledger.shape != (len(seeds), ABI.LEDGER_SIZE):
        raise ValueError("raw ledger must be float64[lives,58]")
    if evaluator.abi.version != 4 or not evaluator.extinct_charge:
        raise ValueError("explicit ABI4 and original extinction charging required")
    result = build.Lives(ledger, np.zeros((len(seeds), ABI.HASH_SIZE), dtype=np.uint64), abi=ABI)
    validate_lives(result, world, allow_guards=True)
    cost = ABI.column_cost(ledger, world)
    if np.any(np.abs(result["cost"] - cost) > 1e-9 * np.maximum(1, np.abs(cost))):
        raise ValueError("raw accumulated cost exceeds the kernel mismatch tolerance")
    for name, expected in (("guard_charge", ABI.guard_charge(ledger, world)),
                           ("net", result["income"] - cost - ABI.guard_charge(ledger, world)),
                           ("F", ABI.fitness(ledger, world))):
        if not np.allclose(result[name], expected, rtol=0, atol=1e-9):
            raise ValueError("raw ledger accountant mismatch: " + name)
    captures, low = result["captures"], result["low_light_captures"]
    if (np.any(captures < 0) or np.any(captures != np.floor(captures))
            or np.any(low < 0) or np.any(low > captures) or np.any(low != np.floor(low))):
        raise ValueError("invalid low-light or total capture counts")
    if not np.allclose(result["income"], world.R_cap * captures, rtol=0, atol=1e-9):
        raise ValueError("capture income mismatch")
    draw = LifeDraw(tuple(seeds), tuple(world for _ in seeds))
    columns = evaluator.columns(result, 1, draw)
    return {key: columns[key][0] for key in COLS}


def score_row(out: Path, index: int, genomes, world, seeds, evaluator, *, identity):
    """One atomic raw+production-scored row; no silent reuse across candidates/stages."""
    out.mkdir(parents=True, exist_ok=True)
    path = out / f"row_{index:04d}.npz"
    binding = json.dumps({**identity, "genome_index": index,
                          "genome_sha256": raw_sha(genomes[index]), "seeds": list(seeds)},
                         sort_keys=True, separators=(",", ":"))
    if path.exists():
        raise ValueError("first-attempt worker refuses an existing row")
    wall_start, cpu_start = time.perf_counter(), time.process_time()
    result = build.run(world, seeds,
                       genomes=ABI.pack_genomes(genomes[index:index + 1], world.lattice),
                       abi=ABI, fast=True, threads=THREADS)
    columns = columns_from_ledger(result.ledger, world, seeds, evaluator)
    atomic_npz(path, identity=np.asarray(binding), seeds=np.asarray(seeds, dtype=np.uint64),
               genome_index=np.asarray(index), ledger=result.ledger,
               cpu_seconds=np.asarray(time.process_time() - cpu_start),
               wall_seconds=np.asarray(time.perf_counter() - wall_start), **columns)
    with np.load(path, allow_pickle=False) as saved:
        if (str(saved["identity"]) != binding or int(saved["genome_index"]) != index
                or saved["seeds"].dtype != np.uint64 or not np.array_equal(saved["seeds"], seeds)):
            raise ValueError("saved row identity changed")
        recomputed = columns_from_ledger(saved["ledger"], world, seeds, evaluator)
        if any(saved[key].tobytes() != recomputed[key].tobytes() for key in COLS):
            raise ValueError("saved columns disagree with production accounting")
        row = {key: saved[key].copy() for key in (*COLS, "cpu_seconds", "wall_seconds")}
    if any(not np.isfinite(float(row[k])) or float(row[k]) < 0 for k in ("cpu_seconds", "wall_seconds")):
        raise ValueError("invalid row timing")
    print(json.dumps({"stage": out.name, "completed_genome_row": index, "lives": len(seeds)}), flush=True)
    return row


class RowStore:
    """I's atomic row index; the external monitor exclusively enforces CPU caps."""

    def __init__(self, out, genomes, world, evaluator, identity):
        self.out, self.genomes, self.world, self.evaluator = out, genomes, world, evaluator
        self.identity, self.index, self.cpu_seconds = identity, {}, 0.0
        if out.exists():
            raise ValueError("first attempt refuses existing measurement directory")

    def row(self, stage, index, seeds):
        target = self.out / stage
        row = score_row(target, index, self.genomes, self.world, seeds, self.evaluator,
                        identity={**self.identity, "stage": stage})
        path = target / f"row_{index:04d}.npz"
        relative = str(path.relative_to(self.out))
        self.cpu_seconds += float(row["cpu_seconds"])
        self.index[relative] = {"sha256": sha(path), "cpu_seconds": float(row["cpu_seconds"])}
        atomic_json(self.out / "row_index.json", self.index)
        return row

    def stage(self, name, indices, seeds):
        rows = {index: self.row(name, index, seeds) for index in indices}
        atomic_npz(self.out / name / "scores.npz", seeds=np.asarray(seeds, dtype=np.uint64),
                   genome_indices=np.asarray(indices),
                   **{key: np.stack([rows[index][key] for index in indices]) for key in COLS})
        return rows


def comparison(winner, parent, world):
    """Retained production accounting, with capture visibility only as a diagnostic."""
    # The kernel uses the reconstructed column cost for net/F. Keep accumulated
    # cost in raw output, but use the identical reconstruction for decomposition.
    def priced(row):
        value = dict(row)
        ledger = np.stack([row[k] for k in ABI.LEDGER], axis=1)
        value["cost"] = ABI.column_cost(ledger, world)
        return value
    winner, parent = priced(winner), priced(parent)
    report = compare_rows(winner, parent, world)
    for name in ("captures", "low_light_captures"):
        report[name] = paired(winner[name], parent[name])
    report["bright_captures"] = paired(winner["captures"] - winner["low_light_captures"],
                                       parent["captures"] - parent["low_light_captures"])
    window = world.T - world.t_open
    pieces = [(winner["income"] - parent["income"]) / window,
              (parent["cost"] - winner["cost"]) / window,
              (parent["guard_charge"] - winner["guard_charge"]) / window,
              parent["extinct_charge"] - winner["extinct_charge"]]
    residual = winner["F"] - parent["F"] - sum(pieces)
    if not np.allclose(residual, 0, atol=1e-9, rtol=0):
        raise ValueError("fitness decomposition does not reconstruct production F")
    report["capture_income"] = paired(pieces[0], np.zeros_like(pieces[0]))
    report["above_3se"] = report["F"]["mean"] > 3 * report["F"]["se"]
    report["interpretation"] = "Paired local fitness/capture improvement; no memory mechanism claim."
    return report
