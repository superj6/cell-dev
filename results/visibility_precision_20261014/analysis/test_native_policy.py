"""Score/receipt fixtures only; no evolutionary RNG, simulator, or compiler calls."""

import copy
import importlib.util
import json
from pathlib import Path
from types import SimpleNamespace

import numpy as np
import pytest
import torch

HERE = Path(__file__).resolve().parent


def load(name, path):
    spec = importlib.util.spec_from_file_location(name, path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


M = load("AB_policy_analysis", HERE / "analyze.py")
N = load("AB_policy_native", HERE / "native_audit.py")
torch.set_num_threads(1)


def setting(background, policy, seed):
    return dict(
        background=background,
        policy=policy,
        seed=seed,
        generations=4 if policy == "depth" else 1,
        initial_lives=3 if policy == "depth" else 12,
        recheck_lives=4 if policy == "depth" else 16,
    )


def seed_fixture():
    # These are completed Z identifiers used only as deterministic unit-test data.
    old = M.read(HERE / "fixtures/Z_seed_audit.json")
    paired = {"D90": 53220, "L92": 53221}
    p = dict(
        runs=M.RUNS,
        paired_native_seeds=paired,
        run_settings={r: setting(*r.split("_"), paired[r.split("_")[0]]) for r in M.RUNS},
        confirmation={"seeds": old["confirmation_seeds"]},
    )
    ids = {r: M.planned_ids(p["run_settings"][r]) for r in M.RUNS}
    reg = dict(runs=M.RUNS, paired_native_seeds=paired, confirmation_seeds=p["confirmation"]["seeds"])
    audit = dict(
        paired_native_seeds=paired,
        confirmation_seeds=p["confirmation"]["seeds"],
        run_life_seeds=ids,
        intentional_overlap={b: sorted(set(ids[b + "_depth"]) & set(ids[b + "_precision"])) for b in paired},
    )
    return p, reg, audit


def test_independent_hash_matches_every_retained_Z_native_ID():
    old = M.read(HERE / "fixtures/Z_seed_audit.json")
    for seed in (53220, 53221):
        assert M.planned_ids(setting("historical", "depth", seed)) == old["run_life_seeds"][str(seed)]


def test_exact_policy_sharing_and_calls():
    p, reg, audit = seed_fixture()
    M.verify_seeds(p, reg, audit)
    assert [len(x) for x in audit["run_life_seeds"].values()] == [64, 48, 64, 48]
    assert all(len(x) == 27 for x in audit["intentional_overlap"].values())
    assert len(set().union(*map(set, audit["run_life_seeds"].values()))) == 170
    assert [
        s["generations"] * (256 * s["initial_lives"] + 64 * s["recheck_lives"]) for s in p["run_settings"].values()
    ] == [4096] * 4


@pytest.mark.parametrize("kind", ["recheck_offset", "unlisted_overlap", "cross_background", "confirmation", "golden"])
def test_seed_audit_corruption(kind):
    p, reg, audit = seed_fixture()
    if kind == "recheck_offset":
        audit["run_life_seeds"]["D90_precision"][12] += 1
    elif kind == "unlisted_overlap":
        audit["intentional_overlap"]["D90"].pop()
    elif kind == "cross_background":
        p["paired_native_seeds"]["L92"] = p["paired_native_seeds"]["D90"]
    else:
        p["confirmation"]["seeds"] = list(p["confirmation"]["seeds"])
        p["confirmation"]["seeds"][0] = 11 if kind == "golden" else audit["run_life_seeds"]["D90_depth"][0]
    with pytest.raises(ValueError):
        M.verify_seeds(p, reg, audit)


@pytest.mark.parametrize("initial,extra", [(3, 4), (12, 16)])
def test_saved_scores_audit_both_weightings(initial, extra):
    # First Z generation supplies saved scores/ancestry; 12+16 is explicitly a score-only synthetic fixture.
    lines = [json.loads(x) for x in (HERE / "fixtures/Z_D90_lineage.jsonl").read_text().splitlines()]
    curves = [json.loads(x) for x in (HERE / "fixtures/Z_D90_curves.jsonl").read_text().splitlines()]
    lines, curves = N.selection_view(lines[:2], curves[:1], 1024)
    lines[1]["seeds"] = [M.native_seed(53220, 1, 0, j) for j in range(initial)]
    lines[1]["recheck"]["seeds"] = [M.native_seed(53220, 1, 0, j) for j in range(initial, initial + extra)]
    state = dict(
        ids=torch.tensor(lines[1]["survivors"]), fitness=torch.tensor(lines[1]["fitness"], dtype=torch.float64)
    )
    L = load("AB_selection_test", HERE / "helpers/selection.py")
    fake_spec = SimpleNamespace(
        hash64=lambda seed, stream, index, life: M.native_seed(seed, stream - 0x4C494645, index, life)
    )
    r = L.audit_lineage(lines, curves, state, 53220, fake_spec, initial, extra)
    assert r["sexual_offspring"] == 224 and r["initial_mutated_copies"] == 31
    lines[1]["fitness"][0] += 0.1
    with pytest.raises(ValueError, match="pooled"):
        L.audit_lineage(lines, curves, state, 53220, fake_spec, initial, extra)


def test_first_cohort_reconstructs_all256_rows_and_detects_change():
    # Dummy numeric arrays and a one-unit layout are not biological genotypes or generated candidates.
    initial = np.arange(32 * 875, dtype=np.float32).reshape(32, 875)
    layout = SimpleNamespace(n_units=1, unit_of=torch.zeros(875, dtype=torch.int64), silence=lambda x: x)

    def point(_, parent, operations):
        result = parent.clone()
        result[0] += operations["mut"][0]
        return result

    helper = SimpleNamespace(point_mutation=point)
    children = [
        dict(id=i, pa=i % 32, pb=(i + 1) % 32, mask=i % 2, ops={"mut": [0.125]}, fitness=99, kept=False)
        for i in range(32, 256)
    ]
    a = N.first_cohort(layout, initial, children, helper)
    assert a["candidate_shape"] == [256, 875] and len(a["row_raw_sha256"]) == 256
    other = copy.deepcopy(children)
    other[0]["fitness"], other[0]["kept"] = -99, True
    assert N.first_cohort(layout, initial, other, helper) == a
    other[-1]["ops"]["mut"][0] = 0.25
    b = N.first_cohort(layout, initial, other, helper)
    assert b["row_raw_sha256"][:-1] == a["row_raw_sha256"][:-1]
    assert b["row_raw_sha256"][-1] != a["row_raw_sha256"][-1]
    assert b["all256_raw_sha256"] != a["all256_raw_sha256"]


def test_helpers_original_preserved_and_parameterization_narrow():
    original = (HERE / "helpers/selection_Z_original.py.txt").read_text()
    expected = original.replace(
        "def audit_lineage(lines, curves, state, seed, spec):",
        "def audit_lineage(lines, curves, state, seed, spec, initial_lives=3, recheck_lives=4):",
    )
    expected = expected.replace(
        'for j in range(3)], "initial seeds")', 'for j in range(initial_lives)], "initial seeds")'
    )
    expected = expected.replace(
        'for j in range(3, 7)], "recheck seeds")',
        'for j in range(initial_lives, initial_lives + recheck_lives)], "recheck seeds")',
    )
    expected = expected.replace(
        "pooled = (3 * base + 4 * extra) / 7",
        "pooled = (initial_lives * base + recheck_lives * extra) / (initial_lives + recheck_lives)",
    )
    expected = expected.replace(
        "selected fitness differs from the seven-life pooled scores",
        "selected fitness differs from the registered pooled scores",
    )
    assert (HERE / "helpers/selection.py").read_text() == expected
    assert M.sha(HERE / "helpers/selection.py") == N.HELPERS["L"][1]
    assert M.sha(HERE / "helpers/genetics.py") == N.HELPERS["G"][1]
    assert M.sha(HERE / "offline_accounting.py") == "7d61ecfbc8c3ae96f3808655901a04c3542c6418fea5d6cc5f696afe22836421"
