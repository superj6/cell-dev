"""Copy immutable N preparation to the public archive; never release or simulate."""
import shutil

from run_budgeted import READY_FILES

import measure as M


def main():
    protocol = M.check_protocol()
    if any((M.STUDY / name).exists() for name in ("ready.json", "budget.json", "measurement")):
        raise ValueError("preparation publisher cannot overwrite a released archive")
    target = M.ROOT / "results/information_duration_20261014"
    target.mkdir(parents=True, exist_ok=True)
    if (target / "provenance.json").exists():
        previous = M.read(target / "provenance.json")
        if previous["status"] != "prospective_preparation_not_released":
            raise ValueError("completed archive cannot be replaced by preparation")
    ready = {"status": "template_not_released", "files": {name: M.sha(M.STUDY / name) for name in READY_FILES},
             "dependencies": protocol["dependencies"]}
    M.save(M.STUDY / "ready.template.json", ready)
    names = (*READY_FILES, "test_monitor.py", "publish.py", "README.md", "input_sources.json", "ready.template.json")
    for name in names:
        shutil.copy2(M.STUDY / name, target / name)
    for folder in ("inputs", "sources"):
        shutil.copytree(M.STUDY / folder, target / folder, dirs_exist_ok=True,
                        ignore=shutil.ignore_patterns("__pycache__", "*.pyc"))
    for relative, digest in protocol["source_pins"].items():
        source = M.ROOT / relative
        if M.sha(source) != digest:
            raise ValueError("numerical source differs: " + relative)
        dest = target / "archive_sources" / relative
        dest.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(source, dest)
    for name in ("science_review.json", "monitor_review.json"):
        source = M.ROOT / "outputs/audit_n_20261014" / name
        if source.exists():
            shutil.copy2(source, target / name)
    artifacts = {str(path.relative_to(target)): {"sha256": M.sha(path), "bytes": path.stat().st_size}
                 for path in sorted(target.rglob("*"))
                 if path.is_file() and path.name != "provenance.json" and "__pycache__" not in path.parts}
    M.save(target / "provenance.json", {"status": "prospective_preparation_not_released",
                                        "source_study": str(M.STUDY.relative_to(M.ROOT)),
                                        "analysis_simulated_lives": 0, "artifacts": artifacts})
    print("Published N preparation: " + str(len(artifacts)) + " artifacts; no release or simulation.")


if __name__ == "__main__":
    main()
