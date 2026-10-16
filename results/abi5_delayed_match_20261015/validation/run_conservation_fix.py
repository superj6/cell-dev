import json, os, pathlib, resource, signal, subprocess, time
base = pathlib.Path('/home/jgon/project/ml/cell-dev/outputs/abi5_delayed_match_20261015')
val = base / 'validation'
commands = [
    ('python_conservation_fix', ['/home/jgon/project/ml/cell-dev/.venv/bin/python', '-m', 'pytest', '-ra', '-p', 'backend_counter', 'tests/test_abi5_delayed_match.py', 'tests/test_abi5_kernel_boundaries.py', 'tests/test_abi5_readouts.py']),
    ('truth_conservation_fix', ['/home/jgon/project/ml/cell-dev/.venv/bin/python', '../validation/export_truth.py', '--out', '../validation/truth_conservation_fix']),
    ('js_conservation_fix', ['/usr/bin/node', '--single-threaded', '--single-threaded-gc', '--max-old-space-size=512', '--require', '../validation/count_js_calls.cjs', 'results/atlas/play/test_delayed_match.js', '--truth', '../validation/truth_conservation_fix/truth.json']),
    ('js_trial64_conservation_fix', ['/usr/bin/node', '--single-threaded', '--single-threaded-gc', '--max-old-space-size=512', '--require', '../validation/count_js_calls.cjs', 'results/atlas/play/test_delayed_match_trial64.js', '../validation/truth_conservation_fix/truth.json']),
    ('ruff_conservation_fix', ['/home/jgon/project/ml/cell-dev/.venv/bin/ruff', 'check', 'src', 'scripts', 'tests']),
]
env = dict(os.environ, OMP_NUM_THREADS='1', OMP_THREAD_LIMIT='1', OPENBLAS_NUM_THREADS='1', MKL_NUM_THREADS='1', NUMEXPR_NUM_THREADS='1', CELL_DEV_CACHE=str(val/'cache'), TMPDIR=str(val), PYTHONPATH=str(val), ABI5_COUNTER_OUTPUT=str(val/'python_conservation_fix.calls.json'))
def available():
    return int(next(l.split()[1] for l in pathlib.Path('/proc/meminfo').read_text().splitlines() if l.startswith('MemAvailable:'))) * 1024
def limits():
    os.sched_setaffinity(0, {min(os.sched_getaffinity(0))})
    resource.setrlimit(resource.RLIMIT_CPU, (600, 600))
    resource.setrlimit(resource.RLIMIT_AS, (8*1024**3, 8*1024**3))
def tree_usage(pid):
    rss = cpu = 0
    try:
        status = pathlib.Path(f'/proc/{pid}/status').read_text().splitlines()
        rss = int(next((l.split()[1] for l in status if l.startswith('VmRSS:')), '0')) * 1024
        stat = pathlib.Path(f'/proc/{pid}/stat').read_text().rsplit(')', 1)[1].split()
        cpu = sum(float(stat[i]) for i in (11,12,13,14)) / os.sysconf('SC_CLK_TCK')
        for child in pathlib.Path(f'/proc/{pid}/task/{pid}/children').read_text().split():
            crss, ccpu = tree_usage(int(child))
            rss += crss
            cpu += ccpu
    except (FileNotFoundError, ProcessLookupError):
        pass
    return rss, cpu
start = time.monotonic()
completed_cpu = 0
results = []
for name, cmd in commands:
    before = resource.getrusage(resource.RUSAGE_CHILDREN)
    started = time.monotonic()
    meta = dict(command=cmd, cwd=str(base/'worktree'), total_cpu_limit_s=600, as_limit_bytes=8*1024**3, tree_rss_limit_bytes=4*1024**3, minimum_host_available_bytes=4*1024**3, host_available_start_bytes=available(), threads=1, omp_thread_limit=1, count_scope='in-process build.run and reference._Life.run invocations; subprocess and raw C life_run calls are not instrumented')
    (val/f'{name}.command.json').write_text(json.dumps(meta, indent=2)+'\n')
    if meta['host_available_start_bytes'] < 4*1024**3:
        raise SystemExit('host memory floor failed')
    peak = peak_cpu = 0
    reason = None
    with (val/f'{name}.log').open('w') as log:
        child_env = dict(env, LIFE_JS_CALL_LOG=str(val/f'{name}.calls.json'))
        proc = subprocess.Popen(cmd, cwd=base/'worktree', env=child_env, stdout=log, stderr=subprocess.STDOUT, start_new_session=True, preexec_fn=limits)
        while proc.poll() is None:
            rss, cpu = tree_usage(proc.pid)
            peak, peak_cpu = max(peak, rss), max(peak_cpu, cpu)
            if rss > 4*1024**3 or available() < 4*1024**3 or completed_cpu+cpu > 600 or time.monotonic()-start > 600:
                reason = 'resource budget exceeded'
                os.killpg(proc.pid, signal.SIGTERM)
                break
            time.sleep(.25)
        rc = proc.wait()
    after = resource.getrusage(resource.RUSAGE_CHILDREN)
    cpu_used = (after.ru_utime+after.ru_stime)-(before.ru_utime+before.ru_stime)
    completed_cpu += cpu_used
    meta.update(returncode=rc, elapsed_s=time.monotonic()-started, cpu_s=cpu_used, cumulative_cpu_s=completed_cpu, peak_tree_rss_bytes=peak, peak_observed_tree_cpu_s=peak_cpu, stop_reason=reason)
    (val/f'{name}.result.json').write_text(json.dumps(meta, indent=2)+'\n')
    results.append(meta)
    print(json.dumps(meta), flush=True)
    print((val/f'{name}.log').read_text()[-24000:], flush=True)
    if reason or rc != 0:
        break
(val/'conservation_fix_batch.result.json').write_text(json.dumps(results, indent=2)+'\n')
raise SystemExit(0 if all(r['returncode']==0 for r in results) else 1)
