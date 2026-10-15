"""Read-only check that the completed AM monitor and every owned worker have exited."""
import datetime
import hashlib
import json
import os
from pathlib import Path

OUT = Path(__file__).resolve().parent
STUDY = OUT.parent
path = STUDY / 'budget.json'
budget = json.loads(path.read_text())
namespace = os.readlink('/proc/self/ns/pid')
if budget['status'] != 'complete' or budget['running'] or budget['queued'] or namespace != budget['pid_namespace']:
    raise ValueError('requires complete run in its original namespace')


def proc(pid):
    try:
        f = (Path('/proc') / str(pid) / 'stat').read_text().rsplit(')', 1)[1].split()
        return {'pid': int(pid), 'pgid': int(f[2]), 'start_ticks': int(f[19])}
    except (FileNotFoundError, ProcessLookupError):
        return None


alive = [now for row in budget['process_identities'] if (now := proc(row['pid']))
         and now['start_ticks'] == row['start_ticks']]
groups = set(budget['owned_process_groups'])
members = [row for p in Path('/proc').iterdir() if p.name.isdecimal()
           and (row := proc(p.name)) and row['pgid'] in groups]
receipt = {'status': 'cleared' if not alive and not members else 'blocked',
    'budget_sha256': hashlib.sha256(path.read_bytes()).hexdigest(), 'pid_namespace': namespace,
    'checked_utc': datetime.datetime.now(datetime.UTC).isoformat(),
    'identities_checked': len(budget['process_identities']), 'groups_checked': len(groups),
    'remaining_identities': alive, 'remaining_group_members': members}
target = OUT / 'host_clearance.json'
with target.open('x') as stream:
    json.dump(receipt, stream, indent=2)
    stream.write('\n')
print(json.dumps(receipt))
if alive or members:
    raise SystemExit(1)
