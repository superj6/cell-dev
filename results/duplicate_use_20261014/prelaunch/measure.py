"""All active duplicate-origin gene deletions, then independent confirmation of fixed choices; dry-run default."""
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
ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))
STUDY = ROOT / "outputs/autonomous_duplicate_use_20261014"
RUNS, LIVES, CAP = (51089, 51090), 512, 7200
HELPERS = ("taskvar_confirm.py", "taskvar_second_step.py", "taskvar_gradient.py", "taskvar_gates.py")


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def raw_sha(array):
    return hashlib.sha256(array.tobytes()).hexdigest()


def check_protocol(study=STUDY):
    p = json.loads((study / "protocol.json").read_text())
    expected = {"runs": list(RUNS), "lives_per_stage": 512, "stage_blocks": {"screen": 98, "confirm": 99},
                "max_genome_lives": 19456, "max_cpu_seconds": CAP, "threads": 2, "T": 1024,
                "endpoint_rule": "exact final population rank0 at generation16",
                "candidate_rule": "every active slot with innovation origin >=16, no fitness or weight filter"}
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
    for relative, digest in p["G_pins"].items():
        if sha(ROOT / p["G_study"] / relative) != digest:
            raise ValueError("fixed G dependency differs: " + relative)
    for relative, digest in p["inputs"].items():
        if sha(study / relative) != digest:
            raise ValueError("fixed input differs: " + relative)
    return p


def world():
    from src.life import spec

    return spec.world("catch_speck_l4", T=1024, d0=.5, d_min=.25, sigma=.4, lam_s=4)


def seeds(stage):
    if stage not in ("screen", "confirm"):
        raise ValueError("unknown fixed stage")
    start = 51_980_000 if stage == "screen" else 51_990_000
    return list(range(start, start + 512))


def load_endpoints(protocol):
    """Read outcomes only after G completes; verify exact endpoint and every recorded genetic operation."""
    import numpy as np
    from omegaconf import OmegaConf

    from src import checkpoint
    from src.genome import Layout

    g = ROOT / protocol["G_study"]
    budget = json.loads((g / "budget.json").read_text())
    if budget["status"] != "complete" or budget.get("running") or budget.get("queued"):
        raise ValueError("G must complete before endpoint inspection")
    module_spec = importlib.util.spec_from_file_location("duplicate_origin_audit", g / "audit_search.py")
    audit = importlib.util.module_from_spec(module_spec)
    module_spec.loader.exec_module(audit)
    layout, founder = Layout.load(STUDY / "inputs/founder_row38.json")
    records = {}
    for seed in RUNS:
        folder = g / f"runs/s{seed}"
        state = checkpoint.load(folder / "checkpoint.pt")
        cfg = OmegaConf.load(g / f"configs/s{seed}.yaml")
        checkpoint.validate(state, cfg, protocol["numerical_identity"])
        state = state["state"]
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
        records[seed] = {"genome": genome, "origins": origins,
                         "audit": {"checkpoint_sha256": sha(folder / "checkpoint.pt"),
                                   "lineage_sha256": sha(folder / "lineage.jsonl"), "health": health,
                                   "genetic_replay": genetic, "genome_raw_sha256": raw_sha(genome.numpy())}}
    return layout, records


def candidates(layout, endpoints):
    """Create every prescribed intervention before any scoring; no candidate deduplication or filtering."""
    import numpy as np

    genomes, labels, branches = [], [], {}
    for seed in RUNS:
        genome, origins = endpoints[seed]["genome"], endpoints[seed]["origins"]
        slots = np.flatnonzero(layout.active(genome).numpy() & (origins >= 16)).tolist()
        branch = {"status": "applicable" if slots else "not_applicable_no_active_duplicate_origin",
                  "slots": slots, "origins": origins.tolist(), "intact_row": None, "knockouts": []}
        branches[str(seed)] = branch
        if not slots:
            continue
        branch["intact_row"] = len(genomes)
        genomes.append(genome.numpy().copy())
        labels.append(f"s{seed}_intact")
        for slot in slots:
            ko = layout.delete(genome, slot)
            canonical = genome.clone()
            layout.view(canonical, "act")[slot] = 0
            packed = layout.pack(ko[None], "hexprism")
            if packed.tobytes() != layout.pack(canonical[None], "hexprism").tobytes():
                raise ValueError("deletion runtime table differs from canonical inactive-gene mask")
            row = len(genomes)
            genomes.append(ko.numpy().copy())
            labels.append(f"s{seed}_delete_slot{slot}_origin{int(origins[slot])}")
            branch["knockouts"].append({"row": row, "slot": slot, "origin_id": int(origins[slot]),
                                         "operation": {"delete": slot}, "raw_sha256": raw_sha(ko.numpy()),
                                         "runtime_table_sha256": raw_sha(packed)})
    matrix = np.stack(genomes) if genomes else np.empty((0, layout.size), dtype=np.float32)
    if len(matrix) > 34:
        raise ValueError("candidate policy upper bound exceeded")
    return matrix, labels, branches


def choose(fitness, branches):
    """Largest paired intact-minus-KO mean; exact ties prefer the smallest slot, even if all losses are negative."""
    import numpy as np

    values = np.asarray(fitness, dtype=np.float64)
    if values.ndim != 2 or values.shape[1] != LIVES or not np.isfinite(values).all():
        raise ValueError("need finite candidate-by-512-life scores")
    selections = {}
    for seed, branch in branches.items():
        if not branch["knockouts"]:
            selections[seed] = {"status": branch["status"]}
            continue
        intact = branch["intact_row"]
        ranked = sorted(branch["knockouts"], key=lambda item: (
            -float(np.mean(values[intact] - values[item["row"]])), item["slot"]))
        selected = ranked[0]
        selections[seed] = {"status": "selected", "intact_screen_row": intact,
                            "knockout_screen_row": selected["row"], "slot": selected["slot"],
                            "origin_id": selected["origin_id"],
                            "screen_mean_loss": float(np.mean(values[intact] - values[selected["row"]]))}
    return selections


def run():
    import numpy as np
    from omegaconf import OmegaConf
    from run_budgeted import check_ready

    from scripts.taskvar_confirm import COLS, atomic_json, atomic_npz, compare_rows
    from scripts.taskvar_second_step import RowStore, freeze
    from src.checkpoint import numerical_identity
    from src.life.evaluate import LifeEvaluator

    protocol, ready = check_protocol(), check_ready()
    identity = numerical_identity()
    if identity != protocol["numerical_identity"]:
        raise ValueError("numerical identity differs")
    layout, endpoints = load_endpoints(protocol)
    genomes, labels, branches = candidates(layout, endpoints)
    settings, out = world(), STUDY / "measurement"
    manifest = {"format": 1, "labels": labels, "branches": branches,
                "genome_raw_sha256": [raw_sha(g) for g in genomes],
                "endpoint_audits": {str(seed): rec["audit"] for seed, rec in endpoints.items()},
                "world": asdict(settings), "seeds": {stage: seeds(stage) for stage in ("screen", "confirm")},
                "numerical_identity": identity, "protocol_sha256": sha(STUDY / "protocol.json"), "ready": ready,
                "screen_genome_lives": len(genomes) * LIVES, "max_genome_lives": 19456}
    manifest = json.loads(json.dumps(manifest))
    if not (out / "manifest.json").exists() and out.exists() and any(out.rglob("*.npz")):
        raise ValueError("cached scoring rows lack frozen interventions")
    out.mkdir(parents=True, exist_ok=True)
    freeze(out / "manifest.json", manifest, "all fixed endpoint interventions")
    atomic_npz(out / "genotypes.npz", genomes=genomes, labels=np.asarray(labels))
    evaluator = LifeEvaluator(OmegaConf.load(STUDY / "inputs/evaluator.yaml"), layout)
    report = {"status": "incomplete", "screen": {}, "confirmation": {}, "branches": branches,
              "row_cpu_seconds": 0, "research_genome_lives": 0, "limitations": protocol["limitations"]}
    if not len(genomes):
        report.update(status="complete", no_applicable_branches=True)
        atomic_json(out / "report.json", report)
        return report
    screen = RowStore(out / "screen", genomes, settings, evaluator, 2, CAP)
    rows = {}
    for i in range(len(genomes)):
        if screen.cpu_seconds >= CAP:
            raise RuntimeError("cpu_budget_stop")
        rows[i] = screen.row("rows", i, seeds("screen"))
        report.update(row_cpu_seconds=screen.cpu_seconds, research_genome_lives=(i + 1) * LIVES)
        atomic_json(out / "report.json", report)
    atomic_npz(out / "screen/scores.npz", seeds=np.asarray(seeds("screen"), dtype=np.uint64),
               genome_indices=np.arange(len(genomes)),
               **{key: np.stack([rows[i][key] for i in range(len(genomes))]) for key in COLS})
    for seed, branch in branches.items():
        report["screen"][seed] = {
            str(item["slot"]): compare_rows(rows[branch["intact_row"]], rows[item["row"]], settings)
            for item in branch["knockouts"]}
    selection = choose(np.stack([rows[i]["F"] for i in range(len(genomes))]), branches)
    selected_rows, confirm_pairs = [], {}
    for seed in map(str, RUNS):
        selected = selection[seed]
        if selected["status"] == "selected":
            confirm_pairs[seed] = [len(selected_rows), len(selected_rows) + 1]
            selected_rows.extend([selected["intact_screen_row"], selected["knockout_screen_row"]])
    frozen_selection = {"selection": selection, "screen_rows": selected_rows, "confirm_pairs": confirm_pairs,
                        "screen_scores_sha256": sha(out / "screen/scores.npz"),
                        "rule": "largest mean intact-minus-KO loss, smallest slot tie break, regardless of sign"}
    freeze(out / "selection.json", frozen_selection, "independent confirmation choices")
    confirmation_genomes = genomes[selected_rows]
    atomic_npz(out / "confirmation_genotypes.npz", genomes=confirmation_genomes,
               screen_rows=np.asarray(selected_rows), labels=np.asarray(labels)[selected_rows])
    confirm = RowStore(out / "confirm", confirmation_genomes, settings, evaluator, 2, CAP)
    fresh = {}
    for i in range(len(selected_rows)):
        if screen.cpu_seconds + confirm.cpu_seconds >= CAP:
            raise RuntimeError("cpu_budget_stop")
        fresh[i] = confirm.row("rows", i, seeds("confirm"))
        report.update(row_cpu_seconds=screen.cpu_seconds + confirm.cpu_seconds,
                      research_genome_lives=(len(genomes) + i + 1) * LIVES)
        atomic_json(out / "report.json", report)
    atomic_npz(out / "confirm/scores.npz", seeds=np.asarray(seeds("confirm"), dtype=np.uint64),
               genome_indices=np.arange(len(selected_rows)),
               **{key: np.stack([fresh[i][key] for i in range(len(selected_rows))]) for key in COLS})
    contrasts = {"seeds": np.asarray(seeds("confirm"), dtype=np.uint64)}
    for seed, (intact, knockout) in confirm_pairs.items():
        effect = compare_rows(fresh[intact], fresh[knockout], settings)
        effect.update(positive_above_3se=effect["F"]["mean"] > 3 * effect["F"]["se"],
                      above_0p5=effect["F"]["mean"] > .5)
        report["confirmation"][seed] = {"selection": selection[seed], "loss": effect}
        contrasts["s" + seed + "_intact_minus_KO"] = fresh[intact]["F"] - fresh[knockout]["F"]
    atomic_npz(out / "contrasts.npz", **contrasts)
    report.update(status="complete", selection=selection, confirmation_genome_lives=len(selected_rows) * LIVES)
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
        print(json.dumps({"status": "dry_run", "max_genome_lives": 19456, "stage_blocks": [98, 99],
                          "max_cpu_seconds": 7200, "simulated_lives": 0}))


if __name__ == "__main__":
    main()
