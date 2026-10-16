"""Count actual backend invocations, including child Python processes; change no simulation arguments."""
import atexit
import collections
import functools
import json
import os
import sys
from pathlib import Path

if os.environ.get('ABI7_COUNT_DIR'):
    from src.life import build, reference

    counts = collections.Counter()
    c_original, reference_original, load_original = build.run, reference._Life.run, build.load

    @functools.wraps(load_original)
    def load_counted(fast=False):
        lib = load_original(fast)
        if not getattr(lib, '_abi7_counted', False):
            original = lib.life_run
            backend = 'C_fast' if fast else 'C_full'

            @functools.wraps(original)
            def native_counted(*args):
                counts[backend+'_native_calls'] += 1
                counts[backend+'_attempted_lives'] += int(args[0])
                result = original(*args)
                counts[backend+'_returned_lives' if result == 0 else backend+'_rejected_calls'] += (
                    int(args[0]) if result == 0 else 1)
                return result

            native_counted.argtypes, native_counted.restype = original.argtypes, original.restype
            lib.life_run = native_counted
            lib._abi7_counted = True
        return lib

    @functools.wraps(c_original)
    def c_counted(worlds, seeds, **kwargs):
        backend = 'C_fast' if kwargs.get('fast') else 'C_full'
        counts[backend+'_calls'] += 1
        counts[backend+'_lives'] += len(seeds)
        return c_original(worlds, seeds, **kwargs)

    @functools.wraps(reference_original)
    def reference_counted(self):
        counts['Python_lives'] += 1
        return reference_original(self)

    build.run, reference._Life.run, build.load = c_counted, reference_counted, load_counted

    @atexit.register
    def persist_counts():
        dest = Path(os.environ['ABI7_COUNT_DIR']) / f'{os.getpid()}.json'
        dest.write_text(json.dumps(dict(pid=os.getpid(), argv=sys.argv, counts=dict(counts)), indent=2)+'\n')
