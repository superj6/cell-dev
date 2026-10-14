"""Synthetic independent-analysis checks only; no kernel or evolution is executed."""
import importlib.util
import json
import shutil
from dataclasses import asdict
from pathlib import Path

import numpy as np
import pytest

HERE = Path(__file__).resolve().parent
loader = importlib.util.spec_from_file_location("structural_analysis_test", HERE / "analyze.py")
analysis = importlib.util.module_from_spec(loader)
loader.loader.exec_module(analysis)


def test_duration_average_uses_shared_covariance_and_keeps_negative_effects():
    sequence = np.arange(256, dtype=float)
    fitness = {}
    for duration, value in zip(analysis.DURATIONS, (sequence, -sequence, np.full(256, -3.))):
        fitness[duration] = np.stack([np.zeros(256)] * 5 + [value])
    values = analysis.duration_contrast(fitness, 5, 3)
    assert np.array_equal(values, np.full(256, -1.))
    assert analysis.accounting.stats(values) == {"mean": -1., "se": 0., "n": 256}
    fitness[768] = fitness[768][:, :-1]
    with pytest.raises(ValueError):
        analysis.duration_contrast(fitness, 5, 3)


@pytest.fixture
def neutrality(tmp_path):
    from src.genome import Layout

    path = tmp_path / "neutrality"
    path.mkdir()
    (tmp_path / "inputs").mkdir()
    founder_file = HERE / "inputs/founder_row38.json"
    shutil.copy2(founder_file, tmp_path / "inputs/founder_row38.json")
    protocol = {"founder_file": "inputs/founder_row38.json"}
    analysis.accounting.write_json(tmp_path / "protocol.json", protocol)
    layout, founder = Layout.load(founder_file)
    genotypes = [founder] + [layout.duplicate(founder, i, 8, split=False) for i in range(8)]
    np.savez_compressed(path / "genotypes.npz", genomes=np.stack([g.numpy() for g in genotypes]))
    world = analysis.accounting.spec.world("catch_speck_l4", T=1024, d0=.5, d_min=.25, sigma=.4, lam_s=4)
    analysis.accounting.write_json(path / "manifest.json", {
        "protocol_sha256": analysis.accounting.digest(tmp_path / "protocol.json"),
        "world": asdict(world), "seeds": [51_090_000, 51_090_001], "source_slots": list(range(8)),
        "destination_slot": 8, "raster_cap": 100000, "fate_cap": 8192})
    rows = []
    for i, genotype in enumerate(genotypes):
        ledger = np.zeros((2, 57))
        ledger[:, analysis.accounting.spec.V3.L["t_end"]] = 1024
        data = {"ledger": ledger, "hashes": np.zeros((2, 5), dtype=np.uint64),
                "raster_n": np.array([2, 2]), "fate_n": np.array([2, 2])}
        for life in (0, 1):
            values = np.arange(36, dtype=float).reshape(2, 18)
            if i:
                values[:, 10] = values[:, i + 1]
            data.update({f"spike_t_{life}": np.array([1., 2.]), f"spike_uid_{life}": np.array([3, 4]),
                         f"fate_i_{life}": np.arange(14).reshape(2, 7), f"fate_f_{life}": values})
        file = path / f"row_{i:02d}.npz"
        np.savez_compressed(file, **data)
        rows.append({"row": i, "raw_sha256": analysis.accounting.digest(file),
                     "genome_sha256": analysis.raw_sha(genotype.numpy())})
    analysis.accounting.write_json(path / "report.json", {"status": "complete", "genome_lives": 18,
                                                          "cpu_seconds": 1., "rows": rows})
    return tmp_path, protocol


def test_independent_neutrality_allows_only_exact_silent_trajectory(neutrality):
    study, protocol = neutrality
    assert analysis.neutrality_audit(study, protocol)["genome_lives"] == 18


@pytest.mark.parametrize("change", ["guard", "spike_uid", "fate_state", "short_log", "genotype"])
def test_independent_neutrality_rejects_altered_evidence_even_with_refreshed_file_hash(neutrality, change):
    study, protocol = neutrality
    folder = study / "neutrality"
    if change == "genotype":
        file = folder / "genotypes.npz"
        data = analysis.accounting.read_npz(file)
        data["genomes"][1, 0] += 1
        np.savez_compressed(file, **data)
    else:
        file = folder / "row_01.npz"
        data = analysis.accounting.read_npz(file)
        if change == "guard":
            data["ledger"][0, analysis.accounting.spec.V3.L["status"]] = analysis.accounting.spec.STATUS["guard_cells"]
        elif change == "spike_uid":
            data["spike_uid_0"][0] += 1
        elif change == "fate_state":
            data["fate_f_0"][0, 10] += 1
        else:
            data["spike_t_0"] = data["spike_t_0"][:-1]
        np.savez_compressed(file, **data)
        report = json.loads((folder / "report.json").read_text())
        report["rows"][1]["raw_sha256"] = analysis.accounting.digest(file)
        analysis.accounting.write_json(folder / "report.json", report)
    with pytest.raises(ValueError):
        analysis.neutrality_audit(study, protocol)


def test_archive_hashes_reject_changed_cached_data(tmp_path):
    file = tmp_path / "scores.npz"
    file.write_bytes(b"fixed")
    analysis.accounting.write_json(tmp_path / "provenance.json", {"artifacts": {
        "scores.npz": {"sha256": analysis.accounting.digest(file)}}})
    analysis.verify_archive(tmp_path)
    file.write_bytes(b"changed")
    with pytest.raises(ValueError, match="archive artifact"):
        analysis.verify_archive(tmp_path)
