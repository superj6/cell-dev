"""Literal review of the single depth namespace scan; no reservation or numerical run."""

from __future__ import annotations

import hashlib
import json
import re
import resource
import time
from pathlib import Path

BASE = Path(__file__).resolve().parent
ROOT = BASE.parents[2]
PRIOR = ROOT / "results/resource_patch_population_20261015/namespace/seed_audit.json"
LOW, HIGH = 52520000, 52540000
PREFIXES = (
    "outputs/resource_patch_population_20261015/",
    "outputs/resource_patch_population_terminal_stage_20261015/",
    "results/resource_patch_population_20261015/",
)


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def read(path):
    return json.loads(Path(path).read_text())


def require(value, message):
    if not value:
        raise ValueError(message)


def numerical_hits(value, native):
    stack, hits = [value], []
    while stack:
        item = stack.pop()
        if isinstance(item, dict):
            stack.extend(item.values())
            stack.extend(item.keys())
        elif isinstance(item, list):
            stack.extend(item)
        elif (isinstance(item, int) and not isinstance(item, bool)) or isinstance(item, str) and item.isdecimal():
            if LOW <= int(item) < HIGH or int(item) in native or int(item) == 53236:
                hits.append(int(item))
    return hits


def main():
    started, cpu = time.monotonic(), time.process_time()
    require(not (BASE / "seed_audit.json").exists(), "first literal classification only")
    data = read(BASE / "candidate_seed_inventory.json")
    require(
        data["status"] == "pending_literal_classification"
        and not data["reserved"]
        and data["seed_blocks"] == [[52520000, 52530000], [52530000, 52540000]]
        and data["endpoint_seeds"] == list(range(52520000, 52520032))
        and data["confirmation_seeds"] == list(range(52530000, 52530512))
        and data["native_seed"] == 53236
        and data["unique_native_ids"] == 564,
        "exact depth candidate schedules required",
    )
    require(sha(BASE / "audit_namespace.py") == data["script_sha256"], "scanner source changed")
    native = set(data["native_life_seeds"])
    require(len(native) == 564 and not any(LOW <= value < HIGH for value in native), "disjoint native schedule")
    require(not data["NPZ_matches"] and not data["JSON_errors"], "no actual collision or unreadable JSON allowed")
    for name, digest in data["native_source_pins"].items():
        require(sha(ROOT / name) == digest, "native schedule source changed")
    historical = data["prior_inventory_pins"]
    for name, digest in historical.items():
        require(sha(ROOT / name) == digest, "historical seed inventory changed")
    manifest = read(PRIOR.parents[1] / "manifest.json")
    require(sha(PRIOR) == manifest["files"]["namespace/seed_audit.json"]["sha256"], "accepted fixture review changed")
    old = read(PRIOR)
    require(old["status"] == "passed" and old["unresolved_NPZ_errors"] == 0, "accepted prior fixture classification")
    known = {item["path"]: item for item in old["classified_legacy_fixture_errors"]}
    errors = []
    for item in data["NPZ_errors"]:
        path = item["path"]
        previous = known[path]
        current = data["changed_npz_records"][path]
        require(
            item["synthetic_fixture"]
            and any(part.startswith("test_") for part in Path(path).parts)
            and current["stat"] == previous["prior_stat"]
            and sha(ROOT / path) == previous["sha256"]
            and (ROOT / path).stat().st_size == previous["bytes"],
            "changed or unknown unreadable NPZ: " + path,
        )
        errors.append(previous)
    require({item["path"] for item in errors} == set(known), "exact prior literal fixture error coverage")
    json_classes = []
    allowed = {"whole_block_half_open.1", "seed_blocks.0.1", "checks.namespace.block_half_open.1"}
    for name, digest in data["JSON_source_pins"].items():
        require(sha(ROOT / name) == digest, "JSON declaration changed")
    for item in data["JSON_hits"]:
        require(
            item["path"].startswith(PREFIXES) and item["value"] == LOW and item["field"] in allowed,
            "unclassified JSON declaration: " + str(item),
        )
        json_classes.append(dict(item, classification="exclusive upper endpoint of preceding block 151"))
    require(sha(BASE / "candidate_text_matches.txt") == data["text_matches_sha256"], "retained text hits changed")
    text_classes, text_pins = [], {}
    for line in (BASE / "candidate_text_matches.txt").read_text().splitlines():
        path, number, source = line.split(":", 2)
        number = int(number)
        require((ROOT / path).read_text().splitlines()[number - 1] == source, "text declaration changed")
        text_pins[path] = sha(ROOT / path)
        compact = source.replace(" ", "").replace("_", "")
        if path.startswith(PREFIXES) and "52510000,52520000" in compact:
            kind = "preceding block 151 has exclusive upper endpoint 52520000"
        elif path.startswith(PREFIXES) and path.endswith("/namespace/audit_namespace.py") and "|52520000)" in source:
            kind = "preceding audit search pattern, not an assignment"
        elif (
            path.endswith(("/ARCHIVE.md", "/archive_terminal.py"))
            and "[prelaunch/manifest.json](prelaunch/manifest.json) preserves all 153 prepared artifacts;" in source
        ):
            require(
                not numerical_hits(re.findall(r"\b[0-9]+\b", source), native),
                "candidate integer in artifact-count text",
            )
            kind = "153 is the count of prepared artifacts, not a seed or block assignment"
        elif (
            path == "outputs/audit_population_depth_20261015/preregister_text.md"
            and source
            == "The native run seed is **53228**; confirmation uses **52,370,000–52,370,511** (block137). Its 152 native IDs"
        ):
            kind = "152 counts derived IDs for native seed 53228; block 137 is disjoint"
        elif path.startswith("outputs/openhr/switching/") and re.search(r"\bblock 15[23]\b", source):
            require(not re.search(r"525[23][0-9]{4}|53[_,]?236", source), "actual new namespace in old label text")
            kind = "older 43-million-base block 152/153; actual IDs remain below 44,532,000"
        elif path.endswith(("/atlas/atlas.html", "/atlas/atlas_play.html")):
            match = re.fullmatch(r'<script type="application/json" id="atlas-data">(.*)</script>', source)
            require(
                match is not None and not numerical_hits(json.loads(match.group(1)), native),
                "actual candidate ID or unknown atlas encoding",
            )
            kind = "formatted-number regex matches array syntax; parsed JSON has no candidate integer"
        else:
            raise ValueError("unclassified text reference: " + path + ":" + str(number))
        text_classes.append(dict(path=path, line=number, classification=kind))
    chain = (
        "outputs/openhr/harness/harness.py",
        "outputs/openhr/switching/swlib.py",
        "outputs/openhr/switching/score2.py",
        "src/life/analysis.py",
    )
    require(
        "SEED_BASE = 43_000_000" in (ROOT / chain[0]).read_text()
        and "SEED_BASE + 10_000 * block" in (ROOT / chain[0]).read_text()
        and "return H.seeds(n, block, first)" in (ROOT / chain[1]).read_text()
        and "flip_from0=152" in (ROOT / chain[2]).read_text()
        and "flip_cue=153" in (ROOT / chain[2]).read_text()
        and "return [seed0 + s for s in range(first, lives)]" in (ROOT / chain[3]).read_text(),
        "old block label numerical source chain differs",
    )
    result = dict(
        status="passed",
        reserved=False,
        registered=False,
        source_revision=data["source_revision"],
        native_seed=53236,
        native_life_seeds=data["native_life_seeds"],
        native_records=data["native_records"],
        unique_native_ids=564,
        endpoint_seeds=data["endpoint_seeds"],
        confirmation_seeds=data["confirmation_seeds"],
        seed_blocks=data["seed_blocks"],
        inventory_sha256=sha(BASE / "candidate_seed_inventory.json"),
        source_sha256=sha(Path(__file__)),
        source_audit_sha256=data["script_sha256"],
        native_source_pins=data["native_source_pins"],
        historical_inventory_references=historical,
        prior_fixture_review_sha256=sha(PRIOR),
        classified_legacy_fixture_errors=errors,
        unresolved_NPZ_errors=0,
        original_NPZ_error_count=len(errors),
        actual_seed_collisions=0,
        JSON_classification=json_classes,
        text_classification=text_classes,
        text_source_pins=text_pins,
        older_label_source_pins={name: sha(ROOT / name) for name in chain},
        simulation_calls=0,
        engine_builds=0,
        genetic_draws=0,
        scope="Recorded NPZ seed payloads and numeric JSON/embedded JSON declarations, plus literal text review.",
        intentional_reuse="Native rechecks share fixed generation IDs; half-duration observations repeat two final IDs. Startup replays retained fixtures.",
        resources=dict(
            cpu_seconds=time.process_time() - cpu,
            wall_seconds=time.monotonic() - started,
            peak_rss_bytes=resource.getrusage(resource.RUSAGE_SELF).ru_maxrss * 1024,
        ),
    )
    with (BASE / "seed_audit.json").open("x") as stream:
        json.dump(result, stream, indent=2)
        stream.write("\n")
    print(
        json.dumps(
            dict(
                status="passed",
                native_ids=564,
                endpoint_seeds=32,
                confirmation_seeds=512,
                actual_seed_collisions=0,
                classified_legacy_fixture_errors=len(errors),
                JSON_references=len(json_classes),
                text_references=len(text_classes),
                reserved=False,
                simulation_calls=0,
                resources=result["resources"],
            )
        )
    )


if __name__ == "__main__":
    main()
