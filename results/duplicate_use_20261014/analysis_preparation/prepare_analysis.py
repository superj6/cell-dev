"""Publish separate J analysis preparation without changing the scientific preparation manifest."""
import hashlib
import json
import shutil
from pathlib import Path

STUDY = Path(__file__).resolve().parent
ROOT = STUDY.parents[1]
PUBLIC = ROOT / "results/duplicate_use_20261014/analysis_preparation"


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def main():
    PUBLIC.mkdir(parents=True, exist_ok=True)
    files = ("analyze.py", "analysis_common.py", "genome_audit.py", "test_analysis.py", "prepare_analysis.py",
             "analysis_validation.json", "independent_review.json")
    mapping = {name: name for name in files}
    mapping.update({"ANALYSIS_PREPARATION.md": "README.md",
                    "test_single_branch_review.py": "test_single_branch_review.py.txt"})
    for source, target in mapping.items():
        shutil.copyfile(STUDY / source, PUBLIC / target)
    artifacts = {name: {"sha256": sha(PUBLIC / name), "bytes": (PUBLIC / name).stat().st_size}
                 for name in mapping.values()}
    manifest = {"status": "analysis_prepared_without_outcome_inspection", "simulated_lives": 0,
                "scientific_protocol_sha256": sha(STUDY / "protocol.json"),
                "scientific_preparation_provenance_sha256": sha(PUBLIC.parent / "provenance.json"),
                "artifacts": artifacts}
    (PUBLIC / "provenance.json").write_text(json.dumps(manifest, indent=2) + "\n")
    print(json.dumps({"status": manifest["status"], "artifacts": len(artifacts), "simulated_lives": 0}))


if __name__ == "__main__":
    main()
