"""Pure genetics, paired arithmetic and mocked full M workflow; never simulate a life."""
import importlib.util
import json
import shutil
import sys
from pathlib import Path
from types import SimpleNamespace

import numpy as np
import pytest

HERE = Path(__file__).resolve().parent
loader = importlib.util.spec_from_file_location("interaction_measure_test", HERE / "measure.py")
m = importlib.util.module_from_spec(loader)
loader.loader.exec_module(m)


def endpoints():
    from src.genome import Layout

    layout, original = Layout.load(HERE / "inputs/founder_row38.json")
    records = {}
    for seed, source in zip(m.RUNS, (0,)):
        genome = layout.duplicate(original, source, 8, split=False)
        origins = np.array(list(range(8)) + [16] + [-1] * 7, dtype=np.int64)
        event = {"origin_id": 16, "generation": 2, "source_slot": source, "destination_slot": 8,
                 "source_origin_id": source, "child_id": 555, "child_retained": True}
        records[seed] = {"genome": genome, "origins": origins, "innovations": [event],
                         "audit": {"fixture": "synthetic"}}
    return layout, records


def test_all_four_roles_are_exact_deletions_and_all_four_rows_retained():
    layout, records = endpoints()
    genomes, labels, branches = m.candidates(layout, records)
    assert genomes.shape == (4, 875) and len(labels) == 4
    for seed, branch in branches.items():
        original = records[int(seed)]["genome"]
        assert branch["copy_origin_id"] == 16 and branch["source_origin_id"] in (0, 5)
        for role in m.ROLES:
            row = branch["rows"][role]
            genome = original.clone()
            for slot in row["deleted_slots"]:
                genome = layout.delete(genome, slot)
            assert genomes[row["row"]].tobytes() == genome.numpy().tobytes()
            assert row["raw_sha256"] == m.raw_sha(genome.numpy())
            assert row["runtime_table_sha256"] == m.raw_sha(layout.pack(genome[None], "hexprism"))
            assert len(row["active_slots"]) == 9 - len(row["deleted_slots"])


def test_source_resolves_by_origin_not_old_slot():
    layout, records = endpoints()
    origins = records[51090]["origins"]
    origins[0], origins[2] = origins[2], origins[0]
    _, _, branches = m.candidates(layout, records)
    assert branches["51090"]["source_slot"] == 2
    assert branches["51090"]["duplication_event"]["source_slot"] == 0


@pytest.mark.parametrize("change", ["missing_source", "duplicate_origin", "absent_event", "multiple_events",
                                  "no_copy", "two_copies", "mask_mismatch"])
def test_scope_mismatches_stop_without_selecting_replacement_genes(change):
    layout, records = endpoints()
    record = records[51090]
    if change == "missing_source":
        record["origins"][0] = 7
    elif change == "duplicate_origin":
        record["origins"][6] = 0
    elif change == "absent_event":
        record["innovations"] = []
    elif change == "multiple_events":
        record["innovations"] *= 2
    elif change == "no_copy":
        record["origins"][8] = 15
    elif change == "two_copies":
        record["origins"][6] = 17
    else:
        record["origins"][7] = -1
    with pytest.raises(ValueError):
        m.candidates(layout, records)


def test_canonical_packing_proof_rejects_bad_delete_operator(monkeypatch):
    layout, records = endpoints()
    monkeypatch.setattr(layout, "delete", lambda genome, slot: genome.clone())
    with pytest.raises(ValueError, match="runtime table"):
        m.candidates(layout, records)


def score_rows():
    from scripts.taskvar_confirm import COLS

    common = np.arange(512, dtype=float) / 1000
    rows = {}
    for i, fitness in enumerate((10, 8, 7, 6, 10, 9, 8, 6)):
        row = {key: np.zeros(512) for key in COLS}
        row.update(cpu_seconds=np.asarray(1.), wall_seconds=np.asarray(1.))
        for key, value in {"F": fitness + common, "F_kernel": fitness + common + i / 10,
                           "extinct_charge": i / 10, "cost": 10000 + 17 * i, "guard_charge": i * 2,
                           "income": (fitness + common + i / 10) * 1024 + 10000 + 19 * i,
                           "live_time": 102400, "n_end": 100 + i, "n_S_end": 30, "n_M_end": 40,
                           "n_H_end": 30 + i, "t_end": 1024, "window": 1024, "last_birth": 100}.items():
            row[key][:] = value
        rows[i] = row
    return rows


def test_four_arm_interaction_keeps_pair_covariance_both_signs_losses_and_accounting():
    layout, records = endpoints()
    _, _, branches = m.candidates(layout, records)
    rows = score_rows()
    for expected, offset in ((1, 0), (-1, 4)):
        paired_rows = {i: rows[i + offset] for i in range(4)}
        report, vectors = m.factorial(paired_rows, branches['51090'], m.world())
        f = report["interaction"]["F"]
        assert f["n"] == 512 and f["mean"] == pytest.approx(expected)
        assert f["se"] < 1e-15
        assert report["interaction"]["abs_above_3se"] and report["interaction"]["abs_at_least_0p5"]
        assert set(report["losses"]) == set(m.ROLES[1:])
        assert set(vectors) == {"interaction", "copy_KO_loss", "source_KO_loss", "double_KO_loss"}
        residual = report["interaction"]["fitness_contributions"]["accounting_residual"]
        assert abs(residual["mean"]) < 1e-14


def test_exact_zero_interaction_remains_unresolved():
    layout, records = endpoints()
    _, _, branches = m.candidates(layout, records)
    rows = score_rows()
    for index, value in enumerate((10., 8., 7., 5.)):
        rows[index]["F"] = np.full(512, value)
    report, _ = m.factorial(rows, branches['51090'], m.world())
    assert report["interaction"]["F"]["mean"] == 0
    assert not report["interaction"]["abs_above_3se"]
    assert not report["interaction"]["abs_at_least_0p5"]


@pytest.mark.parametrize("bad", [np.zeros(511), np.full(512, np.nan)])
def test_pairing_rejects_wrong_shape_or_nonfinite_fitness(bad):
    layout, records = endpoints()
    _, _, branches = m.candidates(layout, records)
    rows = score_rows()
    rows[1]["F"] = bad
    with pytest.raises(ValueError, match="paired"):
        m.factorial(rows, branches['51090'], m.world())


def test_fixed_fresh_seeds_and_unlesioned_world():
    assert m.seeds() == list(range(52_000_000, 52_000_512))
    w = m.world()
    assert (w.T, w.t_open, w.t_fork, w.fork_flags, w.d0, w.d_min, w.sigma, w.lam_s) == (
        1024, 0, 0, 0, .5, .25, .4, 4)


def test_preparation_pins_and_frozen_genomes_replay_without_simulation(monkeypatch):
    from src.life import build

    monkeypatch.setattr(build, "run", lambda *a, **kw: pytest.fail("simulated a life"))
    p = m.check_protocol()
    _, genomes, manifest = m.load_frozen(p)
    assert p["genome_lives"] == 2048 and genomes.shape == (4, 875)
    assert set(manifest["branches"]) == {"51090"}
    assert manifest["branches"]["51090"]["source_origin_id"] == 0


def test_entire_mock_workflow_freezes_all_genomes_before_first_score(monkeypatch, tmp_path):
    from scripts import taskvar_second_step
    from src import checkpoint
    from src.life import build

    protocol = m.check_protocol()
    layout, records = endpoints()
    genomes, labels, branches = m.candidates(layout, records)
    frozen = {"labels": labels, "branches": branches, "fixture": "synthetic"}
    shutil.copytree(HERE / "inputs", tmp_path / "inputs")
    shutil.copy2(HERE / "protocol.json", tmp_path / "protocol.json")
    monkeypatch.setattr(m, "STUDY", tmp_path)
    monkeypatch.setattr(m, "check_protocol", lambda: protocol)
    monkeypatch.setattr(m, "load_frozen", lambda p: (layout, genomes, frozen))
    monkeypatch.setitem(sys.modules, "run_budgeted", SimpleNamespace(check_ready=lambda: {"test": "ready"}))
    monkeypatch.setattr(checkpoint, "numerical_identity", lambda: protocol["numerical_identity"])
    monkeypatch.setattr(build, "run", lambda *a, **kw: pytest.fail("simulated a life"))
    calls, rows = [], score_rows()

    class Store:
        def __init__(self, out, genomes, world, evaluator, threads, cap):
            self.cpu_seconds = 0
            assert len(genomes) == 4 and threads == 2 and cap == 1800

        def row(self, stage, i, seeds):
            assert stage == "rows" and seeds == m.seeds()
            receipt = json.loads((tmp_path / "measurement/manifest.json").read_text())
            assert receipt["frozen_genomes"] == frozen and receipt["genome_lives"] == 2048
            with np.load(tmp_path / "measurement/genotypes.npz") as saved:
                assert saved["genomes"].tobytes() == genomes.tobytes()
            calls.append(i)
            self.cpu_seconds += 1
            return rows[i]

    monkeypatch.setattr(taskvar_second_step, "RowStore", Store)
    result = m.run()
    assert result["status"] == "complete" and result["research_genome_lives"] == 2048
    assert calls == list(range(4)) and result["row_cpu_seconds"] == 4
    assert set(result["endpoints"]) == {"51090"}
    assert result["endpoints"]["51090"]["interaction"]["F"]["mean"] == pytest.approx(1)
    with np.load(tmp_path / "measurement/scores.npz") as scores:
        assert scores["F"].shape == (4, 512) and scores["seeds"].tolist() == m.seeds()
    assert not (tmp_path / "measurement/selection.json").exists()
