"""Pure packed-table and source dependency audit; no kernel build or life simulation."""
from __future__ import annotations

import hashlib
import json
import sys
from pathlib import Path

import numpy as np

ROOT = next(p for p in Path(__file__).resolve().parents if (p / "src/life/spec.py").exists())
sys.path.insert(0, str(ROOT))
from src.life import spec  # noqa: E402

STUDY = ROOT / "results/gene_interaction_20261014/superseded_4096"


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def audit():
    assert sha(STUDY / "provenance.json") == "596b4075a17a2365aeced53622e4c0ee7e96665850d925d8c3862313141bb929"
    prior = json.loads((STUDY / "provenance.json").read_text())
    for name in ("genotypes.npy", "genomes.json", "protocol.json"):
        assert sha(STUDY / name) == prior["artifacts"][name]["sha256"]
    genomes = np.load(STUDY / "genotypes.npy", allow_pickle=False)
    packed = spec.V3.pack_genomes(genomes, "hexprism")
    frozen = json.loads((STUDY / "genomes.json").read_text())
    branches = {}
    for seed, branch in frozen["branches"].items():
        copy = branch["copy_slot"]
        rows = {name: value["row"] for name, value in branch["rows"].items()}
        private = np.zeros(spec.V3.GENOME_SIZE, dtype=bool)
        wa, _ = spec.V3.GENOME_SLICES["W"]
        private[wa + 25 * copy:wa + 25 * (copy + 1)] = True
        for name in ("b", "lam", "s0", "Q", "act"):
            private[spec.V3.GENOME_SLICES[name][0] + copy] = True
        comparisons = {}
        for name, knockout in (("intact", "copy_KO"), ("source_KO", "double_KO")):
            left, right = packed[rows[name]], packed[rows[knockout]]
            W, A = spec.V3.genome_view(left, "W"), spec.V3.genome_view(left, "A")
            bias = spec.V3.genome_view(left, "a0")
            incoming = spec.V3.genome_view(left, "W")[copy]
            changed = np.flatnonzero(left.view(np.uint64) != right.view(np.uint64)).tolist()
            intervals = {}
            for knob in np.flatnonzero(A[:, copy]):
                coefficients = A[knob]
                intervals[spec.V3.KNOBS[knob]] = {
                    "bias": float(bias[knob]), "coefficients": coefficients.tolist(),
                    "cube_min": float(bias[knob] + np.minimum(coefficients, 0).sum()),
                    "cube_max": float(bias[knob] + np.maximum(coefficients, 0).sum())}
            comparisons[name + "__vs__" + knockout] = {
                "left_packed_sha256": hashlib.sha256(left.tobytes()).hexdigest(),
                "right_packed_sha256": hashlib.sha256(right.tobytes()).hexdigest(),
                "outgoing_W_column": W[:, copy].tolist(), "outgoing_A_column": A[:, copy].tolist(),
                "W_column_exact_positive_zero": W[:, copy].tobytes() == np.zeros(16).tobytes(),
                "A_column_exact_positive_zero": A[:, copy].tobytes() == np.zeros(23).tobytes(),
                "copy_incoming_W_row": incoming.tolist(),
                "copy_private_parameters": {field: float(spec.V3.genome_view(left, field)[copy])
                                            for field in ("b", "lam", "s0", "Q", "act")},
                "changed_packed_indices": changed,
                "all_changes_private": bool(np.all(private[changed])),
                "nonprivate_packed_bytes_identical": left[~private].tobytes() == right[~private].tobytes(),
                "affected_readout_cube_intervals": intervals}
        branches[seed] = {"copy_slot": copy, "copy_origin_id": branch["copy_origin_id"],
                          "source_slot": branch["source_slot"], "source_origin_id": branch["source_origin_id"],
                          "comparisons": comparisons}
    first = branches["51089"]["comparisons"]
    assert all(value["W_column_exact_positive_zero"] and value["A_column_exact_positive_zero"]
               and value["nonprivate_packed_bytes_identical"] for value in first.values())
    second = branches["51090"]["comparisons"]
    assert all(value["W_column_exact_positive_zero"] and not value["A_column_exact_positive_zero"]
               for value in second.values())
    # A bounded state is a counterexample to universal threshold invariance, not evidence of reachability.
    state = np.zeros(16)
    state[4], state[9] = .7, spec.V3.genome_view(packed[6], "s0")[9]
    knockout_state = state.copy()
    knockout_state[9] = 0.
    live_readout = np.asarray(spec.V3.readout(packed[6], state))
    ko_readout = np.asarray(spec.V3.readout(packed[7], knockout_state))
    live_phenotype = np.asarray(spec.V3.phenotype(packed[6], state))
    ko_phenotype = np.asarray(spec.V3.phenotype(packed[7], knockout_state))
    changed_knobs = np.flatnonzero(live_phenotype != ko_phenotype).tolist()
    assert changed_knobs == [6]
    counterexample = {"background": "source_origin0_deleted", "gene_state": state.tolist(),
                      "copy_deleted_gene_state": knockout_state.tolist(),
                      "emit1_readout_with_copy": float(live_readout[6]),
                      "emit1_readout_without_copy": float(ko_readout[6]),
                      "emit1_with_copy": float(live_phenotype[6]),
                      "emit1_without_copy": float(ko_phenotype[6]), "changed_knobs": changed_knobs,
                      "reachability": "Not established. This disproves a universal cube/decoder disconnection claim only."}
    return {"status": "passed", "simulated_lives": 0, "kernel_builds": 0,
            "input_directory": str(STUDY.relative_to(ROOT)),
            "inputs": {name: sha(STUDY / name) for name in
                       ("genotypes.npy", "genomes.json", "protocol.json", "provenance.json")},
            "source_sha256": {name: sha(ROOT / name) for name in
                              ("src/life/spec.py", "src/life/kernel.c", "src/genome.py")},
            "branches": branches, "counterexample": counterexample,
            "conclusion": {"51089": "Copy is fully disconnected; copy loss and source/copy fitness interaction are zero.",
                           "51090": "Copy has one possible binary emit1 output. Actual conditional interaction remains "
                                    "unresolved; no universal disconnection proof follows from J zero outcomes."}}


if __name__ == "__main__":
    result = audit()
    Path(__file__).with_name("disconnection_audit.json").write_text(json.dumps(result, indent=2) + "\n")
    print(json.dumps({"conclusion": result["conclusion"], "counterexample": result["counterexample"]}, indent=2))
