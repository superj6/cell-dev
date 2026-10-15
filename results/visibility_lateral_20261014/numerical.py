"""Read-only numerical/library identity, with no kernel loading or simulation."""
from __future__ import annotations

import ctypes
import ctypes.util
import platform
import shutil
import sys
from pathlib import Path

import numpy as np

from common import sha


def identity():
    import torch  # noqa: F401 - Consistent OpenMP initialization before runtime identity.
    # Resolve the actual loaded runtime files, including libm; no numerical golden lives.
    for name in ('m','gomp'):
        target=ctypes.util.find_library(name)
        if target is None:
            raise ValueError('required runtime library missing: '+name)
        ctypes.CDLL(target)
    runtime={}
    for line in Path('/proc/self/maps').read_text().splitlines():
        fields=line.split()
        if len(fields)<6 or not fields[-1].startswith('/'):
            continue
        path=Path(fields[-1]).resolve()
        if any(path.name.startswith(prefix) for prefix in ('libm.so','libc.so','libgomp.so')):
            runtime[str(path)]=sha(path)
    if not all(any(Path(name).name.startswith(prefix) for name in runtime) for prefix in ('libm.so','libc.so','libgomp.so')):
        raise ValueError('required runtime maps incomplete')
    compiler=Path(shutil.which('gcc')).resolve()
    extension=Path(np._core._multiarray_umath.__file__).resolve()
    return {'python':platform.python_version(),'python_executable':str(Path(sys.executable).resolve()),
        'python_executable_sha256':sha(Path(sys.executable).resolve()),'numpy':np.__version__,
        'numpy_core':str(extension),'numpy_core_sha256':sha(extension),'machine':platform.machine(),
        'compiler':str(compiler),'compiler_sha256':sha(compiler),
        'compiler_flags':['-O3','-fopenmp','-ffp-contract=off','-fPIC','-shared','-std=c11'],
        'fast_extra_flags':['-DLIFE_FAST'],'runtime_libraries':runtime}


def check(expected):
    if identity()!=expected:
        raise ValueError('numerical/compiler/runtime identity changed')
