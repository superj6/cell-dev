"""148 declared new calls only; isolated renderer compilation occurs inside the owned released attempt."""
from __future__ import annotations

import argparse
import os
import platform
import sys
import time

from common import ROOT, STUDY, checked_release, parent_check, read, save, sha

sys.dont_write_bytecode = True
sys.path.insert(0, str(ROOT))


def run():
    parent_check()
    protocol = checked_release()
    import numpy as np
    from analyze import analyze, load_raw, validate_life
    from renderer import compile_library, run_c, run_python

    from src.life import spec

    packed = np.load(STUDY / 'inputs/packed_genomes.npy', allow_pickle=False)
    if packed.shape != (2, 875) or packed.dtype != np.float64:
        raise ValueError('two exact inherited packed genotypes required')
    libraries, library_pins = {}, {}
    for mode in ('native', 'constant1', 'constant055'):
        for fast in (False, True):
            libraries[mode, fast], library_pins[f'{mode}_{fast}'] = compile_library(mode, fast)
    save(STUDY / 'startup.json', dict(protocol_sha256=sha(STUDY / 'protocol.json'), startup_lives=0,
        libraries=library_pins, python=platform.python_version(), numpy=np.__version__, libc=platform.libc_ver(),
        affinity=sorted(os.sched_getaffinity(0))), exclusive=True)
    reuse = read(STUDY / 'inputs/reuse.json')
    index, parity, started, returned = {}, {}, 0, 0
    try:
        for item in protocol['schedule']:
            parent_check()
            if checked_release() != protocol or item['index'] != started:
                raise ValueError('frozen protocol/order changed')
            path = STUDY / item['path']
            path.parent.mkdir(parents=True, exist_ok=True)
            if path.exists():
                raise ValueError('no repeated or overwritten life')
            world = spec.World(**protocol['worlds'][item['world']]['world'])
            started += 1
            save(STUDY / 'progress.json', dict(started_calls=started, returned_calls=returned, active=item))
            t_cpu = time.process_time()
            if item['backend'] == 'Python':
                result = run_python(item['mode'], world, packed[item['row']], item['seed'])
            else:
                fast = item['backend'] == 'C_fast'
                result = run_c(libraries[item['mode'], fast], world, packed[item['row']], item['seed'], fast)
            elapsed = time.process_time() - t_cpu
            returned += 1
            ledger, hashes = np.atleast_2d(result.ledger), np.atleast_2d(result.hashes)
            # Preserve native values before any numerical, status or parity check.
            with path.open('xb') as stream:
                np.savez_compressed(stream, ledger=ledger, hashes=hashes,
                    seed=np.asarray([item['seed']], dtype=np.uint64),
                    protocol_sha256=np.array(sha(STUDY / 'protocol.json')))
            index[item['path']] = dict(item, sha256=sha(path), cpu_seconds=elapsed)
            save(STUDY / 'row_index.json', index)
            save(STUDY / 'progress.json', dict(started_calls=started, returned_calls=returned, active=None))
            ledger, hashes = load_raw(path, item['seed'], sha(STUDY / 'protocol.json'), item['backend'] == 'C_fast')
            validate_life(ledger, world)
            if item['group'] == 'native_equivalence':
                old_ledger, old_hashes = load_raw(STUDY / item['comparison'], item['seed'],
                    reuse['baseline_protocol_sha256'], item['backend'] == 'C_fast')
                if ledger.tobytes() != old_ledger.tobytes() or hashes.tobytes() != old_hashes.tobytes():
                    raise ValueError('native-hook equivalence failed; original rows retained')
            elif item['group'] == 'constant_parity':
                group = parity.setdefault(item['pair'], {})
                group[item['backend']] = (ledger.tobytes(), hashes.tobytes())
                if group['C_full'][0] != ledger.tobytes():
                    raise ValueError('constant-renderer ledger parity failed')
                if item['backend'] == 'Python' and group['C_full'][1] != hashes.tobytes():
                    raise ValueError('constant-renderer Python/C full hashes differ')
            if returned <= 20 or returned % 32 == 0:
                print(f'returned {returned}/148', flush=True)
        if started != returned or returned != 148:
            raise ValueError('fixed call count differs')
        summary = analyze()
        save(STUDY / 'measurement_complete.json', dict(status='complete', scientific_lives=128,
            engineering_lives=20, startup_lives=0, backend_calls=148, reused_native_scientific_lives=64,
            protocol_sha256=sha(STUDY / 'protocol.json'), row_index_sha256=sha(STUDY / 'row_index.json'),
            summary_sha256=sha(STUDY / 'summary.json'), per_life_sha256=sha(STUDY / 'per_life.csv'),
            engineering_checks_passed=summary['engineering_checks_passed']), exclusive=True)
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
