"""Offline U search/genetic audit. Reads no confirmation outcomes; runs no lives."""
from __future__ import annotations

import copy
import hashlib
import importlib.util
import io
import json
import os
from pathlib import Path
import sys
import time

os.environ.setdefault("ATEN_CPU_CAPABILITY", "avx2")
os.environ.setdefault("OMP_NUM_THREADS", "1")
os.environ.setdefault("MKL_NUM_THREADS", "1")
sys.dont_write_bytecode = True
ROOT = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(ROOT))
import numpy as np
import torch

STUDY = ROOT / "outputs/autonomous_decoy_evolution_20261014"
OUT = Path(__file__).resolve().parent
PROTOCOL_SHA = "3711f50e66d7a558708da9ee95cd8ddc79648763cf1633c08fc4315006af42f5"
HELPERS = {
    "L": ("results/s7_continuation_20261014/analyze.py",
          "41b97ad3f22db01778d21fe3bb52952016423cb83f453aa1449743d36884c7bd"),
    "G": ("results/s7_continuation_20261014/sources/G_audit_search.py",
          "8fd717bdecb5f0e073e04838bbf286a4a968924bc9848b55c5a8d2b2055f4139"),
}
READS = {}


def read_bytes(path):
    path = Path(path)
    data = path.read_bytes()
    READS[str(path.relative_to(ROOT))] = hashlib.sha256(data).hexdigest()
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
        path = ROOT / relative
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


def audit():
    started = time.process_time()
    torch.set_num_threads(1)
    equal(sha(STUDY / "protocol.json"), PROTOCOL_SHA, "frozen U protocol")
    protocol = read(STUDY / "protocol.json")
    equal(protocol["runs"], [53091, 53092], "fixed runs")
    equal(protocol["generations"], 4, "fixed generations")
    equal(sha(STUDY / "initialization.json"), protocol["initialization_audit_sha256"], "initialization pin")
    equal(sha(STUDY / "seed_audit.json"), protocol["seed_audit_sha256"], "seed audit pin")
    for relative, expected in protocol["source_identity"].items():
        equal(sha(ROOT / relative), expected, "source pin " + relative)
    L, G = load_helpers()
    # These modules only define genome operations and the stateless seed hash.
    from src.genome import Layout
    from src.life import spec
    initialization = read(STUDY / "initialization.json")
    endpoints = read(STUDY / "confirmation/endpoints.json")
    equal(endpoints["protocol_sha256"], PROTOCOL_SHA, "preconfirmation protocol")
    equal(endpoints["numerical_identity"], protocol["expected_numerical_identity"], "saved confirmation identity")
    labels = ["I_s5_row32", "I_s7_row1", "s53091_final_rank0", "s53092_final_rank0"]
    equal(endpoints["labels"], labels, "frozen endpoint labels")
    with np.load(io.BytesIO(read_bytes(STUDY / "confirmation/genotypes.npz")), allow_pickle=False) as data:
        equal(set(data.files), {"genomes", "labels"}, "genotype metadata fields")
        genomes = data["genomes"].copy()
        equal(data["labels"].tolist(), labels, "genotype labels")
    equal(genomes.shape, (4, 875), "confirmation genotype shape")
    equal(str(genomes.dtype), "float32", "confirmation genotype dtype")
    if not np.isfinite(genomes).all():
        raise ValueError("nonfinite confirmation genotypes")
    equal({label: raw(genome) for label, genome in zip(labels, genomes)}, endpoints["genotype_sha256"],
          "every frozen confirmation genotype hash")
    results = {}
    for i, seed in enumerate(protocol["runs"]):
        key = str(seed)
        folder = STUDY / f"runs/s{seed}"
        founder_meta = protocol["founder_mapping"][key]
        founder_path = ROOT / founder_meta["founder_file"]
        equal(sha(founder_path), founder_meta["file_sha256"], "founder file")
        layout, founder = Layout.load(founder_path)
        equal(raw(founder.numpy()), founder_meta["raw_sha256"], "founder raw genotype")
        if not L.identical(founder.numpy(), genomes[i]):
            raise ValueError("confirmation reference differs from registered founder")
        config_path = ROOT / protocol["configs"][key]["path"]
        equal(sha(config_path), protocol["configs"][key]["sha256"], "search configuration")
        cfg = L.config_identity(config_path)
        equal(cfg["life"]["T"], 1024, "fixed selection duration")
        equal(cfg["life"]["T_choices"], None, "no selection duration mixture")
        for name, expected in {"mu": 32, "lam": 224, "generations": 4, "breeding": "sex",
                               "dup_rate": 0.0, "del_rate": 0.0, "recheck_k": 64,
                               "recheck_lives": 4, "recheck_key": "all"}.items():
            equal(cfg["evolve"][name], expected, "registered operator " + name)
        checkpoint_bytes = read_bytes(folder / "checkpoint.pt")
        saved = torch.load(io.BytesIO(checkpoint_bytes), map_location="cpu", weights_only=True)
        equal(saved["format"], 1, "checkpoint format")
        equal(saved["config"], cfg, "checkpoint configuration")
        sha(folder / "config.yaml")
        equal(L.config_identity(folder / "config.yaml"), cfg, "saved run configuration")
        equal(saved["identity"], protocol["expected_numerical_identity"], "saved numerical identity")
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
        equal(lines[0]["seeded"], founder_meta["founder_file"], "recorded founder input")
        view_lines, view_curves = selection_view(lines, curves, 1024)
        selection = L.audit_lineage(view_lines, view_curves, state, seed, spec)
        receipt = initialization["runs"][key]
        equal(receipt["shape"], [32, 875], "initial population shape")
        equal(receipt["dtype"], "float32", "initial population dtype")
        equal(receipt["founder_ids"], [0], "initial exact founder ids")
        equal(receipt["copies"], lines[0]["copies"], "prospective recorded initial mutations")
        initial_path = STUDY / receipt["population_file"]
        equal(sha(initial_path), receipt["file_sha256"], "prospective population file")
        initial = np.load(io.BytesIO(read_bytes(initial_path)), allow_pickle=False)
        reconstructed = np.stack([founder.numpy()] + [
            G.point_mutation(layout, founder, child["ops"]).numpy() for child in receipt["copies"]])
        if not L.identical(initial, reconstructed):
            raise ValueError("initial population does not replay bitwise")
        equal(raw(initial), receipt["population_raw_sha256"], "initial raw population")
        equal([raw(row) for row in initial], receipt["row_raw_sha256"], "every initial raw row")
        replay = G.replay_genetics(lines, state, layout, founder, structural=False)
        health = {name: max(float(row[name]) for row in curves)
                  for name in ("pop_invalid", "pop_mismatch", "recheck_invalid")}
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
        if not L.identical(genomes[i + 2], population[0]):
            raise ValueError("frozen confirmation genotype differs from final rank zero")
        recorded = endpoints["endpoints"][key]
        equal(recorded, {"checkpoint_sha256": hashlib.sha256(checkpoint_bytes).hexdigest(),
              "genome_file_sha256": sha(folder / "best_genome.json"), "genome_raw_sha256": raw(population[0]),
              "generation": 4, "rank": 0, "search_health": health}, "frozen endpoint binding")
        guards = [round(row["pop_guard"] * 768) for row in curves]
        if not all(np.isclose(row["pop_guard"] * 768, n, rtol=0, atol=1e-8)
                   for row, n in zip(curves, guards)):
            raise ValueError("initial guard frequencies are not exact life counts")
        results[key] = {"status": "passed", "generation": 4, "final_rank_zero_id": int(state["ids"][0]),
                        "checkpoint_sha256": recorded["checkpoint_sha256"],
                        "genome_raw_sha256": recorded["genome_raw_sha256"],
                        "prospective_initial_population_bitwise": True, "selection": selection,
                        "genetic_replay": replay, "search_health": health,
                        "initial_evaluation_genome_lives": 3072, "recheck_genome_lives": 1024,
                        "initial_evaluation_guard_lives_by_generation": guards,
                        "final_rank_zero_binding": True, "all_final_population_rows_bound": True}
    forbidden = sorted(name for name in sys.modules if name.startswith(("src.life.build", "src.life.evaluate",
                       "src.life.reference", "src.checkpoint", "src.evolve", "src.run")))
    equal(forbidden, [], "simulation/checkpoint execution modules not imported")
    return {"status": "passed", "study": str(STUDY.relative_to(ROOT)), "protocol_sha256": PROTOCOL_SHA,
            "runs": results, "simulated_lives": 0, "numerical_golden_checks_executed": False,
            "confirmation_outcomes_read": False,
            "confirmation_metadata_only": ["confirmation/endpoints.json", "confirmation/genotypes.npz"],
            "helper_sources": {name: {"path": path, "sha256": value} for name, (path, value) in HELPERS.items()},
            "read_artifact_sha256": dict(sorted(READS.items())), "script_sha256": sha(__file__),
            "audit_process_cpu_seconds": time.process_time() - started,
            "limits": ["Replays recorded genetic operations, not random-number draws or life simulations.",
                       "Selection is checked against logged shortlist scores; unretained per-life search ledgers cannot be reconstructed.",
                       "Search guard frequencies cover initial three-life evaluations; logs do not enumerate every recheck guard life.",
                       "Saved numerical identity receipts are compared; fresh numerical goldens are intentionally not executed.",
                       "Fixed T1024 from the pinned config is supplied to the reused L selection helper because U logs omit constant T.",
                       "No confirmation outcomes are read and no behavioral or out-of-sample performance conclusion is made."]}


if __name__ == "__main__":
    result = audit()
    (OUT / "receipt.json").write_text(json.dumps(result, indent=2, allow_nan=False) + "\n")
    print(json.dumps({"status": result["status"], "runs": list(result["runs"]),
                      "simulated_lives": 0, "audit_process_cpu_seconds": result["audit_process_cpu_seconds"]}))
