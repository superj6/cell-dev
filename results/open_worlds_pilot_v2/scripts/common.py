"""Shared helpers for looking inside pilot v2 bodies (eco worlds, ABI 8)."""
import json
import sys
from dataclasses import replace
from pathlib import Path

import numpy as np

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))
from src.genome import LifeLayout, make_dims  # noqa: E402
from src.life import build, ecology, probe, spec  # noqa: E402

RUNS = ROOT / "outputs/open_worlds_pilot_v2/runs"
V8 = spec.V8


class Org:
    """A GRN body with a raw ABI 8 genome, for probe.trace (world given directly, not by preset)."""

    def __init__(self, name, genome):
        self.name, self.genome, self.flags = name, np.asarray(genome, np.float32).reshape(-1), 0

    def world(self, w, **overrides):
        return replace(w, **overrides) if overrides else w


probe._world = lambda org, preset, **w: org.world(preset, **w)


def grid_genome(run, gen, world, cell):
    d = json.load(open(RUNS / run / "populations" / f"g{gen:06d}.json"))
    lay = LifeLayout(make_dims(d["dims"]))
    gr = d["elites"][world]
    i = gr["cells"].index(cell[0] * 4 + cell[1])
    return Org(f"{run}-g{gen}-{world}{cell}", lay.from_dict(gr["genomes"][i]).numpy())


def top_genome(run, gen, rank=0):
    d = json.load(open(RUNS / run / "populations" / f"g{gen:06d}.json"))
    lay = LifeLayout(make_dims(d["dims"]))
    i = int(np.argsort(-np.array(d["fitness"]))[rank])
    return Org(f"{run}-g{gen}-top{rank}", lay.from_dict(d["genomes"][i]).numpy())


def kernel(org, worlds, seeds, **kw):
    gt = V8.pack_genomes(org.genome[None], "hexprism")
    return build.run(worlds, seeds, genomes=gt, abi=V8, fast=True, **kw)


# eco lives: the observer's "target" is the nearest edible source with stock (nan if none); receptor logging of the
# old single-blob signal share is skipped
_obs0, _rc0 = probe._TAcct._observed_target, probe._TAcct._rcand


def _observed_target(self, t):
    if not getattr(self.life, "eco", False):
        return _obs0(self, t)
    X, Y = self.dot_at(t)
    best = (np.nan, np.nan, np.inf)
    for S in self.src:
        if S["stock"] > 0 and S["value"] > 0:
            d = (S["x"] - X) ** 2 + (S["y"] - Y) ** 2
            if d < best[2]:
                best = (S["x"], S["y"], d)
    return best[0], best[1]


def _rcand(self, t, site, uid, j, counted):
    if getattr(self.life, "eco", False):
        return _rc0.__wrapped__(self, t, site, uid, j, counted) if hasattr(_rc0, "__wrapped__") else \
            probe._R._Accountant._rcand(self, t, site, uid, j, counted)
    return _rc0(self, t, site, uid, j, counted)


probe._TAcct._observed_target = _observed_target
probe._TAcct._rcand = _rcand


# eco click outcomes (world-event word 43): 0 miss, 1 eat, 2 toxin, 3 pick, 4 deliver, 5 prey, 6 harvest, 7 plant, 8 trample
ECO_OUTCOMES = {0: "miss", 1: "eat", 2: "toxin", 3: "pick", 4: "deliver", 5: "prey", 6: "harvest", 7: "plant",
                8: "trample"}
_fw0 = probe._TAcct._fold_world


def _fold_world(self, words):
    if getattr(self.life, "eco", False) and words[0] == 43:
        if not hasattr(self, "eco_clicks"):
            self.eco_clicks = []
        f = probe._f
        self.eco_clicks.append((f(words[1]), ECO_OUTCOMES[int(words[2])], int(words[3]), f(words[5]), f(words[6])))
    return _fw0(self, words)


probe._TAcct._fold_world = _fold_world
_trace0 = probe.trace


def trace(org, seed, w, **kw):
    """probe.trace plus ``tr.eco_clicks`` (t, outcome, index, X, Y) for eco lives."""
    holder = {}
    life0 = probe._life

    def life(*a, **k):
        holder["life"] = life0(*a, **k)
        return holder["life"]

    probe._life = life
    try:
        tr = _trace0(org, seed, w, abi=V8, **kw)
    finally:
        probe._life = life0
    import pandas as pd
    tr.eco_clicks = pd.DataFrame(getattr(holder["life"].acct, "eco_clicks", []), columns=["t", "outcome", "idx", "X", "Y"])
    return tr
