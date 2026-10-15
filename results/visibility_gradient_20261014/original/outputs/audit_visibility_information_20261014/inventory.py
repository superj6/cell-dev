"""Read-only recovery and provisional namespace inventory; no simulation or reservation."""
from __future__ import annotations

import ast
import hashlib
import json
import os
from pathlib import Path
import struct
import sys

import numpy as np

ROOT = Path(__file__).resolve().parents[2]
OUT = Path(__file__).resolve().parent
RANGES = [(52_130_000, 52_140_000), (52_140_000, 52_150_000),
          (52_150_000, 52_160_000), (52_160_000, 52_170_000)]


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def read(path):
    return json.loads(Path(path).read_text())


def literal_assignment(path, name):
    for node in ast.parse(Path(path).read_text()).body:
        if isinstance(node, ast.Assign) and any(isinstance(t, ast.Name) and t.id == name for t in node.targets):
            return ast.literal_eval(node.value)
    raise ValueError("missing literal " + name)


def recover():
    harness = ROOT / "results/open_headroom/harness/harness.py"
    names = literal_assignment(harness, "C4_NAMES") + (
        "dark_amp", "vel", "tau_turn", "tau_v", "conf_v", "idle_dark", "sig_p", "vel_gain", "gate")
    source = ROOT / "results/open_headroom/controllers/mem_ctl.c"
    if sha(source) != sha(ROOT / "outputs/openhr/memory/mem_ctl.c"):
        raise ValueError("archived and original C5 sources differ")
    summary = read(ROOT / "results/open_headroom/data/memory.json")
    retunes = read(ROOT / "outputs/openhr/memory/reflex_knobs_mem.json")
    result = {"status": "recovered_read_only", "simulated_lives": 0, "controller_id": 1102,
              "controller_source": str(source.relative_to(ROOT)), "controller_sha256": sha(source),
              "parameter_names": list(names), "worlds": {}}
    for name, preset, visibility in (
        ("flash5_dim25", "catch_speck_flash5_dim25_l4", [1, 5, 0, 0.25]),
        ("blink20", "catch_speck_blink20_20_l4", [2, 20, 20, 0]),
    ):
        path = ROOT / f"outputs/openhr/memory/scores8/{name}_b100.json"
        data = read(path)
        if set(data["c5_params"]) != set(names):
            raise ValueError("controller parameter names differ")
        vector = [data["c5_params"][key] for key in names]
        knobs = data["rows"]["reflex@hollow3 rt-mem"]["knobs"]
        if knobs != retunes[name]["rt-mem"]["knobs"]:
            raise ValueError("score and retained retune knobs differ")
        tuned = ROOT / f"outputs/openhr/memory/tuned/{name}_ring4.json"
        if tuned.exists() and read(tuned)["x"] != vector:
            raise ValueError("scored vector differs from saved tuning result")
        entry = next(row for row in summary["worlds"] if row["world"] == name)
        if data["c5_source"] != entry["best_info"]["params_source"]:
            raise ValueError("public summary and original parameter source differ")
        control_cpu = entry["rows"]["C5 hollow3"]["cpu_per_life"]
        cpu_names = ["reflex@hollow3 frozen", "reflex@hollow3 rt-mem"]
        cpu_names += [key for key in entry["rows"] if key.startswith("do-less ")]
        cpu = {key: entry["rows"][key]["cpu_per_life"] for key in cpu_names}
        # The historical A/B costs are at ring4, so use max(hollow3 full, ring4 ablation) as a planning proxy.
        cpu["full C5 hollow3"] = control_cpu
        for variant in ("A no dark model", "B idle while believed dark"):
            cpu["C5 hollow3 proxy " + variant] = max(control_cpu, entry["rows"]["C5 ring4 abl " + variant]["cpu_per_life"])
        result["worlds"][name] = {
            "production_preset": preset, "production_visibility_tuple": visibility,
            "scratch_world_rules": data["rules"], "full_parameters": vector,
            "full_parameter_bytes_sha256": hashlib.sha256(struct.pack("<30d", *vector)).hexdigest(),
            "parameter_origin": data["c5_source"], "score_source": str(path.relative_to(ROOT)),
            "score_source_sha256": sha(path), "tune_source": str(tuned.relative_to(ROOT)) if tuned.exists() else None,
            "tune_source_sha256": sha(tuned) if tuned.exists() else None,
            "retuned_reflex_knobs": knobs,
            "retuned_reflex_source": data["rows"]["reflex@hollow3 rt-mem"]["source"],
            "ablation_A_changes": {"9": 0.0, "10": 0.0, "21": 0.0},
            "ablation_B_changes": {"26": 0.5},
            "historical_cpu_per_life_or_proxy": cpu,
            "primary_13_by_512_estimated_cpu_seconds": sum(cpu.values()) * 512,
            "historical_matched_information_gap": entry["info_hollow3_footprint_matched"]["gap"],
            "historical_ring4_ablation_effects": {key: entry["memory"][key] for key in
                ("C5_minus_A_no_dark_model", "C5_minus_B_idle_while_believed_dark")},
        }
    pins = [source, harness, ROOT / "results/open_headroom/harness/make_ckernel.py",
            ROOT / "results/open_headroom/harness/ctl_api.h", ROOT / "results/open_headroom/harness/ctl_core.c",
            ROOT / "results/open_headroom/harness/ctl_builtin.c", ROOT / "results/open_headroom/controllers/mcommon.py",
            ROOT / "results/open_headroom/controllers/t8_score.py", ROOT / "results/open_headroom/data/memory.json",
            ROOT / "outputs/openhr/memory/reflex_knobs_mem.json", ROOT / "results/taskvar/measurement/replay_wrapper.c.in",
            ROOT / "results/prediction_information_20261014/original/src/life/kernel.c",
            ROOT / "results/prediction_information_20261014/original/src/life/spec.py",
            ROOT / "results/prediction_information_20261014/original/src/life/build.py",
            ROOT / "results/prediction_information_20261014/original/src/life/handbuilt.py",
            ROOT / "results/decoy_evolution_20261014/sources/seed_review/namespace_lists.json"]
    result["source_sha256"] = {str(path.relative_to(ROOT)): sha(path) for path in pins}
    result["primary_candidate_lives"] = 2 * 13 * 512
    result["primary_estimated_cpu_seconds"] = sum(w["primary_13_by_512_estimated_cpu_seconds"] for w in result["worlds"].values())
    result["held_duration_extension_candidate_lives"] = 2 * 2 * 13 * 512
    result["held_duration_extension_estimated_cpu_seconds"] = result["primary_estimated_cpu_seconds"] * (768 + 1536) / 1024
    return result


def inventory():
    matches, malformed, npz_errors, pins = [], [], [], {}
    json_count = npz_count = seed_arrays = 0

    def candidate(value):
        return any(lo <= value < hi for lo, hi in RANGES)

    def visit(value, trail, path):
        if isinstance(value, dict):
            for key, child in value.items():
                visit(child, trail + [str(key)], path)
        elif isinstance(value, list):
            for i, child in enumerate(value):
                visit(child, trail + [str(i)], path)
        elif isinstance(value, int) and not isinstance(value, bool) and candidate(value):
            matches.append({"path": path, "field": ".".join(trail), "value": value})

    for top in (ROOT / "results", ROOT / "outputs"):
        for folder, dirs, files in os.walk(top, followlinks=False):
            base = Path(folder)
            dirs[:] = [name for name in dirs if name not in (".git", ".venv", "__pycache__", "node_modules")
                       and not (base / name).is_relative_to(OUT)
                       and not (base / name).is_relative_to(ROOT / 'outputs/autonomous_visibility_information_20261014')]
            for name in sorted(files):
                path = base / name
                relative = str(path.relative_to(ROOT))
                if path.suffix == ".json":
                    try:
                        data = path.read_bytes()
                        value = json.loads(data)
                    except (ValueError, OSError, UnicodeError) as error:
                        malformed.append({"path": relative, "synthetic_fixture": any(part.startswith("test_") for part in path.parts),
                                          "error": type(error).__name__})
                        continue
                    json_count += 1
                    pins[relative] = hashlib.sha256(data).hexdigest()
                    visit(value, [], relative)
                elif path.suffix == ".npz":
                    try:
                        with np.load(path, allow_pickle=False) as data:
                            npz_count += 1
                            for key in data.files:
                                if "seed" not in key.lower():
                                    continue
                                array = data[key]
                                seed_arrays += 1
                                if not np.issubdtype(array.dtype, np.integer):
                                    if not np.issubdtype(array.dtype, np.floating) or not np.isfinite(array).all():
                                        raise ValueError("non-numeric seed array")
                                selected = np.zeros(array.shape, dtype=bool)
                                for lo, hi in RANGES:
                                    selected |= (array >= lo) & (array < hi)
                                for value in array[selected].flat:
                                    matches.append({"path": relative, "field": key, "value": int(value)})
                    except (ValueError, OSError, UnicodeError) as error:
                        npz_errors.append({"path": relative, "error": str(error),
                                           "synthetic_fixture": any(part.startswith("test_") for part in path.parts)})
    return {"status": "provisional_inventory_only", "reserved": False, "simulated_lives": 0,
            "candidate_whole_blocks_half_open": RANGES, "decimal_base": 51_000_000,
            "candidate_block_ids": [113, 114, 115, 116], "json_files_scanned": json_count,
            "npz_files_inspected": npz_count, "npz_seed_arrays_scanned": seed_arrays,
            "numeric_matches": matches, "malformed_json": malformed, "npz_errors": npz_errors,
            "json_input_sha256": pins,
            "scope": "All numeric integer values in results/ and outputs/ JSON, and numeric NPZ arrays whose keys include seed. "
                     "Includes prior explicit hashed and held allocations and worktree copies. Excludes this design directory and its own unreleased preparation directory "
                     "and .git/.venv/__pycache__/node_modules. Text-only formula declarations still require review before reservation."}


if __name__ == "__main__":
    recovered = recover()
    (OUT / "recovered_inputs.json").write_text(json.dumps(recovered, indent=2) + "\n")
    namespaces = inventory()
    if any(name.startswith("src.") for name in sys.modules):
        raise ValueError("design inventory imported an engine module")
    namespaces["engine_modules_imported"] = False
    namespaces["inventory_script_sha256"] = sha(__file__)
    (OUT / "namespace_inventory.json").write_text(json.dumps(namespaces, indent=2) + "\n")
    print(json.dumps({"status": namespaces["status"], "reserved": False,
        "json_files_scanned": namespaces["json_files_scanned"],
        "npz_files_inspected": namespaces["npz_files_inspected"],
        "npz_seed_arrays_scanned": namespaces["npz_seed_arrays_scanned"],
        "numeric_matches": namespaces["numeric_matches"],
        "malformed_json_count": len(namespaces["malformed_json"]),
        "malformed_real_json": [r for r in namespaces["malformed_json"] if not r["synthetic_fixture"]],
        "npz_errors": namespaces["npz_errors"]}))
