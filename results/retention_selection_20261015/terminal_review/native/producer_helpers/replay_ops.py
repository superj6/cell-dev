"""AL recorded-operation primitives, extracted unchanged from reviewed AJ genetics.
Only definitions: no stochastic sampling, evaluator imports, builds or life calls.
"""
from collections import Counter

import numpy as np
import torch


def equal(actual, expected, label):
    if actual != expected:
        raise ValueError(label + " differs from frozen lineage")

def same(left, right):
    a, b = np.asarray(left), np.asarray(right)
    return a.shape == b.shape and a.dtype == b.dtype and a.tobytes() == b.tobytes()

def registry(origins):
    output = {}
    for slot in range(origins.shape[1]):
        counts = Counter(int(x) for x in origins[:, slot] if x >= 0)
        if counts:
            output[str(slot)] = {str(key): value for key, value in sorted(counts.items())}
    return output

def point_mutation(layout, parent, operations):
    """Replay recorded float32 additions, enforcing the ordinary active-mask/block constraints."""
    mutant = parent.clone()
    changes = operations.get("mut", [])
    equal(len(changes), int(layout.n_mut_of(parent[None], 2)[0]), "point mutation count")
    allowed = layout.mutable(parent[None])[0]
    seen, blocks = set(), set()
    for name, indices, delta in changes:
        if name not in layout.slices or not np.isfinite(delta):
            raise ValueError("invalid recorded point mutation")
        start, stop, shape = layout.slices[name]
        try:
            flat = start + int(np.ravel_multi_index(tuple(indices), shape))
        except ValueError as error:
            raise ValueError("point mutation field index is out of range") from error
        if flat >= stop or flat in seen or not bool(allowed[flat]):
            raise ValueError("point mutation violates active mask or uniqueness")
        seen.add(flat)
        blocks.add(int(layout.block_of[flat]))
        mutant[flat] += float(delta)
    if len(blocks) != 1:
        raise ValueError("point mutations span multiple mutation blocks")
    return mutant

def replay_genetics(lines, state, layout, founder, structural, *, initial_population=None):
    """Reconstruct every retained raw genome and gene origin from the recorded operations."""
    torch.set_num_threads(1)
    genes = layout.dims.genes_max
    initial = lines[0]
    if initial_population is None:
        equal(initial["ids"], [0], "single exact founder")
        population = {0: founder.clone()}
        origin = np.where(layout.active(founder).numpy(), np.arange(genes), -1)
        origins = {0: origin.copy()}
        for child in initial["copies"]:
            equal(child["parent"], 0, "initial copy parent")
            if set(child["ops"]) != {"mut"}:
                raise ValueError("initial copies must remain ordinary point mutations")
            population[child["id"]] = point_mutation(layout, founder, child["ops"])
            origins[child["id"]] = origin.copy()
        initial_origin_count = genes
    else:
        equal(initial["ids"], list(range(32)), "all32 imported founder ids")
        equal(initial["copies"], [], "no initial mutation copies")
        equal(tuple(initial_population.shape), (32, layout.size), "full imported population shape")
        equal(initial_population.dtype, torch.float32, "imported population dtype")
        if not bool(torch.isfinite(initial_population).all()):
            raise ValueError("nonfinite imported population")
        population = {i: initial_population[i].clone() for i in range(32)}
        origins = {i: np.where(layout.active(population[i]).numpy(), i * genes + np.arange(genes), -1)
                   for i in range(32)}
        initial_origin_count = 32 * genes
    equal(sorted(population), list(range(32)), "initial population ids")
    next_innovation = initial_origin_count
    innovations, deletions, trajectory = [], [], []
    total_points = sum(len(child["ops"]["mut"]) for child in initial["copies"])
    for row in lines[1:]:
        all_genomes = dict(population)
        all_origins = {key: value.copy() for key, value in origins.items()}
        duplicate_count, deletion_count = 0, 0
        for child in row["children"]:
            if set(child["ops"]) - {"mut", "dup", "del"}:
                raise ValueError("unregistered genetic operator")
            if not structural and set(child["ops"]) != {"mut"}:
                raise ValueError("structural mutation appeared in the point-only D control")
            pa, pb = child["pa"], child["pb"]
            if pa not in population or pb not in population:
                raise ValueError("offspring parent missing from preceding generation")
            mask = child["mask"]
            if not isinstance(mask, int) or mask < 0 or mask >= 1 << layout.n_units:
                raise ValueError("invalid crossover unit mask")
            units = torch.tensor([(mask >> i) & 1 for i in range(layout.n_units)], dtype=torch.bool)
            mixed = torch.where(units[layout.unit_of], population[pa], population[pb])
            mixed = layout.silence(mixed)
            ancestry = np.where(units[:genes].numpy(), origins[pa], origins[pb]).copy()
            mutant = point_mutation(layout, mixed, child["ops"])
            total_points += len(child["ops"]["mut"])
            if "dup" in child["ops"]:
                source, destination = child["ops"]["dup"]
                active = layout.active(mutant)
                if (not 0 <= source < genes or not 0 <= destination < genes or not active[source]
                        or active[destination]):
                    raise ValueError("duplication did not copy an active gene into a free slot")
                innovations.append({"origin_id": next_innovation, "generation": row["gen"],
                                    "child_id": child["id"], "source_slot": source, "destination_slot": destination,
                                    "source_origin_id": int(ancestry[source]), "child_retained": child["kept"]})
                mutant = layout.duplicate(mutant, source, destination, split=False)
                ancestry[destination] = next_innovation
                next_innovation += 1
                duplicate_count += 1
            if "del" in child["ops"]:
                deleted = child["ops"]["del"]
                if not 0 <= deleted < genes or not bool(layout.active(mutant)[deleted]):
                    raise ValueError("deletion did not target an active gene")
                deletions.append({"generation": row["gen"], "child_id": child["id"], "slot": deleted,
                                  "origin_id": int(ancestry[deleted]), "child_retained": child["kept"]})
                mutant = layout.delete(mutant, deleted)
                ancestry[deleted] = -1
                deletion_count += 1
            if not np.array_equal(layout.active(mutant).numpy(), ancestry >= 0):
                raise ValueError("genome active mask differs from replayed origins")
            all_genomes[child["id"]] = mutant
            all_origins[child["id"]] = ancestry
        survivors = row["survivors"]
        population = {key: all_genomes[key] for key in survivors}
        origins = {key: all_origins[key] for key in survivors}
        matrix = np.stack(list(origins.values()))
        equal(registry(matrix), row["registry"], "per-generation innovation registry")
        active_counts = (matrix >= 0).sum(axis=1)
        equal(float(active_counts.mean()), row["n_active"], "mean active genes")
        trajectory.append({"generation": row["gen"], "duplication_events": duplicate_count,
                           "deletion_events": deletion_count, "mean_active_genes": float(active_counts.mean()),
                           "min_active_genes": int(active_counts.min()), "max_active_genes": int(active_counts.max()),
                           "rank_zero_active_genes": int(active_counts[0]),
                           "population_distinct_duplicate_origins": len(set(matrix[matrix >= initial_origin_count].tolist()))})
    equal(list(population), state["ids"].tolist(), "reconstructed final ids")
    genomes = torch.stack(list(population.values())).numpy()
    matrix = np.stack(list(origins.values()))
    if not same(genomes, state["population"].numpy()):
        raise ValueError("raw final population does not replay bitwise from recorded genetic operations")
    if not same(matrix, state["origins"].numpy()):
        raise ValueError("final origins do not replay from crossover and structural events")
    equal(next_innovation, state["next_innov"], "next innovation counter")
    equal(32 + 224 * (len(lines) - 1), state["next_id"], "next individual counter")
    final_origins = matrix[0]
    duplicate_slots = np.flatnonzero(final_origins >= initial_origin_count).tolist()
    return {"raw_population_replay_bitwise": True, "point_mutations_including_initial_copies": total_points,
            "duplication_events": len(innovations), "deletion_events": len(deletions),
            "retained_children_with_duplication": sum(item["child_retained"] for item in innovations),
            "retained_children_with_deletion": sum(item["child_retained"] for item in deletions),
            "duplication_origins": innovations, "deletions": deletions, "trajectory": trajectory,
            "final_rank_zero_active_genes": int(np.count_nonzero(final_origins >= 0)),
            "final_rank_zero_duplicate_slots": duplicate_slots,
            "final_rank_zero_duplicate_origin_ids": final_origins[duplicate_slots].tolist(),
            "interpretation": "Recorded genetic operations and ancestry reproduce raw genomes exactly. "
                              "Active gene count, duplication ancestry and survival do not establish functional use."}
