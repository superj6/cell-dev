"""src/life/probe.py: a traced life is the kernel's life (the trace checks F bitwise), the reference simulator's lateral
message lesion equals the kernel's lateral_off fork, and the chain probe tells the two hand-built SPECK bodies apart:
every receptor-started rim-motor chain of the reflex starts in the motor's own column, while the router relays some
from other columns through in-plane hops (docs/PROBE.md, "Signatures"). Short lives keep the pure-Python traces fast."""
import pandas as pd
import pytest

from src.life import probe as P

T = 128.0


@pytest.fixture(scope="module")
def traces():
    out = {}
    for name in ("reflex@hollow3", "router@ring4"):
        org, preset = P.hand(name)
        out[name] = [P.trace(org, s, preset, T=T) for s in P.SEEDS[:2]]  # check=True: raises unless F == kernel F
    return out


def test_traces_are_the_kernel_lives(traces):
    for trs in traces.values():
        for tr in trs:
            assert tr.meta["kernel_F"] == tr.F and len(tr.spikes) > 0


def test_reference_lateral_lesion_equals_the_kernel_fork():
    org, preset = P.hand("router@ring4")
    pairs = P.check_lesion_equivalence(org, preset, 32.0, P.SEEDS[:2], T=T)
    assert len(pairs) == 2 and all(a == b for a, b in pairs)


def _motor_chains(trs) -> pd.Series:
    return P.chain_summary(pd.concat([P.chains(tr) for tr in trs], ignore_index=True)).set_index("cls").loc["M"]


def test_chains_tell_the_reflex_from_the_router(traces):
    reflex, router = _motor_chains(traces["reflex@hollow3"]), _motor_chains(traces["router@ring4"])
    assert reflex.rec_other_col == 0.0 and reflex.relayed == 0.0
    assert router.rec_other_col > 0.15 and router.relayed > 0.15
