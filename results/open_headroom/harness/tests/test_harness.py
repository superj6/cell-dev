"""Quick exactness checks for a (re)built controller kernel (about 20 s):
    cd /home/jgon/project/ml/cell-dev && PYTHONPATH=.:<harness>:<harness>/tests .venv/bin/python -m pytest -q <harness>/tests/test_harness.py
Set CK_LIB=/path/to/your_ckernel.so (full build, with hashes) to check your own library."""
import os
import numpy as np
import pytest
import harness as H
import replay as RP

LIB = os.environ.get("CK_LIB")  # None: this directory's full build
FP = H.footprint("hollow3")


@pytest.mark.parametrize("world", ["base1", "pool", "blink20", "flip_mid", "decoy_lite", "wound25"])
def test_null_controller_streams_equal_inert_body(world):
    sd = H.seeds(8, 0)
    a = H.ctl_run(H.NULL, [], FP, world, sd, threads=2, fast=False, charge="none", lib=LIB)
    b = H.tissue_run(FP.inert_body(), world, sd, threads=2, fast=False, lib=LIB)
    assert np.array_equal(a.hashes[:, 4], b.hashes[:, 4])
    for c in ("rec_cand", "rec_accept", "respawns", "dist_sum", "zone_samples", "kills", "n_end"):
        assert np.array_equal(a[c], b[c]), c
    assert np.allclose(a["live_time"], b["live_time"], rtol=1e-12)


@pytest.mark.parametrize("world", ["base1", "pool", "blink20", "flip_mid", "lead", "decoy_lite", "wound25"])
def test_replay_reproduces_tissue_world(world):
    eq, _, _ = RP.run(world, n=4, block=0, threads=2)
    assert all(eq.values()), [k for k, v in eq.items() if not v]


@pytest.mark.parametrize("cid", [H.C0, H.C1, H.C2, H.C4])
def test_deterministic_and_thread_independent(cid):
    sd = H.seeds(6, 0)
    p = H.bayes_params("pool") if cid == H.C4 else H.default_params(cid)
    a = H.ctl_run(cid, p, FP, "pool", sd, threads=3, lib=LIB, fast=False)
    b = H.ctl_run(cid, p, FP, "pool", sd, threads=1, lib=LIB, fast=False)
    assert np.array_equal(a.ledger, b.ledger) and np.array_equal(a.hashes, b.hashes)


def test_latency_is_enforced():
    # C0 with latency 3: no stroke can precede the first ping + 3
    sd = H.seeds(4, 0)
    r = H.ctl_run(H.C0, H.default_params(H.C0), FP, "base1", sd, threads=2, latency=3.0, raster_cap=50000,
                  fate_cap=2000, fast=False, charge="none", lib=LIB)
    for i in range(len(sd)):
        t, u = r.spikes(i)
        assert len(t) == 0 or t.min() >= 3.0 + 0.5  # first ping is delivered no earlier than t0 + d_min
    assert np.all(r.latency == 3.0)


def test_information_matched_cannot_read_truth():
    # C1 run as information-matched: ctl_truth returns 0, so it never acts
    sd = H.seeds(4, 0)
    r = H.ctl_run(H.C1, H.default_params(H.C1), FP, "base1", sd, threads=2, privileged=False, lib=LIB)
    assert r.diag[:, 2].sum() == 0 and r["clicks"].sum() == 0
