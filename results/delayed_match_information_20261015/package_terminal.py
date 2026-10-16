"""Package completed saved evidence; no engine imports, builds, lives, or random draws."""
from pathlib import Path
import gzip
import hashlib
import io
import json
import resource
import tarfile
import time

import numpy as np

ROOT = Path(__file__).resolve().parent
RUN = ROOT / "prelaunch"
START_CPU = time.process_time()
START_WALL = time.monotonic()
resource.setrlimit(resource.RLIMIT_CPU, (120, 120))
resource.setrlimit(resource.RLIMIT_AS, (8 * 1024**3, 8 * 1024**3))


def read(path):
    return json.loads(path.read_text())


def digest(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def save(path, value):
    with path.open("x") as out:
        json.dump(value, out, indent=2, allow_nan=False)
        out.write("\n")


budget = read(RUN / "budget.json")
complete = read(RUN / "measurement_complete.json")
assert budget["status"] == complete["status"] == "complete"
assert complete["backend_calls"] == 6656
available = int(next(line.split()[1] for line in Path("/proc/meminfo").read_text().splitlines()
                     if line.startswith("MemAvailable:"))) * 1024
assert available >= 4 * 1024**3
pins = {name: digest(RUN / name) for name in
        ("row_index.json", "summary.json", "budget.json", "measurement_complete.json", "protocol.json")}
assert pins["row_index.json"] == complete["row_index_sha256"]
assert pins["summary.json"] == complete["summary_sha256"]
index = read(RUN / "row_index.json")
summary = read(RUN / "summary.json")
rows = sorted(index, key=lambda row: row["path"])
assert len(rows) == 6656 and all(row["status"] == "complete" for row in rows)
assert len({row["path"] for row in rows}) == len(rows)
assert {row["path"] for row in rows} == {str(p.relative_to(RUN)) for p in (RUN / "raw").glob("*.npz")}

# The summary preserves the frozen 70-column LEDGER order; no production imports are needed.
columns = list(summary["roles"]["I"]["ledger_means"])
assert len(columns) == 70
class_rows = {"narrow": [], "broad": []}
missing = 0
for row in rows:
    if row["stage"] != "confirmation" or row["role"] != "I":
        continue
    assert digest(RUN / row["path"]) == row["sha256"]
    with np.load(RUN / row["path"], allow_pickle=False) as data:
        ledger = data["ledger"][0]
        narrow = ledger[columns.index("choice_opportunities_narrow")]
        broad = ledger[columns.index("choice_opportunities_broad")]
        if narrow + broad != 1:
            missing += 1
            continue
        name = "narrow" if narrow == 1 else "broad"
        class_rows[name].append(float(data["diag"][0, 5]))
calibration = {"status": "complete", "role": "I", "missing_labels": missing,
               "label_source": "sole native opened opportunity, observer analysis only", "classes": {}}
for name, values in class_rows.items():
    logits = np.asarray(values)
    y = float(name == "narrow")
    probability = np.exp(-np.logaddexp(0.0, -logits))
    calibration["classes"][name] = {
        "n": len(values), "predicted_narrow": int((logits >= 0).sum()),
        "predicted_broad": int((logits < 0).sum()),
        "class_accuracy": float(((logits >= 0) == y).mean()),
        "brier": float(((probability - y)**2).mean()),
        "log_loss": float(np.logaddexp(0.0, -(2*y - 1)*logits).mean()),
    }
assert sum(c["n"] for c in calibration["classes"].values()) + missing == 512
save(ROOT / "terminal_calibration.json", calibration)

archive = ROOT / "raw.tar.gz"
total_bytes = 0
with archive.open("xb") as output:
    with gzip.GzipFile(filename="", mode="wb", compresslevel=6, fileobj=output, mtime=0) as compressed:
        with tarfile.open(fileobj=compressed, mode="w|", format=tarfile.USTAR_FORMAT) as tar:
            for row in rows:
                path = RUN / row["path"]
                payload = path.read_bytes()
                assert hashlib.sha256(payload).hexdigest() == row["sha256"]
                info = tarfile.TarInfo("prelaunch/" + row["path"])
                info.size = len(payload)
                info.mode = 0o644
                info.uid = info.gid = info.mtime = 0
                info.uname = info.gname = ""
                tar.addfile(info, io.BytesIO(payload))
                total_bytes += len(payload)

with tarfile.open(archive, "r:gz") as tar:
    members = tar.getmembers()
    assert len(members) == len(rows)
    for member, row in zip(members, rows):
        assert member.name == "prelaunch/" + row["path"] and member.isfile()
        assert (member.mode, member.uid, member.gid, member.mtime) == (0o644, 0, 0, 0)
        assert member.uname == member.gname == ""
        assert hashlib.sha256(tar.extractfile(member).read()).hexdigest() == row["sha256"]
for name, expected in pins.items():
    assert digest(RUN / name) == expected
receipt = {
    "status": "passed", "source_sha256": digest(Path(__file__)), "input_pins": pins,
    "new_simulator_calls": 0, "new_builds": 0, "new_random_draws": 0,
    "archive": archive.name, "archive_sha256": digest(archive), "members": len(rows),
    "member_bytes": total_bytes, "archive_bytes": archive.stat().st_size,
    "layout": "prelaunch/raw/<basename>.npz", "ordering": "lexicographic complete member name",
    "metadata": {"format": "USTAR", "mode": "0644", "uid": 0, "gid": 0,
                 "uname": "", "gname": "", "mtime": 0, "gzip_mtime": 0, "gzip_filename": ""},
    "original_files_preserved": True, "all_archived_member_sha256_verified": True,
    "calibration_sha256": digest(ROOT / "terminal_calibration.json"),
    "cpu_seconds": time.process_time() - START_CPU,
    "wall_seconds": time.monotonic() - START_WALL,
    "peak_rss_kib": resource.getrusage(resource.RUSAGE_SELF).ru_maxrss,
}
save(ROOT / "raw_archive_receipt.json", receipt)
print(json.dumps(receipt, indent=2))
