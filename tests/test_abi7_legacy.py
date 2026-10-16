"""Replay original ABI6 saved truth under explicit ABI6 and neutral ABI7 callers."""
import hashlib
import json
from pathlib import Path

import numpy as np
import pytest

from src.life import build, spec
from tests.test_abi6_legacy import _assert_logs, _bits_equal, _inputs

ROOT = Path(__file__).resolve().parents[1]
TRUTH = ROOT / "results/abi6_resource_patches_20261015/validation/truth/truth.json"
TRUTH_SHA = "6e96a9ec7a089c90349749057adb8686c508d75c97604634f7563e6d388e59ac"
assert hashlib.sha256(TRUTH.read_bytes()).hexdigest() == TRUTH_SHA
DOCUMENT = json.loads(TRUTH.read_text())


@pytest.mark.parametrize("case", DOCUMENT["cases"], ids=lambda c: c["name"])
def test_original_abi6_truth_and_neutral_v7(case):
    world, args = _inputs(case, spec.V6)
    # The original exporter retained a historical ABI3 world_vec; the named full world fields are authoritative.
    caps = dict(raster_cap=DOCUMENT["raster_cap"], fate_cap=DOCUMENT["fate_cap"])
    full = build.run(world, [case["seed"]], **args, **caps)
    fast = build.run(world, [case["seed"]], fast=True, **args, **caps)
    _bits_equal(full.ledger[0], case["ledger"])
    _bits_equal(full.hashes[0], [int(x, 16) for x in case["hashes"]])
    _bits_equal(fast.ledger, full.ledger)
    assert np.all(fast.hashes == spec.HASH_INIT)
    _assert_logs(full, case)
    _assert_logs(fast, case)
    args["abi"] = spec.V7
    neutral = build.run(world, [case["seed"]], **args, **caps)
    _bits_equal(neutral.ledger[0, :107], full.ledger[0])
    assert not neutral.ledger[0, 107:].any()
    hashes = full.hashes[0].copy()
    for _ in range(36):
        hashes[0] = spec.splitmix64(int(hashes[0]))
    _bits_equal(neutral.hashes[0], hashes)
    _assert_logs(neutral, case)


def test_frozen_abi6_truth_digest():
    assert hashlib.sha256(TRUTH.read_bytes()).hexdigest() == TRUTH_SHA
