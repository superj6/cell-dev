"""Build the standalone two-genome watch page without running any lives.

From repository root: .venv/bin/python outputs/autonomous_followthrough_20261013/watch/build_watch.py
The existing browser engine is embedded unchanged; inputs are verified against the public archive.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import os
import shutil
import sys
from pathlib import Path

os.environ.setdefault("ATEN_CPU_CAPABILITY", "avx2")
ROOT = next(path for path in Path(__file__).resolve().parents if (path / "src/life/spec.py").exists())
sys.path.insert(0, str(ROOT))

from src.genome import Layout  # noqa: E402
from src.life import spec  # noqa: E402

HERE = Path(__file__).resolve().parent
ARCHIVE = ROOT / "results/pool_mutants_20261013"
ENGINE = ROOT / "results/atlas/play/lifesim.js"
DEFAULT_SEED = 51_840_000


def digest(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--out", type=Path, default=HERE)
    args = parser.parse_args()
    args.out.mkdir(parents=True, exist_ok=True)
    archive = json.loads((ARCHIVE / "provenance.json").read_text())
    bodies, inputs = [], {}
    for role, relative in (("parent", "parents/s5/best_genome.json"),
                           ("descendant", "genomes/s5_pool_winner.json")):
        path = ARCHIVE / relative
        inputs[relative] = digest(path)
        if inputs[relative] != archive["artifacts"][relative]["sha256"]:
            raise ValueError(f"archived input changed: {relative}")
        _, genome = Layout.load(str(path))
        raw = genome.reshape(-1).float().numpy()
        packed = spec.V3.pack_genomes(raw[None], "hexprism")[0]
        bodies.append({"name": role, "mode": "grn", "genome": packed.tolist(),
                       "raw_sha256": hashlib.sha256(raw.tobytes()).hexdigest()})
    if bodies[1]["raw_sha256"] != "6d79248a5bb82c49aa4278ccd755234b7952a09d9af4873b7a4ad303d3654f92":
        raise ValueError("descendant is not the already-frozen s5 row-38 genotype")
    worlds = {}
    for name in ("base", "pool"):
        overrides = {"sigma": 0.4, "lam_s": 4.0} if name == "pool" else {}
        world = spec.world("catch_speck_l4", T=1024, d0=0.5, d_min=0.25, **overrides)
        worlds[name] = {key: float(getattr(world, key)) for key in spec.V3.WORLD_KEYS}
    data = {"bodies": bodies, "worlds": worlds, "default_seed": DEFAULT_SEED,
            "status_bits": dict(spec.STATUS), "engine_sha256": digest(ENGINE)}
    engine = ENGINE.read_text()
    if "</script" in engine.lower() or "<!--" in engine:
        raise ValueError("engine cannot safely be embedded without alteration")
    data_text = json.dumps(data, separators=(",", ":")).replace("</", "<\\/")
    template = (HERE / "watch.template.html").read_text()
    page = template.replace("__WATCH_DATA__", data_text).replace("__LIFESIM_ENGINE__", engine)
    (args.out / "bodies.json").write_text(json.dumps(data, indent=2) + "\n")
    (args.out / "watch.html").write_text(page)
    shutil.copyfile(ENGINE.parent / "COPYING.LGPL-2.1", args.out / "COPYING.LGPL-2.1")
    provenance = {"format": 1, "purpose": "illustrative single lives, never used to select a genome",
                  "default_seed": DEFAULT_SEED, "T": 1024, "default_world": "pool",
                  "inputs": inputs, "engine_sha256": digest(ENGINE), "engine_modified": False,
                  "builder_sha256": digest(Path(__file__)), "template_sha256": digest(HERE / "watch.template.html"),
                  "genome_raw_sha256": {body["name"]: body["raw_sha256"] for body in bodies},
                  "worlds": worlds, "html_sha256": digest(args.out / "watch.html"),
                  "bytes": (args.out / "watch.html").stat().st_size}
    (args.out / "provenance.json").write_text(json.dumps(provenance, indent=2) + "\n")
    print(json.dumps({"out": str(args.out / "watch.html"), "bytes": provenance["bytes"],
                      "engine_modified": False, "default_seed": DEFAULT_SEED}, indent=2))


if __name__ == "__main__":
    main()
