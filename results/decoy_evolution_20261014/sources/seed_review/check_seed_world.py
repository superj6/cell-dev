"""Independent, simulation-free U namespace audit using only the Python standard library."""
from __future__ import annotations

import ast
import hashlib
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
OUT = Path(__file__).resolve().parent
MASK = (1 << 64) - 1
PURPOSES = dict(gen=1, founders=2, valid=3, heldout=4, final=5, clones=6, sizecurve=7, census=8)
SEED_STREAM = 0x4C494645


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def digest(values):
    return hashlib.sha256(json.dumps(sorted(set(values)), separators=(",", ":")).encode()).hexdigest()


def mix(value):
    value = (value + 0x9E3779B97F4A7C15) & MASK
    value = ((value ^ (value >> 30)) * 0xBF58476D1CE4E5B9) & MASK
    value = ((value ^ (value >> 27)) * 0x94D049BB133111EB) & MASK
    return value ^ (value >> 31)


def seed(run, purpose, index, life):
    value = mix((run & MASK) ^ mix(SEED_STREAM + PURPOSES[purpose]))
    for key in (index, life):
        value = mix(value ^ (key & MASK))
    return value


def schedule(run, generations=16, base=3, recheck=4):
    rows = []
    for index in range(generations):
        for life in range(base + recheck):
            rows.append(dict(purpose="gen", index=index, life=life,
                             stage="initial" if life < base else "recheck",
                             seed=seed(run, "gen", index, life)))
        if index % 4 == 0 or index == generations - 1:
            for life in range(16):
                rows.append(dict(purpose="valid", index=index, life=life, stage="diagnostic",
                                 seed=seed(run, "valid", index, life)))
    for index in (0, 1):
        for life in range(2):
            rows.append(dict(purpose="final", index=index, life=life, stage="diagnostic",
                             seed=seed(run, "final", index, life)))
    return rows


def pilot_seeds():
    values = set()
    for run in range(10):
        for generation in range(500):
            values.update(seed(run, "gen", generation, life) for life in range(7))
            if generation % 10 == 0 or generation == 499:
                for purpose, n in (("valid", 16), ("heldout", 24), ("clones", 3)):
                    values.update(seed(run, purpose, generation, life) for life in range(n))
        for index in range(16):
            values.update(seed(run, "founders", index, life) for life in range(2))
        for index in (0, 1):
            values.update(seed(run, "final", index, life) for life in range(64))
        values.update(seed(run, "sizecurve", 0, life) for life in range(16))
    return values


def source_functions(path, names, namespace):
    nodes = [node for node in ast.parse(path.read_text()).body
             if isinstance(node, ast.FunctionDef) and node.name in names]
    assert {node.name for node in nodes} == set(names)
    exec(compile(ast.Module(body=nodes, type_ignores=[]), str(path), "exec"), namespace)
    return namespace


def main():
    pins = {}

    def pin(path):
        path = ROOT / path
        pins[str(path.relative_to(ROOT))] = sha(path)
        return path

    def read(path):
        return json.loads(pin(path).read_text())

    # Verify the inherited prior-study namespace chain without importing or running its workers.
    prior = read("outputs/autonomous_scoring_budget_20261014/sources/source_seed_review.json")
    assert prior["status"] == "passed" and prior["simulated_lives"] == 0
    for relative, expected in prior["source_sha256"].items():
        assert sha(pin(relative)) == expected, relative
    s_audit = read("outputs/autonomous_scoring_budget_20261014/seed_audit.json")
    p_audit = read("outputs/autonomous_next_step_20261014/seed_audit.json")
    r_audit = read("outputs/autonomous_weight_updates_20261014/seed_audit.json")
    helper = pin("outputs/autonomous_s7_20261014/sources/D_prepare.py")

    # Independently written integer derivation versus narrowly extracted production functions.
    module = type("SpecScope", (), {})()
    production = source_functions(pin("src/life/spec.py"), ("splitmix64", "hash64"), {"MASK64": MASK})
    module.hash64 = production["hash64"]
    life_fn = source_functions(pin("src/life/evaluate.py"), ("life_seed",),
                               {"spec": module, "_SEED_STREAM": SEED_STREAM, "PURPOSES": PURPOSES})["life_seed"]
    old_helper = source_functions(helper, ("pilot_life_seeds", "run_life_seeds"), {"life_seed": life_fn})
    pilot = pilot_seeds()
    assert len(pilot) == 58690 and pilot == old_helper["pilot_life_seeds"]()
    assert digest(pilot) == r_audit["pilot_sorted_unique_sha256"]

    histories = {"pilots_s0_to_s9_conservative_schedule": sorted(pilot)}
    history_scopes = {"pilots_s0_to_s9_conservative_schedule":
                      "Conservative registered 500-generation pilot namespace, not an assertion all lives ran."}
    for run in (51089, 51090, 51891, 51892, 52091, 52092):
        values = [row["seed"] for row in schedule(run)]
        assert len(values) == len(set(values)) == 196
        assert values == old_helper["run_life_seeds"](run)
        label = "D_and_G" if run in (51089, 51090) else "L" if run in (51891, 51892) else "P"
        histories[f"{label}_s{run}"] = values
        if label == "P":
            assert values == p_audit["run_life_seeds"][str(run)]
    for run in (52091, 52092):
        values = [row["seed"] for row in schedule(run, 8, 6, 8)]
        assert values == s_audit["run_life_seeds"][str(run)]
        histories[f"S_held_s{run}"] = values
        history_scopes[f"S_held_s{run}"] = "Prepared and held; all reserved IDs excluded despite no simulation."

    registrations = {name: row["seeds"] for name, row in prior["prior_registered_allocations"].items()}
    registrations["S_held_confirmation"] = s_audit["confirm_seeds"]
    for name, row in prior["prior_registered_allocations"].items():
        assert row["count"] == len(set(row["seeds"])) and digest(row["seeds"]) == row["sha256"]
    assert len(registrations) == 26
    historical_union = {value for values in histories.values() for value in values}
    assert len(historical_union) == 60010
    registered_union = {value for values in registrations.values() for value in values}

    records = {str(run): schedule(run, generations=4) for run in (53091, 53092)}
    run_lists = {run: [row["seed"] for row in rows] for run, rows in records.items()}
    new_hashed = {value for values in run_lists.values() for value in values}
    assert len(new_hashed) == 128 and all(len(set(v)) == len(v) == 64 for v in run_lists.values())
    for run, rows in records.items():
        for row in rows:
            assert row["seed"] == life_fn(int(run), row["purpose"], row["index"], row["life"])

    confirmation = list(range(52_060_000, 52_060_512))
    validation_reserved = list(range(52_070_000, 52_080_000))
    candidate = new_hashed | set(confirmation) | set(validation_reserved)
    assert len(candidate) == 10640
    assert not candidate & historical_union
    assert not candidate & registered_union
    # Conservatively cover unenumerated historical decimal studies and every older E7 reservation.
    decimal_envelopes = [(30_000_000, 50_000_000), (51_000_000, 52_060_000)]
    assert all(not any(lo <= value < hi for lo, hi in decimal_envelopes) for value in candidate)
    assert not set(confirmation) & new_hashed
    assert not set(validation_reserved) & (new_hashed | set(confirmation))
    lists = dict(U_records_by_run=records, U_confirmation=confirmation,
                 U_validation_reserved=validation_reserved, historical_hashed=histories,
                 prior_registered_allocations=registrations)
    lists_path = OUT / "namespace_lists.json"
    lists_path.write_text(json.dumps(lists, indent=2, allow_nan=False) + "\n")
    report = dict(
        status="passed", simulated_lives=0, engine_modules_imported=False,
        run_life_seeds=run_lists, confirm_seeds=confirmation, confirm_block=106,
        validation_reserved_block=107, validation_reserved_half_open=[52_070_000, 52_080_000],
        validation_reservation_is_not_execution=True,
        unique_search_diagnostic_ids=128, unique_ids_per_run=64,
        unique_selection_ids_per_run=28, unique_periodic_validation_ids_per_run=32,
        unique_final_ids_per_run=4,
        simulated_search_genome_lives=8268,
        simulated_search_life_breakdown=dict(selection=8192, periodic_validation=64, final=12,
                                           final_T1024=8, final_T512=4),
        planned_confirmation_genome_lives=8192, planned_research_genome_lives=16460,
        historical_unique_hashed_ids=60010, prior_registration_count=26,
        all_cross_study_overlaps=0, all_internal_unintended_overlaps=0,
        historical_decimal_envelopes_half_open=decimal_envelopes,
        historical_set_summaries={name: dict(count=len(set(values)), sorted_unique_sha256=digest(values))
                                  for name, values in histories.items()},
        historical_scope_notes=history_scopes,
        prior_registration_summaries={name: dict(count=len(set(values)), sorted_unique_sha256=digest(values))
                                     for name, values in registrations.items()},
        namespace_lists_file="namespace_lists.json", namespace_lists_sha256=sha(lists_path),
        source_sha256=pins, script_sha256=sha(Path(__file__)),
        scope=["Seed derivation and reservation only; actual U configs/protocol reviewed separately.",
               "Search genomes within a generation intentionally share three initial seeds and four recheck seeds.",
               "Each final0 pair is evaluated at T1024 and again at T512; half-life reuse is intentional.",
               "All four genotypes and four confirmation conditions intentionally share the same block106 IDs.",
               "Prior G intentionally shared D IDs; held S intentionally shared 184 P IDs.",
               "No new final index2 exists; six final simulations per run use four unique IDs.",
               "Block107 is reserved and has no simulated lives in this audit."])
    out = OUT / "seed_audit.json"
    out.write_text(json.dumps(report, indent=2, allow_nan=False) + "\n")
    print(json.dumps(dict(status="passed", unique_U_search_ids=128, confirmation_ids=512,
                          historical_hashed_ids=60010, overlaps=0, simulated_lives=0,
                          report_sha256=sha(out), lists_sha256=sha(lists_path))))


if __name__ == "__main__":
    main()
