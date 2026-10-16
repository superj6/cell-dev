"""Resume is a continuation of the same search, including RNGs, rechecks and diagnostic schedules."""
import json
import os
import subprocess
import sys
from pathlib import Path

import pytest
import torch

from src import checkpoint
from src.common import load_config

ROOT = Path(__file__).resolve().parents[1]
TIMES = {"t_gen", "t_eval", "t_recheck", "wall_s", "final_s", "elapsed"}


def clean(value):
    if isinstance(value, dict):
        return {k: clean(v) for k, v in value.items() if k not in TIMES}
    if isinstance(value, list):
        return [clean(v) for v in value]
    return value


def canonical_log(path):
    return "".join(json.dumps(clean(json.loads(line))) + "\n" for line in path.read_text().splitlines()).encode()


@pytest.mark.parametrize("catch,override_world,abi_version", [
    (False, None, None), (True, None, None),
    (True, "catch_speck_flash5_dim25_l4", 4), (True, "catch_speck_blink20_20_l4", 4),
    (True, "catch_delayed_match_l4", 5),
], ids=["bell", "catch", "flash", "renewal", "delayed_match"])
def test_three_plus_resume_three_equals_six_bytes(tmp_path, catch, override_world, abi_version):
    config = "configs/life_speck.yaml" if catch else "configs/life_smoke.yaml"
    opts = ["threads=1", "seed=45000123", "evolve.generations=6", "evolve.mu=4", "evolve.lam=6",
            "evolve.founders=2", "evolve.init_samples=8", "evolve.max_init_samples=16",
            "evolve.recheck_k=6", "evolve.recheck_lives=1", "evolve.heldout_every=4",
            "evolve.dup_rate=0.4", "evolve.del_rate=0.2", "logging.checkpoint_every=2",
            "life.T=32", "life.T_choices=[24,32,48]", "life.founder_T=24", "life.founder_lives=1",
            "life.lives=1", "life.valid_lives=1", "life.heldout_lives=1", "life.heldout=[]",
            "life.final_lives=2", "life.final_top=2", "life.final_fork_lives=1", "life.phase_lives=1",
            "life.size_curve=[]", "clones.every=4", "clones.lives=1", "clones.top=1", "clones.times=[0.5]",
            "clones.conditions=[contacts_off]", "world.n_max=48"]
    if catch:
        opts += ["evolve.breeding=asex", "evolve.random_ties=false"]
    if override_world is not None:
        opts += [f"life.abi={abi_version}", f"life.world={override_world}"]
    if abi_version == 5:
        # Exercise SAMPLE/BLANK/CHOICE/timeout cycles within these short determinism fixtures.
        opts += ["world.sample_min=2", "world.sample_max=3", "world.blank_min=3", "world.blank_max=4",
                 "world.choice_T=4", "world.reset_T=1"]
    full, split = tmp_path / "full" / "run", tmp_path / "split" / "run"

    def run(out, *flags):
        env = dict(os.environ, ATEN_CPU_CAPABILITY="avx2", OMP_WAIT_POLICY="PASSIVE")
        cmd = [sys.executable, "-m", "src.run", "--config", config, *flags, *opts, f"logging.output_dir={out}"]
        done = subprocess.run(cmd, cwd=ROOT, env=env, capture_output=True, text=True, timeout=120)
        assert done.returncode == 0, done.stdout + done.stderr

    run(full)
    run(split, "--stop-after", "3")
    mid = checkpoint.load(split / "checkpoint.pt")
    assert mid["state"]["generation"] == 3
    if override_world is not None:
        assert mid["config"]["life"]["abi"] == abi_version
        assert mid["config"]["life"]["world"] == override_world
    assert not (split / "results.jsonl").exists()
    # A crash can leave complete or partial records after the checkpoint. Resume discards only that tail.
    for name in checkpoint.LOGS:
        with (split / name).open("a") as fh:
            fh.write('{"interrupted":')
    run(split, "--resume")
    for name in (*checkpoint.LOGS, "results.jsonl"):
        assert canonical_log(full / name) == canonical_log(split / name), name
    for name in ("population.json", "best_genome.json", "determinism.json"):
        assert (full / name).read_bytes() == (split / name).read_bytes(), name
    if abi_version == 5:
        assert json.loads((full / "results.jsonl").read_text())["abi"] == 5
    a, b = (checkpoint.load(p / "checkpoint.pt")["state"] for p in (full, split))
    assert a.keys() == b.keys()
    for key in a:
        if isinstance(a[key], torch.Tensor):
            assert a[key].numpy().tobytes() == b[key].numpy().tobytes(), key
        elif key not in TIMES:
            assert clean(a[key]) == clean(b[key]), key
    # A completed checkpoint can replay final scoring without repeating a generation or a founder row.
    before = {name: (split / name).read_bytes() for name in checkpoint.LOGS}
    run(split, "--resume")
    assert before == {name: (split / name).read_bytes() for name in checkpoint.LOGS}


def test_log_restore_verifies_every_prefix_before_truncation(tmp_path):
    for name in checkpoint.LOGS:
        (tmp_path / name).write_text("original\n")
    offsets = checkpoint.log_offsets(tmp_path)
    (tmp_path / checkpoint.LOGS[0]).write_text("original\nextra")
    (tmp_path / checkpoint.LOGS[-1]).write_text("tampered\n")
    with pytest.raises(ValueError, match="prefix differs"):
        checkpoint.restore_logs(tmp_path, offsets)
    assert (tmp_path / checkpoint.LOGS[0]).read_text() == "original\nextra"


def test_resume_refuses_changed_search_or_numerical_pins():
    cfg = load_config("configs/life_smoke.yaml")
    saved = {"config": checkpoint.config_identity(cfg), "identity": {"torch": "pinned", "golden": "known"}}
    checkpoint.validate(saved, cfg, saved["identity"])
    for identity in ({"torch": "other", "golden": "known"}, {"torch": "pinned", "golden": "wrong"}):
        with pytest.raises(ValueError, match="determinism pins differ"):
            checkpoint.validate(saved, cfg, identity)
    cfg.evolve.generations += 1
    with pytest.raises(ValueError, match="configuration differs"):
        checkpoint.validate(saved, cfg, saved["identity"])
