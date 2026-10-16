"""One-pass recorded genetics plus independent saved-selection audit; no simulation or random draws."""

from __future__ import annotations

import hashlib
import importlib.util
import json
import sys
from pathlib import Path

import numpy as np
import torch

HERE = Path(__file__).resolve().parent
PROTOCOL_SHA = "86593f759c5c17823d4eaff19800728229f757eb2ffc82b2f54660e9b32653bb"


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def read(path):
    return json.loads(Path(path).read_text())


def require(value, message):
    if not value:
        raise ValueError(message)


def local_module(name):
    descriptor = importlib.util.spec_from_file_location("depth_terminal_" + name, HERE / (name + ".py"))
    module = importlib.util.module_from_spec(descriptor)
    descriptor.loader.exec_module(module)
    return module


def terminal_guard(base):
    """Completion checks precede all outcome/checkpoint/lineage reads."""
    digest = sha(base / "protocol.json")
    require(digest == PROTOCOL_SHA, "registered depth protocol changed")
    protocol = read(base / "protocol.json")
    terminal = {name: read(base / name) for name in ("study_complete.json", "budget.json", "measurement_complete.json")}
    for name, item in terminal.items():
        require(item["status"] == "complete" and item["protocol_sha256"] == digest, name + " is not complete")
    require(
        read(base / "release.json")["protocol_sha256"] == digest
        and read(base / "release.json")["status"] == "released"
        and read(base / "READY.json")["protocol_sha256"] == digest,
        "registration/release binding",
    )
    complete, budget = terminal["study_complete.json"], terminal["budget.json"]
    cleanup = budget["terminal_cleanup"]
    require(
        not budget["running"]
        and not budget["queued"]
        and budget["error"] is None
        and cleanup["checked_in_monitor"]
        and cleanup["same_pid_namespace"]
        and cleanup["all_owned_groups_exited"]
        and cleanup["all_worker_identities_exited"]
        and not cleanup["remaining_group_members"]
        and not cleanup["remaining_worker_identities"]
        and not cleanup["remaining_descendants"],
        "owned execution not cleared",
    )
    require(
        complete["total_calls"] == 97342
        and complete["research_lives"] == 97334
        and complete["startup_lives"] == 8
        and protocol["total_calls"] == 97342
        and complete["budget_sha256"] == sha(base / "budget.json")
        and complete["measurement_complete_sha256"] == sha(base / "measurement_complete.json")
        and complete["summary_sha256"] == sha(base / "summary.json"),
        "terminal evidence binding",
    )
    expected = dict(
        generations=8,
        parents=32,
        children=224,
        shortlist=64,
        base_lives=32,
        recheck_lives=32,
        selection_lives=81920,
        validation_generations=[0, 4, 7],
        validation_lives=48,
        final_lives=6,
        research_lives=81974,
        startup_lives=4,
        total_calls=81978,
    )
    require(protocol["search"] == expected and protocol["native_seed"] == 53236, "registered single-arm search scope")
    for kind, root in (("source_pins", base), ("input_pins", base)):
        for name, pin in protocol[kind].items():
            require(sha(root / name) == pin, "registered source/input changed: " + name)
    require(sha(base / "namespace/seed_audit.json") == protocol["seed_audit_sha256"], "native schedule pin")
    root = base / "production" if (base / "production/src/genome.py").exists() else base.parents[1]
    for name, pin in protocol["production_pins"].items():
        require(sha(root / name) == pin, "production source changed: " + name)
    return protocol, terminal, root


def definitions(root, protocol):
    sys.path.insert(0, str(root))
    from src.genome import Layout

    for name, module in tuple(sys.modules.items()):
        if name in ("src", "src.genome", "src.lattice", "src.life", "src.life.spec"):
            path = Path(module.__file__).resolve()
            require(
                path.is_relative_to(root.resolve())
                and sha(path) == protocol["production_pins"][str(path.relative_to(root.resolve()))],
                "loaded genome definition is outside pinned sources",
            )
    return Layout


def config_identity(path):
    from omegaconf import OmegaConf

    value = OmegaConf.to_container(OmegaConf.load(path), resolve=True)
    value.pop("extends", None)
    value["logging"].pop("output_dir", None)
    value["logging"].pop("checkpoint_every", None)
    return value


def bound_logs(folder, saved):
    require(set(saved["logs"]) == {"curves.jsonl", "lineage.jsonl", "clones.jsonl"}, "checkpoint log coverage")
    result = {}
    for name, pin in saved["logs"].items():
        data = (folder / name).read_bytes()
        require(
            type(pin["bytes"]) is int
            and pin["bytes"] >= 0
            and len(data) == pin["bytes"]
            and hashlib.sha256(data).hexdigest() == pin["sha256"],
            "checkpoint log bytes: " + name,
        )
        result[name] = [json.loads(row) for row in data.splitlines() if row.strip()]
    require(not result["clones.jsonl"], "unexpected clone evaluations")
    return result


def complete_replay(study):
    base = Path(study).resolve()
    protocol, terminal, root = terminal_guard(base)
    torch.set_num_threads(1)
    Layout = definitions(root, protocol)
    independent = local_module("audit_selection")
    ops = local_module("replay_ops")
    layout, _ = Layout.load(base / protocol["references"][0]["path"])
    # Layout.load imports ABI/lattice definitions lazily; check those actual imports too.
    definitions(root, protocol)
    record = protocol["population_start"]
    imported = read(base / record["population_file"])
    initial = torch.stack([layout.from_dict(row) for row in imported["genomes"]])
    rows = [independent.raw_sha(row.numpy()) for row in initial]
    require(
        imported["dims"] == layout.dims.__dict__
        and tuple(initial.shape) == (32, 875)
        and initial.dtype == torch.float32
        and bool(torch.isfinite(initial).all())
        and imported["ids"] == record["old_ids"]
        and len(set(imported["ids"])) == 32
        and record["new_ids"] == list(range(32))
        and record["shape"] == [32, 875]
        and independent.raw_sha(initial.numpy()) == record["population_raw_sha256"]
        and rows == record["row_sha256"]
        and sha(base / record["population_file"]) == record["file_sha256"]
        and record["old_to_new"]
        == [dict(old_id=old, new_id=i, row=i, raw_sha256=rows[i]) for i, old in enumerate(imported["ids"])],
        "all 32 ordered founders/crosswalk",
    )
    folder = base / "runs/pareto"
    marker = read(folder / "search_complete.json")
    require(
        marker["status"] == "complete"
        and marker["arm"] == "pareto"
        and marker["research_lives"] == 81974
        and marker["startup_lives"] == 4
        and marker["protocol_sha256"] == sha(base / "protocol.json")
        and marker["release_sha256"] == sha(base / "release.json")
        and marker["native_rank0_only"]
        and not marker["reporting_endpoint_selected"]
        and terminal["study_complete.json"]["search_complete_sha256"] == sha(folder / "search_complete.json"),
        "completed search marker differs",
    )
    required = {
        "checkpoint.pt",
        "config.yaml",
        "determinism.json",
        "curves.jsonl",
        "lineage.jsonl",
        "population.json",
        "best_genome.json",
        "results.jsonl",
        "search_startup.json",
        *(f"selection/g{g:03d}.npz" for g in range(8)),
    }
    require(set(marker["output_pins"]) == required, "search output coverage")
    for name, pin in marker["output_pins"].items():
        require(sha(folder / name) == pin, "search output pin: " + name)
    cfgpath = base / protocol["configs"]["pareto"]["path"]
    require(sha(cfgpath) == protocol["configs"]["pareto"]["sha256"], "registered config pin")
    cfg = config_identity(cfgpath)
    require(config_identity(folder / "config.yaml") == cfg, "saved config differs")
    expected = dict(
        generations=8,
        mu=32,
        lam=224,
        breeding="sex",
        n_mut=2,
        dup_rate=0.0,
        del_rate=0.0,
        dup_split=False,
        recheck_k=64,
        recheck_lives=32,
        recheck_key="all",
        heldout_every=4,
    )
    require(
        all(cfg["evolve"][key] == value for key, value in expected.items())
        and cfg["seed"] == 53236
        and cfg["life"]["abi"] == 6
        and cfg["life"]["T"] == 1024.0
        and cfg["life"]["lives"] == 32
        and cfg["life"]["T_choices"] is None
        and cfg["life"]["extinct_charge"]
        and cfg["logging"]["lineage"] == "all",
        "native genetics/evaluator scope",
    )
    require(
        cfg["population_start"]
        == dict(
            version=1, **record, source_pins={name: sha(base / name) for name in ("population_loader.py", "search.py")}
        ),
        "configured population import",
    )
    identity = dict(
        protocol["expected_numerical_identity"],
        population_start=cfg["population_start"],
        retention_selection=cfg["retention_selection"],
    )
    require(read(folder / "determinism.json") == identity, "recorded extended identity")
    saved = torch.load(folder / "checkpoint.pt", map_location="cpu", weights_only=True)
    state = saved["state"]
    require(
        saved["format"] == 1
        and saved["config"] == cfg
        and saved["identity"] == identity
        and state["generation"] == 8
        and state["evals"] == 2048
        and state["rc_lives"] == 16384,
        "checkpoint identity/counts",
    )
    logs = bound_logs(folder, saved)
    lines, curves = logs["lineage.jsonl"], logs["curves.jsonl"]
    require(
        state["curves"] == curves
        and [row["gen"] for row in curves] == list(range(8))
        and [row["gen"] for row in curves if "valid" in row] == [0, 4, 7]
        and lines[0].get("event") == "founders"
        and lines[0].get("sampled") == 0
        and lines[0]["ids"] == list(range(32))
        and lines[0]["copies"] == []
        and [row.get("gen") for row in lines[1:]] == list(range(8)),
        "native log schedule/founders",
    )
    results = [json.loads(line) for line in (folder / "results.jsonl").read_text().splitlines()]
    require(len(results) == 1, "one native final result required")
    final = results[0]
    require(
        final["generations"] == 8
        and final["evals"] == 2560
        and final["lives"] == 2
        and final["founders_sampled"] == 0
        and final["top_best_rank"] == 0
        and final["invalid_lives"] == final["mismatch_lives"] == 0
        and np.isfinite(final["F"]),
        "native final diagnostic scope or health differs",
    )
    require(
        marker["count_proof"]
        == dict(
            selection=81920,
            valid=48,
            final=6,
            growth_half=2,
            native_evals=2560,
            generations=8,
            children_per_generation=224,
        ),
        "native call count proof",
    )
    parents = list(range(32))
    for g, row in enumerate(lines[1:]):
        children = row["children"]
        ids = list(range(32 + 224 * g, 32 + 224 * (g + 1)))
        require(
            [child["id"] for child in children] == ids
            and len(row["survivors"]) == 32
            and len(set(row["survivors"])) == 32
            and set(row["survivors"]) <= set(parents + ids),
            "offspring/survivor IDs",
        )
        for child in children:
            require(
                child["pa"] in parents
                and child["pb"] in parents
                and set(child["ops"]) == {"mut"}
                and len(child["ops"]["mut"]) == 2
                and child["kept"] == (child["id"] in row["survivors"]),
                "recorded parent/operator/retention",
            )
        parents = row["survivors"]
    selected, arrays = independent.audit(base, protocol, saved, initial.numpy(), lines, curves)

    def observer(row, candidates):
        a = arrays[row["gen"]]
        independent.same(np.asarray(list(candidates), dtype=np.int64), a["candidate_ids"], "genetically replayed IDs")
        independent.same(
            torch.stack(list(candidates.values())).numpy(),
            a["base_genomes"],
            "every scored candidate must replay from recorded operations",
        )

    genetic = ops.replay_genetics(
        lines, state, layout, initial[0], False, initial_population=initial, candidate_observer=observer
    )
    require(
        genetic["point_mutations_including_initial_copies"] == 3584
        and genetic["duplication_events"] == genetic["deletion_events"] == 0,
        "recorded genetic counts",
    )
    public = read(folder / "population.json")
    for key in ("ids", "breeds", "origins", "fitness"):
        require(public[key] == state[key].tolist(), "public population metadata: " + key)
    _, best = Layout.load(folder / "best_genome.json")
    independent.same(best.numpy(), state["population"][0].numpy(), "native rank-zero export")
    pins = {
        name: sha(base / name)
        for name in (
            "protocol.json",
            "READY.json",
            "release.json",
            "study_complete.json",
            "budget.json",
            "measurement_complete.json",
            "summary.json",
            "namespace/seed_audit.json",
        )
    }
    pins.update({"runs/pareto/" + name: pin for name, pin in marker["output_pins"].items()})
    pins["runs/pareto/search_complete.json"] = sha(folder / "search_complete.json")
    pins["runs/pareto/clones.jsonl"] = sha(folder / "clones.jsonl")
    return dict(
        status="passed",
        protocol_sha256=sha(base / "protocol.json"),
        genetic_replay=genetic,
        selection_audit=selected,
        artifact_pins=pins,
        source_pins_verified=protocol["source_pins"],
        input_pins_verified=protocol["input_pins"],
        source_sha256={p.name: sha(p) for p in sorted(HERE.glob("*.py"))},
        initial_rows=32,
        offspring_replayed=1792,
        point_additions_replayed=3584,
        scored_candidate_rows_bound=2048,
        all_final_rows_bound=32,
        rankings_checked=16,
        tie_permutations_checked=24,
        selection_lives_checked=81920,
        calls=dict(simulator=0, builds=0, random_draws=0),
        limits=[
            "Recorded genetic operations are replayed; random generator streams are not resampled.",
            "Saved capture/F values are checked for selection consistency; no trajectory is recomputed.",
            "Fresh endpoint selection and confirmation accounting are separately audited.",
            "Raw ancestry, selection ranks and byte identity do not establish functional circuitry or memory.",
        ],
    )
