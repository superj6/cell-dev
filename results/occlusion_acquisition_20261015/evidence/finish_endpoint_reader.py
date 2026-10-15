from pathlib import Path
import ast
p=Path('outputs/autonomous_occlusion_acquisition_20261015/analyze.py')
def put(name, value):
 s=p.read_text();n=next(n for n in ast.parse(s).body if isinstance(n,ast.FunctionDef) and n.name==name);lines=s.splitlines(keepends=True)
 p.write_text(''.join(lines[:n.lineno-1])+value.strip()+'\n'+''.join(lines[n.end_lineno:]))
put('verify_endpoints', '''
def verify_endpoints(base, protocol, identity):
    manifest = read(base / "endpoints.json")
    if (manifest["protocol_sha256"] != sha(base / "protocol.json") or manifest["roles"] != list(ROLES)
            or set(manifest["searches"]) != set(ARMS) or len(manifest["genomes"]) != 3
            or manifest["selection"] != "Generation4 and generation8 population rank0 endpoints fixed before confirmation; final is never replaced by midpoint."):
        raise ValueError("frozen endpoint matrix differs")
    expected_paths = [protocol["reference"]["path"], "runs/acquisition/generation4/best_genome.json",
                      "runs/acquisition/best_genome.json"]
    for role, rec, path in zip(ROLES, manifest["genomes"], expected_paths):
        if (rec["role"] != role or rec["path"] != path or sha(local(base, path)) != rec["file_sha256"]
                or hashlib.sha256(json_genome(local(base, path)).tobytes()).hexdigest() != rec["raw_sha256"]):
            raise ValueError("frozen endpoint genome bytes differ")
    if manifest["genomes"][0]["raw_sha256"] != protocol["reference"]["raw_sha256"]:
        raise ValueError("starting reference changed")
    arm = "acquisition"
    folder, record = base / "runs" / arm, manifest["searches"][arm]
    paths = {"checkpoint_sha256": "checkpoint.pt", "genome_file_sha256": "best_genome.json",
             "population_file_sha256": "population.json", "determinism_sha256": "determinism.json",
             "results_sha256": "results.jsonl"}
    if any(sha(folder / path) != record[key] for key, path in paths.items()):
        raise ValueError("search artifact changed after endpoint freeze")
    log_names = {"curves.jsonl", "lineage.jsonl", "clones.jsonl"}
    if set(record["log_prefix_pins"]) != log_names:
        raise ValueError("native checkpoint log coverage differs")
    for name, pin in record["log_prefix_pins"].items():
        if sha(folder / name) != pin["sha256"] or (folder / name).stat().st_size != pin["bytes"]:
            raise ValueError("final checkpoint full log size/hash differs")
    curves, lineage = json_lines(folder / "curves.jsonl"), json_lines(folder / "lineage.jsonl")
    if ([r["gen"] for r in curves] != list(range(8))
            or [r["gen"] for r in curves if "valid" in r] != [0, 4, 7]
            or len(lineage) != 9 or lineage[0]["ids"] != list(range(32)) or lineage[0]["copies"]):
        raise ValueError("eight-generation native history/import differs")
    keys = ("pop_invalid", "pop_mismatch", "recheck_invalid")
    if any(not math.isfinite(float(r[k])) or float(r[k]) != 0 for r in curves for k in keys):
        raise ValueError("nonzero native invalid/mismatch summaries")
    health = {key: max(float(row[key]) for row in curves) for key in keys}
    if record["search_health"] != health or record["generation"] != 8 or record["rank"] != 0:
        raise ValueError("search health or endpoint selection differs")
    population = read(folder / "population.json")
    table = np.stack([json_genome({"dims": population["dims"], "params": value}) for value in population["genomes"]])
    fitness = np.asarray(population["fitness"], dtype=np.float64)
    if (table.shape != (32, 875) or fitness.shape != (32,) or not np.isfinite(fitness).all()
            or np.any(fitness[:-1] < fitness[1:]) or len(set(population["ids"])) != 32
            or population["ids"] != lineage[-1]["survivors"] or population["fitness"] != lineage[-1]["fitness"]
            or record["rank_zero_id"] != population["ids"][0]
            or hashlib.sha256(table.tobytes()).hexdigest() != record["population_raw_sha256"]
            or hashlib.sha256(table[0].tobytes()).hexdigest() != record["genome_raw_sha256"]
            or record["genome_raw_sha256"] != manifest["genomes"][2]["raw_sha256"]):
        raise ValueError("full final population or ordinary rank-zero endpoint differs")
    extended = record["numerical_identity"]
    configured_population = {"version": 1, **protocol["population_start"], "source_pins": {
        name: sha(base / name) for name in ("population_loader.py", "search.py")}}
    if (extended.get("population_start") != configured_population
            or {k: v for k, v in extended.items() if k not in ("population_start", "retention_selection")} != identity
            or read(folder / "determinism.json") != extended):
        raise ValueError("search base/loader startup identity differs")
    expected_selection = {"version": 1, "arm": arm, "worlds": protocol["selection_worlds"],
        "rule": "gen fixed 2pool/2persistent/4blink80_20 per8 repeated for recheck; diagnostics=persistent neutral; R_cap500",
        "pattern": ["pool", "persistent", "blink80_20", "blink80_20"] * 2,
        "source_pins": {"selection.py": sha(base / "selection.py")}}
    if extended["retention_selection"] != expected_selection:
        raise ValueError("selection-arm/source/world identity differs")
    marker = read(folder / "search_complete.json")
    names = {"checkpoint.pt", "config.yaml", "determinism.json", "curves.jsonl", "lineage.jsonl",
             "population.json", "best_genome.json", "results.jsonl", "search_startup.json",
             "generation4/checkpoint.pt", "generation4/best_genome.json", "generation4/snapshot.json"}
    if (marker["status"] != "complete" or marker["arm"] != arm
            or marker["research_lives"] != 20534 or marker["startup_lives"] != 4
            or marker["protocol_sha256"] != sha(base / "protocol.json")
            or marker["release_sha256"] != sha(base / "release.json")
            or marker["count_proof"] != {"selection": 20480, "valid": 48, "final": 6,
                "half_duration": 2, "native_evals": 2560, "generations": 8,
                "children_per_generation": 224, "midpoint_added_lives": 0}
            or set(marker["output_pins"]) != names
            or any(sha(folder / name) != digest for name, digest in marker["output_pins"].items())
            or marker["checkpoint_log_pins"] != record["log_prefix_pins"]):
        raise ValueError("native search completion provenance/counts differ")
    for g, (curve, line) in enumerate(zip(curves, lineage[1:])):
        if (curve["evals"] != 320 * (g + 1) or curve["recheck_k"] != 64 or line["gen"] != g
                or len(line["children"]) != 224 or len(line["seeds"]) != 8
                or len(line["recheck"]["seeds"]) != 8 or len(line["recheck"]["ids"]) != 64
                or len(line["survivors"]) != 32 or len(set(line["survivors"])) != 32
                or not all(math.isfinite(float(curve[k])) for k in ("fitness", "mean_fitness", "pop_guard"))):
            raise ValueError("native generation evaluation counts/finiteness differ")
    for key in (*keys, "pop_guard"):
        if marker["health"][key] != [r[key] for r in curves]:
            raise ValueError("recorded native health differs")
    diagnostic = json_lines(folder / "results.jsonl")
    if len(diagnostic) != 1 or any(diagnostic[0][k] != v for k, v in {
            "seed": protocol["native_seed"], "abi": 4, "generations": 8, "evals": 2560,
            "lives": 2, "founders_sampled": 0, "top_best_rank": 0,
            "invalid_lives": 0, "mismatch_lives": 0, "forks": {}, "heldout_score": None}.items()):
        raise ValueError("native final diagnostic scope or health differs")
    mid = manifest["midpoint"]
    snapshot = read(folder / "generation4/snapshot.json")
    expected_snapshot = {"status": "complete", "generation": 4, "rank": 0,
        "rank_zero_id": lineage[4]["survivors"][0],
        "checkpoint_sha256": sha(folder / "generation4/checkpoint.pt"),
        "genome_file_sha256": manifest["genomes"][1]["file_sha256"],
        "genome_raw_sha256": manifest["genomes"][1]["raw_sha256"],
        "population_raw_sha256": mid["population_raw_sha256"], "identity": extended,
        "log_prefix_pins": mid["log_prefix_pins"], "protocol_sha256": sha(base / "protocol.json"),
        "release_sha256": sha(base / "release.json"), "added_lives": 0, "random_draws": 0}
    expected_mid = {"generation": 4, "rank": 0, "rank_zero_id": expected_snapshot["rank_zero_id"],
        "search_health": {k: max(float(r[k]) for r in curves[:4]) for k in keys},
        "checkpoint_sha256": expected_snapshot["checkpoint_sha256"],
        "log_prefix_pins": expected_snapshot["log_prefix_pins"],
        "genome_file_sha256": expected_snapshot["genome_file_sha256"],
        "genome_raw_sha256": expected_snapshot["genome_raw_sha256"],
        "population_raw_sha256": expected_snapshot["population_raw_sha256"],
        "numerical_identity": extended, "snapshot_sha256": sha(folder / "generation4/snapshot.json")}
    if snapshot != expected_snapshot or marker["midpoint"] != snapshot or mid != expected_mid:
        raise ValueError("generation4 passive snapshot identity/role/rank differs")
    if set(mid["log_prefix_pins"]) != log_names:
        raise ValueError("midpoint native prefix coverage differs")
    prefix_rows = {}
    for name, pin in mid["log_prefix_pins"].items():
        if type(pin["bytes"]) is not int or pin["bytes"] < 0:
            raise ValueError("invalid midpoint prefix length")
        with (folder / name).open("rb") as stream:
            prefix = stream.read(pin["bytes"])
        if len(prefix) != pin["bytes"] or hashlib.sha256(prefix).hexdigest() != pin["sha256"]:
            raise ValueError("midpoint checkpoint no longer matches native log prefix")
        prefix_rows[name] = [json.loads(line) for line in prefix.decode().splitlines() if line.strip()]
    if prefix_rows["curves.jsonl"] != curves[:4] or prefix_rows["lineage.jsonl"] != lineage[:5]:
        raise ValueError("midpoint logs do not end at the prescribed generation")
    proof = read(base / "first_cohort_replay.json")
    if (sha(base / "first_cohort_replay.json") != manifest["first_cohort_replay_sha256"]
            or proof["status"] != "passed" or proof["protocol_sha256"] != sha(base / "protocol.json")
            or proof["initial_rows"] != 32 or proof["offspring_per_arm"] != 224
            or proof["initial_population_raw_sha256"] != protocol["population_start"]["population_raw_sha256"]
            or proof["initial_row_sha256"] != protocol["population_start"]["row_sha256"]
            or proof["recorded_first_256_replayed"] is not True
            or proof["simulated_lives"] != 0 or proof["random_draws"] != 0 or set(proof["runs"]) != set(ARMS)):
        raise ValueError("first-cohort replay proof differs")
    signature = [{k: child[k] for k in ("id", "pa", "pb", "mask", "ops")} for child in lineage[1]["children"]]
    digest = hashlib.sha256(json.dumps(signature, sort_keys=True, separators=(",", ":"), allow_nan=False).encode()).hexdigest()
    item = proof["runs"][arm]
    if (item["genetic_signature_sha256"] != digest or item["lineage_sha256"] != sha(folder / "lineage.jsonl")
            or len(item["candidate_row_sha256"]) != 256
            or item["candidate_row_sha256"][:32] != proof["initial_row_sha256"]):
        raise ValueError("first-cohort signature/raw-row proof differs")
    return manifest, {"searches": {arm: {"generation": 8, "rank": 0, "health": health,
                          "guards_retained": marker["health"]["pop_guard"], "count_proof": marker["count_proof"]}},
                      "midpoint_generation": 4, "midpoint_added_lives": 0,
                      "first_256_raw_rows_replayed_before_confirmation": True,
                      "limitation": "NumPy reader binds midpoint/final checkpoint hashes, JSON rank0 bytes and native log prefixes. Full checkpoint population/genetic/ranking replay is separate; raw search ledgers are not complete."}
''')
# Startup verification applies the same exact standard/truth fixture to each of the two workers.
put('verify_startup', '''
def verify_startup(base, protocol):
    expected_identity = read(base / "inputs/startup_identity.json")["identity"]
    fixture = read(base / "inputs/visibility_truth.json")
    ledger = np.asarray([fixture["ledger"]], dtype=np.float64)
    hashes = np.asarray([[int(value, 16) for value in fixture["hashes"]]], dtype=np.uint64)
    expected_truth = {"name": fixture["name"], "seed": fixture["seed"], "lives": 2,
                      "ledger_sha256": hashlib.sha256(ledger.tobytes()).hexdigest(),
                      "hashes_sha256": hashlib.sha256(hashes.tobytes()).hexdigest()}
    if expected_truth["name"] != "body0_renewal_55040000" or expected_identity["golden"]["all"] != "ebb3ad6fcad2d938":
        raise ValueError("retained ABI3/ABI4 truth fixtures differ")
    receipts = {}
    for phase, path in (("confirmation", "startup.json"), ("acquisition", "runs/acquisition/search_startup.json")):
        receipt = read(base / path)
        if receipt != {"protocol_sha256": sha(base / "protocol.json"), "startup_lives": 4,
                       "identity": expected_identity, "visibility": expected_truth}:
            raise ValueError("four-call startup identity/truth differs: " + phase)
        receipts[phase] = receipt
    library_hashes = {sha(path) for path in (base / "build-cache").rglob("*.so")}
    if not set(expected_identity["kernels"].values()).issubset(library_hashes):
        raise ValueError("retained compiled library bytes do not bind startup identity")
    return {**receipts["confirmation"], "search_startup": receipts["acquisition"], "total_startup_lives": 8}
''')
