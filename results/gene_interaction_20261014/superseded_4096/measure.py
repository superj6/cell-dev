"""Fixed source/copy gene-deletion factorial on both G endpoints; dry-run default."""
from __future__ import annotations

import argparse
import hashlib
import importlib.util
import json
import os
import sys
from dataclasses import asdict
from pathlib import Path

os.environ.setdefault("ATEN_CPU_CAPABILITY", "avx2")
ROOT = next(p for p in Path(__file__).resolve().parents if (p / "src/genome.py").exists())
sys.path.insert(0, str(ROOT))
STUDY = ROOT / "outputs/autonomous_gene_interaction_20261014"
RUNS, LIVES, CAP = (51089, 51090), 512, 3600
ROLES = ("intact", "copy_KO", "source_KO", "double_KO")
HELPERS = ("taskvar_confirm.py", "taskvar_second_step.py", "taskvar_gradient.py", "taskvar_gates.py")
G_AUDIT_SHA = "8fd717bdecb5f0e073e04838bbf286a4a968924bc9848b55c5a8d2b2055f4139"


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def raw_sha(array):
    return hashlib.sha256(array.tobytes()).hexdigest()


def read_json(path):
    return json.loads(Path(path).read_text())


def check_protocol(study=None):
    study = STUDY if study is None else Path(study)
    p = read_json(study / "protocol.json")
    expected = {"runs": list(RUNS), "lives": 512, "seed_block": 100, "genome_lives": 4096,
                "max_cpu_seconds": CAP, "threads": 2, "T": 1024, "roles": list(ROLES),
                "endpoint_rule": "exact final population rank0 at generation16",
                "wait_for_studies": ["outputs/autonomous_s7_20261014"]}
    if any(p[key] != value for key, value in expected.items()):
        raise ValueError("registered scope differs")
    for relative, digest in p["source_identity"].items():
        if sha(ROOT / relative) != digest:
            raise ValueError("numerical source differs: " + relative)
    if set(p["helpers"]) != set(HELPERS):
        raise ValueError("helper pin set differs")
    for name, digest in p["helpers"].items():
        if sha(ROOT / "scripts" / name) != digest:
            raise ValueError("helper differs: " + name)
    for relative, digest in p["inputs"].items():
        if sha(study / relative) != digest:
            raise ValueError("fixed input differs: " + relative)
    for name in ("prepare.py", "PREREG.md", "seed_audit.json", "genomes.json", "genotypes.npy"):
        if sha(study / name) != p["preparation_pins"][name]:
            raise ValueError("preparation pin differs: " + name)
    if sha(study / "sources/G_audit_search.py") != G_AUDIT_SHA:
        raise ValueError("reviewed genetic replay source differs")
    if p["seeds"] != seeds() or p["world"] != asdict(world()):
        raise ValueError("registered world or seed list differs")
    return p


def world():
    from src.life import spec

    return spec.world("catch_speck_l4", T=1024, d0=.5, d_min=.25, sigma=.4, lam_s=4)


def seeds():
    return list(range(52_000_000, 52_000_512))


def load_endpoints(study=None):
    """Read only completed G and replay every genetic operation; no life simulation."""
    import numpy as np
    from omegaconf import OmegaConf

    from src import checkpoint
    from src.genome import Layout

    study = STUDY if study is None else Path(study)
    g = study / "inputs/G"
    budget = read_json(g / "operations/budget.json")
    if budget["status"] != "complete" or budget.get("running") or budget.get("queued"):
        raise ValueError("G must complete before endpoint inspection")
    protocol = read_json(g / "protocol.json")
    source = study / "sources/G_audit_search.py"
    if sha(source) != G_AUDIT_SHA:
        raise ValueError("reviewed genetic replay source differs")
    loader = importlib.util.spec_from_file_location("interaction_G_audit", source)
    audit = importlib.util.module_from_spec(loader)
    loader.loader.exec_module(audit)
    layout, founder = Layout.load(study / "inputs/founder_row38.json")
    records = {}
    for seed in RUNS:
        folder = g / f"runs/s{seed}"
        checkpoint_data = checkpoint.load(folder / "checkpoint.pt")
        checkpoint.validate(checkpoint_data, OmegaConf.load(g / f"configs/s{seed}.yaml"),
                            protocol["expected_numerical_identity"])
        state = checkpoint_data["state"]
        if state["generation"] != 16 or [row["gen"] for row in state["curves"]] != list(range(16)):
            raise ValueError("G endpoint generation/history incomplete")
        health = {key: max(row[key] for row in state["curves"])
                  for key in ("pop_invalid", "pop_mismatch", "recheck_invalid")}
        if any(health.values()):
            raise ValueError("invalid or mismatched G search lives")
        final_layout, genome = Layout.load(folder / "best_genome.json")
        if final_layout.dims != layout.dims or genome.numpy().tobytes() != state["population"][0].numpy().tobytes():
            raise ValueError("G best differs from final rank0")
        lines = [json.loads(line) for line in (folder / "lineage.jsonl").read_text().splitlines() if line.strip()]
        genetic = audit.replay_genetics(lines, state, layout, founder, structural=True)
        origins = state["origins"][0].numpy().copy()
        if not np.array_equal(layout.active(genome).numpy(), origins >= 0):
            raise ValueError("active slots differ from lineage origins")
        records[seed] = {"genome": genome, "origins": origins, "innovations": genetic["duplication_origins"],
                         "audit": {"checkpoint_sha256": sha(folder / "checkpoint.pt"),
                                   "lineage_sha256": sha(folder / "lineage.jsonl"), "health": health,
                                   "genetic_replay": genetic, "genome_raw_sha256": raw_sha(genome.numpy())}}
    return layout, records


def candidates(layout, endpoints):
    """Resolve actual source ancestry, then freeze all four roles without using performance."""
    import numpy as np

    genomes, labels, branches = [], [], {}
    for seed in RUNS:
        record = endpoints[seed]
        genome, origins = record["genome"], record["origins"]
        active = layout.active(genome).numpy()
        if not np.array_equal(active, origins >= 0):
            raise ValueError("active slots disagree with origins")
        copied = np.flatnonzero(active & (origins >= 16))
        if len(copied) != 1:
            raise ValueError("fixed endpoint must have exactly one active copied-origin gene")
        copy_slot, copy_origin = int(copied[0]), int(origins[copied[0]])
        events = [event for event in record["innovations"] if event["origin_id"] == copy_origin]
        if len(events) != 1:
            raise ValueError("copy origin must resolve to one replayed duplication event")
        event = events[0]
        source_origin = event["source_origin_id"]
        matches = np.flatnonzero(active & (origins == source_origin))
        if len(matches) != 1 or matches[0] == copy_slot:
            raise ValueError("exact source origin is absent or ambiguous; no replacement gene is permitted")
        source_slot = int(matches[0])
        branch = {"copy_slot": copy_slot, "copy_origin_id": copy_origin,
                  "source_slot": source_slot, "source_origin_id": int(source_origin),
                  "duplication_event": event, "origins": origins.tolist(), "rows": {}}
        for role, deleted in zip(ROLES, ((), (copy_slot,), (source_slot,), (copy_slot, source_slot))):
            edited, canonical = genome.clone(), genome.clone()
            for slot in deleted:
                edited = layout.delete(edited, slot)
                layout.view(canonical, "act")[slot] = 0
            packed = layout.pack(edited[None], "hexprism")
            if packed.tobytes() != layout.pack(canonical[None], "hexprism").tobytes():
                raise ValueError("deletion runtime table differs from canonical inactive-gene masks")
            if role == "double_KO":
                reverse = layout.delete(layout.delete(genome, source_slot), copy_slot)
                if reverse.numpy().tobytes() != edited.numpy().tobytes():
                    raise ValueError("double deletion depends on operator order")
            branch["rows"][role] = {"row": len(genomes), "deleted_slots": list(deleted),
                                   "raw_sha256": raw_sha(edited.numpy()),
                                   "runtime_table_sha256": raw_sha(packed),
                                   "active_slots": np.flatnonzero(layout.active(edited).numpy()).tolist()}
            genomes.append(edited.numpy().copy())
            labels.append(f"s{seed}_{role}")
        branches[str(seed)] = branch
    return np.stack(genomes), labels, branches


def load_frozen(protocol):
    import numpy as np

    layout, records = load_endpoints()
    genomes, labels, branches = candidates(layout, records)
    frozen = read_json(STUDY / "genomes.json")
    saved = np.load(STUDY / "genotypes.npy", allow_pickle=False)
    audits = {str(seed): record["audit"] for seed, record in records.items()}
    expected = {"labels": labels, "branches": branches, "endpoint_audits": audits,
                "genotypes_raw_sha256": raw_sha(genomes), "simulated_lives": 0}
    if frozen != expected or saved.shape != genomes.shape or saved.dtype != genomes.dtype:
        raise ValueError("frozen prospective genotype mapping differs")
    if saved.tobytes() != genomes.tobytes() or len(genomes) != 8:
        raise ValueError("frozen prospective genotypes differ")
    return layout, genomes, frozen


def factorial(rows, branch, settings):
    """All arithmetic is within seed; opposite signs and individual losses are retained."""
    import numpy as np

    from scripts.taskvar_confirm import compare_rows
    from scripts.taskvar_gates import paired
    from src.life import spec

    selected = {role: rows[branch["rows"][role]["row"]] for role in ROLES}
    if any(np.asarray(row["F"]).shape != (LIVES,) or not np.isfinite(row["F"]).all()
           for row in selected.values()):
        raise ValueError("need finite paired 512-life fitness rows")
    weights = (1., -1., -1., 1.)
    values = {key: sum(weight * selected[role][key] for role, weight in zip(ROLES, weights))
              for key in (*spec.V3.LEDGER, "F_kernel", "extinct_charge", "window")}
    pieces = {"income": values["income"] / settings.T, "cost_saving": -values["cost"] / settings.T,
              "guard_charge_saving": -values["guard_charge"] / settings.T,
              "extinction_charge_saving": -values["extinct_charge"]}
    pieces["accounting_residual"] = values["F"] - sum(pieces.values())
    interaction = {key: paired(value, np.zeros_like(value)) for key, value in values.items() if key != "status"}
    interaction["fitness_contributions"] = {key: paired(value, np.zeros_like(value)) for key, value in pieces.items()}
    f = interaction["F"]
    interaction.update(abs_above_3se=abs(f["mean"]) > 3 * f["se"], abs_at_least_0p5=abs(f["mean"]) >= .5)
    losses = {role: compare_rows(selected["intact"], selected[role], settings) for role in ROLES[1:]}
    contrasts = {"interaction": values["F"], **{role + "_loss": selected["intact"]["F"] - selected[role]["F"]
                                               for role in ROLES[1:]}}
    return {"interaction": interaction, "losses": losses}, contrasts


def run():
    import numpy as np
    from omegaconf import OmegaConf
    from run_budgeted import check_ready

    from scripts.taskvar_confirm import COLS, atomic_json, atomic_npz
    from scripts.taskvar_second_step import RowStore, freeze
    from src.checkpoint import numerical_identity
    from src.life.evaluate import LifeEvaluator

    protocol, ready = check_protocol(), check_ready()
    identity = numerical_identity()
    if identity != protocol["numerical_identity"]:
        raise ValueError("numerical identity differs")
    layout, genomes, frozen = load_frozen(protocol)
    settings, out = world(), STUDY / "measurement"
    manifest = {"format": 1, "frozen_genomes": frozen, "world": asdict(settings), "seeds": seeds(),
                "numerical_identity": identity, "protocol_sha256": sha(STUDY / "protocol.json"), "ready": ready,
                "genome_lives": 4096, "seed_block": 100}
    out.mkdir(parents=True, exist_ok=True)
    freeze(out / "manifest.json", manifest, "all fixed factorial interventions")
    atomic_npz(out / "genotypes.npz", genomes=genomes, labels=np.asarray(frozen["labels"]))
    evaluator = LifeEvaluator(OmegaConf.load(STUDY / "inputs/evaluator.yaml"), layout)
    store = RowStore(out, genomes, settings, evaluator, 2, CAP)
    report = {"status": "incomplete", "endpoints": {}, "row_cpu_seconds": 0,
              "research_genome_lives": 0, "limitations": protocol["limitations"]}
    rows = {}
    for i in range(len(genomes)):
        if store.cpu_seconds >= CAP:
            raise RuntimeError("cpu_budget_stop")
        rows[i] = store.row("rows", i, seeds())
        report.update(row_cpu_seconds=store.cpu_seconds, research_genome_lives=(i + 1) * LIVES)
        atomic_json(out / "report.json", report)
    atomic_npz(out / "scores.npz", seeds=np.asarray(seeds(), dtype=np.uint64), genome_indices=np.arange(8),
               **{key: np.stack([rows[i][key] for i in range(8)]) for key in COLS})
    contrasts = {"seeds": np.asarray(seeds(), dtype=np.uint64)}
    for seed, branch in frozen["branches"].items():
        report["endpoints"][seed], arrays = factorial(rows, branch, settings)
        contrasts.update({"s" + seed + "_" + key: value for key, value in arrays.items()})
    atomic_npz(out / "contrasts.npz", **contrasts)
    report.update(status="complete")
    atomic_json(out / "report.json", report)
    return report


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--run", action="store_true")
    args = parser.parse_args()
    if args.run:
        result = run()
        print(json.dumps({key: result[key] for key in ("status", "research_genome_lives", "row_cpu_seconds")}))
    else:
        print(json.dumps({"status": "dry_run", "genome_lives": 4096, "seed_block": 100,
                          "max_cpu_seconds": CAP, "simulated_lives": 0}))


if __name__ == "__main__":
    main()
