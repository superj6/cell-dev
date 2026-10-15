"""AL ordinary selection checks adapted from AJ solely for four initial plus four recheck lives."""
import numpy as np
from omegaconf import OmegaConf


def identical(left, right):
    left, right = np.asarray(left), np.asarray(right)
    return left.shape == right.shape and left.dtype == right.dtype and left.tobytes() == right.tobytes()

def equal(actual, expected, label):
    if actual != expected:
        raise ValueError(f"{label}: differs from frozen study")

def life_seed(spec, run_seed, purpose, index, life):
    return spec.hash64(run_seed, 0x4C494645 + purpose, index, life)

def config_identity(path):
    value = OmegaConf.to_container(OmegaConf.load(path), resolve=True)
    value.pop("extends", None)
    value["logging"].pop("output_dir", None)
    value["logging"].pop("checkpoint_every", None)
    return value

def audit_lineage(lines, curves, state, seed, spec):
    initial, generations = lines[0], lines[1:]
    equal(initial["event"], "founders", "initial event")
    equal(initial["sampled"], 0, "founder sampling")
    equal(initial["ids"], list(range(32)), "all32 imported founder ids")
    equal(initial["copies"], [], "no new initial copies")
    equal([row["gen"] for row in generations], list(range(len(curves))), "lineage generations")
    parents = list(range(32))
    mutations = sum(len(c["ops"].get("mut", [])) for c in initial["copies"])
    offspring = 0
    for g, (row, curve) in enumerate(zip(generations, curves)):
        equal(row["seeds"], [life_seed(spec, seed, 1, g, j) for j in range(4)], "initial seeds")
        equal(row["recheck"]["seeds"], [life_seed(spec, seed, 1, g, j) for j in range(4, 8)], "recheck seeds")
        equal(float(row["T"]), float(curve["T"]), "lineage duration")
        children = row["children"]
        equal([c["id"] for c in children], list(range(32 + 224 * g, 32 + 224 * (g + 1))), "offspring ids")
        for child in children:
            if child["pa"] not in parents or child["pb"] not in parents:
                raise ValueError("sexual offspring parent is absent from the preceding population")
            if any(key != "mut" and value for key, value in child["ops"].items()):
                raise ValueError("unregistered structural mutation")
            mutations += len(child["ops"].get("mut", []))
        candidates = set(parents) | {c["id"] for c in children}
        survivors = row["survivors"]
        if len(survivors) != 32 or len(set(survivors)) != 32 or not set(survivors) <= candidates:
            raise ValueError("invalid survivor population")
        shortlist = row["recheck"]["ids"]
        if len(shortlist) != 64 or len(set(shortlist)) != 64 or not set(survivors) <= set(shortlist) <= candidates:
            raise ValueError("invalid recheck shortlist")
        equal(row["recheck"]["key"], "all", "recheck ranking key")
        base = np.asarray(row["recheck"]["F_base"])
        extra = np.asarray(row["recheck"]["F_recheck"])
        if base.shape != (64,) or extra.shape != (64,) or not np.isfinite(base + extra).all():
            raise ValueError("invalid recheck score vectors")
        pooled = (4 * base + 4 * extra) / 8
        chosen = [shortlist.index(value) for value in survivors]
        if not np.allclose(pooled[chosen], row["fitness"], rtol=1e-12, atol=1e-12):
            raise ValueError("selected fitness differs from the eight-life pooled scores")
        unchosen = [i for i in range(64) if i not in chosen]
        if (np.any(np.diff(base) > 1e-12) or np.any(np.diff(pooled[chosen]) > 1e-12)
                or np.max(pooled[unchosen]) > np.min(pooled[chosen]) + 1e-12):
            raise ValueError("survivors differ from the top32 pooled shortlist")
        for child in children:
            equal(child["kept"], child["id"] in survivors, "kept child flag")
        equal(curve["best_id"], survivors[0], "selected rank-zero id")
        if not np.isclose(row["fitness"][0], curve["fitness"], rtol=1e-13):
            raise ValueError("selected fitness differs between logs")
        parents = survivors
        offspring += len(children)
    equal(parents, state["ids"].tolist(), "checkpoint final population ids")
    if not np.array_equal(np.asarray(generations[-1]["fitness"]), state["fitness"].numpy()):
        raise ValueError("checkpoint fitness differs from final lineage")
    return {"exact_initial_founders": 32, "initial_mutated_copies": 0, "sexual_offspring": offspring,
            "logged_point_mutations_including_initial_copies": mutations,
            "initial_founder_ids_survive": [i for i in range(32) if i in parents], "final_ids": parents}
