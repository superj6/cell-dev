"""Prepare the fixed registered Y panels/protocol without compiling or running lives.

Dry-run default. --prepare requires root registration; each panel is generated once
with the existing ordinary mutation helper. A partial generation claim cannot restart.
"""
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
STUDY = Path(__file__).resolve().parent
ROOT = STUDY.parents[1]
AUDIT = ROOT / "outputs/audit_visibility_gradient_20261014"
sys.path.insert(0, str(ROOT))

from common import read, save, sha  # noqa: E402
from measure import FOUNDER_SHA, PARENTS, SCOPE, stage_seeds  # noqa: E402

MUTATION = {"n_mut": 2, "p_cell": .5, "scale_n_mut": True, "dup_rate": 0, "del_rate": 0, "split": False}
BLOCKS = {"screen": 117, "confirm": 118, "calibration": 119}
MUTATION_RNG = {"D90": 53117, "L92": 53118}


def freeze_bytes(path, data):
    path.parent.mkdir(parents=True, exist_ok=True)
    if path.exists() and path.read_bytes() != data:
        raise ValueError("prepared input changed: " + str(path))
    path.write_bytes(data)


def preexpected_metadata():
    """Exact numerical_identity metadata subset, without its build/golden calls."""
    import platform

    import numpy as np
    import torch

    from src.checkpoint import libm_identity
    from src.life import build

    def digest(value):
        return hashlib.sha256(value).hexdigest()
    capability = torch.backends.cpu.get_cpu_capability()
    requested = os.environ.get("ATEN_CPU_CAPABILITY")
    if requested != "avx2" or capability != "AVX2":
        raise ValueError("preparation requires the same AVX2 pin as the worker")
    sources = {str(p.relative_to(ROOT)): sha(p) for p in sorted((ROOT / "src").rglob("*.py"))}
    sources["src/life/kernel.c"] = sha(build.SRC)
    rng = torch.Generator().manual_seed(45_000_001)
    noise = torch.randn(4096, generator=rng).numpy().tobytes()
    return {"torch": str(torch.__version__), "numpy": np.__version__, "python": platform.python_version(),
            "aten_cpu_capability": requested, "torch_cpu_capability": capability,
            "torch_build": digest(torch.__config__.show().encode()), "torch_noise_sha256": digest(noise),
            "libm": libm_identity(), "flags": {str(f): list(build.flags(f)) for f in (False, True)},
            "sources": sources}


def registration():
    value = read(STUDY / "registration.json")
    seeds = {stage: list(range(51_000_000 + 10_000 * BLOCKS[stage],
                              51_000_000 + 10_000 * BLOCKS[stage] + count))
             for stage, count in (("screen", 32), ("confirm", 512), ("calibration", 2))}
    if (value.get("status") != "registered" or value.get("world") != "catch_speck_blink20_20_l4"
            or value.get("seed_blocks") != BLOCKS or value.get("mutation_rng") != MUTATION_RNG
            or value.get("seeds") != seeds):
        raise ValueError("exact root world/seed registration required before panel generation")
    stage_seeds({"seeds": seeds})
    return value


def prepare():
    if any((STUDY / name).exists() for name in ("ready.json", "attempt.json", "budget.json", "measurement", "build-cache")):
        raise ValueError("released or executed preparation is immutable")
    registered = registration()  # Must precede mutation imports/calls.
    import numpy as np
    from numerical import identity as source_only_identity
    from omegaconf import OmegaConf
    from scoring import raw_sha

    from scripts.taskvar_gradient import make_mutants
    from src.genome import Layout
    from src.life import spec
    from src.life.evaluate import LifeEvaluator

    founder_receipt = read(AUDIT / "founders/manifest.json")
    world_snapshot = read(AUDIT / "approved_blink_world.json")
    world = spec.world("catch_speck_blink20_20_l4", T=1024)
    if asdict(world) != world_snapshot["production"]["world"]:
        raise ValueError("approved ABI4 world changed")
    inputs = STUDY / "inputs"
    for name in ("founders/manifest.json", "approved_blink_world.json", "final_namespace_inventory.json",
                 "final_namespace_review.json", "CONCRETE_PLAN.md", "concrete_plan.json"):
        freeze_bytes(inputs / "reviews" / Path(name).name, (AUDIT / name).read_bytes())
    for parent in PARENTS:
        prefix = inputs / parent
        source = AUDIT / "founders" / parent
        for path, digest in founder_receipt["founders"][parent]["output_sha256"].items():
            if sha(AUDIT / path) != digest:
                raise ValueError("extracted founder input changed")
        freeze_bytes(prefix / "parent.json", (source / "parent.json").read_bytes())
        freeze_bytes(prefix / "original_config.yaml", (source / "config.yaml").read_bytes())
        cfg = OmegaConf.load(source / "config.yaml")
        cfg.life.abi, cfg.life.world, cfg.life.T = 4, world.name, 1024
        cfg.life.T_choices, cfg.life.flags, cfg.life.t_open, cfg.life.freeze_frac = [], [], 0, None
        cfg.life.fast_kernel = True
        cfg.world, cfg.costs_life, cfg.envelope, cfg.threads = {}, {}, {"enabled": False}, 2
        layout, founder = Layout.load(prefix / "parent.json")
        evaluator = LifeEvaluator(cfg, layout)
        if raw_sha(founder.reshape(-1).float().numpy()) != FOUNDER_SHA[parent] or not evaluator.extinct_charge:
            raise ValueError("founder or production extinction policy changed")
        if asdict(evaluator.world()) != asdict(world):
            raise ValueError("derived world differs")
        freeze_bytes(prefix / "config.yaml", OmegaConf.to_yaml(cfg).encode())
    claim = STUDY / "panel_generation_claim.json"
    existing_claim = claim.exists()
    if not existing_claim:
        with claim.open("x") as stream:
            json.dump({"parents": list(PARENTS), "mutation_rng": MUTATION_RNG,
                       "mutation_helper_sha256": sha(ROOT / "scripts/taskvar_gradient.py"),
                       "registration_sha256": sha(STUDY / "registration.json")}, stream)
            stream.flush()
            os.fsync(stream.fileno())
    else:
        prior = read(claim)
        if (prior["parents"] != list(PARENTS) or prior["mutation_rng"] != MUTATION_RNG
                or prior["mutation_helper_sha256"] != sha(ROOT / "scripts/taskvar_gradient.py")
                or prior["registration_sha256"] != sha(STUDY / "registration.json")):
            raise ValueError("panel generation claim changed")
    row_hashes = {}
    for parent in PARENTS:
        prefix = inputs / parent
        if not existing_claim:
            table, operations = make_mutants(prefix / "parent.json", 64, MUTATION_RNG[parent])
            np.save(prefix / "genomes.npy", table, allow_pickle=False)
            save(prefix / "mutation_ops.json", operations)
            save(prefix / "panel_manifest.json", {
                "genomes_sha256": raw_sha(table), "mutants": 64,
                "parent_sha256": sha(prefix / "parent.json"), "config_sha256": sha(prefix / "config.yaml"),
                "mutation_ops_sha256": sha(prefix / "mutation_ops.json"), "mutation_seed": MUTATION_RNG[parent],
                "mutation_helper_sha256": sha(ROOT / "scripts/taskvar_gradient.py"), "mutation": MUTATION})
        elif any(not (prefix / name).is_file() for name in ("genomes.npy", "mutation_ops.json", "panel_manifest.json")):
            raise ValueError("partial generation claim; refuse regeneration or restart")
        table = np.load(prefix / "genomes.npy", allow_pickle=False)
        manifest = read(prefix / "panel_manifest.json")
        if (table.dtype != np.float32 or table.shape != (65, 875) or not np.isfinite(table).all()
                or raw_sha(table[0]) != FOUNDER_SHA[parent] or manifest["genomes_sha256"] != raw_sha(table)):
            raise ValueError("generated panel differs from fixed identity")
        row_hashes[parent] = [raw_sha(row) for row in table]
    metadata = preexpected_metadata()
    production = dict(metadata["sources"])
    production.update({"scripts/" + name: sha(ROOT / "scripts" / name) for name in
                       ("taskvar_confirm.py", "taskvar_gradient.py", "taskvar_gates.py")})
    pinned = [p for p in inputs.rglob("*") if p.is_file()]
    pinned += list(STUDY.glob("*.py")) + [STUDY / name for name in
                                         ("README.md", "SCHEMA.md", "registration.json", "panel_generation_claim.json")]
    protocol = {"study": "Y ordinary visibility gradient", "world_decision": "complete",
                "world": asdict(world), "monitor_scope": SCOPE, "founder_raw_sha256": FOUNDER_SHA,
                "seed_blocks": BLOCKS, "seeds": registered["seeds"], "mutation_rng": MUTATION_RNG,
                "panel_genotype_sha256": row_hashes, "numerical_identity": source_only_identity(),
                "calibration_rule": {"rate": "max(parent_two_seed_CPU,mutant1_two_seed_CPU)/2 per background",
                    "safety_multiplier": 1.5, "startup_screen_projection_ceiling": 3390,
                    "confirmation_projection_ceiling": 1990, "calibration_lives": 8,
                    "numerical_goldens": {"abi": 3, "seed": 11, "T": 200, "full": 1, "fast": 1}},
                "expected_startup_metadata": metadata, "production_pins": production,
                "file_pins": {str(p.relative_to(STUDY)): sha(p) for p in sorted(pinned)}}
    save(STUDY / "protocol.json", protocol)
    from measure import load_panels
    load_panels(protocol)  # Configuration/array validation only, no build or simulation.
    print(json.dumps({"status": "prepared_no_simulation", "protocol_sha256": sha(STUDY / "protocol.json"),
                      "panels_generated_now": 0 if existing_claim else 2,
                      "simulation_calls": 0, "compiled_libraries": 0}))


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--prepare", action="store_true")
    args = parser.parse_args()
    if not args.prepare:
        print(json.dumps({"status": "dry_run", "scope": SCOPE, "panels_generated": 0,
                          "requires": "root registration before fixed panel generation"}))
        return
    prepare()


if __name__ == "__main__":
    main()
