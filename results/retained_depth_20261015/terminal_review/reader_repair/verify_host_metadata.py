"""Read-only host-process identity check; records no scientific outcomes."""
import datetime
import hashlib
import json
import os
from pathlib import Path

OUT = Path(__file__).resolve().parent
STUDY = OUT.parents[1] / "autonomous_retained_depth_20261015"
budget_path = STUDY / "budget.json"
digest = hashlib.sha256(budget_path.read_bytes()).hexdigest()
assert digest == "4d45d119c72f926bdd20e16d2456df15817042cb018446698bfe392f06fbbe0a"
budget = json.loads(budget_path.read_text())
namespace = os.readlink("/proc/self/ns/pid")
assert namespace == budget["pid_namespace"] == "pid:[4026531836]"


def proc(pid):
    try:
        fields = (Path("/proc") / str(pid) / "stat").read_text().rsplit(")", 1)[1].split()
        return {"pid": int(pid), "ppid": int(fields[1]), "pgid": int(fields[2]), "start_ticks": int(fields[19])}
    except (FileNotFoundError, ProcessLookupError):
        return None


alive = [now for row in budget["process_identities"] if (now := proc(row["pid"]))
         and now["start_ticks"] == row["start_ticks"]]
groups = set(budget["owned_process_groups"])
members = [row for item in Path("/proc").iterdir() if item.name.isdecimal()
           and (row := proc(item.name)) and row["pgid"] in groups]
receipt = {"status": "cleared" if not alive and not members else "blocked", "pid_namespace": namespace,
           "budget_sha256": digest, "checked_utc": datetime.datetime.now(datetime.UTC).isoformat(),
           "identities_checked": len(budget["process_identities"]), "groups_checked": len(groups),
           "remaining_identities": alive, "remaining_group_members": members,
           "source_sha256": hashlib.sha256(Path(__file__).read_bytes()).hexdigest(),
           "scientific_outcomes_read": False}
with (OUT / "independent_host_clearance.json").open("x") as f:
    json.dump(receipt, f, indent=2)
    f.write("\n")
print(json.dumps(receipt))
assert not alive and not members
