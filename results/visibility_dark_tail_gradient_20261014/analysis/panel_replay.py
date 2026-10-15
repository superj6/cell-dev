"""Replay retained Y point-mutation records only; no fresh genetics or lives."""

from __future__ import annotations

import hashlib
import importlib.util
import json
import os
import sys
from pathlib import Path

os.environ.setdefault("ATEN_CPU_CAPABILITY", "avx2")
os.environ.setdefault("OMP_NUM_THREADS", "1")
os.environ.setdefault("MKL_NUM_THREADS", "1")
sys.dont_write_bytecode = True

import numpy as np  # noqa: E402

HELPER_SHA = "8fd717bdecb5f0e073e04838bbf286a4a968924bc9848b55c5a8d2b2055f4139"
HERE = Path(__file__).resolve().parent


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def raw(value):
    return hashlib.sha256(np.asarray(value).tobytes()).hexdigest()


def audit(base, protocol, external):
    """Validate every row by replaying the already-recorded float32 additions."""
    base = Path(base).resolve()
    helper_path = HERE / "helpers/genetics.py"
    if sha(helper_path) != HELPER_SHA:
        raise ValueError("recorded-operation helper changed")
    source_root = external(base, "src/genome.py").parents[1]
    sys.path.insert(0, str(source_root))
    for name in ("src/__init__.py", "src/genome.py", "src/lattice.py", "src/life/__init__.py", "src/life/spec.py"):
        if sha(source_root / name) != protocol["production_pins"][name]:
            raise ValueError("genome definition source differs")
    spec = importlib.util.spec_from_file_location("AG_recorded_genetics", helper_path)
    helper = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(helper)
    import torch
    from omegaconf import OmegaConf

    from src.genome import Layout

    torch.set_num_threads(1)
    results = {}
    for background in ("D90", "L92"):
        folder = base / "inputs/Y/inputs" / background
        layout, founder = Layout.load(folder / "parent.json")
        table = np.load(folder / "genomes.npy", allow_pickle=False)
        if table.dtype != np.float32 or table.shape != (65, 875) or not np.isfinite(table).all():
            raise ValueError("complete unchanged original panel required")
        operations = json.loads((folder / "mutation_ops.json").read_text())
        if len(operations) != 64 or any(set(item) != {"mut"} for item in operations):
            raise ValueError("all64 ordinary recorded point mutations required")
        reconstructed = np.stack(
            [founder.numpy()] + [helper.point_mutation(layout, founder, item).numpy() for item in operations]
        )
        if reconstructed.dtype != table.dtype or reconstructed.tobytes() != table.tobytes():
            raise ValueError("retained panel does not replay bitwise")
        rows = [raw(row) for row in table]
        if rows != protocol["panel_genotype_sha256"][background]:
            raise ValueError("replayed panel differs from protocol")
        old_config = OmegaConf.to_container(OmegaConf.load(folder / "config.yaml"), resolve=True)
        config = OmegaConf.to_container(OmegaConf.load(base / f"configs/flash5_dark_{background}.yaml"), resolve=True)
        expected = __import__("copy").deepcopy(old_config)
        changes = protocol["configuration_changes"]
        expected["life"]["world"] = changes["life.world"]
        expected["life"]["abi"] = changes["life.abi"]
        expected["world"] = changes["world"]
        if config != expected or config["life"]["abi"] != 4:
            raise ValueError("derived configuration changed beyond exact AD/ABI4 fields")
        results[background] = {
            "rows": 65,
            "shape": [65, 875],
            "dtype": "float32",
            "all_rows_bitwise_equal": True,
            "raw_sha256": raw(table),
            "row_raw_sha256": rows,
            "recorded_point_mutations": sum(len(item["mut"]) for item in operations),
            "duplicate_rows_retained": 65 - len({row.tobytes() for row in table}),
            "file_pins": {
                str((folder / name).relative_to(base)): sha(folder / name)
                for name in ("parent.json", "genomes.npy", "mutation_ops.json", "panel_manifest.json")
            },
        }
    loaded = {}
    for name, module in tuple(sys.modules.items()):
        if name == "src" or name.startswith("src."):
            path = Path(module.__file__).resolve()
            relative = str(path.relative_to(source_root))
            if sha(path) != protocol["production_pins"][relative]:
                raise ValueError("loaded genome definition differs from pinned closure")
            if name not in {"src", "src.genome", "src.lattice", "src.life", "src.life.spec"}:
                raise ValueError("unneeded production module loaded during recorded genetic replay: " + name)
            loaded[relative] = sha(path)
    return {
        "status": "passed",
        "protocol_sha256": sha(base / "protocol.json"),
        "script_sha256": sha(__file__),
        "helper_sha256": HELPER_SHA,
        "loaded_definition_pins": loaded,
        "backgrounds": results,
        "random_draws": 0,
        "simulation_calls": 0,
        "compilation_calls": 0,
        "limitation": "Recorded additions and pinned Layout semantics; no RNG or life-dynamics replay.",
    }
