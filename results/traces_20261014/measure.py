"""Observe twelve fixed lives with the existing E6 probes; never changes an organism."""
from __future__ import annotations

import argparse
import hashlib
import json
import os
import sys
from dataclasses import asdict, fields
from pathlib import Path

os.environ.setdefault("ATEN_CPU_CAPABILITY", "avx2")
ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))
STUDY = ROOT / "outputs/autonomous_traces_20261014"
LABELS = ("founder_row38", "d_s51089_final_rank0", "d_s51090_final_rank0")
SEEDS = list(range(51_890_000, 51_890_004))
WORLD = dict(T=1536, d0=.5, d_min=.25, sigma=.4, lam_s=4.0)
DEPENDENCIES = ("outputs/autonomous_hidden_20261014", "outputs/autonomous_decoy_gradient_20261014")


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def save(path, value):
    from src.life.readouts import json_safe

    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_suffix(".tmp")
    temporary.write_text(json.dumps(json_safe(value), indent=2, allow_nan=False) + "\n")
    temporary.replace(path)


def check_protocol():
    value = json.loads((STUDY / "protocol.json").read_text())
    expected = dict(labels=list(LABELS), seeds=SEEDS, world=WORLD, reference_lives=12,
                    kernel_validation_lives=12, threads=1, max_cpu_seconds=1800,
                    readout_starts=[0, 800], silence_window=.5, max_chain_depth=12,
                    wait_for_studies=list(DEPENDENCIES))
    if any(value[key] != item for key, item in expected.items()):
        raise ValueError("registered scope differs")
    for name, digest in value["source_identity"].items():
        if sha(ROOT / name) != digest:
            raise ValueError("source differs: " + name)
    for name, item in value["inputs"].items():
        if sha(STUDY / name) != item["sha256"]:
            raise ValueError("input differs: " + name)
    return value


def store_trace(path, trace, kernel):
    """Store each table column losslessly without pickle or object arrays."""
    import numpy as np
    import pandas as pd

    arrays, tables = {}, {}
    for field in fields(trace):
        frame = getattr(trace, field.name)
        if not isinstance(frame, pd.DataFrame):
            continue
        tables[field.name] = list(frame.columns)
        for column in frame:
            value = frame[column].to_numpy()
            if value.dtype.kind == "O":
                if any(not isinstance(item, str) for item in value):
                    raise ValueError("non-string object in trace table")
                value = value.astype(str)
            arrays[field.name + "__" + str(column)] = value
    arrays["kernel_ledger"] = kernel.ledger
    arrays["kernel_hashes"] = kernel.hashes
    metadata = dict(ledger=trace.ledger, meta={k: v for k, v in trace.meta.items() if k != "world"},
                    world=asdict(trace.meta["world"]), tables=tables)
    arrays["metadata"] = np.asarray(json.dumps(metadata, allow_nan=False))
    temporary = path.with_suffix(".tmp.npz")
    np.savez_compressed(temporary, **arrays)
    temporary.replace(path)


def load_trace(path):
    import numpy as np
    import pandas as pd

    from src.life import probe, spec

    with np.load(path, allow_pickle=False) as data:
        metadata = json.loads(str(data["metadata"]))
        tables = {name: pd.DataFrame({column: data[name + "__" + str(column)] for column in columns})
                  for name, columns in metadata["tables"].items()}
        meta = dict(metadata["meta"], world=spec.World(**metadata["world"]))
        trace = probe.Trace(**tables, ledger=metadata["ledger"], meta=meta)
        ledger = data["kernel_ledger"].copy()
    return trace, ledger



def validate_roundtrip(original, restored):
    """Check every raw table, including columns not used by the descriptive readouts."""
    import pandas as pd

    for field in fields(original):
        left, right = getattr(original, field.name), getattr(restored, field.name)
        if isinstance(left, pd.DataFrame):
            if list(left.columns) != list(right.columns) or not left.index.equals(right.index):
                raise ValueError("trace table schema changed: " + field.name)
            for column in left:
                a, b = left[column].to_numpy(), right[column].to_numpy()
                if a.dtype.kind in "OUS":
                    equal = a.tolist() == b.tolist()
                else:
                    equal = a.dtype == b.dtype and a.shape == b.shape and a.tobytes() == b.tobytes()
                if not equal:
                    raise ValueError("trace table changed: " + field.name + "/" + str(column))
        elif left != right:
            raise ValueError("trace metadata changed: " + field.name)


def describe(trace):
    from src.life import probe, readouts

    probe.relabel(trace)
    return readouts.json_safe(dict(search={str(start): readouts.search_signature(trace, silence_window=.5, start=start)
                        for start in (0, 800)},
                relay={str(start): readouts.relay_chains([trace], start=start, max_depth=12)
                       for start in (0, 800)}))


def validate_match(trace, kernel_ledger):
    import numpy as np

    from src.life import readouts, spec

    reference = np.asarray([trace.ledger[key] for key in spec.V3.LEDGER], dtype=np.float64)
    kernel = np.asarray(kernel_ledger, dtype=np.float64).reshape(-1)
    if reference.tobytes() != kernel.tobytes():
        names = [key for i, key in enumerate(spec.V3.LEDGER)
                 if reference[i:i+1].tobytes() != kernel[i:i+1].tobytes()]
        raise ValueError("reference/kernel ledger differs: " + str(names))
    return readouts.validate_ledger(reference)


def run():
    import numpy as np
    from run_budgeted import check_ready

    from src.checkpoint import numerical_identity
    from src.genome import Layout
    from src.life import handbuilt, probe

    protocol, ready = check_protocol(), check_ready()
    identity = numerical_identity()
    if identity != protocol["numerical_identity"]:
        raise ValueError("numerical identity differs")
    out = STUDY / "measurement"
    out.mkdir(exist_ok=False)
    organisms = {}
    for label in LABELS:
        _, genome = Layout.load(STUDY / "inputs" / (label + ".json"))
        organisms[label] = handbuilt.GrnBody(label, np.asarray(genome, dtype=np.float32).reshape(-1))
    save(out / "manifest.json", dict(protocol_sha256=sha(STUDY / "protocol.json"), ready=ready,
                                     numerical_identity=identity, order=[[label, seed] for seed in SEEDS
                                                                         for label in LABELS]))
    report = dict(status="running", lives=[], reference_lives=0, kernel_validation_lives=0)
    save(out / "report.json", report)
    for seed in SEEDS:
        for label in LABELS:
            org = organisms[label]
            trace = probe.trace(org, seed, "catch_speck_l4", check=False, **WORLD)
            kernel = org.run([seed], preset="catch_speck_l4", threads=1, **WORLD)
            path = out / f"{label}_{seed}.npz"
            store_trace(path, trace, kernel)
            statuses = validate_match(trace, kernel.ledger)
            loaded, ledger = load_trace(path)
            validate_roundtrip(trace, loaded)
            observed = describe(trace)
            validate_match(loaded, ledger)
            if describe(loaded) != observed:
                raise ValueError("trace round-trip changes readout")
            save(path.with_suffix(".json"), observed)
            report["lives"].append(dict(label=label, seed=seed, trace=path.name, sha256=sha(path),
                                        status_counts=statuses, ledger_columns_bitwise_equal=57,
                                        readout=path.with_suffix(".json").name))
            report["reference_lives"] += 1
            report["kernel_validation_lives"] += 1
            save(out / "report.json", report)
            print(label, seed, "saved", flush=True)
    report["status"] = "complete"
    save(out / "report.json", report)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--run", action="store_true")
    args = parser.parse_args()
    if args.run:
        run()
    else:
        print(json.dumps(dict(status="dry_run", reference_lives=12, kernel_validation_lives=12,
                              max_cpu_seconds=1800, threads=1, simulated_lives=0)))


if __name__ == "__main__":
    main()
