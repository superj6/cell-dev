"""Growth and death tests (docs/ONE_LIFE_DESIGN.md, TESTS: test_life_growth_death.py): earliest-claim arbitration,
contact views from notices, uid-checked delivery, apoptosis and refill, left-limit claims, extinction, guards,
view-gated division and mirror symmetry of placement when chi = 0."""
from collections import defaultdict
from dataclasses import replace

import numpy as np
import pytest

from src import lattice
from src.life import handbuilt as hb
from src.life import spec
from tests.life_helpers import BUSY, ROW, fate_uid, kernel, mismatch, r25, reference, same, tick_times

LOCK = spec.flags("lockstep")
DIVIDER = spec.theta(p_div=1.0)  # silent; claims at every tick that sees an empty slot


def _check_site_histories(kinds: np.ndarray, f: np.ndarray) -> int:
    """Every site alternates birth, death, birth, ... with birth indices 0, 1, 2, ...; a birth needs the site empty
    at t- (its last occupant died strictly earlier); a reject (occupied) needs a live occupant at t- or a same-instant
    winner. Returns the number of refills checked."""
    by_site = defaultdict(list)
    for (kind, _uid, _mother, a, b, aux), (t, *_rest) in zip(kinds.tolist(), f.tolist()):
        by_site[(a, b)].append((t, kind, aux))
    refills = 0
    for events in by_site.values():
        occupied, last_death, births, last_birth = False, -np.inf, 0, -np.inf
        for t, kind, aux in events:  # canonical order within one site: claims, then the occupant's own events
            if kind == 1:
                assert not occupied and last_death < t and aux == births
                occupied, births, last_birth = True, births + 1, t
                refills += aux >= 1
            elif kind == 2:
                assert occupied and last_birth < t
                occupied, last_death = False, t
            elif aux == 0:
                assert occupied or last_birth == t or last_death == t
    return refills


def _ring2():
    """A full hex disk of radius 2 minus its centre: each inner cell's only empty contact is the centre."""
    sites = [(a, b) for a in range(-2, 3) for b in range(-2, 3) if lattice.in_disk("hex", a, b, 2) and (a, b) != (0, 0)]
    inner = [s for s in sites if lattice.in_disk("hex", *s, 1)]
    init = [(a, b, -1) for a, b in inner] + [(a, b, ROW["rim"]) for a, b in sites if (a, b) not in inner]
    prog = spec.pack_program(DIVIDER, alone=spec.theta(), rim=spec.theta())
    return prog, init, len(inner)


@pytest.mark.parametrize("lock", [False, True])
def test_earliest_claim_wins_and_the_losers_are_still_charged(lock):
    prog, init, n_in = _ring2()
    w = spec.world(T=60.0, flags=LOCK if lock else 0)
    for seed in (1, 2, 3, 4):
        uids = [spec.uid_initial(seed, j) for j in range(n_in)]
        claim = [min(t for t in tick_times(w, seed, u, *init[j][:2], 0.0, w.T) if t >= w.d_min)
                 for j, u in enumerate(uids)]
        daughters = [spec.uid_daughter(seed, u, 0) for u in uids]
        win = min(range(n_in), key=lambda j: (claim[j], daughters[j]))  # earliest arrival, then lowest daughter uid
        t_b = claim[win] + w.d_min
        claimants = [j for j in range(n_in) if claim[j] < t_b + w.d_min]  # the rest hear of the newborn first
        if lock:
            assert len(set(claim)) == 1 and len(claimants) == n_in  # every claim lands at the same instant
        res = kernel(w, [seed], program=prog, init=init)
        assert not mismatch(res, 0, reference(w, seed, program=prog, init=init))
        assert same(res, kernel(replace(w, window_h=0.125), [[seed, 0, 7, 0]], program=prog, init=init))
        assert res["births"][0] == 1 and res["claims"][0] == len(claimants) >= 2
        assert res["rejects"][0] == len(claimants) - 1
        kinds, f = res.fates(0)
        born = kinds[kinds[:, 0] == 1][-1]
        assert fate_uid(born[1]) == daughters[win] and fate_uid(born[2]) == uids[win]
        assert tuple(born[3:5]) == (0, 0) and f[kinds[:, 0] == 1][-1, 0] == t_b
        rej = kinds[:, 0] == 3
        assert sorted(fate_uid(m) for m in kinds[rej, 2]) == sorted(uids[j] for j in claimants if j != win)
        assert np.all(f[rej, 0] >= t_b) and np.all(kinds[rej, 3:5] == 0)
        led = res.ledger[0]
        assert led[spec.L["cost"]] == pytest.approx(w.c_div * len(claimants) + w.c_live * led[spec.L["live_time"]],
                                                   rel=1e-12)
        assert led[spec.L["F"]] == pytest.approx(-led[spec.L["cost"]] / w.T, rel=1e-12)


def test_a_newborns_view_fills_from_replies_at_two_d_min():
    """Neighbours learn of a birth at t_b + d_min; the newborn learns its neighbours from their replies at
    t_b + 2 d_min. Every spike is charged c_msg per known live contact, so contact_events counts exactly the mother's
    spikes from t_b + d_min on and the daughter's spikes from t_b + 2 d_min on."""
    mother = spec.theta(b=1.5, tau_m=2, t_ref=1, emit0=1, p_div=1.0)
    daughter = spec.theta(b=2.0, tau_m=1, t_ref=0.5, emit0=1)
    prog = spec.pack_program(daughter, alone=daughter, rim=mother, timer_step=1.0, k_grow=1.0)
    w = spec.world(T=40.0)
    early = 0
    for seed in range(6):
        res = kernel(w, [seed], program=prog, init=[(0, 0, ROW["rim"])])
        assert not mismatch(res, 0, reference(w, seed, program=prog, init=[(0, 0, ROW["rim"])]))
        assert res["births"][0] == 1 and res["claims"][0] == 1
        kinds, f = res.fates(0)
        t_b, d_uid = f[1, 0], fate_uid(kinds[1, 1])
        t, u = res.spikes(0)
        tm, td = t[u == spec.uid_initial(seed, 0)], t[u == d_uid]
        early += int(np.sum(td < t_b + 2 * w.d_min))
        assert res["contact_events"][0] == np.sum(tm >= t_b + w.d_min) + np.sum(td >= t_b + 2 * w.d_min)
    assert early >= 6  # the daughter fires before it knows anyone, and those spikes cost no contact events


def _dropped_scenario():
    """Lockstep. S at (0,0) fires tonically with a 3-unit conduction delay. V at (1,0) dies at its first tick (t = 2).
    M at (1,-1), whose other contacts are all occupied, refills V's site with W at t = 4.5. S's two spikes sent to V
    before it heard of the death arrive at 3.69 (empty site) and 4.89 (W's site, but addressed to V)."""
    s = spec.theta(b=2.0, tau_m=1, t_ref=0.5, emit0=1, delta=2)
    v = spec.theta(p_die=1.0)
    m = spec.theta(p_div=1.0)
    det = spec.theta(b=0.0, tau_m=1, t_ref=0.5, w0=2.0)  # fires at any arrival delivered to it
    prog = spec.pack_program(m, alone=det, juvenile=det, rim=v, zygote=s, juv_ticks=1000.0)
    init = [(0, 0, ROW["zygote"]), (1, 0, ROW["rim"]), (1, -1, ROW["contact"])]
    init += [(a, b, ROW["alone"]) for a, b in ((2, -1), (2, -2), (1, -2), (0, -1))]
    return prog, init


def test_arrivals_at_a_dead_or_reoccupied_site_are_dropped_by_uid():
    prog, init = _dropped_scenario()
    w = spec.world(T=40.0, flags=LOCK)
    seed = 3
    res = kernel(w, [seed], program=prog, init=init)
    assert not mismatch(res, 0, reference(w, seed, program=prog, init=init))
    t, u = res.spikes(0)
    ts = t[u == spec.uid_initial(seed, 0)]
    sent_to_v = ts[(ts >= 0.5) & (ts < 2.5)]  # S knows V from its BORN notice (0.5) until its DIED notice (2.5)
    assert len(sent_to_v) == 2 and sent_to_v[0] + 3.0 < 4.5 < sent_to_v[1] + 3.0
    assert res["arrivals_dropped"][0] == 2
    kinds, f = res.fates(0)
    w_row = kinds[(kinds[:, 0] == 1) & (kinds[:, 3] == 1) & (kinds[:, 4] == 0) & (kinds[:, 5] == 1)]
    assert len(w_row) == 1
    w_uid = fate_uid(w_row[0, 1])
    first_to_w = ts[ts >= 5.0][0] + 3.0  # S hears of W at 4.5 + d_min
    assert t[u == w_uid][0] == first_to_w  # the arrival addressed to V at 4.89 never reached W


def test_apoptosis_empties_the_site_and_a_neighbour_refills_it():
    prog, init = _dropped_scenario()
    w = spec.world(T=40.0, flags=LOCK)
    res = kernel(w, [3], program=prog, init=init)
    kinds, f = res.fates(0)
    at_v = [(r[0], fate_uid(r[2]), r[5], x[0]) for r, x in zip(kinds.tolist(), f.tolist()) if tuple(r[3:5]) == (1, 0)]
    # V is born at t0 (birth index 0) and dies at its first tick; M's daughter refills the site (birth index 1)
    assert at_v == [(1, 0, 0, 0.0), (2, 0, 1, 2.0), (1, spec.uid_initial(3, 2), 1, 4.5)]
    assert res["deaths"][0] == 1 and res["births"][0] == 1 and res["claims"][0] == 1 and res["n_end"][0] == 7
    for w2 in (spec.world(T=200.0), spec.world(T=200.0, flags=LOCK)):  # turnover in growing bodies
        prog2 = r25(p_die=2 ** -4)
        lives = kernel(w2, list(range(12)), program=prog2)
        refills = sum(_check_site_histories(*lives.fates(i)) for i in range(12))
        assert refills > 20 and lives["deaths"].sum() > 50


def _race_scenario():
    """Lockstep with P0 = 0.5, so a claim (sent at a tick, landing d_min later) can land exactly at another cell's tick.
    Q at (1,0) claims the empty site X = (0,0) at t = 0.5; V is born there at 1.0. M at (-1,0) has not heard of V and
    claims X at 1.0; its claim lands at 1.5, the instant V dies at its first tick. Q and M then claim X again at 2.0
    and tie at 2.5. Every other contact of Q, M and X is a silent filler."""
    dies = spec.theta(p_die=1.0)  # the "alone" row: a newborn at X dies at its first tick (it knows no one yet)
    prog = spec.pack_program(DIVIDER, alone=dies, juvenile=spec.theta(), rim=spec.theta(), juv_ticks=1.0,
                             timer_step=1.0, k_grow=4.0)
    q, m = (1, 0), (-1, 0)
    filler = {(a + da, b + db) for a, b in (q, m, (0, 0)) for da, db in lattice.offsets("hex")} - {q, m, (0, 0)}
    init = [(*q, ROW["contact"]), (*m, -1)] + [(a, b, ROW["rim"]) for a, b in sorted(filler)]
    return prog, init


def test_a_claim_racing_a_death_follows_the_left_limit_rule():
    prog, init = _race_scenario()
    w = spec.world(T=20.0, P0=0.5, flags=LOCK)
    for seed in (1, 2, 3):
        res = kernel(w, [seed], program=prog, init=init)
        assert not mismatch(res, 0, reference(w, seed, program=prog, init=init))
        for h, order in ((0.5, 1), (0.25, 2), (0.125, 3)):
            assert same(res, kernel(replace(w, window_h=h), [[seed, 0, order, 0]], program=prog, init=init))
        for tie in (1, 2, 3):
            assert same(res, kernel(w, [[seed, tie, 0, tie]], program=prog, init=init))
        uq, um = spec.uid_initial(seed, 0), spec.uid_initial(seed, 1)
        winner = min((spec.uid_daughter(seed, uq, 1), uq), (spec.uid_daughter(seed, um, 1), um))
        loser = um if winner[1] == uq else uq
        kinds, f = res.fates(0)
        at_x = [(int(r[0]), fate_uid(r[2]), float(x[0])) for r, x in zip(kinds, f) if r[3] == 0 and r[4] == 0]
        assert at_x == [(1, uq, 1.0), (3, um, 1.5), (2, uq, 1.5), (1, winner[1], 2.5), (3, loser, 2.5),
                        (2, winner[1], 3.0)]
        assert res["claims"][0] == 4 and res["births"][0] == 2 and res["rejects"][0] == 2 and res["deaths"][0] == 2
        _check_site_histories(kinds, f)


def test_extinction_ends_the_life_and_closes_the_ledger():
    dies = spec.pack_program(spec.theta(b=1.875, tau_m=8, t_ref=2, kappa=1, p_die=1.0))
    accrued = [c for c in spec.LEDGER if c not in ("F", "t_end", "guard_charge", "net")]
    for seed in range(4):
        short, longer = (kernel(spec.world(T=T), [seed], program=dies) for T in (100.0, 300.0))
        t_ext = tick_times(spec.world(), seed, spec.uid_initial(seed, 0), 0, 0, 0.0, 10.0)[0]
        for r, T in ((short, 100.0), (longer, 300.0)):
            assert r.status("extinct")[0] and r["t_ext"][0] == t_ext and r["live_time"][0] == t_ext
            assert r["n_end"][0] == 0 and r["t_end"][0] == T and r["deaths"][0] == 1
            assert r["F"][0] == r["net"][0] / T and r["net"][0] == r["income"][0] - r["cost"][0]
        assert all(short[c][0] == longer[c][0] for c in accrued)
    # the last cell dies while its claim is in flight: the life is extinct only once the daughter has died too
    prune = spec.pack_program(DIVIDER, alone=DIVIDER, prune=1.0, k_keep=0.0, k_die=2.0, timer_step=1.0, k_grow=1.0)
    w = spec.world(T=50.0, P0=0.25, flags=LOCK)
    res = kernel(w, [5], program=prune)
    assert not mismatch(res, 0, reference(w, 5, program=prune))
    kinds, f = res.fates(0)
    assert kinds[:, 0].tolist() == [1, 2, 1, 2] and f[:, 0].tolist() == [0.0, 0.5, 0.75, 1.0]
    assert res.status("extinct")[0] and res["t_ext"][0] == 1.0 and res["live_time"][0] == 0.75
    assert res["cost"][0] == pytest.approx(0.75 * w.c_live + w.c_div, rel=1e-15) and res["deaths"][0] == 2


def _n_at(kinds, f, c):
    t = f[:, 0]
    return int(np.sum((kinds[:, 0] == 1) & (t < c)) - np.sum((kinds[:, 0] == 2) & (t < c)))


def test_a_guard_trip_is_charged():
    w = spec.world(T=200.0, n_max=40)
    res = kernel(w, list(range(8)), program=BUSY)
    tripped = np.flatnonzero(res.status("guard_cells"))
    assert len(tripped) >= 4 and np.all(res["guard_charge"][~res.status("guard_cells")] == 0)
    for i in tripped:
        kinds, f = res.fates(i)
        te = res["t_end"][i]
        assert te == int(te) and _n_at(kinds, f, te) >= 40 and _n_at(kinds, f, te - 1) < 40
        assert res["guard_charge"][i] == w.c_live * w.n_max * (w.T - te)
        assert res["net"][i] == res["income"][i] - spec.column_cost(res.ledger[i], w) - res["guard_charge"][i]
        under = kernel(replace(w, T=te - 1), [i], program=BUSY)  # the same life stopped one unit earlier
        assert not under.status("guard_cells")[0] and under["n_end"][0] < 40
        assert res["F"][i] < under["F"][0] * (te - 1) / w.T  # nothing earned after the trip, and N_max charged
    assert np.array_equal(spec.fitness(res.ledger, w), res["F"])
    e = kernel(spec.world(T=200.0, e_max=2000), [5], program=BUSY)
    te = e["t_end"][0]
    assert e.status("guard_events")[0] and te == int(te) and e["events"][0] > 2000
    assert kernel(spec.world(T=te - 1, e_max=2000), [5], program=BUSY)["events"][0] <= 2000
    assert not mismatch(e, 0, reference(spec.world(T=200.0, e_max=2000), 5, program=BUSY))


def test_the_guard_charge_bounds_the_loss_but_does_not_dominate_a_costlier_body():
    # LIFE_ABI.md 10 and 15.28: after a trip the life pays c_live N_max per remaining unit, which caps its loss. A
    # body that loses more than that below the guard (seizing cells: about 0.038 per cell-unit, above c_live) does
    # better by tripping than by staying just below N_max, so "always worse than staying below" does not hold
    seize = spec.theta(b=2.0, tau_m=1, t_ref=0.5, emit0=1, emit1=1, kappa=1, p_div=0.5, phi=2)
    prog = spec.pack_program(seize, alone=seize)
    w = spec.world(T=200.0, n_max=64)
    seeds = list(range(4))
    trip = kernel(w, seeds, program=prog)
    held = kernel(replace(w, oracle_cap=60), seeds, program=prog)
    assert trip.status("guard_cells").all() and np.all(trip["t_end"] < 50)
    assert not (held.status("guard_cells") | held.status("guard_events")).any() and np.all(held["n_end"] == 60)
    assert np.all((held["cost"] - held["income"]) / held["live_time"] > 1.5 * w.c_live)
    assert np.all(trip["guard_charge"] == w.c_live * w.n_max * (w.T - trip["t_end"]))
    assert np.all(trip["F"] > held["F"])


def _partition_genome() -> np.ndarray:
    """Four saturated or neutral genes (W = A = 0, asym = sigma(0) = 1/2) and p_div = 1 (LIFE_ABI.md 7.4 step 8)."""
    raw = np.zeros(spec.GENOME_SIZE, dtype=np.float32)
    spec.genome_view(raw, "act")[:4] = 1.0
    spec.genome_view(raw, "s0")[:4] = [20.0, -20.0, 0.0, -20.0]  # g = 1 - 2e-9, 2e-9, 1/2, 2e-9: fixed points
    spec.genome_view(raw, "b")[:4] = [20.0, -20.0, 0.0, -20.0]
    spec.genome_view(raw, "Q")[:4] = [1.0, -1.0, 0.5, 1.0]
    spec.genome_view(raw, "a0")[spec.K["p_div"]] = 2.0
    return raw


def test_division_clips_the_genes_of_both_daughter_and_mother_to_the_unit_interval():
    # LIFE_ABI.md 15.29: daughter clip(g + asym Q, 0, 1), mother clip(g - asym Q, 0, 1); the design clips the mother only
    raw, w = _partition_genome(), spec.world(T=12.0)
    res = kernel(w, [3], genome=raw)
    assert not mismatch(res, 0, reference(w, 3, genome=raw))
    kinds, f = res.fates(0)
    zyg = spec.uid_initial(3, 0)
    first, second = [f[i, 2:6] for i in range(len(kinds)) if kinds[i, 0] == 1 and fate_uid(kinds[i, 2]) == zyg][:2]
    assert first[0] == 1.0 and first[1] == 0.0 and first[2] == 0.75  # clipped above, clipped below, exact partition
    assert first[3] == spec.sigmoid(-20.0) + 0.5
    assert 0.5 <= second[3] < 0.5 + 1e-8  # the mother kept 0, not 2e-9 - 1/2 (which would give the next daughter ~0.03)
    births = kinds[:, 0] == 1
    assert np.all((f[births, 2:6] >= 0.0) & (f[births, 2:6] <= 1.0)) and births.sum() > 8


def test_identity_clamp_freezes_g_through_divisions():
    # LIFE_ABI.md 15.31 (review fix): under identity_clamp a claim does not partition g, so every cell keeps its g
    raw = _partition_genome()
    free, clamp = spec.world(T=12.0), spec.world(T=12.0, flags=spec.flags("identity_clamp"))
    for w in (free, clamp):
        assert not mismatch(kernel(w, [3], genome=raw), 0, reference(w, 3, genome=raw))
    g_of = {}
    for w in (free, clamp):
        kinds, f = kernel(w, [3], genome=raw).fates(0)
        births = kinds[:, 0] == 1
        assert births.sum() > 8
        g_of[w.flags] = np.unique(f[births, 2:6], axis=0)
    assert len(g_of[0]) > 1 and len(g_of[clamp.flags]) == 1  # one g for every cell: the zygote's
    # a fork: claims made after t_f send the mother's g, earlier ones keep their partition; kernel == reference
    fork = spec.world(T=12.0, t_fork=4.0, fork_flags=spec.flags("identity_clamp"))
    res = kernel(fork, [3], genome=raw)
    assert not mismatch(res, 0, reference(fork, 3, genome=raw))
    kinds, f = res.fates(0)
    births = [i for i in range(len(kinds)) if kinds[i, 0] == 1 and f[i, 0] > 0]
    late = {fate_uid(kinds[i, 1]): i for i in births if f[i, 0] - fork.d_min >= fork.t_fork}  # claimed after t_f
    assert late and len(late) < len(births)
    by_mother = defaultdict(set)
    for i in late.values():
        mother = fate_uid(kinds[i, 2])
        by_mother[mother].add(tuple(f[i, 2:6]))
        if mother in late:  # a mother born of a post-fork claim passes on exactly the g she was born with
            assert np.array_equal(f[i, 2:6], f[late[mother], 2:6])
    assert all(len(v) == 1 for v in by_mother.values())  # a frozen mother sends the same g at every claim
    # R25-v1 with deaths: under a clamp from t = 0, every cell dies with the g it was born with
    r = hb.r25_genome(timer=1.125).astype(np.float32)
    spec.genome_view(r, "a0")[spec.K["p_die"]] = 0.25
    res = kernel(spec.world(T=160.0, flags=spec.flags("identity_clamp")), [1, 2], genome=r)
    deaths = 0
    for i in range(2):
        kinds, f = res.fates(i)
        born = {int(kinds[j, 1]): f[j, 2:] for j in range(len(kinds)) if kinds[j, 0] == 1}
        for j in np.nonzero(kinds[:, 0] == 2)[0]:
            deaths += 1
            assert np.array_equal(born[int(kinds[j, 1])], f[j, 2:])
    assert deaths > 5


def test_no_division_without_an_empty_slot_in_view():
    ring = [(1, 0), (1, -1), (0, -1), (-1, 0), (-1, 1), (0, 1)]
    prog = spec.pack_program(DIVIDER, alone=spec.theta(), rim=spec.theta())  # the centre divides once it has contacts
    w = spec.world(T=200.0)
    full = kernel(w, list(range(4)), program=prog, init=[(0, 0, -1)] + [(a, b, ROW["rim"]) for a, b in ring])
    assert np.all(full["claims"] == 0) and np.all(full["ticks"] > 400)
    hole = kernel(w, list(range(4)), program=prog, init=[(0, 0, -1)] + [(a, b, ROW["rim"]) for a, b in ring[1:]])
    for i in range(4):
        kinds, _ = hole.fates(i)
        first = kinds[kinds[:, 0] == 1][6]
        assert tuple(first[3:5]) == (1, 0) and fate_uid(first[2]) == spec.uid_initial(i, 0)


def _placement(chi: float, seeds):
    """M at (0,0) hears only from S at (-1,0), which secretes: the polarity vector points at S, and S's site is taken,
    so M's best empty slots are the mirror pair (0,-1) and (-1,1). Returns the side (+1 up, -1 down) of the first
    daughter in each life."""
    src = spec.theta(sec0=0.5)
    m = spec.theta(p_div=1.0, pol0=1.0, chi=chi)
    prog = spec.pack_program(m, alone=spec.theta(), juvenile=spec.theta(), rim=src, juv_ticks=3.0, timer_step=1.0,
                             k_grow=4.0, Dm0=0.05, km0=0.05)
    init = [(0, 0, -1), (-1, 0, ROW["rim"])]
    res = kernel(spec.world(T=40.0), seeds, program=prog, init=init)
    sides = []
    for i in range(len(seeds)):
        kinds, _ = res.fates(i)
        a, b = kinds[2, 3:5]
        assert (a, b) in ((0, -1), (-1, 1)) and res["births"][i] == 1
        sides.append(1 if b > 0 else -1)
    return np.array(sides)


def test_chi_zero_gives_mirror_symmetric_placement():
    seeds = list(range(48))
    flat = _placement(0.0, seeds)
    assert 12 <= np.sum(flat > 0) <= 36  # either mirror image, decided by the placement hash
    assert np.all(_placement(0.5, seeds) == -1) and np.all(_placement(-0.5, seeds) == 1)  # handedness from chi only
