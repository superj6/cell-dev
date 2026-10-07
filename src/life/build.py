"""Compile, cache and load the one-life C kernel (``kernel.c``), and run lives through it (docs/LIFE_ABI.md 4).

The library is built with ``gcc -O3 -fopenmp -ffp-contract=off -fPIC -shared -std=c11`` (no fast-math, no -march), cached
under ``~/.cache/cell-dev/life`` (override with ``CELL_DEV_CACHE``) by the SHA-256 of the source plus the flags, and
loaded with ctypes. ``run`` packs worlds, seeds, genomes or programs and initial bodies into the kernel arrays.
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

SRC = Path(__file__).with_name("kernel.c")
CFLAGS = ("-O3", "-fopenmp", "-ffp-contract=off", "-fPIC", "-shared", "-std=c11")
RETURN_CODES = {-1: "size/ABI mismatch, missing or non-finite table, or genome_of outside its table",
                -2: "invalid world vector", -3: "allocation failure", -4: "invalid lattice table or initial body"}

_lock = threading.Lock()
_lib = None

_i32, _i64, _u64, _f64 = ctypes.c_int32, ctypes.c_int64, ctypes.c_uint64, ctypes.c_double
_P = ctypes.POINTER


def cache_dir() -> Path:
    return Path(os.environ.get("CELL_DEV_CACHE", Path.home() / ".cache" / "cell-dev")) / "life"


def library_path() -> Path:
    """Cache path of the library: ``life_<first 16 hex digits of sha256(source + flags)>.so``."""
    key = hashlib.sha256(SRC.read_bytes() + " ".join(CFLAGS).encode()).hexdigest()[:16]
    return cache_dir() / f"life_{key}.so"


def build(force: bool = False) -> Path:
    """Compile kernel.c into the cache unless an up-to-date library exists; returns its path."""
    out = library_path()
    if out.exists() and not force:
        return out
    out.parent.mkdir(parents=True, exist_ok=True)
    fd, tmp = tempfile.mkstemp(suffix=".so", dir=out.parent)
    os.close(fd)
    try:
        cmd = ["gcc", *CFLAGS, "-o", tmp, str(SRC), "-lm"]
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
    lib.life_run.restype = _i32
    lib.life_run.argtypes = [
        _i32, _i32, _P(_i32), _P(_f64), _i32, _P(_f64), _i32, _P(_f64), _P(_i32), _P(_i32), _P(_i32), _P(_f64),
        _P(_u64), _P(_f64), _P(_u64), _i64, _P(_f64), _P(_u64), _P(_i64), _i64, _P(_i64), _P(_f64), _P(_i64)]


def load():
    """The loaded kernel (built on first use), checked against ``spec.ABI_VERSION`` and ``spec.SIZES``."""
    global _lib
    with _lock:
        if _lib is None:
            lib = ctypes.CDLL(str(build()))
            _declare(lib)
            if lib.life_abi_version() != spec.ABI_VERSION:
                raise RuntimeError(f"kernel ABI {lib.life_abi_version()} != spec ABI {spec.ABI_VERSION}")
            sizes = (_i32 * 10)()
            lib.life_sizes(sizes)
            if list(sizes) != list(spec.SIZES.values()):
                raise RuntimeError(f"kernel sizes {list(sizes)} != spec.SIZES {list(spec.SIZES.values())}")
            _lib = lib
        return _lib


def _ptr(a, t):
    return None if a is None else a.ctypes.data_as(_P(t))


# ------------------------------------------------------------------------------------------- test exports
def hash64(seed: int, stream: int, *keys: int) -> int:
    k = np.array([x & spec.MASK64 for x in keys] or [0], dtype=np.uint64)
    return int(load().life_hash64(seed & spec.MASK64, stream & spec.MASK64, len(keys), _ptr(k, _u64)))


def normal(seed: int, stream: int, *keys: int) -> float:
    k = np.array([x & spec.MASK64 for x in keys] or [0], dtype=np.uint64)
    return float(load().life_normal(seed & spec.MASK64, stream & spec.MASK64, len(keys), _ptr(k, _u64)))


def decode(y) -> np.ndarray:
    y = np.ascontiguousarray(y, dtype=np.float64)
    out = np.zeros(spec.P)
    load().life_decode(_ptr(y, _f64), _ptr(out, _f64))
    return out


def readout(gt_row, g) -> np.ndarray:
    gt = np.ascontiguousarray(gt_row, dtype=np.float64)
    g = np.ascontiguousarray(g, dtype=np.float64)
    out = np.zeros(spec.P)
    load().life_readout(_ptr(gt, _f64), _ptr(g, _f64), _ptr(out, _f64))
    return out


# ------------------------------------------------------------------------------------------------- runs
@dataclass
class Lives:
    """Kernel outputs for a batch of lives (LIFE_ABI.md 4.9-4.11)."""
    ledger: np.ndarray  # float64 [n, 35]
    hashes: np.ndarray  # uint64 [n, 4]: all, spikes, fate, chem
    raster_t: np.ndarray | None = None  # [n, cap]
    raster_uid: np.ndarray | None = None
    raster_n: np.ndarray | None = None  # [n] total spikes (may exceed the capacity)
    fate_i: np.ndarray | None = None  # [n, cap, 6]
    fate_f: np.ndarray | None = None  # [n, cap, 18]
    fate_n: np.ndarray | None = None

    def __getitem__(self, name: str) -> np.ndarray:
        return self.ledger[:, spec.L[name]]

    def status(self, bit: str) -> np.ndarray:
        return (self.ledger[:, spec.L["status"]].astype(np.int64) & spec.STATUS[bit]) != 0

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


def _init(init, n: int) -> tuple[np.ndarray | None, np.ndarray | None]:
    if init is None:
        return None, None
    many = len(init) > 0 and isinstance(init[0][0], (list, tuple))
    bodies = list(init) if many else [init] * n
    if len(bodies) != n:
        raise ValueError(f"{len(bodies)} initial bodies for {n} lives")
    cells = np.zeros((n, spec.MAX_INIT, 3), dtype=np.int32)
    counts = np.zeros(n, dtype=np.int32)
    for i, body in enumerate(bodies):
        sites = [tuple(c[:2]) for c in body]
        rows = [c[2] if len(c) > 2 else -1 for c in body]
        cells[i], counts[i] = spec.pack_init(sites, rows)
    return cells, counts


def run(worlds, seeds, *, genomes=None, programs=None, genome_of=None, init=None, kind: str | None = None,
        threads: int = 1, raster_cap: int = 0, fate_cap: int = 0) -> Lives:
    """Run ``n`` lives. ``worlds``: a ``spec.World`` (or a list, one per life). ``seeds``: life seeds or rows of 4.

    ``genomes`` is a packed genome table ``[G, 793]`` (``spec.pack_genomes``), ``programs`` a program table
    ``[P, 119]`` or ``[119]`` (``spec.pack_program``); the two may have different row counts. ``genome_of[i]`` picks
    the row of life i in the table its mode uses (program mode: ``programs``, else ``genomes``). By default a life uses
    row i of a table with ``n`` rows and row 0 of a one-row table; any other table needs an explicit ``genome_of``.
    ``init`` is one body ``[(a, b) | (a, b, row), ...]`` for every life, or a list of bodies; ``None`` means one
    zygote at the origin. The lattice comes from the worlds unless ``kind`` is given.
    """
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
    lat, unit = spec.lattice_tables(kind)
    wv = np.ascontiguousarray(spec.pack_world(ws), dtype=np.float64)
    tables = []
    for t, size in ((genomes, spec.GENOME_SIZE), (programs, spec.PROGRAM_SIZE)):
        if t is not None:
            t = np.ascontiguousarray(np.atleast_2d(np.asarray(t, dtype=np.float64)))
            if t.shape[1] != size:
                raise ValueError(f"table rows must have {size} entries, got {t.shape[1]}")
        tables.append(t)
    genomes, programs = tables
    n_rows = [0 if t is None else len(t) for t in tables]  # genome rows, program rows
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
    cells, counts = _init(init, n)
    ledger = np.zeros((n, spec.LEDGER_SIZE))
    hashes = np.zeros((n, spec.HASH_SIZE), dtype=np.uint64)
    out = Lives(ledger, hashes)
    if raster_cap > 0:
        out.raster_t = np.zeros((n, raster_cap))
        out.raster_uid = np.zeros((n, raster_cap), dtype=np.uint64)
        out.raster_n = np.zeros(n, dtype=np.int64)
    if fate_cap > 0:
        out.fate_i = np.zeros((n, fate_cap, spec.FATE_I_SIZE), dtype=np.int64)
        out.fate_f = np.zeros((n, fate_cap, spec.FATE_F_SIZE))
        out.fate_n = np.zeros(n, dtype=np.int64)
    rc = load().life_run(
        n, threads, _ptr(lat, _i32), _ptr(unit, _f64), n_rows[0], _ptr(genomes, _f64), n_rows[1], _ptr(programs, _f64),
        _ptr(genome_of, _i32), _ptr(cells, _i32), _ptr(counts, _i32), _ptr(wv, _f64), _ptr(seeds, _u64),
        _ptr(ledger, _f64), _ptr(hashes, _u64), raster_cap, _ptr(out.raster_t, _f64), _ptr(out.raster_uid, _u64),
        _ptr(out.raster_n, _i64), fate_cap, _ptr(out.fate_i, _i64), _ptr(out.fate_f, _f64), _ptr(out.fate_n, _i64))
    if rc != 0:
        raise ValueError(f"life_run returned {rc}: {RETURN_CODES.get(rc, 'unknown error')}")
    return out
