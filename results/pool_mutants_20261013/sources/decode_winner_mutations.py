"""Read-only genome audit; no lives are simulated and no causal mechanism is inferred."""
from __future__ import annotations

import argparse
import hashlib
import json
import os
import sys
from pathlib import Path

os.environ.setdefault("ATEN_CPU_CAPABILITY", "avx2")
ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))

import numpy as np  # noqa: E402
import torch  # noqa: E402

from src.genome import Layout  # noqa: E402

STUDY = Path(__file__).resolve().parent
KNOB_GROUPS = {
    "w0": ["spike_messaging"], "w1": ["spike_messaging"], "b": ["cell_physics"],
    "tau_m": ["cell_physics"], "t_ref": ["cell_physics"],
    "emit0": ["spike_messaging"], "emit1": ["spike_messaging"], "delta": ["spike_messaging"],
    "kappa": ["action"], "p_div": ["development"], "asym": ["development"],
    "p_die": ["development"], "phi": ["development"],
    "sec0": ["development", "chemical_signaling"], "sec1": ["development", "chemical_signaling"],
    "pol0": ["development", "chemical_signaling", "spike_messaging"],
    "pol1": ["development", "chemical_signaling", "spike_messaging"],
    "tau_tr": ["cell_physics", "development"],
    "a0": ["spike_messaging"], "a1": ["spike_messaging"], "chi": ["development"],
    "zeta": ["development"], "g_r": ["sensing"],
}


def digest(data):
    return hashlib.sha256(data).hexdigest()


def describe(layout, field, index):
    """Direct parameter semantics, not a proposed behavioral mechanism."""
    if field in ("A", "a0"):
        knob = layout.knob_names[index[0]]
        label = f"{field}[{','.join(map(str, index))}]: "
        label += f"gene {index[1]} weight into {knob}" if field == "A" else f"bias into {knob}"
        return label, KNOB_GROUPS[knob]
    if field == "W":
        gene, column = index
        source = f"g{column}" if column < layout.dims.genes_max else layout.input_names[column - layout.dims.genes_max]
        source_meaning = {
            "m0": "internal morphogen 0 concentration / (1 + concentration)",
            "m1": "internal morphogen 1 concentration / (1 + concentration)",
            "r0": "received spike-channel 0 trace / previous trace time constant",
            "r1": "received spike-channel 1 trace / previous trace time constant",
            "f": "own spike trace / previous trace time constant",
            "rho": "external receptor trace / previous trace time constant",
            "is_S": "local indicator that this cell occupies sense plane z=0",
            "is_M": "local indicator that this cell occupies motor plane z=1",
            "n_view": "occupied neighbor fraction",
        }.get(source, "gene expression")
        groups = ["development"]
        if source.startswith("rho"):
            groups.append("sensing")
        elif source in ("m0", "m1"):
            groups.append("chemical_signaling")
        elif source in ("r0", "r1"):
            groups.append("spike_messaging")
        elif source == "f":
            groups.append("cell_physics")
        return f"W[{gene},{column}]: input {source} ({source_meaning}) to gene {gene}", groups
    labels = {
        "b": "gene basal expression", "lam": "gene response rate", "s0": "maternal gene level",
        "Q": "gene partition asymmetry", "act": "gene active flag", "Dm": "morphogen transport rate",
        "km": "morphogen decay rate",
    }
    groups = ["development", "chemical_signaling"] if field in ("Dm", "km") else ["development"]
    return f"{field}[{index[0]}]: {labels[field]}", groups


def decode(screen, row, selection=None):
    manifest = json.loads((screen / "manifest.json").read_text())
    genomes = np.load(screen / "genomes.npy", allow_pickle=False)
    if digest(genomes.tobytes()) != manifest["genomes_sha256"]:
        raise ValueError(f"genome table digest differs: {screen}")
    if not 0 < row < len(genomes):
        raise ValueError("winner must be a mutant genome row, with parent at row zero")
    body = screen.name.split("_", 1)[0]
    parent_path = ROOT / f"outputs/catch_pilot/speck_lmax4_hexprism_sex_{body}/best_genome.json"
    if digest(parent_path.read_bytes()) != manifest["parent_sha256"]:
        raise ValueError(f"parent file digest differs: {parent_path}")
    layout, saved_parent = Layout.load(parent_path)
    if not np.array_equal(saved_parent.numpy(), genomes[0]):
        raise ValueError("parent file is not genome row zero")
    if selection and (selection["winner_mutant_index"] != row - 1
                      or selection["winner_sha256"] != digest(genomes[row].tobytes())):
        raise ValueError("winner row/index/digest differs from frozen selection")
    parent, winner = genomes[[0, row]]
    raw = torch.from_numpy(genomes[[0, row]].copy())
    active = layout.active(raw).numpy()
    mutable = layout.mutable(raw).numpy()
    packed = layout.pack(raw, manifest.get("lattice", "hexprism"))
    operations = json.loads((screen / "mutation_ops.json").read_text())[row - 1]
    if "dup" in operations or "del" in operations:
        raise ValueError("this bounded study registered point mutations only")
    reconstructed = parent.copy()
    for field, indices, delta in operations.get("mut", []):
        start, _, shape = layout.slices[field]
        flat = start + np.ravel_multi_index(tuple(indices), shape)
        reconstructed[flat] += np.float32(delta)
    if not np.array_equal(reconstructed, winner):
        raise ValueError("logged point mutations do not reconstruct selected genome exactly")
    changes = []
    for flat in np.flatnonzero(parent != winner):
        field, indices = layout.locate(int(flat))
        label, groups = describe(layout, field, indices)
        gene, source = int(layout.gene_of[flat]), int(layout.src_of[flat])
        changes.append({
            "flat_slot": int(flat), "field": field, "indices": indices, "label": label, "groups": groups,
            "raw_parent": float(parent[flat]), "raw_winner": float(winner[flat]),
            "raw_delta": float(winner[flat]) - float(parent[flat]),
            "owning_gene": gene if gene >= 0 else None, "source_gene": source if source >= 0 else None,
            "owner_active_parent_winner": active[:, gene].tolist() if gene >= 0 else None,
            "source_active_parent_winner": active[:, source].tolist() if source >= 0 else None,
            "point_mutable_parent_winner": mutable[:, flat].tolist(),
            "packed_parent": float(packed[0, flat]), "packed_winner": float(packed[1, flat]),
            "packed_changed": bool(packed[0, flat] != packed[1, flat]),
        })
    theta = layout.zygote_phenotype(raw, "hexprism")
    zygote_changes = [{"knob": knob, "parent": float(theta[0, i]), "winner": float(theta[1, i])}
                      for i, knob in enumerate(layout.knob_names) if theta[0, i] != theta[1, i]]
    chemical_inputs = [change["label"] for change in changes
                       if change["field"] == "W" and "chemical_signaling" in change["groups"]]
    notes = []
    if chemical_inputs:
        notes.append("Changes how the shared gene network reads internal morphogen concentration. "
                     "This chemical concentration includes local secretion, decay, and neighbor packet exchange; "
                     "it is neither the target receptor stream nor a received spike trace.")
    if any(change["field"] == "W" and change["indices"][1] == 24 for change in changes):
        notes.append("The is_M change alters a gene's response to the existing local motor-plane cue. "
                     "It does not directly change the motor gain.")
    notes.append("These changes can alter growth and ongoing cell physiology. Without single-mutation "
                 "or phenotype interventions, their separate contributions and behavioral mechanism remain unknown.")
    return {
        "body": body, "world": manifest["world"], "screen": str(screen.relative_to(ROOT)),
        "winner_genome_row": row, "winner_mutant_index": row - 1,
        "parent_raw_sha256": digest(parent.tobytes()), "winner_raw_sha256": digest(winner.tobytes()),
        "selection_verified": selection is not None, "logged_operations_reconstruct_exactly": True,
        "active_gene_slots_parent": np.flatnonzero(active[0]).tolist(),
        "active_gene_slots_winner": np.flatnonzero(active[1]).tolist(),
        "inactive_gene_slots_parent": np.flatnonzero(~active[0]).tolist(),
        "inactive_gene_slots_winner": np.flatnonzero(~active[1]).tolist(),
        "raw_changed_slots": len(changes), "packed_changed_slots": int(np.sum(packed[0] != packed[1])),
        "parameter_groups": sorted({group for change in changes for group in change["groups"]}),
        "changes": changes, "logged_operations": operations, "zygote_phenotype_changes": zygote_changes,
        "chemical_inputs_changed": chemical_inputs, "explanatory_notes": notes,
        "lateral_off_scope": "Suppresses in-plane spike ARRIVAL delivery after the fork; vertical spikes and "
                             "morphogen PACKET exchange continue. Interaction measures the mutation's changed "
                             "dependence on lateral spikes, which may be mediated by development.",
    }


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--screen", type=Path)
    parser.add_argument("--row", type=int, help="Explicit diagnostic row; otherwise use frozen winner selection")
    parser.add_argument("--out", type=Path, default=STUDY / "winner_mutations.json")
    args = parser.parse_args()
    if args.row is not None and args.screen is None:
        parser.error("--row requires --screen")
    screens = [args.screen.resolve()] if args.screen else sorted((STUDY / "screens").glob("s*_T1024_b80"))
    winners, pending = [], []
    for screen in screens:
        selection_path = screen / "followup/selection.json"
        if args.row is None and not selection_path.exists():
            pending.append(str(screen.relative_to(ROOT)))
            continue
        selection = json.loads(selection_path.read_text()) if args.row is None else None
        row = selection["winner_genome_row"] if selection else args.row
        winners.append(decode(screen, row, selection))
    report = {
        "format": 2, "runner_sha256": digest(Path(__file__).read_bytes()), "winners": winners, "pending": pending,
        "caveats": [
            "Parameter groups describe direct inputs/readouts; they do not identify the cause of any fitness gain.",
            "Development includes the shared gene network, which can affect any phenotype throughout life.",
            "Chemical signaling and spike messaging are distinct; m0/m1 denote internal chemicals, not receptors.",
            "Lateral-off lesions suppress in-plane spike arrivals; morphogen packet exchange continues.",
            "Both point mutations occur together; this study does not isolate either mutation's contribution.",
            "Packed changes can be quantized away in a particular cell state; zygote changes describe only time zero.",
            "Active gene slots denote genetic availability, not whether a gene is expressed or used in a circuit.",
        ],
    }
    args.out.write_text(json.dumps(report, indent=2, allow_nan=False) + "\n")
    print(json.dumps({"decoded": len(winners), "pending": len(pending), "out": str(args.out)}))


if __name__ == "__main__":
    main()
