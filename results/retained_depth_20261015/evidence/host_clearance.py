"""Recheck prior research processes in their original namespace; run no life."""
import datetime
import hashlib
import json
import os
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
OUT = Path(__file__).resolve().parent
SOURCE = OUT / 'new_prepare_prep/prior_resource_evidence.json'


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def proc(pid):
    try:
        f = (Path('/proc') / str(pid) / 'stat').read_text().rsplit(')', 1)[1].split()
        return {'pid': int(pid), 'start_ticks': int(f[19]), 'pgid': int(f[2])}
    except (FileNotFoundError, ProcessLookupError):
        return None


prior = json.loads(SOURCE.read_text())
namespace = os.readlink('/proc/self/ns/pid')
if namespace != prior['required_host_pid_namespace']:
    raise ValueError('prior resource identities must be checked in original host namespace')
for name, digest in prior['budget_pins'].items():
    if sha(ROOT / name) != digest:
        raise ValueError('prior budget changed: ' + name)
alive = [now for row in prior['processes'] if (now := proc(row['pid']))
         and now['start_ticks'] == row['start_ticks']]
groups = set(prior['process_groups'])
members = [row for p in Path('/proc').iterdir() if p.name.isdecimal()
           and (row := proc(p.name)) and row['pgid'] in groups]
available = next(int(line.split()[1]) * 1024 for line in Path('/proc/meminfo').read_text().splitlines()
                 if line.startswith('MemAvailable:'))
result = {'status': 'cleared' if not alive and not members else 'blocked', 'pid_namespace': namespace,
          'checked_utc': datetime.datetime.now(datetime.UTC).isoformat(), 'prior_evidence_sha256': sha(SOURCE),
          'processes_checked': len(prior['processes']), 'groups_checked': len(groups),
          'remaining_identities': alive, 'remaining_group_members': members,
          'available_memory_bytes': available, 'simulation_calls': 0}
(OUT / 'host_resource_clearance.json').open('x').write(json.dumps(result, indent=2) + '\n')
print(json.dumps(result))
if alive or members or available < 4 * 1024**3:
    raise SystemExit(1)
