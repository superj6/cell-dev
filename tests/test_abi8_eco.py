"""ABI 8: modality slots and the eco world (docs/OPEN_WORLDS.md, LIFE_ABI.md 9.8), kernel against reference."""
import json
from dataclasses import replace
from pathlib import Path

import numpy as np
import pytest

from src.genome import LIFE_DIMS_ABI3, LifeLayout
from src.life import build, ecology, reference, spec

V3, V7, V8 = spec.V3, spec.V7, spec.V8
ROOT = Path(__file__).resolve().parents[1]


def _founder() -> np.ndarray:
    """An evolved ABI 3 genome (it grows a real body) as a raw ABI 8 row."""
    sel = json.loads((ROOT / "results/multitask_20261018/selected_genomes.json").read_text())
    g3 = LifeLayout(LIFE_DIMS_ABI3).from_dict(sel["D90_Z_s5"]["250"]["genome"]).detach().numpy()
    return V8.pad_genomes(g3.astype(np.float32).reshape(1, -1), V3)[0].astype(np.float32)


FOUNDER = _founder()


def _gated(seed: int = 0) -> np.ndarray:
    """The founder with gene-dependent gains on every new modality, so streams start and stop during a life."""
    g = FOUNDER.copy()
    rng = np.random.default_rng(seed)
    a0, _ = V8.GENOME_SLICES["a0"]
    A, _ = V8.GENOME_SLICES["A"]
    act = V8.genome_view(g, "act") > 0.5
    for m in range(1, spec.S_MAX):
        p = 22 + m
        g[a0 + p] = 0.4 * (1 if m % 2 else -1)
        row = rng.normal(0.0, 1.5, spec.G_MAX) * act
        g[A + p * spec.G_MAX:A + (p + 1) * spec.G_MAX] = row
    return g


def _both(w, genome, seeds, **kw):
    gt = V8.pack_genomes(genome[None], w.lattice)
    k = build.run(w, seeds, genomes=gt, abi=V8, **kw)
    refs = [reference.run(w, genome_table=gt[0], seed=s, abi=V8) for s in seeds]
    return k, refs


def _bits(x):
    return np.asarray(x, dtype=np.float64).view(np.uint64)


def test_layout_appends_slots_and_keeps_every_older_entry():
    assert (V8.GENOME_SIZE, V8.PROGRAM_SIZE, V8.WORLD_SIZE, V8.LEDGER_SIZE, V8.P, V8.NIN) == (1172, 174, 499, 212, 32,
                                                                                          34)
    assert V8.WORLD_KEYS[:V7.WORLD_SIZE] == V7.WORLD_KEYS and V8.LEDGER[:V7.LEDGER_SIZE] == V7.LEDGER
    assert V8.INPUTS[:V7.NIN] == V7.INPUTS and V8.KNOBS[:V7.P] == V7.KNOBS
    assert LifeLayout(LIFE_DIMS_ABI3).abi is V3
    assert build.load().life_abi_version() == 8


@pytest.mark.parametrize("preset", ["catch_speck_l4", "catch_contact_resources_l4"])
def test_older_lives_are_bitwise_unchanged_under_v8(preset):
    w = spec.world(preset, T=96)
    g3 = V8.genome_view(FOUNDER, "W")  # noqa: F841 (shape check of the view helper)
    raw3 = np.zeros(V3.GENOME_SIZE, np.float32)
    lay3 = LifeLayout(LIFE_DIMS_ABI3)
    sel = json.loads((ROOT / "results/multitask_20261018/selected_genomes.json").read_text())
    raw3[:] = lay3.from_dict(sel["AO_s7"]["250"]["genome"]).detach().numpy().reshape(-1)
    old = build.run(w, [3, 4], genomes=V7.pack_genomes(raw3[None], w.lattice), abi=V7)
    new = build.run(w, [3, 4], genomes=V8.pack_genomes(V8.pad_genomes(raw3[None], V3), w.lattice), abi=V8)
    assert np.array_equal(_bits(old.ledger), _bits(new.ledger[:, :V7.LEDGER_SIZE]))
    assert not np.any(new.ledger[:, V7.LEDGER_SIZE:])
    assert np.array_equal(old.hashes[:, 1:], new.hashes[:, 1:])
    assert np.array_equal(old.hashes[:, 0], build.unfold_close(new.hashes[:, 0], new.ledger, V7.LEDGER_SIZE))


@pytest.mark.parametrize("family", ecology.FAMILIES)
def test_kernel_matches_reference_on_every_family(family):
    w = ecology.realize(family, 11, T=56)
    k, refs = _both(w, _gated(3), [5, 6])
    for i, r in enumerate(refs):
        assert np.array_equal(_bits(r.ledger), _bits(k.ledger[i])), [
            (n, r.ledger[j], k.ledger[i][j]) for j, n in enumerate(V8.LEDGER) if r.ledger[j] != k.ledger[i][j]][:8]
        assert np.array_equal(r.hashes, k.hashes[i])
    assert k["status"].max() == 0
    assert sum(k[f"mod_cand_{m}"].sum() for m in range(1, 9)) > 0  # the gated streams ran


def test_padded_genomes_sense_nothing_new():
    w = ecology.realize("plume", 2, T=64)
    gt = V8.pack_genomes(FOUNDER[None], w.lattice)
    lv = build.run(w, [1, 2], genomes=gt, abi=V8)
    assert not any(lv[f"mod_cand_{m}"].any() for m in range(1, spec.S_MAX))
    assert lv["rec_cand"].sum() > 0 and lv["eco_puffs"].sum() > 0


def test_schedulers_threads_and_fast_build_agree():
    ws = [ecology.realize(f, 4, T=80) for f in ecology.FAMILIES]
    gt = V8.pack_genomes(_gated(1)[None], ws[0].lattice)
    seeds = list(range(5))
    heap = build.run(ws, seeds, genomes=gt, abi=V8, threads=1)
    par = build.run(ws, seeds, genomes=gt, abi=V8, threads=4)
    fast = build.run(ws, seeds, genomes=gt, abi=V8, threads=2, fast=True)
    win = build.run([replace(w, window_h=0.25) for w in ws], seeds, genomes=gt, abi=V8)
    assert np.array_equal(_bits(heap.ledger), _bits(par.ledger)) and np.array_equal(heap.hashes, par.hashes)
    assert np.array_equal(_bits(heap.ledger), _bits(fast.ledger))
    assert np.array_equal(heap.hashes, win.hashes)
    assert np.array_equal(_bits(heap.ledger), _bits(win.ledger))


def _eco(**changes):
    e = dict(eco_mode=1, eco_puff_sigma0=0.4, eco_puff_life=50.0, eco_puff_cut=16.0, eco_puff_cap=32, eco_vib_vref=0.2,
             eco_arena=10.0, eco_home_sigma=1.0, eco_plant_sigma=0.8, eco_soil_sigma=1.5)
    e.update(changes)
    return spec.eco_world("catch_speck_l4", mod=ecology.MOD_BLOCK, eco=spec.eco_block(**e), T=64, v_t=0.0,
                          tau_turn=0.0, t_resp=0.0)


def test_kill_ends_the_life_at_a_guard_time_without_a_guard_charge():
    pred = dict(eco_n_ag=1, ag0_type=1, ag0_x=0.0, ag0_y=0.0, ag0_v1=0.0, ag0_v2=0.3, ag0_r_sense=50.0, ag0_p=1.0,
                ag0_r_contact=50.0, ag0_value=700.0, ag0_look=1.0, ag0_t_state=100.0, ag0_t_rest=1.0, ag0_sigma=1.0,
                eco_kill_hits=2)
    w = _eco(**pred)
    k, refs = _both(w, _gated(2), [1, 2])
    for i, r in enumerate(refs):
        assert np.array_equal(_bits(r.ledger), _bits(k.ledger[i])) and np.array_equal(r.hashes, k.hashes[i])
    assert np.all(k.status("killed")) and np.all(k["eco_killed"] == 1) and np.all(k["t_end"] < w.T)
    assert np.all(k["guard_charge"] == 0) and np.all(k["eco_hits"] >= 1)
    assert np.allclose(spec.V8.fitness(k.ledger, w), k["F"], rtol=0, atol=1e-12)


def test_walls_keep_the_dot_outside_their_inflated_boxes(monkeypatch):
    walls = dict(eco_n_wall=4, wall0_x0=2.0, wall0_x1=2.5, wall0_y0=-6.0, wall0_y1=6.0, wall1_x0=-2.5, wall1_x1=-2.0,
                 wall1_y0=-6.0, wall1_y1=6.0, wall2_x0=-2.0, wall2_x1=2.0, wall2_y0=3.0, wall2_y1=3.5,
                 wall3_x0=-2.0, wall3_x1=2.0, wall3_y0=-3.5, wall3_y1=-3.0, eco_r_body=0.5)
    w = replace(_eco(**walls), T=200)
    seen = []
    orig = reference._Accountant.dot_adv

    def checked(self, t):
        orig(self, t)
        for x0, x1, y0, y1 in getattr(self, "walls", []):
            rb, tol = self.r_body, 1e-12  # a hit time rounds to within an ulp of the face; contact clamps it there
            inside = x0 - rb + tol < self.X < x1 + rb - tol and y0 - rb + tol < self.Y < y1 + rb - tol
            seen.append(inside)

    monkeypatch.setattr(reference._Accountant, "dot_adv", checked)
    gt = V8.pack_genomes(_gated(5)[None], w.lattice)
    res = [reference.run(w, genome_table=gt[0], seed=s, abi=V8) for s in (1, 2, 3)]
    assert seen and not any(seen)
    k = build.run(w, [1, 2, 3], genomes=gt, abi=V8)
    assert np.array_equal(_bits(np.stack([r.ledger for r in res])), _bits(k.ledger))
    assert k["eco_wall_contacts"].sum() > 0


@pytest.mark.parametrize("change", [
    dict(eco_mode=3), dict(eco_n_src=9), dict(eco_puff_cap=0), dict(eco_n_ag=1, ag0_type=7, ag0_look=1.0,
                                                                     ag0_sigma=1.0),
    dict(eco_n_wall=1, wall0_x0=1.0, wall0_x1=0.5, wall0_y0=0.0, wall0_y1=1.0), dict(src3_x=1.0),
    dict(eco_carry_cap=2, eco_carry_digest=0.0), dict(eco_plant_cap=17)])
def test_invalid_eco_blocks_are_refused(change):
    with pytest.raises(ValueError):
        V8.validate_world(_eco(**change))


def test_modalities_need_an_eco_life_and_older_abis_refuse_them():
    w = spec.eco_world("catch_speck_l4", mod=ecology.MOD_BLOCK)
    with pytest.raises(ValueError):
        V8.validate_world(w)
    with pytest.raises(NotImplementedError):
        V7.validate_world(ecology.realize("plume", 1))


def test_generator_is_deterministic_and_valid_across_families():
    for fam in (*ecology.FAMILIES, *(f"{f}_transfer" for f in ecology.FAMILIES)):
        a, b = ecology.realize(fam, 21), ecology.realize(fam, 21)
        assert a == b and ecology.realize(fam, 22) != a
        V8.validate_world(a)


def test_eco_tasks_draw_one_world_per_life_from_its_seed(tmp_path):
    from src.common import load_config
    from src.evolve import setup

    cfg = load_config(str(ROOT / "configs/open_worlds_pilot_LP.yaml"), [f"logging.output_dir={tmp_path}", "life.T=64"])
    _, layout, _, ev = setup(cfg)
    assert layout.abi is V8 and ev.training_task_names == ("plume", "predator", "home", "prey", "farm")
    draw = ev.draw_allocated("gen", 3, [2, 1, 1, 1, 3])
    again = ev.draw_allocated("gen", 3, [2, 1, 1, 1, 3])
    assert draw.worlds == again.worlds and draw.seeds == again.seeds
    assert all(isinstance(w, spec.EcoWorld) for w in draw.worlds) and len(set(draw.worlds)) == draw.n
    farm = [w for w, t in zip(draw.worlds, draw.tasks) if t == "farm"]
    assert farm == [ecology.realize("farm", s, **_common(w)) for s, w, t in zip(draw.seeds, draw.worlds, draw.tasks)
                    if t == "farm"]
    other = ev.draw_allocated("gen", 3, [1, 1, 1, 1, 3])  # one task's count moves no other task's lives
    assert [w for w, t in zip(other.worlds, other.tasks) if t == "farm"] == farm


def _common(w):
    """The evaluator's common settings in an eco world (everything except the drawn entities)."""
    return dict(T=w.T, lattice=w.lattice, flags=w.flags, t_open=w.t_open, t_fork=w.t_fork, fork_flags=w.fork_flags,
                d_min=w.d_min, d0=w.d0)


def _mode(w, m):
    e = list(w.eco)
    e[spec.ECO_INDEX["eco_mode"]] = float(m)
    return replace(w, eco=tuple(e))


def test_eco_mode_1_lives_replay_the_first_abi8_build():
    """Eco v2 is opt-in (eco_mode 2): mode 1 lives are bitwise those recorded before the v2 rules existed."""
    gold = json.loads((ROOT / "tests/data/abi8_eco_mode1_golden.json").read_text())
    worlds = [spec.EcoWorld(**{k: tuple(v) if isinstance(v, list) else v for k, v in d.items()})
              for d in gold["worlds"]]
    assert {spec.eco_view(w)["eco_mode"] for w in worlds} == {1.0}
    gt = V8.pack_genomes(_gated(gold["genome_seed"])[None], worlds[0].lattice)
    k = build.run(worlds, gold["seeds"], genomes=gt, abi=V8)
    assert np.array_equal(_bits(k.ledger), _bits(np.array(gold["ledger"])))
    assert np.array_equal(k.hashes, np.array(gold["hashes"], dtype=np.uint64))


PURSUER = dict(eco_n_ag=1, ag0_type=1, ag0_x=3.0, ag0_y=0.0, ag0_v1=0.0, ag0_v2=0.3, ag0_r_sense=50.0, ag0_p=1.0,
               ag0_r_contact=0.5, ag0_value=100.0, ag0_look=1.0, ag0_t_state=100.0, ag0_t_rest=1.0, ag0_sigma=1.0)


def test_v2_pursuers_do_not_see_a_still_body():
    still = np.zeros(V8.GENOME_SIZE, np.float32)  # a lone zygote that never moves
    seen = {}
    for m in (1, 2):
        k, refs = _both(_mode(_eco(**PURSUER), m), still, [1, 2])
        for i, r in enumerate(refs):
            assert np.array_equal(_bits(r.ledger), _bits(k.ledger[i])) and np.array_equal(r.hashes, k.hashes[i])
        seen[m] = k["eco_detections"]
    assert np.all(seen[1] > 10) and np.all(seen[2] == 0)


def test_v2_shelter_cover_is_felt_by_touch():
    w = _eco(eco_n_shelter=1, shelter0_x=0.0, shelter0_y=0.0, shelter0_r=3.0)
    acc = {}
    for m in (1, 2):
        k, refs = _both(_mode(w, m), _gated(4), [1, 2])
        for i, r in enumerate(refs):
            assert np.array_equal(_bits(r.ledger), _bits(k.ledger[i])) and np.array_equal(r.hashes, k.hashes[i])
        assert np.all(k["eco_shelter_samples"] > 0)
        acc[m] = k["mod_accept_6"] / k["mod_cand_6"]
    assert np.all(acc[2] > 0.5) and np.all(acc[1] < 0.05)


def test_v2_a_tap_on_a_growing_plant_destroys_it(monkeypatch):
    farm = dict(eco_n_fertile=1, fertile0_x=0.0, fertile0_y=0.0, fertile0_r=4.0, eco_plant_cap=8, eco_plant_cost=10.0,
                eco_ripen_min=40.0, eco_ripen_max=60.0, eco_ripe_window=50.0, eco_plant_value=300.0, eco_plant_b0=0.8)
    outcomes = []
    orig = reference._Accountant._fold_world

    def fold(self, words):
        if words[0] == 43:
            outcomes.append(words[2])
        return orig(self, words)

    monkeypatch.setattr(reference._Accountant, "_fold_world", fold)
    found = {}
    for m in (1, 2):
        outcomes.clear()
        w = replace(_mode(_eco(**farm), m), T=200)
        k, refs = _both(w, FOUNDER, [1, 2, 3])
        for i, r in enumerate(refs):
            assert np.array_equal(_bits(r.ledger), _bits(k.ledger[i])) and np.array_equal(r.hashes, k.hashes[i])
        found[m] = outcomes.count(8)
        assert outcomes.count(7) == k["eco_planted"].sum()
    assert found[1] == 0 and found[2] >= 1
