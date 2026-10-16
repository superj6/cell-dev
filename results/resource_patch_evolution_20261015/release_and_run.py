"""Repair a zero-call launcher omission, bind the namespace, and run the frozen watchdog once."""
import os
import subprocess
import sys
from pathlib import Path

sys.dont_write_bytecode = True
from common import ROOT, STUDY, checked_protocol, read, save, sha

if sys.argv[1:] != ['--run']:
    raise SystemExit('explicit --run required')

protocol = checked_protocol()
public = ROOT / 'results/resource_patch_evolution_20261015'
review = read(STUDY / 'reviews/actual_input_review.json')
assert review['status'] == 'passed' and review['protocol_sha256'] == sha(STUDY / 'protocol.json')
assert sha(public / 'protocol.json') == sha(STUDY / 'protocol.json')
assert sha(public / 'reviews/actual_input_review.json') == sha(STUDY / 'reviews/actual_input_review.json')
commit = subprocess.check_output(['git', 'rev-parse', 'HEAD'], cwd=ROOT, text=True).strip()
assert commit == '742f5e75ff9d8564457d662a624be6dae26b4306'
assert subprocess.check_output(['git', 'rev-parse', 'origin/master'], cwd=ROOT, text=True).strip() == commit
assert subprocess.check_output(['git', 'status', '--porcelain'], cwd=ROOT) == b''
runtime_names = ('attempt.json', 'budget.json', 'execution', 'runs', 'raw', 'endpoints.json', 'build-cache')
assert not any((STUDY / name).exists() for name in runtime_names)
original = read(STUDY / 'release.json')
assert original['status'] == 'released' and original['protocol_sha256'] == sha(STUDY / 'protocol.json')
assert 'pid_namespace' not in original
history = STUDY / 'prelaunch_launcher_history'
history.mkdir(exist_ok=False)
(history / 'release_before_namespace.json').write_bytes((STUDY / 'release.json').read_bytes())
save(history / 'preflight_failure.json', dict(
    status='stopped_before_execution', command='.venv/bin/python outputs/resource_patch_evolution_20261015/monitor.py --run',
    tool_exit_code=1, tool_wall_seconds=0.011339076,
    error="KeyError: 'pid_namespace' at monitor.py line 312 before runtime artifact checks/attempt creation",
    evidence='Tool response and absence of every runtime path independently checked before correction.',
    original_release_sha256=sha(history / 'release_before_namespace.json'),
    frozen_monitor_sha256=sha(STUDY / 'monitor.py'), protocol_sha256=sha(STUDY / 'protocol.json'),
    runtime_paths_absent=list(runtime_names), started_builds=0, started_lives=0,
    correction='Bind release pid_namespace in the same process that invokes the unchanged watchdog.'), exclusive=True)
available = next(int(line.split()[1]) * 1024 for line in Path('/proc/meminfo').read_text().splitlines()
                 if line.startswith('MemAvailable:'))
assert available >= protocol['budget']['minimum_available_bytes']
release = dict(original, pid_namespace=os.readlink('/proc/self/ns/pid'), available_memory_bytes=available,
               public_commit=commit, public_manifest_sha256=sha(public / 'manifest.json'),
               launch_source_sha256=sha(Path(__file__)),
               preflight_failure_sha256=sha(history / 'preflight_failure.json'))
save(STUDY / 'release.json', release)
import monitor
monitor.main()
