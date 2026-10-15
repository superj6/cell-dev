"""Independently audit and archive the two fixed 16-generation continuations; never simulate lives.

Incomplete studies produce an explicitly incomplete status and cannot be exported.
Completed exports include frozen sources, checkpoints, populations, lineage and all
confirmation ledger columns. The exported analyze.py rechecks those artifacts.
"""
from __future__ import annotations

import argparse
import hashlib
import importlib.util
import io
import json
import os
import shutil
import sys
from pathlib import Path

os.environ.setdefault("ATEN_CPU_CAPABILITY", "avx2")
os.environ.setdefault("OMP_NUM_THREADS", "1")
os.environ.setdefault("MKL_NUM_THREADS", "1")

sys.dont_write_bytecode = True

import numpy as np  # noqa: E402
import torch  # noqa: E402
from omegaconf import OmegaConf  # noqa: E402

RUNS = (51891, 51892)
DURATIONS = (768, 1024, 1536)
LABELS = ("pilot_s7", "founder_row29", "s51891_final_rank0", "s51892_final_rank0")
FIELDS = ("W", "b", "lam", "s0", "Q", "act", "A", "a0", "Dm", "km")
STATUS = dict(extinct=1, guard_cells=2, guard_events=4, ledger_mismatch=64, capacity=128)
ROOT = next((p for p in Path(__file__).resolve().parents if (p / "src/genome.py").exists()), None)
D_ANALYZER_SHA = "78a21cde2e65cf733ba072e51f09be043d681640a696b00f43462fdf4d3fd497"
G_GENETICS_SHA = "8fd717bdecb5f0e073e04838bbf286a4a968924bc9848b55c5a8d2b2055f4139"
DEPENDENCIES = {"outputs/autonomous_duplicate_use_20261014", "outputs/autonomous_traces_20261014"}
LIMITATIONS = [
    "Two fixed exploratory continuation replicates do not estimate general search reliability.",
    "The final population rank-zero genome was frozen before confirmation; no validation-best reselection occurred.",
    "Search fitness and selected-body descriptors are winner-biased and use changing durations and seeds.",
    "Periodic validation uses 16 fresh lives at T1024 and describes successive selected genomes; "
    "it is not an independent repeated measurement of one fixed organism.",
    "The duration mixture averages three paired effects within each shared seed before computing SE "
    "over 256 seed clusters. The endpoints also share those seeds.",
    "Guarded lives retain the production continuation charge; capacity or ledger mismatch blocks inference.",
    "These data concern adaptation from a preselected founder in fast-conduction POOL, not a new algorithm.",
    "Saved numerical pins are compared without executing numerical golden checks or any simulation.",
    "Recorded genetic replay checks inheritance and every retained genome, not the random-number draws.",
]


def digest(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def identical(left, right):
    left, right = np.asarray(left), np.asarray(right)
    return left.shape == right.shape and left.dtype == right.dtype and left.tobytes() == right.tobytes()


def raw_digest(value):
    return hashlib.sha256(np.asarray(value).tobytes()).hexdigest()


def read_json(path):
    return json.loads(Path(path).read_text())


def write_json(path, value):
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_suffix(".tmp")
    temporary.write_text(json.dumps(value, indent=2, allow_nan=False) + "\n")
    temporary.replace(path)


def equal(actual, expected, label):
    if actual != expected:
        raise ValueError(f"{label}: differs from frozen study")


def stats(values):
    values = np.asarray(values, dtype=np.float64)
    if values.ndim != 1 or len(values) < 2 or not np.isfinite(values).all():
        raise ValueError("statistics require finite paired seed values")
    return {"mean": float(values.mean()), "se": float(values.std(ddof=1) / np.sqrt(len(values))), "n": len(values)}


def check_stats(value, saved, label):
    equal(value["n"], saved["n"], label + " sample count")
    if any(not np.isclose(value[k], saved[k], rtol=1e-11, atol=1e-12) for k in ("mean", "se")):
        raise ValueError(label + ": report differs from independently recomputed paired values")


def mixture(values):
    if set(values) != set(DURATIONS):
        raise ValueError("duration mixture requires all three registered durations")
    rows = np.stack([values[t] for t in DURATIONS])
    if rows.ndim != 2 or not np.isfinite(rows).all():
        raise ValueError("duration mixture requires finite matched seed rows")
    return rows.mean(axis=0)


def genome(params):
    equal(set(params), set(FIELDS), "genome field names")
    flat = np.concatenate([np.asarray(params[key], dtype=np.float32).reshape(-1) for key in FIELDS])
    if not np.isfinite(flat).all():
        raise ValueError("nonfinite raw genotype")
    return flat


def source(study, relative):
    archived = study / "sources" / relative
    if archived.exists():
        return archived
    if ROOT is None:
        raise ValueError(f"missing archived source: {relative}")
    return ROOT / relative


def operation(study, name):
    archived = study / "operations" / name
    return archived if archived.exists() else study / name


def provenance_check(study):
    path = study / "provenance.json"
    if path.exists():
        for relative, meta in read_json(path)["artifacts"].items():
            equal(digest(study / relative), meta["sha256"], "archived artifact " + relative)
            equal((study / relative).stat().st_size, meta["bytes"], "archived size " + relative)


def dependency(study, relative):
    archived = study / "dependencies" / Path(relative).name
    return archived if archived.exists() else ROOT / relative


def template(study, relative):
    archived = study / "templates" / relative
    return archived if archived.exists() else ROOT / relative


def genetic_helper(study):
    path = study / "sources/G_audit_search.py"
    equal(digest(path), G_GENETICS_SHA, "reviewed G genetic replay source")
    loader = importlib.util.spec_from_file_location("s7_frozen_genetic_replay", path)
    helper = importlib.util.module_from_spec(loader)
    loader.loader.exec_module(helper)
    return helper


def initialization_audit(study, seed, lines, state, founder):
    """Bind the prospective 32-genome receipt to recorded genetics and the complete final population."""
    from src.genome import Layout

    helper = genetic_helper(study)
    layout, source_founder = Layout.load(study / "inputs/founder_row29.json")
    if not identical(source_founder.numpy(), founder):
        raise ValueError("initialization founder differs")
    receipt = read_json(study / "initialization.json")["runs"][str(seed)]
    equal(receipt["shape"], [32, 875], "initial population shape")
    equal(receipt["dtype"], "float32", "initial population dtype")
    equal(receipt["founder_ids"], [0], "initial founder ids")
    equal(receipt["copies"], lines[0]["copies"], "prospective initial mutation operations")
    path = study / receipt["population_file"]
    equal(digest(path), receipt["file_sha256"], "prospective population file")
    population = np.load(path, allow_pickle=False)
    reconstructed = np.stack([source_founder.numpy()] + [
        helper.point_mutation(layout, source_founder, child["ops"]).numpy() for child in receipt["copies"]])
    if not identical(population, reconstructed):
        raise ValueError("prospective initial population does not replay bitwise")
    equal(raw_digest(population), receipt["population_raw_sha256"], "initial raw population")
    equal([raw_digest(row) for row in population], receipt["row_raw_sha256"], "every initial genotype")
    replay = helper.replay_genetics(lines, state, layout, source_founder, structural=False)
    return {"prospective_population_bitwise": True, "population_sha256": receipt["population_raw_sha256"],
            "genetic_replay": replay}


def frozen_inputs(study):
    provenance_check(study)
    protocol, ready = read_json(study / "protocol.json"), read_json(study / "ready.json")
    equal(digest(study / "protocol.json"), ready["protocol_sha256"], "protocol")
    equal(digest(operation(study, "run_budgeted.py")), ready["runner_sha256"], "budgeted runner")
    equal(digest(operation(study, "measure.py")), ready["measurement_sha256"], "measurement runner")
    equal(digest(operation(study, "prepare.py")), protocol["prepare_sha256"], "preparation source")
    equal(digest(study / "seed_audit.json"), protocol["seed_audit_sha256"], "seed audit")
    equal(digest(study / "initialization.json"), protocol["initialization_audit_sha256"], "initialization audit")
    equal(digest(study / "sources/D_analyze.py"), D_ANALYZER_SHA, "reviewed D analysis source")
    genetic_helper(study)
    equal(protocol["runs"], list(RUNS), "replicates")
    equal(protocol["generations"], 16, "registered generations")
    equal(protocol["max_cpu_seconds"], 14400, "CPU cap")
    equal(protocol["max_simulation_threads"], 4, "worker cap")
    equal(protocol["planned_genome_lives"], 36012, "registered life count")
    equal(protocol["confirmation_genome_lives"], 3072, "registered confirmation count")
    for group in ("inputs", "reference_sources"):
        for relative, expected in protocol[group].items():
            equal(digest(study / relative), expected, group + " " + relative)
    for relative, expected in protocol["template_pins"].items():
        equal(digest(template(study, relative)), expected, "ordinary search template")
    equal(ready["helpers"], protocol["helpers"], "helper pin set")
    equal(set(protocol["wait_for_studies"]), DEPENDENCIES, "registered dependencies")
    equal(set(ready["dependencies"]), DEPENDENCIES, "dependency release pins")
    for relative, files in ready["dependencies"].items():
        folder = dependency(study, relative)
        equal(set(files), {"protocol.json", "run_budgeted.py"}, "dependency source pin set")
        for name, expected in files.items():
            equal(digest(operation(folder, name)), expected, "dependency " + relative + "/" + name)
        budget = read_json(operation(folder, "budget.json"))
        if budget["status"] != "complete" or budget.get("running") or budget.get("queued"):
            raise ValueError("predecessor did not complete before L")
    for relative, expected in protocol["source_identity"].items():
        equal(digest(source(study, relative)), expected, "source " + relative)
    for name, expected in ready["helpers"].items():
        equal(digest(source(study, "scripts/" + name)), expected, "helper " + name)
    equal(protocol["expected_numerical_identity"]["sources"], protocol["source_identity"], "identity sources")
    prior_path = study / "inputs/prior_provenance.json"
    if not prior_path.exists():
        prior_path = ROOT / "results/pool_mutants_20261013/provenance.json"
    equal(digest(prior_path), protocol["archive_provenance_sha256"], "prior archive provenance")
    prior = read_json(prior_path)
    equal(prior["numerical_identity"], protocol["expected_numerical_identity"], "prior numerical identity")
    inputs = {}
    for name in ("founder", "pilot"):
        path = study / "inputs" / Path(protocol[name + "_file"]).name
        equal(digest(path), protocol[name + "_sha256"], name + " file")
        original = str(Path(protocol["input_sources"][name]).relative_to("results/pool_mutants_20261013"))
        equal(digest(path), prior["artifacts"][original]["sha256"], name + " original archive artifact")
        inputs[name] = genome(read_json(path)["params"])
    equal(raw_digest(inputs["founder"]), protocol["founder_raw_sha256"], "founder raw genome")
    selected = read_json(study / "inputs/original_selection.json")
    equal(selected["winner_genome_row"], 29, "original fixed mutant row")
    equal(selected["winner_mutant_index"], 28, "original fixed mutation index")
    equal(selected["winner_sha256"], raw_digest(inputs["founder"]), "original selected genome")
    original_pool = np.load(study / "inputs/original_mutants.npy", allow_pickle=False)
    if original_pool.shape != (65, 875) or not identical(original_pool[0], inputs["pilot"]):
        raise ValueError("original s7 mutation pool or pilot differs")
    if not identical(original_pool[29], inputs["founder"]):
        raise ValueError("founder differs from the original archived s7 row29")
    for seed in RUNS:
        equal(digest(study / f"configs/s{seed}.yaml"), protocol["configs"][str(seed)]["sha256"], "config")
    sys.path.insert(0, str(study / "sources" if (study / "sources/src").exists() else ROOT))
    from src.life import spec

    seed_audit = read_json(study / "seed_audit.json")
    equal(seed_audit["confirm_seeds"], list(range(51_900_000, 51_900_256)), "confirmation seeds")
    equal(protocol["confirmation"]["labels"], list(LABELS), "registered genotype labels")
    all_seeds = []
    for seed in RUNS:
        expected = []
        for generation in range(16):
            expected.extend(life_seed(spec, seed, 1, generation, j) for j in range(7))
            if generation % 4 == 0 or generation == 15:
                expected.extend(life_seed(spec, seed, 3, generation, j) for j in range(16))
        for index in (0, 1):
            expected.extend(life_seed(spec, seed, 5, index, j) for j in range(2))
        equal(seed_audit["run_life_seeds"][str(seed)], expected, "run seeds")
        all_seeds.extend(expected)
        choices = list(DURATIONS)
        lengths = [choices[min(int(spec.draw(seed, 0x54445257, g) * 3), 2)] for g in range(16)]
        equal(protocol["selection_durations"][str(seed)], lengths, "selection duration draw")
    equal(len(set(all_seeds)), 392, "unique hashed search/report seeds")
    if any(51_000_000 <= x < 52_000_000 for x in all_seeds):
        raise ValueError("hashed seeds overlap reserved decimal blocks")
    return protocol, ready, inputs, spec


def life_seed(spec, run_seed, purpose, index, life):
    return spec.hash64(run_seed, 0x4C494645 + purpose, index, life)


def config_identity(path):
    value = OmegaConf.to_container(OmegaConf.load(path), resolve=True)
    value.pop("extends", None)
    value["logging"].pop("output_dir", None)
    value["logging"].pop("checkpoint_every", None)
    return value


def read_lines(path, limit=None):
    data = Path(path).read_bytes()
    if limit is not None:
        data = data[:limit]
    return [json.loads(line) for line in data.decode().splitlines() if line.strip()]


def audit_lineage(lines, curves, state, seed, spec, initial_lives=3, recheck_lives=4):
    initial, generations = lines[0], lines[1:]
    equal(initial["event"], "founders", "initial event")
    equal(initial["sampled"], 0, "founder sampling")
    equal(initial["ids"], [0], "exact founder ids")
    equal([c["id"] for c in initial["copies"]], list(range(1, 32)), "31 mutated copies")
    equal([c["parent"] for c in initial["copies"]], [0] * 31, "copy parents")
    equal([row["gen"] for row in generations], list(range(len(curves))), "lineage generations")
    parents = list(range(32))
    mutations = sum(len(c["ops"].get("mut", [])) for c in initial["copies"])
    offspring = 0
    for g, (row, curve) in enumerate(zip(generations, curves)):
        equal(row["seeds"], [life_seed(spec, seed, 1, g, j) for j in range(initial_lives)], "initial seeds")
        equal(row["recheck"]["seeds"], [life_seed(spec, seed, 1, g, j) for j in range(initial_lives, initial_lives + recheck_lives)], "recheck seeds")
        equal(float(row["T"]), float(curve["T"]), "lineage duration")
        children = row["children"]
        equal([c["id"] for c in children], list(range(32 + 224 * g, 32 + 224 * (g + 1))), "offspring ids")
        for child in children:
            if child["pa"] not in parents or child["pb"] not in parents:
                raise ValueError("sexual offspring parent is absent from the preceding population")
            if any(key != "mut" and value for key, value in child["ops"].items()):
                raise ValueError("unregistered structural mutation")
            mutations += len(child["ops"].get("mut", []))
        candidates = set(parents) | {c["id"] for c in children}
        survivors = row["survivors"]
        if len(survivors) != 32 or len(set(survivors)) != 32 or not set(survivors) <= candidates:
            raise ValueError("invalid survivor population")
        shortlist = row["recheck"]["ids"]
        if len(shortlist) != 64 or len(set(shortlist)) != 64 or not set(survivors) <= set(shortlist) <= candidates:
            raise ValueError("invalid recheck shortlist")
        equal(row["recheck"]["key"], "all", "recheck ranking key")
        base = np.asarray(row["recheck"]["F_base"])
        extra = np.asarray(row["recheck"]["F_recheck"])
        if base.shape != (64,) or extra.shape != (64,) or not np.isfinite(base + extra).all():
            raise ValueError("invalid recheck score vectors")
        pooled = (initial_lives * base + recheck_lives * extra) / (initial_lives + recheck_lives)
        chosen = [shortlist.index(value) for value in survivors]
        if not np.allclose(pooled[chosen], row["fitness"], rtol=1e-12, atol=1e-12):
            raise ValueError("selected fitness differs from the registered pooled scores")
        unchosen = [i for i in range(64) if i not in chosen]
        if (np.any(np.diff(base) > 1e-12) or np.any(np.diff(pooled[chosen]) > 1e-12)
                or np.max(pooled[unchosen]) > np.min(pooled[chosen]) + 1e-12):
            raise ValueError("survivors differ from the top32 pooled shortlist")
        for child in children:
            equal(child["kept"], child["id"] in survivors, "kept child flag")
        equal(curve["best_id"], survivors[0], "selected rank-zero id")
        if not np.isclose(row["fitness"][0], curve["fitness"], rtol=1e-13):
            raise ValueError("selected fitness differs between logs")
        parents = survivors
        offspring += len(children)
    equal(parents, state["ids"].tolist(), "checkpoint final population ids")
    if not np.array_equal(np.asarray(generations[-1]["fitness"]), state["fitness"].numpy()):
        raise ValueError("checkpoint fitness differs from final lineage")
    return {"exact_initial_founders": 1, "initial_mutated_copies": 31, "sexual_offspring": offspring,
            "logged_point_mutations_including_initial_copies": mutations,
            "founder_id_survives": 0 in parents, "final_ids": parents}


def search_audit(study, seed, protocol, inputs, spec, complete):
    folder = study / f"runs/s{seed}"
    checkpoint_path = folder / "checkpoint.pt"
    if not checkpoint_path.exists():
        return {"status": "no_checkpoint"}, None
    # weights_only excludes arbitrary checkpoint pickle objects; no resume or log truncation is called.
    checkpoint_bytes = checkpoint_path.read_bytes()
    saved = torch.load(io.BytesIO(checkpoint_bytes), map_location="cpu", weights_only=True)
    equal(saved["format"], 1, "checkpoint format")
    equal(saved["config"], config_identity(study / f"configs/s{seed}.yaml"), "checkpoint configuration")
    equal(saved["identity"], protocol["expected_numerical_identity"], "checkpoint numerical identity")
    equal(read_json(folder / "determinism.json"), saved["identity"], "run numerical identity")
    equal(config_identity(folder / "config.yaml"), saved["config"], "saved run configuration")
    state = saved["state"]
    generation = int(state["generation"])
    if complete:
        equal(generation, 16, "completed endpoint generation")
    if generation < 1 or generation > 16:
        raise ValueError("checkpoint generation outside registered study")
    for name, meta in saved["logs"].items():
        data = (folder / name).read_bytes()[:meta["bytes"]]
        equal(len(data), meta["bytes"], "checkpoint log prefix size")
        equal(hashlib.sha256(data).hexdigest(), meta["sha256"], "checkpoint log prefix hash")
        if complete:
            equal((folder / name).stat().st_size, meta["bytes"], "complete log size")
    curves = read_lines(folder / "curves.jsonl", saved["logs"]["curves.jsonl"]["bytes"])
    equal(curves, state["curves"], "checkpoint curves")
    equal([row["gen"] for row in curves], list(range(generation)), "ordered generation history")
    equal([row["T"] for row in curves], protocol["selection_durations"][str(seed)][:generation], "durations")
    lines = read_lines(folder / "lineage.jsonl", saved["logs"]["lineage.jsonl"]["bytes"])
    ancestry = audit_lineage(lines, curves, state, seed, spec)
    ancestry.update(initialization_audit(study, seed, lines, state, inputs["founder"]))
    health = {key: max(float(row[key]) for row in curves)
              for key in ("pop_invalid", "pop_mismatch", "recheck_invalid")}
    if complete and any(health.values()):
        raise ValueError("invalid or mismatched search lives block endpoint inference")
    selected = state["population"][0].numpy()
    expected_dims = read_json(study / "inputs/founder_row29.json")["dims"]
    if selected.dtype != np.float32 or not np.isfinite(state["population"].numpy()).all():
        raise ValueError("invalid checkpoint population")
    if complete:
        best_record = read_json(folder / "best_genome.json")
        equal(best_record["dims"], expected_dims, "endpoint genome dimensions")
        best = genome(best_record["params"])
        if not identical(best, selected):
            raise ValueError("best genome differs from completed final rank zero")
        public = read_json(folder / "population.json")
        equal(public["dims"], expected_dims, "population genome dimensions")
        for key in ("ids", "breeds", "origins", "fitness"):
            equal(public[key], state[key].tolist(), "saved final population " + key)
        if not identical(np.stack([genome(p) for p in public["genomes"]]), state["population"].numpy()):
            raise ValueError("population JSON differs from checkpoint")
    valid = [{"generation": row["gen"], "F": row["valid"], "n_lives": 16, "T": 1024}
             for row in curves if "valid" in row]
    equal([row["generation"] for row in valid], [g for g in range(generation) if g % 4 == 0 or g == 15],
          "validation schedule")
    initial_guard_counts = [round(row["pop_guard"] * 768) for row in curves]
    if not all(np.isclose(row["pop_guard"] * 768, n, atol=1e-8) for row, n in zip(curves, initial_guard_counts)):
        raise ValueError("initial guard frequencies do not correspond to 256 by three lives")
    columns = ("gen", "T", "fitness", "mean_fitness", "n_cells", "captures", "clicks", "body", "pop_body",
               "pop_guard", "guard", "pop_invalid", "pop_mismatch", "recheck_invalid", "recheck_changed",
               "best_id", "t_gen", "t_eval", "t_recheck")
    result = {"status": "complete" if complete else "checkpoint_only", "generation": generation,
              "checkpoint_sha256": hashlib.sha256(checkpoint_bytes).hexdigest(),
              "raw_genome_sha256": raw_digest(selected),
              "final_rank_zero_id": int(state["ids"][0]), "lineage": ancestry, "search_health": health,
              "initial_evaluation_guard_lives": sum(initial_guard_counts),
              "initial_evaluation_genome_lives": generation * 768,
              "recheck_genome_lives": generation * 256,
              "selection_T1024_equivalent_lives": int(sum(row["T"] for row in curves)),
              "raw_changed_slots_from_founder": int(np.count_nonzero(selected != inputs["founder"])),
              "genetic_distance_from_founder": float(np.linalg.norm(selected.astype(float) - inputs["founder"])),
              "final_population_mean_pair_distance": float(lines[-1]["distance"]),
              "periodic_validation": valid,
              "selected_trajectory": [{key: row[key] for key in columns} for row in curves],
              "guard_limit": "Full per-life search ledgers were not retained; initial guard counts are exact "
                             "from pop_guard, while pooled selected/recheck summaries do not identify all guard lives."}
    return result, selected


def prices(world):
    return {"living": ("live_time", world.c_live), "spiking": ("spikes", world.c_spike),
            "twitching": ("kappa_sum", world.c_tw), "messages": ("contact_events", world.c_msg),
            "division": ("claims", world.c_div), "secretion": ("sec_int", world.c_sec),
            "missed_clicks": ("misses", world.c_miss), "receptors": ("rec_gain", world.c_rec),
            "decoy_clicks": ("b2_clicks", max(0.0, -world.b2_value))}


def check_scores(data, seeds, world, ledger):
    if not np.array_equal(data["seeds"], seeds) or not np.array_equal(data["genome_indices"], np.arange(4)):
        raise ValueError("confirmation seed or genotype order differs")
    shape = (4, len(seeds))
    for key in (*ledger, "F_kernel", "extinct_charge", "window"):
        if data[key].shape != shape or not np.isfinite(data[key]).all():
            raise ValueError(f"invalid ledger column: {key}")
    status = data["status"].astype(np.int64)
    if not np.array_equal(data["status"], status) or np.any(status & 192):
        raise ValueError("noninteger status, capacity or ledger mismatch in confirmation")
    if np.any(((status & 7) == 0) & (data["t_end"] != world.t0 + world.T)):
        raise ValueError("unexplained incomplete confirmation life")
    window = world.T - world.t_open
    if not np.all(data["window"] == window):
        raise ValueError("incorrect scoring window")
    cost = sum(price * data[key] for key, price in prices(world).values())
    guard = np.where(status & 6 != 0, world.c_live * world.n_max * (world.t0 + world.T - data["t_end"]), 0)
    extinct = world.c_live * np.where(status & 1 != 0,
        world.t0 + world.T - np.maximum(data["t_ext"], world.t0 + world.t_open), 0) / window
    for key, value in (("cost", cost), ("guard_charge", guard), ("extinct_charge", extinct),
                       ("F_kernel", (data["income"] - cost - guard) / window)):
        if not np.allclose(data[key], value, rtol=1e-10, atol=1e-9):
            raise ValueError(f"independent accounting differs: {key}")
    if not np.array_equal(data["F"], data["F_kernel"] - data["extinct_charge"]):
        raise ValueError("production F differs from kernel/extinction accounting")


def pair_arrays(data, candidate, reference, world):
    window = world.T - world.t_open
    result = {"F": data["F"][candidate] - data["F"][reference],
              "income": (data["income"][candidate] - data["income"][reference]) / window,
              "cost_saving": (data["cost"][reference] - data["cost"][candidate]) / window,
              "guard_charge_saving": (data["guard_charge"][reference] - data["guard_charge"][candidate]) / window,
              "extinction_charge_saving": data["extinct_charge"][reference] - data["extinct_charge"][candidate]}
    result["accounting_residual"] = result["F"] - sum(result[k] for k in
        ("income", "cost_saving", "guard_charge_saving", "extinction_charge_saving"))
    for name, (key, price) in prices(world).items():
        result["cost_saving_" + name] = price * (data[key][reference] - data[key][candidate]) / window
    for key in ("captures", "clicks", "misses", "n_end", "live_time", "spikes", "path"):
        result[key] = data[key][candidate] - data[key][reference]
    return result


def npz(path):
    with np.load(path, allow_pickle=False) as loaded:
        return {key: loaded[key].copy() for key in loaded.files}


def confirmation(study, protocol, ready, endpoints, spec, searches):
    from dataclasses import asdict

    folder = study / "confirmation"
    manifest, report = read_json(folder / "manifest.json"), read_json(folder / "report.json")
    equal(report["status"], "complete", "confirmation status")
    equal(report["genome_lives"], 3072, "completed confirmation count")
    equal(manifest["labels"], list(LABELS), "genotype labels")
    equal(manifest["seeds"], list(range(51_900_000, 51_900_256)), "fresh confirmation seeds")
    equal(manifest["seed_block"], 90, "confirmation block")
    equal(manifest["ready"], ready, "confirmation readiness pins")
    equal(manifest["protocol_sha256"], digest(study / "protocol.json"), "confirmation protocol")
    equal(manifest["numerical_identity"], protocol["expected_numerical_identity"], "confirmation numerical identity")
    equal(manifest["search_health"], {str(s): searches[str(s)]["search_health"] for s in RUNS}, "search health")
    for seed in RUNS:
        equal(manifest["checkpoint_sha256"][str(seed)], searches[str(seed)]["checkpoint_sha256"], "checkpoint pin")
    stored = npz(folder / "genotypes.npz")
    if not identical(stored["genomes"], endpoints) or not np.array_equal(stored["labels"], LABELS):
        raise ValueError("confirmation genomes differ from fixed inputs/final rank-zero endpoints")
    for label, value in zip(LABELS, endpoints):
        equal(manifest["genotype_sha256"][label], raw_digest(value), "confirmation genotype hash")
    row_index = read_json(folder / "row_index.json")
    equal(set(row_index), {f"{t}/row_{i:04d}.npz" for t in DURATIONS for i in range(4)}, "raw row index")
    equal(set(manifest["worlds"]), {str(t) for t in DURATIONS}, "registered confirmation worlds")
    for relative, expected in row_index.items():
        row = folder / relative
        if row.exists():
            equal(digest(row), expected, "local raw confirmation row")
        else:
            raise ValueError("missing local raw confirmation row")
    comparisons = ((2, 1), (3, 1), (2, 0), (3, 0), (1, 0), (3, 2))
    per_duration, arrays, safety = {}, {}, {}
    for duration in DURATIONS:
        world = spec.world("catch_speck_l4", T=duration, d0=0.5, d_min=0.25, sigma=0.4, lam_s=4.0)
        equal(manifest["worlds"][str(duration)], asdict(world), "confirmation world")
        data = npz(folder / str(duration) / "scores.npz")
        check_scores(data, manifest["seeds"], world, spec.V3.LEDGER)
        expected_income = world.R_cap * data["captures"] + max(0.0, world.b2_value) * data["b2_clicks"]
        if (not np.allclose(data["income"], expected_income, rtol=1e-10, atol=1e-9)
                or not np.allclose(data["net"], data["income"] - data["cost"] - data["guard_charge"],
                                   rtol=1e-10, atol=1e-9)):
            raise ValueError("capture income or net ledger accounting differs")
        per_duration[str(duration)] = {}
        safety[str(duration)] = {}
        for i, label in enumerate(LABELS):
            flags = data["status"][i].astype(np.int64)
            safety[str(duration)][label] = {
                "F": stats(data["F"][i]), "captures": stats(data["captures"][i]),
                "n_end": stats(data["n_end"][i]),
                "status_flag_counts": {key: int(np.count_nonzero(flags & bit)) for key, bit in spec.STATUS.items()},
                "distinct_status_counts": {str(int(flag)): int(np.sum(flags == flag)) for flag in np.unique(flags)}}
        for candidate, reference in comparisons:
            label = LABELS[candidate] + "__vs__" + LABELS[reference]
            values = pair_arrays(data, candidate, reference, world)
            arrays.setdefault(label, {})[duration] = values
            per_duration[str(duration)][label] = {key: stats(value) for key, value in values.items()}
            if candidate in (2, 3) and reference in (0, 1):
                saved = report["worlds"][str(duration)][LABELS[candidate]]["vs_founder" if reference else "vs_pilot"]
                check_stats(per_duration[str(duration)][label]["F"], saved["F"], label)
                for key in ("income", "cost_saving", "guard_charge_saving", "extinction_charge_saving",
                            "accounting_residual"):
                    check_stats(per_duration[str(duration)][label][key], saved["fitness_contributions"][key], key)
        for index in range(4):
            path = folder / str(duration) / f"row_{index:04d}.npz"
            if path.exists():
                raw = npz(path)
                if raw["ledger"].shape != (256, 57) or raw["ledger"].dtype != np.float64:
                    raise ValueError("raw complete ledger dimensions differ")
                equal(raw["seeds"].tolist(), manifest["seeds"], "raw confirmation seeds")
                equal(int(raw["genome_index"]), index, "raw confirmation row identity")
                for column, key in enumerate(spec.V3.LEDGER):
                    if not identical(raw["ledger"][:, column], raw["F_kernel" if key == "F" else key]):
                        raise ValueError("raw ledger differs from scored column " + key)
                for key in (*spec.V3.LEDGER, "F_kernel", "extinct_charge", "window"):
                    if not identical(raw[key], data[key][index]):
                        raise ValueError("aggregate differs from hashed raw row")
    combined, contrasts = {}, {"seeds": np.asarray(manifest["seeds"], dtype=np.uint64)}
    for label, durations in arrays.items():
        combined[label] = {key: stats(mixture({t: durations[t][key] for t in DURATIONS}))
                           for key in durations[1024]}
        for t in DURATIONS:
            contrasts[f"{label}__T{t}"] = durations[t]["F"]
        contrasts[label + "__duration_average"] = mixture({t: durations[t]["F"] for t in DURATIONS})
    primary = {}
    for label in LABELS[2:]:
        value = combined[label + "__vs__founder_row29"]["F"]
        check_stats(value, report["primary"][label], "primary mixture")
        primary[label] = {**value, "above_3se": value["mean"] > 3 * value["se"],
                          "at_least_0p5": value["mean"] >= 0.5}
        for key in ("above_3se", "at_least_0p5"):
            equal(primary[label][key], report["primary"][label][key], "primary threshold")
    return {"primary": primary, "duration_average": combined, "per_duration": per_duration,
            "per_genotype": safety, "paired_seed_clusters": 256, "genome_lives": 3072}, contrasts


def analyze(study):
    study = Path(study).resolve()
    budget = read_json(operation(study, "budget.json")) if operation(study, "budget.json").exists() else {}
    complete = budget.get("status") == "complete"
    if not complete:
        return {"status": budget.get("status", "not_started"), "confirmation": None,
                "interpretation": "Incomplete L study: no search outcomes or endpoint claims inspected."}, {}
    protocol, ready, inputs, spec = frozen_inputs(study)
    if complete:
        equal(sorted((x["name"], x["exit_code"]) for x in budget["completed"]),
              [("confirmation", 0), ("evolve_s51891", 0), ("evolve_s51892", 0)], "completed jobs")
        if budget["running"] or budget["queued"] or budget["cpu_seconds"] > protocol["max_cpu_seconds"]:
            raise ValueError("completed resource record is inconsistent")
        equal(budget["ready"], ready, "resource release identity")
        equal(budget["exit_code"], 0, "successful monitor exit")
        equal(budget["cap_cpu_seconds"], 14400, "resource cap")
        if not np.isfinite(budget["cpu_seconds"]) or budget["cpu_seconds"] <= 0:
            raise ValueError("invalid final resource usage")
    summary = {"study": "two_fixed_s7_16_generation_continuations", "status": budget.get("status", "not_started"),
               "report_only": True, "protocol_sha256": digest(study / "protocol.json"), "searches": {},
               "resources": budget, "planned_genome_lives": protocol["planned_genome_lives"],
               "limitations": LIMITATIONS}
    endpoints = [inputs["pilot"], inputs["founder"]]
    for seed in RUNS:
        report, endpoint = search_audit(study, seed, protocol, inputs, spec, complete)
        summary["searches"][str(seed)] = report
        endpoints.append(endpoint)
    summary["audited_checkpoint_selection_lives"] = sum(
        value.get("initial_evaluation_genome_lives", 0) + value.get("recheck_genome_lives", 0)
        for value in summary["searches"].values())
    summary["confirmation"], contrasts = confirmation(
        study, protocol, ready, np.stack(endpoints), spec, summary["searches"])
    equal(summary["audited_checkpoint_selection_lives"], 32768, "selection life count")
    equal(
        sum(x["selection_T1024_equivalent_lives"] for x in summary["searches"].values()),
        protocol["selection_T1024_equivalent_lives"], "duration-adjusted selection life count")
    equal(sum(len(x["periodic_validation"]) * 16 for x in summary["searches"].values()), 160, "valid life count")
    summary["completed_genome_lives"] = 36012
    summary["life_accounting"] = {"selection": 32768, "periodic_validation": 160,
                                  "tiny_final_diagnostics": 12, "tiny_final_half_duration_lives": 4,
                                  "independent_confirmation": 3072,
                                  "numerical_golden_replays": "Additional engine self-checks; included in CPU usage."}
    return summary, contrasts


def plots(out, summary):
    if summary["status"] != "complete":
        return
    import matplotlib

    matplotlib.use("Agg")
    import matplotlib.pyplot as plt

    fig, axes = plt.subplots(1, 2, figsize=(10, 4.1), constrained_layout=True)
    colors = ("#276b9d", "#c06527")
    for i, seed in enumerate(RUNS):
        rows = summary["searches"][str(seed)]["periodic_validation"]
        axes[0].plot([r["generation"] + 1 for r in rows], [r["F"] for r in rows], "o-",
                     label=f"seed {seed}", color=colors[i])
        label = LABELS[i + 2]
        value = summary["confirmation"]["primary"][label]
        axes[1].errorbar(value["mean"], i, xerr=3 * value["se"], fmt="o", color=colors[i], capsize=5)
    axes[0].set(xlabel="Completed generations", ylabel="Periodic validation F (16 lives)",
                title="Selected genomes at T1024\n16 fresh lives per checkpoint")
    axes[0].legend(frameon=False)
    axes[1].axvline(0, color="#666", lw=1)
    axes[1].axvline(0.5, color="#888", ls=":", label="Registered practical gain: 0.5 F")
    axes[1].set(yticks=[0, 1], yticklabels=["search 51891", "search 51892"],
                xlabel="Final rank-zero gain versus founder (±3 SE)",
                title="Independent equal-duration mixture\n256 shared seed clusters", ylim=(-0.8, 1.8))
    axes[1].legend(frameon=False, loc="upper left", fontsize=8)
    fig.savefig(out / "continuation_summary.png", dpi=170)
    plt.close(fig)


def export(study, target, summary, analysis_out):
    if summary["status"] != "complete":
        raise ValueError("export requires all runs and confirmation to complete within the cap")
    study, target = Path(study).resolve(), Path(target).resolve()
    if study == target:
        return
    protocol, ready = read_json(study / "protocol.json"), read_json(study / "ready.json")
    historical = target / "prelaunch"
    if not historical.exists():
        prepared = read_json(target / "provenance.json")
        equal(prepared["status"], "prepared_not_released", "original public preparation")
        provenance_check(target)
        for relative in (*prepared["artifacts"], "provenance.json"):
            destination = historical / relative
            destination.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(target / relative, destination)
    files = {}
    prior = study / "inputs/prior_provenance.json"
    files["inputs/prior_provenance.json"] = (
        prior if prior.exists() else ROOT / "results/pool_mutants_20261013/provenance.json")
    for name in ("protocol.json", "ready.json", "seed_audit.json", "initialization.json", "search_health.json"):
        files[name] = study / name
    for folder in ("configs", "inputs", "runs", "logs", "initialization"):
        files.update({str(p.relative_to(study)): p for p in (study / folder).rglob("*") if p.is_file()})
    for name in ("run_budgeted.py", "measure.py", "prepare.py", "test_prepared.py", "test_monitor.py", "budget.json"):
        path = operation(study, name)
        if path.exists():
            files["operations/" + name] = path
    for relative in protocol["source_identity"]:
        files["sources/" + relative] = source(study, relative)
    for name in ready["helpers"]:
        files["sources/scripts/" + name] = source(study, "scripts/" + name)
    for relative in protocol["reference_sources"]:
        files[relative] = study / relative
    files["sources/G_audit_search.py"] = study / "sources/G_audit_search.py"
    for relative in protocol["template_pins"]:
        files["templates/" + relative] = template(study, relative)
    for relative in protocol["wait_for_studies"]:
        for name in ("protocol.json", "run_budgeted.py", "budget.json"):
            files[str(Path("dependencies") / Path(relative).name / name)] = operation(dependency(study, relative), name)
    for path in (study / "confirmation").rglob("*"):
        if path.is_file() and path.suffix in (".json", ".npz"):
            files[str(path.relative_to(study))] = path
    files["analyze.py"] = Path(__file__)
    test_file = Path(__file__).with_name("test_analyze.py")
    if test_file.exists():
        files["test_analyze.py"] = test_file
    for name in ("summary.json", "contrasts.npz", "continuation_summary.png"):
        files[name] = analysis_out / name
    total = sum(path.stat().st_size for path in files.values())
    if total > 50 * 1024 * 1024:
        raise ValueError(f"archive unexpectedly large: {total} bytes; review before copying")
    target.mkdir(parents=True, exist_ok=True)
    for relative, original in files.items():
        destination = target / relative
        destination.parent.mkdir(parents=True, exist_ok=True)
        if destination.exists() and digest(destination) != digest(original) and (target / "provenance.json").exists():
            raise ValueError("refuse to overwrite a differing frozen archive artifact: " + relative)
        if destination.resolve() != original.resolve():
            shutil.copy2(original, destination)
    lines = ["# Two fixed continuation replicates", "", "Each run starts from the same previously selected s7 row29 "
             "founder: one exact copy and 31 ordinary mutated copies. Ordinary sexual evolution runs 16 generations "
             "with 32 parents, 224 offspring, three initial lives and four recheck lives on the top64. "
             "All parents are reevaluated; the founder and historical best are not protected.", "",
             "Final population rank zero is fixed before fresh confirmation. Both endpoints, founder and original "
             "pilot are measured on the same 256 seeds at each of T768/1024/1536. The primary averages the three "
             "paired effects within seed; SE uses 256 clusters.", "",
             "| Search | Additional gain versus founder (mean ± SE) | >3 SE | ≥0.5 F |",
             "| --- | ---: | --- | --- |"]
    for label, value in summary["confirmation"]["primary"].items():
        lines.append(f"| {label} | {value['mean']:+.6f} ± {value['se']:.6f} | "
                     f"{value['above_3se']} | {value['at_least_0p5']} |")
    lines += ["", f"Completed research lives: {summary['completed_genome_lives']:,}. Monitored CPU: "
              f"{summary['resources']['cpu_seconds']:.6f} seconds, within the 14,400-second cap.", "",
              "The archive retains final checkpoints, all populations and lineage, search/validation curves, "
              "source/configuration/numerical pins, the prospective initial populations, and every raw confirmation "
              "ledger beside the independently checked aggregate. The original public preparation is preserved "
              "under prelaunch/. Both negative and unresolved outcomes remain.", "",
              "Independent reanalysis (no simulation):", "",
              "```sh", "python results/s7_continuation_20261014/analyze.py --study results/s7_continuation_20261014 "
              "--out outputs/s7_continuation_reanalysis", "```", "",
              "Requires NumPy, PyTorch, OmegaConf and Matplotlib from the project environment. Frozen src is included "
              "for schema/hash definitions. operations/run_budgeted.py records the executed launch and cap logic; "
              "its original relative paths are provenance, not a standalone archived launcher.", ""]
    lines += ["- " + value for value in LIMITATIONS]
    (target / "README.md").write_text("\n".join(lines) + "\n")
    # The old preparation manifest describes its original README, preserved under prelaunch/.
    # Publish a completed manifest only after the copied study independently reproduces the result.
    (target / "provenance.json").unlink(missing_ok=True)
    checked, rebuilt = analyze(target)
    equal(checked, summary, "public independent summary")
    saved = npz(target / "contrasts.npz")
    equal(set(saved), set(rebuilt), "public paired contrast names")
    if any(not identical(saved[key], value) for key, value in rebuilt.items()):
        raise ValueError("public paired contrast bytes differ")
    artifacts = {str(path.relative_to(target)): {"sha256": digest(path), "bytes": path.stat().st_size}
                 for path in sorted(target.rglob("*")) if path.is_file() and path != target / "provenance.json"
                 and "__pycache__" not in path.parts and ".pytest_cache" not in path.parts}
    write_json(target / "provenance.json", {"format": 1, "status": "complete", "artifacts": artifacts,
        "protocol_sha256": digest(study / "protocol.json"), "analysis_sha256": digest(Path(__file__)),
        "source_identity": protocol["source_identity"], "numerical_identity": protocol["expected_numerical_identity"],
        "total_artifact_bytes": sum(value["bytes"] for value in artifacts.values()),
        "no_simulation_during_analysis": True})


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--study", type=Path, default=Path(__file__).resolve().parent)
    parser.add_argument("--out", type=Path)
    parser.add_argument("--export", action="store_true")
    parser.add_argument("--target", type=Path,
                        default=ROOT / "results/s7_continuation_20261014" if ROOT else Path("continuation_archive"))
    args = parser.parse_args()
    out = args.out or args.study / "analysis"
    out.mkdir(parents=True, exist_ok=True)
    summary, contrasts = analyze(args.study)
    write_json(out / "summary.json", summary)
    if contrasts:
        np.savez_compressed(out / "contrasts.npz", **contrasts)
        plots(out, summary)
    if args.export:
        export(args.study, args.target, summary, out)
    print(json.dumps({"status": summary["status"], "summary": str(out / "summary.json"),
                      "completed_genome_lives": summary.get("completed_genome_lives"),
                      "primary": (summary.get("confirmation") or {}).get("primary")}, indent=2))


if __name__ == "__main__":
    main()
