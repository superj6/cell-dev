"""Independent saved-ledger recount; no build, simulation, or study-analyzer import."""
import hashlib
import json
import resource
import sys
import time
from pathlib import Path

import numpy as np

ROOT = Path(__file__).resolve().parents[2]
STUDY = Path(__file__).resolve().parent
sys.path.insert(0, str(ROOT))
from src.life import spec  # noqa: E402


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def main():
    start = time.process_time()
    protocol = json.loads((STUDY / "protocol.json").read_text())
    summary = json.loads((STUDY / "summary.json").read_text())
    index = json.loads((STUDY / "row_index.json").read_text())
    budget = json.loads((STUDY / "budget.json").read_text())
    assert budget["status"] == "complete" and budget["terminal_cleanup"]["all_owned_groups_exited"]
    assert summary["valid"] and len(index) == len(protocol["schedule"]) == 390
    col = {name: i for i, name in enumerate(spec.V5.LEDGER)}
    groups, all_rows = {}, {}
    max_roundoff = 0.0
    for item in protocol["schedule"]:
        path = STUDY / item["path"]
        assert sha(path) == index[item["path"]]["sha256"]
        with np.load(path, allow_pickle=False) as a:
            assert a["seeds"].tolist() == [item["seed"]]
            row = a["ledger"][0].copy()
        assert row.shape == (70,) and np.isfinite(row).all()
        d = {name: float(row[i]) for name, i in col.items()}
        correct = wrong = 0
        for label in ("narrow", "broad"):
            counts = [d[x + "_" + label] for x in ("choice_opportunities", "choice_carry_in", "correct_choices",
                                      "wrong_choices", "choice_timeouts", "unfinished_choices")]
            assert all(v >= 0 and v == int(v) for v in counts)
            assert counts[0] + counts[1] == sum(counts[2:])
            correct += counts[2]
            wrong += counts[3]
        w = protocol["worlds"][str(item["T"])]["world"]
        income = 500 * correct
        costs = {"maintenance": w["c_live"] * d["live_time"], "spikes": w["c_spike"] * d["spikes"],
                 "motor": w["c_tw"] * d["kappa_sum"], "messages": w["c_msg"] * d["contact_events"],
                 "division_claims": w["c_div"] * d["claims"], "secretion": w["c_sec"] * d["sec_int"],
                 "misses": w["c_miss"] * d["misses"], "receptors": w["c_rec"] * d["rec_gain"],
                 "wrong_choices": 50 * wrong}
        assert income == d["income"]
        residual = abs(sum(costs.values()) - d["cost"])
        max_roundoff = max(max_roundoff, residual)
        assert residual < 1e-9 * max(1, abs(d["cost"]))
        assert abs(d["net"] - (income - d["cost"] - d["guard_charge"])) < 1e-9 * max(1, abs(d["net"]))
        assert abs(d["F"] * item["T"] - d["net"]) < 1e-9 * max(1, abs(d["net"]))
        key = (item["role"], item["T"], item["seed"])
        if item["fast"]:
            all_rows[key] = row
            groups.setdefault((item["role"], item["T"]), []).append((d, costs))
        else:
            assert row.tobytes() == all_rows[key].tobytes()
    findings = []
    for group in summary["groups"]:
        key = (group["role"], group["T"])
        data = groups[key]
        assert len(data) == group["n"] == 32
        for name, values in group["metrics"].items():
            if name == "physical_cost":
                actual = np.array([sum(c.values()) for _, c in data])
            else:
                actual = np.array([d[name] for d, _ in data])
            assert abs(float(actual.mean()) - values["mean"]) < 1e-9 * max(1, abs(values["mean"]))
        for name, values in group["costs"].items():
            assert abs(np.mean([c[name] for _, c in data]) - values["mean"]) < 1e-9
        classes = {}
        for label in ("narrow", "broad"):
            cc = group["class_choice"][label]
            for name in ("choice_opportunities", "choice_carry_in", "correct_choices", "wrong_choices",
                         "choice_timeouts", "unfinished_choices"):
                assert sum(d[name + "_" + label] for d, _ in data) == cc[name]
            classes[label] = {k: cc[k] for k in ("total_opportunities", "narrow_choice", "broad_choice",
                                                "no_completed_choice", "choice_coverage", "accuracy_among_choices")}
        f = np.array([d["F"] for d, _ in data])
        findings.append(dict(role=key[0], T=key[1], F_mean=float(f.mean()),
                             F_se=float(f.std(ddof=1) / np.sqrt(len(f))), classes=classes))
    out = dict(status="passed", simulation_calls=0, rows_checked=390, fast_full_pairs_checked=6,
               source_sha256=sha(Path(__file__)), protocol_sha256=sha(STUDY / "protocol.json"),
               summary_sha256=sha(STUDY / "summary.json"), row_index_sha256=sha(STUDY / "row_index.json"),
               max_native_cost_roundoff=max_roundoff, findings=findings,
               cpu_seconds=time.process_time()-start, max_rss_kib=resource.getrusage(0).ru_maxrss,
               limitation="Arithmetic and class-count recount only; not independent genetic replay or memory inference.")
    path = STUDY / "independent_audit.json"
    with path.open("x") as f:
        json.dump(out, f, indent=2, allow_nan=False)
        f.write("\n")
    print(json.dumps({k: out[k] for k in ("status", "rows_checked", "cpu_seconds")}))


if __name__ == "__main__":
    main()
