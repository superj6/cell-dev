"""Deterministic, simulation-free selection on supplied life arrays and tie permutations.

No simulator, genome, torch or random-number API is imported. The adapter supplies the
native tie_gen permutation for each ranking call; this module consumes no RNG stream.
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import Sequence

import numpy as np

DOMAINS = ("patch", "pool", "persistent")
PATTERN = (0, 1, 0, 2) * 8
AO_REFERENCE = (19.046875, 16.029296875, 5.919921875)
OBJECTIVES = (*DOMAINS, "production_F")


def _indices(value: Sequence[int] | None, n: int, name: str) -> np.ndarray:
    if value is None:
        return np.arange(n, dtype=np.int64)
    result = np.asarray(value)
    if (result.shape != (n,) or result.dtype.kind not in "iu"
            or not np.array_equal(np.sort(result), np.arange(n))):
        raise ValueError(f"{name} must be a permutation of 0..{n - 1}")
    return result.astype(np.int64, copy=True)


def _matrix(value, name: str, width: int | None = None) -> np.ndarray:
    result = np.asarray(value, dtype=np.float64)
    if (result.ndim != 2 or min(result.shape) == 0
            or (width is not None and result.shape[1] != width) or not np.isfinite(result).all()):
        raise ValueError(f"{name} must be a nonempty finite matrix" + (f" with {width} columns" if width else ""))
    return result.copy()


def objective_vectors(captures, production_f, domains: Sequence[int] = PATTERN) -> np.ndarray:
    """Three within-domain capture means and the ordinary, life-weighted F mean.

    production_f must already include production extinction/invalid-life accounting.
    This module neither reprices lives nor silently excludes guards or extinctions.
    """
    cap = _matrix(captures, "captures")
    fit = _matrix(production_f, "production_f")
    labels = np.asarray(domains)
    if cap.shape != fit.shape or np.any(cap < 0) or not np.equal(cap, np.floor(cap)).all():
        raise ValueError("captures must be nonnegative integer counts matching production_f")
    if (labels.shape != (cap.shape[1],) or labels.dtype.kind not in "iu"
            or set(labels.tolist()) != {0, 1, 2}):
        raise ValueError("each life needs one valid domain label and all three domains must occur")
    result = np.column_stack([cap[:, labels == d].mean(axis=1) for d in range(3)] + [fit.mean(axis=1)])
    if not np.isfinite(result).all():
        raise ValueError("objective mean overflow")
    return result


def _front_ranks(values: np.ndarray) -> np.ndarray:
    # Row i dominates column j iff it is at least as good everywhere and better somewhere.
    dominates = (values[:, None, :] >= values[None, :, :]).all(axis=2)
    dominates &= (values[:, None, :] > values[None, :, :]).any(axis=2)
    remaining = dominates.sum(axis=0)
    ranks = np.full(len(values), -1, dtype=np.int64)
    front = np.flatnonzero(remaining == 0)
    level = 0
    while front.size:
        ranks[front] = level
        remaining -= dominates[front].sum(axis=0)
        front = np.flatnonzero((ranks < 0) & (remaining == 0))
        level += 1
    if np.any(ranks < 0):
        raise AssertionError("strict Pareto dominance must be acyclic")
    return ranks


def _crowding(values: np.ndarray, ranks: np.ndarray) -> np.ndarray:
    """Front-normalized crowding, treating equal coordinates as one value group.

    Zero-range coordinates contribute zero, including for singleton/all-equal fronts.
    Each nonconstant coordinate gives every minimum/maximum point infinite distance.
    Each interior equal-value group gets the same next-distinct minus prior-distinct
    gap divided by that front's coordinate range. Exact duplicate objective vectors
    therefore have equal ranks and crowding; supplied tie order alone distinguishes them.
    """
    distance = np.zeros(len(values), dtype=np.float64)
    for rank in range(int(ranks.max()) + 1):
        members = np.flatnonzero(ranks == rank)
        for column in range(values.shape[1]):
            levels, inverse = np.unique(values[members, column], return_inverse=True)
            if levels.size == 1:
                continue
            # Scaling before subtraction avoids overflow for finite extreme signed F.
            scale = max(abs(float(levels[0])), abs(float(levels[-1])))
            scaled = levels / scale
            span = scaled[-1] - scaled[0]
            contribution = np.full(levels.size, np.inf)
            contribution[1:-1] = (scaled[2:] - scaled[:-2]) / span
            distance[members] += contribution[inverse]
    return distance


@dataclass(frozen=True)
class Ranking:
    objectives: np.ndarray
    ranks: np.ndarray
    crowding: np.ndarray
    order: np.ndarray
    tie_order: np.ndarray

    def audit(self) -> dict:
        """Strict-JSON-safe data; null crowding is an explicitly marked infinite endpoint."""
        return {
            "objective_names": list(OBJECTIVES), "objectives": self.objectives.tolist(),
            "ranks": self.ranks.tolist(), "crowding": [None if np.isinf(v) else float(v) for v in self.crowding],
            "crowding_infinite": np.isinf(self.crowding).tolist(),
            "order": self.order.tolist(), "tie_order": self.tie_order.tolist(),
        }


def rank_objectives(objectives, tie_order: Sequence[int] | None = None) -> Ranking:
    """All objectives maximize; rank ascending, crowding descending, supplied tie priority.

    Infinite-distance endpoints share equal priority and are capped by tie_order when
    there are more boundary points than places. No unrecorded secondary objective or
    candidate-position preference overrides the supplied tie permutation.
    """
    values = _matrix(objectives, "objectives", 4)
    ties = _indices(tie_order, len(values), "tie_order")
    priority = np.empty(len(values), dtype=np.int64)
    priority[ties] = np.arange(len(values))
    ranks = _front_ranks(values)
    crowding = _crowding(values, ranks)
    if np.isnan(crowding).any():
        raise ValueError("crowding normalization produced NaN")
    order = np.lexsort((priority, -crowding, ranks))
    return Ranking(values, ranks, crowding, order, ties)


def rank_mean(production_f, tie_order: Sequence[int] | None = None) -> np.ndarray:
    """Native stable descending scalar-F ordering with a supplied, already drawn permutation."""
    values = np.asarray(production_f, dtype=np.float64)
    if values.ndim != 1 or not len(values) or not np.isfinite(values).all():
        raise ValueError("production_f must be a nonempty finite vector")
    ties = _indices(tie_order, len(values), "tie_order")
    return ties[np.argsort(-values[ties], kind="stable")]


@dataclass(frozen=True)
class StageSelection:
    ranking: Ranking
    candidate_indices: np.ndarray
    selected: np.ndarray
    lives_per_candidate: int

    def audit(self) -> dict:
        return {**self.ranking.audit(), "candidate_indices": self.candidate_indices.tolist(),
                "selected": self.selected.tolist(), "lives_per_candidate": self.lives_per_candidate}


def select_shortlist(captures, production_f, tie_order: Sequence[int] | None = None) -> StageSelection:
    """The 256 candidates' base32 lives select exactly 64 for recheck."""
    cap = _matrix(captures, "base captures", 32)
    fit = _matrix(production_f, "base production_f", 32)
    if cap.shape != (256, 32) or fit.shape != cap.shape:
        raise ValueError("shortlist requires exactly 256 candidates with32 lives each")
    ranking = rank_objectives(objective_vectors(cap, fit), tie_order)
    return StageSelection(ranking, np.arange(256), ranking.order[:64].copy(), 32)


def select_survivors(base_captures, base_production_f, shortlist: Sequence[int], recheck_captures,
                     recheck_production_f, tie_order: Sequence[int] | None = None) -> StageSelection:
    """Recheck rows must follow shortlist order; concatenate base32 + new32 before ranking.

    tie_order addresses the 64 local shortlist rows. The selected result contains their
    original 256-row indices; ranking.order retains the full 64-row local ordering.
    """
    base_cap = _matrix(base_captures, "base captures", 32)
    base_fit = _matrix(base_production_f, "base production_f", 32)
    new_cap = _matrix(recheck_captures, "recheck captures", 32)
    new_fit = _matrix(recheck_production_f, "recheck production_f", 32)
    short = np.asarray(shortlist)
    if (base_cap.shape != (256, 32) or base_fit.shape != base_cap.shape
            or new_cap.shape != (64, 32) or new_fit.shape != new_cap.shape
            or short.shape != (64,) or short.dtype.kind not in "iu"
            or len(np.unique(short)) != 64 or np.any(short < 0) or np.any(short >= 256)):
        raise ValueError("recheck requires 64 unique base indices and exact 256x32 / 64x32 arrays")
    # Validate the entire retained base batch, including rows outside this shortlist.
    objective_vectors(base_cap, base_fit)
    pooled_cap = np.concatenate((base_cap[short], new_cap), axis=1)
    pooled_fit = np.concatenate((base_fit[short], new_fit), axis=1)
    ranking = rank_objectives(objective_vectors(pooled_cap, pooled_fit, PATTERN * 2), tie_order)
    return StageSelection(ranking, short.copy(), short[ranking.order[:32]].copy(), 64)


@dataclass(frozen=True)
class EndpointSelection:
    objectives: np.ndarray
    fractions: np.ndarray
    worst_fraction: np.ndarray
    order: np.ndarray
    tie_order: np.ndarray
    candidate_ids: np.ndarray

    @property
    def selected(self) -> int:
        return int(self.order[0])

    def audit(self) -> dict:
        return {"objective_names": list(OBJECTIVES), "objectives": self.objectives.tolist(),
                "ao_reference": list(AO_REFERENCE), "fractions": self.fractions.tolist(),
                "worst_fraction": self.worst_fraction.tolist(), "order": self.order.tolist(),
                "tie_order": self.tie_order.tolist(), "candidate_ids": self.candidate_ids.tolist(),
                "selected": self.selected, "selected_id": int(self.candidate_ids[self.selected])}


def select_endpoint(objectives, candidate_ids: Sequence[int]) -> EndpointSelection:
    """Common endpoint math for a separately supplied panel; never called by search.

    Maximize weakest AO-normalized capture mean, then aggregate ordinary F, then
    unique survivor ID ascending. No extra RNG draw, Pareto-front restriction or
    per-domain winner assembly. IDs are the existing native integer genome IDs.
    """
    values = _matrix(objectives, "survivor objectives", 4)
    if len(values) != 32 or np.any(values[:, :3] < 0):
        raise ValueError("endpoint selection requires exactly 32 survivors with nonnegative capture means")
    ids = np.asarray(candidate_ids)
    if (ids.shape != (32,) or ids.dtype.kind not in "iu" or len(np.unique(ids)) != 32
            or np.any(ids < 0) or np.any(ids > np.iinfo(np.int64).max)):
        raise ValueError("candidate_ids must contain 32 unique nonnegative int64 genome IDs")
    ids = ids.astype(np.int64, copy=True)
    ties = np.argsort(ids, kind="stable")
    priority = np.empty(32, dtype=np.int64)
    priority[ties] = np.arange(32)
    fractions = values[:, :3] / np.asarray(AO_REFERENCE)
    worst = fractions.min(axis=1)
    order = np.lexsort((priority, -values[:, 3], -worst))
    return EndpointSelection(values, fractions, worst, order, ties, ids)
