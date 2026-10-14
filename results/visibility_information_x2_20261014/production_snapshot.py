"""Read-only production packing in its own ABI-4 process; never imported into scratch workers."""
from dataclasses import asdict
import hashlib
import json
from pathlib import Path
import sys
sys.path.insert(0, str(Path(__file__).resolve().parents[2]))
from src.life import spec, build
if build.KERNEL is not spec.V4:
    raise ValueError('production must have integrated ABI 4')
result = {}
for key, preset in [('flash5_dim25', 'catch_speck_flash5_dim25_l4'), ('blink20', 'catch_speck_blink20_20_l4')]:
    world = spec.world(preset, T=1024)
    result[key] = {'preset': preset, 'world': asdict(world), 'packed_world': spec.V4.pack_world(world).tolist(),
                   'sizes': list(spec.V4.SIZES.values())}
root=Path(__file__).resolve().parents[2]
modules={}
for name,module in list(sys.modules.items()):
    if name=='src' or name.startswith('src.'):
        path=Path(module.__file__).resolve()
        if not path.is_relative_to(root/'src'):
            raise ValueError('production source escaped main frozen checkout: '+name)
        modules[str(path.relative_to(root))]=hashlib.sha256(path.read_bytes()).hexdigest()
if list(sys.modules['src'].__path__)!=[str(root/'src')]:
    raise ValueError('production source package path differs')
print(json.dumps({'worlds':result,'module_pins':modules},allow_nan=False))
