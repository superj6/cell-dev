"""Review prepared AK metadata once; no wait, compilation, simulation or genetic draws."""
from __future__ import annotations

import argparse
import ast
import hashlib
import importlib.util
import json
import sys
from dataclasses import asdict
from pathlib import Path

import numpy as np

sys.dont_write_bytecode = True
ROOT = next(p for p in Path(__file__).resolve().parents if (p / "src/life/spec.py").is_file())
STUDY = ROOT / "outputs/autonomous_retention_frontier_20261015"
ANALYZER_SHA = "45b5b47cba510f355d16f88241a9d98aa662867c48b0420b8452c8765e5a97fc"


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def read(path):
    return json.loads(Path(path).read_text())


def review(study):
    path = study / "analyze.py"
    if sha(path) != ANALYZER_SHA:
        raise ValueError("frozen reviewed analyzer changed")
    definition = importlib.util.spec_from_file_location("ak_frozen_reader", path)
    analyzer = importlib.util.module_from_spec(definition)
    definition.loader.exec_module(analyzer)
    protocol = analyzer.verify_protocol(study)
    # Validate original evidence and review files too, beyond the analyzer's portable copied-input closure.
    for key in ("original_input_pins", "review_pins"):
        for name, digest in protocol[key].items():
            if sha(analyzer.external(study, name)) != digest:
                raise ValueError("changed " + key + ": " + name)
    acceptance = read(study / "preparation_acceptance.json")
    if (acceptance["status"] != "accepted_by_root" or acceptance["source_pins"] != protocol["source_pins"]
            or acceptance["review_pins"] != protocol["review_pins"]):
        raise ValueError("actual preparation differs from reviewed root acceptance")
    mappings = {record["path"]: record["source"] for record in protocol["genomes"]}
    mappings.update({
        "inputs/config.yaml": "results/exploratory_reserve_replication_20261014/runs/control/config.yaml",
        "inputs/pool_config.yaml": "results/s7_continuation_20261014/runs/s51892/config.yaml",
        "inputs/persistent_protocol.json": "results/exploratory_reserve_replication_20261014/protocol.json",
        "inputs/startup_identity.json": "results/visibility_dark_tail_gradient_20261014/startup_identity.json",
        "inputs/seed_audit.json": acceptance["seed_audit_path"],
    })
    for copied, original in mappings.items():
        if sha(study / copied) != sha(analyzer.external(study, original)):
            raise ValueError("copied input differs bytewise: " + copied)
    fixture = read(study / "inputs/visibility_truth.json")
    original_truth = analyzer.external(study, "results/abi4_visibility_20261014/final_truth/truth.json")
    expected = next(c for c in read(original_truth)["cases"] if c["name"] == "body0_renewal_55040000")
    if fixture != expected:
        raise ValueError("copied visibility fixture differs from the exact retained case")
    if set(protocol["input_pins"]) != set(mappings) | {"inputs/visibility_truth.json"}:
        raise ValueError("unexpected copied-input set")

    # Only import the metadata module. Do not import build/evaluate/checkpoint or invoke a golden.
    sys.path.insert(0, str(ROOT))
    from src.life import spec

    if Path(spec.__file__).resolve() != ROOT / "src/life/spec.py":
        raise ValueError("metadata spec resolved outside the pinned source closure")
    # Execute exactly the frozen worker's world-construction prefix, ending before kwargs/build.run.
    tree = ast.parse((study / "measure.py").read_text())
    function = next(n for n in tree.body if isinstance(n, ast.FunctionDef) and n.name == "check_visibility_truth")
    prefix = []
    for node in function.body:
        if isinstance(node, (ast.Import, ast.ImportFrom)):
            continue
        if isinstance(node, ast.Assign) and any(isinstance(t, ast.Name) and t.id == "kwargs" for t in node.targets):
            break
        prefix.append(node)
    if any(isinstance(n, ast.Name) and n.id == "build" for node in prefix for n in ast.walk(node)):
        raise ValueError("world-construction prefix unexpectedly refers to the engine")
    environment = {"read": read, "STUDY": study, "spec": spec}
    exec(compile(ast.Module(body=prefix, type_ignores=[]), str(study / "measure.py"), "exec"), environment)
    world = environment["world"]
    integers = (*spec.INT_WORLD_KEYS, "flags", "fork_flags")
    if any(type(getattr(world, key)) is not int for key in integers):
        raise ValueError("retained fixture integer fields were not reconstructed as integers")
    vector = spec.V4.pack_world(world)  # Pure validation and float64 packing, no foreign call.
    if not np.array_equal(vector, np.asarray(fixture["body"]["world_vec"], dtype=np.float64)):
        raise ValueError("reconstructed visibility world differs from its retained packed vector")
    if (world.visibility_mode, world.visibility_on, world.visibility_off, world.visibility_low) != (2, 20, 20, 0):
        raise ValueError("retained fixture is not the approved renewal truth case")
    forbidden = [name for name in sys.modules if name in (
        "src.life.build", "src.life.evaluate", "src.checkpoint", "src.evolve", "src.run")]
    if forbidden:
        raise ValueError("an engine/search module was imported: " + str(forbidden))
    runtime = [name for name in ("release.json", "attempt.json", "budget.json", "raw", "build-cache",
                                 "startup.json", "measurement_complete.json") if (study / name).exists()]
    if runtime:
        raise ValueError("prelaunch metadata review found runtime files: " + str(runtime))
    return {
        "status": "passed_prepared_inputs_no_runtime", "protocol_sha256": sha(study / "protocol.json"),
        "analyzer_sha256": ANALYZER_SHA, "script_sha256": sha(Path(__file__)),
        "input_pins": protocol["input_pins"], "original_input_pins": protocol["original_input_pins"],
        "production_pins": protocol["production_pins"], "source_pins": protocol["source_pins"],
        "review_pins": protocol["review_pins"], "copied_bytewise_inputs": mappings,
        "preparation_acceptance_sha256": sha(study / "preparation_acceptance.json"),
        "genomes": protocol["genomes"], "roles": protocol["roles"],
        "worlds": {name: {"abi": rec["abi"], "packed_values": len(rec["world_vector"]),
                          "ledger_columns": len(rec["ledger_columns"])} for name, rec in protocol["worlds"].items()},
        "fixture": {"name": fixture["name"], "seed": fixture["seed"], "integer_fields": list(integers),
                    "reconstructed_world": asdict(world),
                    "world_vector_sha256": hashlib.sha256(vector.tobytes()).hexdigest(),
                    "construction": "exact frozen worker prefix; execution stops before engine kwargs/build call"},
        "counts": {"research_lives_planned": 3072, "startup_lives_planned": 4,
                   "genetic_draws": 0, "compiled_libraries": 0, "simulation_calls": 0},
        "runtime_files_present": runtime,
    }


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--study", type=Path, default=STUDY)
    parser.add_argument("--out", type=Path, default=Path(__file__).with_name("actual_input_review.json"))
    args = parser.parse_args()
    if args.out.exists():
        raise ValueError("preserve the previous review; choose a new output path")
    result = review(args.study.resolve())
    args.out.parent.mkdir(parents=True, exist_ok=True)
    with args.out.open("x") as stream:
        stream.write(json.dumps(result, indent=2, allow_nan=False) + "\n")
    print(json.dumps({"status": result["status"], "protocol_sha256": result["protocol_sha256"],
                      "review_sha256": sha(args.out), "simulation_calls": 0}))


if __name__ == "__main__":
    main()
