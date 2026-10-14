"""Freeze and export the existing mutant-panel decoy protocol; never simulate or generate mutants."""
from __future__ import annotations

import hashlib
import json
import shutil
import sys
from dataclasses import asdict
from pathlib import Path

sys.dont_write_bytecode = True
HERE = Path(__file__).resolve().parent
ROOT = next(p for p in HERE.parents if (p / "src/life/spec.py").exists())
sys.path.insert(0, str(HERE))
sys.path.insert(0, str(ROOT))

import measure  # noqa: E402

PRIOR = ROOT / "results/pool_mutants_20261013"
F = ROOT / "results/discrimination_20261013"
G = ROOT / "outputs/autonomous_structural_20261013"
PUBLIC = ROOT / "results/decoy_gradient_20261014"


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def write(path, value):
    path.write_text(json.dumps(value, indent=2, allow_nan=False) + "\n")


def main():
    if (HERE / "ready.json").exists() or (HERE / "budget.json").exists():
        raise ValueError("study already released; do not rewrite preparation")
    prior = json.loads((PRIOR / "provenance.json").read_text())
    inputs = {"inputs/prior_provenance.json": PRIOR / "provenance.json",
              "inputs/F_protocol.json": F / "protocol.json"}
    original_sources = {}
    for parent in measure.PARENTS:
        mapping = {"parent.json": f"parents/{parent}/best_genome.json",
                   "config.yaml": f"parents/{parent}/config.yaml", "genomes.npy": f"genomes/{parent}_pool.npy",
                   "mutation_ops.json": f"genomes/{parent}_mutation_ops.json",
                   "original_screen_manifest.json": f"screens/{parent}_pool_T1024_b80/manifest.json"}
        for name, relative in mapping.items():
            source = PRIOR / relative
            if sha(source) != prior["artifacts"][relative]["sha256"]:
                raise ValueError("original archive artifact changed: " + relative)
            target = f"inputs/{parent}/{name}"
            inputs[target], original_sources[target] = source, relative
    for relative, source in inputs.items():
        target = HERE / relative
        target.parent.mkdir(parents=True, exist_ok=True)
        shutil.copyfile(source, target)
    identity = prior["numerical_identity"]
    for relative, expected in identity["sources"].items():
        if sha(ROOT / relative) != expected:
            raise ValueError("numerical/search source changed: " + relative)
    world = asdict(measure.spec.world("catch_speck_l4", **measure.WORLD_OVERRIDES))
    if world != json.loads((F / "protocol.json").read_text())["world"]:
        raise ValueError("world differs from completed F measurement")
    dependencies = {str(folder.relative_to(ROOT)): {name: sha(folder / name)
                                                   for name in ("protocol.json", "run_budgeted.py")}
                    for folder in (G,)}
    protocol = {"status": "prepared_not_released", "study": "fixed_decoy_mutant_gradient",
                "world": world, "parents": list(measure.PARENTS), "mutants_per_parent": 64,
                "new_mutants_generated": 0, "seed_blocks": measure.BLOCKS, "seeds": measure.stage_seeds(),
                "lives_per_row": measure.LIVES, "scientific_genome_lives": 11328,
                "life_accounting": {"screen": 4160, "rescore": 5120, "confirm": 2048},
                "startup_validation": "E1 full/fast golden pair; separate from scientific lives, inside CPU cap",
                "max_cpu_seconds": 3600, "simulation_workers": 2,
                "input_sha256": {relative: sha(HERE / relative) for relative in inputs},
                "original_archive_paths": original_sources,
                "source_identity": identity["sources"], "expected_numerical_identity": identity,
                "helpers": {name: sha(ROOT / "scripts" / name) for name in measure.HELPERS},
                "dependencies": dependencies,
                "selection": {"screen": "Top four mutant rows by mean F; exact ties use ascending original row",
                              "rescore": "One highest mean-F mutant among those four; ties use original row",
                              "freeze": "Both winners are frozen before either independent confirmation",
                              "negative_results": "Selected mutant retained even below parent; no extensions"},
                "primary": "Fresh confirmation winner minus original parent, per parent, paired mean and SE",
                "thresholds": {"positive": "mean > 3 SE", "practical": "mean >= 0.5 F",
                               "use": "Descriptive diagnostic only; no automatic admission or selection change"},
                "reporting": ["capture income", "poison-click costs", "miss costs", "other costs",
                              "guard/extinction charges", "end cells", "hidden end cells", "clicks", "captures"],
                "failure_policy": "Keep valid guards and their penalties; invalid/capacity/mismatch blocks inference",
                "budget_policy": "One shared cap across all stages; no automatic restart or budget reset",
                "limits": ["The whole preexisting panel is reused without consulting its other-world outcomes.",
                           "Two backgrounds and 64 mutants each do not estimate general evolvability.",
                           "Information-controller behavior never enters any organism.",
                           "No world admission, prices, ABI or organism rule change follows automatically."]}
    write(HERE / "protocol.json", protocol)
    measure.load_inputs(HERE)
    ready = {"format": 1, "files": {name: sha(HERE / name) for name in
                                     ("protocol.json", "measure.py", "run_budgeted.py", "prepare.py",
                                      "prereg_draft.md", "test_prepared.py")},
             "operator_release_required": True}
    write(HERE / "ready.template.json", ready)
    PUBLIC.mkdir(parents=True, exist_ok=True)
    for path in (HERE / "inputs").rglob("*"):
        if path.is_file():
            destination = PUBLIC / path.relative_to(HERE)
            destination.parent.mkdir(parents=True, exist_ok=True)
            shutil.copyfile(path, destination)
    for name in ("protocol.json", "measure.py", "run_budgeted.py", "prepare.py", "prereg_draft.md",
                 "test_prepared.py", "README.md", "ready.template.json"):
        shutil.copyfile(HERE / name, PUBLIC / name)
    for relative in protocol["source_identity"]:
        target = PUBLIC / "sources" / relative
        target.parent.mkdir(parents=True, exist_ok=True)
        shutil.copyfile(ROOT / relative, target)
    for name in measure.HELPERS:
        target = PUBLIC / "sources/scripts" / name
        target.parent.mkdir(parents=True, exist_ok=True)
        shutil.copyfile(ROOT / "scripts" / name, target)
    artifacts = {str(p.relative_to(PUBLIC)): {"sha256": sha(p), "bytes": p.stat().st_size}
                 for p in sorted(PUBLIC.rglob("*")) if p.is_file() and p.name != "preparation_provenance.json"}
    write(PUBLIC / "preparation_provenance.json", {"status": "prepared_not_released", "artifacts": artifacts,
                                                 "simulation_lives": 0, "new_mutants_generated": 0})
    print(json.dumps({"status": "prepared_not_released", "artifacts": len(artifacts), "simulation_lives": 0,
                      "research_lives_planned": 11328, "source_pins": len(protocol["source_identity"])}))


if __name__ == "__main__":
    main()
