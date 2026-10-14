"""Prepare fixed continuation configs and verify seeds without running any life."""
from __future__ import annotations

import hashlib
import json
import os
import sys
from pathlib import Path

os.environ.setdefault("ATEN_CPU_CAPABILITY", "avx2")
ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))

from omegaconf import OmegaConf  # noqa: E402

from src.common import load_config  # noqa: E402
from src.genome import Layout  # noqa: E402
from src.life.evaluate import LifeEvaluator, life_seed  # noqa: E402

STUDY = Path(__file__).resolve().parent
ARCHIVE = ROOT / "results/pool_mutants_20261013"
RUN_SEEDS = (51089, 51090)
CONFIRM_SEEDS = list(range(51_910_000, 51_910_256))


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def run_life_seeds(run_seed):
    out = []
    for generation in range(16):
        out.extend(life_seed(run_seed, "gen", generation, j) for j in range(7))
        if generation % 4 == 0 or generation == 15:
            out.extend(life_seed(run_seed, "valid", generation, j) for j in range(16))
    for index in (0, 1):
        out.extend(life_seed(run_seed, "final", index, j) for j in range(2))
    return out


def pilot_life_seeds():
    out = set()
    for run in range(10):
        for generation in range(500):
            out.update(life_seed(run, "gen", generation, j) for j in range(7))
            if generation % 10 == 0 or generation == 499:
                for purpose, lives in (("valid", 16), ("heldout", 24), ("clones", 3)):
                    out.update(life_seed(run, purpose, generation, j) for j in range(lives))
        for index in range(16):
            out.update(life_seed(run, "founders", index, j) for j in range(2))
        for index in (0, 1):
            out.update(life_seed(run, "final", index, j) for j in range(64))
        out.update(life_seed(run, "sizecurve", 0, j) for j in range(16))
    return out


def main():
    provenance = json.loads((ARCHIVE / "provenance.json").read_text())
    founder_source = ARCHIVE / "genomes/s5_pool_winner.json"
    pilot_source = ARCHIVE / "parents/s5/best_genome.json"
    for path in (founder_source, pilot_source):
        if sha(path) != provenance["artifacts"][str(path.relative_to(ARCHIVE))]["sha256"]:
            raise ValueError("archived genome bytes differ")
    inputs = STUDY / "inputs"
    inputs.mkdir(parents=True, exist_ok=True)
    founder, pilot = inputs / "founder_row38.json", inputs / "pilot_s5.json"
    founder.write_bytes(founder_source.read_bytes())
    pilot.write_bytes(pilot_source.read_bytes())
    sources = {str(path.relative_to(ROOT)): sha(path) for path in sorted((ROOT / "src").rglob("*.py"))}
    sources["src/life/kernel.c"] = sha(ROOT / "src/life/kernel.c")
    if sources != provenance["numerical_identity"]["sources"]:
        raise ValueError("engine or search source differs from the measured archive")
    layout, genome = Layout.load(founder)
    founder_raw_sha = hashlib.sha256(genome.numpy().tobytes()).hexdigest()
    configs, seeds, lengths = {}, {}, {}
    for run_seed in RUN_SEEDS:
        cfg = load_config(str(ROOT / "configs/life_speck.yaml"))
        cfg.pop("extends", None)
        cfg.seed, cfg.threads = run_seed, 2
        cfg.evolve.generations = 16
        cfg.evolve.seed_genome = str(founder.relative_to(ROOT))
        cfg.evolve.heldout_every = 4
        cfg.evolve.random_ties = True
        cfg.life.fast_kernel = True
        cfg.life.control = "pool_row38_continuation"
        cfg.life.valid_lives, cfg.life.heldout = 16, []
        cfg.life.final_top, cfg.life.final_lives, cfg.life.final_fork_lives = 1, 2, 0
        cfg.life.size_curve = []
        cfg.clones.every, cfg.clones.conditions = 0, []
        cfg.envelope = {"enabled": False}
        cfg.world = {"d0": 0.5, "d_min": 0.25, "sigma": 0.4, "lam_s": 4.0}
        cfg.logging.output_dir = str(STUDY / f"runs/s{run_seed}")
        cfg.logging.checkpoint_every, cfg.logging.lineage = 4, "all"
        ev = LifeEvaluator(cfg, layout)
        assert ev.fast and not ev.has_envelope and ev.T_choices == (768, 1024, 1536)
        assert cfg.evolve.mu == 32 and cfg.evolve.lam == 224 and cfg.life.lives == 3
        assert cfg.evolve.recheck_k == 64 and cfg.evolve.recheck_lives == 4 and cfg.evolve.recheck_key == "all"
        assert cfg.evolve.breeding == "sex" and cfg.evolve.n_mut == 2
        assert cfg.evolve.dup_rate == cfg.evolve.del_rate == 0 and cfg.life.extinct_charge
        out = STUDY / f"configs/s{run_seed}.yaml"
        out.parent.mkdir(parents=True, exist_ok=True)
        OmegaConf.save(cfg, out, resolve=True)
        configs[str(run_seed)] = {"path": str(out.relative_to(ROOT)), "sha256": sha(out)}
        seeds[str(run_seed)] = run_life_seeds(run_seed)
        lengths[str(run_seed)] = [ev.draw("gen", g).worlds[0].T for g in range(16)]
    combined = [value for these in seeds.values() for value in these]
    old = pilot_life_seeds()
    assert len(combined) == len(set(combined)) == 392
    assert not set(combined).intersection(old)
    assert not any(51_000_000 <= seed < 52_000_000 for seed in combined)
    assert not set(CONFIRM_SEEDS).intersection(old)
    # Check the full reserved decimal block range, not just the immediately preceding experiments.
    audit = {"run_life_seeds": seeds, "confirm_seeds": CONFIRM_SEEDS, "old_pilot_unique_seeds_checked": len(old),
             "run_seeds_unique_and_cross_run_disjoint": True, "old_pilot_overlap": 0,
             "run_seed_overlap_reserved_decimal_51M_blocks_0_to_99": 0,
             "confirm_block": 91, "confirm_cross_duration_seeds_intentionally_shared": True,
             "half_final_seeds_intentionally_reuse_final0": True}
    (STUDY / "seed_audit.json").write_text(json.dumps(audit, indent=2) + "\n")
    protocol = {"status": "prepared_not_started", "runs": list(RUN_SEEDS), "generations": 16,
                "configs": configs, "founder_file": str(founder.relative_to(ROOT)), "founder_sha256": sha(founder),
                "founder_raw_sha256": founder_raw_sha, "pilot_file": str(pilot.relative_to(ROOT)),
                "pilot_sha256": sha(pilot), "archive_provenance_sha256": sha(ARCHIVE / "provenance.json"),
                "input_sources": {"founder": str(founder_source.relative_to(ROOT)),
                                  "pilot": str(pilot_source.relative_to(ROOT))},
                "source_identity": sources, "expected_numerical_identity": provenance["numerical_identity"],
                "selection_durations": lengths, "selection_genome_lives": 32768,
                "selection_T1024_equivalent_lives": sum(map(sum, lengths.values())),
                "periodic_valid_genome_lives": 160, "tiny_final_genome_lives": 12,
                "tiny_final_half_duration_lives": 4, "confirmation_genome_lives": 3072,
                "planned_genome_lives": 36012, "max_cpu_seconds": 10800, "max_simulation_threads": 4,
                "seed_audit_sha256": sha(STUDY / "seed_audit.json"),
                "prepare_sha256": sha(Path(__file__)),
                "initialization": "One exact row38 founder plus 31 ordinary point-mutated copies; "
                                  "then ordinary 32+224 sexual evolution, no guaranteed founder preservation.",
                "population_loading": "population.json initialization is unsupported; exact resume uses checkpoint.pt."}
    (STUDY / "protocol.json").write_text(json.dumps(protocol, indent=2) + "\n")
    print(json.dumps({key: protocol[key] for key in ("status", "planned_genome_lives", "selection_durations",
                                                    "selection_T1024_equivalent_lives", "max_cpu_seconds")}, indent=2))


if __name__ == "__main__":
    main()
