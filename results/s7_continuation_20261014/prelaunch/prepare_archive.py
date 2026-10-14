"""Publish L's concrete preparation and readiness template; never create ready.json or launch work."""
import json
import shutil
from pathlib import Path

from run_budgeted import check_protocol, sha

STUDY = Path(__file__).resolve().parent
ROOT = STUDY.parents[1]
PUBLIC = ROOT / "results/s7_continuation_20261014"


def save(path, value):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, indent=2, allow_nan=False) + "\n")


def main():
    protocol = check_protocol()
    if (STUDY / "ready.json").exists() or (STUDY / "budget.json").exists():
        raise ValueError("this preparation publisher cannot rewrite a released study")
    dependencies = {}
    for relative in protocol["wait_for_studies"]:
        folder = ROOT / relative
        ready = json.loads((folder / "ready.json").read_text())
        for name in ("protocol.json", "run_budgeted.py"):
            if sha(folder / name) != ready["files"][name]:
                raise ValueError("dependency source differs from released pins")
        dependencies[relative] = {name: sha(folder / name) for name in ("protocol.json", "run_budgeted.py")}
    ready = {"status": "template_not_released", "runner_sha256": sha(STUDY / "run_budgeted.py"),
             "measurement_sha256": sha(STUDY / "measure.py"), "protocol_sha256": sha(STUDY / "protocol.json"),
             "helpers": protocol["helpers"], "dependencies": dependencies}
    save(STUDY / "ready.template.json", ready)
    artifacts = {}

    def keep(source, name):
        target = PUBLIC / name
        target.parent.mkdir(parents=True, exist_ok=True)
        shutil.copyfile(source, target)
        artifacts[str(name)] = {"sha256": sha(target), "bytes": target.stat().st_size}

    for name in ("README.md", "PREREG.md", "protocol.json", "seed_audit.json", "initialization.json",
                 "prepare.py", "measure.py", "run_budgeted.py", "prepare_archive.py", "test_prepared.py",
                 "test_monitor.py", "validation.json", "ready.template.json"):
        keep(STUDY / name, name)
    for name in ("monitor_review.json", "independent_review.json", "test_monitor_review.py"):
        if (STUDY / name).exists():
            keep(STUDY / name, name)
    for name in protocol["inputs"]:
        keep(STUDY / name, name)
    for name in protocol["reference_sources"]:
        keep(STUDY / name, name)
    for seed, item in protocol["configs"].items():
        keep(ROOT / item["path"], f"configs/s{seed}.yaml")
    for row in json.loads((STUDY / "initialization.json").read_text())["runs"].values():
        keep(STUDY / row["population_file"], row["population_file"])
    for name in protocol["source_identity"]:
        keep(ROOT / name, Path("sources") / name)
    for name in protocol["helpers"]:
        keep(ROOT / "scripts" / name, Path("sources/scripts") / name)
    for relative, files in dependencies.items():
        for name in files:
            keep(ROOT / relative / name, Path("dependencies") / Path(relative).name / name)
    manifest = {"status": "prepared_not_released", "artifacts": artifacts, "simulated_lives": 0,
                "research_genome_lives_planned": 36012, "max_worker_cpu_seconds": 14400,
                "numerical_identity": protocol["expected_numerical_identity"],
                "protocol_sha256": sha(STUDY / "protocol.json"), "readiness_created": False}
    save(PUBLIC / "provenance.json", manifest)
    save(STUDY / "preparation_manifest.json", manifest)
    print(json.dumps({"status": manifest["status"], "artifacts": len(artifacts), "simulated_lives": 0,
                      "ready_json_created": False}))


if __name__ == "__main__":
    main()
