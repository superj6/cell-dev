"""Pure arrays and mocked lives only; the flash confirmation tail never reaches C here."""
import json
import sys
from dataclasses import dataclass

import numpy as np
import pytest
import torch
from omegaconf import OmegaConf

from scripts import confirm_flash_ladder as flash
from src.life import build, spec
from src.life.evaluate import LifeDraw


@pytest.fixture(autouse=True)
def forbid_engine(monkeypatch):
    def forbidden(*args, **kwargs):
        raise AssertionError("test must not build or run the life engine")

    monkeypatch.setattr(build, "build", forbidden)
    monkeypatch.setattr(build, "run", forbidden)


@dataclass
class Dims:
    size: int = 1


class Layout:
    dims = Dims()

    def from_dict(self, value):
        return torch.tensor(value, dtype=torch.float32)

    def to_dict(self, value):
        return value.tolist()


def snapshot(generation=0, offset=0, archive=()):
    def group(values, ids):
        return dict(dims={"size": 1}, ids=list(ids), genomes=[[float(v)] for v in values])

    return dict(group(np.arange(32) + offset, range(32)), generation=generation,
                archive=group(archive, range(100, 100 + len(archive))))


def draw(lives=2):
    levels = (.5, .25, .1, 0.)
    worlds = tuple(spec.world("catch_speck_flash5_dim25_l4", visibility_low=b) for b in levels for _ in range(lives))
    names = tuple(f"flash{j}" for j in range(4) for _ in range(lives))
    return LifeDraw(tuple(range(4 * lives)), worlds, names)


def test_balanced_and_dark_roles_can_be_different_and_use_ids_for_final_ties():
    panel = draw()
    col = {"F": np.array([[9] * 8, [4] * 8, [4] * 8]),
           "low_light_captures": np.array([[100] * 4 + [0] * 4, [0] * 4 + [8] * 4, [0] * 4 + [8] * 4])}
    rows = [{"id": 9}, {"id": 8}, {"id": 2}]
    assert flash.choose(col, panel, rows) == {"balanced": 0, "dark_specialist": 2}
    col["F"][1] = 5
    assert flash.choose(col, panel, rows)["dark_specialist"] == 1


def test_population_combines_archive_exactly_deduplicates_and_keeps_smallest_id():
    payload = snapshot(archive=(3, 99))
    payload["archive"]["ids"][0] = -1
    genomes, rows = flash.population(payload, Layout())
    assert len(rows) == 33
    assert [r["id"] for r in rows if genomes[rows.index(r), 0] == 3] == [-1]
    assert rows[-1]["source"] == "archive" and genomes[-1, 0] == 99
    payload["archive"]["ids"][0] = 0
    with pytest.raises(ValueError, match="repeats a native ID"):
        flash.population(payload, Layout())


def test_final_snapshot_must_match_checkpoint_archive_and_order():
    payload = snapshot(120, archive=(99,))
    state = dict(population=torch.arange(32, dtype=torch.float32)[:, None], ids=torch.arange(32),
                 archive=torch.tensor([[99.]]), archive_ids=torch.tensor([100]))
    flash.verify_final_snapshot(payload, Layout(), state)
    payload["archive"]["genomes"][0] = [98.]
    with pytest.raises(ValueError, match="snapshot differs"):
        flash.verify_final_snapshot(payload, Layout(), state)


def test_pairing_uses_life_differences_and_specialist_both_hard_rungs():
    panel = draw()
    observations = {}
    noisy = np.arange(8.) * 1000
    for g in flash.STAGES:
        for role in flash.ROLES:
            observations[g, role] = {"low_light_captures": noisy + (g / 60 if role == "dark_specialist" else 0)}
    report = flash.summarize(observations, panel)
    estimate = report["paired"]["dark_specialist"]["g120_minus_g0"]["flash2"]["low_light_captures"]
    assert estimate == {"mean": 2., "se": 0., "n": 2}
    assert report["primary_founder_pass"]
    observations[120, "dark_specialist"]["low_light_captures"][-2:] = noisy[-2:]
    assert not flash.summarize(observations, panel)["primary_founder_pass"]


class MockEvaluator:
    abi = spec.V7

    def __init__(self, out):
        self.out, self.calls = out, []
        self.invalid = False

    def draw_tasks(self, purpose, index, tasks, lives):
        return draw(lives)

    def run(self, genomes, panel):
        if panel.n == 4 * flash.CONFIRMATION:
            frozen = json.loads((self.out / "confirmation" / "selection.json").read_text())
            assert len(frozen["choices"]) == 3
            assert all(set(roles) == set(flash.ROLES) for roles in frozen["choices"].values())
        self.calls.append((len(genomes), panel.n, panel.seeds))
        led = np.zeros((len(genomes) * panel.n, self.abi.LEDGER_SIZE), dtype=np.float64)
        values = np.repeat(genomes[:, 0].numpy(), panel.n)
        for key in ("F", "captures", "income", "cost", "n_end", "live_time"):
            led[:, self.abi.L[key]] = values
        led[:, self.abi.L["low_light_captures"]] = 100 - values
        led[:, self.abi.L["status"]] = int(self.invalid)
        return build.Lives(led, np.zeros((len(led), self.abi.HASH_SIZE), dtype=np.uint64), abi=self.abi)

    def columns(self, result, batch, panel):
        led = result.ledger.reshape(batch, panel.n, -1)
        col = {name: led[:, :, i] for name, i in self.abi.L.items()}
        col.update(window=np.ones((batch, panel.n)), extinct_charge=np.zeros((batch, panel.n)),
                   guard=np.zeros((batch, panel.n), dtype=bool), extinct=np.zeros((batch, panel.n), dtype=bool),
                   invalid=col["status"] != 0)
        return col


def test_full_mocked_tail_freezes_all_roles_resumes_and_rejects_changed_inputs(tmp_path):
    populations = tmp_path / "populations"
    populations.mkdir()
    for g in flash.STAGES:
        (populations / f"g{g:06d}.json").write_text(json.dumps(snapshot(g)))
    cfg = OmegaConf.create({"logging": {"output_dir": str(tmp_path)}, "life": {"training_tasks": []}})
    ev = MockEvaluator(tmp_path)
    report = flash.confirm(cfg, Layout(), ev, {"checkpoint": "fixed"})
    assert len(ev.calls) == 9 and report["lives"] == 24576
    assert all(ev.calls[i][2] == ev.calls[0][2] for i in range(3))
    assert all(ev.calls[i][2] == ev.calls[3][2] for i in range(3, 9))
    assert set(ev.calls[0][2]).isdisjoint(ev.calls[3][2])
    assert flash.confirm(cfg, Layout(), ev, {"checkpoint": "fixed"}) == report
    assert len(ev.calls) == 9
    # A changed snapshot invalidates the entire selection binding, even if chosen genomes would stay the same.
    path = populations / "g000060.json"
    path.write_text(json.dumps(snapshot(60, offset=1)))
    with pytest.raises(ValueError, match="cached input metadata differs"):
        flash.confirm(cfg, Layout(), ev, {"checkpoint": "fixed"})
    assert len(ev.calls) == 9


def test_raw_invalid_result_saved_before_rejection_and_never_repeated(tmp_path):
    ev = MockEvaluator(tmp_path)
    ev.invalid = True
    path = tmp_path / "invalid.npz"
    for _ in range(2):
        with pytest.raises(ValueError, match="invalid lives retained"):
            flash.cached_lives(path, ev, torch.tensor([[1.]]), draw(), {})
    assert path.exists() and len(ev.calls) == 1


def test_interrupted_call_is_not_automatically_retried(tmp_path):
    ev = MockEvaluator(tmp_path)
    path = tmp_path / "interrupted.npz"
    path.with_suffix(".pending.json").write_text("{}")
    with pytest.raises(RuntimeError, match="not automatic retry"):
        flash.cached_lives(path, ev, torch.tensor([[1.]]), draw(), {})
    assert ev.calls == []


def test_guard_extinction_and_production_f_are_preserved_as_outcomes():
    col = {k: np.array([[v, v]]) for k, v in {
        "captures": 0, "low_light_captures": 0, "misses": 1, "F": -5, "income": 0, "cost": 3,
        "n_end": 0, "extinct_charge": 2, "guard": 1, "extinct": 1, "live_time": 4, "window": 8}.items()}
    col["guard"] = col["guard"].astype(bool)
    col["extinct"] = col["extinct"].astype(bool)
    result = flash.metrics(col)
    assert result["F"].tolist() == [-5, -5]
    assert result["mean_cells"].tolist() == [.5, .5]
    assert result["guard"].all() and result["extinct"].all()
    assert result["guard"].dtype == result["extinct"].dtype == np.float64


@pytest.mark.parametrize("generation, expected_resume", [(None, False), (60, True), (120, None)])
def test_queue_resume_opt_in_fresh_partial_and_complete(tmp_path, monkeypatch, generation, expected_resume):
    from src import run

    cfg = OmegaConf.create({"logging": {"output_dir": str(tmp_path)}, "evolve": {"generations": 120}, "threads": 1})
    path = tmp_path / "checkpoint.pt"
    if generation is not None:
        path.write_bytes(b"checkpoint")
    (tmp_path / "populations").mkdir()
    (tmp_path / "populations" / "g000120.json").write_text("{}")
    saved = {"config": {}, "state": {"generation": generation}, "identity": {
        "sources": {}, "torch": str(torch.__version__), "numpy": np.__version__, "libm": {},
        "torch_cpu_capability": torch.backends.cpu.get_cpu_capability(),
        "torch_build": flash.digest(torch.__config__.show().encode())}}
    calls = []

    def train(config, *, resume):
        calls.append(resume)
        path.write_bytes(b"checkpoint")
        saved["state"]["generation"] = 120

    monkeypatch.setattr(run, "main", train)
    monkeypatch.setattr(flash, "load_config", lambda _: cfg)
    monkeypatch.setattr(flash.checkpoint, "load", lambda _: saved)
    monkeypatch.setattr(flash.checkpoint, "config_identity", lambda _: {})
    monkeypatch.setattr(flash.checkpoint, "libm_identity", lambda: {})
    monkeypatch.setattr(flash, "setup", lambda _: (None, None, None, None))
    monkeypatch.setattr(flash, "verify_final_snapshot", lambda *args: None)
    monkeypatch.setattr(flash, "confirm", lambda *args: dict(status="complete", lives=0, primary_founder_pass=False))
    monkeypatch.setattr(sys, "argv", ["confirm", "--config", "resolved.yaml", "--train", "--resume-if-present"])
    flash.main()
    assert calls == ([] if expected_resume is None else [expected_resume])
