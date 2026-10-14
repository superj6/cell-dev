"""Pin the fixed trace study without running a life."""
from __future__ import annotations

import hashlib
import json
import shutil
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
STUDY = ROOT / "outputs/autonomous_traces_20261014"
PUBLIC = ROOT / "results/traces_20261014"


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def save(path, value):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, indent=2, allow_nan=False) + "\n")


def main():
    if (STUDY / "ready.json").exists() or (STUDY / "budget.json").exists():
        raise ValueError("released study cannot be prepared again")
    hidden = ROOT / "outputs/autonomous_hidden_20261014"
    h = json.loads((hidden / "protocol.json").read_text())
    inputs = {key: item for key, item in h["inputs"].items()
              if key.endswith('.json') and any(label in key for label in h['labels'])}
    for name, item in inputs.items():
        target = STUDY / name
        target.parent.mkdir(parents=True, exist_ok=True)
        shutil.copyfile(ROOT / item["source"], target)
        assert sha(target) == item["sha256"]
    source_archive = "results/decoy_gradient_20261014/sources"
    for name, digest in h["source_identity"].items():
        assert sha(ROOT / name) == digest
        assert sha(ROOT / source_archive / name) == digest
    protocol = dict(study="fixed_continuation_traces", status="prepared_not_released",
                    labels=h["labels"], seeds=list(range(51_890_000, 51_890_004)),
                    world=dict(T=1536, d0=.5, d_min=.25, sigma=.4, lam_s=4.0),
                    reference_lives=12, kernel_validation_lives=12, threads=1, max_cpu_seconds=1800,
                    readout_starts=[0, 800], silence_window=.5, max_chain_depth=12,
                    wait_for_studies=["outputs/autonomous_hidden_20261014",
                                      "outputs/autonomous_decoy_gradient_20261014"],
                    source_identity=h["source_identity"], source_archive=source_archive,
                    numerical_identity=h["numerical_identity"], inputs=inputs,
                    limitations=["Four descriptive seeds; no success thresholds or claim of a new algorithm.",
                                 "Largest-input attribution omits subthreshold integration.",
                                 "Normal growing tissues have different footprints and earlier states.",
                                 "Movement during silence does not establish use of silence as evidence."])
    save(STUDY / "protocol.json", protocol)
    ready = dict(status="template_not_released",
                 files={name: sha(STUDY / name) for name in ("measure.py", "run_budgeted.py", "protocol.json")},
                 dependencies={name: {f: sha(ROOT / name / f) for f in ("protocol.json", "run_budgeted.py")}
                               for name in protocol["wait_for_studies"]})
    save(STUDY / "ready.template.json", ready)
    PUBLIC.mkdir(exist_ok=True)
    for name in ("measure.py", "run_budgeted.py", "prepare.py", "test_trace_io.py", "protocol.json",
                 "ready.template.json", "PREREG.md", "test_monitor_review.py", "validation.json"):
        shutil.copyfile(STUDY / name, PUBLIC / name)
    shutil.copytree(STUDY / "inputs", PUBLIC / "inputs", dirs_exist_ok=True)
    (PUBLIC / "README.md").write_text(
        "# Fixed continuation traces\n\nPrepared and preregistered; no trace lives run yet.\n\n"
        "See PREREG.md for scope. Source bytes are shared with the pinned decoy-gradient source archive; "
        "protocol.json records every hash. Working outputs stay under outputs/autonomous_traces_20261014/.\n")
    artifacts = {str(path.relative_to(PUBLIC)): dict(sha256=sha(path), bytes=path.stat().st_size)
                 for path in sorted(PUBLIC.rglob('*')) if path.is_file() and path.name != 'provenance.json'}
    save(PUBLIC / "provenance.json", dict(status="preparation", artifacts=artifacts,
                                        simulations_in_preparation=0))
    print("prepared", len(artifacts), "artifacts")


if __name__ == "__main__":
    main()
