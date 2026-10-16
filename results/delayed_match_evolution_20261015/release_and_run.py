"""Bind the first owned attempt to its public registration, then run the reviewed watchdog."""
import os
import subprocess
import sys
from pathlib import Path

sys.dont_write_bytecode=True
from common import ROOT, STUDY, checked_protocol, read, save, sha

if sys.argv[1:] != ['--run']:
    raise SystemExit('explicit --run required')
protocol=checked_protocol()
public=ROOT/'results/delayed_match_evolution_20261015'
review=read(STUDY/'reviews/actual_input_review.json')
assert review['status']=='passed' and review['protocol_sha256']==sha(STUDY/'protocol.json')
assert sha(public/'protocol.json')==sha(STUDY/'protocol.json')
assert sha(public/'reviews/actual_input_review.json')==sha(STUDY/'reviews/actual_input_review.json')
assert subprocess.check_output(['git','status','--porcelain'],cwd=ROOT)==b''
commit=subprocess.check_output(['git','rev-parse','HEAD'],cwd=ROOT,text=True).strip()
assert commit.startswith('382761c')
assert subprocess.check_output(['git','rev-parse','origin/master'],cwd=ROOT,text=True).strip()==commit
prior=ROOT/'outputs/delayed_match_information_20261015/prelaunch/budget.json'
proof=read(prior)
assert proof['status']=='complete' and proof['terminal_cleanup']['all_worker_identities_exited']
assert proof['terminal_cleanup']['all_owned_groups_exited'] and not proof['terminal_cleanup']['remaining_descendants']
available=next(int(line.split()[1])*1024 for line in Path('/proc/meminfo').read_text().splitlines()
               if line.startswith('MemAvailable:'))
assert available>=protocol['budget']['minimum_available_bytes']
save(STUDY/'release.json',dict(status='released',protocol_sha256=sha(STUDY/'protocol.json'),
    public_commit=commit,public_manifest_sha256=sha(public/'manifest.json'),
    actual_input_review_sha256=sha(STUDY/'reviews/actual_input_review.json'),
    prior_terminal_budget_sha256=sha(prior),pid_namespace=os.readlink('/proc/self/ns/pid'),
    available_memory_bytes=available,launch_source_sha256=sha(Path(__file__)),
    authority='Standing user authorization for bounded safe local experiments; budget reported before launch.'),exclusive=True)
import monitor
monitor.main()
