"""One saved-data recovery of the renamed CSV metadata; no builds or lives."""
from __future__ import annotations

import os
import resource
import signal
import sys
import time
from pathlib import Path

sys.dont_write_bytecode = True
from common import STUDY, checked_protocol, read, save, sha  # noqa: E402


def main():
    started, cpu_start = time.monotonic(), time.process_time()
    for name in ('terminal_recovery.json', 'summary.json', 'per_life.csv'):
        if (STUDY / name).exists():
            raise ValueError('fresh saved-data recovery only: ' + name)
    os.sched_setaffinity(0, {min(os.sched_getaffinity(0))})
    for key in ('OMP_NUM_THREADS', 'OMP_THREAD_LIMIT', 'MKL_NUM_THREADS', 'OPENBLAS_NUM_THREADS',
                'NUMEXPR_NUM_THREADS', 'VECLIB_MAXIMUM_THREADS'):
        os.environ[key] = '1'
    resource.setrlimit(resource.RLIMIT_CPU, (30, 30))
    resource.setrlimit(resource.RLIMIT_AS, (8*1024**3, 8*1024**3))

    def bounded(signum=None, frame=None):
        available = next(int(x.split()[1])*1024 for x in Path('/proc/meminfo').read_text().splitlines()
                         if x.startswith('MemAvailable:'))
        if (time.monotonic() - started >= 60 or available < 4*1024**3 or
                resource.getrusage(resource.RUSAGE_SELF).ru_maxrss*1024 >= 2*1024**3):
            raise RuntimeError('saved-data recovery resource cap reached')

    bounded()
    signal.signal(signal.SIGALRM, bounded)
    signal.setitimer(signal.ITIMER_REAL, .25, .25)
    protocol = checked_protocol()
    original, budget = read(STUDY / 'measurement_complete.json'), read(STUDY / 'budget.json')
    amendment = read(STUDY / 'terminal_recovery/amendment.json')
    review = read(STUDY / 'terminal_recovery/source_review.json')
    if (original['status'] != 'invalid' or original['started_calls'] != 148 or original['returned_calls'] != 148 or
            original['error'] != "TypeError: dict() got multiple values for keyword argument 'path'" or
            budget['status'] != 'incomplete' or budget['reason'] != 'worker_failed' or
            not budget['terminal_cleanup']['all_owned_groups_exited'] or
            budget['terminal_cleanup']['remaining_descendants']):
        raise ValueError('expected preserved post-return failure and cleared execution required')
    for name, digest in amendment['original_evidence'].items():
        if sha(STUDY / name) != digest or sha(STUDY / 'terminal_recovery/original' / name) != digest:
            raise ValueError('original evidence changed: ' + name)
    if (review['status'] != 'passed' or review['terminal_source_sha256'] != sha(STUDY / 'analyze_terminal.py') or
            amendment['terminal_source_sha256'] != sha(STUDY / 'analyze_terminal.py')):
        raise ValueError('review must bind this exact saved-data analyzer')
    from analyze_terminal import analyze
    summary = analyze()
    bounded()
    signal.setitimer(signal.ITIMER_REAL, 0)
    receipt = dict(status='complete_saved_data_recovery', protocol_sha256=sha(STUDY / 'protocol.json'),
        original_measurement_sha256=sha(STUDY / 'measurement_complete.json'),
        original_budget_sha256=sha(STUDY / 'budget.json'), row_index_sha256=sha(STUDY / 'row_index.json'),
        analyzer_sha256=sha(STUDY / 'analyze_terminal.py'), wrapper_sha256=sha(__file__),
        amendment_sha256=sha(STUDY / 'terminal_recovery/amendment.json'),
        review_sha256=sha(STUDY / 'terminal_recovery/source_review.json'),
        summary_sha256=sha(STUDY / 'summary.json'), per_life_sha256=sha(STUDY / 'per_life.csv'),
        new_backend_calls=0, new_builds=0, new_random_draws=0, original_returned_calls=148,
        original_scientific_calls=128, original_engineering_calls=20, reused_native_scientific_rows=64,
        reused_native_engineering_rows=8, combined_csv_rows=212,
        engineering_checks_passed=summary['engineering_checks_passed'],
        resources=dict(cpu_seconds=time.process_time()-cpu_start, wall_seconds=time.monotonic()-started,
            peak_rss_bytes=resource.getrusage(resource.RUSAGE_SELF).ru_maxrss*1024,
            cap_cpu_seconds=30, cap_wall_seconds=60, cap_rss_bytes=2*1024**3,
            address_space_bytes=8*1024**3, minimum_available_bytes=4*1024**3, threads=1),
        production_pins_unchanged=checked_protocol() == protocol)
    save(STUDY / 'terminal_recovery.json', receipt, exclusive=True)
    print('Saved-data recovery complete; no additional lives, builds or draws.')


if __name__ == '__main__':
    main()
