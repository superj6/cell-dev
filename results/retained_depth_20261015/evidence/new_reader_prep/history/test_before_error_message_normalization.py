"""AO changed coverage/decision rules; no inputs, draws, engines or file fixture tree."""

import ast
import copy
import hashlib
import importlib.util
import json
import sys
from pathlib import Path
import numpy as np
import pytest

ROOT = next(p for p in Path(__file__).resolve().parents if (p / "src/life/spec.py").is_file())
STUDY = ROOT / "outputs/autonomous_retained_depth_20261015"
AN = ROOT / "outputs/autonomous_occlusion_acquisition_20261015"


def load(name, path):
    spec = importlib.util.spec_from_file_location(name, path)
    result = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(result)
    return result


M = load("ao_reader", STUDY / "analyze.py")


def functions(path):
    return {n.name: n for n in ast.parse(path.read_text()).body if isinstance(n, ast.FunctionDef)}


def rows():
    fixture = load(
        "retained_test_row", ROOT / "outputs/cumulative_capability_20261015/design/test_retention_analyze.py"
    )
    values, _ = M.reconstruct(*fixture.row(n=512))
    return {w: {r: copy.deepcopy(values) for r in M.ROLES} for w in M.WORLDS}


def flat_captures(data, value=10.0):
    for world in M.WORLDS:
        for role in M.ROLES:
            data[world][role]["captures"][:] = value


def test_unchanged_physics_and_truth():
    for filename, names in [
        (
            "analyze.py",
            (
                "identical",
                "stats",
                "prices",
                "physical_costs",
                "validate_row",
                "reconstruct",
                "json_genome",
                "describe_counts",
                "contrasts",
                "retention_diagnostics",
            ),
        ),
        ("measure.py", ("parent_check", "check_visibility_truth")),
    ]:
        old, new = functions(AN / filename), functions(STUDY / filename)
        assert all(ast.dump(old[k]) == ast.dump(new[k]) for k in names)


def test_all11967_vectors_covariance_and_duplicates():
    data = rows()
    assert len(M.PAIRS) == 15 and len(set(M.PAIRS)) == 15
    noise = np.arange(512, dtype=np.float64)
    data["persistent"]["balanced24"]["captures"] += noise
    data["turn100_blink80_20"]["balanced24"]["captures"] += noise + 2
    report, arrays = M.contrasts(data)
    margins, retention = M.retention_diagnostics(data)
    assert (len(report), len(arrays), len(margins), len(retention)) == (159, 11925, 21, 42)
    assert len(set(arrays) | set(retention)) == 11967
    key = "interaction__turn100_blink80_20_minus_persistent__balanced24_minus_AN_start"
    np.testing.assert_array_equal(arrays[key + "__captures"], np.full(512, 2.0))
    assert report[key]["captures"]["se"] == 0
    np.testing.assert_array_equal(arrays["within__pool__unchanged8_minus_AM_reference__captures"], np.zeros(512))
    expected = {(i, 1, w) for i in range(2, 6) for w in ("pool", "persistent", "blink80_20")}
    expected |= {(i, 0, w) for i in range(2, 6) for w in ("pool", "persistent")}
    expected.add((5, 3, "blink80_20"))
    assert set(M.RETENTION) == expected


def test_joint_claim_requires_both_and_discloses_actual_blink_loss():
    data = rows()
    flat_captures(data, 10.0)
    data["pool"]["balanced24"]["captures"][:] = 11
    data["blink80_20"]["balanced24"]["captures"][:] = 9.5
    result = M.verdicts(data)
    assert result["joint_primary_passes"]
    assert result["primary_blink80_20_actual_capture_difference"]["mean"] == -0.5
    assert result["primary_blink80_20_ninety_percent_noninferiority"]["mean"] == 0.5
    data["blink80_20"]["balanced24"]["captures"][:] = 9
    assert not M.verdicts(data)["joint_primary_passes"]
    data["blink80_20"]["balanced24"]["captures"][:] = 10
    data["pool"]["balanced24"]["captures"][:] = 10
    assert not M.verdicts(data)["joint_primary_passes"]


def test_unrounded_three_se_blink_margin():
    data = rows()
    flat_captures(data, 10.0)
    data["pool"]["balanced24"]["captures"][:] = 11
    noise = np.tile([-1.0, 1.0], 256)
    boundary = 3 * M.stats(noise)["se"]
    data["blink80_20"]["balanced24"]["captures"] = 9 + noise + boundary + 1e-10
    assert M.verdicts(data)["joint_primary_passes"]
    data["blink80_20"]["balanced24"]["captures"] -= 2e-10
    assert not M.verdicts(data)["joint_primary_passes"]


def test_fixed_reference_checkpoint_order_and_single_confirmation_identity(monkeypatch):
    monkeypatch.syspath_prepend(str(STUDY))
    worker = load("ao_measure", STUDY / "measure.py")
    assert worker.ROLES == M.ROLES and worker.ARMS == M.ARMS
    for generation in (8, 24):
        state = {
            "generation": generation,
            "curves": [dict(gen=g, pop_invalid=0, pop_mismatch=0, recheck_invalid=0) for g in range(generation)],
        }
        worker.validate_search_state(state, generation)
        with pytest.raises(ValueError):
            worker.validate_search_state(state, 4)
    f = functions(STUDY / "measure.py")["freeze_endpoints"]
    refs = next(
        n.value
        for n in f.body
        if isinstance(n, ast.Assign) and any(isinstance(t, ast.Name) and t.id == "references" for t in n.targets)
    )
    assert [x.slice.value for x in refs.elts] == ["ancestral_reference", "reference"]
    t = ast.parse((STUDY / "measure.py").read_text())
    assert (
        sum(
            isinstance(n, ast.Call) and isinstance(n.func, ast.Attribute) and n.func.attr == "numerical_identity"
            for n in ast.walk(t)
        )
        == 1
    )
    assert not any(n.startswith(("src.life.build", "src.run", "src.evolve")) for n in sys.modules)


def terminal_fixture(monkeypatch):
    base = Path("/synthetic_AO")
    docs = {}

    def put(name, value):
        docs[str(base / name)] = value

    def digest(path):
        return hashlib.sha256(json.dumps(docs[str(path)], sort_keys=True).encode()).hexdigest()

    monkeypatch.setattr(M, "read", lambda path: copy.deepcopy(docs[str(path)]))
    monkeypatch.setattr(M, "sha", digest)
    namespace = "pid:[4026531836]"
    budget_spec = {
        "cpu_seconds": 28800,
        "wall_seconds": 14400,
        "search_cpu_seconds": 24000,
        "confirmation_cpu_seconds": 4800,
        "threads": 2,
        "workers": 1,
        "cleanup_margin_seconds": 10,
        "rss_bytes": 4 * 1024**3,
        "minimum_available_bytes": 4 * 1024**3,
        "address_space_bytes": 8 * 1024**3,
    }
    protocol = {"budget": budget_spec}
    put("protocol.json", protocol)
    pd = digest(base / "protocol.json")
    put("release.json", {"status": "released", "protocol_sha256": pd, "pid_namespace": namespace})
    rd = digest(base / "release.json")
    monitor = {"pid": 100, "ppid": 90, "pgid": 100, "start_ticks": 1000}
    phases = (*M.ARMS, "confirmation")
    commands = {p: ["python", p] for p in phases}
    put(
        "attempt.json",
        {
            "monitor": monitor,
            "pid_namespace": namespace,
            "protocol_sha256": pd,
            "release_sha256": rd,
            "commands": commands,
            "budget": budget_spec,
        },
    )
    cleanup = {
        "pid_namespace": namespace,
        "checked_in_monitor": True,
        "same_pid_namespace": True,
        "all_owned_groups_exited": True,
        "all_worker_identities_exited": True,
        "remaining_group_members": [],
        "remaining_worker_identities": [],
        "remaining_descendants": [],
    }
    workers, all_receipts, records = [], [], {}
    for i, phase in enumerate(phases):
        worker = {"pid": 101 + i, "ppid": 100, "pgid": 101 + i, "start_ticks": 1001 + i, "name": phase}
        workers.append(worker)
        cap = 24000 if i < 2 else 5010
        pb = {
            "cpu_seconds": cap,
            "wall_seconds": 14400 - i * 100,
            "threads": 2,
            "workers": 1,
            "cleanup_margin_seconds": 10,
            "rss_bytes": 4 * 1024**3,
            "minimum_available_bytes": 4 * 1024**3,
            "address_space_bytes": 8 * 1024**3,
        }
        put(
            f"execution/{phase}/attempt.json",
            {
                "monitor": monitor,
                "pid_namespace": namespace,
                "protocol_sha256": pd,
                "release_sha256": rd,
                "command": commands[phase],
                "budget": pb,
            },
        )
        receipts = [
            {
                "pid": worker["pid"],
                "wait_status": 0,
                "exit_code": 0,
                "user_cpu_seconds": 45.0,
                "system_cpu_seconds": 5.0,
            }
        ]
        all_receipts.extend(receipts)
        record = {
            "status": "complete",
            "exit_code": 0,
            "worker_exit_code": 0,
            "running": {},
            "queued": [],
            "reason": None,
            "error": None,
            "cleanup_error": None,
            "cpu_seconds": 100 * (i + 1),
            "wall_seconds": 90,
            "cap_cpu_seconds": cap,
            "cap_wall_seconds": pb["wall_seconds"],
            "pid_namespace": namespace,
            "protocol_sha256": pd,
            "release_sha256": rd,
            "attempt_sha256": digest(base / f"execution/{phase}/attempt.json"),
            "process_identities": [{**monitor, "name": "monitor"}, {**worker, "name": "worker"}],
            "owned_process_groups": [worker["pid"]],
            "terminal_cleanup": copy.deepcopy(cleanup),
            "wait4_receipts": receipts,
            "cap_rss_bytes": 4 * 1024**3,
            "minimum_available_bytes": 4 * 1024**3,
            "worker_address_space_bytes": 8 * 1024**3,
            "peak_owned_rss_bytes": 100000,
        }
        name = f"execution/{phase}/budget.json"
        put(name, record)
        records[phase] = {"path": name, "sha256": digest(base / name)}
    global_record = {
        **copy.deepcopy(record),
        "cpu_seconds": 310.0,
        "wall_seconds": 300.0,
        "cap_cpu_seconds": 28800,
        "cap_wall_seconds": 14400,
        "search_cpu_cap": 24000,
        "confirmation_cpu_cap": 4800,
        "search_cpu_seconds": 210.0,
        "confirmation_cpu_seconds": 100.0,
        "phase": "confirmation",
        "attempt_sha256": digest(base / "attempt.json"),
        "process_identities": [{**monitor, "name": "monitor"}, *workers],
        "owned_process_groups": [w["pid"] for w in workers],
        "phase_records": records,
        "wait4_receipts": all_receipts,
    }
    put("budget.json", global_record)
    put("measurement_complete.json", {"fixture": True})
    for arm in M.ARMS:
        put(f"runs/{arm}/search_complete.json", {"fixture": arm})
    put(
        "study_complete.json",
        {
            "status": "complete",
            "research_lives": 138476,
            "startup_lives": 12,
            "total_calls": 138488,
            "protocol_sha256": pd,
            "measurement_complete_sha256": digest(base / "measurement_complete.json"),
            "search_complete_pins": {a: digest(base / f"runs/{a}/search_complete.json") for a in M.ARMS},
        },
    )
    return base, protocol, docs, digest


def test_three_phase_inclusive_caps(monkeypatch):
    base, protocol, docs, digest = terminal_fixture(monkeypatch)
    assert M.verify_terminal(base, protocol)["cpu_seconds"] == 310
    docs[str(base / "budget.json")]["confirmation_cpu_seconds"] = 4800
    with pytest.raises(ValueError):
        M.verify_terminal(base, protocol)


@pytest.mark.parametrize("missing_last_role", [False, True])
def test_exact_thirty_rows(monkeypatch, missing_last_role):
    from contextlib import contextmanager

    base = Path("/synthetic_AM_rows")
    fixture = load(
        "retained_row_schema", ROOT / "outputs/cumulative_capability_20261015/design/test_retention_analyze.py"
    )
    payloads, index, worlds = {}, {}, {}
    for world in M.WORLDS:
        abi = 4 if world in M.WORLDS[2:] else 3
        for i, role in enumerate(M.ROLES):
            raw, rec, seeds = fixture.row(abi=abi, n=512)
            raw.update(
                {
                    k: np.asarray(v)
                    for k, v in {
                        "role": role,
                        "world_name": world,
                        "protocol_sha256": "pin",
                        "genome_raw_sha256": f"genome_{i}",
                        "endpoints_sha256": "pin",
                    }.items()
                }
            )
            name = f"raw/{world}/row_{i:02d}.npz"
            payloads[str(base / name)] = raw
            index[name] = {"sha256": "pin", "lives": 512, "abi": abi, "cpu_seconds": 1.0, "wall_seconds": 0.6}
            worlds[world] = rec
    protocol = {"worlds": worlds, "seeds": seeds}
    endpoints = {"genomes": [{"raw_sha256": f"genome_{i}"} for i in range(6)]}
    complete = {
        "status": "complete",
        "research_lives": 15360,
        "startup_lives": 4,
        "rows": 30,
        "protocol_sha256": "pin",
        "row_index_sha256": "pin",
        "endpoints_sha256": "pin",
    }
    if missing_last_role:
        del index["raw/pool/row_05.npz"]
    monkeypatch.setattr(M, "sha", lambda _: "pin")
    monkeypatch.setattr(M, "read", lambda p: index if p.name == "row_index.json" else complete)
    monkeypatch.setattr(Path, "rglob", lambda _self, _glob: iter(Path(k) for k in payloads))

    class Raw(dict):
        @property
        def files(self):
            return tuple(self)

    @contextmanager
    def load_raw(path, allow_pickle):
        assert allow_pickle is False
        yield Raw(payloads[str(path)])

    monkeypatch.setattr(M.np, "load", load_raw)
    if missing_last_role:
        with pytest.raises(ValueError, match="30-row"):
            M.load_rows(base, protocol, endpoints)
    else:
        values, health, cpu = M.load_rows(base, protocol, endpoints)
        assert cpu == 30
        assert sum(r["all_fitness_rows_retained"] for w in health.values() for r in w.values()) == 15360
        assert all(tuple(values[w]) == M.ROLES for w in M.WORLDS)


@pytest.mark.parametrize("corruption", [None, "missing_search_truth", "extra_search_calls"])
def test_three_startup_receipts(monkeypatch, corruption):
    base = Path("/synthetic_AN_startup")
    ledger = np.zeros((1, 58), dtype=np.float64)
    hashes = np.zeros((1, 5), dtype=np.uint64)
    identity = {"golden": {"all": "ebb3ad6fcad2d938"}, "kernels": {"full": "library", "fast": "library"}}
    fixture = {"name": "body0_renewal_55040000", "seed": 55040000, "ledger": ledger[0].tolist(), "hashes": ["0"] * 5}
    truth = {
        "name": fixture["name"],
        "seed": fixture["seed"],
        "lives": 2,
        "ledger_sha256": hashlib.sha256(ledger.tobytes()).hexdigest(),
        "hashes_sha256": hashlib.sha256(hashes.tobytes()).hexdigest(),
    }
    expected = {"protocol_sha256": "protocol", "startup_lives": 4, "identity": identity, "visibility": truth}
    docs = {
        "inputs/startup_identity.json": {"identity": identity},
        "inputs/visibility_truth.json": fixture,
        "startup.json": copy.deepcopy(expected),
        "runs/unchanged/search_startup.json": copy.deepcopy(expected),
        "runs/balanced/search_startup.json": copy.deepcopy(expected),
    }
    if corruption == "missing_search_truth":
        docs["runs/balanced/search_startup.json"]["visibility"]["lives"] = 0
    elif corruption == "extra_search_calls":
        docs["runs/balanced/search_startup.json"]["startup_lives"] = 6
    monkeypatch.setattr(M, "read", lambda p: copy.deepcopy(docs[str(p.relative_to(base))]))
    monkeypatch.setattr(M, "sha", lambda p: "protocol" if p.name == "protocol.json" else "library")
    monkeypatch.setattr(Path, "rglob", lambda p, _: iter([base / "build-cache/library.so"]))
    if corruption:
        with pytest.raises(ValueError):
            M.verify_startup(base, {})
    else:
        assert M.verify_startup(base, {})["total_startup_lives"] == 12


def endpoint_fixture(monkeypatch, arm="unchanged"):
    """Compact virtual JSON/checkpoint archive: no files, random draws or engine calls."""
    import io
    from types import SimpleNamespace

    base = Path("/synthetic_AO_endpoints")
    docs, blobs, genomes = ({}, {}, {})

    def key(path):
        return str(path if isinstance(path, Path) else base / path)

    def put(name, value):
        docs[key(name)] = value

    def payload(path):
        k = key(path)
        if k in blobs:
            return blobs[k]
        return json.dumps(docs[k], sort_keys=True).encode()

    def digest(path):
        return hashlib.sha256(payload(path)).hexdigest()

    def raw(value):
        return hashlib.sha256(np.asarray(value).tobytes()).hexdigest()

    def put_lines(name, values):
        blobs[key(name)] = b"".join(((json.dumps(v) + "\n").encode() for v in values))

    put("protocol.json", {"synthetic": True})
    put("release.json", {"status": "released"})
    for name in ("population_loader.py", "selection.py", "search.py"):
        blobs[key(name)] = name.encode()
    pd, rd = (digest("protocol.json"), digest("release.json"))
    start = np.zeros(875, np.float32)
    mid = np.ones(875, np.float32)
    table = np.stack([np.full(875, i + 2, np.float32) for i in range(32)])
    prefix = f"runs/{arm}/"
    for path, genome in [
        ("inputs/AN_start.json", start),
        (prefix + "generation8/best_genome.json", mid),
        (prefix + "best_genome.json", table[0]),
    ]:
        put(path, {"synthetic_genome": raw(genome)})
        genomes[key(path)] = genome
    for name in ("checkpoint.pt", "generation8/checkpoint.pt", "config.yaml"):
        blobs[key(prefix + name)] = name.encode()
    curves = [
        dict(
            gen=g,
            evals=320 * (g + 1),
            recheck_k=64,
            pop_invalid=0,
            pop_mismatch=0,
            recheck_invalid=0,
            pop_guard=0,
            fitness=1.0,
            mean_fitness=1.0,
        )
        for g in range(24)
    ]
    for g in (0, 4, 8, 12, 16, 20, 23):
        curves[g]["valid"] = 1.0
    lineage = [dict(event="founders", ids=list(range(32)), copies=[])]
    for g in range(24):
        lineage.append(
            dict(
                gen=g,
                children=[dict(id=32 + 224 * g + i, pa=0, pb=1, mask=0, ops={"mut": []}) for i in range(224)],
                seeds=list(range(8)),
                recheck={"seeds": list(range(8, 16)), "ids": list(range(64))},
                survivors=list(range(32)),
                fitness=[1.0] * 32,
            )
        )
    log_pins, mid_pins = ({}, {})
    for name, values, mid_values in [
        ("curves.jsonl", curves, curves[:8]),
        ("lineage.jsonl", lineage, lineage[:9]),
        ("clones.jsonl", [], []),
    ]:
        put_lines(prefix + name, values)
        data = payload(prefix + name)
        partial = b"".join(((json.dumps(v) + "\n").encode() for v in mid_values))
        log_pins[name] = {"bytes": len(data), "sha256": raw(np.frombuffer(data, dtype=np.uint8))}
        mid_pins[name] = {"bytes": len(partial), "sha256": hashlib.sha256(partial).hexdigest()}
    population = dict(
        dims={}, genomes=[{"synthetic": i + 2} for i in range(32)], fitness=[1.0] * 32, ids=list(range(32))
    )
    put(prefix + "population.json", population)
    popstart = {"population_raw_sha256": "initial32", "row_sha256": ["initialrow"] * 32}
    identity = {"identity": "base"}
    extended = {
        **identity,
        "population_start": {
            "version": 1,
            **popstart,
            "source_pins": {n: digest(n) for n in ("population_loader.py", "search.py")},
        },
        "retention_selection": {
            "version": 1,
            "arm": arm,
            "worlds": {},
            "rule": "gen fixed per-arm allocation per8 repeated for recheck; unchanged2/2/4 balanced4/2/2; diagnostics=persistent neutral; R_cap500",
            "pattern": (
                ["pool", "persistent", "blink80_20", "blink80_20"]
                if arm == "unchanged"
                else ["pool", "persistent", "pool", "blink80_20"]
            )
            * 2,
            "source_pins": {"selection.py": digest("selection.py")},
        },
    }
    put(prefix + "determinism.json", extended)
    diagnostic = dict(
        seed=123,
        abi=4,
        generations=24,
        evals=7680,
        lives=2,
        founders_sampled=0,
        top_best_rank=0,
        invalid_lives=0,
        mismatch_lives=0,
        forks={},
        heldout_score=None,
    )
    put_lines(prefix + "results.jsonl", [diagnostic])
    put(prefix + "search_startup.json", {"startup_lives": 4})
    health = dict(pop_invalid=0.0, pop_mismatch=0.0, recheck_invalid=0.0)
    common = dict(rank=0, rank_zero_id=0, search_health=health, numerical_identity=extended)
    final = {
        **common,
        "generation": 24,
        "checkpoint_sha256": digest(prefix + "checkpoint.pt"),
        "log_prefix_pins": log_pins,
        "genome_file_sha256": digest(prefix + "best_genome.json"),
        "genome_raw_sha256": raw(table[0]),
        "population_raw_sha256": raw(table),
        "population_file_sha256": digest(prefix + "population.json"),
        "determinism_sha256": digest(prefix + "determinism.json"),
        "results_sha256": digest(prefix + "results.jsonl"),
    }
    snapshot = dict(
        status="complete",
        generation=8,
        rank=0,
        rank_zero_id=0,
        checkpoint_sha256=digest(prefix + "generation8/checkpoint.pt"),
        genome_file_sha256=digest(prefix + "generation8/best_genome.json"),
        genome_raw_sha256=raw(mid),
        population_raw_sha256="midpoint32",
        identity=extended,
        log_prefix_pins=mid_pins,
        protocol_sha256=pd,
        release_sha256=rd,
        added_lives=0,
        random_draws=0,
    )
    put(prefix + "generation8/snapshot.json", snapshot)
    midpoint = {
        **common,
        "generation": 8,
        "checkpoint_sha256": snapshot["checkpoint_sha256"],
        "log_prefix_pins": mid_pins,
        "genome_file_sha256": snapshot["genome_file_sha256"],
        "genome_raw_sha256": raw(mid),
        "population_raw_sha256": "midpoint32",
        "snapshot_sha256": digest(prefix + "generation8/snapshot.json"),
    }
    names = (
        "checkpoint.pt",
        "config.yaml",
        "determinism.json",
        "curves.jsonl",
        "lineage.jsonl",
        "population.json",
        "best_genome.json",
        "results.jsonl",
        "search_startup.json",
        "generation8/checkpoint.pt",
        "generation8/best_genome.json",
        "generation8/snapshot.json",
    )
    marker = dict(
        status="complete",
        arm=arm,
        research_lives=61558,
        startup_lives=4,
        protocol_sha256=pd,
        release_sha256=rd,
        count_proof=dict(
            selection=61440,
            valid=112,
            final=6,
            half_duration=2,
            native_evals=7680,
            generations=24,
            children_per_generation=224,
            midpoint_added_lives=0,
        ),
        output_pins={n: digest(prefix + n) for n in names},
        checkpoint_log_pins=log_pins,
        midpoint=snapshot,
        health={k: [r[k] for r in curves] for k in (*health, "pop_guard")},
    )
    put(prefix + "search_complete.json", marker)
    sig = [{k: c[k] for k in ("id", "pa", "pb", "mask", "ops")} for c in lineage[1]["children"]]
    proof = dict(
        status="passed",
        protocol_sha256=pd,
        initial_rows=32,
        offspring_per_arm=224,
        initial_population_raw_sha256="initial32",
        initial_row_sha256=popstart["row_sha256"],
        recorded_first_256_replayed=True,
        simulated_lives=0,
        random_draws=0,
        runs={
            "acquisition": dict(
                genetic_signature_sha256=hashlib.sha256(
                    json.dumps(sig, sort_keys=True, separators=(",", ":"), allow_nan=False).encode()
                ).hexdigest(),
                lineage_sha256=digest(prefix + "lineage.jsonl"),
                candidate_row_sha256=["initialrow"] * 32 + ["child"] * 224,
            )
        },
    )
    put("first_cohort_replay.json", proof)
    paths = ["inputs/AN_start.json", prefix + "generation8/best_genome.json", prefix + "best_genome.json"]
    manifest = dict(
        protocol_sha256=pd,
        roles=list(M.ROLES),
        searches={arm: final},
        midpoints={arm: midpoint},
        genomes=[
            dict(role=role, path=path, file_sha256=digest(path), raw_sha256=raw(genomes[key(path)]))
            for role, path in zip(M.ROLES, paths)
        ],
        first_cohort_replay_sha256=digest("first_cohort_replay.json"),
        selection="Generation4 and generation8 population rank0 endpoints fixed before confirmation; final is never replaced by midpoint.",
    )
    manifest["genomes"] = [
        manifest["genomes"][0],
        manifest["genomes"][0],
        manifest["genomes"][1],
        manifest["genomes"][2],
        manifest["genomes"][1],
        manifest["genomes"][2],
    ]
    put("endpoints.json", manifest)
    protocol = dict(
        reference=dict(path=paths[0], raw_sha256=raw(start)),
        population_start=popstart,
        selection_worlds={},
        native_seed=123,
    )
    monkeypatch.setattr(M, "read", lambda p: copy.deepcopy(docs[key(p)]))
    monkeypatch.setattr(M, "sha", digest)
    monkeypatch.setattr(
        M,
        "json_genome",
        lambda p: np.full(875, p["params"]["synthetic"], np.float32) if isinstance(p, dict) else genomes[key(p)].copy(),
    )
    monkeypatch.setattr(M, "json_lines", lambda p: [json.loads(line) for line in payload(p).decode().splitlines()])
    original_stat, original_open = (Path.stat, Path.open)
    monkeypatch.setattr(
        Path,
        "stat",
        lambda p, *args, **kwargs: (
            SimpleNamespace(st_size=len(payload(p)))
            if str(p) in docs or str(p) in blobs
            else original_stat(p, *args, **kwargs)
        ),
    )
    monkeypatch.setattr(
        Path,
        "open",
        lambda p, *args, **kwargs: (
            io.BytesIO(payload(p)) if str(p).startswith(str(base)) else original_open(p, *args, **kwargs)
        ),
    )
    return (base, protocol, identity, docs, blobs, digest)


@pytest.mark.parametrize("arm", ["unchanged", "balanced"])
def test_arm_checkpoint_prefix_and_counts(monkeypatch, arm):
    base, protocol, identity, docs, _, _ = endpoint_fixture(monkeypatch, arm)
    manifest = docs[str(base / "endpoints.json")]
    index = 2 if arm == "unchanged" else 4
    review, lines = M.verify_search_endpoint(base, protocol, identity, manifest, arm, index, index + 1)
    assert review["generation"] == 24 and len(lines) == 25
    assert review["count_proof"]["selection"] == 61440
    manifest["midpoints"][arm]["log_prefix_pins"]["lineage.jsonl"]["bytes"] -= 1
    with pytest.raises(ValueError):
        M.verify_search_endpoint(base, protocol, identity, manifest, arm, index, index + 1)
