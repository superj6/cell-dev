"""Count actual backend invocations, including child Python processes; change no simulation arguments."""
import atexit
import collections
import functools
import json
import os
import sys
from pathlib import Path

if os.environ.get('ABI6_COUNT_DIR'):
    from src.life import build, reference

    counts = collections.Counter()
    c_original, reference_original = build.run, reference._Life.run

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

    build.run, reference._Life.run = c_counted, reference_counted

    @atexit.register
    def persist_counts():
        dest = Path(os.environ['ABI6_COUNT_DIR']) / f'{os.getpid()}.json'
        dest.write_text(json.dumps(dict(pid=os.getpid(), argv=sys.argv, counts=dict(counts)), indent=2)+'\n')
