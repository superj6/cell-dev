"""Independent NumPy ABI3 genotype operations and recorded-lineage replay; never simulate."""
from __future__ import annotations

import hashlib
import math
from collections import Counter

import numpy as np

FIELDS = {"W": (16, 25), "b": (16,), "lam": (16,), "s0": (16,), "Q": (16,), "act": (16,),
          "A": (23, 16), "a0": (23,), "Dm": (2,), "km": (2,)}
SLICES = {}
_offset = 0
for _name, _shape in FIELDS.items():
    SLICES[_name] = slice(_offset, _offset + math.prod(_shape))
    _offset += math.prod(_shape)
SIZE = _offset
UNITS = np.concatenate([np.repeat(np.arange(16), 25), *([np.arange(16)] * 5),
                        np.tile(np.arange(16), 23), np.full(27, 16)])


def raw_sha(value):
    return hashlib.sha256(np.asarray(value).tobytes()).hexdigest()


def same(left, right):
    return left.shape == right.shape and left.dtype == right.dtype and left.tobytes() == right.tobytes()


def view(genome, name):
    return genome[SLICES[name]].reshape(FIELDS[name])


def from_json(record):
    expected = {"genes_max": 16, "genes_init": 8, "morph": 2, "channels": 2, "stim": 1,
                "pheno": 22, "kind": "life", "cues": 2}
    if record["dims"] != expected or set(record["params"]) != set(FIELDS):
        raise ValueError("genome ABI/dimensions differ")
    values = [np.asarray(record["params"][key], dtype=np.float32) for key in FIELDS]
    if any(value.shape != shape for value, shape in zip(values, FIELDS.values())):
        raise ValueError("genome field shape differs")
    result = np.concatenate([value.reshape(-1) for value in values])
    if not np.isfinite(result).all():
        raise ValueError("nonfinite genome")
    return result


def silence(genome):
    result = genome.copy()
    keep = (view(result, "act") > .5)[None, :] | np.eye(16, dtype=bool)
    view(result, "W")[:, :16] = np.where(keep, view(result, "W")[:, :16], np.float32(0))
    return result


def delete(genome, slot):
    if not 0 <= slot < 16 or view(genome, "act")[slot] <= .5:
        raise ValueError("delete requires an active gene")
    result = genome.copy()
    view(result, "act")[slot] = 0
    return silence(result)


def duplicate(genome, source, destination):
    active = view(genome, "act") > .5
    if not 0 <= source < 16 or not 0 <= destination < 16 or not active[source] or active[destination]:
        raise ValueError("duplicate requires active source and inactive destination")
    result = genome.copy()
    w, a = view(result, "W"), view(result, "A")
    w[:, destination], a[:, destination] = 0, 0
    w[destination] = w[source]
    for name in ("b", "lam", "s0", "Q"):
        view(result, name)[destination] = view(result, name)[source]
    view(result, "act")[destination] = 1
    return result


def sigmoid(value):
    try:
        return 1.0 / (1.0 + math.exp(-float(value)))
    except OverflowError:
        return 0.0


def pack(genome):
    """Independent fixed ABI3/hexprism decoder, preserving the specified scalar operation order."""
    if genome.shape != (875,) or genome.dtype != np.float32 or not np.isfinite(genome).all():
        raise ValueError("need one finite raw FP32 ABI3 genome")
    result = genome.astype(np.float64)
    active = (view(result, "act") > .5).astype(np.float64)
    w, a = view(result, "W"), view(result, "A")
    w[active == 0, :], w[:, :16][:, active == 0], a[:, active == 0] = 0, 0, 0
    for name in ("b", "Q"):
        view(result, name)[:] *= active
    view(result, "lam")[:] = [2.0 ** -(1.0 + min(6.0, max(0.0, float(round(float(x) + 3.0)))))
                              for x in view(result, "lam")]
    view(result, "lam")[:] *= active
    view(result, "s0")[:] = [sigmoid(x) for x in view(result, "s0")]
    view(result, "s0")[:] *= active
    view(result, "act")[:] = active
    view(result, "Dm")[:] = [(0.9 * sigmoid(x)) / (8 * 3.0) for x in view(result, "Dm")]
    view(result, "km")[:] = [0.005 + 0.3 * sigmoid(x) for x in view(result, "km")]
    return np.ascontiguousarray(result + 0.0)


def point(genome, operations):
    active = view(genome, "act") > .5
    changes = operations.get("mut", [])
    if len(changes) != max(1, round(2 * int(active.sum()) / 8)):
        raise ValueError("point mutation count differs")
    result, seen, blocks = genome.copy(), set(), set()
    for name, indices, delta in changes:
        if name not in FIELDS or not np.isfinite(delta):
            raise ValueError("invalid point mutation")
        local = int(np.ravel_multi_index(tuple(indices), FIELDS[name]))
        flat = SLICES[name].start + local
        unit = UNITS[flat]
        if (flat in seen or name == "act" or (unit < 16 and not active[unit])
                or (name == "W" and indices[1] < 16 and not active[indices[1]])):
            raise ValueError("point mutation violates active mask or uniqueness")
        seen.add(flat)
        blocks.add(name in ("A", "a0"))
        result[flat] = np.float32(result[flat] + np.float32(delta))
    if len(blocks) != 1:
        raise ValueError("point mutations span blocks")
    return result


def registry(origins):
    result = {}
    for slot in range(16):
        counts = Counter(int(value) for value in origins[:, slot] if value >= 0)
        if counts:
            result[str(slot)] = {str(k): v for k, v in sorted(counts.items())}
    return result


def replay(lines, founder, generations=16):
    """Replay all recorded genotypes/origins, including discarded duplications; no outcome-based filtering."""
    if len(lines) != generations + 1 or lines[0]["ids"] != [0]:
        raise ValueError("lineage generations/founder differ")
    population = {0: founder.copy()}
    origin = np.where(view(founder, "act") > .5, np.arange(16), -1)
    origins = {0: origin.copy()}
    for item in lines[0]["copies"]:
        if item["parent"] != 0 or set(item["ops"]) != {"mut"} or item["id"] in population:
            raise ValueError("initial founder copies differ")
        population[item["id"]] = point(founder, item["ops"])
        origins[item["id"]] = origin.copy()
    if sorted(population) != list(range(32)):
        raise ValueError("initial population differs")
    innovations = []
    next_origin, next_id, points, duplicates, deletions = 16, 32, 62, 0, 0
    for generation, row in enumerate(lines[1:]):
        if row["gen"] != generation or len(row["children"]) != 224:
            raise ValueError("lineage generation/offspring count differs")
        candidates, ancestry = dict(population), dict(origins)
        for item in row["children"]:
            if item["id"] != next_id:
                raise ValueError("individual id sequence differs")
            next_id += 1
            pa, pb, mask, operations = item["pa"], item["pb"], item["mask"], item["ops"]
            if pa not in population or pb not in population or set(operations) - {"mut", "dup", "del"}:
                raise ValueError("parent/operator outside registered policy")
            if not isinstance(mask, int) or not 0 <= mask < 1 << 17:
                raise ValueError("invalid crossover unit mask")
            bits = np.asarray([(mask >> k) & 1 for k in range(17)], dtype=bool)
            mixed = silence(np.where(bits[UNITS], population[pa], population[pb]))
            gene_origin = np.where(bits[:16], origins[pa], origins[pb]).copy()
            child = point(mixed, operations)
            points += len(operations.get("mut", []))
            if "dup" in operations:
                source, destination = operations["dup"]
                child = duplicate(child, source, destination)
                innovations.append({"origin_id": next_origin, "generation": generation, "child_id": item["id"],
                                    "source_slot": source, "destination_slot": destination,
                                    "source_origin_id": int(gene_origin[source]),
                                    "child_retained": item["id"] in row["survivors"]})
                gene_origin[destination] = next_origin
                next_origin += 1
                duplicates += 1
            if "del" in operations:
                child = delete(child, operations["del"])
                gene_origin[operations["del"]] = -1
                deletions += 1
            if not np.array_equal(view(child, "act") > .5, gene_origin >= 0):
                raise ValueError("active slots disagree with innovation origins")
            candidates[item["id"]], ancestry[item["id"]] = child, gene_origin
        survivors = row["survivors"]
        if len(survivors) != 32 or len(set(survivors)) != 32 or not set(survivors) <= set(candidates):
            raise ValueError("invalid survivor ids")
        population = {key: candidates[key] for key in survivors}
        origins = {key: ancestry[key] for key in survivors}
        matrix = np.stack(list(origins.values()))
        if registry(matrix) != row["registry"] or float((matrix >= 0).sum(axis=1).mean()) != row["n_active"]:
            raise ValueError("innovation registry or active count differs")
    return np.stack(list(population.values())), matrix, {
        "next_innovation": next_origin, "next_individual": next_id, "point_mutations": points,
        "duplication_events": duplicates, "deletion_events": deletions, "generations": generations,
        "duplication_origins": innovations,
        "final_ids": list(population), "rank_zero_raw_sha256": raw_sha(next(iter(population.values())))}
