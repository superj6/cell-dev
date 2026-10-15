"""Metadata-only ABI4 world packing; no compilation or numerical golden calls."""
import json
import sys
from dataclasses import asdict, replace
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))
from src.life import build, spec  # noqa: E402

if build.KERNEL is not spec.V4:
    raise ValueError('integrated production ABI4 required')
original = spec.world('catch_speck_flash5_dim25_l4', T=1024)
world = replace(original, visibility_low=0.)
root = Path(__file__).resolve().parents[2]
from common import sha  # noqa: E402

modules = {}
for name, module in list(sys.modules.items()):
    if name == 'src' or name.startswith('src.'):
        path = Path(module.__file__).resolve()
        if not path.is_relative_to(root / 'src'):
            raise ValueError('production source escaped repository')
        modules[str(path.relative_to(root))] = sha(path)
if list(sys.modules['src'].__path__) != [str(root / 'src')]:
    raise ValueError('production package search path changed')
print(json.dumps({'world': asdict(world), 'original_world': asdict(original),
                  'preset': original.name, 'packed_world': spec.V4.pack_world(world).tolist(),
                  'sizes': list(spec.V4.SIZES.values()), 'module_pins': modules}, allow_nan=False))
