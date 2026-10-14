"""Build the four-genome continuation viewer without simulating any lives.

The embedded engine is unchanged. Scientific input hashes are checked against the
completed continuation archive; viewer provenance stays separate from that archive.
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
sys.dont_write_bytecode = True
ROOT = next(path for path in Path(__file__).resolve().parents if (path / "src/life/spec.py").exists())
sys.path.insert(0, str(ROOT))

from src.genome import Layout  # noqa: E402
from src.life import spec  # noqa: E402

HERE = Path(__file__).resolve().parent
ARCHIVE = ROOT / "results/s7_continuation_20261014"
PRIOR = ROOT / "results/continuation_20261013"
ENGINE = ROOT / "results/continuation_20261013/viewer/lifesim.js"
DEFAULT_SEED = 51_840_000
GENOMES = (
    ("pilot_s7", "inputs/pilot_s7.json", "Original s7", "Pilot genome", "Original"),
    ("founder_row29", "inputs/founder_row29.json", "First-step founder", "Confirmed s7 row 29", "Founder"),
    ("s51891_final_rank0", "runs/s51891/best_genome.json", "Continuation 51891", "Final rank 0 · 16 generations",
     "16 generations"),
    ("s51892_final_rank0", "runs/s51892/best_genome.json", "Continuation 51892", "Final rank 0 · 16 generations",
     "16 generations"),
)


def digest(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def write_json(path, data):
    path.write_text(json.dumps(data, indent=2, allow_nan=False) + "\n")


def verify_input(relative, archive):
    path = ARCHIVE / relative
    if digest(path) != archive["artifacts"][relative]["sha256"]:
        raise ValueError(f"archived scientific input changed: {relative}")
    return path


def comparison_values(summary):
    """Keep the actual paired uncertainty and reverse signs when the UI swaps sides."""
    result = {}
    for left, *_ in GENOMES:
        result[left] = {}
        for right, *_ in GENOMES:
            if left == right:
                result[left][right] = {"mean": 0.0, "se": 0.0, "n": 256}
                continue
            key, sign = right + "__vs__" + left, 1
            if key not in summary:
                key, sign = left + "__vs__" + right, -1
            value = summary[key]["F"]
            result[left][right] = {**value, "mean": sign * value["mean"]}
    return result


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--out", type=Path, default=HERE)
    parser.add_argument("--publish", action="store_true", help="Copy the viewer with its own provenance to results")
    args = parser.parse_args()
    args.out.mkdir(parents=True, exist_ok=True)
    archive = json.loads((ARCHIVE / "provenance.json").read_text())
    prior_data = json.loads((PRIOR / "viewer/bodies.json").read_text())
    if digest(ENGINE) != prior_data["engine_sha256"]:
        raise ValueError("engine changed since the previously validated watch page")
    engine = ENGINE.read_text()
    if "</script" in engine.lower() or "<!--" in engine:
        raise ValueError("engine cannot safely be embedded unchanged")
    prior_page = (PRIOR / "watch.html").read_text()
    if "<script>" + engine + "</script>" not in prior_page:
        raise ValueError("the existing watch page embeds a different engine")
    bodies, inputs = [], {}
    for name, relative, title, subtitle, tag in GENOMES:
        path = verify_input(relative, archive)
        inputs[relative] = digest(path)
        _, genome = Layout.load(str(path))
        raw = genome.reshape(-1).float().numpy()
        packed = spec.V3.pack_genomes(raw[None], "hexprism")[0]
        bodies.append({"name": name, "title": title, "subtitle": subtitle, "tag": tag,
                       "mode": "grn", "genome": packed.tolist(),
                       "raw_sha256": hashlib.sha256(raw.tobytes()).hexdigest()})
    summary = json.loads(verify_input("summary.json", archive).read_text())
    manifest = json.loads(verify_input("confirmation/manifest.json", archive).read_text())
    for body in bodies:
        if body["raw_sha256"] != manifest["genotype_sha256"][body["name"]]:
            raise ValueError("viewer genome differs from the independently confirmed genotype")
    worlds = {}
    for name in ("base", "pool"):
        overrides = {"sigma": 0.4, "lam_s": 4.0} if name == "pool" else {}
        world = spec.world("catch_speck_l4", T=1024, d0=0.5, d_min=0.25, **overrides)
        worlds[name] = {key: float(getattr(world, key)) for key in spec.V3.WORLD_KEYS}
        if worlds[name] != prior_data["worlds"][name]:
            raise ValueError("world differs from the existing watch page")
    data = {"bodies": bodies, "worlds": worlds, "default_seed": DEFAULT_SEED,
            "default_pair": ["founder_row29", "s51891_final_rank0"],
            "status_bits": dict(spec.STATUS), "engine_sha256": digest(ENGINE),
            "paired_duration_effects": comparison_values(summary["confirmation"]["duration_average"])}
    data_text = json.dumps(data, separators=(",", ":")).replace("</", "<\\/")
    template = (HERE / "watch.template.html").read_text()
    page = template.replace("__WATCH_DATA__", data_text).replace("__LIFESIM_ENGINE__", engine)
    write_json(args.out / "bodies.json", data)
    (args.out / "watch.html").write_text(page)
    for name in ("lifesim.js", "COPYING.LGPL-2.1"):
        shutil.copyfile(ENGINE.parent / name, args.out / name)
    provenance = {"format": 1, "purpose": "Illustrative lives; never used for endpoint or seed selection",
                  "default_seed": DEFAULT_SEED, "T": 1024, "default_world": "pool",
                  "default_pair": data["default_pair"], "inputs": inputs,
                  "scientific_archive_provenance_sha256": digest(ARCHIVE / "provenance.json"),
                  "scientific_summary_sha256": digest(ARCHIVE / "summary.json"),
                  "engine_sha256": digest(ENGINE), "engine_modified": False,
                  "builder_sha256": digest(Path(__file__)), "template_sha256": digest(HERE / "watch.template.html"),
                  "genome_raw_sha256": {body["name"]: body["raw_sha256"] for body in bodies},
                  "worlds": worlds, "html_sha256": digest(args.out / "watch.html"),
                  "scientific_lives_run_by_builder": 0, "parity_validation": "pending explicit worker release"}
    if (HERE / "validation.json").exists():
        validation = json.loads((HERE / "validation.json").read_text())
        if (validation["html_sha256"] != provenance["html_sha256"]
                or validation["engine_sha256"] != provenance["engine_sha256"]):
            raise ValueError("completed parity belongs to different viewer bytes")
        provenance["parity_validation"] = "passed eight T32 cases in both C and embedded JS"
        provenance["validation_sha256"] = digest(HERE / "validation.json")
    write_json(args.out / "provenance.json", provenance)
    if args.publish:
        target = ARCHIVE / "viewer"
        target.mkdir(parents=True, exist_ok=True)
        shutil.copyfile(args.out / "watch.html", ARCHIVE / "watch.html")
        for name in ("bodies.json", "lifesim.js", "COPYING.LGPL-2.1", "provenance.json"):
            shutil.copyfile(args.out / name, target / name)
        for name in ("build_watch.py", "watch.template.html", "test_watch.js", "validate_watch.py",
                     "verify_parity.js", "README.md", "parity_plan.json", "ui_validation.json",
                     "truth_T32.json", "parity_budget.json", "validation.json"):
            if (HERE / name).exists():
                shutil.copyfile(HERE / name, target / name)
        published = json.loads((target / "provenance.json").read_text())
        published["artifacts"] = {str(p.relative_to(target)): {"sha256": digest(p), "bytes": p.stat().st_size}
                                  for p in sorted(target.iterdir()) if p.is_file() and p.name != "provenance.json"}
        published["html_path"] = "../watch.html"
        write_json(target / "provenance.json", published)
    print(json.dumps({"out": str(args.out / "watch.html"), "engine_modified": False,
                      "default_seed": DEFAULT_SEED, "genomes": [b["name"] for b in bodies],
                      "published": args.publish, "scientific_lives_run": 0}, indent=2))


if __name__ == "__main__":
    main()
