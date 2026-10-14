"""Independent OS lifecycle check: no simulation or study release."""
import hashlib
import importlib.util
import json
import os
from pathlib import Path
import resource
import subprocess
import sys
import time

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[1]
SOURCE = ROOT / 'outputs/autonomous_visibility_information_20261014/monitor.py'
specification = importlib.util.spec_from_file_location('reviewed_monitor', SOURCE)
monitor = importlib.util.module_from_spec(specification)
specification.loader.exec_module(monitor)
monitor.enable_subreaper()
identity = HERE / 'synthetic_descendant.json'
if identity.exists():
    raise ValueError('this OS check has already run; retain its evidence')
descendant = 'import time\ns=time.process_time()\nwhile time.process_time()-s<0.2: pass\ntime.sleep(30)\n'
leader = (
    'import subprocess,sys,json,os\n'
    'p=subprocess.Popen([sys.executable,"-c",sys.argv[2]])\n'
    'open(sys.argv[1],"w").write(json.dumps({"leader":os.getpid(),"child":p.pid}))\n'
)
before = resource.getrusage(resource.RUSAGE_CHILDREN)
process = subprocess.Popen([sys.executable, '-c', leader, str(identity), descendant],
                           start_new_session=True, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
try:
    assert process.wait(timeout=5) == 0
    ids = json.loads(identity.read_text())
    assert ids['leader'] == process.pid
    deadline = time.monotonic() + 5
    while monitor.active_cpu(process.pid) < 0.15 and time.monotonic() < deadline:
        time.sleep(.02)
    rows = monitor.proc_table()
    assert rows[ids['child']]['ppid'] == os.getpid(), 'orphan was not adopted'
    active = monitor.active_cpu(process.pid)
    assert active >= .15, 'live adopted child CPU was omitted'
    monitor.cleanup_group(process)
    assert not any(row['pgrp'] == process.pid for row in monitor.proc_table().values())
    after = resource.getrusage(resource.RUSAGE_CHILDREN)
    reaped = after.ru_utime + after.ru_stime - before.ru_utime - before.ru_stime
    assert reaped >= .15, 'reaped descendant CPU was omitted'
    report = dict(status='passed', scientific_lives=0, simulated_lives=0, compilation=False,
                  monitor_sha256=hashlib.sha256(SOURCE.read_bytes()).hexdigest(),
                  active_descendant_cpu_seconds=active, reaped_child_cpu_seconds=reaped,
                  identities=ids, all_owned_processes_exited=True)
    (HERE / 'root_process_cleanup_review.json').write_text(json.dumps(report, indent=2)+'\n')
    print(json.dumps(report))
finally:
    monitor.cleanup_group(process)
