"""Exact 384 C-fast lives plus six predetermined C-full repeats; source-only by default."""
from __future__ import annotations

import argparse
import os
import platform
import sys
import time

from common import ROOT, STUDY, checked_release, parent_check, save, sha

sys.dont_write_bytecode = True
sys.path.insert(0, str(ROOT))


def run():
    parent_check()
    protocol = checked_release()
    import numpy as np

    from src.life import build, spec

    protocol_sha = sha(STUDY / 'protocol.json')
    packed = np.load(STUDY / 'inputs/packed_genomes.npy', allow_pickle=False)
    if packed.shape != (6, spec.V5.GENOME_SIZE) or packed.dtype != np.float64:
        raise ValueError('six frozen packed genomes required')
    libraries = {str(fast): build.build(fast=fast) for fast in (False, True)}
    save(STUDY / 'startup.json', {
        'builds': {key: {'path': str(path.relative_to(STUDY)), 'sha256': sha(path),
                         'flags': list(build.flags(key == 'True'))} for key, path in libraries.items()},
        'python': platform.python_version(), 'numpy': np.__version__, 'libc': platform.libc_ver(),
        'affinity': sorted(os.sched_getaffinity(0)), 'startup_lives': 0,
        'protocol_sha256': protocol_sha,
    }, exclusive=True)
    index, started, returned = {}, 0, 0
    for item in protocol['schedule']:
        parent_check()
        if checked_release() != protocol:
            raise ValueError('frozen protocol changed')
        world = spec.World(**protocol['worlds'][str(item['T'])]['world'])
        path = STUDY / item['path']
        path.parent.mkdir(parents=True, exist_ok=True)
        if path.exists():
            raise ValueError('refuse repeated life: ' + item['path'])
        started += 1
        save(STUDY / 'progress.json', dict(started_calls=started, returned_calls=returned,
            active=item, protocol_sha256=protocol_sha))
        start = time.process_time()
        result = build.run(world, [item['seed']], genomes=packed[item['role_index']:item['role_index'] + 1],
            abi=spec.V5, threads=1, fast=item['fast'], fate_cap=0 if item['fast'] else protocol['fate_cap'])
        cpu = time.process_time() - start
        returned += 1
        arrays = dict(ledger=result.ledger, hashes=result.hashes, seeds=np.array([item['seed']], dtype=np.uint64),
            physical_cost=spec.V5.column_cost(result.ledger, world), F=spec.V5.fitness(result.ledger, world),
            guard_charge=spec.V5.guard_charge(result.ledger, world), protocol_sha256=np.array(protocol_sha))
        if not item['fast']:
            fi, ff = result.fates(0)
            arrays.update(fate_i=fi, fate_f=ff, fate_n=result.fate_n)
        with path.open('xb') as stream:
            np.savez_compressed(stream, **arrays)
        index[item['path']] = dict(sha256=sha(path), cpu_seconds=cpu, **item)
        save(STUDY / 'row_index.json', index)
        save(STUDY / 'progress.json', dict(started_calls=started, returned_calls=returned,
            active=None, protocol_sha256=protocol_sha))
        if returned % 32 == 0 or not item['fast']:
            print(f'completed {returned}/390 lives', flush=True)
    if started != 390 or returned != 390:
        raise ValueError('fixed count differs')
    from analyze import analyze
    try:
        summary = analyze(require_complete=True)
    except Exception as error:
        save(STUDY / 'analysis_failure.json', dict(status='invalid', error=f'{type(error).__name__}: {error}',
            retained_calls=returned, protocol_sha256=protocol_sha), exclusive=True)
        save(STUDY / 'measurement_complete.json', dict(status='invalid', backend_calls=returned,
            scientific_lives=384, diagnostic_repeat_lives=6, startup_lives=0,
            protocol_sha256=protocol_sha, analysis_failure_sha256=sha(STUDY / 'analysis_failure.json')),
            exclusive=True)
        raise
    save(STUDY / 'measurement_complete.json', dict(status='complete' if summary['valid'] else 'invalid', scientific_lives=384,
        diagnostic_repeat_lives=6, startup_lives=0, backend_calls=390,
        protocol_sha256=protocol_sha, row_index_sha256=sha(STUDY / 'row_index.json'),
        summary_sha256=sha(STUDY / 'summary.json'),
        full_fast_ledgers_identical=summary['full_fast_ledgers_identical']), exclusive=True)
    if not summary['valid']:
        raise ValueError('retained diagnostic failed validation; no retry or replacement')


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--run-child', action='store_true')
    if parser.parse_args().run_child:
        run()
    else:
        print('prepared source only; zero builds, zero lives')
