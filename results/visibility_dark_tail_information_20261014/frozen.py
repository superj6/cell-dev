"""Load only the complete retained ABI-3 source package; never compile or simulate on import."""
from __future__ import annotations

import ctypes
import importlib
import os
import sys
from pathlib import Path

from common import SIZES, STUDY, read, sha, verify_pins

BUNDLE = STUDY / 'original'
_H = None


def modules_pinned():
    pins = read(STUDY / 'bundle.json')['file_pins']
    verify_pins(pins)
    for name, module in list(sys.modules.items()):
        if name == 'src' or name.startswith('src.'):
            path = getattr(module, '__file__', None)
            if path is None or not Path(path).resolve().is_relative_to(BUNDLE / 'src'):
                raise ValueError('unfrozen engine import: ' + name)
            key = str(Path(path).resolve().relative_to(STUDY))
            if pins.get(key) != sha(path):
                raise ValueError('unverified engine module: ' + name)
    if 'src' in sys.modules and list(sys.modules['src'].__path__) != [str(BUNDLE / 'src')]:
        raise ValueError('engine package search path escaped frozen bundle')


def load_harness():
    global _H
    modules_pinned()
    if _H is not None:
        return _H
    sys.path.insert(0, str(BUNDLE))
    sys.path.insert(0, str(BUNDLE / 'harness'))
    os.environ.setdefault('CELL_DEV_CACHE', str(STUDY / 'kernel-cache'))
    # Preload the frozen package before archived harness prepends the main repository.
    for name in ('src', 'src.life', 'src.life.spec', 'src.life.build', 'src.life.analysis', 'src.life.handbuilt'):
        importlib.import_module(name)
    modules_pinned()
    H = importlib.import_module('harness')
    if Path(H.__file__).resolve() != BUNDLE / 'harness/harness.py':
        raise ValueError('unexpected harness module')
    if H.KERNEL is not H.spec.V3 or H.build.KERNEL is not H.spec.V3 or list(H.spec.V3.SIZES.values()) != SIZES:
        raise ValueError('Python ABI-3 contract changed')
    # Import the retained definition-only helper for byte-identical C5 names/defaults/bounds.
    sys.path.insert(0,str(BUNDLE / 'controllers'))
    metadata = importlib.import_module('mcommon')
    if Path(metadata.__file__).resolve() != BUNDLE / 'controllers/mcommon.py':
        raise ValueError('unexpected controller metadata module')
    if metadata.C5 != 1102 or list(metadata.C5_NAMES) != read(STUDY / 'inputs/recovered_inputs.json')['parameter_names']:
        raise ValueError('retained controller metadata changed')
    # Disable every implicit library compilation path in this private module instance.
    def forbidden_load(*args, **kwargs):
        raise ValueError('archived implicit loader disabled; use checked_library')
    H.load = forbidden_load
    H.build.load = forbidden_load
    H.build.build = forbidden_load
    _H = H
    modules_pinned()
    return H


def checked_library(path, expected_sha, *, require_c5=True):
    H = load_harness()
    path = Path(path).resolve()
    if not path.is_file() or sha(path) != expected_sha:
        raise ValueError('missing or changed pinned library; no implicit build')
    lib = ctypes.CDLL(str(path))
    H.build._declare(lib)
    sizes = (ctypes.c_int32 * 10)()
    # Metadata calls precede every simulation/data-buffer call.
    version = lib.life_abi_version()
    lib.life_sizes(sizes)
    if version != 3 or list(sizes) != SIZES or list(sizes) != list(H.spec.V3.SIZES.values()):
        raise ValueError('library ABI/stride mismatch')
    if require_c5:
        lib.ctl_count.restype = ctypes.c_int32
        lib.ctl_count.argtypes = []
        lib.ctl_info.restype = ctypes.c_int32
        lib.ctl_info.argtypes = [ctypes.c_int32, ctypes.c_char_p, ctypes.c_int32]
        found = {}
        for index in range(lib.ctl_count()):
            buffer = ctypes.create_string_buffer(128)
            cid = int(lib.ctl_info(index, buffer, 128))
            if cid in found:
                raise ValueError('duplicate controller registration')
            found[cid] = buffer.value.decode()
        if found.get(1102) != 'C5 Bayes memory tracker':
            raise ValueError('retained C5 registration missing or renamed')
        P = ctypes.POINTER
        i32, i64, u64, f64 = ctypes.c_int32, ctypes.c_int64, ctypes.c_uint64, ctypes.c_double
        lib.ctl_life_run.restype = i32
        lib.ctl_life_run.argtypes = [i32,i32,P(i32),P(f64),i32,P(f64),P(i32),P(i32),P(i32),P(f64),P(u64),
            P(f64),P(u64),i64,P(f64),P(u64),P(i64),i64,P(i64),P(f64),P(i64),
            P(i32),P(f64),i32,P(f64),P(f64),P(i32),P(f64),i32,P(f64)]
    modules_pinned()
    return lib
