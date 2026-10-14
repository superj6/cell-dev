"""Fresh-process import-order diagnosis only; never loads a cell-dev kernel."""
import ctypes
import ctypes.util
import hashlib
import json
import os
from pathlib import Path
import sys
import types

ROOT=Path(__file__).resolve().parents[3]
X=ROOT/'outputs/autonomous_visibility_information_20261014'
sys.path.insert(0,str(X))
mode=sys.argv[1]
if mode=='candidate_system_first':
    ctypes.CDLL('/usr/lib/x86_64-linux-gnu/libgomp.so.1')
if mode=='candidate_frozen_first':
    import frozen
    frozen.load_harness()
if mode=='candidate_production_first':
    sys.path.insert(0,str(ROOT))
    from src.life import spec,build
    assert build.KERNEL is spec.V4
source=(X/'numerical.py').read_text()
if mode!='old_fresh':
    old='def identity():\n'
    assert source.count(old)==1
    source=source.replace(old,old+'    import torch  # Consistent OpenMP runtime initialization before library identity.\n')
module=types.ModuleType('numeric_probe')
exec(compile(source,str(X/'numerical.py'),'exec'),module.__dict__)
actual=module.identity()
expected=json.loads((X/'protocol.json').read_text())['numerical_identity']
differences={key:{'expected':expected.get(key),'actual':actual.get(key)} for key in set(actual)|set(expected)
             if expected.get(key)!=actual.get(key)}
print(json.dumps({'case':mode,'equal_expected':actual==expected,'differences':differences,
 'src_modules':[name for name in sys.modules if name=='src' or name.startswith('src.')],
 'torch_loaded':'torch' in sys.modules,'compiled_libraries':0,'simulation_calls':0,
 'candidate_source_sha256':hashlib.sha256(source.encode()).hexdigest()},indent=2))
