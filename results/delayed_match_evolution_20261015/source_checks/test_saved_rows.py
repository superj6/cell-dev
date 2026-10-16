"""No new lives: test the reader against retained native bytes and deterministic synthetic rows."""
from pathlib import Path
import copy
import json
import resource
import sys

import numpy as np

HERE = Path(__file__).resolve().parent
STUDY = HERE.parent
ROOT = STUDY.parents[1]
resource.setrlimit(resource.RLIMIT_CPU, (30, 30))
resource.setrlimit(resource.RLIMIT_AS, (2 * 1024**3, 2 * 1024**3))
sys.path.insert(0, str(STUDY))
import analyze as a  # noqa: E402


def load(path):
    with np.load(path, allow_pickle=False) as data:
        return {key: data[key].copy() for key in data.files}


def save(path, value):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, indent=2, allow_nan=False)+"\n")


def rejects(function, label):
    try:
        function()
    except ValueError:
        return
    raise AssertionError("expected rejection: "+label)


baseline = ROOT / "outputs/delayed_match_baseline_20261015"
baseline_protocol = a.read(baseline/"protocol.json")
saved = {}
for duration in (85, 1024):
    definition = baseline_protocol["worlds"][str(duration)]
    definition = dict(definition, ledger_columns=list(a.LEDGER))
    native = load(baseline/f"raw/fast/T{duration}/AM_reference/52430000.npz")
    row = dict(ledger=native["ledger"], hashes=native["hashes"], seeds=np.asarray([52430000], dtype=np.uint64),
               cpu_seconds=np.asarray(0.), wall_seconds=np.asarray(0.))
    metrics, health = a.reconstruct(row, definition, [52430000])
    assert health["all_fitness_rows_retained"] == 1
    saved[f"match{duration}"] = (row, definition)

old = ROOT / "results/retained_depth_20261015"
old_protocol = a.read(old/"protocol.json")
for world in ("pool", "persistent", "blink80_20"):
    row = load(old/f"raw/{world}/row_00.npz")
    ledger = np.zeros((512, 70), dtype=np.float64)
    ledger[:, :row["ledger"].shape[1]] = row["ledger"]
    row["ledger"] = ledger
    definition = copy.deepcopy(old_protocol["worlds"][world])
    definition.update(abi=5, ledger_columns=list(a.LEDGER))
    definition["world"].update(task_mode=0)
    metrics, health = a.reconstruct(row, definition, old_protocol["seeds"])
    assert a.identical(metrics["F"], row["production_F"])
    assert health["all_fitness_rows_retained"] == 512
    saved[world] = (row, definition)

base_world = saved["match85"][1]["world"]
for status in (0, 1, 2):
    ledger = np.zeros((2, 70), dtype=np.float64)
    end = 85. if status != 2 else 10.
    live = 85. if status == 0 else 10.
    for key, value in dict(live_time=live, live_S=live, n_end=int(status != 1), n_S_end=int(status != 1),
                           n_peak=1, deaths=int(status == 1), t_end=end, t_ext=10. if status == 1 else -1.,
                           status=status).items():
        ledger[:, a.L[key]] = value
    cost = base_world["c_live"]*live
    guard = base_world["c_live"]*base_world["n_max"]*(85.-end) if status == 2 else 0.
    for key, value in dict(cost=cost, guard_charge=guard, net=-cost-guard, F=(-cost-guard)/85.).items():
        ledger[:, a.L[key]] = value
    row = dict(ledger=ledger, hashes=np.full((2, 5), 0x243F6A8885A308D3, dtype=np.uint64),
               seeds=np.asarray([1, 2], dtype=np.uint64), cpu_seconds=np.asarray(0.), wall_seconds=np.asarray(0.))
    metrics, health = a.reconstruct(row, saved["match85"][1], [1, 2])
    assert health["extinct"] == 2*int(status == 1) and health["guarded"] == 2*int(status == 2)
    if status == 1:
        np.testing.assert_allclose(metrics["F"], -.02, atol=1e-15)
    if status == 0:
        bad = copy.deepcopy(row)
        bad["ledger"][0, a.L["wrong_choices_narrow"]] = 1
        rejects(lambda: a.reconstruct(bad, saved["match85"][1], [1, 2]), "class conservation")
        bad = copy.deepcopy(row)
        bad["ledger"][0, a.L["status"]] = 64
        rejects(lambda: a.reconstruct(bad, saved["match85"][1], [1, 2]), "ledger status")

ratio, influence = a.ratio_with_influence(np.asarray([1., 1., 0., 0.]), np.asarray([1., 1., 1., 0.]))
assert ratio["estimate"] == 2/3 and abs(influence.mean()) < 1e-15
assert a.paired_ratio(ratio, ratio, influence, influence)["se"] == 0
assert a.paired_ratio(None, ratio, None, influence) is None

# This whole fixture is explicitly synthetic reader coverage, not scientific outcome evidence.
fixture = HERE/"synthetic_reader_fixture"
fixture.mkdir(exist_ok=False)
seeds = list(range(512))
worlds = {}
for name in a.WORLDS:
    source = name if name in saved else "match85"
    worlds[name] = saved[source][1]
protocol = dict(roles=list(a.ROLES), worlds=worlds, seeds=seeds, extinct_charge=True)
save(fixture/"protocol.json", protocol)
endpoints = {"genomes": [{"raw_sha256": "synthetic-"+role} for role in a.ROLES]}
save(fixture/"endpoints.json", endpoints)
index = {}
for world in a.WORLDS:
    original = saved[world if world in saved else "match85"][0]
    for i, role in enumerate(a.ROLES):
        take = np.arange(512) % len(original["ledger"])
        row = dict(ledger=original["ledger"][take], hashes=original["hashes"][take],
                   seeds=np.asarray(seeds, dtype=np.uint64), cpu_seconds=np.asarray(0.), wall_seconds=np.asarray(0.),
                   world_name=np.asarray(world), role=np.asarray(role),
                   protocol_sha256=np.asarray(a.sha(fixture/"protocol.json")),
                   endpoints_sha256=np.asarray(a.sha(fixture/"endpoints.json")),
                   genome_raw_sha256=np.asarray(endpoints["genomes"][i]["raw_sha256"]))
        relative = f"raw/{world}/row_{i:02d}.npz"
        path = fixture/relative
        path.parent.mkdir(parents=True, exist_ok=True)
        np.savez_compressed(path, **row)
        metrics, _ = a.reconstruct(row, worlds[world], seeds)
        scored_relative = f"scored/{world}/row_{i:02d}.npz"
        scored = fixture/scored_relative
        scored.parent.mkdir(parents=True, exist_ok=True)
        np.savez_compressed(scored, raw_sha256=np.asarray(a.sha(path)), production_F=metrics["F"],
                            native_F=metrics["native_F"], extinct_charge=metrics["extinct_charge"])
        index[relative] = dict(status="validated", lives=512, sha256=a.sha(path),
                               scored_path=scored_relative, scored_sha256=a.sha(scored))
save(fixture/"row_index.json", index)
save(fixture/"measurement_complete.json", dict(status="complete", research_lives=14336, startup_lives=4,
     rows=28, protocol_sha256=a.sha(fixture/"protocol.json"), row_index_sha256=a.sha(fixture/"row_index.json"),
     endpoints_sha256=a.sha(fixture/"endpoints.json")))
report = a.analyze(fixture)
assert report["status"] == "complete"
assert set(report["absolute"]) == set(a.WORLDS)
for world in a.WORLDS:
    assert report["paired"][world]["mixed24_minus_AO_start"]["F"]["mean"] == 0
    assert report["paired"][world]["mixed24_minus_mixed8"]["F"]["se"] == 0
json.dumps(report, allow_nan=False)
assert not any(name == "src" or name.startswith("src.") for name in sys.modules)
print(json.dumps(dict(status="passed", saved_matching_rows=2, saved_legacy_lives_checked=1536,
                      synthetic_early_endings=3, synthetic_reader_rows=28,
                      new_simulator_calls=0, new_builds=0, new_random_draws=0)))
