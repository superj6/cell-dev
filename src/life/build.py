"""Compile, cache and load the one-life C kernel (``kernel.c``), and run lives through it (docs/LIFE_ABI.md 4).

The library is built with ``gcc -O3 -fopenmp -ffp-contract=off -fPIC -shared -std=c11`` (no fast-math, no -march), cached
under ``~/.cache/cell-dev/life`` (override with ``CELL_DEV_CACHE``) by the SHA-256 of the source plus the flags, and
loaded with ctypes. ``run`` packs worlds, seeds, genomes or programs and initial bodies into the kernel arrays.

The kernel implements ABI 4 (``KERNEL = spec.V4``). ``run`` speaks an explicit caller ABI, preserving the
legacy ``spec.CURRENT`` default (ABI 2). ABI 3 keeps its 66 world fields and 57 ledger columns; ABI 4 appends
four target-visibility fields and one capture readout. Older worlds pad neutrally. ABI 2 genome/program/body
inputs also retain their earlier neutral padding. Returned arrays use the caller's shapes, and undoing the
extra close-ledger folds recovers older full-mode ``all`` hashes exactly. Fast mode preserves each older
adapter's existing hash behavior; its hashes are not replay evidence.
"""
from __future__ import annotations

import ctypes
import hashlib
import os
import subprocess
import tempfile
import threading
from dataclasses import dataclass
from pathlib import Path

import numpy as np

from src.life import spec

KERNEL = spec.V4  # the contract kernel.c implements
SRC = Path(__file__).with_name("kernel.c")
CFLAGS = ("-O3", "-fopenmp", "-ffp-contract=off", "-fPIC", "-shared", "-std=c11")
FAST_FLAGS = ("-DLIFE_FAST",)  # the fast build: same lives and ledger, no hashes (see ``run``'s ``fast``)
RETURN_CODES = {-1: "size/ABI mismatch, missing or non-finite table, or genome_of outside its table",
                -2: "invalid world vector", -3: "allocation failure",
                -4: "invalid lattice table or initial body (duplicate sites, a cell outside the stack or the bound)"}

_lock = threading.Lock()
_libs: dict[bool, ctypes.CDLL] = {}  # full build (False) and fast build (True)

_i32, _i64, _u64, _f64 = ctypes.c_int32, ctypes.c_int64, ctypes.c_uint64, ctypes.c_double
_P = ctypes.POINTER


def cache_dir() -> Path:
    return Path(os.environ.get("CELL_DEV_CACHE", Path.home() / ".cache" / "cell-dev")) / "life"


def flags(fast: bool = False) -> tuple[str, ...]:
    return CFLAGS + FAST_FLAGS if fast else CFLAGS


def library_path(fast: bool = False) -> Path:
    """Cache path of the library: ``life_<first 16 hex digits of sha256(source + flags)>.so``."""
    key = hashlib.sha256(SRC.read_bytes() + " ".join(flags(fast)).encode()).hexdigest()[:16]
    return cache_dir() / f"life_{key}.so"


def build(force: bool = False, fast: bool = False) -> Path:
    """Compile kernel.c into the cache unless an up-to-date library exists; returns its path. ``fast`` builds the
    ``LIFE_FAST`` variant (see ``run``)."""
    out = library_path(fast)
    if out.exists() and not force:
        return out
    out.parent.mkdir(parents=True, exist_ok=True)
    fd, tmp = tempfile.mkstemp(suffix=".so", dir=out.parent)
    os.close(fd)
    try:
        cmd = ["gcc", *flags(fast), "-o", tmp, str(SRC), "-lm"]
        res = subprocess.run(cmd, capture_output=True, text=True)
        if res.returncode != 0:
            raise RuntimeError(f"kernel build failed: {' '.join(cmd)}\n{res.stderr}")
        os.replace(tmp, out)  # atomic: concurrent builders never see a partial library
    finally:
        if os.path.exists(tmp):
            os.unlink(tmp)
    return out


def _declare(lib) -> None:
    lib.life_abi_version.restype = _i32
    lib.life_abi_version.argtypes = []
    lib.life_sizes.restype = None
    lib.life_sizes.argtypes = [_P(_i32)]
    lib.life_hash64.restype = _u64
    lib.life_hash64.argtypes = [_u64, _u64, _i32, _P(_u64)]
    lib.life_normal.restype = _f64
    lib.life_normal.argtypes = [_u64, _u64, _i32, _P(_u64)]
    lib.life_decode.restype = None
    lib.life_decode.argtypes = [_P(_f64), _P(_f64)]
    lib.life_readout.restype = None
    lib.life_readout.argtypes = [_P(_f64), _P(_f64), _P(_f64)]
    lib.life_halo.restype = _f64
    lib.life_halo.argtypes = [_f64, _f64, _f64]
    lib.life_dot_gain.restype = None
    lib.life_dot_gain.argtypes = [_f64, _f64, _f64, _P(_f64)]
    lib.life_blob_heading.restype = None
    lib.life_blob_heading.argtypes = [_u64, _i32, _u64, _f64, _P(_f64)]
    lib.life_blob_place.restype = None
    lib.life_blob_place.argtypes = [_u64, _i32, _u64, _f64, _f64, _f64, _f64, _P(_f64)]
    lib.life_receptor_next.restype = _f64
    lib.life_receptor_next.argtypes = [_u64, _u64, _u64, _f64, _f64]
    lib.life_run.restype = _i32
    lib.life_run.argtypes = [
        _i32, _i32, _P(_i32), _P(_f64), _i32, _P(_f64), _i32, _P(_f64), _P(_i32), _P(_i32), _P(_i32), _P(_f64),
        _P(_u64), _P(_f64), _P(_u64), _i64, _P(_f64), _P(_u64), _P(_i64), _i64, _P(_i64), _P(_f64), _P(_i64)]
    lib.life_filled_footprint.restype = _i64
    lib.life_filled_footprint.argtypes = [_i32, _i64, _P(_i32), _P(_i32)]


def load(fast: bool = False):
    """The loaded kernel (built on first use), checked against ``KERNEL.version`` and ``KERNEL.SIZES``. ``fast``: the
    ``LIFE_FAST`` build (``run``'s ``fast``)."""
    with _lock:
        if fast not in _libs:
            lib = ctypes.CDLL(str(build(fast=fast)))
            _declare(lib)
            if lib.life_abi_version() != KERNEL.version:
                raise RuntimeError(f"kernel ABI {lib.life_abi_version()} != spec ABI {KERNEL.version}")
            sizes = (_i32 * 10)()
            lib.life_sizes(sizes)
            if list(sizes) != list(KERNEL.SIZES.values()):
                raise RuntimeError(f"kernel sizes {list(sizes)} != kernel ABI sizes {list(KERNEL.SIZES.values())}")
            _libs[fast] = lib
        return _libs[fast]


def _ptr(a, t):
    return None if a is None else a.ctypes.data_as(_P(t))


def _abi(abi) -> spec.Abi:
    abi = spec.CURRENT if abi is None else abi
    if abi.version not in (2, 3, 4):
        raise ValueError(f"build.run speaks ABI 2, 3 and {KERNEL.version}, not ABI {abi.version}")
    return abi


# ------------------------------------------------------------------------------------------- test exports
def hash64(seed: int, stream: int, *keys: int) -> int:
    k = np.array([x & spec.MASK64 for x in keys] or [0], dtype=np.uint64)
    return int(load().life_hash64(seed & spec.MASK64, stream & spec.MASK64, len(keys), _ptr(k, _u64)))


def normal(seed: int, stream: int, *keys: int) -> float:
    k = np.array([x & spec.MASK64 for x in keys] or [0], dtype=np.uint64)
    return float(load().life_normal(seed & spec.MASK64, stream & spec.MASK64, len(keys), _ptr(k, _u64)))


def decode(y) -> np.ndarray:
    """The kernel's knob decode of readout values ``y``: ABI 2's 21 rows or ABI 3's 23 (rows 0-20 are the same)."""
    y = np.asarray(y, dtype=np.float64)
    if y.shape not in ((spec.V2.P,), (KERNEL.P,)):
        raise ValueError(f"decode takes {spec.V2.P} or {KERNEL.P} readout values, got {y.shape}")
    yy = np.zeros(KERNEL.P)
    yy[:len(y)] = y
    out = np.zeros(KERNEL.P)
    load().life_decode(_ptr(yy, _f64), _ptr(out, _f64))
    return out[:len(y)]


def readout(gt_row, g) -> np.ndarray:
    """The kernel's readout ``a0 + A g`` of a packed genome row of ABI 2 (793, padded) or ABI 3 (875)."""
    gt = np.asarray(gt_row, dtype=np.float64)
    if gt.shape == (spec.V2.GENOME_SIZE,):
        gt, n = KERNEL.pad_genomes(gt, spec.V2), spec.V2.P
    elif gt.shape == (KERNEL.GENOME_SIZE,):
        n = KERNEL.P
    else:
        raise ValueError(f"a packed genome row has {spec.V2.GENOME_SIZE} or {KERNEL.GENOME_SIZE} entries")
    gt = np.ascontiguousarray(gt)
    g = np.ascontiguousarray(g, dtype=np.float64)
    out = np.zeros(KERNEL.P)
    load().life_readout(_ptr(gt, _f64), _ptr(g, _f64), _ptr(out, _f64))
    return out[:n]


def halo(dx: float, dy: float, sigma: float) -> float:
    return float(load().life_halo(dx, dy, sigma))


def dot_gain(dt: float, tau_z: float, gam: float) -> tuple[float, float]:
    out = np.zeros(2)
    load().life_dot_gain(dt, tau_z, gam, _ptr(out, _f64))
    return float(out[0]), float(out[1])


def blob_heading(seed: int, blob: int, h: int, v_t: float) -> tuple[float, float]:
    out = np.zeros(2)
    load().life_blob_heading(seed & spec.MASK64, blob, h & spec.MASK64, v_t, _ptr(out, _f64))
    return float(out[0]), float(out[1])


def blob_place(seed: int, blob: int, q: int, x: float, y: float, r_min: float, r_max: float) -> tuple[float, float]:
    out = np.zeros(2)
    load().life_blob_place(seed & spec.MASK64, blob, q & spec.MASK64, x, y, r_min, r_max, _ptr(out, _f64))
    return float(out[0]), float(out[1])


def receptor_next(seed: int, uid: int, j: int, t_prev: float, lam_max: float) -> float:
    return float(load().life_receptor_next(seed & spec.MASK64, uid & spec.MASK64, j & spec.MASK64, t_prev, lam_max))


def filled_footprint(cols, kind: str = "hexprism") -> int:
    """The kernel's filled footprint of the columns ``cols`` (``spec.filled_footprint``, LIFE_ABI.md 9.7.2)."""
    ab = np.ascontiguousarray(np.array(list(cols), dtype=np.int32).reshape(-1, 2).T)
    out = int(load().life_filled_footprint(KERNEL.LATTICE_CODES[kind] % 3, ab.shape[1], _ptr(ab[0], _i32),
                                           _ptr(ab[1], _i32)))
    if out < 0:
        raise MemoryError("life_filled_footprint: allocation failure")
    return out


# ------------------------------------------------------------------------------------- ABI 2 at the boundary
_SM_ADD = np.uint64(0x9E3779B97F4A7C15)
_SM_INV1 = np.uint64(pow(0xBF58476D1CE4E5B9, -1, 1 << 64))
_SM_INV2 = np.uint64(pow(0x94D049BB133111EB, -1, 1 << 64))


def _unmix(z: np.ndarray) -> np.ndarray:
    """The inverse of splitmix64 on a uint64 array (each xorshift and odd multiply is a bijection mod 2^64)."""
    def unshift(x, s):
        out = x.copy()
        for k in range(s, 64, s):
            out ^= x >> np.uint64(k)
        return out

    z = unshift(z, 31) * _SM_INV2
    z = unshift(z, 27) * _SM_INV1
    return unshift(z, 30) - _SM_ADD


def unfold_close(h: np.ndarray, ledger: np.ndarray, start: int) -> np.ndarray:
    """The ``all`` hash before the close folded ledger columns ``start..`` (``h = splitmix64(h ^ bits(col))`` each):
    ABI 2's ``all`` of a life is ``unfold_close(all, ledger, 35)`` of its ABI-3 outputs."""
    h = np.array(h, dtype=np.uint64, copy=True).reshape(-1)
    words = np.ascontiguousarray(ledger, dtype=np.float64).reshape(len(h), -1).view(np.uint64)
    for c in range(words.shape[1] - 1, start - 1, -1):
        h = _unmix(h) ^ words[:, c]
    return h


# ------------------------------------------------------------------------------------------------- runs
@dataclass
class Lives:
    """Kernel outputs for a batch of lives (LIFE_ABI.md 4.9-4.11), in the shapes of ``abi`` (``spec.CURRENT`` if
    None): ABI 2 has 35 ledger columns, 4 hashes and 6 fate-log columns; ABI 3 has 57/5/7 and ABI 4 has 58/5/7."""
    ledger: np.ndarray  # float64 [n, LEDGER_SIZE]
    hashes: np.ndarray  # uint64 [n, HASH_SIZE]: all, spikes, fate, chem (, world)
    raster_t: np.ndarray | None = None  # [n, cap]
    raster_uid: np.ndarray | None = None
    raster_n: np.ndarray | None = None  # [n] total spikes (may exceed the capacity)
    fate_i: np.ndarray | None = None  # [n, cap, FATE_I_SIZE]
    fate_f: np.ndarray | None = None  # [n, cap, 18]
    fate_n: np.ndarray | None = None
    abi: spec.Abi | None = None

    @property
    def layout(self) -> spec.Abi:
        return spec.CURRENT if self.abi is None else self.abi

    def __getitem__(self, name: str) -> np.ndarray:
        return self.ledger[:, self.layout.L[name]]

    def status(self, bit: str) -> np.ndarray:
        return (self.ledger[:, self.layout.L["status"]].astype(np.int64) & spec.STATUS[bit]) != 0

    def spikes(self, i: int) -> tuple[np.ndarray, np.ndarray]:
        n = int(min(self.raster_n[i], self.raster_t.shape[1]))
        return self.raster_t[i, :n], self.raster_uid[i, :n]

    def fates(self, i: int) -> tuple[np.ndarray, np.ndarray]:
        n = int(min(self.fate_n[i], self.fate_i.shape[1]))
        return self.fate_i[i, :n], self.fate_f[i, :n]


def _seeds(seeds) -> np.ndarray:
    a = np.asarray(seeds, dtype=object)
    if a.ndim == 0:
        a = a.reshape(1)
    if a.ndim == 1:  # life seeds only: tie seed, order seed and relabel salt 0
        a = np.array([[int(s), 0, 0, 0] for s in a], dtype=object)
    if a.ndim != 2 or a.shape[1] != 4:
        raise ValueError("seeds must be ints or rows (seed, tie seed, order seed, relabel salt)")
    return np.array([[int(x) & spec.MASK64 for x in row] for row in a], dtype=np.uint64)


def _init(init, n: int, abi: spec.Abi) -> tuple[np.ndarray | None, np.ndarray | None]:
    """Initial bodies -> the kernel's int32 ``[n, 1024, 4]`` rows ``(a, b, z, row)`` and counts. ABI 2 cells are
    ``(a, b)`` or ``(a, b, row)`` (z = 0); ABI 3 cells are ``(a, b)``, ``(a, b, z)`` or ``(a, b, z, row)``."""
    if init is None:
        return None, None
    many = len(init) > 0 and isinstance(init[0][0], (list, tuple))
    bodies = list(init) if many else [init] * n
    if len(bodies) != n:
        raise ValueError(f"{len(bodies)} initial bodies for {n} lives")
    cells = np.zeros((n, KERNEL.MAX_INIT, KERNEL.INIT_COLS), dtype=np.int32)
    counts = np.zeros(n, dtype=np.int32)
    packed = {}
    for i, body in enumerate(bodies):
        if id(body) not in packed:
            nsite = 2 if abi.version < 3 else 3
            sites = [tuple(c[:nsite]) for c in body]
            rows = [c[nsite] if len(c) > nsite else -1 for c in body]
            rows3 = abi.pack_init(sites, rows)
            if abi.version < 3:  # ABI 2 (a, b, row) -> (a, b, 0, row)
                old, cnt = rows3
                new = np.zeros((KERNEL.MAX_INIT, KERNEL.INIT_COLS), dtype=np.int32)
                new[:len(old), 0:2] = old[:, 0:2]
                new[:len(old), 3] = old[:, 2]
                rows3 = (new, cnt)
            packed[id(body)] = rows3
        cells[i], counts[i] = packed[id(body)]
    return cells, counts


def _worlds(ws, abi: spec.Abi) -> np.ndarray:
    """World vectors for the kernel; each world is validated under the caller's ABI (ABI 2 refuses CATCH)."""
    out = np.empty((len(ws), KERNEL.WORLD_SIZE), dtype=np.float64)
    done = {}
    for i, w in enumerate(ws):
        v = done.get(id(w))
        if v is None:
            if abi is not KERNEL:
                abi.validate_world(w)
            v = done[id(w)] = KERNEL.pack_world(w)
        out[i] = v
    return out


def _tables(genomes, programs, abi: spec.Abi) -> list:
    out = []
    for t, size, kind in ((genomes, abi.GENOME_SIZE, "genome"), (programs, abi.PROGRAM_SIZE, "program")):
        if t is not None:
            t = np.ascontiguousarray(np.atleast_2d(np.asarray(t, dtype=np.float64)))
            if t.shape[1] != size:
                raise ValueError(f"table rows must have {size} entries, got {t.shape[1]}")
            if abi is not KERNEL:  # neutral padding (LIFE_ABI.md 4.4, 4.5): every new entry 0
                if kind == "genome":
                    t = KERNEL.pad_genomes(t, abi)
                else:
                    t = np.stack([KERNEL.pad_program(row, abi) for row in t])
                t = np.ascontiguousarray(t, dtype=np.float64)
        out.append(t)
    return out


def run(worlds, seeds, *, genomes=None, programs=None, genome_of=None, init=None, kind: str | None = None,
        threads: int = 1, raster_cap: int = 0, fate_cap: int = 0, abi: spec.Abi | None = None,
        fast: bool = False) -> Lives:
    """Run ``n`` lives. ``worlds``: a ``spec.World`` (or a list, one per life). ``seeds``: life seeds or rows of 4.

    ``abi`` (``spec.CURRENT`` if None) is the ABI of the tables, bodies and outputs; the kernel itself is ABI 4.
    ``genomes`` is a packed genome table ``[G, GENOME_SIZE]`` (``abi.pack_genomes``), ``programs`` a program table
    ``[P, PROGRAM_SIZE]`` or one row (``abi.pack_program``); the two may have different row counts. ``genome_of[i]``
    picks the row of life i in the table its mode uses (program mode: ``programs``, else ``genomes``). By default a
    life uses row i of a table with ``n`` rows and row 0 of a one-row table; any other table needs an explicit
    ``genome_of``. ``init`` is one body for every life, or a list of bodies; ``None`` means one zygote at the origin.
    ABI 2 cells are ``(a, b)`` or ``(a, b, row)``; ABI 3 cells are ``(a, b)``, ``(a, b, z)`` or ``(a, b, z, row)``.
    The lattice comes from the worlds unless ``kind`` is given.

    ``fast`` uses the ``LIFE_FAST`` build: the same lives, bitwise (ledger, raster, fate log; tests/test_life_fast.py),
    about 1.25x faster, but it folds no hashes, so the raw families stay ``HASH_INIT``. ABI 2 preserves its legacy
    adapter's transformed ``all`` value (undoing the 22 ABI-3 close folds even in fast mode); ABI 3/4 return the
    constants. None is replay evidence. Use fast mode where hashes are not read (evolution); golden tests and
    anything comparing hashes keep the full build.
    """
    abi = _abi(abi)
    seeds = _seeds(seeds)
    n = len(seeds)
    ws = list(worlds) if isinstance(worlds, (list, tuple)) else [worlds] * n
    if len(ws) != n:
        raise ValueError(f"{len(ws)} worlds for {n} lives")
    kinds = {w.lattice for w in ws}
    if kind is None:
        if len(kinds) != 1:
            raise ValueError(f"one lattice per call, got {sorted(kinds)}")
        kind = kinds.pop()
    if kind not in abi.LATTICE_CODES:
        raise ValueError(f"lattice {kind!r} is not part of ABI {abi.version}")
    lat, unit = KERNEL.lattice_tables(kind)
    wv = _worlds(ws, abi)
    genomes, programs = _tables(genomes, programs, abi)
    n_rows = [0 if t is None else len(t) for t in (genomes, programs)]  # genome rows, program rows
    prog = [bool(w.flags & spec.FLAGS["program_mode"]) for w in ws]
    if genome_of is None:
        genome_of = []
        for i in range(n):
            rows = n_rows[prog[i]]
            if rows == 0:
                raise ValueError(f"life {i} is in {'program' if prog[i] else 'GRN'} mode, but its table was not given")
            if rows not in (1, n):
                raise ValueError(f"a {'program' if prog[i] else 'genome'} table with {rows} rows for {n} lives "
                                 "needs an explicit genome_of")
            genome_of.append(i if rows == n else 0)
    genome_of = np.ascontiguousarray(genome_of, dtype=np.int32)
    if genome_of.shape != (n,):
        raise ValueError(f"genome_of must have one entry per life ({n})")
    for i in range(n):
        if not 0 <= genome_of[i] < n_rows[prog[i]]:
            table = "program" if prog[i] else "genome"
            raise ValueError(f"life {i}: genome_of {genome_of[i]} outside the {table} table ({n_rows[prog[i]]} rows)")
    cells, counts = _init(init, n, abi)
    ledger = np.zeros((n, KERNEL.LEDGER_SIZE))
    hashes = np.zeros((n, KERNEL.HASH_SIZE), dtype=np.uint64)
    out = Lives(ledger, hashes, abi=abi)
    if raster_cap > 0:
        out.raster_t = np.zeros((n, raster_cap))
        out.raster_uid = np.zeros((n, raster_cap), dtype=np.uint64)
        out.raster_n = np.zeros(n, dtype=np.int64)
    if fate_cap > 0:
        out.fate_i = np.zeros((n, fate_cap, KERNEL.FATE_I_SIZE), dtype=np.int64)
        out.fate_f = np.zeros((n, fate_cap, KERNEL.FATE_F_SIZE))
        out.fate_n = np.zeros(n, dtype=np.int64)
    rc = load(fast).life_run(
        n, threads, _ptr(lat, _i32), _ptr(unit, _f64), n_rows[0], _ptr(genomes, _f64), n_rows[1], _ptr(programs, _f64),
        _ptr(genome_of, _i32), _ptr(cells, _i32), _ptr(counts, _i32), _ptr(wv, _f64), _ptr(seeds, _u64),
        _ptr(ledger, _f64), _ptr(hashes, _u64), raster_cap, _ptr(out.raster_t, _f64), _ptr(out.raster_uid, _u64),
        _ptr(out.raster_n, _i64), fate_cap, _ptr(out.fate_i, _i64), _ptr(out.fate_f, _f64), _ptr(out.fate_n, _i64))
    if rc != 0:
        raise ValueError(f"life_run returned {rc}: {RETURN_CODES.get(rc, 'unknown error')}")
    if abi is not KERNEL:  # caller shapes and compatible close hash (module docstring)
        L2, H2 = abi.LEDGER_SIZE, abi.HASH_SIZE
        h = hashes[:, :H2].copy()
        if not fast:
            h[:, 0] = unfold_close(hashes[:, 0], ledger, L2)
        elif abi.version == 2:
            # Retain the legacy ABI-2 fast adapter exactly; ABI 3/4 fast hashes stay HASH_INIT.
            h[:, 0] = unfold_close(hashes[:, 0], ledger[:, :spec.V3.LEDGER_SIZE], L2)
        out.ledger, out.hashes = np.ascontiguousarray(ledger[:, :L2]), np.ascontiguousarray(h)
        if fate_cap > 0:
            out.fate_i = np.ascontiguousarray(out.fate_i[:, :, :abi.FATE_I_SIZE])
    return out
