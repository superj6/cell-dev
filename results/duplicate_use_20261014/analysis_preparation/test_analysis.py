"""Pure synthetic J independent analysis tests; never inspect G outcomes or simulate lives."""
import copy
import importlib.util
import json
import sys
from pathlib import Path

import numpy as np
import pytest

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
import analysis_common as common  # noqa: E402
import genome_audit as genes  # noqa: E402

loader = importlib.util.spec_from_file_location("independent_J_test", HERE / "analyze.py")
a = importlib.util.module_from_spec(loader)
loader.loader.exec_module(a)
ROOT = a.ROOT


def world():
    return a.expected_world(a.source(HERE, "src/life/spec.py"))


@pytest.fixture(scope="module")
def genetic_fixture():
    if ROOT is None:
        pytest.skip("Optional source cross-check needs the repository's synthetic G fixture")
    path = ROOT / "outputs/autonomous_structural_20261013/test_audit_search.py"
    if not path.exists():
        pytest.skip("Optional synthetic G fixture unavailable outside working repository")
    spec = importlib.util.spec_from_file_location("synthetic_genetics_for_J_analysis", path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    import torch

    torch.set_num_threads(1)
    return module.synthetic.__wrapped__()


def test_numpy_genetics_reproduces_entire_synthetic_population_and_origins(genetic_fixture):
    lines, state, _, founder = genetic_fixture
    population, origins, details = genes.replay(lines, founder.numpy(), generations=1)
    assert a.identical(population, state["population"].numpy())
    assert a.identical(origins, state["origins"].numpy())
    assert details["next_innovation"] == state["next_innov"]
    assert details["next_individual"] == state["next_id"]
    assert details["final_ids"] == state["ids"].tolist()
    assert details["duplication_events"] > 0 and details["deletion_events"] > 0
    assert details["point_mutations"] == 62 + 224 * 2


def test_second_generation_inherits_distinct_duplicate_origins_and_scaled_points(genetic_fixture):
    import torch

    lines, state, layout, founder = genetic_fixture
    rng = torch.Generator().manual_seed(91)
    pa = torch.randint(32, (224,), generator=rng)
    pb = torch.randint(32, (224,), generator=rng)
    crossed, masks = layout.crossover(state["population"][pa], state["population"][pb], rng, masks=True)
    operations = []
    children = layout.mutate(crossed, rng, dup_rate=.5, del_rate=.5, split=False, ops=operations)
    origins = np.where(masks[:, :16].numpy(), state["origins"][pa].numpy(), state["origins"][pb].numpy())
    next_origin = state["next_innov"]
    for i, operation in enumerate(operations):
        if "dup" in operation:
            origins[i, operation["dup"][1]] = next_origin
            next_origin += 1
        if "del" in operation:
            origins[i, operation["del"]] = -1
    ids = state["ids"].tolist()
    row = {"gen": 1, "survivors": list(range(256, 288)), "registry": genes.registry(origins[:32]),
           "n_active": float((origins[:32] >= 0).sum(axis=1).mean()), "children": [
               {"id": 256 + i, "pa": ids[int(pa[i])], "pb": ids[int(pb[i])],
                "mask": sum(1 << j for j, bit in enumerate(masks[i]) if bit), "ops": operation, "kept": i < 32}
               for i, operation in enumerate(operations)]}
    population, replayed_origins, detail = genes.replay([*lines, row], founder.numpy(), generations=2)
    assert a.identical(population, children[:32].numpy())
    assert a.identical(replayed_origins, origins[:32])
    assert detail["next_innovation"] == next_origin
    assert detail["point_mutations"] == 62 + 448 + sum(len(item["mut"]) for item in operations)
    assert np.any((origins[:32] >= 16) & (origins[:32] < state["next_innov"]))


def test_scaled_point_counts_and_distinct_crossover_units_vs_blocks(genetic_fixture):
    _, _, _, founder = genetic_fixture
    raw = founder.numpy().copy()
    for slot in range(8, 12):
        raw = genes.duplicate(raw, 0, slot)
    changes = [["a0", [index], .125] for index in range(3)]
    assert genes.point(raw, {"mut": changes}).shape == (875,)
    with pytest.raises(ValueError, match="count"):
        genes.point(raw, {"mut": changes[:2]})
    # W and b belong to the same mutation block even when owned by different crossover units.
    allowed = [["W", [0, 16], .125], ["b", [1], .25], ["Dm", [0], .125]]
    assert genes.point(raw, {"mut": allowed}).shape == (875,)
    with pytest.raises(ValueError, match="span blocks"):
        genes.point(raw, {"mut": [allowed[0], allowed[1], ["a0", [0], .125]]})
    assert len(set(genes.UNITS)) == 17


def test_numpy_pack_and_delete_match_fixed_layout_on_every_synthetic_active_slot(genetic_fixture):
    _, state, layout, _ = genetic_fixture
    for genome in state["population"]:
        raw = genome.numpy()
        assert a.identical(genes.pack(raw), layout.pack(genome[None], "hexprism")[0])
        for slot in np.flatnonzero(genes.view(raw, "act") > .5):
            actual = genes.delete(raw, int(slot))
            assert a.identical(actual, layout.delete(genome, int(slot)).numpy())
            canonical = raw.copy()
            genes.view(canonical, "act")[slot] = 0
            assert a.identical(genes.pack(actual), genes.pack(canonical))


def test_genetics_rejects_wrong_registry_and_point_mask(genetic_fixture):
    lines, _, _, founder = genetic_fixture
    wrong = copy.deepcopy(lines)
    slot = next(iter(wrong[1]["registry"]))
    origin = next(iter(wrong[1]["registry"][slot]))
    wrong[1]["registry"][slot][origin] += 1
    with pytest.raises(ValueError, match="registry"):
        genes.replay(wrong, founder.numpy(), generations=1)
    with pytest.raises(ValueError, match="active mask"):
        genes.point(founder.numpy(), {"mut": [["act", [8], 1.0], ["a0", [0], .125]]})


def test_candidate_audit_matches_pinned_runner_and_rejects_missing_or_changed_genes(
        genetic_fixture, monkeypatch, tmp_path):
    lines, state, layout, founder = genetic_fixture
    runner_path = HERE / "measure.py"
    if not runner_path.exists():
        runner_path = ROOT / "outputs/autonomous_duplicate_use_20261014/measure.py"
    loader = importlib.util.spec_from_file_location("J_runner_candidate_fixture", runner_path)
    runner = importlib.util.module_from_spec(loader)
    loader.loader.exec_module(runner)
    records = {int(seed): {"genome": state["population"][0], "origins": state["origins"][0].numpy()}
               for seed in a.RUNS}
    genomes, labels, branch = runner.candidates(layout, records)
    replay = genes.replay
    monkeypatch.setattr(genes, "replay", lambda lines, genome: replay(lines, genome, generations=1))
    folder = tmp_path / "G"
    (folder / "configs").mkdir(parents=True)
    (tmp_path / "inputs").mkdir()
    (tmp_path / "measurement").mkdir()
    layout.save(founder, tmp_path / "inputs/founder_row38.json")
    previous = {"raw_population_replay_bitwise": True, "duplication_events": state["next_innov"] - 16,
                "deletion_events": sum("del" in item["ops"] for item in lines[1]["children"]),
                "point_mutations_including_initial_copies": 62 + 448,
                "final_rank_zero_duplicate_slots": branch["51089"]["slots"],
                "final_rank_zero_duplicate_origin_ids": [int(state["origins"][0, i])
                                                         for i in branch["51089"]["slots"]],
                "final_rank_zero_active_genes": int((state["origins"][0] >= 0).sum())}
    manifest = {"endpoint_audits": {}, "branches": branch, "labels": labels,
                "genome_raw_sha256": [genes.raw_sha(row) for row in genomes], "screen_genome_lives": len(genomes) * 512}
    configs = {}
    for seed in a.RUNS:
        run = folder / ("runs/s" + seed)
        run.mkdir(parents=True)
        (run / "lineage.jsonl").write_text("".join(json.dumps(line) + "\n" for line in lines))
        (run / "checkpoint.pt").write_bytes(b"synthetic checkpoint bytes, never deserialized")
        layout.save(state["population"][0], run / "best_genome.json")
        cfg = folder / ("configs/s" + seed + ".yaml")
        cfg.write_text("synthetic: true\n")
        configs[seed] = {"sha256": a.sha(cfg)}
        manifest["endpoint_audits"][seed] = {"checkpoint_sha256": a.sha(run / "checkpoint.pt"),
            "lineage_sha256": a.sha(run / "lineage.jsonl"), "health": {
                "pop_invalid": 0, "pop_mismatch": 0, "recheck_invalid": 0}, "genetic_replay": previous,
            "genome_raw_sha256": genes.raw_sha(state["population"][0].numpy())}
    a.save(folder / "protocol.json", {"configs": configs})
    np.savez_compressed(tmp_path / "measurement/genotypes.npz", genomes=genomes, labels=np.asarray(labels))
    checked, branches_checked, _ = a.audit_candidates(tmp_path, manifest, folder)
    assert a.identical(checked, genomes) and branches_checked == branch
    corrupted = genomes.copy()
    corrupted[0, 0] += .125
    np.savez_compressed(tmp_path / "measurement/genotypes.npz", genomes=corrupted, labels=np.asarray(labels))
    with pytest.raises(ValueError, match="prescribed genetic deletions"):
        a.audit_candidates(tmp_path, manifest, folder)


def synthetic_row(captures=10, n=512, status=None):
    w = world()
    row = {key: np.zeros(n, dtype=np.float64) for key in common.COLS}
    row.update(cpu_seconds=np.asarray(1.), wall_seconds=np.asarray(.5))
    for name, value in {"captures": captures, "income": captures * 500, "n_end": 100,
                        "n_S_end": 30, "n_M_end": 40, "n_H_end": 30, "live_time": 102400,
                        "t_end": 1024, "window": 1024, "last_birth": 300, "spikes": 10,
                        "clicks": captures + 2, "misses": 2, "path": 5}.items():
        row[name][:] = value
    if status is not None:
        row["status"][:] = status
        ended = np.asarray(status, dtype=np.int64) & 7 != 0
        row["t_end"][ended], row["t_ext"][ended] = 700, 700
    row["cost"] = sum(price * row[column] for _, column, price in common.prices(w))
    states = row["status"].astype(np.int64)
    row["guard_charge"] = np.where(states & 6 != 0, w["c_live"] * w["n_max"] * (1024 - row["t_end"]), 0)
    row["net"] = row["income"] - row["cost"] - row["guard_charge"]
    row["F_kernel"] = row["net"] / 1024
    row["extinct_charge"] = w["c_live"] * np.where(states & 1 != 0, 1024 - row["t_ext"], 0) / 1024
    row["F"] = row["F_kernel"] - row["extinct_charge"]
    row["ledger"] = np.stack([row["F_kernel" if key == "F" else key] for key in common.LEDGER], axis=1)
    return row


def test_guard_and_extinction_stay_in_production_fitness():
    row = synthetic_row(n=4, status=[0, 2, 4, 1])
    result = common.validate_row(row, world(), n=4)
    assert result == {"guarded": 2, "extinct": 1, "valid_other_status": 0}
    assert row["guard_charge"][1] > 0 and row["extinct_charge"][3] > 0


@pytest.mark.parametrize("key,change", [("F", 1), ("cost", 1), ("extinct_charge", 1),
                                        ("window", 1), ("status", 64), ("status", 128), ("t_end", -1)])
def test_corrupt_accounting_rejected(key, change):
    row = synthetic_row(n=4)
    row[key][0] += change
    if key in common.LEDGER and key != "F":
        row["ledger"][0, common.L[key]] += change
    with pytest.raises(ValueError):
        common.validate_row(row, world(), n=4)


def branches(counts):
    output, index = {}, 0
    for seed, count in zip(a.RUNS, counts):
        branch = {"status": "applicable" if count else a.NA, "slots": list(range(8, 8 + count)),
                  "origins": list(range(8)) + list(range(16, 16 + count)) + [-1] * (8 - count),
                  "intact_row": index if count else None, "knockouts": []}
        if count:
            index += 1
        for k in range(count):
            branch["knockouts"].append({"row": index, "slot": 8 + k, "origin_id": 16 + k})
            index += 1
        output[seed] = branch
    return output, index


def test_negative_selection_and_exact_slot_ties():
    branch, count = branches((2, 0))
    fitness = np.tile(np.asarray([0, 1, 1])[:, None], (1, 512)).astype(float)
    chosen, rows, pairs = a.selection(fitness, branch)
    assert count == 3 and rows == [0, 1] and pairs == {"51089": [0, 1]}
    assert chosen["51089"]["slot"] == 8 and chosen["51089"]["screen_mean_loss"] == -1
    assert chosen["51090"]["status"] == a.NA


def test_pairing_preserves_covariance_and_reconciles_costs():
    rows = [synthetic_row(10), synthetic_row(12)]
    data = {key: np.stack([row[key] for row in rows]) for key in common.COLS}
    shared = np.arange(512)
    data["F"] += shared
    data["F_kernel"] += shared
    data["income"] += shared * 1024
    comparison = a.comparison(data, 0, 1, world())
    assert comparison["F"]["mean"] == -1000 / 1024 and comparison["F"]["se"] < 1e-12
    assert abs(comparison["fitness_contributions"]["accounting_residual"]["mean"]) < 1e-12


def write_stage(base, name, captures, manifest):
    folder = base / "measurement" / name
    (folder / "rows").mkdir(parents=True)
    rows, index = [], {}
    for i, value in enumerate(captures):
        row = synthetic_row(value)
        relative = f"rows/row_{i:04d}.npz"
        np.savez_compressed(folder / relative, **row,
                            seeds=np.asarray(manifest["seeds"][name], dtype=np.uint64), genome_index=np.asarray(i))
        index[relative] = {"sha256": a.sha(folder / relative), "cpu_seconds": 1.}
        rows.append(row)
    a.save(folder / "row_index.json", index)
    data = {key: np.stack([row[key] for row in rows]) for key in common.COLS}
    np.savez_compressed(folder / "scores.npz", **data, genome_indices=np.arange(len(rows)),
                        seeds=np.asarray(manifest["seeds"][name], dtype=np.uint64))
    return data


def workflow(monkeypatch, tmp_path, counts):
    branch, count = branches(counts)
    genome = np.zeros((count, 875), dtype=np.float32)
    protocol = {"limitations": ["Synthetic test data"]}
    manifest = {"branches": branch, "labels": [f"row{i}" for i in range(count)], "ready": {}, "world": world(),
                "seeds": {"screen": list(range(51_980_000, 51_980_512)),
                          "confirm": list(range(51_990_000, 51_990_512))}}
    a.save(tmp_path / "budget.json", {"status": "complete", "exit_code": 0, "running": {}, "queued": [],
        "cap_cpu_seconds": 7200, "cpu_seconds": 30., "ready": {}})
    monkeypatch.setattr(a, "audit_inputs", lambda base: (protocol, manifest, tmp_path / "G"))
    monkeypatch.setattr(a, "audit_candidates", lambda base, man, g: (genome, branch, {"test": "synthetic"}))
    report = {"status": "complete", "branches": branch, "screen": {}, "confirmation": {},
              "research_genome_lives": 0, "row_cpu_seconds": 0}
    if count:
        first = write_stage(tmp_path, "screen", list(range(10, 10 + count)), manifest)
        chosen, selected, pairs = a.selection(first["F"], branch)
        a.save(tmp_path / "measurement/selection.json", {"selection": chosen, "screen_rows": selected,
            "confirm_pairs": pairs, "screen_scores_sha256": a.sha(tmp_path / "measurement/screen/scores.npz")})
        np.savez_compressed(tmp_path / "measurement/confirmation_genotypes.npz", genomes=genome[selected],
            screen_rows=np.asarray(selected), labels=np.asarray([manifest["labels"][i] for i in selected]))
        fresh = write_stage(tmp_path, "confirm", [10, 13] * len(pairs), manifest)
        for seed in a.RUNS:
            report["screen"][seed] = {str(item["slot"]): a.comparison(
                first, branch[seed]["intact_row"], item["row"], world()) for item in branch[seed]["knockouts"]}
        vectors = {"seeds": np.asarray(manifest["seeds"]["confirm"], dtype=np.uint64)}
        for seed, (intact, knockout) in pairs.items():
            value = a.comparison(fresh, intact, knockout, world())
            value.update(positive_above_3se=False, above_0p5=False)
            report["confirmation"][seed] = {"selection": chosen[seed], "loss": value}
            vectors["s" + seed + "_intact_minus_KO"] = fresh["F"][intact] - fresh["F"][knockout]
        np.savez_compressed(tmp_path / "measurement/contrasts.npz", **vectors)
        report.update(selection=chosen, confirmation_genome_lives=len(selected) * 512,
                      research_genome_lives=(count + len(selected)) * 512, row_cpu_seconds=count + len(selected))
    else:
        report["no_applicable_branches"] = True
    a.save(tmp_path / "measurement/report.json", report)
    return a.analyze(tmp_path)


@pytest.mark.parametrize("counts,lives", [((0, 0), 0), ((2, 0), 2560), ((0, 2), 2560), ((2, 1), 4608)])
def test_whole_raw_data_analysis_preserves_all_branch_cases(monkeypatch, tmp_path, counts, lives):
    summary, vectors = workflow(monkeypatch, tmp_path, counts)
    assert summary["status"] == "complete" and summary["research_genome_lives"] == lives
    for seed, count in zip(a.RUNS, counts):
        if count:
            assert summary["selection"][seed]["slot"] == 8
            assert summary["confirmation"][seed]["F"]["mean"] == -1500 / 1024
            assert np.all(vectors["s" + seed + "_intact_minus_KO"] == -1500 / 1024)
        else:
            assert summary["selection"][seed]["status"] == a.NA
            assert seed not in summary["confirmation"]


@pytest.mark.parametrize("target", ["selection", "raw_hash", "aggregate", "report", "contrasts", "count", "budget"])
def test_complete_data_corruption_is_rejected(monkeypatch, tmp_path, target):
    workflow(monkeypatch, tmp_path, (0, 2))
    if target in ("selection", "report", "count", "budget", "raw_hash"):
        file = {"selection": "measurement/selection.json", "report": "measurement/report.json",
                "count": "measurement/report.json", "budget": "budget.json",
                "raw_hash": "measurement/screen/row_index.json"}[target]
        record = a.read(tmp_path / file)
        if target == "selection":
            record["selection"]["51090"]["slot"] += 1
        elif target == "report":
            record["confirmation"]["51090"]["loss"]["F"]["mean"] += .1
        elif target == "count":
            record["research_genome_lives"] += 512
        elif target == "budget":
            record["cpu_seconds"] = 7201
        else:
            record["rows/row_0000.npz"]["sha256"] = "wrong"
        a.save(tmp_path / file, record)
    else:
        file = "measurement/confirm/scores.npz" if target == "aggregate" else "measurement/contrasts.npz"
        record = a.arrays(tmp_path / file)
        key = "F" if target == "aggregate" else "s51090_intact_minus_KO"
        record[key].reshape(-1)[0] += .1
        np.savez_compressed(tmp_path / file, **record)
    with pytest.raises(ValueError):
        a.analyze(tmp_path)


def test_incomplete_budget_never_reads_inputs_or_G_outcomes(monkeypatch, tmp_path):
    monkeypatch.setattr(a, "audit_inputs", lambda base: pytest.fail("read inputs/outcomes before completion"))
    assert a.analyze(tmp_path)[0]["budget_status"] == "not_started"
    a.save(tmp_path / "budget.json", {"status": "running"})
    assert a.analyze(tmp_path)[0]["budget_status"] == "running"
    a.save(tmp_path / "budget.json", {"status": "complete", "running": {"123": "work"}, "queued": []})
    with pytest.raises(ValueError, match="active or queued"):
        a.analyze(tmp_path)


def test_export_preserves_prelaunch_and_raw_bytes_and_rechecks_analysis(monkeypatch, tmp_path):
    base, destination = tmp_path / "working", tmp_path / "public"
    base.mkdir()
    destination.mkdir()
    summary, vectors = workflow(monkeypatch, base, (0, 2))
    protocol = {"G_study": "outputs/mock_G", "wait_for_studies": ["outputs/mock_H", "outputs/mock_I"],
                "source_identity": {}, "helpers": {}}
    a.save(base / "protocol.json", protocol)
    (base / "inputs").mkdir()
    for name in ("measure.py", "run_budgeted.py", "run.log"):
        (base / name).write_text("# synthetic exported receipt\n")
    a.save(base / "ready.json", {})
    for study in [protocol["G_study"], *protocol["wait_for_studies"]]:
        folder = base / "dependencies" / Path(study).name
        names = ["protocol.json", "run_budgeted.py", "budget.json"]
        if study == protocol["G_study"]:
            names += ["audit_search.py", *[f"configs/s{seed}.yaml" for seed in a.RUNS],
                      *[f"runs/s{seed}/{name}" for seed in a.RUNS for name in
                        ("checkpoint.pt", "lineage.jsonl", "best_genome.json")]]
        for name in names:
            path = folder / name
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_text("synthetic dependency bytes\n")
    (destination / "README.md").write_text("Original immutable preparation\n")
    initial = {"status": "prospective_preparation_not_released", "artifacts": {
        "README.md": {"sha256": a.sha(destination / "README.md"),
                      "bytes": (destination / "README.md").stat().st_size}}}
    a.save(destination / "provenance.json", initial)
    a.export(base, destination, summary, vectors)
    assert a.read(destination / "prelaunch/provenance.json") == initial
    assert (destination / "prelaunch/README.md").read_text() == "Original immutable preparation\n"
    public = a.read(destination / "provenance.json")
    assert public["status"] == "complete" and public["research_genome_lives"] == 2560
    for name, record in public["artifacts"].items():
        assert a.sha(destination / name) == record["sha256"]
    for row in (base / "measurement").rglob("row_*.npz"):
        assert row.read_bytes() == (destination / row.relative_to(base)).read_bytes()
    assert a.read(destination / "summary.json") == summary
    assert (destination / "review/test_single_branch.py.txt").exists()
