"""AH owned first-attempt native worker with an external selection adapter."""
from __future__ import annotations

import argparse
import json
import os
import sys
from pathlib import Path

os.environ.setdefault('ATEN_CPU_CAPABILITY', 'avx2')
sys.dont_write_bytecode = True
STUDY = Path(__file__).resolve().parent
ROOT = STUDY.parents[1]
sys.path.insert(0, str(ROOT))


def parent_check():
    from run_budgeted import process_identity, sha
    monitor = int(os.environ.get('CELLDEV_CONTINUATION_MONITOR_PID', '0'))
    if monitor <= 1 or os.getppid() != monitor:
        raise ValueError('search must be a child of its monitor')
    attempt = json.loads((STUDY / 'attempt.json').read_text())
    actual = process_identity(monitor)
    if (attempt['monitor']['pid'] != monitor or attempt['monitor']['start_ticks'] != actual['start_ticks']
            or attempt['ready_sha256'] != sha(STUDY / 'ready.json')):
        raise ValueError('monitor identity or release changed')
    budget = json.loads((STUDY / 'budget.json').read_text())
    if (budget.get('status') != 'running' or budget.get('phase') != 'search'
            or os.getpgrp() != os.getpid() or os.getsid(0) != os.getpid()
            or 'CELLDEV_THREADS_FILE' in os.environ):
        raise ValueError('search requires its active owned phase and fixed threads')


def one_identity(original, expected, configured, mode):
    from reserve_adapter import extended_identity
    calls = 0

    def capture():
        nonlocal calls
        if calls:
            raise ValueError('exactly one numerical identity invocation per search worker')
        calls += 1
        value = original()
        if value != expected:
            raise ValueError('native numerical identity differs from complete AE')
        return extended_identity(value, configured, mode)

    return capture


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--run-id', choices=('control', 'reserve'), required=True)
    args = parser.parse_args()
    from run_budgeted import check_protocol, check_ready
    protocol, ready = check_protocol(), check_ready()
    parent_check()
    from omegaconf import OmegaConf
    from reserve_adapter import installed, selection_identity

    import src.evolve as native
    from src import checkpoint, run
    cfg = OmegaConf.load(STUDY / protocol['configs'][args.run_id]['path'])
    configured = OmegaConf.to_container(cfg.exploratory_reserve, resolve=True)
    if configured != selection_identity(args.run_id) or cfg.seed != protocol['paired_native_seed']:
        raise ValueError('configured external selection or paired seed differs')
    if Path(cfg.logging.output_dir) != STUDY / 'runs' / args.run_id or Path(cfg.logging.output_dir).exists():
        raise ValueError('first attempt refuses previous search output')
    original = checkpoint.numerical_identity
    checkpoint.numerical_identity = one_identity(original, protocol['expected_numerical_identity'], configured, args.run_id)
    try:
        with installed(native, int(cfg.seed), args.run_id):
            run.main(cfg)
    finally:
        checkpoint.numerical_identity = original
    if check_protocol() != protocol or check_ready() != ready:
        raise ValueError('source or release changed during search')


if __name__ == '__main__':
    main()
