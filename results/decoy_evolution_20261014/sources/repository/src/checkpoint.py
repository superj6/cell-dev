"""Atomic life-search checkpoints and strict numerical replay pins (outside the organism)."""
from __future__ import annotations

import ctypes
import hashlib
import json
import os
import platform
import tempfile
from pathlib import Path

import numpy as np
import torch
from omegaconf import OmegaConf

ROOT = Path(__file__).resolve().parents[1]
FORMAT = 1
LOGS = ("curves.jsonl", "lineage.jsonl", "clones.jsonl")


def sha(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def config_identity(cfg) -> dict:
    """The search and its diagnostic schedule are fixed; output location and save frequency may change."""
    obj = OmegaConf.to_container(cfg, resolve=True)
    obj.pop("extends", None)
    obj["logging"].pop("output_dir", None)
    obj["logging"].pop("checkpoint_every", None)
    return obj


def libm_identity() -> dict:
    """Identify glibc's actual IFUNC choices by object-relative addresses, including its FMA paths."""
    class DlInfo(ctypes.Structure):
        _fields_ = [("fname", ctypes.c_char_p), ("base", ctypes.c_void_p),
                    ("sname", ctypes.c_char_p), ("saddr", ctypes.c_void_p)]

    libm = ctypes.CDLL("libm.so.6")
    dladdr = ctypes.CDLL(None).dladdr
    dladdr.argtypes, dladdr.restype = [ctypes.c_void_p, ctypes.POINTER(DlInfo)], ctypes.c_int
    offsets, objects = {}, {}
    for name in ("exp", "log", "sin", "cos", "pow", "atan2", "hypot", "fma"):
        addr = ctypes.cast(getattr(libm, name), ctypes.c_void_p).value
        info = DlInfo()
        if not dladdr(addr, ctypes.byref(info)):
            raise RuntimeError(f"cannot identify libm implementation: {name}")
        path = Path(os.fsdecode(info.fname))
        objects[path.name] = sha(path.read_bytes())
        offsets[name] = {"object": path.name, "offset": addr - info.base}
    return {"objects": objects, "implementations": offsets, "libc": list(platform.libc_ver()),
            "glibc_tunables": os.environ.get("GLIBC_TUNABLES", "")}


def golden_life() -> dict:
    """Replay the existing ring-1 CATCH truth life (commit 8395c12), then compare the fast ledger."""
    from src.life import build, spec

    v = spec.V3
    program = v.pack_program(v.theta(w0=1, kappa=1, t_ref=4, tau_m=2),
                             alone=v.theta(g_r=1, emit0=1, tau_m=2, t_ref=1),
                             juvenile=v.theta(g_r=0.55, emit0=1, tau_m=2, t_ref=1),
                             rim=v.theta(tau_m=2, t_ref=1))
    sites = [(a, b) for a in range(-1, 2) for b in range(-1, 2) if max(abs(a), abs(b), abs(a + b)) <= 1]
    rows = v.PROGRAM_ROW
    body = [(a, b, 0, rows["juvenile"] if (a, b) == (0, 0) else rows["alone"]) for a, b in sites]
    body += [(a, b, 1, rows["contact"]) for a, b in sites]
    world = spec.world("catch_v1_l2", T=200, flags=v.flags("program_mode"))
    kw = dict(programs=program, init=body, kind="hexprism", abi=v, threads=1)
    full = build.run(world, [11], **kw)
    expected = "ebb3ad6fcad2d938"
    actual = f"{int(full.hashes[0, 0]):016x}"
    if actual != expected:
        raise RuntimeError(f"golden life mismatch: {actual} != {expected}; check libm/FMA and kernel")
    fast = build.run(world, [11], fast=True, **kw)
    if full.ledger.tobytes() != fast.ledger.tobytes():
        raise RuntimeError("golden life: fast and full kernel ledgers differ")
    return {"all": actual, "ledger_sha256": sha(full.ledger.tobytes())}


def numerical_identity() -> dict:
    from src.life import build

    capability = torch.backends.cpu.get_cpu_capability()
    requested = os.environ.get("ATEN_CPU_CAPABILITY")
    if requested != "avx2" or capability != "AVX2":
        raise RuntimeError("life runs require ATEN_CPU_CAPABILITY=avx2 before importing torch; restart the process")
    # Pin search code too: a resume must not silently change mutation, selection or fitness.
    sources = {str(p.relative_to(ROOT)): sha(p.read_bytes())
               for p in sorted((ROOT / "src").rglob("*.py"))}
    sources["src/life/kernel.c"] = sha(build.SRC.read_bytes())
    rng = torch.Generator().manual_seed(45_000_001)
    noise = torch.randn(4096, generator=rng).numpy().tobytes()
    return {"torch": str(torch.__version__), "numpy": np.__version__, "python": platform.python_version(),
            "aten_cpu_capability": requested, "torch_cpu_capability": capability,
            "torch_build": sha(torch.__config__.show().encode()), "torch_noise_sha256": sha(noise),
            "libm": libm_identity(), "kernels": {str(f): sha(build.build(fast=f).read_bytes()) for f in (False, True)},
            "flags": {str(f): list(build.flags(f)) for f in (False, True)},
            "sources": sources, "golden": golden_life()}


def load(path: Path) -> dict:
    payload = torch.load(path, map_location="cpu", weights_only=True)
    if payload.get("format") != FORMAT:
        raise ValueError("unsupported checkpoint format")
    return payload


def validate(payload: dict, cfg, identity: dict) -> None:
    if payload["config"] != config_identity(cfg):
        raise ValueError("checkpoint configuration differs; keep the original target generations and search settings")
    if payload["identity"] != identity:
        changed = [key for key in identity if payload["identity"].get(key) != identity[key]]
        raise ValueError(f"checkpoint determinism pins differ: {', '.join(changed)}")


def log_offsets(out: Path) -> dict:
    """Flushers run before this call; fsync logs before making a checkpoint that refers to them."""
    offsets = {}
    for name in LOGS:
        path = out / name
        if path.exists():
            with path.open("rb") as fh:
                data = fh.read()
                os.fsync(fh.fileno())
            offsets[name] = {"bytes": len(data), "sha256": sha(data)}
    return offsets


def restore_logs(out: Path, offsets: dict) -> None:
    """Verify every prefix before truncating any tail left by a crash after the last checkpoint."""
    for name, meta in offsets.items():
        path = out / name
        if not path.exists():
            raise ValueError(f"checkpoint log missing: {path}")
        with path.open("rb") as fh:
            prefix = fh.read(meta["bytes"])
        if len(prefix) != meta["bytes"] or sha(prefix) != meta["sha256"]:
            raise ValueError(f"checkpoint log prefix differs: {path}")
    for name, meta in offsets.items():
        with (out / name).open("r+b") as fh:
            fh.truncate(meta["bytes"])


def save(path: Path, *, cfg, identity: dict, state: dict) -> None:
    payload = {"format": FORMAT, "config": config_identity(cfg), "identity": identity,
               "state": state, "logs": log_offsets(path.parent)}
    fd, tmp = tempfile.mkstemp(prefix=".checkpoint-", suffix=".pt", dir=path.parent)
    try:
        with os.fdopen(fd, "wb") as fh:
            torch.save(payload, fh)
            fh.flush()
            os.fsync(fh.fileno())
        os.replace(tmp, path)
        directory = os.open(path.parent, os.O_RDONLY | os.O_DIRECTORY)
        try:
            os.fsync(directory)
        finally:
            os.close(directory)
    finally:
        if os.path.exists(tmp):
            os.unlink(tmp)


def write_identity(out: Path, identity: dict) -> None:
    (out / "determinism.json").write_text(json.dumps(identity, indent=2, sort_keys=True) + "\n")
