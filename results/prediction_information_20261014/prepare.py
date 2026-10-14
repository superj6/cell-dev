"""Freeze a source-pinned four-life calibration and audit unused V seed namespaces; no simulation."""
from __future__ import annotations
import hashlib
import importlib.util
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
STUDY = Path(__file__).resolve().parent


def load_measure():
    module_spec = importlib.util.spec_from_file_location("prediction_information_measure", STUDY / "measure.py")
    module = importlib.util.module_from_spec(module_spec)
    module_spec.loader.exec_module(module)
    return module


def namespace_audit():
    targets = [(52_080_000, 52_080_511), (52_090_000, 52_090_001)]
    matches, files, unreadable = [], 0, []

    def walk(value, trail, path):
        if isinstance(value, dict):
            for key, child in value.items():
                walk(child, trail + [str(key)], path)
        elif isinstance(value, list):
            for index, child in enumerate(value):
                walk(child, trail + [str(index)], path)
        elif isinstance(value, int) and not isinstance(value, bool):
            if any(lo <= value <= hi for lo, hi in targets):
                matches.append({"path": path, "field": ".".join(trail), "value": value})

    for top in (ROOT / "results", ROOT / "outputs"):
        for path in sorted(top.rglob("*.json")):
            if path.is_relative_to(STUDY):
                continue
            try:
                value = json.loads(path.read_text())
            except (ValueError, OSError, UnicodeError):
                unreadable.append(str(path.relative_to(ROOT)))
                continue
            files += 1
            walk(value, [], str(path.relative_to(ROOT)))
    return {"passed": not matches and not unreadable, "candidate_namespaces": targets,
            "json_files_scanned": files, "matches": matches, "unreadable": unreadable,
            "scope": "Every integer in existing results/ and outputs/ JSON files, excluding this new study. "
                     "Source namespace registry and historical tuning exclusions also retained."}


def main():
    measure = load_measure()
    inventory_path = STUDY / "namespace_inventory.json"
    if inventory_path.exists():
        inventory = json.loads(inventory_path.read_text())
    else:
        inventory = namespace_audit()
        measure.freeze(inventory_path, inventory)
    unexpected_unreadable = [p for p in inventory["unreadable"]
                            if not any(part.startswith("test_") for part in Path(p).parts)]
    boundary = "outputs/audit_decoy_evolution_20261014/seed_audit.json"
    boundary_value = json.loads((ROOT / boundary).read_text())["validation_reserved_half_open"]
    expected_boundary = {"path": boundary, "field": "validation_reserved_half_open.1", "value": 52_080_000}
    if boundary_value != [52_070_000, 52_080_000]:
        raise ValueError("U validation namespace changed")
    unexpected_matches = [row for row in inventory["matches"] if row != expected_boundary]
    audit = {"passed": not unexpected_unreadable and not unexpected_matches,
             "inventory_sha256": measure.sha(inventory_path), "json_files_scanned": inventory["json_files_scanned"],
             "candidate_namespaces": inventory["candidate_namespaces"],
             "excluded_synthetic_malformed_json": len(inventory["unreadable"]) - len(unexpected_unreadable),
             "exclusion_rule": "Malformed JSON beneath explicitly named test_* synthetic fixture directories.",
             "exclusive_upper_boundary": {"path": boundary, "sha256": measure.sha(ROOT / boundary),
                 "half_open": boundary_value, "interpretation": "52,080,000 is excluded from U block107, not a used seed."},
             "unexpected_matches": unexpected_matches, "unexpected_unreadable": unexpected_unreadable}
    measure.freeze(STUDY / "namespace_audit.json", audit)
    if not audit["passed"]:
        raise ValueError("namespace overlaps or unreadable non-fixture records require review")
    pins = dict(measure.harness_identity())
    paths = [STUDY / "measure.py", STUDY / "run_budgeted.py", STUDY / "prepare.py", measure.CONFIG,
             measure.AUDIT, measure.INPUTS / "prediction_ctl.c"]
    paths += sorted((ROOT / "src").rglob("*.py"))
    paths += [ROOT / "scripts/taskvar_gates.py", ROOT / "scripts/taskvar_gradient.py"]
    for path in paths:
        pins[str(path.relative_to(ROOT))] = measure.sha(path)
    plan = {"study": "V prediction information", "candidate_lives": 4, "T": 1024,
            "seeds": measure.analysis.fresh_seeds(2, seed0=52_090_000), "seed_block": 109,
            "candidates": measure.candidates(json.loads(measure.CONFIG.read_text()))[-2:],
            "max_cpu_seconds": 30, "threads": 2, "source_pins": pins,
            "numerical_identity": measure.numerical_pins(),
            "policy": "Cost/accounting validation only. Fixed full and broad-ablation controllers, two seeds each. "
                      "No retuning, variants, sample extensions or selective reruns. Every CPU second carries into V cap3600."}
    measure.freeze(STUDY / "calibration_plan.json", plan)
    print(json.dumps({"status": "prepared_no_simulation", "namespace_audit": audit,
                      "calibration_plan_sha256": hashlib.sha256((STUDY / "calibration_plan.json").read_bytes()).hexdigest()}))


if __name__ == "__main__":
    main()
