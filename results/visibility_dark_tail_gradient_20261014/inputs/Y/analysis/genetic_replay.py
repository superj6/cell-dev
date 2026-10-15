"""Replay registered ordinary mutation panels without compiling or simulating lives."""
from __future__ import annotations

import argparse
import hashlib
import json
import os
import sys
from dataclasses import asdict
from pathlib import Path

os.environ.setdefault("ATEN_CPU_CAPABILITY", "avx2")
sys.dont_write_bytecode = True
PROTOCOL_SHA256 = "1880ff6e21b4689031e892d9dc6765a8d9673a35efeefb213acf268f5370adf4"


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def read(path):
    return json.loads(Path(path).read_text())


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--study", type=Path, required=True)
    parser.add_argument("--out", type=Path, required=True)
    args = parser.parse_args()
    base = args.study.resolve()
    if args.out.exists() or sha(base / "protocol.json") != PROTOCOL_SHA256:
        raise ValueError("fresh replay receipt and exact reviewed protocol required")
    protocol = read(base / "protocol.json")
    # The published bundle carries the exact importable source closure under production/.
    source_root = next((root for root in (base / "production", *base.parents)
                        if (root / "src/life/spec.py").is_file()), None)
    if source_root is None:
        raise ValueError("missing pinned production source bundle")
    sys.path.insert(0, str(source_root))
    for root, table in ((base, protocol["file_pins"]), (source_root, protocol["production_pins"])):
        for name, expected in table.items():
            path = (root / name).resolve()
            if not path.is_relative_to(root.resolve()) or sha(path) != expected:
                raise ValueError("changed pinned input: " + name)
    import numpy as np
    import torch
    from omegaconf import OmegaConf

    from src.life import build

    prohibited = {"simulation_calls": 0, "compilation_calls": 0}

    def no_simulation(*args, **kwargs):
        prohibited["simulation_calls"] += 1
        raise RuntimeError("genetic replay prohibits life simulation")

    def no_compilation(*args, **kwargs):
        prohibited["compilation_calls"] += 1
        raise RuntimeError("genetic replay prohibits kernel compilation")

    build.run, build.build = no_simulation, no_compilation
    from scripts.taskvar_gradient import make_mutants
    from src.genome import Layout
    from src.life.evaluate import LifeEvaluator

    results = {}
    for parent in ("D90", "L92"):
        prefix = base / "inputs" / parent
        expected = np.load(prefix / "genomes.npy", allow_pickle=False)
        table, operations = make_mutants(prefix / "parent.json", 64, protocol["mutation_rng"][parent])
        if (table.dtype != np.float32 or table.shape != (65, 875)
                or table.tobytes() != expected.tobytes()):
            raise ValueError("whole generated panel does not replay: " + parent)
        if json.loads(json.dumps(operations)) != read(prefix / "mutation_ops.json"):
            raise ValueError("recorded mutation operations do not replay: " + parent)
        layout, founder = Layout.load(prefix / "parent.json")
        if table[0].tobytes() != founder.reshape(-1).float().numpy().tobytes():
            raise ValueError("replay changed original founder")
        evaluator = LifeEvaluator(OmegaConf.load(prefix / "config.yaml"), layout)
        if (evaluator.abi.version != 4 or not evaluator.extinct_charge or evaluator.threads != 2
                or evaluator.T_choices or evaluator.has_envelope or asdict(evaluator.world()) != protocol["world"]):
            raise ValueError("derived config does not produce registered ABI4 world")
        results[parent] = {
            "mutation_rng": protocol["mutation_rng"][parent], "rows": 65, "columns": 875,
            "dtype": "float32", "all_rows_byte_identical": True, "recorded_operations_equal": True,
            "config_world_equal": True, "abi": 4, "extinct_charge": True, "threads": 2,
            "raw_row_sha256": [hashlib.sha256(row.tobytes()).hexdigest() for row in table],
            "file_pins": {str((prefix / name).relative_to(base)): sha(prefix / name) for name in
                          ("parent.json", "genomes.npy", "mutation_ops.json", "panel_manifest.json", "config.yaml")},
            "duplicate_rows_retained": 65 - len({row.tobytes() for row in table}),
        }
    receipt = {
        "status": "pass", "protocol_sha256": PROTOCOL_SHA256, "registration_sha256": sha(base / "registration.json"),
        "script_sha256": sha(__file__), "production_pins": protocol["production_pins"],
        "simulation_calls": prohibited["simulation_calls"], "compilation_calls": prohibited["compilation_calls"],
        "mutation_replay_calls": 2, "torch": str(torch.__version__), "numpy": np.__version__,
        "aten_cpu_capability": os.environ.get("ATEN_CPU_CAPABILITY"),
        "torch_cpu_capability": torch.backends.cpu.get_cpu_capability(), "backgrounds": results,
        "limitation": "Independent invocation of the same pinned ordinary mutation operator; not an independently rewritten mutation implementation.",
    }
    args.out.parent.mkdir(parents=True, exist_ok=True)
    args.out.write_text(json.dumps(receipt, indent=2, allow_nan=False) + "\n")
    print(json.dumps({"status": "pass", "rows_replayed": 130, **prohibited, "receipt_sha256": sha(args.out)}))


if __name__ == "__main__":
    main()
