"""CATCH world tests (BODY_DESIGN_PROPOSAL.md 2-3, LIFE_ABI.md 9.7), the analogue of test_life_world_bell.py: the
closed-form dot against Euler integration of its strokes, surface-normal faces that cancel over any shape (uniform
firing never drifts a body, islands exert no force), clicks only at the hotspot with the key's hysteresis, the
accounting of captures, misses and timer re-placements, receptor events at the world's rate, and F T = income minus
every charge. The checks rebuild the world from the kernel's raster and fate log (or replay its hash streams), never
from the accountant's own state."""
import math
from dataclasses import replace

import numpy as np
import pytest

from src import lattice
from src.life import build, spec
from src.life import handbuilt as hb
from tests.life_helpers import (
    CLICKER3,
    COLUMN3,
    GROWER3,
    MOTOR3,
    QUIET3,
    R3,
    SENSE3,
    TURNOVER3,
    TURNOVER_BODY,
    V3,
    bits,
    catch,
    columns,
    grn3,
    hexdisk,
    kernel3,
    reference3,
)

L = V3.L
UNITS = lattice.unit_vectors("hex")
OFFS = lattice.offsets("hex")
RING1 = columns(hexdisk(1))
TONIC = V3.theta(b=1.875, tau_m=8, t_ref=2, kappa=1)  # fires every ~6 units; a twitch from rest is a full 1
ISLANDS = [(0, 0), (3, 0), (0, 3), (-3, 3), (-3, 0), (0, -3), (3, -3)]  # the centre and the 6 ring-3 corners


def _cells(res, i) -> dict:
    """uid -> [a, b, z, t_birth, t_death] from a life's fate log (t_death = inf for survivors)."""
    kinds, f = res.fates(i)
    assert res.fate_n[i] == len(kinds)  # the log is complete
    out = {}
    for row, fr in zip(kinds.tolist(), f.tolist()):
        uid = row[1] & spec.MASK64
        if row[0] == 1:
            out[uid] = [row[3], row[4], row[6], fr[0], math.inf]
        elif row[0] == 2:
            out[uid][4] = fr[0]
    return out


def _strokes(res, i, w) -> tuple[list, list, list]:
    """The act-plane strokes of a life rebuilt from its raster and fate log, for bodies whose act-plane cells have
    kappa 1 whenever they fire (COLUMN3, TURNOVER3 and the tonic rows here): ``(t, fx, fy, t_stop)`` with the force
    g_n dz n of the stroke, n the face toward act-plane sites empty at the left limit, and t_stop the cell's death;
    the feet as the (t_birth, t_death) of every sense-plane cell (traction); and every cell as (a, b, t_birth,
    t_death), whose occupied columns are the projected footprint (drag, LIFE_ABI.md 15.59)."""
    cells = _cells(res, i)
    life = {}
    for a, b, z, tb, td in cells.values():
        life.setdefault((a, b, z), []).append((tb, td))
    twitch = {}
    out = []
    for t, u in zip(*res.spikes(i)):
        a, b, z, tb, td = cells[int(u)]
        if z != 1:
            continue
        zz, tz = twitch.get(int(u), (0.0, tb))
        zt = zz * math.exp(-(t - tz) / w.tau_z)
        zn = min(zt + 1.0, 1.0)
        twitch[int(u)] = (zn, t)
        nx = ny = 0.0
        for d, (da, db) in enumerate(OFFS):
            if not any(t0 < t <= t1 for t0, t1 in life.get((a + da, b + db, 1), [])):
                nx, ny = nx + UNITS[d][0], ny + UNITS[d][1]
        if zn - zt > 0 and math.hypot(nx, ny) > 1e-9:
            out.append((t, w.g_n * (zn - zt) * nx, w.g_n * (zn - zt) * ny, td))
    feet = [(tb, td) for a, b, z, tb, td in cells.values() if z == 0]
    return out, feet, [(a, b, tb, td) for a, b, z, tb, td in cells.values()]


def _euler_dot(w, strokes, feet, every, t_end, dt=1e-3, fill=True):
    """Explicit Euler (step dt) of the overdamped dot, dX/dt = F(t) / n_fill^drag_exp, with n_fill the filled
    footprint (the columns (a, b) occupied in any plane plus the tiles they enclose; ``fill=False``: the occupied
    columns alone, the drag before 15.61), and 0 without a sense-plane cell (no traction). F is the sum of the
    strokes' forces decaying with tau_z from onset to the cell's death: (X, Y, path)."""
    steps = int(round((t_end - w.t0) / dt))
    ts = w.t0 + dt * np.arange(steps)
    n_foot = np.zeros(steps)
    for tb, td in feet:
        n_foot += (ts >= tb) & (ts < td)
    per_col: dict = {}
    for a, b, tb, td in every:
        per_col.setdefault((a, b), np.zeros(steps, dtype=bool))
        per_col[(a, b)] |= (ts >= tb) & (ts < td)
    keys, occ = list(per_col), np.array(list(per_col.values()))
    edges = np.concatenate([[0], np.flatnonzero(np.any(occ[:, 1:] != occ[:, :-1], axis=0)) + 1, [steps]])
    n_col = np.zeros(steps)
    for s0, s1 in zip(edges[:-1], edges[1:]):  # one footprint per stretch of constant occupancy
        cols = [keys[i] for i in np.flatnonzero(occ[:, s0])]
        n_col[s0:s1] = spec.filled_footprint(cols, w.lattice) if fill else len(cols)
    inc = np.zeros((steps, 2))
    for s, fx, fy, stop in strokes:
        for when, sign in ((s, 1.0), (stop, -1.0)):
            j = int(math.ceil((when - w.t0) / dt)) if when < t_end else steps
            if j < steps:
                inc[j] += sign * np.array([fx, fy]) * math.exp(-(ts[j] - s) / w.tau_z)
    a = math.exp(-dt / w.tau_z)
    F, prev = np.empty_like(inc), np.zeros(2)
    for s0 in range(0, steps, 4096):  # F_j = a F_(j-1) + inc_j, as an exact scan per chunk
        x = inc[s0:s0 + 4096]
        p = a ** np.arange(len(x))
        F[s0:s0 + len(x)] = p[:, None] * (a * prev + np.cumsum(x / p[:, None], axis=0))
        prev = F[s0 + len(x) - 1]
    gam = np.where(n_foot > 0, np.maximum(n_col, 1.0) ** w.drag_exp, 1.0)
    V = np.where(n_foot[:, None] > 0, F / gam[:, None], 0.0)
    return V[:, 0].sum() * dt, V[:, 1].sum() * dt, np.hypot(V[:, 0], V[:, 1]).sum() * dt


def test_closed_form_dot_matches_euler_within_0_1_percent():
    lop = columns([(0, 0), (1, 0), (1, -1), (0, -1)])  # centre + 3 adjacent columns: a lopsided body
    tonic = V3.pack_program(V3.theta(b=2.0, tau_m=1, t_ref=0.5, kappa=1), alone=V3.theta(b=1.1, tau_m=4, t_ref=1,
                                                                                         kappa=1),
                            juvenile=V3.theta(b=1.5, tau_m=2, t_ref=1, kappa=1, p_div=1.0, zeta=-2))
    footless = [(a, b, 1, R3["contact"]) for a, b in hexdisk(1) if (a, b) != (0, 0)] + [(0, 0, 1, R3["juvenile"])]
    cases = [(catch(T=200.0), COLUMN3, RING1), (catch(T=200.0), COLUMN3, lop),
             (catch(T=200.0, drag_exp=1.0, g_n=2.0), COLUMN3, RING1),
             (catch(T=200.0), TURNOVER3, TURNOVER_BODY),  # births and deaths: faces, footprint and drag change
             (catch(T=60.0), tonic, footless)]  # no traction until the centre divides down and grows a foot
    for w, prog, init in cases:
        res = kernel3(w, [1, 2], program=prog, init=init)
        for i in range(2):
            strokes, feet, every = _strokes(res, i, w)
            X, Y, path = _euler_dot(w, strokes, feet, every, res["t_end"][i])
            led = res.ledger[i]
            assert led[L["path"]] > 5.0 and len(strokes) > 20, (w, led[L["path"]])
            assert abs(path - led[L["path"]]) < 1e-3 * led[L["path"]], (path, led[L["path"]])
            assert math.hypot(X - led[L["X_end"]], Y - led[L["Y_end"]]) < 1e-3 * led[L["path"]]
            assert len(strokes) == led[L["nudges"]]  # every stroke with dz > 0 and a face is one nudge


def test_footless_act_cells_add_drag():
    """Review fix (LIFE_ABI.md 15.59): the drag counts the projected footprint, every column (a, b) that holds a live
    cell in any plane, not the sense-plane cells alone. Two footless tonic drifters beside the 2-cell clicker pulled
    at drag 1 and beat the 4-column body; now they slow the dot like the columns they occupy (n_col 3 here), and
    traction still needs a sense-plane cell (15.44)."""
    prog = V3.pack_program(MOTOR3, alone=SENSE3, juvenile=CLICKER3, rim=QUIET3,
                           zygote=V3.theta(b=1.5, tau_m=8, t_ref=4, kappa=1))
    body = [(0, 0, 0, R3["juvenile"]), (0, 0, 1, R3["contact"]), (1, 0, 1, R3["zygote"]), (1, -1, 1, R3["zygote"])]
    w = catch(T=200.0)
    res = kernel3(w, [3, 4], program=prog, init=body)
    for i in range(2):
        strokes, feet, every = _strokes(res, i, w)
        path = res.ledger[i][L["path"]]
        _, _, euler = _euler_dot(w, strokes, feet, every, res["t_end"][i])
        _, _, feet_only = _euler_dot(w, strokes, feet, [(0, 0, *f) for f in feet], res["t_end"][i])
        assert path > 5.0 and abs(euler - path) < 1e-3 * path
        assert abs(feet_only / path - math.sqrt(3.0)) < 1e-2  # the old law: drag 1, the dot sqrt(3) faster


RING3 = [s for s in hexdisk(3) if max(abs(s[0]), abs(s[1]), abs(s[0] + s[1])) == 3]
INSIDE3 = [s for s in hexdisk(2) if s != (0, 0)]  # the 18 tiles a ring-3 body encloses besides its centre


def _same_dot(a, b) -> bool:
    """The dots of two batches moved bitwise alike: path, end point, nudges, clicks and their outcomes."""
    cols = [L[k] for k in ("path", "X_end", "Y_end", "nudges", "clicks", "captures", "misses")]
    return np.array_equal(bits(a.ledger[:, cols]), bits(b.ledger[:, cols]))


def test_a_hollow_ring_drags_like_the_filled_disk():
    """Red-team tweak RT-T1 (LIFE_ABI.md 15.61): the drag follows the body's extent, the filled footprint, so a
    hollow ring drags like the disk it encloses. The hollow ring 3 (centre and ring-3 columns: 19 occupied columns,
    37 filled tiles) and the same body with quiet receptor-less sense cells on the 18 enclosed tiles (37 columns)
    make the same strokes (faces read the act plane only) on the same drag, so their dots move bitwise alike, and
    the Euler re-integration with the filled footprint matches the hollow body; with the occupied columns alone
    (the drag before 15.61) it is off by about sqrt(37 / 19)."""
    hollow = columns([(0, 0)] + RING3)
    filled = hollow + [(a, b, 0, R3["rim"]) for a, b in INSIDE3]  # the rim row is QUIET3: g_r 0, never fires
    w = catch(T=200.0)
    a = kernel3(w, [1, 2, 3], program=COLUMN3, init=hollow)
    b = kernel3(w, [1, 2, 3], program=COLUMN3, init=filled)
    assert _same_dot(a, b) and a["path"].min() > 5.0 and a["clicks"].min() > 0
    for i in range(3):  # the hollow body's own cells spike bitwise alike in both
        (ta, ua), (tb, ub) = a.spikes(i), b.spikes(i)
        assert np.array_equal(bits(ta), bits(tb)) and np.array_equal(ua, ub)
        strokes, feet, every = _strokes(a, i, w)
        path = a.ledger[i][L["path"]]
        _, _, filled_path = _euler_dot(w, strokes, feet, every, a["t_end"][i])
        _, _, projected = _euler_dot(w, strokes, feet, every, a["t_end"][i], fill=False)
        assert abs(filled_path - path) < 1e-3 * path
        assert abs(projected / path - math.sqrt(37 / 19)) < 1e-2


def test_footless_cells_enclose_and_islands_do_not():
    """15.61 with footless cells: an act-plane ring with no sense cell under it (tonic, around a quiet centre column)
    encloses the tiles inside it like any body, so filling them with quiet sense cells changes nothing; islands
    (the centre and the six ring-3 corners) enclose nothing, so their footprint stays 7 columns (spec level:
    tests/test_life_spec_abi3.py)."""
    ring = [(0, 0, 0, R3["alone"]), (0, 0, 1, R3["contact"])] + [(a, b, 1, R3["contact"]) for a, b in RING3]
    filled = ring + [(a, b, 0, R3["alone"]) for a, b in INSIDE3]
    w = catch(T=200.0)
    a = kernel3(w, [4, 5], program=_TONIC_PROGRAM, init=ring)
    b = kernel3(w, [4, 5], program=_TONIC_PROGRAM, init=filled)
    assert _same_dot(a, b) and a["path"].min() > 1.0 and a["nudges"].min() > 100
    assert spec.filled_footprint(ISLANDS) == 7


def test_a_slit_to_the_outside_leaves_the_hole_free():
    """Recorded residual of 15.61 (review 2026-10-08): only tiles with no edge path to infinity are filled, so a
    one-column slit from a hole to the outside leaves the hole free. The thick hollow body (centre + rings 2-3, every
    plane) fills its ring-1 hole (37 tiles); cutting the two edge-sharing columns (2, 0) and (3, 0) opens it, and the
    body drags like its 29 columns although it spans the same disk (LIFE_ABI.md 15.61 has the measured discount).
    Closing either end of the slit closes the hole again. The kernel counts and drags the same."""
    thick = [(0, 0)] + [s for s in hexdisk(3) if max(abs(s[0]), abs(s[1]), abs(s[0] + s[1])) >= 2]
    slit = [s for s in thick if s not in ((2, 0), (3, 0))]
    counts = {"thick": (thick, 37), "slit": (slit, 29), "outer end closed": (slit + [(3, 0)], 37),
              "inner end closed": (slit + [(2, 0)], 36)}  # the ring-2 wall closes the hole; the notch stays free
    for name, (cols, n) in counts.items():
        assert spec.filled_footprint(cols) == build.filled_footprint(cols) == n, name
    w = catch(T=200.0)
    res = kernel3(w, [6, 7], program=COLUMN3, init=columns(slit))
    assert res["path"].min() > 5.0
    for i in range(2):
        strokes, feet, every = _strokes(res, i, w)
        _, _, path = _euler_dot(w, strokes, feet, every, res["t_end"][i])
        assert abs(path - res.ledger[i][L["path"]]) < 1e-3 * path  # the drag of 29 tiles: no hole is filled


# The `all` hash of 3 lives (seeds 11-13) of bodies that never enclose a tile, computed by the kernel of commit
# 8395c12 (BODY-1 v1, drag from the occupied columns). Their filled footprint is their occupied columns at every
# instant, so RT-T1 (15.61) must leave every one of them bitwise unchanged: full disks, hidden stacks, a lopsided
# body, islands, turnover, footless drifters, a footless ring that grows a foot, and a square prism.
CATCH_GOLDEN = {
    "ring 1": ("ebb3ad6fcad2d938", "e514aacbfa9d617d", "d4454d0cf784b840"),
    "ring 3 L4": ("5d4113f98ccce87a", "35851e7857541e43", "94459d8dd794534a"),
    "ring 2 + 2 hidden L4": ("f089898e545d0d83", "3563a5cf102a1657", "4fb21a7bcdf75b07"),
    "lopsided": ("6e3ca4debbaaf298", "6a0b8635194b5f86", "c82e4c8a20df74e2"),
    "islands": ("b426b8207d4a2304", "5685943920ec313c", "ebe0af4b9ca1e55f"),
    "turnover": ("b4f4b71167f49d5a", "98d60092e3ebade2", "22a056a3dc80d57d"),
    "runner x3 footless": ("381c82602eb704de", "4e6bdcda910807d0", "937f8647410f0990"),
    "footless then a foot": ("5815620dbacefe6e", "527540b71bb79214", "e72de59c931454f0"),
    "square4prism plus": ("940ac875b528e7ad", "a7874df74e46b3e1", "f25318845cca68cc"),
}


def _golden_catch_cases() -> dict:
    footless = [(a, b, 1, R3["contact"]) for a, b in hexdisk(1) if (a, b) != (0, 0)] + [(0, 0, 1, R3["juvenile"])]
    tonic = V3.pack_program(V3.theta(b=2.0, tau_m=1, t_ref=0.5, kappa=1), alone=V3.theta(b=1.1, tau_m=4, t_ref=1,
                                                                                         kappa=1),
                            juvenile=V3.theta(b=1.5, tau_m=2, t_ref=1, kappa=1, p_div=1.0, zeta=-2))
    run3 = hb.runner(*hb.RUNNER_PROTOTYPE, drifters=3)
    return {
        "ring 1": (catch(T=200.0), dict(program=COLUMN3, init=columns(hexdisk(1)))),
        "ring 3 L4": (catch("catch_v1_l4", T=150.0), dict(program=COLUMN3, init=columns(hexdisk(3)))),
        "ring 2 + 2 hidden L4": (catch("catch_v1_l4", T=150.0), dict(program=COLUMN3,
                                                                     init=columns(hexdisk(2), hidden=2))),
        "lopsided": (catch(T=200.0), dict(program=COLUMN3, init=columns([(0, 0), (1, 0), (1, -1), (0, -1)]))),
        "islands": (catch(T=200.0), dict(program=COLUMN3, init=columns(ISLANDS))),
        "turnover": (catch(T=200.0), dict(program=TURNOVER3, init=TURNOVER_BODY)),
        "runner x3 footless": (catch(T=200.0), dict(program=run3.program, init=list(run3.cells))),
        "footless then a foot": (catch(T=60.0), dict(program=tonic, init=footless)),
        "square4prism plus": (catch(T=150.0, lattice="square4prism"),
                              dict(program=COLUMN3, init=columns([(0, 0), (1, 0), (0, 1), (-1, 0), (0, -1)]))),
    }


def test_bodies_without_holes_live_bitwise_as_before_the_filled_footprint():
    cases = _golden_catch_cases()
    assert set(cases) == set(CATCH_GOLDEN)
    for label, (w, kw) in cases.items():
        res = kernel3(w, [11, 12, 13], **kw)
        assert [f"{int(h):016x}" for h in res.hashes[:, 0]] == list(CATCH_GOLDEN[label]), label


def test_surface_normal_faces_cancel_over_any_shape():
    """Every shared face is counted once in each direction (9.7.2): the faces of any act plane, holes and islands
    included, sum to zero up to rounding, and an isolated cell's face is exactly zero."""
    rng = np.random.default_rng(7)
    disk = hexdisk(4)
    shapes = [[s for s in disk if rng.random() < p] for p in (0.2, 0.5, 0.8) for _ in range(5)]
    shapes += [[s for s in disk if max(abs(s[0]), abs(s[1]), abs(s[0] + s[1])) in (2, 4)], ISLANDS, hexdisk(1)]
    for shape in shapes:
        occ = set(shape)
        nx = ny = 0.0
        for a, b in shape:
            empty = [d for d, (da, db) in enumerate(OFFS) if (a + da, b + db) not in occ]
            fx, fy = spec.exposed_face("hexprism", empty)
            nx, ny = nx + fx, ny + fy
        assert abs(nx) < 1e-12 and abs(ny) < 1e-12, (shape, nx, ny)
    assert spec.exposed_face("hexprism", range(6)) == (0.0, 0.0)


def _tonic_body(shape, hidden: int = 0):
    """Tonic act cells over silent sense cells (a footprint that never fires), rows of _TONIC_PROGRAM."""
    body = [(a, b, 0, R3["alone"]) for a, b in shape] + [(a, b, 1, R3["contact"]) for a, b in shape]
    return body + [(a, b, 2 + h, R3["alone"]) for h in range(hidden) for a, b in shape]


_TONIC_PROGRAM = V3.pack_program(TONIC, alone=QUIET3)


def test_uniform_firing_never_drifts_a_body_of_any_shape():
    # lockstep: every act cell twitches at the same instants with the same dz, so the strokes cancel in every
    # group, whatever the shape (lopsided, holed, scattered); only the rounding of the running force sum remains
    rng = np.random.default_rng(11)
    disk = hexdisk(3)
    shapes = [[s for s in disk if s == (0, 0) or rng.random() < p] for p in (0.3, 0.6, 0.9)]
    shapes += [[(0, 0), (1, 0), (2, 0), (2, -1)], [s for s in disk if s[0] >= 0], ISLANDS[:4] + [(1, 0)]]
    lock = catch(T=200.0, flags=V3.flags("lockstep"))
    for shape in shapes:
        res = kernel3(lock, [1, 2], program=_TONIC_PROGRAM, init=_tonic_body(shape))
        assert res["nudges"].min() > 0 or len(shape) == 1
        assert res["path"].max() < 1e-9 and np.abs(res.ledger[:, [L["X_end"], L["Y_end"]]]).max() < 1e-12, shape
    # jittered clocks: the cells fire at slightly different rates, so a lopsided body wanders, but with no standing
    # pull: over many lives its mean displacement is 0 (an offset law would drift it toward its heavy side)
    shape = [s for s in disk if s[0] >= 0 and s != (3, 0)]
    res = kernel3(catch(T=400.0), list(range(64)), program=_TONIC_PROGRAM, init=_tonic_body(shape), threads=4)
    xy = res.ledger[:, [L["X_end"], L["Y_end"]]]
    assert res["path"].min() > 0.5  # it does move
    se = xy.std(axis=0, ddof=1) / math.sqrt(len(xy))
    assert np.all(np.abs(xy.mean(axis=0)) < 4 * se), (xy.mean(axis=0), se)


def test_islands_exert_no_force():
    # the prototype's island cheat (BODY_DESIGN_PROPOSAL.md 1): the centre column and the 6 ring-3 corner columns.
    # Every act cell is isolated in the act plane, so its face is 0 and the body never moves, though it senses,
    # relays and clicks; hidden cells above an island change nothing
    w = catch("catch_v1_l4", T=400.0)
    for hidden in (2, 0):
        res = kernel3(w, list(range(16)), program=COLUMN3, init=columns(ISLANDS, hidden=hidden), threads=4)
        assert not res["nudges"].any() and not res["path"].any() and not res["X_end"].any()
        assert res["clicks"].sum() > 0 and res["rec_events"].min() > 0 and res["spikes"].min() > 100
    tonic = kernel3(catch(T=200.0), [1, 2], program=_TONIC_PROGRAM, init=_tonic_body(ISLANDS))
    assert not tonic["nudges"].any() and not tonic["path"].any() and tonic["spikes"].min() > 100
    compact = kernel3(w, list(range(16)), program=COLUMN3, init=RING1, threads=4)  # the same 14 cells, together
    assert compact["F"].mean() > res["F"].mean() + 0.5 and compact["path"].min() > 10


def _key_replay(t_spikes, kappa: float, w) -> int:
    """Clicks of a hotspot cell that fires at ``t_spikes`` (9.7.4): its twitch from the spike times, then the key."""
    armed, z, tz, clicks = True, 0.0, w.t0, 0
    for t in t_spikes:
        zt = z * math.exp(-(t - tz) / w.tau_z)
        zn = min(zt + kappa, 1.0)
        z, tz = zn, t
        armed, click = spec.key_step(armed, zt, zn, w.th_click, w.th_rel)
        clicks += click
    return clicks


def test_clicks_happen_only_at_the_hotspot_with_hysteresis():
    w = catch(T=200.0)
    # no act cell at the hotspot (0, 0, 1): a twitching act ring around it pulls but never clicks
    ring = [(a, b, 1, R3["contact"]) for a, b in hexdisk(1) if (a, b) != (0, 0)]
    res = kernel3(w, range(4), program=_TONIC_PROGRAM, init=[(a, b, 0, R3["alone"]) for a, b in hexdisk(1)] + ring)
    assert res["nudges"].min() > 0 and not res["clicks"].any()
    # tonic cells straight under and above the hotspot site (z = 0 and z = 2) are not at the hotspot
    tower = V3.pack_program(TONIC)
    res = kernel3(catch("catch_v1_l4", T=200.0), range(4), program=tower, init=[(0, 0, 0, 1), (0, 0, 2, 1)])
    assert res["spikes"].min() > 40 and not res["clicks"].any()
    # the hotspot's own cell: the key clicks at an upward crossing of th_click while armed and re-arms below th_rel;
    # the count equals a replay of key_step over the cell's own spike train: tonic cells that hold the key or release
    # it between twitches, and half twitches driven by a sensor's Poisson relays, which press only when two come close
    tried = []
    for b, tau_m, t_ref, kappa in ((2.0, 1, 0.5, 1.0), (1.875, 8, 2, 1.0), (1.125, 1, 4, 1.0), (2.0, 1, 0.5, 0.5),
                                   (1.5, 2, 1.5, 0.5), (2.0, 1, 0.5, 0.25), (1.875, 8, 2, 0.5), (0.0, 2, 2, 0.5),
                                   (0.0, 2, 1, 0.5), (0.0, 1, 0.5, 0.25)):
        hot = V3.theta(b=b, tau_m=tau_m, t_ref=t_ref, kappa=kappa, w0=1.0 if b == 0 else 0.0)
        prog = V3.pack_program(hot, alone=V3.theta(g_r=1.0, emit0=1, tau_m=2, t_ref=0.5))
        init = [(0, 0, 1, R3["contact"])] + ([(0, 0, 0, R3["alone"])] if b == 0 else [])  # driven: a sensor below
        res = kernel3(replace(w, lam_bg=0.5), range(2), program=prog, init=init)
        for i in range(2):
            t, u = res.spikes(i)
            mine = t[u == spec.uid_initial(i, 0)]
            assert res["clicks"][i] == _key_replay(mine, kappa, w), (b, tau_m, t_ref, kappa)
            assert res["captures"][i] + res["misses"][i] == res["clicks"][i]
            tried.append((len(mine), res["clicks"][i]))
    spikes, clicks = np.array(tried).T
    assert np.any((clicks == 1) & (spikes > 100))  # a tonic hotspot holds the key: one click
    assert np.any((clicks == spikes) & (spikes > 10))  # a slow one releases between twitches: every spike clicks
    assert np.any((clicks > 1) & (clicks < spikes / 2))  # summed half twitches press now and then
    assert np.any((clicks == 0) & (spikes > 10))  # lone half twitches never reach th_click
    off = kernel3(replace(w, flags=V3.flags("motor_off")), range(2), program=V3.pack_program(TONIC),
                  init=[(0, 0, 1, 0)])
    assert off["spikes"].min() > 10 and not off["clicks"].any()


def _timer_times(w, seed: int) -> list[float]:
    """The target's timer re-placements below t0 + T (9.7.3): a Poisson chain of mean t_resp keyed by its counter."""
    if w.t_resp <= 0:
        return []
    out, t, k = [], w.t0, 0
    while True:
        t = spec.poisson_next(seed, spec.S_RTIME, 0, k, t, w.t_resp)
        if t >= w.t0 + w.T:
            return out
        out.append(t)
        k += 1


def test_captures_misses_and_respawns_are_accounted():
    seeds = list(range(24))
    battery = [(catch(T=400.0), dict(program=COLUMN3, init=RING1)),
               (catch(T=400.0, t_resp=10.0, t_open=100.5), dict(program=COLUMN3, init=RING1)),
               (catch(T=300.0, t_resp=0.0), dict(program=COLUMN3, init=RING1)),
               (catch(T=300.0, b2_amp=1.0, b2_value=-5.0, b2_p=0.5), dict(program=COLUMN3, init=RING1)),
               (catch(T=300.0, b2_amp=1.0, b2_value=100.0, b2_mode=1), dict(program=COLUMN3, init=RING1)),
               (catch(T=300.0), dict(program=TURNOVER3, init=TURNOVER_BODY)),
               (catch("catch_v1_l4", T=150.0, n_max=120), dict(genome=grn3(25)))]
    for w, kw in battery:
        res = kernel3(w, seeds, threads=4, **kw)
        assert np.array_equal(res["clicks"], res["captures"] + res["misses"] + res["b2_clicks"])
        b2_income = w.b2_value * res["b2_clicks"] if w.b2_value > 0 else 0.0
        assert np.array_equal(res["income"], w.R_cap * res["captures"] + b2_income)
        assert np.all(res["zone_samples"] <= res["samples"]) and np.all(res["dist_sum"] > 0)
        for i, s in enumerate(seeds):  # the timer runs whatever the body does, keyed by its own counter
            t_end = res["t_end"][i]
            want = sum(w.t0 + w.t_open <= t < t_end for t in _timer_times(w, s))
            assert res["respawns"][i] == want, (w, s)
        assert res["clicks"].sum() > 0 and (w.t_resp == 0) == (res["respawns"].sum() == 0)
        if w.b2_amp > 0:
            assert res["b2_clicks"].sum() > 0
    # the capture radius decides the outcome: 0 turns every click into a miss, a huge radius every click into a
    # capture; the miss cost is a pure charge (no column but cost, net and F moves)
    base = catch(T=300.0)
    hits = kernel3(replace(base, rho_c=1e6), seeds, program=COLUMN3, init=RING1, threads=4)
    none = kernel3(replace(base, rho_c=0.0), seeds, program=COLUMN3, init=RING1, threads=4)
    assert np.array_equal(hits["captures"], hits["clicks"]) and not hits["misses"].any()
    assert not none["captures"].any() and np.array_equal(none["misses"], none["clicks"]) and none["clicks"].sum() > 0
    one = kernel3(base, seeds, program=COLUMN3, init=RING1, threads=4)
    three = kernel3(replace(base, c_miss=3.0), seeds, program=COLUMN3, init=RING1, threads=4)
    same_cols = [c for c in V3.LEDGER if c not in ("cost", "net", "F")]
    assert np.array_equal(bits(one.ledger[:, [L[c] for c in same_cols]]), bits(three.ledger[:, [L[c] for c in
                                                                                                   same_cols]]))
    assert np.allclose((one["F"] - three["F"]) * base.T, (3.0 - base.c_miss) * one["misses"], rtol=0, atol=1e-9)
    assert one["misses"].sum() > 0 and one["captures"].sum() > 0


def test_world_timers_below_the_step_floor_are_refused_so_every_life_ends():
    """Review fix (LIFE_ABI.md 4.7, 15.58): a mean timer interval below half an ulp of t never advanced world time,
    so ``life_run`` never returned (t_resp 1e-20 hung; 1e-5 made about 4e5 re-placements in 4 units). Both world
    timers are now 0 (off) or at least 2^-10, like every delay and tick period, and the floor itself runs."""
    for key in ("t_resp", "tau_turn"):
        for bad in (1e-20, 1e-5, 2.0 ** -11):
            with pytest.raises(ValueError):
                kernel3(catch(T=4.0, **{key: bad}), [1], program=COLUMN3, init=columns([(0, 0)]))
    res = kernel3(catch(T=4.0, t_resp=2.0 ** -10, tau_turn=2.0 ** -10), [1], program=COLUMN3,
                  init=columns([(0, 0)]))
    assert 3000 < res["respawns"][0] < 5500  # about T / t_resp = 4096 timer re-placements


def test_every_capture_re_places_the_target_around_the_dot():
    # the reference's world log (the CATCH words of 9.6): a capture is followed, after its time group, by PLACE(0,
    # cause 1) at the same time, at a distance in [R_min, R_max] of the dot; timer placements (cause 2) sit at the
    # replayed timer times; the second blob follows the target (cause 3) in DECOY mode
    for w, seed in ((catch(T=300.0), 42), (catch(T=300.0, b2_amp=1.0, b2_value=-5.0, b2_p=0.5), 4)):
        r = reference3(w, seed, program=COLUMN3, init=RING1, records=True)
        log = [(x[0], float(np.uint64(x[1]).view(np.float64)), x) for x in r.world]
        clicks = [(t, x) for kind, t, x in log if kind == 11]
        places = [(t, x) for kind, t, x in log if kind == 12]
        assert sum(x[2] == 1 for _, x in clicks) == r["captures"] > 0
        for t, x in clicks:
            if x[2] != 1:
                continue
            X, Y = (float(np.uint64(v).view(np.float64)) for v in x[3:5])
            p = [y for tp, y in places if tp == t and y[2] == 0 and y[3] == 1]
            assert len(p) == 1
            d = math.hypot(float(np.uint64(p[0][4]).view(np.float64)) - X,
                           float(np.uint64(p[0][5]).view(np.float64)) - Y)
            assert w.R_min - 1e-9 <= d <= w.R_max + 1e-9
        timer = [t for t, y in places if y[2] == 0 and y[3] == 2]
        assert timer == _timer_times(w, seed) and len(timer) == r["respawns"]
        if w.b2_amp > 0:
            assert sum(y[2] == 1 and y[3] == 3 for _, y in places) == sum(y[2] == 0 and y[3] in (1, 2)
                                                                           for _, y in places)


def _replay_receptors(w, seed: int, sites, t_end: float) -> tuple[int, int, list[int]]:
    """Candidates, accepts and per-site deliveries of initial sense cells at ``sites`` (uid index = position) on a
    dot that never moves, with a target that runs straight from its first placement (no turns, no timer, no
    clicks): the thinning of 9.7.5 replayed with spec's closed forms, bitwise."""
    lam = spec.lambda_max(w)
    x0, y0 = spec.blob_place(seed, 0, 0, 0.0, 0.0, w.R_min, w.R_max)
    vx, vy = spec.blob_heading(seed, 0, 0, w.v_t)
    cand = acc = 0
    got = []
    for j_cell, (a, b) in enumerate(sites):
        got.append(0)
        uid = spec.uid_initial(seed, j_cell)
        ox, oy = lattice.to_xy("hex", a, b)
        px, py = 0.0 + ox, 0.0 + oy
        t, j = w.t0, 0
        while True:
            t = spec.receptor_next(seed, uid, j, t, lam)
            if t >= t_end:
                break
            cand += 1
            dt = t - w.t0
            rate = spec.receptor_rate(w, px, py, (x0 + vx * dt, y0 + vy * dt))
            if spec.receptor_accepts(seed, uid, j, rate, lam):
                acc += 1
                got[-1] += t + w.d_min < t_end
            j += 1
    return cand, acc, got


def test_receptor_events_arrive_at_the_rate_of_the_screen_point_under_each_sense_cell():
    sites = hexdisk(1)
    # sense cells that emit nothing (and seldom fire: the centre's bias holds its membrane near -2), so nothing moves
    sense = V3.pack_program(V3.theta(g_r=0.375, b=-2), alone=V3.theta(g_r=-0.75))
    body = [(a, b, 0, R3["alone"] if (a, b) != (0, 0) else R3["contact"]) for a, b in sites]
    gains = [0.75 if (a, b) != (0, 0) else 0.375 for a, b in sites]
    for w in (catch(T=300.0, tau_turn=0.0, t_resp=0.0), catch(T=300.0, tau_turn=0.0, t_resp=0.0, v_t=0.0, sigma=3.0),
              catch(T=300.0, tau_turn=0.0, t_resp=0.0, lam_s=5.0, lam_bg=0.5, R_min=0.0, R_max=2.0)):
        res = kernel3(w, range(8), program=sense, init=body)
        for i in range(8):
            cand, acc, got = _replay_receptors(w, i, sites, w.t0 + w.T)
            assert (res["rec_cand"][i], res["rec_accept"][i], res["rec_events"][i]) == (cand, acc, sum(got)), (w, i)
            assert res["rec_gain"][i] == sum(g * n for g, n in zip(gains, got))  # |g_r| per delivered event
        assert res["rec_accept"].sum() > res["rec_events"].sum() * 0.99 > 0 and not res["contact_events"].any()
        assert np.all(res["rec_cand"] > res["rec_accept"])
    # the kept candidates are a Poisson process at the true rate: pooled counts match the integral of the rate
    w = catch(T=400.0, tau_turn=0.0, t_resp=0.0, R_min=0.0, R_max=1.5)
    res = kernel3(w, range(32), program=sense, init=body, threads=4)
    ts = w.t0 + np.arange(0.0, w.T, 0.01) + 0.005
    expect = 0.0
    for s in range(32):
        x0, y0 = spec.blob_place(s, 0, 0, 0.0, 0.0, w.R_min, w.R_max)
        vx, vy = spec.blob_heading(s, 0, 0, w.v_t)
        for a, b in sites:
            ox, oy = lattice.to_xy("hex", a, b)
            d2 = (ox - x0 - vx * (ts - w.t0)) ** 2 + (oy - y0 - vy * (ts - w.t0)) ** 2
            expect += np.sum(w.lam_bg + w.lam_s * np.exp(-d2 / (2 * w.sigma ** 2))) * 0.01
    got = res["rec_accept"].sum()
    assert abs(got - expect) < 4 * math.sqrt(expect), (got, expect)
    assert abs(res["rec_cand"].sum() - spec.lambda_max(w) * w.T * 7 * 32) < 4 * math.sqrt(spec.lambda_max(w) * w.T
                                                                                           * 7 * 32)
    # without a target term every candidate is kept: the background is lam_bg per sense cell per unit
    flat = kernel3(catch(T=400.0, lam_s=0.0, lam_bg=0.5), range(16), program=sense, init=body)
    assert np.array_equal(flat["rec_accept"], flat["rec_cand"])
    n = 0.5 * 400.0 * 7 * 16
    assert abs(flat["rec_cand"].sum() - n) < 4 * math.sqrt(n)


def _plane_time(cells: dict, t_from: float, t_end: float) -> list[float]:
    out = [0.0, 0.0, 0.0]
    for _a, _b, z, tb, td in cells.values():
        lo, hi = max(tb, t_from), min(td, t_end)
        out[min(z, 2)] += max(0.0, hi - lo)
    return out


LEDGER_LIVES = [  # (label, world, organism): reflexes, turnover, growth, guards, both blobs, forks and t_open
    ("column", catch(T=300.0), dict(program=COLUMN3, init=RING1)),
    ("column L4 hidden t_open", catch("catch_v1_l4", T=300.0, t_open=99.5), dict(program=COLUMN3, init=columns(
        hexdisk(1), hidden=2))),
    ("turnover", catch(T=300.0), dict(program=TURNOVER3, init=TURNOVER_BODY)),
    ("grower", catch("catch_v1_l4", T=150.0, n_max=200), dict(program=GROWER3)),
    ("grn guard", catch("catch_v1_l4", T=150.0, n_max=60), dict(genome=grn3(25))),
    ("grn L2", catch(T=80.0), dict(genome=grn3(21, p_div=0.4))),
    ("decoy", catch(T=300.0, b2_amp=1.0, b2_value=-5.0, b2_p=0.5), dict(program=COLUMN3, init=RING1)),
    ("twin", catch(T=300.0, b2_amp=1.0, b2_value=100.0, b2_mode=1), dict(program=COLUMN3, init=RING1)),
    ("motor fork", catch(T=300.0, t_fork=150.0, t_open=150.0, fork_flags=V3.flags("motor_off")),
     dict(program=COLUMN3, init=RING1)),
    ("receptor fork", catch(T=300.0, t_fork=100.0, t_open=120.0, fork_flags=V3.flags("receptor_off")),
     dict(program=COLUMN3, init=RING1)),
    ("kill panel", catch(T=300.0, kill_t=100.0, kill_frac=0.4, t_open=99.75), dict(program=COLUMN3, init=RING1)),
]


@pytest.mark.parametrize("label,w,kw", LEDGER_LIVES, ids=[c[0] for c in LEDGER_LIVES])
def test_f_times_t_is_income_minus_every_charge_in_catch(label, w, kw):
    res = kernel3(w, range(6), threads=2, **kw)
    t_open = w.t0 + w.t_open
    for i in range(6):
        led = res.ledger[i]
        col = V3.column_cost(led, w)
        assert led[L["net"]] == led[L["income"]] - col - led[L["guard_charge"]]
        assert abs(led[L["F"]] * (w.T - w.t_open) - led[L["net"]]) <= 1e-12 * max(1.0, abs(led[L["net"]]))
        assert bits(V3.fitness(led, w)) == bits(led[L["F"]])
        assert abs(led[L["cost"]] - col) <= 1e-9 * max(1.0, col)
        assert not int(led[L["status"]]) & (spec.STATUS["ledger_mismatch"] | spec.STATUS["capacity"])
        # the counted columns rebuilt from the logs: spikes from the raster, cells and cell-time per plane from the
        # fate log (its z column)
        t, _ = res.spikes(i)
        assert led[L["spikes"]] == np.sum(t >= t_open)
        cells = _cells(res, i)
        live = [c for c in cells.values() if c[4] > led[L["t_end"]]]
        assert [led[L[c]] for c in ("n_S_end", "n_M_end", "n_H_end")] == [
            sum(min(c[2], 2) == p for c in live) for p in range(3)]
        rebuilt = _plane_time(cells, t_open, led[L["t_end"]])
        for c, want in zip(("live_S", "live_M", "live_H"), rebuilt):
            assert abs(led[L[c]] - want) <= 1e-9 * max(1.0, want), (c, led[L[c]], want)
        assert abs(led[L["live_time"]] - sum(rebuilt)) <= 1e-9 * max(1.0, sum(rebuilt))
        assert led[L["samples"]] == sum(c >= t_open for c in range(int(w.t0) + 1, int(led[L["t_end"]])))
    # costs never feed back into the life: another cost table re-prices the same records exactly
    priced = replace(w, c_live=0.03, c_spike=0.01, c_tw=0.02, c_msg=0.002, c_miss=2.5, c_rec=0.01, c_div=0.25,
                     b2_value=w.b2_value * 2)
    other = kernel3(priced, range(6), threads=2, **kw)
    keep = [L[c] for c in V3.LEDGER if c not in ("cost", "net", "F", "guard_charge", "income")]
    assert np.array_equal(bits(other.ledger[:, keep]), bits(res.ledger[:, keep])), label
    assert np.array_equal(bits(other["F"]), bits(V3.fitness(other.ledger, priced)))
    if w.b2_value <= 0:
        assert np.array_equal(bits(other["F"]), bits(V3.fitness(res.ledger, priced)))
