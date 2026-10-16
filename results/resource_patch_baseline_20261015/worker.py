"""One declared456-call attempt; inert unless launched by its released owned monitor."""
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
    from analyze import analyze, validate_life

    from src.life import build, spec

    packed = np.load(STUDY / 'inputs/packed_genomes.npy', allow_pickle=False)
    if packed.shape != (33, 875) or packed.dtype != np.float64:
        raise ValueError('33 exact frozen packed inputs required')
    libraries = {str(fast): build.build(fast=fast) for fast in (False, True)}
    save(STUDY / 'startup.json', dict(protocol_sha256=sha(STUDY / 'protocol.json'), startup_lives=0,
        libraries={key: dict(path=str(path.relative_to(STUDY)), sha256=sha(path),
                             flags=list(build.flags(key == 'True'))) for key, path in libraries.items()},
        python=platform.python_version(), numpy=np.__version__, libc=platform.libc_ver(),
        affinity=sorted(os.sched_getaffinity(0))), exclusive=True)
    index, pairs, started, returned = {}, {}, 0, 0
    try:
        for item in protocol['schedule']:
            parent_check()
            if checked_release() != protocol:
                raise ValueError('frozen protocol changed')
            if item['index'] != started:
                raise ValueError('schedule index differs')
            path = STUDY / item['path']
            path.parent.mkdir(parents=True, exist_ok=True)
            if path.exists():
                raise ValueError('no repeated or overwritten life')
            world = spec.World(**protocol['worlds'][item['world']]['world'])
            started += 1
            save(STUDY / 'progress.json', dict(started_calls=started, returned_calls=returned, active=item))
            t_cpu = time.process_time()
            result = build.run(world, [item['seed']], genomes=packed[item['row']:item['row'] + 1],
                               abi=spec.V6, threads=1, fast=item['fast'], raster_cap=0, fate_cap=0)
            cpu = time.process_time() - t_cpu
            returned += 1
            # Preserve the exact native return BEFORE any numerical/accounting interpretation.
            with path.open('xb') as stream:
                np.savez_compressed(stream, ledger=result.ledger, hashes=result.hashes,
                    seed=np.asarray([item['seed']], dtype=np.uint64),
                    protocol_sha256=np.array(sha(STUDY / 'protocol.json')))
            index[item['path']] = dict(item, sha256=sha(path), cpu_seconds=cpu)
            save(STUDY / 'row_index.json', index)
            save(STUDY / 'progress.json', dict(started_calls=started, returned_calls=returned, active=None))
            validate_life(result.ledger, world)
            if result.hashes.shape != (1, 5) or result.hashes.dtype != np.uint64:
                raise ValueError('native hash shape/dtype')
            if item['fast'] and not np.all(result.hashes == spec.HASH_INIT):
                raise ValueError('fast hashes must remain constant')
            if item['group'] == 'engineering':
                pair = pairs.setdefault(item['pair'], {})
                pair[item['fast']] = result.ledger.tobytes()
                if item['fast'] and pair[True] != pair[False]:
                    raise ValueError('full/fast engineering ledgers differ')
            if returned % 32 == 0 or returned <= 8:
                print(f'returned {returned}/456', flush=True)
        if started != returned or returned != 456:
            raise ValueError('fixed call count differs')
        summary = analyze()
        save(STUDY / 'measurement_complete.json', dict(status='complete', scientific_lives=448,
            engineering_lives=8, startup_lives=0, backend_calls=456,
            protocol_sha256=sha(STUDY / 'protocol.json'), row_index_sha256=sha(STUDY / 'row_index.json'),
            summary_sha256=sha(STUDY / 'summary.json'), per_life_sha256=sha(STUDY / 'per_life.csv'),
            full_fast_ledgers_identical=summary['full_fast_ledgers_identical']), exclusive=True)
    except Exception as error:
        save(STUDY / 'measurement_complete.json', dict(status='invalid', started_calls=started,
            returned_calls=returned, protocol_sha256=sha(STUDY / 'protocol.json'),
            error=f'{type(error).__name__}: {error}'), exclusive=True)
        raise


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--run-child', action='store_true')
    if parser.parse_args().run_child:
        run()
    else:
        print('source only; no builds, lives or draws')
