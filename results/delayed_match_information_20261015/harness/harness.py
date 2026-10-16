"""Minimal ABI5 scratch runner. No prototype worlds, seed allocation, or matcher policy."""
from pathlib import Path
import ctypes as C
import sys
from dataclasses import replace
import numpy as np

HERE = Path(__file__).resolve().parent
WORKTREE = HERE.parents[2] / 'outputs/abi5_delayed_match_20261015/worktree'
sys.path.insert(0, str(WORKTREE))
from src.life import build, spec, handbuilt as hb

V = spec.V5
I, U, F, Q = C.c_int32, C.c_uint64, C.c_double, C.c_int64
P = C.POINTER


def load(path):
    lib = C.CDLL(str(path))
    build._declare(lib)
    lib.ctl_life_run.restype = I
    lib.ctl_life_run.argtypes = [
        I, I, P(I), P(F), I, P(F), P(I), P(I), P(I), P(F), P(U), P(F), P(U), Q,
        P(F), P(U), P(Q), Q, P(Q), P(F), P(Q), P(I), P(F), I, P(F), P(F), P(I), P(F), I, P(F)]
    return lib


def inert(shape='hollow3'):
    sense, act = hb.speck_shape(shape)
    cells = tuple((a, b, z, 0) for a, b, z, _ in hb.role_cells(sense, act))
    row = V.theta(tau_m=2.0, t_ref=1.0)
    program = V.pack_program(row, alone=row, juvenile=row, rim=row, zygote=row)
    return program, cells


def run_controller(lib, world, seed, cid=0, parameters=(), shape='hollow3', charge='relay',
                   raster_cap=16384, fate_cap=1024):
    """One life, one thread. Only null, script and replay engineering controllers exist."""
    program, cells = inert(shape)
    world = replace(world, flags=world.flags | V.FLAGS['program_mode'])
    lat, unit = V.lattice_tables(world.lattice)
    w = V.pack_world(world)[None]
    seeds = build._seeds([seed])
    initial, counts = build._init(cells, 1, V)
    pg = np.ascontiguousarray(program[None])
    gof = np.zeros(1, dtype=np.int32)
    ledger = np.zeros((1, V.LEDGER_SIZE))
    hashes = np.zeros((1, V.HASH_SIZE), dtype=np.uint64)
    result = build.Lives(ledger, hashes, abi=V)
    result.raster_t = np.zeros((1, raster_cap))
    result.raster_uid = np.zeros((1, raster_cap), dtype=np.uint64)
    result.raster_n = np.zeros(1, dtype=np.int64)
    result.fate_i = np.zeros((1, fate_cap, V.FATE_I_SIZE), dtype=np.int64)
    result.fate_f = np.zeros((1, fate_cap, V.FATE_F_SIZE))
    result.fate_n = np.zeros(1, dtype=np.int64)
    cids = np.array([cid], dtype=np.int32)
    pp = np.ascontiguousarray(parameters, dtype=np.float64)
    latency = np.array([world.d0])
    tref = np.array([0.5])
    flags = np.array([8 | {'none': 0, 'receptor': 2, 'relay': 6}[charge]], dtype=np.int32)
    extra = np.zeros(1)
    diag = np.zeros((1, 16))
    ptr = lambda x, t: x.ctypes.data_as(P(t))
    rc = lib.ctl_life_run(
        1, 1, ptr(lat, I), ptr(unit, F), 1, ptr(pg, F), ptr(gof, I), ptr(initial, I), ptr(counts, I),
        ptr(w, F), ptr(seeds, U), ptr(ledger, F), ptr(hashes, U), raster_cap,
        ptr(result.raster_t, F), ptr(result.raster_uid, U), ptr(result.raster_n, Q), fate_cap,
        ptr(result.fate_i, Q), ptr(result.fate_f, F), ptr(result.fate_n, Q), ptr(cids, I), ptr(pp, F),
        len(pp), ptr(latency, F), ptr(tref, F), ptr(flags, I), ptr(extra, F), 1, ptr(diag, F))
    if rc:
        raise RuntimeError(f'ctl_life_run returned {rc}')
    result.diag = diag
    assert int(result.raster_n[0]) <= raster_cap and int(result.fate_n[0]) <= fate_cap
    return result


def run_tissue(lib, world, seed, **kwargs):
    """Use the ABI5 production wrapper against the explicitly supplied scratch library."""
    original = build.load
    try:
        build.load = lambda fast=False: lib
        return build.run(world, [seed], threads=1, abi=V, raster_cap=16384, fate_cap=1024, **kwargs)
    finally:
        build.load = original
