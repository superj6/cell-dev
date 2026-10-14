"""Config loading, seeding, device resolution, structured logging (same pattern as latent-memory)."""
from __future__ import annotations

import json
import random
import sys
from pathlib import Path
from typing import Any, Optional, Sequence

import numpy as np
import torch
from omegaconf import DictConfig, OmegaConf

repo_root = Path(__file__).resolve().parents[1]
if str(repo_root) not in sys.path:
    sys.path.insert(0, str(repo_root))


def log_event(**payload: Any) -> None:
    print(json.dumps(payload, default=str), flush=True)


def load_config(path: str, overrides: Optional[Sequence[str]] = None) -> DictConfig:
    """Load a YAML config, following ``extends`` chains; apply ``key=value`` dotlist overrides last."""
    config_path = Path(path).resolve()
    cfg = OmegaConf.load(config_path)
    if cfg.get("extends"):
        candidate = (config_path.parent / cfg.extends).resolve()
        if not candidate.exists():
            candidate = (repo_root / cfg.extends).resolve()
        cfg = OmegaConf.merge(load_config(str(candidate)), cfg)
    if overrides:
        cfg = OmegaConf.merge(cfg, OmegaConf.from_dotlist(list(overrides)))
    return cfg


def set_seed(seed: int) -> None:
    random.seed(seed)
    np.random.seed(seed)
    torch.manual_seed(seed)


def resolve_device(name: Optional[str]) -> torch.device:
    if not name:
        name = "cuda" if torch.cuda.is_available() else "cpu"
    if name.startswith("cuda") and not torch.cuda.is_available():
        name = "cpu"
    return torch.device(name)
