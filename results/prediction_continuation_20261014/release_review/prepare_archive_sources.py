"""Narrow adaptation of reviewed AE packaging; writes only AF audit source, no simulations."""
from pathlib import Path
ROOT=Path(__file__).resolve().parents[2]
OUT=Path(__file__).resolve().parent
old=ROOT/'outputs/audit_prediction_gradient_20261014/new_ae/archive.py'
s=old.read_text().replace('Package AE','Package AF').replace('parents[3]','parents[2]').replace('autonomous_prediction_gradient_20261014','autonomous_prediction_continuation_20261014').replace('results/prediction_gradient_20261014','results/prediction_continuation_20261014').replace('0f5a591fbfb66fd29b5f9cd11d42b482eb8cb09e74613b17cc384ed2c3daa849','ebdc3f37dc5d9a882b2b7d68ed3913a08540be4f476bdd6cf4b6c446e315b5e0').replace('reviewed AE registration','reviewed AF registration')
a=s.index('    # Current namespace proof is bundled;');b=s.index('    add(audit / "NAMESPACE_PROVENANCE.md"',a)
block='''    # Current proof is bundled; immutable older namespace proof stays content-addressed.
    registration = read(study / "registration.json")
    external = dict(registration["review_pins"])
    for name, digest in registration["AE_complete"]["file_pins"].items():
        external["results/prediction_gradient_20261014/" + name] = digest
    external.update(read(study / "seed_audit.json")["source_pins"])
    namespace = audit / "namespace"
    candidate = read(namespace / "candidate_namespace_review.json")
    external.update(candidate["source_pins"])
    delta = read(namespace / "final_namespace_delta.json")
    external.update(delta["JSON_source_pins"])
    external.update(delta["root_watchable_illustration"]["source_pins"])
    for path in sorted(namespace.iterdir()):
        if path.is_file():
            external[str(path.relative_to(root))] = sha(path)
    refs = read(namespace / "history_references.json")
    for digest, item in refs["content_by_sha256"].items():
        source = inside(root, item["repository_path"])
        if sha(source) != digest or source.stat().st_size != item["bytes"]:
            raise ValueError("historical public namespace content differs")
        recorded = subprocess.run(["git", "show", item["containing_public_commit"] + ":" + item["repository_path"]],
                                  cwd=root, capture_output=True, check=True).stdout
        if hashlib.sha256(recorded).hexdigest() != digest:
            raise ValueError("historical committed namespace content differs")
    u = root / "results/decoy_evolution_20261014"
    provenance = read(u / "provenance.json")
    for name in ("runs/s53091/config.yaml", "protocol.json", "run_budgeted.py", "test_monitor.py", "reviews/monitor_review.json"):
        external[str((u/name).relative_to(root))] = provenance["artifacts"][name]["sha256"]
    external[str((u/"provenance.json").relative_to(root))] = sha(u/"provenance.json")
    watchable = root / "results/ae_watchable_20261014"
    wm = read(watchable/"manifest.json")
    for name,item in wm["artifacts"].items():
        external[str((watchable/name).relative_to(root))] = item["sha256"]
    external[str((watchable/"manifest.json").relative_to(root))] = sha(watchable/"manifest.json")
    external.update({name:item["sha256"] for name,item in wm["external_artifacts"].items()})
    for name, digest in external.items():
        if digest in refs["content_by_sha256"] or protocol["production_pins"].get(name) == digest:
            continue
        add(inside(root,name), "original/" + name, digest)
    # These two global-doc claim snapshots predate AF registration and stay historical.
    document_history = read(audit/"watchable_document_history.json")
    for name,item in document_history.items():
        add(inside(root,item["preserved_path"]), "original/"+name, item["sha256"],
            origin="git:"+item["containing_commit"]+":"+name)
'''
s=s[:a]+block+s[b:]
s=s.replace('("analyze.py", "offline_accounting.py", "panel_replay.py", "panel_replay.json", "analysis_review.json")','("analyze.py", "offline_accounting.py", "native_audit.py", "initialization_replay.json", "analysis_review.json")')
s=s.replace('"measurement", "logs", "build-cache", "startup_identity.json", "selection.json", "requests", "monitor_receipts"','"runs", "confirmation", "logs", "build-cache"')
s=s.replace('"planned_research_lives": 6208, "planned_validation_lives": 10','"planned_research_lives": 10316, "planned_validation_lives": 6')
(OUT/'archive.py').write_text(s)
