"""AG prepared-input check and recorded-operation replay; no engine calls."""

import argparse
import ast
import hashlib
import importlib.util
import json
import sys
from pathlib import Path

sys.dont_write_bytecode = True
HERE = Path(__file__).resolve().parent


def module(name, path):
    spec = importlib.util.spec_from_file_location(name, path)
    value = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(value)
    return value


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def normalized(path):
    tree = ast.parse(path.read_text())
    assert isinstance(tree.body[0], ast.Expr) and isinstance(tree.body[0].value, ast.Constant)
    tree.body.pop(0)
    for node in tree.body:
        if isinstance(node, ast.Assign) and isinstance(node.targets[0], ast.Name) and node.targets[0].id == "PROTOCOL_SHA":
            node.value = ast.Constant(value=None)
    return ast.dump(tree, include_attributes=False)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--study", type=Path, required=True)
    parser.add_argument("--out", type=Path, required=True)
    args = parser.parse_args()
    base = args.study.resolve()
    sources = HERE / "analysis" if (HERE / "analysis/analyze.py").is_file() else HERE
    history = HERE / "analysis_history" if (HERE / "analysis_history").is_dir() else HERE / "history"
    reader = module("AG_actual_bound_reader", sources / "analyze.py")
    p, panels = reader.verify_protocol(base)
    replay = module("AG_actual_bound_replay", sources / "panel_replay.py").audit(base, p, reader.external)
    assert sum(x["rows"] for x in replay["backgrounds"].values()) == 130
    assert sum(x["recorded_point_mutations"] for x in replay["backgrounds"].values()) == 256
    assert normalized(sources / "analyze.py") == normalized(history / "analyze.py.unbound.txt")
    absent = ("ready.json", "attempt.json", "budget.json", "measurement", "logs", "build-cache")
    assert all(not (base / name).exists() for name in absent)
    forbidden = {"src.life.build", "src.life.evaluate", "src.checkpoint", "src.run", "src.evolve"}
    assert not (forbidden & set(sys.modules))
    summary, vectors = reader.analyze(base)
    assert summary["status"] == "incomplete" and summary["scientific_outcomes_emitted"] is False and not vectors
    assert "ready.json" in summary["error"]
    result = {
        "status": "passed_prepared_unreleased",
        "protocol_sha256": reader.PROTOCOL_SHA,
        "local_pins": len(p["file_pins"]),
        "production_pins": len(p["production_pins"]),
        "panel_rows": sum(len(x) for x in panels.values()),
        "historical_timing_rows": 130,
        "abi": p["abi"],
        "world_keys": len(p["world_packing"]["keys"]),
        "derived_configs": 2,
        "configuration_changes": p["configuration_changes"],
        "all_reader_AST_unchanged_except_protocol_and_docstring": True,
        "unreleased_entrypoint": summary,
        "retained_input_replay": replay,
        "runtime_paths_absent": list(absent),
        "activity": {"simulation_calls": 0, "compilation_calls": 0, "random_draws": 0},
        "source_pins": {name: sha(sources / name) for name in
                        ("analyze.py", "offline_accounting.py", "panel_replay.py", "helpers/genetics.py")},
        "check_source_sha256": sha(Path(__file__)),
    }
    args.out.mkdir(parents=True, exist_ok=True)
    for name, value in (("actual_bound_input_review.json", result), ("panel_replay.json", replay)):
        target = args.out / name
        assert not target.exists()
        target.write_text(json.dumps(value, indent=2, allow_nan=False) + "\n")
    print(json.dumps({k: v for k, v in result.items() if k != "retained_input_replay"}, indent=2))


if __name__ == "__main__":
    main()
