"""Recheck the completed AI host process chain; read-only except its receipt."""
import datetime
import hashlib
import json
import os
from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]
OUT = Path(__file__).resolve().parent


def sha(p):
    return hashlib.sha256(p.read_bytes()).hexdigest()


def proc(pid):
    try:
        fields = (Path('/proc') / str(pid) / 'stat').read_text().rsplit(')', 1)[1].split()
        return {'pid': int(pid), 'start_ticks': int(fields[19]), 'pgid': int(fields[2])}
    except (FileNotFoundError, ProcessLookupError):
        return None


prior_path = ROOT / 'results/exploratory_reserve_replication_20261014/operations/resource_clearance.json'
budget_path = ROOT / 'results/exploratory_reserve_replication_20261014/operations/budget.json'
prior, budget = [json.loads(p.read_text()) for p in (prior_path, budget_path)]
namespace = os.readlink('/proc/self/ns/pid')
if namespace != 'pid:[4026531836]':
    raise ValueError('this receipt must recheck the original host PID namespace')
assert budget['status'] == 'complete' and not budget['running'] and not budget['queued']
identities = prior['processes'] + budget['process_identities']
groups = set(prior['process_groups'] + budget['owned_process_groups'])
alive = []
for identity in identities:
    now = proc(identity['pid'])
    if now and now['start_ticks'] == identity['start_ticks']:
        alive.append(now)
members, scanned = [], 0
for p in Path('/proc').iterdir():
    if p.name.isdigit():
        row = proc(p.name)
        scanned += 1
        if row and row['pgid'] in groups:
            members.append(row)
pins = dict(prior['budget_pins'])
pins[str(budget_path.relative_to(ROOT))] = sha(budget_path)
for name, expected in pins.items():
    if sha(ROOT / name) != expected:
        raise ValueError('terminal budget changed: ' + name)
receipt = {'status': 'cleared' if not alive and not members else 'blocked',
           'pid_namespace': namespace, 'checked_utc': datetime.datetime.now(datetime.UTC).isoformat(),
           'prior_chain_sha256': sha(prior_path), 'budget_pins': pins,
           'processes_checked': len(identities), 'groups_checked': len(groups), 'host_entries_checked': scanned,
           'remaining_identities': alive, 'remaining_group_members': members, 'simulation_calls': 0}
(OUT / 'host_resource_clearance.json').write_text(json.dumps(receipt, indent=2) + '\n')
print(json.dumps({k: v for k, v in receipt.items() if k != 'budget_pins'}))
if alive or members:
    raise SystemExit(1)
