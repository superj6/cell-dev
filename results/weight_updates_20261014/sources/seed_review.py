"""Pure R seed audit against retained production schedules and F--Q registrations; no simulation."""
from __future__ import annotations

import ast
import hashlib
import json
import os
import sys
from pathlib import Path

os.environ.setdefault("ATEN_CPU_CAPABILITY", "avx2")
ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))
from src.life.evaluate import life_seed  # noqa: E402

STUDY = Path(__file__).resolve().parent
HELPER = ROOT / "outputs/autonomous_s7_20261014/sources/D_prepare.py"
NAMES = {
    "D": "autonomous_continuation_20261013", "E": "autonomous_frozen_20261013",
    "F": "autonomous_discrimination_20261013", "G": "autonomous_structural_20261013",
    "H": "autonomous_hidden_20261014", "I": "autonomous_decoy_gradient_20261014",
    "J": "autonomous_duplicate_use_20261014", "K": "autonomous_traces_20261014",
    "L": "autonomous_s7_20261014", "M": "autonomous_gene_interaction_20261014",
    "N": "autonomous_information_duration_20261014", "O": "autonomous_regulation_20261014",
    "P": "autonomous_next_step_20261014",
    "Q": "autonomous_s7_hidden_20261014",
}


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def digest(values):
    return hashlib.sha256(json.dumps(sorted(set(values)), separators=(",", ":")).encode()).hexdigest()


def pure_functions(path, names, namespace):
    """Execute only the named function definitions, never module setup, main or scientific workers."""
    tree = ast.parse(path.read_text())
    nodes = [node for node in tree.body if isinstance(node, ast.FunctionDef) and node.name in names]
    assert {node.name for node in nodes} == set(names)
    exec(compile(ast.Module(body=nodes, type_ignores=[]), str(path), "exec"), namespace)
    return namespace


def main():
    sources = {}

    def source(path):
        sources[str(path.relative_to(ROOT))] = sha(path)
        return path

    def read(label, name="protocol.json"):
        return json.loads(source(ROOT / "outputs" / NAMES[label] / name).read_text())

    ns = pure_functions(source(HELPER), ["run_life_seeds", "pilot_life_seeds"], {"life_seed": life_seed})
    for relative in ("src/life/evaluate.py", "src/life/spec.py"):
        source(ROOT / relative)
    pilot = ns["pilot_life_seeds"]()
    assert len(pilot) == 58_690
    prior = {str(seed): ns["run_life_seeds"](seed)
             for seed in (51089, 51090, 51891, 51892, 52091, 52092)}
    prior_union = {value for values in prior.values() for value in values}
    assert len(prior_union) == 1176
    confirm = list(range(52_040_000, 52_040_512))
    candidate = set(confirm)
    assert len(confirm) == len(candidate) == 512
    assert not candidate & pilot and not candidate & prior_union
    protocols = {label: read(label) for label in NAMES}
    registrations = {}

    def register(label, values, evidence):
        values = list(map(int, values))
        assert values and len(values) == len(set(values)), label
        assert not candidate.intersection(values), label
        registrations[label] = {"count": len(values), "first": min(values), "last": max(values),
                                "sorted_unique_sha256": digest(values), "seeds": values,
                                "R_measurement_overlap": 0, "evidence": evidence}

    for label in ("D", "G", "L", "P"):
        audit = read(label, "seed_audit.json")
        for seed, values in audit["run_life_seeds"].items():
            assert values == prior[seed]
        register(label + "_confirmation", audit["confirm_seeds"], "seed_audit.json:confirm_seeds")
    for label in ("E", "F", "H", "K", "M", "O", "Q"):
        register(label + "_measurement", protocols[label]["seeds"], "protocol.json:seeds")
    register("F_prior_tuning", protocols["F"]["tuning_seeds"], "protocol.json:tuning_seeds")
    register("G_neutrality_validation", protocols["G"]["neutrality_validation"]["seeds"],
             "protocol.json:neutrality_validation.seeds")
    for stage, values in protocols["I"]["seeds"].items():
        register("I_" + stage, values, "protocol.json:seeds." + stage)
    j_measure = source(ROOT / "outputs" / NAMES["J"] / "measure.py")
    j = pure_functions(j_measure, ["seeds"], {})
    assert protocols["J"]["stage_blocks"] == {"screen": 98, "confirm": 99}
    for stage, block in protocols["J"]["stage_blocks"].items():
        values = j["seeds"](stage)
        assert values == list(range(51_000_000 + 10_000 * block, 51_000_512 + 10_000 * block))
        register("J_" + stage, values, "measure.py:seeds(stage); protocol.json:stage_blocks")
    for duration, values in protocols["N"]["seeds"].items():
        register("N_T" + duration, values, "protocol.json:seeds." + duration)
    n_validation = protocols["N"]["validation"]["seeds"]
    assert n_validation == list(range(51_099_000, 51_099_004))
    register("N_validation", n_validation, "protocol.json:validation.seeds")
    # K's C validation deliberately uses the same four seed IDs as its reference lives.
    assert protocols["K"]["kernel_validation_lives"] == 12
    register("K_C_validation", protocols["K"]["seeds"], "protocol.json:seeds; measure.py reference/C pair")
    source(ROOT / "outputs" / NAMES["K"] / "measure.py")
    # Existing F replay/parity source uses two closed-loop plus two different-life controls.
    audit_path = source(ROOT / "results/taskvar/validation/discrimination_audit.json")
    audit = json.loads(audit_path.read_text())
    f_closed = sorted({row["seed"] for row in audit["rows"]})
    assert f_closed == [51_040_000, 51_040_001]
    assert audit["world_parity_audit"]["seeds"] == f_closed
    source(ROOT / "scripts/taskvar_replay.py")
    register("F_prior_replay_parity_validation", range(51_040_000, 51_040_004),
             "discrimination_audit.json closed seeds; taskvar_replay.py 2*lives seed/control allocation")
    # Startup numerical identity intentionally repeats seed11 across studies/full and fast kernels.
    checkpoint = source(ROOT / "src/checkpoint.py")
    golden = next(node for node in ast.parse(checkpoint.read_text()).body
                  if isinstance(node, ast.FunctionDef) and node.name == "golden_life")
    calls = [node for node in ast.walk(golden) if isinstance(node, ast.Call)
             and isinstance(node.func, ast.Attribute) and node.func.attr == "run"]
    assert len(calls) == 2 and all(ast.literal_eval(node.args[1]) == [11] for node in calls)
    register("startup_full_fast_golden", [11], "src/checkpoint.py:golden_life, shared repeated ID")
    # Conservatively reserve all historical decimal allocations up to Q, including earlier E validation,
    # viewers, prior references, and unused slots; this is a namespace envelope, not a claim of lives run.
    envelopes = [(30_000_000, 50_000_000), (51_000_000, 52_040_000)]
    for first, stop in envelopes:
        assert not any(first <= value < stop for value in candidate)
    source(ROOT / "outputs/audit_m_20261014/source_seed_review.json")
    source(ROOT / "outputs/prospective_g5_20261014/namespace_audit.json")
    source(ROOT / "outputs/audit_p_20261014/check_namespace.py")
    source(ROOT / "outputs/audit_p_20261014/seed_review.json")
    source(ROOT / "outputs/audit_q_20261014/seed_review.json")
    source(ROOT / "outputs/audit_q_20261014/check_namespace.py")
    report = {"status": "passed", "simulated_lives": 0,
              "candidate_seeds": confirm, "candidate_block": 104,
              "candidate_sorted_unique_sha256": digest(confirm),
              "helper_sha256": sha(HELPER), "script_sha256": sha(Path(__file__)),
              "pure_hashed_pilot_seeds_checked": len(pilot), "pilot_sorted_unique_sha256": digest(pilot),
              "pure_hashed_D_G_L_P_seeds_checked": len(prior_union),
              "D_G_L_P_sorted_unique_sha256": digest(prior_union),
              "all_cross_study_overlaps": 0, "registrations": registrations,
              "historical_decimal_envelopes_half_open": envelopes, "source_sha256": sources,
              "R_scope": {"genotypes": ["founder_row38", "D51089_final_rank0", "D51090_final_rank0"],
                          "arms": ["structure", "structure_identity_clamp_pheno_fixed", "freeze"],
                          "life_T": 1536, "fork_time": 768, "measurement_open": 800,
                          "research_genome_lives": 3 * 3 * 512,
                          "startup_golden_seed": 11, "startup_golden_lives": 2,
                          "startup_golden_T": 200},
              "scope": "Pure registered schedules only; no active scientific outcomes read. D/G search IDs "
                       "deliberately coincide. All D--Q measurement and validation seed registrations are "
                       "checked. Shared R IDs across genotypes/arms and repeated startup golden seed11 "
                       "are intentional. No new smoke or validation allocation."}
    path = STUDY / "seed_review.json"
    text = json.dumps(report, indent=2, allow_nan=False) + "\n"
    if path.exists() and path.read_text() != text:
        raise ValueError("Existing R seed receipt differs; inspect before replacing")
    path.write_text(text)
    print(json.dumps({"status": report["status"], "receipt": str(path.relative_to(ROOT)),
                      "pilot": len(pilot), "D_G_L_P": len(prior_union),
                      "candidate": len(confirm), "registrations": len(registrations), "simulated_lives": 0}))



if __name__ == "__main__":
    main()
