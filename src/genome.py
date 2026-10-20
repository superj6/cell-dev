"""Genome: one flat parameter vector per individual, with named slices in two blocks.

- ``grn``: the developmental gene-regulatory network (how cells divide and differentiate);
- ``cell``: the spiking rule of each cell type (what grown cells do).

Crossover works on whole *units*, so children inherit each unit intact from one parent:
each gene (its regulatory row, its product's effects, its asymmetry and maternal level), each cell type (its whole
rule), and the remaining global parameters. Genes regulate each other through the rows they own, so a regulatory
input travels with the gene being regulated, as cis-regulatory DNA does.

Two layouts share this machinery: kind ``types`` (``Dims``, the legacy tick pipeline above) and kind ``life``
(``LifeDims``, ``LifeLayout``: the 793-slot one-life genome of docs/ONE_LIFE_DESIGN.md, laid out exactly as
``src/life/spec.py`` packs it for the kernel, and the 875-slot ABI-3 genome of BODY-1, ``LIFE_DIMS_ABI3``).
``make_layout`` picks the class by ``dims.kind``.
"""
from __future__ import annotations

import json
import math
from dataclasses import dataclass

import torch


@dataclass(frozen=True)
class Dims:
    genes: int = 8
    morph: int = 2
    types: int = 4
    channels: int = 2
    stim: int = 2

    @property
    def grn_inputs(self) -> int:  # gene products, morphogens, neighbour fraction, age
        return self.genes + self.morph + 2

    @property
    def effectors(self) -> int:  # divide, asym, secrete[M], type logits[K]
        return 2 + self.morph + self.types

    @property
    def kind(self) -> str:  # a property, not a field: saved legacy genomes keep their exact dims payload
        return "types"


@dataclass(frozen=True)
class Field:
    name: str
    shape: tuple
    block: str  # grn | cell
    unit: str  # row | col | elem | global : how entries map onto crossover units
    init_std: float
    sigma: float  # mutation step


def _fields(d: Dims) -> list[Field]:
    G, M, K, C, S, A = d.genes, d.morph, d.types, d.channels, d.stim, d.effectors
    return [
        Field("W", (G, d.grn_inputs), "grn", "row", 1.0, 0.5),
        Field("b", (G,), "grn", "elem", 1.0, 0.5),
        Field("E", (A, G), "grn", "col", 1.5, 0.5),
        Field("e0", (A,), "grn", "global", 1.0, 0.5),
        Field("U", (M, G), "grn", "col", 1.0, 0.5),
        Field("u0", (M,), "grn", "global", 0.5, 0.5),
        Field("Q", (G,), "grn", "elem", 0.5, 0.25),
        Field("s0", (G,), "grn", "elem", 1.5, 0.5),
        Field("D", (M,), "grn", "global", 1.0, 0.5),
        Field("k", (M,), "grn", "global", 1.0, 0.5),
        Field("w", (K, C), "cell", "row", 0.75, 0.25),
        Field("gs", (K, S), "cell", "row", 0.75, 0.25),
        Field("bias", (K,), "cell", "elem", 0.5, 0.25),
        Field("leak", (K,), "cell", "elem", 1.0, 0.6),
        Field("refr", (K,), "cell", "elem", 1.0, 0.6),
        Field("emit", (K, C), "cell", "row", 1.0, 1.0),
    ]


class Layout:
    """Named slices of the flat genome plus the per-entry metadata that mutation and crossover need."""

    def __init__(self, dims: Dims):
        self.dims = dims
        self.fields = _fields(dims)
        self.slices: dict[str, tuple[int, int, tuple]] = {}
        units, blocks, init_std, sigma = [], [], [], []
        G, K = dims.genes, dims.types
        offset = 0
        for f in self.fields:
            n = math.prod(f.shape)
            self.slices[f.name] = (offset, offset + n, f.shape)
            offset += n
            idx = torch.arange(n).reshape(f.shape)
            base = 0 if f.block == "grn" else G  # gene units come first, then type units, then one global unit
            if f.unit == "row":
                u = base + (idx // f.shape[1]) if len(f.shape) == 2 else base + idx
            elif f.unit == "col":
                u = base + (idx % f.shape[1])
            elif f.unit == "elem":
                u = base + idx
            else:
                u = torch.full_like(idx, G + K)
            units.append(u.reshape(-1))
            blocks.append(torch.full((n,), 0 if f.block == "grn" else 1))
            init_std.append(torch.full((n,), f.init_std))
            sigma.append(torch.full((n,), f.sigma))
        self.size = offset
        self.n_units = G + K + 1
        self.unit_of = torch.cat(units)
        self.block_of = torch.cat(blocks)
        self.init_std = torch.cat(init_std)
        self.sigma = torch.cat(sigma)

    def view(self, params: torch.Tensor, name: str) -> torch.Tensor:
        a, b, shape = self.slices[name]
        return params[..., a:b].reshape(*params.shape[:-1], *shape)

    def random(self, n: int, gen: torch.Generator, scale: float = 1.0) -> torch.Tensor:
        return torch.randn(n, self.size, generator=gen) * self.init_std * scale

    def mutate(self, params: torch.Tensor, gen: torch.Generator, n_mut: int = 2, p_cell: float = 0.5) -> torch.Tensor:
        """Each child mutates ``n_mut`` entries inside one block (grn or cell), chosen per child."""
        B = params.shape[0]
        block = (torch.rand(B, 1, generator=gen) < p_cell).long()  # 1 = cell block
        in_block = self.block_of[None, :] == block
        scores = torch.rand(B, self.size, generator=gen).masked_fill(~in_block, -1.0)
        pick = scores.topk(n_mut, dim=1).indices
        noise = torch.randn(B, n_mut, generator=gen) * self.sigma[pick]
        out = params.clone()
        out.scatter_add_(1, pick, noise)
        return out

    def crossover(self, pa: torch.Tensor, pb: torch.Tensor, gen: torch.Generator, masks: bool = False):
        """Uniform crossover over units: each gene, cell type and the global unit comes whole from one parent.

        With ``masks`` it also returns the unit masks ``[B, n_units]`` (True = unit from ``pa``) for lineage logs.
        """
        bits = torch.rand(pa.shape[0], self.n_units, generator=gen) < 0.5
        child = torch.where(bits[:, self.unit_of], pa, pb)
        return (child, bits) if masks else child

    def to_dict(self, params: torch.Tensor) -> dict:
        return {f.name: self.view(params, f.name).tolist() for f in self.fields}

    def from_dict(self, d: dict) -> torch.Tensor:
        return torch.cat([torch.tensor(d[f.name], dtype=torch.float32).reshape(-1) for f in self.fields])

    def save(self, params: torch.Tensor, path) -> None:
        payload = {"dims": self.dims.__dict__, "params": self.to_dict(params)}
        with open(path, "w") as fh:
            json.dump(payload, fh)

    @staticmethod
    def load(path) -> tuple["Layout", torch.Tensor]:
        with open(path) as fh:
            payload = json.load(fh)
        layout = make_layout(make_dims(payload["dims"]))
        return layout, layout.from_dict(payload["params"])


# ========================================================================================================== kind life
# The one-life genome (docs/ONE_LIFE_DESIGN.md, Genome; docs/LIFE_ABI.md 4.4). For the v1 dims its fields, offsets,
# mutation blocks and unit kinds are exactly ``spec.GENOME_FIELDS``, and ``spec.pack_genomes`` turns a raw row into the
# kernel's table (decoding lam, s0, act, Dm and km, and zeroing everything that belongs to an inactive gene slot).
# ``src.life.spec`` is imported where it is used, so the legacy layout never depends on the life package.


@dataclass(frozen=True)
class LifeDims:
    """Dims of the one-life genome. The defaults (stim 0, cues 0, pheno 21) are ABI 2's 793-slot table (BELL-1).
    Larger dims describe padded later layouts: ``stim`` receptor-trace inputs appended to W and
    receptor gain rows appended to A and a0, ``cues`` plane-cue inputs after them, and ``pheno`` 22 for the vertical
    placement knob zeta. ``LIFE_DIMS_ABI3`` (stim 1, cues 2, pheno 22: 875 slots) is ABI 3's table (LIFE_ABI.md 4.4);
    ``LifeLayout.pad`` embeds an ABI-2 genome into it neutrally. The kernel runs both ABIs (``build.run`` speaks ABI 2
    and ABI 3), so the layouts of both are ``runnable``; other padded layouts are not."""

    genes_max: int = 16  # spec.G_MAX (LifeLayout checks every dimension of an ABI layout against src/life/spec.py)
    genes_init: int = 8  # spec.G_INIT
    morph: int = 2  # spec.M
    channels: int = 2  # spec.C
    stim: int = 0  # spec.S
    pheno: int = 21  # spec.P (ABI 3: 22 phenotype knobs, then the receptor gain row)
    kind: str = "life"
    cues: int = 0  # plane-cue inputs (ABI 3: is_S, is_M)
    stim2: int = 0  # ABI 8: receptor modalities whose trace inputs come after the cues (and gain rows after g_r)

    def __post_init__(self):
        # saved populations compare and hash ``dims.__dict__``: without ABI 8 modalities it stays the earlier payload
        # (stim2 then reads the class default 0)
        if self.stim2 == 0:
            object.__delattr__(self, "stim2")

    @property
    def genes(self) -> int:
        return self.genes_max

    @property
    def grn_inputs(self) -> int:  # g, m/(1+m)[M], own trace, received traces[C], n_view/D, receptors[S], cues, ...
        return self.genes_max + self.morph + 1 + self.channels + 1 + self.stim + self.cues + self.stim2

    @property
    def readout(self) -> int:  # the phenotype knobs, then one receptor gain row per modality
        return self.pheno + self.stim + self.stim2


LIFE_DIMS_ABI3 = LifeDims(stim=1, cues=2, pheno=22)  # BODY-1 v1 (LIFE_ABI.md 4.4): W [16][25], A [23][16]
LIFE_DIMS_ABI8 = LifeDims(stim=1, cues=2, pheno=22, stim2=9)  # ABI 8 (OPEN_WORLDS.md 4.1): W [16][34], A [32][16]


def make_dims(d) -> Dims | LifeDims:
    """Dims from a config or saved-genome mapping: ``kind: life`` gives ``LifeDims``, anything else the legacy ``Dims``."""
    d = dict(d)
    if d.get("kind", "types") == "life":
        return LifeDims(**d)
    d.pop("kind", None)
    return Dims(**d)


def make_layout(dims, **kw) -> Layout:
    return LifeLayout(dims, **kw) if dims.kind == "life" else Layout(dims)


# Initialization (design, INITIALIZATION: distribution choices, not rules; the census calibrates them). The knob
# priors below are BELL-1's. BODY-1 configs set their own (configs/life_catch.yaml: readout_std, knob_init and
# input_init, a tweak calibrated by the CATCH census):
# knob -> (a0 mean, a0 std, std of the knob's A row). A knob whose two stds are 0 starts exactly at decode(mean) in
# every cell of every founder: no cell dies (p_die = 0), placement starts without the flank term (phi = 0), and the
# dormant directional and chiral gains start at exactly 0.
# Knobs not listed start at (0.0, LIFE_A0_STD, LIFE_A_STD).
LIFE_A0_STD, LIFE_A_STD = 1.0, 1.5
LIFE_KNOB_INIT = dict(b=(1.0, LIFE_A0_STD, LIFE_A_STD), tau_m=(0.5, LIFE_A0_STD, LIFE_A_STD),
                      kappa=(0.5, LIFE_A0_STD, LIFE_A_STD), p_die=(-2.0, 0.0, 0.0), phi=(0.0, 0.0, 0.0),
                      a0=(0.0, 0.0, 0.0), a1=(0.0, 0.0, 0.0), chi=(0.0, 0.0, 0.0))
LIFE_BLOCKS = ("reg", "pheno")  # mutation blocks: regulation (block 0) and phenotype readout (block 1)


def _life_fields(d: LifeDims) -> list[Field]:
    G, M, R, NIN = d.genes_max, d.morph, d.readout, d.grn_inputs
    return [
        Field("W", (G, NIN), "reg", "row", 1.0, 0.5),
        Field("b", (G,), "reg", "elem", 1.0, 0.5),
        Field("lam", (G,), "reg", "elem", 1.5, 0.5),
        Field("s0", (G,), "reg", "elem", 1.5, 0.5),
        Field("Q", (G,), "reg", "elem", 0.5, 0.25),
        Field("act", (G,), "reg", "elem", 0.0, 0.0),  # never point-mutated: set at init, by duplicate and delete
        Field("A", (R, G), "pheno", "col", LIFE_A_STD, 0.5),
        Field("a0", (R,), "pheno", "global", LIFE_A0_STD, 0.5),
        Field("Dm", (M,), "reg", "global", 1.0, 0.5),
        Field("km", (M,), "reg", "global", 1.0, 0.5),
    ]


class LifeLayout(Layout):
    """Layout of kind ``life``: 16 gene slots (8 active at init) plus one global unit.

    - Crossover units: gene slot k carries its W row, b, lam, s0, Q, act and A column; the global unit carries a0,
      Dm and km. ``crossover(..., masks=True)`` returns the unit masks.
    - Mutation respects the active-gene mask: only entries of active genes (and global entries) change, a W column fed
      by an inactive gene stays put, and ``act`` is never point-mutated.
    - ``duplicate`` copies an active gene into a spare slot with silent outgoing weights (bitwise neutral); ``delete``
      clears an active bit; ``pad`` embeds a genome into a later-stage layout with zero new entries.
    - Invariant: a W entry fed by an inactive gene (``W[r, k]``, gene k off, r != k) is 0 in the raw genome, not
      only in the kernel table. ``delete`` and ``crossover`` restore it (``silence``), so a gene that later fills the
      slot, from this lineage or another, starts with no regulatory targets it did not bring.
    """

    def __init__(self, dims: LifeDims, knob_init: dict | None = None, input_init: dict | None = None,
                 readout_std: tuple | None = None):
        from src.life import spec

        n_pheno = (len(spec.KNOBS_V2), len(spec.KNOBS_V3) - spec.V3.S)  # 21 (ABI 2) or 22 (ABI 3: + zeta)
        if (dims.genes_max, dims.morph, dims.channels) != (spec.G_MAX, spec.M, spec.C) or dims.pheno not in n_pheno:
            raise ValueError(f"life dims must have genes_max {spec.G_MAX}, morph {spec.M}, channels {spec.C} and pheno "
                             f"21 or 22 (fixed by the kernel ABIs), got {dims}")
        if not 0 <= dims.genes_init <= dims.genes_max or dims.stim < 0 or dims.cues < 0:
            raise ValueError(f"need 0 <= genes_init <= genes_max and stim, cues >= 0, got {dims}")
        self.dims = dims
        self.fields = _life_fields(dims)
        # readout row names: the phenotype knobs, then one receptor gain row per modality
        self.knob_names = (spec.KNOBS_V3[:dims.pheno] + tuple("g_r" if m == 0 else f"g_r{m}" for m in range(dims.stim))
                           + tuple(f"g_r{m}" for m in range(dims.stim, dims.stim + dims.stim2)))
        init = {k: (0.0, LIFE_A0_STD, LIFE_A_STD) for k in self.knob_names}
        init.update(LIFE_KNOB_INIT)
        if readout_std is not None:  # (a0 std, A std) of every knob that does not start fixed (config readout_std)
            s0, sa = (float(x) for x in readout_std)
            init = {k: v if v[1:] == (0.0, 0.0) else (v[0], s0, sa) for k, v in init.items()}
        init.update({k: tuple(float(x) for x in v) for k, v in (knob_init or {}).items()})
        bad = set(init) - set(spec.KNOBS_V8) - set(self.knob_names)
        if bad:
            raise KeyError(f"unknown knobs in knob_init: {sorted(bad)}")
        G = dims.genes_max
        view_col = G + dims.morph + 1 + dims.channels  # n_view/D (ABI 2 has no flank_best input)
        recept = slice(view_col + 1, view_col + 1 + dims.stim)  # receptor traces, then the plane cues
        recept2 = slice(view_col + 1 + dims.stim + dims.cues, view_col + 1 + dims.stim + dims.cues + dims.stim2)
        # non-gene inputs by name (W columns G..), for input_init: founder std of every weight from that input
        cues = ("is_S", "is_M", *(f"cue{c}" for c in range(2, dims.cues)))[:dims.cues]
        self.input_names = (tuple(f"m{i}" for i in range(dims.morph)) + ("f",)
                            + tuple(f"r{c}" for c in range(dims.channels)) + ("n_view",)
                            + tuple("rho" if m == 0 else f"rho{m}" for m in range(dims.stim)) + cues
                            + tuple(f"rho{m}" for m in range(dims.stim, dims.stim + dims.stim2)))
        bad = set(input_init or {}) - set(self.input_names)
        if bad:
            raise KeyError(f"unknown inputs in input_init: {sorted(bad)} (inputs: {self.input_names})")
        self.slices = {}
        units, blocks, stds, means, sigmas, genes, srcs = [], [], [], [], [], [], []
        offset = 0
        for f in self.fields:
            n = math.prod(f.shape)
            self.slices[f.name] = (offset, offset + n, f.shape)
            offset += n
            idx = torch.arange(n).reshape(f.shape)
            if f.unit == "row":
                u = idx // f.shape[1]
            elif f.unit == "col":
                u = idx % f.shape[1]
            elif f.unit == "elem":
                u = idx
            else:
                u = torch.full_like(idx, G)
            units.append(u.reshape(-1))
            genes.append(torch.where(u.reshape(-1) < G, u.reshape(-1), torch.tensor(-1)))
            blocks.append(torch.full((n,), LIFE_BLOCKS.index(f.block)))
            sigmas.append(torch.full((n,), f.sigma))
            std, mean = torch.full(f.shape, f.init_std), torch.zeros(f.shape)
            src = torch.full(f.shape, -1)
            if f.name == "W":
                src[:, :G] = torch.arange(G)  # entries fed by gene j are mutable only while j is active
                std[:, view_col] = 0.0  # homogeneous founders: n_view starts with no weight
                std[:, recept] = 0.0  # receptor-trace inputs start silent; plane cues start random (BODY-1 census)
                std[:, recept2] = 0.0
                for name, v in (input_init or {}).items():  # overrides (config genome.input_init)
                    std[:, G + self.input_names.index(name)] = float(v)
            if f.name in ("A", "a0"):
                for r in range(dims.readout):
                    m, s0, sa = init[self.knob_names[r]]
                    std[r] = sa if f.name == "A" else s0
                    mean[r] = 0.0 if f.name == "A" else m
            stds.append(std.reshape(-1))
            means.append(mean.reshape(-1))
            srcs.append(src.reshape(-1))
        self.size = offset
        self.n_units = G + 1
        self.unit_of = torch.cat(units)
        self.block_of = torch.cat(blocks)
        self.init_std = torch.cat(stds)
        self.init_mean = torch.cat(means)
        self.sigma = torch.cat(sigmas)
        self.gene_of = torch.cat(genes)  # gene slot whose activity gates the entry, -1 for the global unit
        self.src_of = torch.cat(srcs)  # W only: the gene that feeds the entry's input, else -1
        a, b, _ = self.slices["act"]
        self.is_act = torch.zeros(self.size, dtype=torch.bool)
        self.is_act[a:b] = True
        self._gene_idx = torch.where(self.gene_of >= 0, self.gene_of, torch.tensor(G))
        self._src_idx = torch.where(self.src_of >= 0, self.src_of, torch.tensor(G))
        self._field_at = torch.cat([torch.full((math.prod(f.shape),), i) for i, f in enumerate(self.fields)]).tolist()
        # the spec ABI whose genome table these dims are (None for other padded layouts)
        shape = (dims.stim + dims.stim2, dims.cues, dims.pheno)
        self.abi = next((x for x in (spec.V2, spec.V3, spec.V8)
                         if shape == (x.S, x.NIN - len(spec.INPUTS_V2) - x.S, x.P - x.S)
                         and (dims.stim2 == 0) == (x.version < 8) and (x.version < 8 or dims.stim == 1)), None)
        if self.abi is not None:
            ours = [(f.name, tuple(f.shape), f.block, f.unit) for f in self.fields]
            theirs = [(f.name, tuple(f.shape), f.block, f.unit) for f in self.abi.GENOME_FIELDS]
            if ours != theirs or {k: v[:2] for k, v in self.slices.items()} != self.abi.GENOME_SLICES:
                raise RuntimeError(f"the life layout disagrees with src/life/spec.py ABI {self.abi.version}")

    @property
    def runnable(self) -> bool:
        """True for the genome table of a kernel ABI (ABI 2 or ABI 3: ``build.run`` speaks both)."""
        return self.abi is not None

    def from_dict(self, d: dict) -> torch.Tensor:
        """``Layout.from_dict`` with a shape check per field. A genome saved under ABI 1 has the same dims but a
        ``W`` of 23 columns (its last one read flank_best, removed in ABI 2: LIFE_ABI.md 15.32); it is refused rather
        than loaded with every later field shifted."""
        for f in self.fields:
            got = tuple(torch.tensor(d[f.name]).shape)
            if got != tuple(f.shape):
                old = f.name == "W" and got == (f.shape[0], f.shape[1] + 1)
                raise ValueError(f"saved field {f.name} has shape {got}, this layout needs {tuple(f.shape)}"
                                 + (" (an ABI 1 genome with the flank_best input; it cannot be loaded)" if old else ""))
        return super().from_dict(d)

    # ------------------------------------------------------------------------------------------- masks and init
    def active(self, params: torch.Tensor) -> torch.Tensor:
        """Active-gene mask ``[..., G]`` (the kernel's rule: act > 0.5)."""
        return self.view(params, "act") > 0.5

    def mutable(self, params: torch.Tensor) -> torch.Tensor:
        """Entries ``[B, size]`` that point mutation may change: global entries, and entries of active genes whose input
        (for W columns fed by a gene) is active too. ``act`` itself is never mutable."""
        act = self.active(params.reshape(-1, self.size))
        act = torch.cat([act, torch.ones(act.shape[0], 1, dtype=torch.bool)], dim=1)  # column G = the global unit
        return act[:, self._gene_idx] & act[:, self._src_idx] & ~self.is_act

    def random(self, n: int, gen: torch.Generator, scale: float = 1.0) -> torch.Tensor:
        """Founder candidates: the first ``genes_init`` slots active, every entry of a spare slot 0, the knob priors of
        ``LIFE_KNOB_INIT`` (stds times ``scale``) and zero weights from n_view (homogeneous founders)."""
        x = torch.randn(n, self.size, generator=gen) * self.init_std * scale + self.init_mean
        a, b, _ = self.slices["act"]
        x[:, a:b] = (torch.arange(self.dims.genes_max) < self.dims.genes_init).float()
        return torch.where(self.mutable(x) | self.is_act, x, torch.zeros(()))

    # --------------------------------------------------------------------------------------------- operators
    def silence(self, params: torch.Tensor) -> torch.Tensor:
        """Zero every W entry fed by an inactive gene (``W[r, k]`` with gene k off and r != k). ``pack`` masks these
        entries already, so a genome's own life is unchanged; the raw genome then carries no stale weight that a later
        gene in slot k (a crossover partner's, or a new duplicate) would inherit."""
        p = params.clone()
        G = self.dims.genes_max
        W = self.view(p, "W")
        keep = self.active(p)[..., None, :] | torch.eye(G, dtype=torch.bool)  # [..., row r, input gene k]
        W[..., :, :G] = torch.where(keep, W[..., :, :G], torch.zeros((), dtype=p.dtype))
        return p

    def crossover(self, pa: torch.Tensor, pb: torch.Tensor, gen: torch.Generator, masks: bool = False):
        """``Layout.crossover`` (whole units, the same draws), then ``silence``: a regulator row from one parent drops
        its weights from genes the child did not inherit."""
        out = super().crossover(pa, pb, gen, masks=masks)
        child, bits = out if masks else (out, None)
        child = self.silence(child)
        return (child, bits) if masks else child

    def n_mut_of(self, params: torch.Tensor, n_mut: int, scale: bool = True) -> torch.Tensor:
        """Point mutations per child: ``n_mut``, scaled by (active genes / genes_init) when ``scale`` (design:
        n_mut scales with the number of active genes), at least 1."""
        B = params.shape[0]
        if not scale or self.dims.genes_init == 0:
            return torch.full((B,), int(n_mut), dtype=torch.long)
        n_act = self.active(params).sum(1).double()
        return torch.clamp(torch.round(n_mut * n_act / self.dims.genes_init), min=1).long()

    def locate(self, flat: int) -> tuple[str, list[int]]:
        """Field name and index of one flat genome entry."""
        f = self.fields[self._field_at[flat]]
        rest, idx = flat - self.slices[f.name][0], []
        for n in reversed(f.shape):
            rest, i = divmod(rest, n)
            idx.append(i)
        return f.name, idx[::-1]

    def mutate(self, params: torch.Tensor, gen: torch.Generator, n_mut: int = 2, p_cell: float = 0.5, *,
               dup_rate: float = 0.0, del_rate: float = 0.0, split: bool = False, scale_n_mut: bool = True,
               slot_use: torch.Tensor | None = None, ops: list | None = None) -> torch.Tensor:
        """Point mutations inside one block per child (the phenotype block with probability ``p_cell``), drawn from the
        mutable entries with each field's sigma; then duplication and deletion at their per-child rates. ``ops`` (a
        list) receives one record per child: ``{"mut": [[field, index, delta], ...], "dup": [src, dst], "del": k}``.
        ``slot_use`` (carriers per slot in the population) is copied and counted up after each duplication, so the
        duplications of one batch spread over the least used slots instead of piling into one."""
        B = params.shape[0]
        if slot_use is not None:
            slot_use = slot_use.clone().long()
        out = params.clone()
        block = (torch.rand(B, 1, generator=gen) < p_cell).long()
        ok = (self.block_of[None, :] == block) & self.mutable(params)
        k = self.n_mut_of(params, n_mut, scale_n_mut)
        kmax = int(k.max()) if B else 0
        rec = [{} for _ in range(B)]
        if kmax > 0:
            scores = torch.rand(B, self.size, generator=gen).masked_fill(~ok, -1.0)
            top = scores.topk(kmax, dim=1)
            noise = torch.randn(B, kmax, generator=gen) * self.sigma[top.indices]
            valid = (top.values >= 0) & (torch.arange(kmax)[None, :] < k[:, None])
            rows, cols = valid.nonzero(as_tuple=True)
            out.index_put_((rows, top.indices[rows, cols]), noise[rows, cols], accumulate=True)
            if ops is not None:
                for r, c in zip(rows.tolist(), cols.tolist()):
                    name, idx = self.locate(int(top.indices[r, c]))
                    rec[r].setdefault("mut", []).append([name, idx, float(noise[r, c])])
        if dup_rate > 0 or del_rate > 0:
            u = torch.rand(B, 2, generator=gen)
            for i in range(B):
                if float(u[i, 0]) < dup_rate:
                    act = self.active(out[i])
                    src_ok, free = act.nonzero()[:, 0], (~act).nonzero()[:, 0]
                    if len(src_ok) and len(free):
                        src = int(src_ok[torch.randint(len(src_ok), (1,), generator=gen)])
                        dst = self._free_slot(free, slot_use, gen)
                        out[i] = self.duplicate(out[i], src, dst, split)
                        rec[i]["dup"] = [src, dst]
                        if slot_use is not None:
                            slot_use[dst] += 1
                if float(u[i, 1]) < del_rate:
                    act = self.active(out[i]).nonzero()[:, 0]
                    if len(act):
                        kk = int(act[torch.randint(len(act), (1,), generator=gen)])
                        out[i] = self.delete(out[i], kk)
                        rec[i]["del"] = kk
        if ops is not None:
            ops.extend(rec)
        return out

    @staticmethod
    def _free_slot(free: torch.Tensor, slot_use, gen: torch.Generator) -> int:
        """A spare slot for a duplicate: the one least used across the population (the slot registry, so a new gene
        rarely shares its slot index with another lineage's gene), ties broken at random."""
        if slot_use is not None:
            use = slot_use[free]
            free = free[use == use.min()]
        return int(free[torch.randint(len(free), (1,), generator=gen)])

    def duplicate(self, params: torch.Tensor, src: int, dst: int, split: bool = False) -> torch.Tensor:
        """Copy active gene ``src`` into the inactive slot ``dst``: its W row, b, lam, s0 and Q, and set act[dst].

        The copy's outgoing weights (its W column in every row and its A column) start at 0, so it regulates and
        reads out nothing until mutation gives it targets: the life is bitwise unchanged, and the copy's state equals
        the original's. ``split`` is the design's operator instead: the original's outgoing W and A columns are
        halved between the two copies. That is neutral in exact arithmetic, but the kernel then sums two halves where
        it summed one term, so a life can differ by rounding.
        """
        p = params.clone()
        act, W, A = self.view(p, "act"), self.view(p, "W"), self.view(p, "A")
        if not (float(act[src]) > 0.5 and float(act[dst]) <= 0.5):
            raise ValueError(f"duplicate needs an active source and a spare destination, got {src} -> {dst}")
        if split:
            W[:, src] = W[:, src] * 0.5
            A[:, src] = A[:, src] * 0.5
            W[:, dst] = W[:, src]
            A[:, dst] = A[:, src]
        else:
            W[:, dst] = 0.0
            A[:, dst] = 0.0
        W[dst, :] = W[src, :]
        for name in ("b", "lam", "s0", "Q"):
            v = self.view(p, name)
            v[dst] = v[src]
        act[dst] = 1.0
        return p

    def delete(self, params: torch.Tensor, k: int) -> torch.Tensor:
        """Clear gene k's active bit and zero the weights other genes read from it (``silence``). Its own entries stay
        in the genome but are masked: the kernel table zeroes them and mutation skips them, until a duplication writes
        the slot again. The life is the same as with the weights kept, because the kernel table masks them too."""
        p = params.clone()
        act = self.view(p, "act")
        if float(act[k]) <= 0.5:
            raise ValueError(f"gene {k} is not active")
        act[k] = 0.0
        return self.silence(p)

    def pad(self, params: torch.Tensor, target: "LifeLayout") -> torch.Tensor:
        """Embed genomes into a later-stage layout with at least as many inputs and knobs (design: LATER-STAGE
        FIELDS), for example ABI 2 into ``LIFE_DIMS_ABI3`` (the same as ``spec.V3.pad_genomes``).

        New inputs (W columns) and knobs (A rows and a0 entries) are appended, so every existing entry keeps its
        (row, column) place, and every new entry is 0: a new receptor or cue input has no weight, and a new knob or
        gain row decodes to 0. Padding to the same dims returns an identical genome.
        """
        a, b = self.dims, target.dims
        grows = b.stim >= a.stim and b.cues >= a.cues and b.pheno >= a.pheno and b.stim2 >= a.stim2
        # appending keeps every entry in place only if nothing of the source sits after a part that grows
        in_place = (a.stim == b.stim or a.cues == 0) and (a.pheno == b.pheno or a.stim == 0)
        in_place = in_place and (a.stim2 == b.stim2 or (a.stim == b.stim and a.cues == b.cues and a.pheno == b.pheno))
        if (a.genes_max, a.morph, a.channels) != (b.genes_max, b.morph, b.channels) or not (grows and in_place):
            raise ValueError(f"cannot pad {a} into {b}")
        lead = params.shape[:-1]
        parts = []
        for f, g in zip(self.fields, target.fields):
            out = torch.zeros(*lead, *g.shape, dtype=params.dtype)
            out[(..., *[slice(0, n) for n in f.shape])] = self.view(params, f.name)
            parts.append(out.reshape(*lead, -1))
        return torch.cat(parts, dim=-1)

    # ------------------------------------------------------------------------------------------------ kernel
    def pack(self, params: torch.Tensor, kind: str = "hex"):
        """Raw genomes -> the kernel's float64 genome table of this layout's ABI (``abi.pack_genomes``): ``[B, 793]``
        under ABI 2, ``[B, 875]`` under ABI 3."""
        if not self.runnable:
            raise ValueError(f"no kernel ABI has the genome table of {self.dims}")
        return self.abi.pack_genomes(params.detach().cpu().numpy().reshape(-1, self.size), kind)

    def zygote_phenotype(self, params: torch.Tensor, kind: str = "hex"):
        """Decoded phenotype ``[B, P]`` of each genome's zygote, theta = decode(A g0 + a0) (P = 21 under ABI 2, 23
        under ABI 3). The genes start at g0 in every plane, so this is the phenotype before the plane cues act."""
        import numpy as np

        gt = self.pack(params, kind)
        a, b = self.abi.GENOME_SLICES["s0"]
        return np.array([self.abi.phenotype(row, row[a:b]) for row in gt])
