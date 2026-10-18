"""CPU selection on supplied objectives; all columns maximize and inputs remain unchanged.

Randomness comes only from the caller's CPU ``torch.Generator``. Epsilon lexicase
uses one population MAD per task, a fresh task permutation for each pick, the best
score among remaining candidates, and inclusive epsilon filtering. This is the
semi-dynamic variant described by La Cava et al., Evol. Comput. 27(3), 2019:
https://pmc.ncbi.nlm.nih.gov/articles/PMC9453780/

These functions do not aggregate lives, assign prices, or handle invalid organisms.
The caller supplies finite objective vectors after its declared accounting rules.
"""
from __future__ import annotations

from dataclasses import dataclass
from numbers import Integral

import numpy as np
import torch


def _array(value) -> np.ndarray:
    if isinstance(value, torch.Tensor):
        if value.device.type != "cpu":
            raise ValueError("selection requires CPU arrays")
        value = value.detach().numpy()
    result = np.asarray(value)
    if result.dtype.kind not in "fiu":
        raise ValueError("selection requires real numeric arrays")
    return result


def _objectives(value) -> np.ndarray:
    result = np.asarray(_array(value), dtype=np.float64)
    if result.ndim != 2 or min(result.shape) == 0 or not np.isfinite(result).all():
        raise ValueError("objectives must be a nonempty finite [candidates, tasks] matrix")
    return result.copy()


def _generator(generator: torch.Generator) -> None:
    if not isinstance(generator, torch.Generator) or generator.device.type != "cpu":
        raise ValueError("supply a CPU torch.Generator")


def epsilon_lexicase(objectives, k: int, *, generator: torch.Generator,
                     replace: bool = True, epsilon_multiplier: float = 1.0) -> torch.Tensor:
    """Pick ``k`` row indices, with replacement for mating or without it for retention.

    Epsilon is ``multiplier * median(abs(x - median(x)))`` for each task over the
    entire supplied population. Even-size medians use the two central values'
    midpoint, not torch's lower median. Epsilon stays fixed throughout this call,
    including when ``replace=False`` removes winners. Zero multiplier gives exact
    lexicase. For each pick, shuffle all tasks and retain scores >= best - epsilon;
    stop at one candidate or choose uniformly among survivors after the last task.

    Each nontrivial pick consumes one task randperm and, only if needed, one final
    randint tie draw. A sole available candidate and k=0 consume no random draws.
    Return a CPU int64 tensor in selection order. Invalid arguments consume no RNG.
    """
    values = _objectives(objectives)
    _generator(generator)
    if not isinstance(k, Integral) or isinstance(k, bool) or k < 0 or (not replace and k > len(values)):
        raise ValueError("k must be nonnegative and at most population size without replacement")
    if not isinstance(replace, bool):
        raise ValueError("replace must be boolean")
    multiplier = float(epsilon_multiplier)
    if not np.isfinite(multiplier) or multiplier < 0:
        raise ValueError("epsilon_multiplier must be finite and nonnegative")
    with np.errstate(over="ignore", invalid="ignore"):
        median = np.median(values, axis=0)
        epsilon = multiplier * np.median(np.abs(values - median), axis=0)
    if not np.isfinite(epsilon).all():
        raise ValueError("population MAD or scaled epsilon overflowed")
    selected = np.empty(int(k), dtype=np.int64)
    available = np.ones(len(values), dtype=bool)
    for draw in range(int(k)):
        pool = np.flatnonzero(available)
        if len(pool) > 1:
            for task in torch.randperm(values.shape[1], generator=generator).tolist():
                scores = values[pool, task]
                with np.errstate(over="ignore"):
                    threshold = scores.max() - epsilon[task]
                pool = pool[scores >= threshold]
                if len(pool) == 1:
                    break
        chosen = int(pool[0]) if len(pool) == 1 else int(
            pool[int(torch.randint(len(pool), (1,), generator=generator).item())])
        selected[draw] = chosen
        if not replace:
            available[chosen] = False
    return torch.from_numpy(selected)


def _front_ranks(values: np.ndarray) -> np.ndarray:
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
    return ranks


def _crowding(values: np.ndarray, ranks: np.ndarray) -> np.ndarray:
    distance = np.zeros(len(values), dtype=np.float64)
    for rank in range(int(ranks.max()) + 1):
        members = np.flatnonzero(ranks == rank)
        for column in range(values.shape[1]):
            levels, inverse = np.unique(values[members, column], return_inverse=True)
            if levels.size == 1:
                continue
            # Normalize before subtracting to avoid overflow for opposite finite extremes.
            scale = max(abs(float(levels[0])), abs(float(levels[-1])))
            scaled = levels / scale
            contribution = np.full(levels.size, np.inf)
            contribution[1:-1] = (scaled[2:] - scaled[:-2]) / (scaled[-1] - scaled[0])
            distance[members] += contribution[inverse]
    return distance


@dataclass(frozen=True)
class ParetoRanking:
    """CPU tensors in original row order, except order and tie_order (row permutations)."""

    objectives: torch.Tensor
    ranks: torch.Tensor
    crowding: torch.Tensor
    order: torch.Tensor
    tie_order: torch.Tensor


def pareto_ranking(objectives, *, generator: torch.Generator) -> ParetoRanking:
    """Rank fronts ascending, grouped crowding descending, then a random tie priority.

    Draw exactly one randperm(candidates) using the supplied generator. Within each
    front, each nonconstant task contributes its adjacent-distinct-value gap divided
    by that front's range; every minimum/maximum group gets infinity. Constant tasks
    contribute zero, including singleton fronts. Duplicate vectors get equal ranks
    and crowding. Equal-coordinate groups share contributions, so arbitrary input
    ordering cannot give one duplicate a spurious boundary advantage. If more boundary
    points exist than available places, the tie permutation determines their order.
    """
    values = _objectives(objectives)
    _generator(generator)
    ranks = _front_ranks(values)
    crowding = _crowding(values, ranks)
    if np.isnan(crowding).any():
        raise ValueError("crowding normalization produced NaN")
    ties = torch.randperm(len(values), generator=generator)
    priority = np.empty(len(values), dtype=np.int64)
    priority[ties.numpy()] = np.arange(len(values))
    order = np.lexsort((priority, -crowding, ranks))
    return ParetoRanking(torch.from_numpy(values), torch.from_numpy(ranks), torch.from_numpy(crowding),
                         torch.from_numpy(order), ties)


def pareto_order(objectives, *, generator: torch.Generator) -> torch.Tensor:
    """Return the same ordering as pareto_ranking; select its first k entries without replacement."""
    return pareto_ranking(objectives, generator=generator).order


def unique_genome_indices(genomes) -> torch.Tensor:
    """Indices of first occurrences of exact row bytes, preserving dtype and input order.

    No rounding, objective deduplication or RNG. Signed zero differs because these
    are exact genome bytes. Empty populations are allowed; rows must have positive
    width and all entries must be finite. The caller can concatenate current rows
    before archived rows to give current genomes precedence.
    """
    values = _array(genomes)
    if values.ndim != 2 or values.shape[1] == 0 or not np.isfinite(values).all():
        raise ValueError("genomes must be a finite [candidates, parameters] matrix with positive width")
    values = np.ascontiguousarray(values)
    seen, keep = set(), []
    for i, row in enumerate(values):
        key = row.tobytes()
        if key not in seen:
            seen.add(key)
            keep.append(i)
    return torch.tensor(keep, dtype=torch.int64)
