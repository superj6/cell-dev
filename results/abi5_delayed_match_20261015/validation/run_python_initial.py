import json, os, pathlib, resource, signal, subprocess, time
base = pathlib.Path('/home/jgon/project/ml/cell-dev/outputs/abi5_delayed_match_20261015')
val = base / 'validation'
cmd = ['/home/jgon/project/ml/cell-dev/.venv/bin/python', '-m', 'pytest', '-q', 'tests/test_abi5_delayed_match.py', 'tests/test_life_visibility_reference.py', 'tests/test_life_visibility_kernel.py', 'tests/test_life_abi4_legacy.py']
env = dict(os.environ, OMP_NUM_THREADS='1', OPENBLAS_NUM_THREADS='1', MKL_NUM_THREADS='1', NUMEXPR_NUM_THREADS='1', CELL_DEV_CACHE=str(val / 'cache'), TMPDIR=str(val))
def available():
    return int(next(l.split()[1] for l in pathlib.Path('/proc/meminfo').read_text().splitlines() if l.startswith('MemAvailable:'))) * 1024
def limits():
    resource.setrlimit(resource.RLIMIT_CPU, (600, 600))
    resource.setrlimit(resource.RLIMIT_AS, (8 * 1024**3, 8 * 1024**3))
def rss_tree(pid):
    total = 0
    try:
        status = pathlib.Path(f'/proc/{pid}/status').read_text().splitlines()
        total += int(next((l.split()[1] for l in status if l.startswith('VmRSS:')), '0')) * 1024
        children = pathlib.Path(f'/proc/{pid}/task/{pid}/children').read_text().split()
        total += sum(rss_tree(int(child)) for child in children)
    except (FileNotFoundError, ProcessLookupError):
        pass
    return total
start = time.monotonic()
meta = dict(command=cmd, cwd=str(base / 'worktree'), cpu_limit_s=600, as_limit_bytes=8*1024**3, rss_limit_bytes=4*1024**3, minimum_host_available_bytes=4*1024**3, host_available_start_bytes=available(), threads=1)
(val / 'python_initial.command.json').write_text(json.dumps(meta, indent=2)+'\n')
if meta['host_available_start_bytes'] < 4 * 1024**3:
    raise SystemExit('host memory floor failed')
peak, reason = 0, None
with (val / 'python_initial.log').open('w') as log:
    proc = subprocess.Popen(cmd, cwd=base/'worktree', env=env, stdout=log, stderr=subprocess.STDOUT, start_new_session=True, preexec_fn=limits)
    while proc.poll() is None:
        peak = max(peak, rss_tree(proc.pid))
        if peak > 4*1024**3 or available() < 4*1024**3 or time.monotonic()-start > 600:
            reason = 'resource budget exceeded'
            os.killpg(proc.pid, signal.SIGTERM)
            break
        time.sleep(0.25)
    rc = proc.wait()
meta.update(returncode=rc, elapsed_s=time.monotonic()-start, peak_tree_rss_bytes=peak, stop_reason=reason)
(val / 'python_initial.result.json').write_text(json.dumps(meta, indent=2)+'\n')
print(json.dumps(meta, indent=2))
print((val / 'python_initial.log').read_text())
raise SystemExit(rc)
