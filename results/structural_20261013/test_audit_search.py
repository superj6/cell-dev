"""Synthetic recorded genetics only; no life simulations or selection experiment."""
import copy
import importlib.util
import json
import sys
from collections import Counter
from pathlib import Path

import numpy as np
import pytest
import torch
from omegaconf import OmegaConf

PATH = Path(__file__).with_name("audit_search.py")
SPEC = importlib.util.spec_from_file_location("G_genetic_audit", PATH)
audit = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(audit)
sys.path.insert(0, str(audit.ROOT))


@pytest.fixture(scope="module")
def synthetic():
    from src.evolve import fill
    from src.genome import Layout

    study = Path(__file__).resolve().parent
    layout, founder = Layout.load(study / "inputs/founder_row38.json")
    cfg = OmegaConf.load(study / "configs/s51089.yaml")
    rng = torch.Generator().manual_seed(9)
    initial_ops = []
    parents = fill(founder[None], 32, layout, rng, cfg.evolve, ops=initial_ops)
    pa = torch.randint(32, (224,), generator=rng)
    pb = torch.randint(32, (224,), generator=rng)
    crossed, masks = layout.crossover(parents[pa], parents[pb], rng, masks=True)
    operations = []
    children = layout.mutate(crossed, rng, dup_rate=0.5, del_rate=0.5, split=False, ops=operations)
    assert any("dup" in x and "del" in x for x in operations)
    assert any("dup" in x and "del" not in x for x in operations)
    assert any("del" in x and "dup" not in x for x in operations)
    origins = np.tile(np.r_[np.arange(8), np.full(8, -1)], (224, 1))
    next_origin = 16
    for i, op in enumerate(operations):
        if "dup" in op:
            origins[i, op["dup"][1]] = next_origin
            next_origin += 1
        if "del" in op:
            origins[i, op["del"]] = -1
    chosen = np.arange(32)
    survivors = (chosen + 32).tolist()
    registry = {}
    for slot in range(16):
        count = Counter(int(x) for x in origins[chosen, slot] if x >= 0)
        if count:
            registry[str(slot)] = {str(k): v for k, v in sorted(count.items())}
    initial = {"ids": [0], "copies": [{"id": i + 1, "parent": 0, "ops": op}
                                       for i, op in enumerate(initial_ops)]}
    row = {"gen": 0, "survivors": survivors, "registry": registry,
           "n_active": float((origins[chosen] >= 0).sum(1).mean()),
           "children": [{"id": i + 32, "pa": int(pa[i]), "pb": int(pb[i]),
                         "mask": sum((1 << j) for j, bit in enumerate(masks[i]) if bit),
                         "ops": operations[i], "kept": i < 32} for i in range(224)]}
    state = {"ids": torch.tensor(survivors), "population": children[chosen].clone(),
             "origins": torch.from_numpy(origins[chosen].copy()), "next_innov": next_origin, "next_id": 256}
    return [initial, row], state, layout, founder


def test_structural_replay_reconstructs_raw_population_and_innovation_registry(synthetic):
    lines, state, layout, founder = synthetic
    result = audit.replay_genetics(lines, state, layout, founder, True)
    assert result["raw_population_replay_bitwise"]
    assert result["duplication_events"] > 0 and result["deletion_events"] > 0
    assert result["point_mutations_including_initial_copies"] == 2 * (31 + 224)
    assert result["duplication_events"] == state["next_innov"] - 16


def test_control_cannot_silently_acquire_structural_operations(synthetic):
    lines, state, layout, founder = synthetic
    with pytest.raises(ValueError, match="point-only D"):
        audit.replay_genetics(lines, state, layout, founder, False)


def test_wrong_innovation_registry_is_rejected(synthetic):
    lines, state, layout, founder = synthetic
    altered = copy.deepcopy(lines)
    slot = next(iter(altered[1]["registry"]))
    origin = next(iter(altered[1]["registry"][slot]))
    altered[1]["registry"][slot][origin] += 1
    with pytest.raises(ValueError, match="innovation registry"):
        audit.replay_genetics(altered, state, layout, founder, True)


def test_wrong_final_population_bytes_are_rejected(synthetic):
    lines, state, layout, founder = synthetic
    altered = copy.deepcopy(state)
    altered["population"][0, 0] += 0.125
    with pytest.raises(ValueError, match="raw final population"):
        audit.replay_genetics(lines, altered, layout, founder, True)


def test_wrong_innovation_counter_is_rejected(synthetic):
    lines, state, layout, founder = synthetic
    altered = {**state, "next_innov": state["next_innov"] + 1}
    with pytest.raises(ValueError, match="innovation counter"):
        audit.replay_genetics(lines, altered, layout, founder, True)


def test_point_mutation_cannot_write_an_activation_flag(synthetic):
    _, _, layout, founder = synthetic
    with pytest.raises(ValueError, match="active mask"):
        audit.point_mutation(layout, founder, {"mut": [["act", [8], 1.0], ["a0", [0], 0.1]]})


def test_frozen_D_helper_hash_is_checked(tmp_path):
    path = tmp_path / "sources/continuation_analyze.py"
    path.parent.mkdir()
    path.write_text("# wrong source\n")
    with pytest.raises(ValueError, match="source"):
        audit.bridge(tmp_path)


def test_replay_completed_D_checkpoint_without_any_life_simulation():
    from src.genome import Layout

    study = audit.ROOT / "results/continuation_20261013"
    layout, founder = Layout.load(study / "inputs/founder_row38.json")
    # One real complete baseline validates the operation logger/replay contract as well as the synthetic fixture.
    folder = study / "runs/s51089"
    lines = [json.loads(row) for row in (folder / "lineage.jsonl").read_text().splitlines()]
    state = torch.load(folder / "checkpoint.pt", map_location="cpu", weights_only=True)["state"]
    result = audit.replay_genetics(lines, state, layout, founder, False)
    assert result["raw_population_replay_bitwise"] and result["duplication_events"] == 0
