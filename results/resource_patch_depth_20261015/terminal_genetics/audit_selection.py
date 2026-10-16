"""Independent saved-selection mathematics; no selector, simulator or RNG imports/calls."""

from __future__ import annotations

import hashlib
import json
import math
from pathlib import Path

import numpy as np

PATTERN = ("patch", "pool", "patch", "persistent") * 8
NAMES = ("patch", "pool", "persistent", "production_F")
FIELDS = ("W", "b", "lam", "s0", "Q", "act", "A", "a0", "Dm", "km")


def require(condition, message):
    if not condition:
        raise ValueError(message)


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def read(path):
    return json.loads(Path(path).read_text())


def raw_sha(value):
    return hashlib.sha256(np.asarray(value).tobytes()).hexdigest()


def same(actual, expected, label):
    actual, expected = np.asarray(actual), np.asarray(expected)
    require(
        actual.shape == expected.shape and actual.dtype == expected.dtype and actual.tobytes() == expected.tobytes(),
        label,
    )


def permutation(value, n):
    value = np.asarray(value)
    require(
        value.shape == (n,) and value.dtype.kind in "iu" and sorted(value.tolist()) == list(range(n)),
        "invalid supplied tie permutation",
    )
    return [int(i) for i in value]


def objectives(captures, fitness):
    """Recompute registered float64 means, separately cross-checking F with scalar fsum."""
    captures, fitness = np.asarray(captures), np.asarray(fitness)
    require(
        captures.shape == fitness.shape
        and fitness.ndim == 2
        and fitness.shape[1] in (32, 64)
        and captures.dtype == fitness.dtype == np.float64
        and np.isfinite(fitness).all()
        and np.isfinite(captures).all()
        and (captures >= 0).all()
        and np.equal(captures, np.floor(captures)).all(),
        "invalid objective source matrices",
    )
    labels = PATTERN * (fitness.shape[1] // 32)
    parts = [captures[:, [i for i, label in enumerate(labels) if label == name]].mean(axis=1) for name in NAMES[:3]]
    means = fitness.mean(axis=1)
    for row, mean in zip(fitness, means, strict=True):
        reference = math.fsum(float(x) for x in row) / len(row)
        error_bound = 8 * np.finfo(np.float64).eps * math.fsum(abs(float(x)) for x in row) / len(row)
        require(abs(float(mean) - reference) <= error_bound, "F mean differs from fsum bound")
    return np.column_stack([*parts, means])


def ranking(values, ties):
    """Lexicographic DAG traversal gives front depth; scalar value groups give crowding.

    This does not use the production selector's dominance matrix, front peeling,
    np.unique grouping or lexsort ordering. Shared NumPy mean rounding is explicit.
    """
    rows = np.asarray(values, dtype=np.float64).tolist()
    require(
        rows and all(len(row) == 4 and all(math.isfinite(x) for x in row) for row in rows),
        "finite four-objective rows required",
    )
    ties = permutation(ties, len(rows))
    ranks = [-1] * len(rows)
    previous = []
    for j in sorted(range(len(rows)), key=lambda i: tuple(rows[i]), reverse=True):
        dominators = [
            i
            for i in previous
            if all(a >= b for a, b in zip(rows[i], rows[j], strict=True))
            and any(a > b for a, b in zip(rows[i], rows[j], strict=True))
        ]
        ranks[j] = 1 + max((ranks[i] for i in dominators), default=-1)
        previous.append(j)
    crowd = [0.0] * len(rows)
    for front in range(max(ranks) + 1):
        members = [i for i, rank in enumerate(ranks) if rank == front]
        for dimension in range(4):
            groups = {}
            for i in members:
                groups.setdefault(rows[i][dimension], []).append(i)
            levels = sorted(groups)
            if len(levels) < 2:
                continue
            scale = max(abs(levels[0]), abs(levels[-1]))
            scaled = [value / scale for value in levels]
            span = scaled[-1] - scaled[0]
            for k, level in enumerate(levels):
                delta = math.inf if k in (0, len(levels) - 1) else (scaled[k + 1] - scaled[k - 1]) / span
                for i in groups[level]:
                    crowd[i] += delta
    priority = {i: rank for rank, i in enumerate(ties)}
    order = sorted(range(len(rows)), key=lambda i: (ranks[i], -crowd[i], priority[i]))
    return {
        "objective_names": list(NAMES),
        "objectives": rows,
        "ranks": ranks,
        "crowding": [None if math.isinf(x) else x for x in crowd],
        "crowding_infinite": [math.isinf(x) for x in crowd],
        "order": order,
        "tie_order": ties,
    }


def mean_order(values, ties):
    return sorted(permutation(ties, len(values)), key=lambda i: -float(values[i]))


def packed_genome(params):
    require(set(params) == set(FIELDS), "genome field schema differs")
    result = np.concatenate([np.asarray(params[name], dtype=np.float32).reshape(-1) for name in FIELDS])
    require(result.shape == (875,) and np.isfinite(result).all(), "genome packed dimensions/finiteness")
    return result


def stage_arrays(arrays, record):
    for prefix, size in (("base", 256), ("recheck", 64)):
        for field in ("captures", "production_F", "native_F", "status", "extinct_charge", "invalid", "mismatch"):
            a = arrays[f"{prefix}_{field}"]
            require(a.shape == (size, 32) and np.isfinite(a).all(), "scored row shape/finiteness")
        require(
            not arrays[prefix + "_invalid"].any() and not arrays[prefix + "_mismatch"].any(),
            "invalid/mismatch source rows",
        )
        same(
            arrays[prefix + "_production_F"],
            arrays[prefix + "_native_F"] - arrays[prefix + "_extinct_charge"],
            "ordinary production F differs",
        )
    permutation(arrays["pre_permutation"], 256)
    base = objectives(arrays["base_captures"], arrays["base_production_F"])
    first = ranking(base, arrays["shortlist_permutation"])
    require(record["stage0_pareto"] == first, "base front/crowding/order audit differs")
    order0 = first["order"]
    short = np.asarray(order0[:64], dtype=np.int64)
    joined = [
        np.concatenate((arrays["base_" + name][short], arrays["recheck_" + name]), axis=1)
        for name in ("captures", "production_F")
    ]
    pooled = objectives(*joined)
    second = ranking(pooled, arrays["survivor_permutation"])
    require(record["stage1_pareto"] == second, "pooled64 front/crowding/order audit differs")
    order1 = second["order"]
    pick = np.asarray(order1[:32], dtype=np.int64)
    for key, value in (
        ("base_objectives", base),
        ("pooled_objectives", pooled),
        ("shortlist", short),
        ("pick", pick),
        ("shortlist_order", np.asarray(order0, dtype=np.int64)),
        ("survivor_order", np.asarray(order1, dtype=np.int64)),
    ):
        same(arrays[key], value, key + " differs")
    same(arrays["recheck_genomes"], arrays["base_genomes"][short], "recheck genotype row order")
    require(record["selection_order"] == short[pick].tolist(), "selected candidate order differs")
    return short, pick, pooled[pick]


def audit(study, protocol, saved, initial, lines, curves):
    """Independent ranks and recorded row linkage; return arrays for the genetic observer."""
    folder = study / "runs/pareto"
    state = saved["state"]
    parents, parent_genomes = list(range(32)), initial
    stages, loaded, pins = [], {}, {}
    schedule = read(study / "namespace/seed_audit.json")["native_records"]
    generation_seeds = {
        g: [row["seed"] for row in schedule if row["purpose"] == "gen" and row["index"] == g] for g in range(8)
    }
    expected_worlds = np.asarray([protocol["worlds"][name]["world_vector"] for name in PATTERN])
    for g, row in enumerate(lines[1:]):
        rec = row["selection"]
        filename = f"selection/g{g:03d}.npz"
        require(
            rec["path"] == filename
            and rec["sha256"] == sha(folder / filename)
            and rec["arm"] == "pareto"
            and rec["base_shape"] == [256, 32]
            and rec["recheck_shape"] == [64, 32]
            and rec["survivor_lives"] == 64
            and rec["extra_lives"] == rec["extra_rng_draws"] == 0,
            "selection dimensions/provenance differ",
        )
        with np.load(folder / filename, allow_pickle=False) as file:
            a = {name: file[name] for name in file.files}
        loaded[g] = a
        children = [child["id"] for child in row["children"]]
        require(children == list(range(32 + g * 224, 32 + (g + 1) * 224)), "child ID sequence")
        ids = np.asarray(parents + children, dtype=np.int64)
        same(a["candidate_ids"], ids, "candidate IDs")
        require(
            a["base_genomes"].shape == (256, 875)
            and a["base_genomes"].dtype == np.float32
            and np.isfinite(a["base_genomes"]).all(),
            "candidate genotype matrix",
        )
        same(a["base_genomes"][:32], parent_genomes, "retained parent genotype order")
        require(raw_sha(a["base_genomes"]) == rec["candidate_raw_sha256"], "candidate genotype hash")
        require(
            len(generation_seeds[g]) == 64
            and row["seeds"] == generation_seeds[g][:32]
            and row["recheck"]["seeds"] == generation_seeds[g][32:],
            "registered native life schedule",
        )
        for prefix, seeds in (("base", row["seeds"]), ("recheck", row["recheck"]["seeds"])):
            same(a[prefix + "_seeds"], np.asarray(seeds, dtype=np.uint64), "native seed rows")
            same(a[prefix + "_worlds"], expected_worlds, "selection world rows")
        short, pick, final_objectives = stage_arrays(a, rec)
        chosen = short[pick]
        require(
            ids[short].tolist() == row["recheck"]["ids"]
            and ids[chosen].tolist() == row["survivors"]
            and final_objectives[:, 3].tolist() == row["fitness"],
            "lineage retention/F differs",
        )
        base_F, new_F = a["base_production_F"].mean(axis=1), a["recheck_production_F"].mean(axis=1)
        require(
            base_F[32:].tolist() == [child["fitness"] for child in row["children"]]
            and base_F[short].tolist() == row["recheck"]["F_base"]
            and new_F.tolist() == row["recheck"]["F_recheck"],
            "recorded scalar life means differ",
        )
        changed = 32 - len(set(chosen.tolist()) & set(short[:32].tolist()))
        curve = curves[g]
        require(
            row["recheck"]["key"] == "all"
            and row["recheck"]["changed"] == changed == curve["recheck_changed"]
            and curve["best_id"] == int(ids[chosen[0]])
            and curve["fitness"] == float(final_objectives[0, 3])
            and curve["evals"] == 320 * (g + 1)
            and curve["recheck_k"] == 64,
            "native curve/recheck linkage differs",
        )
        diagnostic_order = mean_order(base_F, a["pre_permutation"])
        parents = ids[chosen].tolist()
        parent_genomes = a["base_genomes"][chosen]
        stages.append(
            dict(
                generation=g,
                selection_sha256=rec["sha256"],
                rankings_checked=2,
                tie_permutations_checked=3,
                base_rows=256,
                pooled_rows=64,
                diagnostic_scalar_top32_ids=ids[diagnostic_order[:32]].tolist(),
            )
        )
        pins["runs/pareto/" + filename] = rec["sha256"]
    same(state["population"].numpy(), parent_genomes, "checkpoint selected genotypes")
    same(state["ids"].numpy(), np.asarray(parents, dtype=np.int64), "checkpoint selected IDs")
    same(state["fitness"].numpy(), final_objectives[:, 3], "checkpoint selected F")
    public = read(folder / "population.json")
    same(np.stack([packed_genome(row) for row in public["genomes"]]), parent_genomes, "public genotypes")
    require(public["ids"] == parents, "public survivor IDs")
    return dict(
        status="passed",
        stages=stages,
        artifact_pins=pins,
        rankings_checked=16,
        tie_permutations_checked=24,
        selection_lives_checked=81920,
        initial_rows=32,
        all_final_rows_checked=32,
        first_candidate_raw_sha256=raw_sha(loaded[0]["base_genomes"]),
        limits=[
            "Independent dominance DAG and scalar grouped-coordinate crowding, without importing the selector.",
            "Native tie permutations are retained and applied; their RNG stream is not resampled.",
            "NumPy mean rounding is shared; scalar fsum independently bounds aggregate F arithmetic.",
            "Fresh reporting endpoint and confirmation accounting belong to the separate measurement audit.",
        ],
    ), loaded
