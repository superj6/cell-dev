"""Independent saved-array arithmetic and paired moments; no simulator/worker imports."""
# ruff: noqa: E402
import hashlib
import json
import math
import sys
from pathlib import Path

import numpy as np

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE.parent / "flash_ladder_20261017/checkout"))
from src.life import spec


def read(path):
    return json.loads(Path(path).read_bytes())


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def save(path, obj):
    path.write_text(json.dumps(obj, indent=2, allow_nan=False) + "\n")


def moment(values):
    values = [float(x) for x in values]
    mean = math.fsum(values) / len(values)
    return dict(mean=mean, se=math.sqrt(math.fsum((x - mean)**2 for x in values) / 511 / 512), n=512)


def check_tree(a, b):
    assert a.keys() == b.keys()
    for key, value in a.items():
        if isinstance(value, dict):
            check_tree(value, b[key])
        else:
            assert math.isclose(value, b[key], abs_tol=1e-11, rel_tol=1e-11), (key, value, b[key])


def recount(ledger, w, charge):
    assert ledger.shape == (512, 143) and np.isfinite(ledger).all()
    c = {name: ledger[:, index] for name, index in spec.V7.L.items()}
    assert np.all(c["status"] == 0), "unexpected nonzero status retained"
    for name in ("captures", "low_light_captures", "misses", "clicks", "n_end"):
        assert np.all(c[name] >= 0) and np.all(c[name] == np.floor(c[name]))
    assert np.array_equal(c["clicks"], c["captures"] + c["misses"])
    assert np.all(c["low_light_captures"] <= c["captures"])
    assert np.all(ledger[:, 58:] == 0) and np.all(c["b2_clicks"] == 0)
    cost = np.zeros(512)
    for price, amount in (("c_live", "live_time"), ("c_spike", "spikes"), ("c_tw", "kappa_sum"),
                          ("c_msg", "contact_events"), ("c_div", "claims"), ("c_sec", "sec_int"),
                          ("c_miss", "misses"), ("c_rec", "rec_gain")):
        cost += w[price] * c[amount]
    np.testing.assert_allclose(cost, c["cost"], rtol=1e-9, atol=1e-9)
    np.testing.assert_array_equal(c["income"], w["R_cap"] * c["captures"])
    np.testing.assert_array_equal(c["guard_charge"], 0)
    np.testing.assert_allclose(c["net"], c["income"] - c["cost"], rtol=1e-12, atol=1e-12)
    window = w["T"] - w["t_open"]
    np.testing.assert_allclose(c["F"], c["net"] / window, rtol=1e-12, atol=1e-12)
    # Every saved status is zero, so the enabled production extinction surcharge is exactly zero.
    assert charge is True
    keys = ("captures", "low_light_captures", "misses", "F", "income", "cost", "n_end", "clicks")
    return {k: c[k] for k in keys} | dict(mean_cells=c["live_time"] / window,
                                         extinct_charge=np.zeros(512), guard=np.zeros(512), extinct=np.zeros(512))


def main():
    protocol, manifest, monitor = (read(HERE / n) for n in ("protocol.json", "manifest.json", "queue/monitor.json"))
    for path, expected in (manifest["files"] | manifest["source_pins"]).items():
        assert sha(path) == expected, path
    assert monitor["status"] == "complete" and monitor["stop_reason"] is None and len(monitor["jobs"]) == 4
    assert not list((HERE / "runs").rglob("*.pending.json"))
    for job in monitor["jobs"]:
        assert job["status"] == "complete" and len(job["attempts"]) == 1
        attempt = job["attempts"][0]
        assert attempt["exit_code"] == 0 and attempt["cleanup_complete"] and not attempt["remaining_owned"]
    results, raw, calls = {}, {}, 0
    for name, case in protocol["cases"].items():
        observations = {}
        worker = read(HERE / "runs" / name / "summary.json")
        assert worker["status"] == "complete" and worker["protocol_sha256"] == sha(HERE / "protocol.json")
        assert worker["native_lives_this_invocation"] == worker["distinct_signal_off_lives"] == 1024
        calls += worker["native_lives_this_invocation"]
        for stage, row in case["stages"].items():
            off_path = HERE / "runs" / name / f"signal_off_g{int(stage):03d}.npz"
            assert sha(off_path) == worker["raw"][off_path.name]
            for condition, path in (("normal", Path(row["raw"])), ("off", off_path)):
                with np.load(path, allow_pickle=False) as data:
                    ledger, hashes, meta = data["ledger"], data["hashes"], json.loads(str(data["metadata"]))
                indices = row["rows"] if condition == "normal" else list(range(512))
                assert [meta["seeds"][i] for i in indices] == row["seeds"]
                assert [meta["tasks"][i] for i in indices] == ["flash00"] * 512
                assert meta["genomes"] == row["role"]["genome_sha256"]
                world = row["world"] | ({"lam_s": 0.0} if condition == "off" else {})
                assert meta["worlds"]["flash00"] == world
                assert hashes.shape[1] == 5 and np.all(hashes == spec.HASH_INIT)
                observations[f"g{stage}_{condition}"] = recount(
                    ledger[indices], world, case["config"]["life"]["extinct_charge"])
                raw[str(path)] = dict(sha256=sha(path), rows=indices, counted_lives=512, reused=condition == "normal")
        pairs = dict(cue_g0=("g0_normal", "g0_off"), cue_g120=("g120_normal", "g120_off"),
                     normal_gain=("g120_normal", "g0_normal"), off_gain=("g120_off", "g0_off"))
        diff = {label: {k: observations[a][k] - observations[b][k] for k in observations[a]}
                for label, (a, b) in pairs.items()}
        diff["cue_gain_interaction"] = {k: diff["cue_g120"][k] - diff["cue_g0"][k] for k in diff["cue_g0"]}
        expected = {label: {name: {k: moment(v) for k, v in row.items()} for name, row in group.items()}
                    for label, group in (("absolute", observations), ("paired", diff))}
        check_tree(expected["absolute"], worker["absolute"])
        check_tree(expected["paired"], worker["paired"])
        results[name] = expected
    assert calls == protocol["new_lives"] == 4096 and sum(r["counted_lives"] for r in raw.values()) == 8192
    resources = {k: monitor[k] for k in ("cpu_seconds", "wall_seconds", "peak_rss_bytes")}
    save(HERE / "summary.json", dict(status="complete", protocol_sha256=sha(HERE / "protocol.json"),
         new_lives=calls, reused_lives=4096, results=results, resources=resources, caveat=protocol["caveat"]))
    save(HERE / "raw_pins.json", raw)
    save(HERE / "audit.json", dict(status="passed", source_sha256=sha(Path(__file__)),
         protocol_sha256=sha(HERE / "protocol.json"), summary_sha256=sha(HERE / "summary.json"),
         raw_pins_sha256=sha(HERE / "raw_pins.json"), monitor_sha256=sha(HERE / "queue/monitor.json"),
         verified_lives=8192, verified_raw_files=16, all_status_zero=True, new_simulator_calls=0,
         note="Independent scalar moments and native accounting; no worker/analyzer import; fast hashes are constant."))


if __name__ == "__main__":
    main()
