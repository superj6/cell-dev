"""Frozen-role target-signal diagnostic; --prepare reads saved data, --lineage runs one owned job."""
# ruff: noqa: E402
import argparse
import hashlib
import json
import os
import shutil
import subprocess
import sys
from dataclasses import replace
from pathlib import Path

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[1]
OLD = ROOT / "outputs/flash_ladder_20261017"
CHECKOUT = OLD / "checkout"
REVISION = "54c531026528b824bae7d670c3092ffe7abc9d39"
NAMES = ("AO_s7", "D90_Z_s5", "speck_s6", "speck_s8")
sys.path.insert(0, str(CHECKOUT))
import numpy as np
import torch
from omegaconf import OmegaConf

from scripts.confirm_flash_ladder import cached_lives, describe, metrics, write_json
from src import checkpoint
from src.evolve import setup
from src.life import build, spec
from src.life.evaluate import LifeDraw


def read(path):
    return json.loads(Path(path).read_bytes())


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def prepare():
    assert not (HERE / "manifest.json").exists(), "preparation already frozen"
    torch.set_num_threads(2)
    assert subprocess.check_output(["git", "-C", str(CHECKOUT), "rev-parse", "HEAD"], text=True).strip() == REVISION
    files, cases, identity = {}, {}, None
    for name in NAMES:
        base = OLD / "runs" / name
        chosen, summary = read(base / "confirmation/selection.json"), read(base / "confirmation/summary.json")
        binding = chosen["binding"]
        assert summary["status"] == "complete" and summary["binding"] == binding
        assert summary["selection_sha256"] == sha(base / "confirmation/selection.json")
        identity = identity or binding["identity"]
        assert identity == binding["identity"]
        assert binding["script_sha256"] == sha(CHECKOUT / "scripts/confirm_flash_ladder.py")
        cfg = OmegaConf.create(binding["config"])
        _, layout, _, _ = setup(cfg)
        pins = {base / "checkpoint.pt": binding["checkpoint_sha256"],
                base / "confirmation/selection.json": summary["selection_sha256"],
                base / "confirmation/summary.json": sha(base / "confirmation/summary.json")}
        stages = {}
        for stage in (0, 120):
            role = chosen["choices"][str(stage)]["dark_specialist"]
            snapshot = base / "populations" / f"g{stage:06d}.json"
            pins[snapshot] = binding["snapshots"][str(stage)]
            snap = read(snapshot)
            group = snap if role["source"] == "current" else snap["archive"]
            assert group["genomes"][group["ids"].index(role["id"])] == role["genome"]
            genome = layout.from_dict(role["genome"]).numpy()
            assert hashlib.sha256(genome.tobytes()).hexdigest() == role["genome_sha256"]
            raw = base / "confirmation" / f"confirmation_g{stage:03d}_dark_specialist.npz"
            pins[raw] = next(r["sha256"] for r in summary["raw"] if r["path"] == raw.name)
            with np.load(raw, allow_pickle=False) as saved:
                meta = json.loads(str(saved["metadata"]))
                assert saved["ledger"].shape == (2048, 143) and saved["hashes"].shape == (2048, 5)
            assert meta["binding"] == dict(binding, selection_sha256=summary["selection_sha256"])
            assert meta["genomes"] == role["genome_sha256"] and meta["shape"] == [1, layout.size]
            mask = [i for i, task in enumerate(meta["tasks"]) if task == "flash00"]
            seeds = [meta["seeds"][i] for i in mask]
            world = meta["worlds"]["flash00"]
            assert len(mask) == len(set(seeds)) == 512
            assert world["visibility_low"] == 0 and world["visibility_on"] == 5 and world["lam_s"] == 2
            assert world["lam_bg"] == .05 and world["b2_amp"] == world["task_mode"] == world["patch_count"] == 0
            stages[str(stage)] = dict(role=role, raw=str(raw), rows=mask, seeds=seeds, world=world)
        assert stages["0"]["seeds"] == stages["120"]["seeds"]
        assert stages["0"]["world"] == stages["120"]["world"]
        cases[name] = dict(config=binding["config"], stages=stages)
        for path, expected in pins.items():
            assert sha(path) == expected, str(path)
            files[str(path)] = expected
    reference = cases[NAMES[0]]["stages"]["0"]
    assert all(c["stages"]["0"][k] == reference[k] for c in cases.values() for k in ("seeds", "world"))
    source_pins = {str(CHECKOUT / p): h for p, h in identity["sources"].items()}
    source_pins[str(CHECKOUT / "scripts/confirm_flash_ladder.py")] = binding["script_sha256"]
    source_pins[str(CHECKOUT / "scripts/run_local_queue.py")] = sha(CHECKOUT / "scripts/run_local_queue.py")
    for path, expected in source_pins.items():
        assert sha(path) == expected, path
    for fast in (False, True):
        key = hashlib.sha256(build.SRC.read_bytes() + " ".join(build.flags(fast)).encode()).hexdigest()[:16]
        source = OLD / "build-cache/life" / f"life_{key}.so"
        assert sha(source) == identity["kernels"][str(fast)]
        dest = HERE / "build-cache/life" / source.name
        dest.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(source, dest)
        files[str(dest)] = sha(dest)
    (HERE / "tmp").mkdir(exist_ok=True)
    protocol = dict(source_commit=REVISION, checkout=str(CHECKOUT), identity=identity, cases=cases,
                    new_lives=4096, reused_normal_lives=4096, lives_per_role=512,
                    role="frozen dark_specialist", stages=[0, 120], intervention={"lam_s": 0.0},
                    estimand="(g120 normal-off)-(g0 normal-off), paired by whole-life seed",
                    caveat="Revealed confirmation panel; not fresh. Background rate remains .05, but candidate "
                           "bound changes from2.05 to0.05, so events differ. No isolated memory/spatial-decoding claim.")
    write_json(HERE / "protocol.json", protocol)
    jobs = dict(max_workers=4, cpu_seconds=1800, wall_seconds=900, rss_bytes=8 * 2**30,
                minimum_available_bytes=4 * 2**30, jobs=[dict(id=n, cwd=str(CHECKOUT), output=str(HERE / "runs" / n),
                argv=["/usr/bin/env", "ATEN_CPU_CAPABILITY=avx2", f"CELL_DEV_CACHE={HERE / 'build-cache'}",
                      f"TMPDIR={HERE / 'tmp'}", "PYTHONHASHSEED=0", "PYTHONDONTWRITEBYTECODE=1",
                      str(ROOT / ".venv/bin/python"), "-u", str(Path(__file__)), "--lineage", n]) for n in NAMES])
    write_json(HERE / "jobs.json", jobs)
    for path in (Path(__file__), HERE / "protocol.json", HERE / "jobs.json"):
        files[str(path)] = sha(path)
    write_json(HERE / "manifest.json", dict(status="prepared_not_launched", files=files, source_pins=source_pins))


def run(name):
    manifest = read(HERE / "manifest.json")
    for path, expected in (manifest["files"] | manifest["source_pins"]).items():
        assert sha(path) == expected, path
    protocol = read(HERE / "protocol.json")
    case, identity = protocol["cases"][name], protocol["identity"]
    assert str(torch.__version__) == identity["torch"] and np.__version__ == identity["numpy"]
    assert torch.backends.cpu.get_cpu_capability() == identity["torch_cpu_capability"]
    assert hashlib.sha256(torch.__config__.show().encode()).hexdigest() == identity["torch_build"]
    assert checkpoint.libm_identity() == identity["libm"]
    assert sha(build.library_path(True)) == identity["kernels"]["True"]  # exists: never invoke a build/golden life
    out = HERE / "runs" / name
    assert os.environ.get("CELLDEV_JOB_OUTPUT") == str(out), "use the owned queue"
    out.mkdir(parents=True, exist_ok=True)
    torch.set_num_threads(2)
    cfg = OmegaConf.create(case["config"])
    _, layout, _, ev = setup(cfg)
    observations, outputs, called = {}, {}, 0
    for stage, row in case["stages"].items():
        world = spec.World(**row["world"])
        draw = LifeDraw(tuple(row["seeds"]), (world,) * 512, ("flash00",) * 512)
        with np.load(row["raw"], allow_pickle=False) as saved:
            native = build.Lives(saved["ledger"][row["rows"]].copy(), saved["hashes"][row["rows"]].copy(), abi=ev.abi)
        normal = ev.columns(native, 1, draw)
        assert not normal["invalid"].any()
        genome = layout.from_dict(row["role"]["genome"])[None, :]
        path = out / f"signal_off_g{int(stage):03d}.npz"
        called += 0 if path.exists() else 512
        off = cached_lives(path, ev, genome, replace(draw, worlds=(replace(world, lam_s=0.),) * 512),
                           dict(protocol_sha256=sha(HERE / "protocol.json"), lineage=name, stage=stage))
        outputs[path.name] = sha(path)
        for condition, col in (("normal", normal), ("off", off)):
            values = metrics(col)
            values["clicks"] = col["captures"][0] + col["misses"][0]  # one-target CATCH, no second blob
            observations[f"g{stage}_{condition}"] = values
    pairs = {"cue_g0": ("g0_normal", "g0_off"), "cue_g120": ("g120_normal", "g120_off"),
             "normal_gain": ("g120_normal", "g0_normal"), "off_gain": ("g120_off", "g0_off")}
    differences = {label: {k: observations[a][k] - observations[b][k] for k in observations[a]}
                   for label, (a, b) in pairs.items()}
    differences["cue_gain_interaction"] = {k: differences["cue_g120"][k] - differences["cue_g0"][k]
                                           for k in differences["cue_g0"]}
    def summarize(rows):
        return {label: {k: describe(v) for k, v in values.items()} for label, values in rows.items()}
    write_json(out / "summary.json", dict(status="complete", lineage=name, protocol_sha256=sha(HERE / "protocol.json"),
               native_lives_this_invocation=called, distinct_signal_off_lives=1024, raw=outputs,
               absolute=summarize(observations), paired=summarize(differences), caveat=protocol["caveat"]))


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    group = parser.add_mutually_exclusive_group(required=True)
    group.add_argument("--prepare", action="store_true")
    group.add_argument("--lineage", choices=NAMES)
    args = parser.parse_args()
    prepare() if args.prepare else run(args.lineage)
