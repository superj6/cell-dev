"""Independent fixed candidate reconstruction: arrays only, no engine imports/execution."""

from __future__ import annotations

import ast
import hashlib
import math
from pathlib import Path

import numpy as np

ROLES = ["R0", "R1", "I", "A", "B", *[f"D{i}" for i in range(8)]]
WORLDS = ["flash5_dim25", "blink20"]
ACTION = dict(latency="d0", charge="relay", t_ref_min=0.5, privileged=False, quant=False)
KNOBS = (
    "w0",
    "w1",
    "b",
    "tau_m",
    "t_ref",
    "emit0",
    "emit1",
    "delta",
    "kappa",
    "p_div",
    "asym",
    "p_die",
    "phi",
    "sec0",
    "sec1",
    "pol0",
    "pol1",
    "tau_tr",
    "a0",
    "a1",
    "chi",
    "zeta",
    "g_r",
)
NB6 = ((1, 0), (1, -1), (0, -1), (-1, 0), (-1, 1), (0, 1))
HB_SHA = "d19ba200142f0c5ec41d5da4deff4788ed77ef22f01ba69c552968b5fddfa71c"
SPEC_SHA = "bdd06966fe7068bbac0d4a0269583aa6e7029bdee6556bb57c7e33e30b109c07"
CTL_SHA = "35e41256f9fcb84f2192531615c1002e5132a510ec3070ccb6127f696ad25816"
PARAM_SHA = {
    "flash5_dim25": "6dd3d97fcb86d718a036d500d514ead0752323e4f668b06a62b0849db1281523",
    "blink20": "7a971009e5bc301995b7a1a6c790afa5bcb81f18cff80dd1a9ee8958a72bdc35",
}


def digest(data):
    return hashlib.sha256(data).hexdigest()


def literals(source, name):
    """Extract one immutable literal; never evaluate functions/import original modules."""
    for node in ast.parse(source).body:
        if isinstance(node, ast.AnnAssign) and isinstance(node.target, ast.Name) and node.target.id == name:
            return ast.literal_eval(node.value)
        if isinstance(node, ast.Assign) and any(isinstance(t, ast.Name) and t.id == name for t in node.targets):
            return ast.literal_eval(node.value)
    raise ValueError("missing literal " + name)


def theta(**over):
    row = dict.fromkeys(KNOBS, 0.0)
    row.update(tau_m=1.0, t_ref=0.5, tau_tr=2.0)
    if set(over) - set(row):
        raise ValueError("unknown independent knob")
    row.update(over)
    return [float(row[k]) for k in KNOBS]


def program(rows):
    scalars = [0.0, 0.0, 0.0, 0.0, 0.0, 1e300, 2.0, 0.0, 1e300, 1e300, 0.0, 0.0, 0.0, 0.0]
    return [x for row in rows for x in theta(**row)] + scalars


def disk(radius):
    def ring(a, b):
        return max(abs(a), abs(b), abs(a + b))

    sites = [(a, b) for a in range(-radius, radius + 1) for b in range(-radius, radius + 1) if ring(a, b) <= radius]
    return sorted(sites, key=lambda s: (ring(*s), math.atan2(s[1] * 0.866, s[0] + s[1] / 2)))


def geometry(shape, inert=False):
    if shape == "clicker":
        return [[0, 0, 0, 2], [0, 0, 1, 1]], [(0, 0)], [(0, 0)]
    k = int(shape[-1])
    act = disk(k)
    sense = (
        [s for s in act if s == (0, 0) or max(abs(s[0]), abs(s[1]), abs(sum(s))) == k]
        if shape.startswith("hollow")
        else act
    )
    cells = []
    for z, sites in enumerate((sense, act)):
        occupied = set(sites)
        for a, b in sites:
            interior = all((a + da, b + db) in occupied for da, db in NB6)
            if inert:
                row = 0
            elif z == 0:
                row = 2 if (a, b) == (0, 0) else (3 if interior else 0)
            else:
                row = 4 if (a, b) == (0, 0) else (2 if interior else 1)
            cells.append([a, b, z, row])
    return cells, sense, act


def descriptions(recovered):
    knobs = recovered["retuned_reflex_knobs"]
    rows = []
    for role, kind, shape, values in (
        ("R0", "frozen_reflex", "hollow3", None),
        ("R1", "retuned_reflex", "hollow3", knobs),
        ("D0", "do_less", "hollow2", None),
        ("D1", "do_less", "hollow2", knobs),
        ("D2", "do_less", "ring2", None),
        ("D3", "do_less", "clicker", None),
        ("D4", "do_less", "hollow3", dict(knobs, **{"K.w0": 0.75})),
        ("D5", "do_less", "hollow3", dict(knobs, **{"C.g_r": 0.5})),
        ("D6", "do_less", "hollow3", dict(knobs, **{"C.t_ref": 4.0, "K.t_ref": 4.0})),
        ("D7", "do_less", "hollow3", dict(knobs, **{"M.kappa": 0.5})),
    ):
        rows.append(dict(role=role, kind=kind, footprint=shape, knobs=values))
    # Changes are specified here independently, not taken from worker ablation metadata.
    for role, changes in [("I", {}), ("A", {9: 0.0, 10: 0.0, 21: 0.0}), ("B", {26: 0.5})]:
        p = list(recovered["full_parameters"])
        for i, v in changes.items():
            p[i] = v
        rows.append(
            dict(
                role=role,
                kind="information" if role == "I" else "broad_ablation",
                footprint="hollow3",
                params=p,
                controller_id=1102,
                action=ACTION,
                isolates_capability=False,
                changed_parameter_indices=sorted(changes),
            )
        )
    return sorted(rows, key=lambda x: ROLES.index(x["role"]))


def reconstruct(descriptor, tuned):
    item = dict(descriptor)
    controller = "params" in item
    cells, sense, act = geometry(item["footprint"], controller)
    if controller:
        prog = program([dict(tau_m=2.0, t_ref=1.0)] * 5)
        item.update(sense_sites=[list(s) for s in sense], act_sites=[list(s) for s in act])
    elif item["footprint"] == "clicker":
        sensor = dict(g_r=1.0, emit0=1.0, tau_m=2.0, t_ref=1.0)
        motor = dict(w0=1.0, kappa=1.0, t_ref=4.0, tau_m=2.0)
        click = dict(g_r=0.55, emit0=1.0, tau_m=2.0, t_ref=1.0)
        prog = program([sensor, motor, click, dict(tau_m=2.0, t_ref=1.0), motor])
    else:
        knobs = dict(tuned["reflex@" + item["footprint"]] if item["knobs"] is None else item["knobs"])
        knobs.update({"S.emit0": 1.0, "C.emit0": 1.0})
        rows = {role: dict(b=0.0, tau_m=2.0, t_ref=1.0) for role in ("S", "J", "C", "M", "K")}
        for key, value in knobs.items():
            role, key = key.split(".")
            if role != "J":
                rows[role][key] = value
        rows["J"] = dict(rows["S"], **{key[2:]: v for key, v in knobs.items() if key.startswith("J.")})
        prog = program([rows[r] for r in ("S", "M", "C", "J", "K")])
    item.update(
        cells=cells,
        program=prog,
        body_flags=0,
        cell_count=len(cells),
        program_bytes_sha256=digest(np.asarray(prog, dtype="<f8").tobytes()),
        cells_bytes_sha256=digest(np.asarray(cells, dtype="<i4").tobytes()),
    )
    return item


def verify(study, protocol, recovered):
    source = Path(study) / "original/src/life/handbuilt.py"
    if digest(source.read_bytes()) != HB_SHA:
        raise ValueError("unreviewed body source")
    if digest((Path(study) / "original/src/life/spec.py").read_bytes()) != SPEC_SHA:
        raise ValueError("unreviewed ABI3 source")
    if digest((Path(study) / "original/controllers/mem_ctl.c").read_bytes()) != CTL_SHA:
        raise ValueError("controller source changed")
    tuned = literals(source.read_text(), "SPECK_TUNED")
    for world in WORLDS:
        rec = recovered["worlds"][world]
        if digest(np.asarray(rec["full_parameters"], dtype="<f8").tobytes()) != PARAM_SHA[world]:
            raise ValueError("full C5 vector changed")
        expected = [reconstruct(d, tuned) for d in descriptions(rec)]
        if protocol["worlds"][world]["candidates"] != expected:
            raise ValueError("independently reconstructed candidates differ: " + world)
    return {
        "candidate_count": 26,
        "body_and_program_bytes_reconstructed": True,
        "controller_source_sha256": CTL_SHA,
        "full_parameter_bytes_sha256": PARAM_SHA,
    }
