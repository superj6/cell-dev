"""AH offline recorded-operation audit, narrowly adapted from the completed U audit.
No genetic draws, setup/fill, engine imports, compilation or life replay. External tie RNG is replayed.
"""

from __future__ import annotations

import copy
import hashlib
import importlib.util
import io
import json
import os
import sys
import time
from pathlib import Path

os.environ.setdefault("ATEN_CPU_CAPABILITY", "avx2")
os.environ.setdefault("OMP_NUM_THREADS", "1")
os.environ.setdefault("MKL_NUM_THREADS", "1")
sys.dont_write_bytecode = True
import numpy as np  # noqa: E402
import torch  # noqa: E402

HERE = Path(__file__).resolve().parent
HELPERS = {
    "L": ("selection.py", "b1a5bfb55f3cf9fdbb8ad46aa1aebd8f2aa5cacd8e02cc0b4ae943f025b107b8"),
    "G": ("helpers/genetics.py", "8fd717bdecb5f0e073e04838bbf286a4a968924bc9848b55c5a8d2b2055f4139"),
}
READS = {}


def read_bytes(path):
    path = Path(path)
    data = path.read_bytes()
    if path.is_relative_to(STUDY):
        name = str(path.relative_to(STUDY))
    elif path.is_relative_to(HERE):
        name = "analysis/" + str(path.relative_to(HERE))
    else:
        name = "production/" + str(path.relative_to(PRODUCTION_ROOT))
    READS[name] = hashlib.sha256(data).hexdigest()
    return data


def sha(path):
    return hashlib.sha256(read_bytes(path)).hexdigest()


def read(path):
    return json.loads(read_bytes(path))


def equal(actual, expected, label):
    if actual != expected:
        raise ValueError(label + " differs")


def raw(value):
    return hashlib.sha256(np.asarray(value).tobytes()).hexdigest()


def load_helpers():
    helpers = {}
    for name, (relative, expected) in HELPERS.items():
        path = HERE / relative
        equal(sha(path), expected, name + " reviewed helper source")
        module_spec = importlib.util.spec_from_file_location("U_offline_" + name, path)
        module = importlib.util.module_from_spec(module_spec)
        module_spec.loader.exec_module(module)
        helpers[name] = module
    return helpers["L"], helpers["G"]


def selection_view(lines, curves, duration):
    """L expects logged varying T; U has fixed T, independently bound to its config."""
    lines, curves = copy.deepcopy(lines), copy.deepcopy(curves)
    for row in [*lines[1:], *curves]:
        if "T" in row:
            equal(row["T"], duration, "optional recorded duration")
        row["T"] = duration
    return lines, curves


def external_identity(protocol, mode):
    equal(mode in ("control", "reserve"), True, "declared arm")
    return {
        "mode": mode,
        "policy": protocol["reserve_policy"],
        "policy_sha256": hashlib.sha256(
            json.dumps(protocol["reserve_policy"], sort_keys=True, separators=(",", ":"), allow_nan=False).encode()
        ).hexdigest(),
        "source_pins": {name: protocol["file_pins"][name] for name in ("reserve_adapter.py", "search.py")},
    }


def check_config(cfg, protocol, mode):
    """Count-critical physics/operators and the explicit external adapter identity."""
    equal(cfg["life"]["T"], 1024, "fixed selection duration")
    equal(cfg["life"]["T_choices"], None, "no selection duration mixture")
    for name, expected in {
        "mu": 32,
        "lam": 224,
        "generations": 4,
        "breeding": "sex",
        "n_mut": 2,
        "p_cell": 0.5,
        "n_mut_scale": True,
        "random_ties": True,
        "immigrants": 0.0,
        "dup_rate": 0.0,
        "del_rate": 0.0,
        "recheck_k": 64,
        "recheck_lives": 4,
        "recheck_key": "all",
    }.items():
        equal(cfg["evolve"][name], expected, "registered operator " + name)
    equal(cfg["threads"], 2, "native thread cap")
    for name, expected in {
        "abi": 3,
        "world": "catch_speck_l4",
        "lives": 3,
        "valid_lives": 16,
        "final_lives": 2,
        "final_top": 1,
        "final_fork_lives": 0,
        "heldout": [],
        "size_curve": [],
        "extinct_charge": True,
        "fast_kernel": True,
        "flags": [],
        "freeze_frac": None,
        "t_open": 0.0,
    }.items():
        equal(cfg["life"][name], expected, "count-critical life config " + name)
    equal(cfg["world"], {"d0": 1.0, "d_min": 0.5, "v_t": 0.3, "tau_turn": 200.0}, "exact persistent V overrides")
    equal(cfg["costs_life"], {}, "unchanged prices")
    equal(cfg["envelope"], {"enabled": False}, "no world envelope")
    equal(cfg["clones"]["every"], 0, "no clone lives")
    equal(cfg["clones"]["conditions"], [], "no clone conditions")
    equal(cfg["evolve"]["heldout_every"], 4, "periodic validation schedule")
    equal(cfg["evolve"]["dup_split"], False, "no split operator")
    equal(cfg["seed"], protocol["paired_native_seed"], "shared native seed")
    equal(cfg["exploratory_reserve"], external_identity(protocol, mode), "configured external adapter")


def first_cohort(layout, initial, children, helper):
    """Reconstruct the recorded first cohort, without drawing another mutation."""
    equal([c["id"] for c in children], list(range(32, 256)), "first offspring IDs")
    parents = torch.from_numpy(initial)
    candidates = [row.copy() for row in initial]
    records = []
    for child in children:
        pa, pb, mask = child["pa"], child["pb"], child["mask"]
        if not 0 <= pa < 32 or not 0 <= pb < 32 or not isinstance(mask, int) or not 0 <= mask < 1 << layout.n_units:
            raise ValueError("invalid first-cohort genetic record")
        equal(set(child["ops"]), {"mut"}, "ordinary first-cohort operations")
        units = torch.tensor([(mask >> i) & 1 for i in range(layout.n_units)], dtype=torch.bool)
        mixed = layout.silence(torch.where(units[layout.unit_of], parents[pa], parents[pb]))
        candidates.append(helper.point_mutation(layout, mixed, child["ops"]).numpy())
        records.append({k: child[k] for k in ("id", "pa", "pb", "mask", "ops")})
    table = np.stack(candidates)
    return {
        "candidate_shape": list(table.shape),
        "candidate_dtype": str(table.dtype),
        "initial_raw_sha256": raw(initial),
        "all256_raw_sha256": raw(table),
        "row_raw_sha256": [raw(row) for row in table],
        "recorded_genetics": records,
    }


def audit(base, protocol, endpoints, genomes, external):
    global STUDY, READS, PRODUCTION_ROOT
    STUDY, READS = Path(base).resolve(), {}
    started = time.process_time()
    torch.set_num_threads(1)
    PRODUCTION_ROOT = external(STUDY, "src/genome.py").parents[1]
    sys.path.insert(0, str(PRODUCTION_ROOT))
    for name in ("src/__init__.py", "src/genome.py", "src/life/__init__.py", "src/life/spec.py", "src/lattice.py"):
        equal(sha(external(STUDY, name)), protocol["production_pins"][name], "offline definition source " + name)
    L, G = load_helpers()
    # These modules only define genome operations and the stateless seed hash.
    from src.genome import Layout
    from src.life import spec

    for name, mod in tuple(sys.modules.items()):
        if name == "src" or name.startswith("src."):
            path = Path(mod.__file__).resolve()
            equal(
                sha(path),
                protocol["production_pins"][str(path.relative_to(PRODUCTION_ROOT))],
                "loaded definition source",
            )

    initialization = read(STUDY / "initialization.json")
    equal(genomes.shape, (3, 875), "three confirmation genotypes")
    equal(str(genomes.dtype), "float32", "confirmation dtype")
    results, first_cohorts, first_scores = {}, {}, {}
    for i, key in enumerate(protocol["runs"]):
        seed = protocol["paired_native_seed"]
        folder = STUDY / "runs" / key
        founder_meta = protocol["founder_mapping"]["L92"]
        founder_path = STUDY / founder_meta["start_file"]
        layout, founder = Layout.load(founder_path)
        equal(raw(founder.numpy()), founder_meta["raw_sha256"], "founder raw genotype")
        if not L.identical(founder.numpy(), genomes[0]):
            raise ValueError("confirmation reference differs from registered founder")
        config_path = STUDY / protocol["configs"][key]["path"]
        equal(sha(config_path), protocol["configs"][key]["sha256"], "search configuration")
        cfg = L.config_identity(config_path)
        check_config(cfg, protocol, key)
        checkpoint_bytes = read_bytes(folder / "checkpoint.pt")
        saved = torch.load(io.BytesIO(checkpoint_bytes), map_location="cpu", weights_only=True)
        equal(saved["format"], 1, "checkpoint format")
        equal(saved["config"], cfg, "checkpoint configuration")
        sha(folder / "config.yaml")
        equal(L.config_identity(folder / "config.yaml"), cfg, "saved run configuration")
        configured = external_identity(protocol, key)
        equal(cfg["exploratory_reserve"], configured, "configured external adapter identity")
        equal(
            saved["identity"],
            dict(protocol["expected_numerical_identity"], external_selection=configured),
            "saved extended numerical identity",
        )
        equal(read(folder / "determinism.json"), saved["identity"], "run identity receipt")
        state = saved["state"]
        equal(state["generation"], 4, "completed endpoint generation")
        equal(state["evals"], 1024, "four 256-candidate initial evaluation batches")
        equal(state["rc_lives"], 1024, "four 64-by-four recheck batches")
        equal(set(saved["logs"]), {"curves.jsonl", "lineage.jsonl", "clones.jsonl"}, "checkpoint logs")
        logs = {}
        for name, metadata in saved["logs"].items():
            data = read_bytes(folder / name)
            equal(len(data), metadata["bytes"], "complete log size " + name)
            equal(hashlib.sha256(data).hexdigest(), metadata["sha256"], "complete log hash " + name)
            logs[name] = [json.loads(line) for line in data.splitlines() if line.strip()]
        curves, lines = logs["curves.jsonl"], logs["lineage.jsonl"]
        equal(logs["clones.jsonl"], [], "disabled search clones")
        equal(curves, state["curves"], "checkpoint curve history")
        equal([row["gen"] for row in curves], [0, 1, 2, 3], "generation sequence")
        equal([row["gen"] for row in curves if "valid" in row], [0, 3], "periodic validation schedule")
        equal(lines[0]["seeded"], cfg["evolve"]["seed_genome"], "recorded founder input")
        view_lines, view_curves = selection_view(lines, curves, 1024)
        selection = L.audit_lineage(view_lines, view_curves, state, seed, spec, key, protocol["reserve_policy"])
        receipt = initialization["backgrounds"]["L92"]
        equal(initialization["runs"][key], "L92", "shared initialization mapping")
        equal(receipt["copies"], lines[0]["copies"], "prospective recorded initial mutations")
        initial_path = STUDY / receipt["population_file"]
        equal(sha(initial_path), receipt["file_sha256"], "prospective population file")
        initial = np.load(io.BytesIO(read_bytes(initial_path)), allow_pickle=False)
        equal(initial.shape, (32, 875), "initial population shape")
        equal(str(initial.dtype), "float32", "initial population dtype")
        reconstructed = np.stack(
            [founder.numpy()] + [G.point_mutation(layout, founder, child["ops"]).numpy() for child in receipt["copies"]]
        )
        if not L.identical(initial, reconstructed):
            raise ValueError("initial population does not replay bitwise")
        equal(raw(initial), receipt["population_raw_sha256"], "initial raw population")
        first_cohorts[key] = first_cohort(layout, initial, lines[1]["children"], G)
        first_scores[key] = lines[1]["exploratory_reserve"]["base_F"]
        first_cohorts[key]["signature"] = {
            "founder_ids": lines[0]["ids"],
            "copies": lines[0]["copies"],
            "children": first_cohorts[key]["recorded_genetics"],
        }
        replay = G.replay_genetics(lines, state, layout, founder, structural=False)
        if any(
            not np.isfinite(row[name]) or row[name] != 0
            for row in curves
            for name in ("pop_invalid", "pop_mismatch", "recheck_invalid")
        ):
            raise ValueError("nonfinite or nonzero search health")
        health = {
            name: max(float(row[name]) for row in curves) for name in ("pop_invalid", "pop_mismatch", "recheck_invalid")
        }
        if any(value != 0 for value in health.values()):
            raise ValueError("nonzero search invalid/mismatch health")
        population = state["population"].numpy()
        equal(population.shape, (32, 875), "final population shape")
        equal(str(population.dtype), "float32", "final population dtype")
        if not np.isfinite(population).all():
            raise ValueError("nonfinite final population")
        best = read(folder / "best_genome.json")
        public = read(folder / "population.json")
        dims = read(founder_path)["dims"]
        equal(best["dims"], dims, "best genome dimensions")
        equal(public["dims"], dims, "population dimensions")
        for name in ("ids", "breeds", "origins", "fitness"):
            equal(public[name], state[name].tolist(), "public population " + name)
        if not L.identical(np.stack([L.genome(row) for row in public["genomes"]]), population):
            raise ValueError("public population does not match raw checkpoint")
        if not L.identical(L.genome(best["params"]), population[0]):
            raise ValueError("best genome differs from final rank zero")
        if not L.identical(genomes[i + 1], population[0]):
            raise ValueError("frozen confirmation genotype differs from final rank zero")
        recorded = endpoints["endpoints"][key]
        equal(
            recorded,
            {
                "checkpoint_sha256": hashlib.sha256(checkpoint_bytes).hexdigest(),
                "genome_file_sha256": sha(folder / "best_genome.json"),
                "genome_raw_sha256": raw(population[0]),
                "determinism_sha256": sha(folder / "determinism.json"),
                "log_pins": {name: sha(folder / name) for name in saved["logs"]},
                "generation": 4,
                "rank": 0,
                "search_health": health,
                "selection_identity": configured,
            },
            "frozen endpoint binding",
        )
        diagnostic = [json.loads(line) for line in read_bytes(folder / "results.jsonl").splitlines() if line.strip()]
        equal(len(diagnostic), 1, "one completed native diagnostic record")
        diagnostic = diagnostic[0]
        for name, value in {
            "seed": seed,
            "abi": 3,
            "generations": 4,
            "world": protocol["world"]["name"],
            "selection_physics": "base",
            "lives": 2,
            "founders_sampled": 0,
            "top_best_rank": 0,
            "invalid_lives": 0,
            "mismatch_lives": 0,
            "forks": {},
            "heldout_score": None,
        }.items():
            equal(diagnostic[name], value, "native final diagnostic " + name)
        equal(diagnostic["final_seeds"], [L.life_seed(spec, seed, 5, 0, j) for j in range(2)], "native final0 seeds")
        for name in ("F", "top_best_F", "top_best_F_se", "n_half", "growing"):
            if not np.isfinite(diagnostic[name]):
                raise ValueError("nonfinite native final diagnostic")
        equal(diagnostic["top_F"], [diagnostic["F"]], "single native diagnostic endpoint")
        equal(diagnostic["top_best_F_pick"], diagnostic["F"], "no tiny-diagnostic endpoint substitution")
        guards = [round(row["pop_guard"] * 768) for row in curves]
        if not all(np.isclose(row["pop_guard"] * 768, n, rtol=0, atol=1e-8) for row, n in zip(curves, guards)):
            raise ValueError("initial guard frequencies are not exact life counts")
        results[key] = {
            "status": "passed",
            "generation": 4,
            "final_rank_zero_id": int(state["ids"][0]),
            "checkpoint_sha256": recorded["checkpoint_sha256"],
            "genome_raw_sha256": recorded["genome_raw_sha256"],
            "prospective_initial_population_bitwise": True,
            "selection": selection,
            "genetic_replay": replay,
            "search_health": health,
            "initial_evaluation_genome_lives": 3072,
            "recheck_genome_lives": 1024,
            "initial_evaluation_guard_lives_by_generation": guards,
            "final_rank_zero_binding": True,
            "all_final_population_rows_bound": True,
        }
    equal(first_cohorts["control"], first_cohorts["reserve"], "all256 first-cohort genotypes and recorded operations")
    if not L.identical(
        np.asarray(first_scores["control"], dtype=np.float64), np.asarray(first_scores["reserve"], dtype=np.float64)
    ):
        raise ValueError("all256 first initial fitness values differ bitwise")
    signature = first_cohorts["control"]["signature"]
    expected_first = {
        "initial_population_raw_sha256": first_cohorts["control"]["initial_raw_sha256"],
        "recorded_genetics_sha256": hashlib.sha256(json.dumps(signature, sort_keys=True).encode()).hexdigest(),
        "initial_rows": 32,
        "candidate_count": 256,
        "offspring_count": 224,
        "base_F_exact": True,
    }
    claimed = dict(endpoints["matched_first_cohort"])
    limitation = claimed.pop("limitation")
    if not isinstance(limitation, str) or not limitation:
        raise ValueError("first-cohort proof limitation missing")
    equal(claimed, expected_first, "producer matched first-cohort receipt")
    for name, mod in tuple(sys.modules.items()):
        if name == "src" or name.startswith("src."):
            path = Path(mod.__file__).resolve()
            relative = str(path.relative_to(PRODUCTION_ROOT))
            equal(sha(path), protocol["production_pins"][relative], "loaded source closure")
    forbidden = sorted(
        name
        for name in sys.modules
        if name.startswith(
            ("src.life.build", "src.life.evaluate", "src.life.reference", "src.checkpoint", "src.evolve", "src.run")
        )
    )
    equal(forbidden, [], "simulation/checkpoint execution modules not imported")
    return {
        "status": "passed",
        "protocol_sha256": sha(STUDY / "protocol.json"),
        "runs": results,
        "matched_first_cohort": first_cohorts["control"],
        "first_base_F_bitwise_equal": True,
        "simulated_lives": 0,
        "numerical_golden_checks_executed": False,
        "confirmation_outcomes_read": False,
        "confirmation_metadata_only": ["confirmation/endpoints.json", "confirmation/genotypes.npz"],
        "helper_sources": {name: {"path": path, "sha256": value} for name, (path, value) in HELPERS.items()},
        "read_artifact_sha256": dict(sorted(READS.items())),
        "script_sha256": hashlib.sha256(Path(__file__).read_bytes()).hexdigest(),
        "audit_process_cpu_seconds": time.process_time() - started,
        "limits": [
            "Replays recorded genetic operations and external tie/lottery streams; no fresh genetic draws or life simulations.",
            "Policy selection is checked against all logged rank inputs and exact tie streams; unretained per-life search ledgers cannot be reconstructed.",
            "Search guard frequencies cover initial three-life evaluations; logs do not enumerate every recheck guard life.",
            "Saved numerical identity receipts are compared; fresh numerical goldens are intentionally not executed.",
            "Fixed T1024 from the pinned config is supplied to the reused L selection helper because native logs omit constant T.",
            "No confirmation outcomes are read and no behavioral or out-of-sample performance conclusion is made.",
        ],
    }


def initialization_audit(base, protocol, external):
    """Check the one shared32-row table using only recorded additions."""
    global STUDY, READS, PRODUCTION_ROOT
    STUDY, READS = Path(base).resolve(), {}
    PRODUCTION_ROOT = external(STUDY, "src/genome.py").parents[1]
    sys.path.insert(0, str(PRODUCTION_ROOT))
    for name in ("src/__init__.py", "src/genome.py", "src/life/__init__.py", "src/life/spec.py", "src/lattice.py"):
        equal(sha(external(STUDY, name)), protocol["production_pins"][name], "offline definition source " + name)
    L, G = load_helpers()
    from src.genome import Layout
    from src.life import spec  # noqa: F401

    for name, mod in tuple(sys.modules.items()):
        if name == "src" or name.startswith("src."):
            path = Path(mod.__file__).resolve()
            equal(
                sha(path),
                protocol["production_pins"][str(path.relative_to(PRODUCTION_ROOT))],
                "loaded definition source",
            )
    receipt = read(STUDY / "initialization.json")
    equal(receipt["status"], "pure_genetic_preparation", "initialization status")
    equal(receipt["simulation_calls"], 0, "no preparation simulation")
    equal(receipt["runs"], {"control": "L92", "reserve": "L92"}, "one shared initial cohort")
    equal(set(receipt["backgrounds"]), {"L92"}, "one unique background")
    item = receipt["backgrounds"]["L92"]
    layout, founder = Layout.load(STUDY / protocol["founder_mapping"]["L92"]["start_file"])
    equal(raw(founder.numpy()), protocol["founder_mapping"]["L92"]["raw_sha256"], "fixed start")
    equal([x["id"] for x in item["copies"]], list(range(1, 32)), "31 copy IDs")
    equal([x["parent"] for x in item["copies"]], [0] * 31, "copy parent IDs")
    if any(set(x["ops"]) != {"mut"} or len(x["ops"]["mut"]) != 2 for x in item["copies"]):
        raise ValueError("only recorded ordinary mutations required")
    path = STUDY / item["population_file"]
    equal(sha(path), item["file_sha256"], "initial file bytes")
    initial = np.load(io.BytesIO(read_bytes(path)), allow_pickle=False)
    equal(initial.shape, (32, 875), "initial shape")
    equal(str(initial.dtype), "float32", "initial dtype")
    rebuilt = np.stack(
        [founder.numpy()] + [G.point_mutation(layout, founder, x["ops"]).numpy() for x in item["copies"]]
    )
    if not L.identical(initial, rebuilt):
        raise ValueError("initial recorded additions differ")
    equal(raw(initial), item["population_raw_sha256"], "initial raw hash")
    configs = {}
    for run in protocol["runs"]:
        record = protocol["configs"][run]
        config_path = STUDY / record["path"]
        equal(sha(config_path), record["sha256"], "configuration file pin")
        cfg = L.config_identity(config_path)
        check_config(cfg, protocol, run)
        configs[run] = copy.deepcopy(cfg)
        configs[run]["exploratory_reserve"]["mode"] = "normalized"
    equal(configs["control"], configs["reserve"], "same configurations except policy mode/output path")
    return {
        "status": "passed",
        "protocol_sha256": sha(STUDY / "protocol.json"),
        "backgrounds": {
            "L92": {
                "rows": 32,
                "recorded_mutations": 62,
                "all_rows_bitwise_equal": True,
                "raw_sha256": raw(initial),
                "file_sha256": sha(path),
            }
        },
        "runs": receipt["runs"],
        "simulation_calls": 0,
        "compilation_calls": 0,
        "random_draws": 0,
        "limit": "Recorded additions only; initial RNG hashes are bound but genetic draws are not rerun.",
        "script_sha256": hashlib.sha256(Path(__file__).read_bytes()).hexdigest(),
    }
