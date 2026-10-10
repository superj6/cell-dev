"""Prototype of a task family drawn per life (POST_PILOT_CALLS L1) as a subclass of LifeEvaluator; no repo edit.

Config (new section):
  family:
    purposes: [gen, founders, valid]        # where lives draw a member (heldout keeps its override list)
    members:                                # world overrides, a draw weight and a FIXED scale per member
      - {name: base,  weight: 2, scale: 8.7, world: {}}
      - {name: wound, weight: 1, scale: 4.9, world: {kill_t: 512.0, kill_frac: 0.25}}
Each life of draw (purpose, index) gets member m = the weighted bin of draw(run seed, FAM_STREAM, purpose, index,
life): keyed like the life seed, so every genome of a generation (and its recheck shortlist) shares the same worlds
(CRN). The member id rides in World.name ("family:<m>"), so recheck_draw's slicing keeps seeds, worlds and members
aligned. Selection F of a life = kernel F (after the extinct charge and the invalid floor) / scale[m]: linear, so
every cell cost stays linear in each world; under CRN an additive per-world offset would cancel in ranking anyway."""
from __future__ import annotations

import sys
from dataclasses import replace

import numpy as np

sys.path.insert(0, str(__import__("pathlib").Path(__file__).resolve().parents[3]))
from src.life import evaluate as E, spec  # noqa: E402

FAM_STREAM = 0x46414D31  # "FAM1"
PREFIX = "family:"


class FamilyEvaluator(E.LifeEvaluator):
    def __init__(self, cfg, layout):
        super().__init__(cfg, layout)
        fam = E._plain(cfg.get("family"))
        self.members = [dict(m) for m in fam.get("members", [])]
        self.fam_purposes = tuple(fam.get("purposes", ("gen", "founders", "valid")))
        w = np.array([float(m.get("weight", 1.0)) for m in self.members])
        self.cum = np.cumsum(w) / w.sum() if len(w) else w
        self.scales = np.array([float(m["scale"]) for m in self.members])
        if np.any(self.scales <= 0):
            raise ValueError("family scales must be positive constants measured once per world")
        for m in self.members:  # every member must make a valid world at every selection length
            for T in self.T_choices or (self.T,):
                self.world(T, **{k: float(v) for k, v in (m.get("world") or {}).items()})

    def member_of(self, purpose: str, index: int, life: int) -> int:
        u = spec.draw(self.seed, FAM_STREAM, E.PURPOSES[purpose], int(index), int(life))
        return min(int(np.searchsorted(self.cum, u, side="right")), len(self.members) - 1)

    def draw(self, purpose, index, lives=None, T=None, overrides=None, envelope=None) -> E.LifeDraw:
        d = super().draw(purpose, index, lives=lives, T=T, overrides=overrides, envelope=envelope)
        if not self.members or overrides or purpose not in self.fam_purposes:
            return d
        worlds = []
        for life, w in enumerate(d.worlds):
            m = self.member_of(purpose, index, life)
            wm = replace(w, name=f"{PREFIX}{m}", **{k: float(v) for k, v in (self.members[m].get("world") or {}).items()})
            self.abi.validate_world(wm)
            worlds.append(wm)
        return E.LifeDraw(d.seeds, tuple(worlds))

    def scale_of(self, draw) -> np.ndarray:
        return np.array([self.scales[int(w.name[len(PREFIX):])] if w.name.startswith(PREFIX) else 1.0
                         for w in draw.worlds])

    def columns(self, res, B, draw):
        col = super().columns(res, B, draw)
        col["F_raw"] = col["F"]
        col["F"] = col["F"] / self.scale_of(draw)[None, :]
        col["member"] = np.broadcast_to(np.array([int(w.name[len(PREFIX):]) if w.name.startswith(PREFIX) else -1
                                                  for w in draw.worlds])[None, :], col["F"].shape)
        return col

    def per_member(self, params, purpose: str, index: int, lives_per_member: int) -> dict:
        """Report-only: raw and normalised F of each genome in each member world (stratified lives)."""
        out = {}
        for m, mem in enumerate(self.members):
            d = super().draw(purpose, index, lives=lives_per_member,
                             overrides=[{k: float(v) for k, v in (mem.get("world") or {}).items()}])
            ev = E.LifeEvaluator.__call__(self, params, d)
            out[mem.get("name", str(m))] = dict(F_raw=ev.fitness.tolist(),
                                                F_norm=(ev.fitness / float(self.scales[m])).tolist())
        return out


def install() -> None:
    """Make src.evolve.setup build a FamilyEvaluator (setup imports LifeEvaluator from src.life.evaluate)."""
    E.LifeEvaluator = FamilyEvaluator
