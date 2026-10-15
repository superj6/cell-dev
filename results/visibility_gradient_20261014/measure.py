"""Two ordinary-mutant ABI4 screens and fresh confirmation; dry run by default.

Registered panels and a pinned protocol are prepared separately. --run additionally
requires root release, the reviewed monitor's live ownership and phase acknowledgments.
"""
from __future__ import annotations

import argparse
import json
import os
import sys
import time
from dataclasses import asdict
from pathlib import Path

os.environ.setdefault("ATEN_CPU_CAPABILITY", "avx2")
sys.dont_write_bytecode = True
STUDY = Path(__file__).resolve().parent
ROOT = STUDY.parents[1]
sys.path.insert(0, str(ROOT))

from common import parent_check, read, require_release, save, sha  # noqa: E402

PARENTS = ("D90", "L92")
CAP, SCREEN_CAP, RESERVE, MARGIN = 5400, 3400, 2000, 10
SCOPE = {"total_cpu_seconds": CAP, "startup_screen_cpu_seconds": SCREEN_CAP,
         "confirmation_reserve_cpu_seconds": RESERVE, "max_workers": 1,
         "threads_per_worker": 2, "research_lives": 6208, "validation_lives": 10}
FOUNDER_SHA = {
    "D90": "1287ee4421f88fc108c073eae282f625bd0e340a5e4b12d590cd27cbc046bfac",
    "L92": "8f14c79b8bea73c08dff7f6bc1094dc848534f9f2d45598c99c4351cf364cf27",
}


def stage_seeds(protocol):
    seeds = protocol["seeds"]
    expected = {"screen": 32, "confirm": 512, "calibration": 2}
    if set(seeds) != set(expected):
        raise ValueError("fixed stage seed set changed")
    flat = []
    for key, count in expected.items():
        row = seeds[key]
        if len(row) != count or any(not isinstance(x, int) or isinstance(x, bool) or x < 0 for x in row):
            raise ValueError("fixed stage seeds changed")
        flat.extend(row)
    if len(set(flat)) != len(flat) or 11 in flat:
        raise ValueError("fresh stages or retained numerical golden overlap")
    return seeds


def select_winner(rows):
    """The same whole-mean/row-order rule as I, now without an intermediate rescore."""
    import numpy as np
    if set(rows) != set(range(65)):
        raise ValueError("selection requires all65 parent/mutant rows")
    for row in rows.values():
        if np.asarray(row["F"]).shape != (32,) or not np.isfinite(row["F"]).all():
            raise ValueError("selection requires complete finite32-life rows")
    return min(range(1, 65), key=lambda i: (-float(rows[i]["F"].mean()), i))


def calibration_projection(rows, startup_cpu):
    rates = {parent: max(float(rows[parent][i]["cpu_seconds"]) / 2 for i in (0, 1))
             for parent in PARENTS}
    screen = startup_cpu + 1.5 * 2080 * sum(rates.values())
    confirmation = 1.5 * 1024 * sum(rates.values())
    return {"batch_max_cpu_per_life": rates, "startup_cpu_seconds": startup_cpu,
            "screen_projection_cpu_seconds": screen, "confirmation_projection_cpu_seconds": confirmation,
            "feasible": screen <= SCREEN_CAP - MARGIN and confirmation <= RESERVE - MARGIN,
            "limitation": "Four2-seed batches cannot bound slow unsampled mutants or the eventual winners."}


def monitor_ack(name, payload, parent_pid):
    """Pause before dependent work until monitor accounts the completed phase."""
    parent_check(parent_pid)
    request = STUDY / "requests" / (name + ".json")
    response = STUDY / "monitor_receipts" / (name + ".json")
    if request.exists() or response.exists():
        raise ValueError("first attempt refuses a previous phase handshake")
    save(request, {"protocol_sha256": sha(STUDY / "protocol.json"), **payload})
    deadline = time.monotonic() + 60
    while not response.exists():
        parent_check(parent_pid)
        if time.monotonic() >= deadline:
            raise RuntimeError("monitor phase acknowledgment timed out")
        time.sleep(0.1)
    receipt = read(response)
    if (receipt.get("status") != "allowed" or receipt.get("request_sha256") != sha(request)
            or receipt.get("protocol_sha256") != sha(STUDY / "protocol.json")
            or receipt.get("attempt_sha256") != sha(STUDY / "attempt.json")):
        raise ValueError("monitor phase receipt changed")
    cpu = receipt.get("cpu_seconds")
    if not isinstance(cpu, (int, float)) or not 0 <= cpu <= SCREEN_CAP - MARGIN:
        raise ValueError("startup/screen ceiling exceeded before dependent work")
    parent_check(parent_pid)
    return receipt


def load_panels(protocol):
    import numpy as np
    from omegaconf import OmegaConf
    from scoring import raw_sha

    from src.genome import Layout
    from src.life import spec
    from src.life.evaluate import LifeEvaluator

    if protocol["monitor_scope"] != SCOPE or protocol["founder_raw_sha256"] != FOUNDER_SHA:
        raise ValueError("fixed resource or founder scope changed")
    world = spec.world("catch_speck_blink20_20_l4", T=1024)
    if asdict(world) != protocol["world"] or list(spec.V4.pack_world(world).shape) != [70]:
        raise ValueError("approved production visibility world changed")
    panels, evaluators = {}, {}
    for parent in PARENTS:
        prefix = STUDY / "inputs" / parent
        manifest = read(prefix / "panel_manifest.json")
        table = np.load(prefix / "genomes.npy", allow_pickle=False)
        layout, founder = Layout.load(str(prefix / "parent.json"))
        cfg = OmegaConf.load(prefix / "config.yaml")
        if (table.dtype != np.float32 or table.shape != (65, 875) or not np.isfinite(table).all()
                or raw_sha(table[0]) != FOUNDER_SHA[parent]
                or table[0].tobytes() != founder.reshape(-1).float().numpy().tobytes()):
            raise ValueError("unchanged parent and all64 fixed mutants required")
        if [raw_sha(row) for row in table] != protocol["panel_genotype_sha256"][parent]:
            raise ValueError("candidate row hashes disagree with the registered panel")
        if (manifest["genomes_sha256"] != raw_sha(table) or manifest["mutants"] != 64
                or manifest["parent_sha256"] != sha(prefix / "parent.json")
                or manifest["config_sha256"] != sha(prefix / "config.yaml")
                or manifest["mutation_ops_sha256"] != sha(prefix / "mutation_ops.json")
                or manifest["mutation_seed"] != protocol["mutation_rng"][parent]
                or manifest["mutation_helper_sha256"] != protocol["production_pins"]["scripts/taskvar_gradient.py"]
                or manifest["mutation"] != {"n_mut": 2, "p_cell": 0.5, "scale_n_mut": True,
                                             "dup_rate": 0, "del_rate": 0, "split": False}):
            raise ValueError("frozen panel generation identity changed")
        evaluator = LifeEvaluator(cfg, layout)
        if (evaluator.abi.version != 4 or not evaluator.extinct_charge or evaluator.threads != 2
                or evaluator.T_choices or evaluator.has_envelope or asdict(evaluator.world()) != asdict(world)):
            raise ValueError("derived configuration differs from fixed ABI4 scoring world")
        panels[parent], evaluators[parent] = table, evaluator
    return panels, evaluators, world


def run(parent_pid):
    parent_check(parent_pid)
    protocol = require_release()
    for forbidden in ("measurement", "startup_identity.json", "report.json", "selection.json", "requests", "monitor_receipts"):
        if (STUDY / forbidden).exists():
            raise ValueError("first attempt refuses existing generated work: " + forbidden)
    if os.environ.get("CELLDEV_THREADS_FILE"):
        raise ValueError("elastic thread override is forbidden")
    from numerical import check
    check(protocol["numerical_identity"])
    panels, evaluators, world = load_panels(protocol)
    seeds = stage_seeds(protocol)
    from scoring import RowStore, comparison, raw_sha

    from src.checkpoint import numerical_identity

    # The only numerical_identity invocation: exactly two ABI3 seed11 T200
    # full/fast compatibility goldens, both within the startup/screen budget.
    identity = numerical_identity()
    metadata = {k: v for k, v in identity.items() if k not in ("kernels", "golden")}
    if metadata != protocol["expected_startup_metadata"]:
        raise ValueError("pinned startup numerical/source metadata changed")
    save(STUDY / "startup_identity.json", {
        "identity": identity, "preexpected_fields": sorted(metadata),
        "newly_captured_fields": ["kernels", "golden"], "numerical_identity_invocations": 1,
        "golden_lives": {"abi": 3, "seed": 11, "T": 200, "full": 1, "fast": 1},
        "limitation": "New build hashes are captured identity, not independent replay proof."})
    stores = {parent: RowStore(STUDY / "measurement" / parent, panels[parent], world, evaluators[parent],
                              {"protocol_sha256": sha(STUDY / "protocol.json"), "background": parent})
              for parent in PARENTS}
    report = {"status": "incomplete", "scope": SCOPE, "screen": {}, "confirmation": {}}
    save(STUDY / "report.json", report)
    calibration = {parent: stores[parent].stage("calibration", [0, 1], seeds["calibration"]) for parent in PARENTS}
    receipt = monitor_ack("calibration_complete", {"validation_lives": 10,
        "startup_identity_sha256": sha(STUDY / "startup_identity.json"),
        "row_index_sha256": {p: sha(stores[p].out / "row_index.json") for p in PARENTS}}, parent_pid)
    projection = calibration_projection(calibration, receipt["cpu_seconds"])
    save(STUDY / "calibration_projection.json", projection)
    if not projection["feasible"]:
        raise RuntimeError("fixed_scope_cost_projection_does_not_fit")
    winners = {}
    for parent in PARENTS:
        parent_check(parent_pid)
        rows = stores[parent].stage("screen", list(range(65)), seeds["screen"])
        chosen = select_winner(rows)
        winners[parent] = {"genome_row": chosen, "raw_sha256": raw_sha(panels[parent][chosen])}
        report["screen"][parent] = {"selected": winners[parent], "complete_rows": 65,
                                    "row_index_sha256": sha(stores[parent].out / "row_index.json")}
        save(STUDY / "report.json", report)
    save(STUDY / "selection.json", winners)
    monitor_ack("screens_complete", {"scientific_genome_lives": 4160,
        "selection_sha256": sha(STUDY / "selection.json"),
        "row_index_sha256": {p: sha(stores[p].out / "row_index.json") for p in PARENTS}}, parent_pid)
    for parent in PARENTS:
        parent_check(parent_pid)
        chosen = winners[parent]["genome_row"]
        rows = stores[parent].stage("confirm", [0, chosen], seeds["confirm"])
        report["confirmation"][parent] = comparison(rows[chosen], rows[0], world)
        save(STUDY / "report.json", report)
    report.update(status="complete", research_genome_lives=6208, validation_lives=10,
                  total_genome_lives=6218, row_cpu_seconds=sum(s.cpu_seconds for s in stores.values()),
                  row_index_sha256={p: sha(stores[p].out / "row_index.json") for p in PARENTS},
                  limitations=["A32-life screen can select noise; confirmation does not exhaust accessible mutations.",
                               "Capture gains, including low-light captures, do not isolate a memory mechanism."])
    save(STUDY / "report.json", report)
    return report


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--run", action="store_true")
    parser.add_argument("--monitor-pid", type=int)
    args = parser.parse_args()
    if not args.run:
        print(json.dumps({"status": "dry_run_unreleased_preparation", "scope": SCOPE,
                          "total_genome_lives": 6218, "mutants_generated": 0,
                          "requires": "complete X2/world decision, panel/source pins, registration and monitor release"}))
        return
    result = run(args.monitor_pid)
    print(json.dumps({"status": result["status"], "total_genome_lives": result["total_genome_lives"]}))


if __name__ == "__main__":
    main()
