"""Pure genome/mocked scoring tests for prospective duplicate use; no life simulation or G outcome inspection."""
import importlib.util
from pathlib import Path

import numpy as np
import pytest

HERE = Path(__file__).resolve().parent
loader = importlib.util.spec_from_file_location("duplicate_measure_test", HERE / "measure.py")
m = importlib.util.module_from_spec(loader)
loader.loader.exec_module(m)


def endpoints(counts=(2, 1)):
    from src.genome import Layout

    layout, original = Layout.load(HERE / "inputs/founder_row38.json")
    records = {}
    for seed, count in zip(m.RUNS, counts):
        genome = original.clone()
        origins = np.array(list(range(8)) + [-1] * 8, dtype=np.int64)
        for k in range(count):
            genome = layout.duplicate(genome, k, 8 + k, split=False)
            origins[8 + k] = 16 + k
        records[seed] = {"genome": genome, "origins": origins, "audit": {"test": "synthetic"}}
    return layout, records


def test_all_active_duplicate_origins_get_exact_delete_interventions():
    layout, records = endpoints()
    genomes, labels, branches = m.candidates(layout, records)
    assert len(genomes) == len(labels) == 5
    for seed, branch in branches.items():
        original = records[int(seed)]["genome"]
        np.testing.assert_array_equal(genomes[branch["intact_row"]], original.numpy())
        for candidate in branch["knockouts"]:
            ko = layout.delete(original, candidate["slot"])
            assert genomes[candidate["row"]].tobytes() == ko.numpy().tobytes()
            assert candidate["raw_sha256"] == m.raw_sha(ko.numpy())
            assert candidate["runtime_table_sha256"] == m.raw_sha(layout.pack(ko[None], "hexprism"))
            assert candidate["origin_id"] >= 16
            assert not layout.active(ko)[candidate["slot"]]
    assert branches["51089"]["slots"] == [8, 9] and branches["51090"]["slots"] == [8]


def test_candidate_rule_uses_origin_not_slot_number_and_keeps_silent_copies():
    layout, records = endpoints((1, 0))
    genome = records[51089]["genome"]
    # Represent a duplicate lineage that replaced an original slot; this is a pure synthetic genotype fixture.
    records[51089]["origins"][2] = 30
    assert np.count_nonzero(layout.view(genome, "A")[:, 8].numpy()) == 0
    _, _, branches = m.candidates(layout, records)
    assert branches["51089"]["slots"] == [2, 8]
    assert branches["51090"]["status"] == "not_applicable_no_active_duplicate_origin"
    assert branches["51090"]["intact_row"] is None


def test_no_copies_produces_no_scientific_rows():
    layout, records = endpoints((0, 0))
    genomes, labels, branches = m.candidates(layout, records)
    assert genomes.shape == (0, layout.size) and labels == []
    assert all(not b["knockouts"] and b["intact_row"] is None for b in branches.values())


def test_policy_bound_is_34_rows_even_when_original_slots_were_replaced():
    layout, records = endpoints((0, 0))
    for value in records.values():
        layout.view(value["genome"], "act")[:] = 1
        value["origins"] = np.arange(16, 32)
    matrix, _, branches = m.candidates(layout, records)
    assert len(matrix) == 34 and sum(len(b["knockouts"]) for b in branches.values()) == 32
    assert (34 + 4) * m.LIVES == 19456


def test_selection_is_paired_mean_slot_tie_break_and_retains_negative_winner():
    layout, records = endpoints()
    genomes, _, branches = m.candidates(layout, records)
    noise = np.arange(512, dtype=float)
    fitness = np.tile(noise, (len(genomes), 1))
    fitness[1] -= 2
    fitness[2] -= 2
    fitness[4] += 3
    selected = m.choose(fitness, branches)
    assert selected["51089"]["slot"] == 8 and selected["51089"]["screen_mean_loss"] == 2
    assert selected["51090"]["status"] == "selected" and selected["51090"]["screen_mean_loss"] == -3


@pytest.mark.parametrize("bad", [np.zeros((5, 511)), np.zeros(5), np.full((5, 512), np.nan)])
def test_selection_rejects_invalid_paired_score_matrix(bad):
    layout, records = endpoints()
    _, _, branches = m.candidates(layout, records)
    with pytest.raises(ValueError):
        m.choose(bad, branches)


def test_seeds_and_world_fixed_before_endpoints():
    assert m.seeds("screen") == list(range(51_980_000, 51_980_512))
    assert m.seeds("confirm") == list(range(51_990_000, 51_990_512))
    assert not set(m.seeds("screen")) & set(m.seeds("confirm"))
    w = m.world()
    assert (w.T, w.t_open, w.t_fork, w.fork_flags, w.d0, w.d_min, w.sigma, w.lam_s) == (
        1024, 0, 0, 0, .5, .25, .4, 4)
    with pytest.raises(ValueError):
        m.seeds("extend")


def test_preparation_and_pins_do_not_read_G_endpoints_or_simulate(monkeypatch):
    from src.life import build

    real_text, real_bytes = Path.read_text, Path.read_bytes

    def text(path, *args, **kwargs):
        assert "/runs/" not in str(path), "read interim G endpoint"
        return real_text(path, *args, **kwargs)

    def data(path, *args, **kwargs):
        assert "/runs/" not in str(path), "read interim G endpoint"
        return real_bytes(path, *args, **kwargs)

    monkeypatch.setattr(Path, "read_text", text)
    monkeypatch.setattr(Path, "read_bytes", data)
    monkeypatch.setattr(build, "run", lambda *a, **kw: pytest.fail("simulated life"))
    p = m.check_protocol()
    assert p["max_genome_lives"] == 19456 and p["candidate_rule"].startswith("every active slot")


@pytest.mark.parametrize("empty", [False, True])
def test_entire_two_stage_runner_preserves_roles_and_negative_confirmation(monkeypatch, tmp_path, empty):
    import json
    import shutil
    import sys
    from types import SimpleNamespace

    from scripts import taskvar_second_step
    from scripts.taskvar_confirm import COLS
    from src import checkpoint
    from src.life import build

    protocol = m.check_protocol()
    layout, records = endpoints((0, 0) if empty else (1, 1))
    shutil.copytree(HERE / "inputs", tmp_path / "inputs")
    shutil.copy2(HERE / "protocol.json", tmp_path / "protocol.json")
    monkeypatch.setattr(m, "STUDY", tmp_path)
    monkeypatch.setattr(m, "check_protocol", lambda: protocol)
    monkeypatch.setattr(m, "load_endpoints", lambda p: (layout, records))
    monkeypatch.setitem(sys.modules, "run_budgeted", SimpleNamespace(check_ready=lambda: {"test": "ready"}))
    monkeypatch.setattr(checkpoint, "numerical_identity", lambda: protocol["numerical_identity"])
    monkeypatch.setattr(build, "run", lambda *a, **kw: pytest.fail("simulated a life"))
    calls = []

    class Store:
        def __init__(self, out, genomes, world, evaluator, threads, cap):
            self.cpu_seconds, self.stage = 0, out.name
            out.mkdir(parents=True, exist_ok=True)
            assert len(genomes) == 4 and threads == 2 and cap == 7200

        def row(self, stage, i, seeds):
            assert seeds == m.seeds(self.stage)
            if self.stage == "screen":
                assert (tmp_path / "measurement/genotypes.npz").exists()
            else:
                assert (tmp_path / "measurement/selection.json").exists()
            calls.append((self.stage, i))
            self.cpu_seconds += 1
            fitness = [0, -2, 0, 4][i] if self.stage == "screen" else [0, -1, 0, 3][i]
            row = {key: np.zeros(512) for key in COLS}
            row.update(cpu_seconds=np.asarray(1.), wall_seconds=np.asarray(1.))
            for key, value in {"F": fitness, "F_kernel": fitness, "cost": 10000,
                               "income": fitness * 1024 + 10000, "live_time": 102400, "n_end": 100,
                               "n_S_end": 30, "n_M_end": 40, "n_H_end": 30, "t_end": 1024,
                               "window": 1024, "last_birth": 100}.items():
                row[key][:] = value
            return row

    monkeypatch.setattr(taskvar_second_step, "RowStore", Store)
    result = m.run()
    assert result["status"] == "complete"
    if empty:
        assert result["research_genome_lives"] == 0 and calls == []
        assert result["no_applicable_branches"]
    else:
        assert result["research_genome_lives"] == 4096
        assert calls == [(stage, i) for stage in ("screen", "confirm") for i in range(4)]
        assert result["confirmation"]["51089"]["loss"]["F"]["mean"] == 1
        assert result["confirmation"]["51090"]["loss"]["F"]["mean"] == -3
        selected = json.loads((tmp_path / "measurement/selection.json").read_text())
        assert selected["screen_rows"] == [0, 1, 2, 3]
        assert selected["selection"]["51090"]["screen_mean_loss"] == -4
