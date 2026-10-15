from pathlib import Path
import ast
STUDY = Path('outputs/autonomous_occlusion_acquisition_20261015')

def replace_function(path, name, value):
    text = path.read_text()
    node = next(n for n in ast.parse(text).body if isinstance(n, ast.FunctionDef) and n.name == name)
    lines = text.splitlines(keepends=True)
    path.write_text(''.join(lines[:node.lineno-1]) + value.strip() + '\n' + ''.join(lines[node.end_lineno:]))

replace_function(STUDY/'measure.py', 'freeze_endpoints', '''
def freeze_endpoints(protocol, identity):
    """Bind the prescribed midpoint and final rank-zero genomes before confirmation."""
    import numpy as np
    from native_replay import first_cohort
    from omegaconf import OmegaConf
    from population_loader import extended_identity as population_identity
    from population_loader import loader_identity
    from selection import extended_identity as selection_identity
    from selection import selection_identity as selection_config

    from src import checkpoint
    from src.genome import Layout

    reference = protocol["reference"]
    if reference["role"] != ROLES[0] or sha(STUDY / reference["path"]) != reference["file_sha256"]:
        raise ValueError("fixed starting reference differs")
    folder = STUDY / "runs/acquisition"
    cfg = OmegaConf.load(STUDY / protocol["configs"]["acquisition"]["path"])
    population = loader_identity(protocol["population_start"])
    selection = selection_config("acquisition", protocol["selection_worlds"])
    if (OmegaConf.to_container(cfg.population_start, resolve=True) != population
            or OmegaConf.to_container(cfg.retention_selection, resolve=True) != selection):
        raise ValueError("configured external identities differ")
    extended = selection_identity(population_identity(identity, population), selection)
    if read(folder / "determinism.json") != extended:
        raise ValueError("search numerical/source identity differs")
    marker = read(folder / "search_complete.json")
    if (marker["status"] != "complete" or marker["protocol_sha256"] != sha(STUDY / "protocol.json")
            or marker["release_sha256"] != sha(STUDY / "release.json")
            or any(sha(folder / name) != digest for name, digest in marker["output_pins"].items())):
        raise ValueError("completed search artifacts differ")
    records = {}
    paths = [STUDY / reference["path"]]
    for generation, subfolder in ((4, folder / "generation4"), (8, folder)):
        saved = checkpoint.load(subfolder / "checkpoint.pt")
        checkpoint.validate(saved, cfg, extended)  # Captured identity, no extra golden calls.
        state = saved["state"]
        health = validate_search_state(state, generation)
        if (state["evals"] != generation * 256 or state["rc_lives"] != generation * 512
                or tuple(state["population"].shape) != (32, 875)):
            raise ValueError("prescribed checkpoint population/counts differ")
        if set(saved["logs"]) != {"curves.jsonl", "lineage.jsonl", "clones.jsonl"}:
            raise ValueError("checkpoint log coverage differs")
        for name, pin in saved["logs"].items():
            data = (folder / name).read_bytes()
            prefix = data[:pin["bytes"]]
            if (len(prefix) != pin["bytes"] or hashlib.sha256(prefix).hexdigest() != pin["sha256"]
                    or (generation == 8 and len(data) != pin["bytes"])):
                raise ValueError("checkpoint log prefix differs")
        path = subfolder / "best_genome.json"
        endpoint_layout, genome = Layout.load(path)
        if genome.numpy().tobytes() != state["population"][0].numpy().tobytes():
            raise ValueError("prescribed endpoint differs from checkpoint rank zero")
        record = {"generation": generation, "rank": 0, "rank_zero_id": int(state["ids"][0]),
                  "search_health": health, "checkpoint_sha256": sha(subfolder / "checkpoint.pt"),
                  "log_prefix_pins": saved["logs"], "genome_file_sha256": sha(path),
                  "genome_raw_sha256": raw_sha(genome.numpy()),
                  "population_raw_sha256": raw_sha(state["population"].numpy()),
                  "numerical_identity": extended}
        if generation == 4:
            snapshot = read(subfolder / "snapshot.json")
            expected = {"status": "complete", "generation": 4, "rank": 0,
                        "rank_zero_id": record["rank_zero_id"],
                        "checkpoint_sha256": record["checkpoint_sha256"],
                        "genome_file_sha256": record["genome_file_sha256"],
                        "genome_raw_sha256": record["genome_raw_sha256"],
                        "population_raw_sha256": record["population_raw_sha256"],
                        "identity": extended, "log_prefix_pins": saved["logs"],
                        "protocol_sha256": sha(STUDY / "protocol.json"),
                        "release_sha256": sha(STUDY / "release.json"),
                        "added_lives": 0, "random_draws": 0}
            if snapshot != expected or marker["midpoint"] != snapshot:
                raise ValueError("passive midpoint snapshot differs")
            record["snapshot_sha256"] = sha(subfolder / "snapshot.json")
        else:
            public = read(folder / "population.json")
            rows = np.stack([endpoint_layout.from_dict(p).numpy() for p in public["genomes"]])
            if (rows.shape != (32, 875) or rows.tobytes() != state["population"].numpy().tobytes()
                    or public["ids"] != state["ids"].tolist()
                    or public["fitness"] != state["fitness"].tolist()):
                raise ValueError("public final population differs from checkpoint")
            record.update(population_file_sha256=sha(folder / "population.json"),
                          determinism_sha256=sha(folder / "determinism.json"),
                          results_sha256=sha(folder / "results.jsonl"))
        records[generation] = record
        paths.append(path)
    loaded = [Layout.load(path) for path in paths]
    layout = loaded[0][0]
    if any(other.dims != layout.dims for other, _ in loaded):
        raise ValueError("confirmation genome layouts differ")
    genomes = np.stack([genome.numpy() for _, genome in loaded])
    if genomes.shape != (3, 875) or genomes.dtype != np.float32 or not np.isfinite(genomes).all():
        raise ValueError("three exact BODY-1 genotypes required")
    if raw_sha(genomes[0]) != reference["raw_sha256"]:
        raise ValueError("starting reference raw bytes differ")
    genotypes = [{"role": role, "path": str(path.relative_to(STUDY)),
                  "file_sha256": sha(path), "raw_sha256": raw_sha(genome)}
                 for role, path, genome in zip(ROLES, paths, genomes)]
    replay = first_cohort(STUDY, protocol)  # Recorded operations only: no RNG, builds or lives.
    save(STUDY / "first_cohort_replay.json", replay, exclusive=True)
    manifest = {"protocol_sha256": sha(STUDY / "protocol.json"), "roles": list(ROLES),
                "genomes": genotypes, "searches": {"acquisition": records[8]}, "midpoint": records[4],
                "first_cohort_replay_sha256": sha(STUDY / "first_cohort_replay.json"),
                "selection": "Generation4 and generation8 population rank0 endpoints fixed before confirmation; final is never replaced by midpoint."}
    save(STUDY / "endpoints.json", manifest, exclusive=True)
    return layout, genomes, manifest
''')
replace_function(STUDY/'analyze.py', 'verdicts', '''
def verdicts(rows):
    primary = describe(rows["blink80_20"][ROLES[2]]["captures"] - rows["blink80_20"][ROLES[0]]["captures"])
    own_start = {role: {world: describe(rows[world][role]["captures"] - rows[world][ROLES[0]]["captures"])
                        for world in WORLDS} for role in ROLES[1:]}
    return {"primary_generation8_minus_start_blink80_20_captures": primary,
            "primary_capture_gain_above_3se": primary["lower_3se"] > 0,
            "checkpoint_minus_start_captures": own_start,
            "confirmation_capture_value": 500, "independent_evolutionary_runs": 1,
            "interpretation": "One uninterrupted acquisition trajectory; midpoint and final are fixed. It does not establish a curriculum or depth advantage, broad generalization, or richer computation."}
''')
# Exact reviewed aggregate-count definition; no binomial SE or extra paired arrays.
accuracy = Path('outputs/audit_capture_value_selection_20261015/terminal_review/accuracy_supplement.py').read_text()
node = next(n for n in ast.parse(accuracy).body if isinstance(n, ast.FunctionDef) and n.name == 'describe_counts')
body = '\n'.join(accuracy.splitlines()[node.lineno-1:node.end_lineno])
p = STUDY/'analyze.py'
s = p.read_text().replace('\ndef verdicts(rows):', '\n'+body+'\n\n\ndef verdicts(rows):')
s = s.replace('"contrasts": differences, "retention": retention,', '"capture_accuracy": {w: {r: describe_counts(rows[w][r]["captures"], rows[w][r]["misses"], rows[w][r]["clicks"])\n                                    for r in ROLES} for w in WORLDS},\n        "accuracy_limit": "Aggregate captures/clicks across lives; null with no clicks, no binomial standard error. Lives are the sampling unit.",\n        "contrasts": differences, "retention": retention,')
p.write_text(s)
