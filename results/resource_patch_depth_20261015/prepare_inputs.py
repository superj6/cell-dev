"""Exact full-population import and prospectively chosen comparators; no builds, lives or draws."""

from __future__ import annotations

import copy
import hashlib
import json
import os
import shutil
import subprocess
import sys
from dataclasses import asdict, replace
from pathlib import Path

os.environ.setdefault("ATEN_CPU_CAPABILITY", "avx2")
sys.dont_write_bytecode = True
STUDY = Path(__file__).resolve().parent
ROOT = STUDY.parents[1]
SELECTION = ROOT / "results/resource_patch_selection_20261015"
PANEL = ROOT / "results/resource_patch_population_20261015"
REVISION = "1a7f38bd3222bacf27367fd99998d87776c34ec5"
REFERENCE_ROWS = (
    ("AO", 96, "AO", 0, 5336),
    ("G8_joint", 20, "G8", 20, 1795),
    ("Pareto4_joint", 90, "pareto4", 26, 918),
)
OLD_WORLDS = ("patch", "pool", "persistent", "blink80_20", "transfer")


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def raw_sha(array):
    return hashlib.sha256(array.tobytes()).hexdigest()


def read(path):
    return json.loads(Path(path).read_text())


def save(path, value):
    with Path(path).open("x") as stream:
        json.dump(value, stream, indent=2, allow_nan=False)
        stream.write("\n")


def materialize_inputs(revision):
    """Return protocol-ready records; root owns configs, protocol, reservation and execution."""
    if any(
        (STUDY / name).exists() for name in ("inputs", "configs", "protocol.json", "reservation.json", "release.json")
    ):
        raise ValueError("first preparation requires absent inputs/configs/protocol/reservation")
    head = subprocess.check_output(["git", "rev-parse", "HEAD"], cwd=ROOT, text=True).strip()
    if revision != REVISION or head != revision:
        raise ValueError("exact completed population milestone revision required")
    audit = read(STUDY / "namespace/seed_audit.json")
    if (
        audit["status"] != "passed"
        or audit["reserved"]
        or audit["native_seed"] != 53236
        or audit["endpoint_seeds"] != list(range(52520000, 52520032))
        or audit["confirmation_seeds"] != list(range(52530000, 52530512))
        or audit["seed_blocks"] != [[52520000, 52530000], [52530000, 52540000]]
        or audit["unique_native_ids"] != 564
    ):
        raise ValueError("passed unreserved exact depth schedules required")
    sys.path.insert(0, str(ROOT))
    import numpy as np
    import torch
    from omegaconf import OmegaConf

    from src import checkpoint
    from src.genome import make_dims, make_layout
    from src.life import spec

    torch.set_num_threads(1)
    archives = {base: read(base / "manifest.json") for base in (SELECTION, PANEL)}
    if any(doc["status"] != "complete" or not isinstance(doc["files"], dict) for doc in archives.values()):
        raise ValueError("complete public patch archives required")
    originals, copies = {}, {}

    def bind(base, relative, destination=None):
        path = base / relative
        pin = archives[base]["files"][relative]
        if sha(path) != pin["sha256"] or path.stat().st_size != pin["bytes"]:
            raise ValueError("changed public input: " + relative)
        originals[str(path.relative_to(ROOT))] = pin["sha256"]
        if destination is not None:
            if destination in copies:
                raise ValueError("duplicate input destination")
            copies[destination] = path
        return path

    for base in archives:
        originals[str((base / "manifest.json").relative_to(ROOT))] = sha(base / "manifest.json")
    prior = read(bind(PANEL, "protocol.json", "population_protocol.json"))
    for name in ("budget.json", "study_complete.json", "measurement_complete.json"):
        if read(bind(PANEL, name))["status"] != "complete":
            raise ValueError("completed population diagnostic required")
    if read(bind(PANEL, "reviews/independent_review.json"))["status"] != "passed":
        raise ValueError("independently checked population diagnostic required")
    if tuple(prior["worlds"]) != OLD_WORLDS or prior["total_calls"] != 15524:
        raise ValueError("exact preceding population panel required")
    for name, pin in prior["production_pins"].items():
        if sha(ROOT / name) != pin:
            raise ValueError("unchanged production required: " + name)
    panel_rows = read(bind(PANEL, "inputs/rows.json", "prior_rows.json"))
    panel_genomes = np.load(bind(PANEL, "inputs/genomes.npy"), allow_pickle=False)
    if (
        panel_genomes.shape != (97, 875)
        or panel_genomes.dtype != np.float32
        or not np.isfinite(panel_genomes).all()
        or raw_sha(panel_genomes) != panel_rows["raw_sha256"]
    ):
        raise ValueError("exact completed raw panel required")
    summary = read(bind(PANEL, "summary.json"))
    layout = make_layout(make_dims(panel_rows["dims"]))
    population = read(bind(SELECTION, "runs/pareto/population.json", "input_population.json"))
    state_path = bind(SELECTION, "runs/pareto/checkpoint.pt", "input_checkpoint.pt")
    cfg_path = bind(SELECTION, "runs/pareto/config.yaml", "input_config.yaml")
    identity_path = bind(SELECTION, "runs/pareto/determinism.json", "input_determinism.json")
    saved = checkpoint.load(state_path)
    checkpoint.validate(saved, OmegaConf.load(cfg_path), read(identity_path))
    state = saved["state"]
    table = np.stack([layout.from_dict(row).numpy() for row in population["genomes"]])
    if (
        population["dims"] != layout.dims.__dict__
        or table.shape != (32, 875)
        or table.dtype != np.float32
        or not np.isfinite(table).all()
        or len(set(population["ids"])) != 32
        or population["ids"] != state["ids"].tolist()
        or state["generation"] != 4
        or table.tobytes() != state["population"].numpy().tobytes()
        or table.tobytes() != panel_genomes[64:96].tobytes()
    ):
        raise ValueError("All 32 ordered Pareto4 rows must equal checkpoint and completed panel bytes")
    hashes = [raw_sha(row) for row in table]
    start = dict(
        population_file="inputs/input_population.json",
        file_sha256=sha(SELECTION / "runs/pareto/population.json"),
        population_raw_sha256=raw_sha(table),
        shape=[32, 875],
        old_ids=population["ids"],
        new_ids=list(range(32)),
        row_sha256=hashes,
        old_to_new=[dict(old_id=old, new_id=i, row=i, raw_sha256=hashes[i]) for i, old in enumerate(population["ids"])],
    )
    reference_rows, reference_vectors = [], []
    for role, index, group, local, native_id in REFERENCE_ROWS:
        row = panel_rows["rows"][index]
        vector = panel_genomes[index]
        if (
            row["index"] != index
            or row["group"] != group
            or row["row"] != local
            or row["native_id"] != native_id
            or row["raw_sha256"] != raw_sha(vector)
        ):
            raise ValueError("prospective fixed comparator identity differs: " + role)
        details = summary["descriptive_orders"][group]
        if details["fresh_order_local_rows"][0] != local:
            raise ValueError("comparator does not match the prior development joint ordering: " + role)
        reference_rows.append(
            dict(
                role=role,
                path=f"inputs/{role}.json",
                panel_index=index,
                group=group,
                local_row=local,
                native_id=native_id,
                raw_sha256=raw_sha(vector),
                selection="Prospective comparator for this new study, chosen by prior development joint order; no historical endpoint replacement.",
            )
        )
        reference_vectors.append(vector)
    definitions = {name: spec.World(**record["world"]) for name, record in prior["worlds"].items()}
    definitions["reserved_capacity3"] = replace(
        definitions["patch"],
        patch_count=4,
        patch_capacity=3,
        R_min=2.5,
        R_max=4.5,
        patch_refill_fast=60.0,
        patch_refill_slow=180.0,
    )
    worlds = {}
    for name, world in definitions.items():
        spec.V6.validate_world(world)
        record = dict(
            abi=6,
            world=asdict(world),
            world_vector=spec.V6.pack_world(world).tolist(),
            ledger_columns=list(spec.V6.LEDGER),
        )
        if name in prior["worlds"] and record != prior["worlds"][name]:
            raise ValueError("prior world or prices changed: " + name)
        worlds[name] = record
    bind(PANEL, "inputs/patch_truth.json", "patch_truth.json")
    bind(PANEL, "inputs/startup_identity.json", "startup_identity.json")
    bind(PANEL, "inputs/accounting.py", "accounting.py")
    if read(PANEL / "inputs/startup_identity.json")["identity"] != prior["expected_numerical_identity"]:
        raise ValueError("startup identity differs from completed sources")
    inputs = STUDY / "inputs"
    inputs.mkdir()
    for name, path in copies.items():
        shutil.copyfile(path, inputs / name)
    for record, vector in zip(reference_rows, reference_vectors, strict=True):
        target = STUDY / record["path"]
        save(target, dict(dims=layout.dims.__dict__, params=layout.to_dict(torch.from_numpy(vector.copy()))))
        record["file_sha256"] = sha(target)
    refs = np.stack(reference_vectors)
    with (inputs / "references.npy").open("xb") as stream:
        np.save(stream, refs, allow_pickle=False)
    ref_manifest = dict(
        roles=[row["role"] for row in reference_rows],
        dims=layout.dims.__dict__,
        shape=[3, 875],
        dtype="float32",
        raw_sha256=raw_sha(refs),
        rows=reference_rows,
        prior_summary_source=str((PANEL / "summary.json").relative_to(ROOT)),
        prior_summary_sha256=sha(PANEL / "summary.json"),
    )
    save(inputs / "references.json", ref_manifest)
    save(inputs / "population_import.json", start)
    result = dict(
        source_revision=REVISION,
        engine_revision=prior["engine_revision"],
        population_start=start,
        references=reference_rows,
        reference_input="inputs/references.npy",
        references_manifest="inputs/references.json",
        reference_roles=ref_manifest["roles"],
        native_seed=53236,
        endpoint_seeds=audit["endpoint_seeds"],
        confirmation_seeds=audit["confirmation_seeds"],
        native_life_seeds=audit["native_life_seeds"],
        worlds=worlds,
        selection_worlds={name: worlds[name]["world"] for name in OLD_WORLDS[:3]},
        expected_numerical_identity=copy.deepcopy(prior["expected_numerical_identity"]),
        extinct_charge=True,
        accounting_input="inputs/accounting.py",
        endpoint_reference_captures=prior["endpoint_reference_captures"],
        endpoint_reference_worlds=prior["endpoint_reference_worlds"],
        production_pins=prior["production_pins"],
        original_input_pins=originals,
        input_pins={str(path.relative_to(STUDY)): sha(path) for path in sorted(inputs.iterdir()) if path.is_file()},
        seed_audit_sha256=sha(STUDY / "namespace/seed_audit.json"),
        preparation_lives=0,
        preparation_builds=0,
        preparation_random_draws=0,
    )
    save(STUDY / "materialized_inputs.json", result)
    return result


if __name__ == "__main__":
    print("Source only. Root calls materialize_inputs(revision) after reviewed audit; no preparation or reservation.")
