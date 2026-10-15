"""Replay G/D recorded genetics and audit fixed search checkpoints; no life simulations.

The frozen D analyzer supplies selection/accounting checkpoint checks. This helper
adds exact crossover/point/structural genetic replay and innovation ancestry.
"""
from __future__ import annotations

import copy
import hashlib
import importlib.util
import json
from collections import Counter
from pathlib import Path

import numpy as np
import torch

ROOT = next((p for p in Path(__file__).resolve().parents if (p / "src/genome.py").exists()), None)
D_ANALYZER_SHA = "78a21cde2e65cf733ba072e51f09be043d681640a696b00f43462fdf4d3fd497"


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def read(path):
    return json.loads(Path(path).read_text())


def equal(actual, expected, label):
    if actual != expected:
        raise ValueError(label + " differs from frozen lineage")


def same(left, right):
    a, b = np.asarray(left), np.asarray(right)
    return a.shape == b.shape and a.dtype == b.dtype and a.tobytes() == b.tobytes()


def bridge(study):
    path = study / "sources/continuation_analyze.py"
    if not path.exists():
        path = ROOT / "results/continuation_20261013/analyze.py"
    equal(sha(path), D_ANALYZER_SHA, "frozen D checkpoint/selection analysis source")
    module_spec = importlib.util.spec_from_file_location("structural_D_audit", path)
    module = importlib.util.module_from_spec(module_spec)
    module_spec.loader.exec_module(module)
    return module


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


def replay_genetics(lines, state, layout, founder, structural):
    """Reconstruct every retained raw genome and gene origin from the recorded operations."""
    torch.set_num_threads(1)
    genes = layout.dims.genes_max
    initial = lines[0]
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
    equal(sorted(population), list(range(32)), "initial population ids")
    next_innovation = genes
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
                           "population_distinct_duplicate_origins": len(set(matrix[matrix >= genes].tolist()))})
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
    duplicate_slots = np.flatnonzero(final_origins >= genes).tolist()
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


def lineage_audit(original, lines, curves, state, seed, spec, layout, founder, structural):
    # D's selector audit checks seeds, offspring ids, sexual parentage and pooled top32 ranking.
    # Structural operations are audited separately below, so remove only those keys from its view.
    point_view = copy.deepcopy(lines)
    for row in point_view[1:]:
        for child in row["children"]:
            child["ops"] = {key: value for key, value in child["ops"].items() if key == "mut"}
    report = original(point_view, curves, state, seed, spec)
    report["genetic_replay"] = replay_genetics(lines, state, layout, founder, structural)
    return report


def operation(study, name):
    path = study / name
    return path if path.exists() else study / "operations" / name


def audit(study, protocol, manifest, genomes):
    """Caller has verified completed resource/ledger/source records; reconcile all four fixed endpoints."""
    from src.genome import Layout
    from src.life import spec

    study = Path(study).resolve()
    equal(read(operation(study, "budget.json"))["status"], "complete", "G completed budget")
    baseline = study / "dependency"
    if not baseline.exists():
        baseline = ROOT / protocol["D_study"]
    for name, expected in protocol["D_pins"].items():
        equal(sha(operation(baseline, name)), expected, "D frozen control pin " + name)
    equal(read(operation(baseline, "budget.json"))["status"], "complete", "D completed budget")
    baseline_protocol = read(baseline / "protocol.json")
    equal(baseline_protocol["source_identity"], protocol["source_identity"], "matched D/G sources")
    equal(baseline_protocol["expected_numerical_identity"], protocol["expected_numerical_identity"],
          "matched numerical identity")
    layout, founder = Layout.load(study / "inputs/founder_row38.json")
    helper = bridge(study)
    original = helper.audit_lineage
    result = {}
    for group, folder, plan, offset in (("D", baseline, baseline_protocol, 2), ("G", study, protocol, 4)):
        helper.audit_lineage = lambda lines, curves, state, seed, spec, structural=(group == "G"): lineage_audit(
            original, lines, curves, state, seed, spec, layout, founder, structural)
        result[group] = {}
        for name in ("founder", "pilot"):
            input_path = folder / "inputs" / Path(plan[name + "_file"]).name
            equal(sha(input_path), plan[name + "_sha256"], group + " input " + name)
        for i, seed in enumerate(protocol["runs"]):
            equal(sha(folder / f"configs/s{seed}.yaml"), plan["configs"][str(seed)]["sha256"],
                  group + " pinned search configuration")
            report, raw_genome = helper.search_audit(folder, seed, plan, {"founder": founder.numpy()}, spec, True)
            if not same(raw_genome, genomes[offset + i]):
                raise ValueError("confirmation genotype differs from completed endpoint")
            recorded = manifest["endpoint_audits"][group][str(seed)]
            equal(report["checkpoint_sha256"], recorded["checkpoint_sha256"], "confirmation checkpoint pin")
            equal(report["search_health"], recorded["health"], "confirmation search health")
            replay = report["lineage"]["genetic_replay"]
            for key, actual in (("active_genes", replay["final_rank_zero_active_genes"]),
                                ("duplicate_derived_slots", replay["final_rank_zero_duplicate_slots"]),
                                ("duplicate_origin_ids", replay["final_rank_zero_duplicate_origin_ids"])):
                equal(actual, recorded[key], "endpoint " + key)
            result[group][str(seed)] = report
    helper.audit_lineage = original
    return {"runs": result, "frozen_D_analyzer_sha256": D_ANALYZER_SHA,
            "simulated_lives": 0, "limits": [
                "Genetic replay checks inheritance and recorded operations, not RNG draws.",
                                             "No ancestry or active-gene statistic proves functional use."]}
