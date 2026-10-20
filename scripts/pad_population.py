"""Pad a saved population snapshot to a later genome layout (OPEN_WORLDS.md 6.6: founders padded to ABI 8).

    python -m scripts.pad_population SNAPSHOT OUT_PREFIX [--dims abi8]

SNAPSHOT is a ``populations/gNNNNNN.json`` file (current rows plus ``archive``) or a plain population file. Writes
``OUT_PREFIX_population.json`` and, if the snapshot has one, ``OUT_PREFIX_archive.json``, in the format that
``evolve.seed_population`` / ``evolve.seed_archive`` load. Every new entry is 0 (``LifeLayout.pad``): the padded
genomes grow and behave exactly as before and start blind to the new senses. IDs, breeds and origins are kept;
fitness is dropped, since it was measured on other tasks.
"""
import argparse
import hashlib
import json
from pathlib import Path

import torch

from src.genome import LIFE_DIMS_ABI8, LifeLayout, make_dims

TARGETS = {"abi8": LIFE_DIMS_ABI8}


def pad_group(group: dict, target: LifeLayout) -> dict:
    source = LifeLayout(make_dims(group["dims"]))
    rows = torch.stack([source.from_dict(g) for g in group["genomes"]])
    padded = source.pad(rows, target)
    return {"dims": target.dims.__dict__, "ids": group["ids"], "breeds": group["breeds"], "origins": group["origins"],
            "fitness": None, "genomes": [target.to_dict(g) for g in padded]}


def main(argv=None):
    p = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    p.add_argument("snapshot")
    p.add_argument("out_prefix")
    p.add_argument("--dims", default="abi8", choices=sorted(TARGETS))
    args = p.parse_args(argv)
    raw = Path(args.snapshot).read_bytes()
    snap = json.loads(raw)
    target = LifeLayout(TARGETS[args.dims])
    out = {"population": pad_group(snap, target)}
    if snap.get("archive"):
        out["archive"] = pad_group(snap["archive"], target)
    source = {"file": str(Path(args.snapshot).resolve()), "sha256": hashlib.sha256(raw).hexdigest(),
              "generation": snap.get("generation")}
    for kind, payload in out.items():
        payload["padded_from"] = source
        path = Path(f"{args.out_prefix}_{kind}.json")
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(json.dumps(payload))
        print(f"{path}: {len(payload['genomes'])} genomes")


if __name__ == "__main__":
    main()
