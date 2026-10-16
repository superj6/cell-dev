"""ABI6 replays immutable ABI3--5 truth; no expected values are regenerated.

Execution inventory: 28 one-life C backend calls (14 full and 14 fast), all using
existing engineering seeds/bodies. Collection only reads the two archived JSON files.
"""
import hashlib
import json
from pathlib import Path

import numpy as np
import pytest

from src.life import build, spec

ROOT = Path(__file__).resolve().parents[1]
TRUTH = (
    ("results/abi5_delayed_match_20261015/validation/truth_conservation_fix/truth.json",
     "7c0a040ec715fdf65ed51a285f48c46a1c9b1440f6f1774fab3d819462c844db", None),
    ("results/abi4_visibility_20261014/final_truth/truth.json",
     "bdd69384d4926b67a8e163dc68c616b7f4968b5df15bd90a1d7a42ce68c4f737",
     {"body0_neutral_abi3", "body0_flash_55040000", "body7_renewal_55040000",
      "shifted_renewal_open", "flash_at_end"}),
)


def _fixtures():
    cases = []
    for relative, digest, names in TRUTH:
        data = (ROOT / relative).read_bytes()
        assert hashlib.sha256(data).hexdigest() == digest, "historical truth changed"
        document = json.loads(data)
        assert document["status"] == "complete"
        selected = [case for case in document["cases"] if names is None or case["name"] in names]
        assert names is None or {case["name"] for case in selected} == names
        cases.extend((document, case) for case in selected)
    return cases


CASES = _fixtures()


def _inputs(case, abi):
    body = case["body"]
    defaults = spec.world(body["preset"])
    fields = {key: int(value) if isinstance(getattr(defaults, key), int) else value
              for key, value in body["world"].items()}
    world = spec.world(body["preset"], **fields)
    if body["mode"] == "grn":
        tables = dict(genomes=np.asarray(body["genome"], dtype=np.float64)[None])
    else:
        tables = dict(programs=np.asarray(body["program"], dtype=np.float64))
    return world, dict(**tables, init=body.get("cells"), abi=abi, threads=1)


def _bits_equal(actual, expected):
    expected = np.asarray(expected, dtype=actual.dtype).reshape(actual.shape)
    assert actual.tobytes() == expected.tobytes()


def _assert_logs(result, case):
    times, uids = result.spikes(0)
    _bits_equal(times, case["raster_t"])
    _bits_equal(uids, [int(value, 16) for value in case["raster_uid"]])
    assert int(result.raster_n[0]) == case["raster_total"]
    fate_i, fate_f = result.fates(0)
    _bits_equal(fate_i, case["fate_i"])
    _bits_equal(fate_f, case["fate_f"])
    assert int(result.fate_n[0]) == len(case["fate_i"])


@pytest.mark.parametrize("document,case", CASES, ids=[case["name"] for _, case in CASES])
def test_old_callers_replay_frozen_truth_under_abi6_kernel(document, case):
    abi = getattr(spec, f"V{case['body']['abi']}")
    world, arguments = _inputs(case, abi)
    _bits_equal(abi.pack_world(world), case["body"]["world_vec"])
    full = build.run(world, [case["seed"]], **arguments,
                     raster_cap=document["raster_cap"], fate_cap=document["fate_cap"])
    # Log capacities are observable through overflow status, even in fast mode.
    fast = build.run(world, [case["seed"]], **arguments, fast=True,
                     raster_cap=document["raster_cap"], fate_cap=document["fate_cap"])
    assert full.ledger.shape == fast.ledger.shape == (1, abi.LEDGER_SIZE)
    assert full.hashes.shape == fast.hashes.shape == (1, abi.HASH_SIZE)
    _bits_equal(full.ledger[0], case["ledger"])
    _bits_equal(full.hashes[0], [int(value, 16) for value in case["hashes"]])
    _bits_equal(fast.ledger, full.ledger)
    assert np.all(fast.hashes == spec.HASH_INIT)
    _assert_logs(full, case)
    _assert_logs(fast, case)


def test_neutral_v6_adds_only_zero_close_ledger_folds_to_v5_truth():
    document, case = CASES[0]
    assert case["name"] == "reflex_preset_0"
    world, arguments = _inputs(case, spec.V6)
    full = build.run(world, [case["seed"]], **arguments,
                     raster_cap=document["raster_cap"], fate_cap=document["fate_cap"])
    fast = build.run(world, [case["seed"]], **arguments, fast=True,
                     raster_cap=document["raster_cap"], fate_cap=document["fate_cap"])
    _bits_equal(full.ledger[0, :70], case["ledger"])
    _bits_equal(full.ledger[0, 70:], np.zeros(37))
    expected_hashes = [int(value, 16) for value in case["hashes"]]
    for _ in range(37):
        expected_hashes[0] = spec.splitmix64(expected_hashes[0])
    _bits_equal(full.hashes[0], expected_hashes)
    _bits_equal(fast.ledger, full.ledger)
    assert np.all(fast.hashes == spec.HASH_INIT)
    _assert_logs(full, case)
    _assert_logs(fast, case)


def test_abi6_layout_keeps_legacy_default_and_cellular_interface():
    assert spec.CURRENT is spec.V2
    assert (spec.V6.WORLD_SIZE, spec.V6.LEDGER_SIZE, spec.V6.HASH_SIZE) == (82, 107, 5)
    assert spec.V6.WORLD_KEYS[:77] == spec.V5.WORLD_KEYS
    assert spec.V6.LEDGER[:70] == spec.V5.LEDGER
    for field in ("GENOME_FIELDS", "GENOME_SIZE", "GENOME_SLICES", "PROGRAM_SIZE", "INPUTS", "NIN", "KNOBS"):
        assert getattr(spec.V6, field) == getattr(spec.V5, field)
    assert [abi.WORLD_SIZE for abi in (spec.V2, spec.V3, spec.V4, spec.V5)] == [41, 66, 70, 77]
    assert [abi.LEDGER_SIZE for abi in (spec.V2, spec.V3, spec.V4, spec.V5)] == [35, 57, 58, 70]
    patch_world = spec.world("catch_resource_patches_l4")
    for abi in (spec.V2, spec.V3, spec.V4, spec.V5):
        with pytest.raises(NotImplementedError):
            abi.pack_world(patch_world)
