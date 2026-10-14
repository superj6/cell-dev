"""Confirmation keeps selection, fresh seeds, production accounting and lesion contrasts separate."""
import hashlib
import json
from types import SimpleNamespace

import numpy as np
import pytest
import torch

from scripts import taskvar_confirm as confirm
from src.life import build, spec
from src.life.evaluate import LifeEvaluator


def test_top_five_percent_rounds_up_and_ties_use_original_rows():
    scores = np.zeros((65, 2))
    scores[0] = 999  # The parent is never a candidate.
    scores[[20, 8, 3, 1, 2]] = 5
    assert confirm.select_top(scores) == [1, 2, 3, 8]
    assert confirm.select_top(np.zeros((2, 2))) == [1]
    scores[4, 0] = np.nan
    with pytest.raises(ValueError, match="finite"):
        confirm.select_top(scores)


def test_all_followup_lives_are_disjoint_with_explicit_order():
    lives = {"rescore": 512, "confirm": 512, "lesion": 256}
    blocks = {"rescore": 81, "confirm": 82, "lesion": 83}
    seeds = confirm.stage_seeds([51_800_000, 51_800_001], lives, blocks)
    assert seeds["rescore"] == list(range(51_810_000, 51_810_512))
    assert len(set().union(*map(set, seeds.values()))) == 1280
    with pytest.raises(ValueError, match="overlap"):
        confirm.stage_seeds([51_810_010], lives, blocks)
    with pytest.raises(ValueError, match="overlap"):
        confirm.stage_seeds([1], lives, dict(blocks, lesion=82))
    with pytest.raises(ValueError, match="duplicates"):
        confirm.stage_seeds([1, 1], lives, blocks)


def score_columns(score, world):
    row = {key: np.zeros(len(score), dtype=float) for key in confirm.COLS}
    row["F"] = np.asarray(score, dtype=float)
    row["F_kernel"] = row["F"].copy()
    row["income"] = row["F"] * world.T
    row["window"][:] = world.T
    row["t_end"][:] = world.T
    row.update(cpu_seconds=np.asarray(0.1), wall_seconds=np.asarray(0.2))
    return row


def test_lesion_interaction_pairs_four_arms_on_same_lives():
    world = spec.world("catch_speck_l4", T=1024)
    normal = {0: score_columns([10, 20, 30], world), 4: score_columns([14, 25, 36], world)}
    lesioned = {0: score_columns([9, 19, 29], world), 4: score_columns([10, 21, 32], world)}
    report = confirm.lesion_report(normal, lesioned, 4, world)
    assert report["gain_dependence"] == {"mean": 3, "se": 0, "n": 3}
    assert report["winner_loss"]["mean"] == 4
    assert report["parent_loss"]["mean"] == 1


def test_fitness_decomposition_retains_extinction_and_accounting_residual():
    world = spec.world("catch_speck_l4", T=10)
    parent = score_columns([10, 20], world)
    mutant = score_columns([12, 22], world)
    mutant["income"] = parent["income"] + 40
    mutant["cost"] = parent["cost"] + 10
    mutant["extinct_charge"][:] = 0.2
    report = confirm.compare_rows(mutant, parent, world)
    terms = report["fitness_contributions"]
    assert terms["income"]["mean"] == 4
    assert terms["cost_saving"]["mean"] == -1
    assert terms["extinction_charge_saving"]["mean"] == -0.2
    assert terms["accounting_residual"]["mean"] == pytest.approx(-0.8)
    assert sum(value["mean"] for value in terms.values()) == pytest.approx(report["F"]["mean"])


def test_rescore_freezes_one_winner_before_independent_confirmation(tmp_path, monkeypatch):
    world = spec.world("catch_speck_l4", T=32)
    manifest = {"seeds": [1, 2], "numerical_identity": {"test": 1}, "world": "base"}
    genomes = np.zeros((65, 10), dtype=np.float32)
    monkeypatch.setattr(confirm, "load_screen", lambda *args: (manifest, genomes, world, None, [3, 2]))
    monkeypatch.setattr(confirm, "numerical_identity", lambda: {"test": 1})
    monkeypatch.setattr(confirm, "sha", lambda path: "unchanged")
    calls = []

    def fake_row(out, index, genomes, trial_world, seeds, evaluator, threads):
        out.mkdir(parents=True, exist_ok=True)
        calls.append((out.name, index, trial_world, seeds))
        # Tied re-score picks original row 2 despite row 3 appearing first.
        score = {"rescore": {0: 10, 2: 12, 3: 12}, "confirm": {0: 10, 2: 8},
                 "lesion_normal": {0: 10, 2: 14}, "lesion_lateral_off": {0: 8, 2: 9}}[out.name][index]
        return score_columns([score] * len(seeds), trial_world)

    monkeypatch.setattr(confirm, "score_row", fake_row)
    out = tmp_path / "followup"
    report = confirm.run_followup(tmp_path / "screen", tmp_path / "parent", out,
                                  lives=dict.fromkeys(confirm.STAGES, 2),
                                  blocks=dict(zip(confirm.STAGES, (81, 82, 83))), fork_time=16)
    assert report["winner_genome_row"] == 2
    assert report["winner_mutant_index"] == 1
    assert report["confirmation"]["F"]["mean"] == -2
    assert not report["confirmed_positive_2se"]
    assert not report["confirmed_positive_3se"]
    assert not report["practical_gain_at_least_0p5"]
    assert report["lesion"]["gain_dependence"]["mean"] == 3
    assert [i for stage, i, _, _ in calls if stage == "confirm"] == [0, 2]
    lesion_calls = [call for call in calls if call[0].startswith("lesion")]
    assert all(w.t_open == 0 and w.t_fork == 16 for _, _, w, _ in lesion_calls)
    assert len({tuple(seeds) for _, _, _, seeds in lesion_calls}) == 1
    assert all(w.fork_flags == spec.V3.flags("lateral_off")
               for stage, _, w, _ in lesion_calls if stage == "lesion_lateral_off")
    saved = json.loads((out / "selection.json").read_text())
    assert saved["winner_genome_row"] == 2 and saved["winner_mutant_index"] == 1
    assert len(saved["winner_sha256"]) == 64
    saved["winner_genome_row"] = 3
    confirm.atomic_json(out / "selection.json", saved)
    with pytest.raises(ValueError, match="frozen selection differs"):
        confirm.run_followup(tmp_path / "screen", tmp_path / "parent", out,
                             lives=dict.fromkeys(confirm.STAGES, 2),
                             blocks=dict(zip(confirm.STAGES, (81, 82, 83))), fork_time=16)
    with pytest.raises(ValueError, match="inputs changed"):
        confirm.run_followup(tmp_path / "screen", tmp_path / "parent", out,
                             lives=dict.fromkeys(confirm.STAGES, 2),
                             blocks=dict(zip(confirm.STAGES, (81, 82, 84))), fork_time=16)


def test_numerical_pin_mismatch_stops_before_creating_output(tmp_path, monkeypatch):
    world = spec.world("catch_speck_l4", T=32)
    manifest = {"seeds": [1, 2], "numerical_identity": {"test": 1}}
    monkeypatch.setattr(confirm, "load_screen", lambda *args: (manifest, np.zeros((2, 2)), world, None, [1]))
    monkeypatch.setattr(confirm, "numerical_identity", lambda: {"test": 2})
    with pytest.raises(ValueError, match="identity differs"):
        confirm.run_followup(tmp_path / "screen", tmp_path / "parent", tmp_path / "out",
                             lives=dict.fromkeys(confirm.STAGES, 2),
                             blocks=dict(zip(confirm.STAGES, (81, 82, 83))), fork_time=16)
    assert not (tmp_path / "out").exists()


def test_atomic_rows_resume_with_production_extinction_and_guard_accounting(tmp_path, monkeypatch):
    world = spec.world("catch_speck_l4", T=32)
    ledger = np.zeros((2, spec.V3.LEDGER_SIZE))
    ledger[:, spec.V3.L["t_end"]] = [10, 8]
    ledger[:, spec.V3.L["t_ext"]] = [0, 8]
    ledger[:, spec.V3.L["status"]] = [spec.STATUS["guard_events"], spec.STATUS["extinct"]]
    ledger[:, spec.V3.L["live_time"]] = 100
    ledger[:, spec.V3.L["cost"]] = spec.V3.column_cost(ledger, world)
    ledger[:, spec.V3.L["guard_charge"]] = spec.V3.guard_charge(ledger, world)
    ledger[:, spec.V3.L["F"]] = spec.V3.fitness(ledger, world)
    result = build.Lives(ledger, np.zeros((2, spec.V3.HASH_SIZE), dtype=np.uint64), abi=spec.V3)
    monkeypatch.setattr(build, "run", lambda *args, **kwargs: result)
    monkeypatch.setattr(spec.V3, "pack_genomes", lambda genomes, lattice: genomes)
    evaluator = SimpleNamespace(extinct_charge=True)
    evaluator.columns = lambda *args: LifeEvaluator.columns(evaluator, *args)
    args = (tmp_path, 0, np.zeros((1, 10)), world, [1, 2], evaluator, 1)
    row = confirm.score_row(*args)
    assert row["F"][0] == row["F_kernel"][0]
    assert row["guard_charge"][0] == world.c_live * world.n_max * (world.T - 10)
    assert row["extinct_charge"][1] == pytest.approx(0.02 * 24 / 32)
    assert row["F"][1] == row["F_kernel"][1] - row["extinct_charge"][1]
    assert not list(tmp_path.glob("*.tmp.npz"))
    monkeypatch.setattr(build, "run", lambda *args, **kwargs: pytest.fail("resume reran a completed genome"))
    assert confirm.score_row(*args)["F"].tobytes() == row["F"].tobytes()
    path = tmp_path / "row_0000.npz"
    with np.load(path) as saved:
        damaged = {key: saved[key].copy() for key in saved.files}
    damaged["F"][1] += 1
    confirm.atomic_npz(path, **damaged)
    with pytest.raises(ValueError, match="production accounting"):
        confirm.score_row(*args)


def saved_screen(tmp_path, monkeypatch, change=None):
    screen = tmp_path / "screen"
    screen.mkdir()
    parent = tmp_path / "parent.json"
    parent.write_text("parent")
    cfg = tmp_path / "config.yaml"
    cfg.write_text("configuration")
    genomes = np.zeros((3, 2), dtype=np.float32)
    np.save(screen / "genomes.npy", genomes)
    manifest = {"parent_sha256": confirm.sha(parent), "config_sha256": confirm.sha(cfg),
                "runner_sha256": confirm.sha(confirm.ROOT / "scripts/taskvar_gradient.py"),
                "kernel_source_sha256": confirm.sha(confirm.ROOT / "src/life/kernel.c"),
                "genomes_sha256": hashlib.sha256(genomes.tobytes()).hexdigest(), "mutants": 2,
                "world": "base", "overrides": {"T": 32}, "seeds": [1, 2]}
    confirm.atomic_json(screen / "manifest.json", manifest)
    columns = {key: np.zeros((3, 2)) for key in confirm.SCREEN_COLS}
    columns["t_end"][:] = 32
    if change:
        change(columns)
    np.savez_compressed(screen / "scores.npz", seeds=np.asarray([1, 2], dtype=np.uint64), **columns)
    for i in range(3):
        np.savez_compressed(screen / f"row_{i:04d}.npz", **{key: values[i] for key, values in columns.items()})
    monkeypatch.setattr(confirm.Layout, "load", lambda path: (None, torch.zeros(2)))
    monkeypatch.setattr(confirm, "LifeEvaluator", lambda *args: None)
    return screen, parent


def test_saved_screen_binds_parent_and_runner_sources(tmp_path, monkeypatch):
    screen, parent = saved_screen(tmp_path, monkeypatch)
    assert confirm.load_screen(screen, parent)[-1] == [1]
    parent.write_text("changed parent")
    with pytest.raises(ValueError, match="sources differ"):
        confirm.load_screen(screen, parent)


@pytest.mark.parametrize("failure", ["capacity", "ledger_mismatch", "incomplete", "accounting"])
def test_cached_screen_rejects_invalid_lives_even_when_checkpoints_agree(tmp_path, monkeypatch, failure):
    def change(columns):
        if failure in spec.STATUS:
            columns["status"][1, 0] = spec.STATUS[failure]
        elif failure == "incomplete":
            columns["t_end"][1, 0] = 10
        else:
            columns["F"][1, 0] = 1

    screen, parent = saved_screen(tmp_path, monkeypatch, change)
    with pytest.raises(ValueError, match="capacity|mismatch|incomplete|accounting"):
        confirm.load_screen(screen, parent)
