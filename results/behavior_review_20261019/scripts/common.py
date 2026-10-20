"""Shared setup for the 2026-10-19 behaviour review (read-only on the repo; writes under this folder)."""
import json, os, sys, time
from dataclasses import replace
from pathlib import Path
os.environ.setdefault("ATEN_CPU_CAPABILITY", "avx2")
ROOT = Path("/home/jgon/project/ml/cell-dev")
sys.path.insert(0, str(ROOT))
import numpy as np
import torch
from omegaconf import OmegaConf
from src.common import load_config
from src.evolve import setup
from src.life import build, spec, probe
from src.life.evaluate import life_seed
from src.life import handbuilt as hb

OUT = ROOT / "outputs" / "behavior_20261019"
cfg = load_config(str(ROOT / "configs" / "multitask.yaml"))
cfg.logging.output_dir = str(OUT / "unused")
_, layout, _, ev = setup(cfg)
ABI = ev.abi
SEL = json.load(open(ROOT / "results" / "multitask_20261018" / "selected_genomes.json"))
LINEAGES = ["AO_s7", "D90_Z_s5", "speck_s6", "speck_s8"]
STAGES = ["0", "125", "250"]
TRAIN = OmegaConf.to_container(cfg.life.training_tasks, resolve=True)
RES = OmegaConf.to_container(cfg.confirmation.reserved_tasks, resolve=True)
TASKS = {t["name"]: t for t in TRAIN + RES}
SEED_BASE = 45_919_000  # this review's own life seeds (outside study seed streams)


def genome(lin, stage):
    return layout.from_dict(SEL[lin][stage]["genome"]).detach().cpu().numpy().astype(np.float32).reshape(-1)


def world(task, T=None, **extra):
    w = ev._task_world(dict(name=task, world=TASKS[task]["world"], overrides=TASKS[task].get("overrides", {}),
                            weight=1), T)
    return replace(w, **extra) if extra else w


def seeds(n, offset=0):
    return [int(spec.hash64(SEED_BASE, 7, offset, i)) for i in range(n)]


def run(g, w, sd, threads=2, raster_cap=0, fate_cap=0, **kw):
    return build.run(w, sd, genomes=ABI.pack_genomes(np.asarray(g)[None], w.lattice), abi=ABI, threads=threads,
                     raster_cap=raster_cap, fate_cap=fate_cap, **kw)


class Org:
    """Minimal GrnBody-like wrapper for probe.trace with explicit ABI."""
    def __init__(self, name, g):
        self.name, self.genome, self.flags = name, g, 0
    def world(self, preset, **ov):
        return ov.pop("_w")
