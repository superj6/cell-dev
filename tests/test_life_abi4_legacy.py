"""Replay pre-port ABI2/3 output bytes, including their distinct fast-hash conventions."""
import hashlib
import json
from pathlib import Path

import numpy as np
import pytest

from src.life import build, spec

DATA = Path(__file__).parent / 'data/abi4_legacy'
MANIFEST = json.loads((DATA / 'manifest.json').read_text())


def test_pre_port_fixture_integrity():
    for name, digest in json.loads((DATA / 'checksums.json').read_text()).items():
        assert hashlib.sha256((DATA / name).read_bytes()).hexdigest() == digest, name
    assert MANIFEST['validation_lives'] == 32


@pytest.mark.parametrize('case', MANIFEST['cases'], ids=lambda c: c['file'])
def test_pre_port_caller_outputs_are_byte_identical(case):
    abi = {2: spec.V2, 3: spec.V3}[case['abi']]
    with np.load(DATA / case['inputs'], allow_pickle=False) as source:
        kwargs = {name: source[name] for name in source.files}
    if 'init' in kwargs:
        kwargs['init'] = kwargs['init'].tolist()
    actual = build.run(spec.World(**case['world']), case['seeds'], abi=abi, fast=case['fast'],
                       threads=1, raster_cap=512, fate_cap=128, **kwargs)
    with np.load(DATA / case['file'], allow_pickle=False) as expected:
        for name in expected.files:
            value = getattr(actual, name)
            assert value.dtype == expected[name].dtype, name
            assert value.shape == expected[name].shape, name
            assert value.tobytes() == expected[name].tobytes(), name
