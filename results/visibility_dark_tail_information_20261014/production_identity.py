"""Exactly one owned, isolated production identity invocation; dry run by default."""
from __future__ import annotations

import argparse
import json
import sys
import time
from pathlib import Path

from common import ROOT, STUDY, parent_check, require_release, save, sha


def verify_modules(value):
    for name, module in list(sys.modules.items()):
        if name == 'src' or name.startswith('src.'):
            path = Path(module.__file__).resolve()
            if (not path.is_relative_to(ROOT / 'src')
                    or value['production_pins'].get(str(path.relative_to(ROOT))) != sha(path)):
                raise ValueError('unfrozen production identity definition: ' + name)
    if list(sys.modules['src'].__path__) != [str(ROOT / 'src')]:
        raise ValueError('production package search path changed')


def run(parent):
    parent_check(parent, nested=True, phase='validation')
    value = require_release()  # Torch first, then strict runtime equality, before src imports.
    output = STUDY / 'validation/startup_identity.json'
    if output.exists():
        raise ValueError('the standard identity pair may run only once')
    sys.path.insert(0, str(ROOT))
    from src.checkpoint import numerical_identity
    verify_modules(value)
    c0, w0 = time.process_time(), time.monotonic()
    identity = numerical_identity()  # Exactly two ABI3 seed-11 T200 compatibility lives.
    if identity != value['expected_numerical_identity']:
        raise ValueError('retained production numerical/source/golden identity changed')
    verify_modules(value)
    parent_check(parent, nested=True, phase='validation')
    save(output, {'status': 'complete', 'identity': identity,
                  'protocol_sha256': sha(STUDY / 'protocol.json'),
                  'preexpected_fields': sorted(identity), 'newly_captured_fields': [],
                  'numerical_identity_invocations': 1, 'simulation_calls': 2,
                  'abi': 3, 'seeds': [11, 11], 'T': 200,
                  'cpu_seconds': time.process_time() - c0,
                  'wall_seconds': time.monotonic() - w0})


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--run', action='store_true')
    parser.add_argument('--expected-parent', type=int)
    args = parser.parse_args()
    if args.run:
        run(args.expected_parent)
    else:
        print(json.dumps({'status': 'dry_run', 'simulation_calls': 0, 'compiled_libraries': 0,
                          'planned_identity_invocations': 1, 'planned_simulation_calls': 2}))
