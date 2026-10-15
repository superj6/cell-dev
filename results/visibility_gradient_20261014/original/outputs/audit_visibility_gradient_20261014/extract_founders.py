"""Extract two existing confirmation rows; never imports or runs the life engine."""
from __future__ import annotations

import hashlib
import json
from pathlib import Path
import shutil
import sys

import numpy as np

ROOT = Path(__file__).resolve().parents[2]
OUT = Path(__file__).resolve().parent / "founders"
CASES = (
    ("D90", "continuation_20261013", "s51090_final_rank0", "founder_row38", "s51090"),
    ("L92", "s7_continuation_20261014", "s51892_final_rank0", "founder_row29", "s51892"),
)


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def freeze_bytes(path, value):
    if path.exists() and path.read_bytes() != value:
        raise ValueError("existing extracted input differs: " + str(path))
    path.write_bytes(value)


def main():
    OUT.mkdir(exist_ok=True)
    records = {}
    for name, study, label, template_label, run in CASES:
        archive = ROOT / "results" / study
        manifest_path = archive / "confirmation/manifest.json"
        table_path = archive / "confirmation/genotypes.npz"
        template_path = archive / "inputs" / (template_label + ".json")
        config_path = archive / "configs" / (run + ".yaml")
        manifest = json.loads(manifest_path.read_text())
        template = json.loads(template_path.read_text())
        with np.load(table_path, allow_pickle=False) as data:
            labels = data["labels"].tolist()
            assert labels == manifest["labels"] and len(labels) == len(set(labels))
            index = labels.index(label)
            row = data["genomes"][index].copy()
        assert index == 3 and row.dtype == np.dtype("<f4") and row.shape == (875,)
        assert np.isfinite(row).all()
        raw_hash = hashlib.sha256(row.tobytes()).hexdigest()
        assert raw_hash == manifest["genotype_sha256"][label]
        # The archived layout's ordered field shapes are authenticated against its
        # own independently retained confirmation row before reusing their layout.
        flat_template = np.concatenate([np.asarray(v, dtype="<f4").reshape(-1)
                                        for v in template["params"].values()])
        assert hashlib.sha256(flat_template.tobytes()).hexdigest() == manifest["genotype_sha256"][template_label]
        cursor, params, shapes = 0, {}, {}
        for field, value in template["params"].items():
            shape = np.asarray(value).shape
            count = int(np.prod(shape))
            params[field] = row[cursor:cursor + count].reshape(shape).tolist()
            shapes[field] = list(shape)
            cursor += count
        assert cursor == len(row)
        payload = {"dims": template["dims"], "params": params}
        encoded = (json.dumps(payload, indent=2, allow_nan=False) + "\n").encode()
        reparsed = json.loads(encoded)
        reconstructed = np.concatenate([np.asarray(v, dtype="<f4").reshape(-1)
                                        for v in reparsed["params"].values()])
        assert reconstructed.tobytes() == row.tobytes()
        target = OUT / name
        target.mkdir(exist_ok=True)
        freeze_bytes(target / "parent.json", encoded)
        freeze_bytes(target / "config.yaml", config_path.read_bytes())
        if (target / "genome.npy").exists():
            assert np.load(target / "genome.npy", allow_pickle=False).tobytes() == row.tobytes()
        else:
            np.save(target / "genome.npy", row, allow_pickle=False)
        records[name] = {
            "label": label, "row_index": index, "dtype": row.dtype.str,
            "shape": list(row.shape), "raw_sha256": raw_hash,
            "dims": template["dims"], "field_shapes_in_layout_order": shapes,
            "source_sha256": {str(p.relative_to(ROOT)): sha(p) for p in
                              (manifest_path, table_path, template_path, config_path)},
            "output_sha256": {str(p.relative_to(OUT.parent)): sha(p)
                              for p in (target / "parent.json", target / "genome.npy", target / "config.yaml")},
            "interpretation": "Exact confirmed final rank zero, not historical best_genome.json; no allele edited.",
        }
    assert not any(name == "src" or name.startswith("src.") for name in sys.modules)
    receipt = {"status": "extracted_existing_founders_only", "simulation_calls": 0,
               "mutants_generated": 0, "seed_reservations": [], "engine_imported": False,
               "extraction_source_sha256": sha(__file__), "founders": records}
    freeze_bytes(OUT / "manifest.json", (json.dumps(receipt, indent=2) + "\n").encode())
    print(json.dumps({"status": receipt["status"], "manifest_sha256": sha(OUT / "manifest.json"),
                      "raw_sha256": {k: v["raw_sha256"] for k, v in records.items()}}))


if __name__ == "__main__":
    main()
