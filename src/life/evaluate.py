"""LifeEvaluator: each genome lives L continuous lives in the C kernel, and the evaluator returns the legacy ``Eval``
fields (docs/ONE_LIFE_DESIGN.md, EVALUATION PROTOCOL; Code plan, src/evolve.py).

- fitness = mean F over the genome's lives; score = income rate; energy = cost rate (charges plus any guard charge),
  both per unit of ledger time; n_cells = mean live cells at the end; spikes = spikes per unit; divisions = mean
  successful divisions; trial_scores = F per life ``[B, L]``.
- Lives come from a ``LifeDraw``: life seeds shared by every genome of one call (common random numbers: frozen
  physics is keyed by coordinates, so the same place has the same physics for every genome) and one world per life.
  Seeds are a hash of (run seed, purpose, index, life), so each generation gets fresh lives.
- Lives are independent in the kernel and each genome's numbers are averaged over its own lives in a fixed order, so
  a genome's evaluation does not depend on the rest of the batch or on the thread count (bitwise).
- The envelope control draws each life's noise physics uniformly from configured ranges, keyed like the seeds, so
  it is shared within a generation and fresh across generations. It applies to the selection lives only
  (``ENVELOPE_PURPOSES``: generations and founder batches). Valid, held-out, final, clone and size-curve lives use the
  base physics in every condition, so F compares like for like across conditions; ``draw(..., envelope=True)`` gives
  the same lives under envelope physics for a robustness column that every condition reports.
- A life whose kernel status has the ``capacity`` or ``ledger_mismatch`` bit is invalid: it is scored as the worst
  guard trip and counted (``invalid``; ``mismatch`` counts the ledger failures alone).
"""
from __future__ import annotations

from dataclasses import dataclass, replace

import numpy as np
import torch
from omegaconf import OmegaConf

from src.evolve import Eval
from src.life import build, spec

PURPOSES = dict(gen=1, founders=2, valid=3, heldout=4, final=5, clones=6, sizecurve=7, census=8)
_SEED_STREAM = 0x4C494645  # "LIFE": keeps life seeds apart from every kernel stream
_ENV_STREAM = 0x454E5631  # "ENV1"
ENVELOPE_KEYS = ("delay_sd", "tau_mis", "jit", "clock_sd", "tick_jit", "drop_p", "noise_rate")
CAPACITY = spec.STATUS["capacity"]  # an implementation limit was reached: the life must not be used (LIFE_ABI.md 4.12)
MISMATCH = spec.STATUS["ledger_mismatch"]  # F*T != income - sum of costs beyond 1e-9 (design: every life checks it)
INVALID = CAPACITY | MISMATCH
ENVELOPE_PURPOSES = ("gen", "founders")  # the envelope control changes what selection sees, nothing it is judged on
GUARDS = spec.STATUS["guard_cells"] | spec.STATUS["guard_events"]


def life_seed(run_seed: int, purpose: str, index: int, life: int) -> int:
    """The life seed of life ``life`` of draw ``index`` for ``purpose`` (generation, founder batch, ...)."""
    return spec.hash64(int(run_seed), _SEED_STREAM + PURPOSES[purpose], int(index), int(life))


@dataclass(frozen=True)
class LifeDraw:
    """The lives of one evaluation: one seed and one world per life, the same for every genome evaluated on it."""
    seeds: tuple[int, ...]
    worlds: tuple[spec.World, ...]

    @property
    def n(self) -> int:
        return len(self.seeds)


@dataclass
class LifeEval(Eval):
    """``Eval`` plus life statistics (per genome, means over its lives)."""
    n_peak: torch.Tensor
    body: torch.Tensor  # mean live cells over the ledger window (live_time / window)
    income_per_cell: torch.Tensor  # income / live_time
    contact_events: torch.Tensor  # per unit
    extinct: torch.Tensor  # fraction of lives that went extinct
    guard: torch.Tensor  # fraction of lives ended by a compute guard
    invalid: torch.Tensor  # lives with the capacity or ledger_mismatch bit (scored as the worst guard trip)
    events: torch.Tensor
    mismatch: torch.Tensor  # lives whose ledger check failed (a kernel fault; also counted in invalid)

    KEYS = ("fitness", "score", "energy", "n_cells", "spikes", "divisions", "n_peak", "body", "income_per_cell",
            "contact_events", "extinct", "guard", "invalid", "events", "mismatch")

    def take(self, i: int) -> dict:
        return {k: float(getattr(self, k)[i]) for k in self.KEYS}


def _plain(x) -> dict:
    if x is None:
        return {}
    return dict(OmegaConf.to_container(x, resolve=True)) if OmegaConf.is_config(x) else dict(x)


class LifeEvaluator:
    """Runs genomes of a ``LifeLayout`` in BELL-1 worlds built from the config (sections life, world, costs_life,
    envelope). Call it as ``ev(params, draw)``; ``draw(purpose, index)`` makes the lives."""

    def __init__(self, cfg, layout):
        self.cfg, self.layout = cfg, layout
        lc = cfg.life
        self.kind = str(cfg.lattice.kind)
        self.seed = int(cfg.seed)
        self.T = float(lc.T)
        self.lives = int(lc.lives)
        self.threads = int(cfg.threads)
        self.batch = int(cfg.evolve.get("batch", 256))
        self.envelope = _plain(cfg.get("envelope"))
        bad = [k for k in self.envelope if k not in ("enabled",) + ENVELOPE_KEYS]
        if bad:  # e.g. a YAML key `on`, which YAML 1.1 reads as the boolean True
            raise ValueError(f"unknown envelope keys {bad}: use enabled and {list(ENVELOPE_KEYS)}")
        self.world()  # validate the configuration once

    # ------------------------------------------------------------------------------------------------- worlds
    def world(self, T: float | None = None, **extra) -> spec.World:
        """The base world of this run for a life of length T: preset, overrides, costs, base flags and the
        freeze-after-growth fork (``life.freeze_frac`` of T)."""
        lc = self.cfg.life
        T = self.T if T is None else float(T)
        over = _plain(self.cfg.get("world"))
        over.update(_plain(self.cfg.get("costs_life")))
        flags = spec.flags(*[str(f) for f in (lc.get("flags") or [])])
        t_fork, fork_flags = 0.0, 0
        if lc.get("freeze_frac") is not None:
            t_fork, fork_flags = float(lc.freeze_frac) * T, spec.FLAGS["freeze"]
        w = spec.world(str(lc.get("world", "bell_v1")), T=T, lattice=self.kind, flags=flags,
                       t_open=float(lc.get("t_open", 0.0)), t_fork=t_fork, fork_flags=fork_flags, **over)
        w = replace(w, **extra)
        spec.validate_world(w)
        return w

    @property
    def has_envelope(self) -> bool:
        """True if the config gives at least one envelope range (whether or not the envelope is enabled)."""
        return any(k in self.envelope for k in ENVELOPE_KEYS)

    def _envelope(self, w: spec.World, purpose: str, index: int, life: int) -> spec.World:
        vals = {}
        for j, key in enumerate(ENVELOPE_KEYS):
            if key in self.envelope:
                lo, hi = (float(x) for x in self.envelope[key])
                u = spec.draw(self.seed, _ENV_STREAM, PURPOSES[purpose], int(index), int(life), j)
                vals[key] = lo + (hi - lo) * u
        return replace(w, **vals)

    def draw(self, purpose: str, index: int, lives: int | None = None, T: float | None = None,
             overrides: list[dict] | None = None, envelope: bool | None = None) -> LifeDraw:
        """Lives for one evaluation. ``overrides`` (a list of world-field dicts) gives every override ``lives`` lives
        of its own (held-out physics, base noise); otherwise every life uses the base world. ``envelope`` picks the
        noise physics of those lives: None (default) applies the envelope to selection purposes when it is enabled;
        True draws envelope physics from the configured ranges even when the envelope is off (the same seeds, so a
        robustness column pairs with the base one); False never applies it."""
        L = self.lives if lives is None else int(lives)
        if envelope is None:
            envelope = bool(self.envelope.get("enabled", False)) and purpose in ENVELOPE_PURPOSES
        base = self.world(T)
        if overrides:
            worlds, seeds = [], []
            for j, o in enumerate(overrides):
                w = replace(base, **{k: float(v) for k, v in _plain(o).items()})
                spec.validate_world(w)
                for life in range(L):
                    seeds.append(life_seed(self.seed, purpose, index, j * L + life))
                    worlds.append(w)
            return LifeDraw(tuple(seeds), tuple(worlds))
        seeds = tuple(life_seed(self.seed, purpose, index, life) for life in range(L))
        worlds = tuple(self._envelope(base, purpose, index, life) if envelope else base for life in range(L))
        return LifeDraw(seeds, worlds)

    # ------------------------------------------------------------------------------------------------- runs
    def table(self, params) -> np.ndarray:
        """Packed kernel genome table ``[B, 809]`` of raw genomes (a tensor or an array)."""
        if isinstance(params, torch.Tensor):
            return self.layout.pack(params, self.kind)
        return spec.pack_genomes(np.asarray(params, dtype=np.float32).reshape(-1, spec.GENOME_SIZE), self.kind)

    def run(self, params, draw: LifeDraw, **logs) -> build.Lives:
        """Kernel lives of every genome on every life of the draw, genome-major: life ``b * L + l``."""
        gt = self.table(params)
        B, L = len(gt), draw.n
        worlds = [draw.worlds[life] for _ in range(B) for life in range(L)]
        seeds = [draw.seeds[life] for _ in range(B) for life in range(L)]
        return build.run(worlds, seeds, genomes=gt, genome_of=np.repeat(np.arange(B), L), kind=self.kind,
                         threads=self.threads, **logs)

    @torch.inference_mode()
    def __call__(self, params, draw: LifeDraw) -> LifeEval:
        n = params.shape[0]
        parts = [self._eval(params[i: i + self.batch], draw) for i in range(0, n, self.batch)]
        return LifeEval(*[torch.cat([getattr(p, f) for p in parts]) for f in LifeEval.__dataclass_fields__])

    @staticmethod
    def columns(res: build.Lives, B: int, draw: LifeDraw) -> dict[str, np.ndarray]:
        """Ledger columns ``[B, L]`` of a genome-major batch, plus ``window`` (T - t_open), the status flags
        ``extinct``, ``guard``, ``mismatch`` and ``invalid``, and F with every invalid life scored as the worst guard
        trip."""
        led = res.ledger.reshape(B, draw.n, spec.LEDGER_SIZE)
        col = {k: led[:, :, i] for k, i in spec.L.items()}
        status = col["status"].astype(np.int64)
        col["window"] = np.broadcast_to(np.array([w.T - w.t_open for w in draw.worlds])[None, :], (B, draw.n))
        col["invalid"] = (status & INVALID) != 0
        col["mismatch"] = (status & MISMATCH) != 0
        col["extinct"] = (status & spec.STATUS["extinct"]) != 0
        col["guard"] = (status & GUARDS) != 0
        floor = np.array([-w.c_live * w.n_max for w in draw.worlds])[None, :]
        col["F"] = np.where(col["invalid"], floor, col["F"])
        return col

    def _eval(self, params, draw: LifeDraw) -> LifeEval:
        col = self.columns(self.run(params, draw), params.shape[0], draw)
        window, live = col["window"], np.maximum(col["live_time"], 1e-300)

        def mean(x) -> torch.Tensor:
            return torch.from_numpy(np.ascontiguousarray(np.asarray(x, dtype=np.float64).mean(axis=1)))

        return LifeEval(
            fitness=mean(col["F"]), score=mean(col["income"] / window),
            energy=mean((col["income"] - col["net"]) / window), n_cells=mean(col["n_end"]),
            spikes=mean(col["spikes"] / window), divisions=mean(col["births"]),
            trial_scores=torch.from_numpy(np.ascontiguousarray(col["F"])), n_peak=mean(col["n_peak"]),
            body=mean(col["live_time"] / window), income_per_cell=mean(col["income"] / live),
            contact_events=mean(col["contact_events"] / window), extinct=mean(col["extinct"]), guard=mean(col["guard"]),
            invalid=mean(col["invalid"]), events=mean(col["events"]), mismatch=mean(col["mismatch"]))
