"""Independent AH selection replay; only external tie-stream draws, never genetics or lives."""

from __future__ import annotations

import hashlib
import json

import numpy as np
import torch
from omegaconf import OmegaConf

FIELDS = ("W", "b", "lam", "s0", "Q", "act", "A", "a0", "Dm", "km")
DOMAIN = "cell-dev:AH:reserve:v1"
TIE_SEED = 7_919_001


def equal(actual, expected, label):
    if actual != expected:
        raise ValueError(label + " differs")


def identical(left, right):
    a, b = np.asarray(left), np.asarray(right)
    return a.dtype == b.dtype and a.shape == b.shape and a.tobytes() == b.tobytes()


def config_identity(path):
    value = OmegaConf.to_container(OmegaConf.load(path), resolve=True)
    value.pop("extends", None)
    value["logging"].pop("output_dir", None)
    value["logging"].pop("checkpoint_every", None)
    return value


def genome(params):
    equal(set(params), set(FIELDS), "genome fields")
    value = np.concatenate([np.asarray(params[k], dtype=np.float32).reshape(-1) for k in FIELDS])
    if value.shape != (875,) or not np.isfinite(value).all():
        raise ValueError("finite875 genotype required")
    return value


def life_seed(spec, seed, purpose, index, life):
    return spec.hash64(seed, 0x4C494645 + purpose, index, life)


def reserve_positions(seed, generation):
    """Reconstruct unbiased draws from exactly the declared byte stream."""
    if type(seed) is not int or not 0 <= seed < 2**64 or generation not in range(4):
        raise ValueError("invalid reserve key")
    candidates, selected, counter = list(range(32, 256)), [], 0
    for _ in range(2):
        modulus = len(candidates)
        upper = (1 << 64) - ((1 << 64) % modulus)
        while True:
            payload = "|".join((DOMAIN, str(seed), str(generation), str(counter))).encode("ascii")
            value = int.from_bytes(hashlib.sha256(payload).digest()[:8], byteorder="little", signed=False)
            counter += 1
            if value < upper:
                break
        selected.append(candidates.pop(value % modulus))
    return selected


def state_sha(generator):
    return hashlib.sha256(generator.get_state().numpy().tobytes()).hexdigest()


def replay_rank(call, generator, n):
    equal(set(call), {"size", "fitness", "order", "tie_before_sha256", "tie_after_sha256"}, "rank record schema")
    equal(call["size"], n, "native rank permutation size")
    values = np.asarray(call["fitness"], dtype=np.float64)
    if values.shape != (n,) or not np.isfinite(values).all():
        raise ValueError("finite complete rank fitness required")
    equal(call["tie_before_sha256"], state_sha(generator), "tie RNG before rank")
    permutation = torch.randperm(n, generator=generator).tolist()
    # Python's stable ordering independently reproduces native stable descending
    # sorting after its recorded random permutation, including exact ties.
    ordered = sorted(permutation, key=lambda i: -float(values[i]))
    equal(call["order"], ordered, "exact native stable randomized rank")
    equal(call["tie_after_sha256"], state_sha(generator), "tie RNG after rank")
    return values, ordered


def audit_generation(row, curve, parents, seed, mode, policy_sha, tie_generator):
    g = row["gen"]
    if mode not in ("control", "reserve") or g not in range(4):
        raise ValueError("unknown policy mode or generation")
    active = mode == "reserve" and g < 3
    children = row["children"]
    equal([c["id"] for c in children], list(range(32 + 224 * g, 32 + 224 * (g + 1))), "fresh offspring IDs")
    candidate_ids = parents + [c["id"] for c in children]
    if len(set(candidate_ids)) != 256:
        raise ValueError("candidate identifiers overlap")
    for child in children:
        if child["pa"] not in parents or child["pb"] not in parents:
            raise ValueError("parent absent from preceding population")
        if set(child["ops"]) != {"mut"}:
            raise ValueError("ordinary point operations required")
    item = row["exploratory_reserve"]
    equal(set(item), {"generation", "mode", "active", "policy_sha256", "reserve_indices", "base_F",
                     "ranking_calls", "shortlist_indices", "pick_positions", "survivor_indices",
                     "candidate_ids", "reserve_ids"}, "durable policy metadata schema")
    for name, expected in (("generation", g), ("mode", mode), ("active", active),
                           ("policy_sha256", policy_sha), ("candidate_ids", candidate_ids)):
        equal(item[name], expected, name)
    protected = reserve_positions(seed, g) if active else []
    equal(item["reserve_indices"], protected, "independent fresh-offspring lottery")
    equal(item["reserve_ids"], [candidate_ids[i] for i in protected], "lottery genotype identifiers")
    equal(len(item["ranking_calls"]), 3, "exact three ranking calls")
    diagnostic, _ = replay_rank(item["ranking_calls"][0], tie_generator, 256)
    base, initial_order = replay_rank(item["ranking_calls"][1], tie_generator, 256)
    pooled, pooled_order = replay_rank(item["ranking_calls"][2], tie_generator, 64)
    if not identical(diagnostic, base) or not identical(base, np.asarray(item["base_F"], dtype=np.float64)):
        raise ValueError("base fitness changed between native ranking calls")
    if not identical(base[32:], np.asarray([c["fitness"] for c in children], dtype=np.float64)):
        raise ValueError("child initial fitness differs from complete candidate record")
    if active:
        members = set(protected + [i for i in initial_order if i not in protected][:62])
        short = [i for i in initial_order if i in members]
    else:
        short = initial_order[:64]
    equal(item["shortlist_indices"], short, "protected/top62 shortlist and rank order")
    rc = row["recheck"]
    equal(rc["ids"], [candidate_ids[i] for i in short], "rechecked candidate IDs")
    equal(rc["key"], "all", "pooled recheck key")
    if not identical(np.asarray(rc["F_base"], dtype=np.float64), base[short]):
        raise ValueError("recheck base scores differ")
    extra = np.asarray(rc["F_recheck"], dtype=np.float64)
    if extra.shape != (64,) or not np.isfinite(extra).all():
        raise ValueError("all64 finite recheck means required")
    if not np.allclose(pooled, (3 * base[short] + 4 * extra) / 7, rtol=1e-12, atol=1e-12):
        raise ValueError("actual pooled fitness differs from seven-life accounting")
    if active:
        protected_slots = {j for j, i in enumerate(short) if i in protected}
        slots = protected_slots | set([j for j in pooled_order if j not in protected_slots][:30])
        pick = [j for j in pooled_order if j in slots]
    else:
        pick = pooled_order[:32]
    order = [short[j] for j in pick]
    equal(item["pick_positions"], pick, "protected/top30 survivors and rank order")
    equal(item["survivor_indices"], order, "survivor candidate positions")
    survivors = [candidate_ids[i] for i in order]
    equal(row["survivors"], survivors, "survivor identifiers")
    if not identical(np.asarray(row["fitness"], dtype=np.float64), pooled[pick]):
        raise ValueError("survivor fitness differs from actual pooled rank inputs")
    changed = 32 - len(set(order) & set(initial_order[:32]))
    equal(rc["changed"], changed, "reported recheck change count")
    equal(curve["recheck_changed"], changed, "curve recheck change count")
    equal(curve["best_id"], survivors[0], "rank-zero ID")
    equal(curve["fitness"], row["fitness"][0], "rank-zero fitness")
    for child in children:
        equal(child["kept"], child["id"] in survivors, "kept child flag")
    return survivors, {
        "generation": g, "active": active, "protected_ids": item["reserve_ids"],
        "protected_outside_ordinary_initial_top64": [candidate_ids[i] for i in protected if i not in initial_order[:64]],
        "protected_outside_treatment_pooled_top32": [candidate_ids[i] for i in protected if short.index(i) not in pooled_order[:32]],
        "ranking_calls_exact": 3, "tie_state_sha256": state_sha(tie_generator),
    }


def audit_lineage(lines, curves, state, seed, spec, mode, policy):
    initial, generations = lines[0], lines[1:]
    equal(initial["event"], "founders", "initial event")
    equal(initial["sampled"], 0, "no founder sampling")
    equal(initial["ids"], [0], "one initial founder")
    equal([c["id"] for c in initial["copies"]], list(range(1, 32)), "31 recorded ordinary copies")
    equal([c["parent"] for c in initial["copies"]], [0] * 31, "copy parent IDs")
    equal([row["gen"] for row in generations], [0, 1, 2, 3], "four complete lineage generations")
    equal([row["gen"] for row in curves], [0, 1, 2, 3], "four complete curve generations")
    policy_sha = hashlib.sha256(json.dumps(policy, sort_keys=True, separators=(",", ":"), allow_nan=False).encode()).hexdigest()
    tie_generator = torch.Generator().manual_seed(seed + TIE_SEED)
    parents, decisions = list(range(32)), []
    for g, (row, curve) in enumerate(zip(generations, curves)):
        equal(row["seeds"], [life_seed(spec, seed, 1, g, j) for j in range(3)], "initial life IDs")
        equal(row["recheck"]["seeds"], [life_seed(spec, seed, 1, g, j) for j in range(3, 7)], "recheck life IDs")
        equal(float(row["T"]), 1024.0, "lineage duration")
        equal(float(curve["T"]), 1024.0, "curve duration")
        parents, decision = audit_generation(row, curve, parents, seed, mode, policy_sha, tie_generator)
        decisions.append(decision)
    equal(parents, state["ids"].tolist(), "checkpoint final IDs")
    if not identical(np.asarray(generations[-1]["fitness"], dtype=np.float64), state["fitness"].numpy()):
        raise ValueError("checkpoint final fitness differs")
    if not identical(tie_generator.get_state().numpy(), state["tie_generator"].numpy()):
        raise ValueError("checkpoint final tie RNG state differs")
    return {"exact_initial_founders": 1, "initial_mutated_copies": 31, "sexual_offspring": 896,
            "logged_point_mutations_including_initial_copies": sum(len(c["ops"]["mut"]) for c in initial["copies"]) +
                sum(len(c["ops"]["mut"]) for row in generations for c in row["children"]),
            "founder_id_survives": 0 in parents, "final_ids": parents, "policy_decisions": decisions,
            "tie_ranking_calls_replayed": 12, "genetic_random_draws": 0, "simulation_calls": 0}
