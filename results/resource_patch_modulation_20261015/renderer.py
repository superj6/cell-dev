"""Isolated sensory-amplitude adapter; no production writes and no work at import."""
from __future__ import annotations

import ctypes
import os
import subprocess
from contextlib import contextmanager

from common import STUDY, save, sha

AMPLITUDES = {'native': None, 'constant1': 1.0, 'constant055': 0.55}
NATIVE_RATE_LINES = '''    const double fraction = (double)c->patch_left[i] / (double)c->patch_capacity;
    const double amplitude = c->patch_landmark + (1.0 - c->patch_landmark) * fraction;'''
RENDERER_RATE_LINES = '''#ifdef RESOURCE_OBSERVATION_AMPLITUDE
    const double amplitude = RESOURCE_OBSERVATION_AMPLITUDE;
#else
    const double fraction = (double)c->patch_left[i] / (double)c->patch_capacity;
    const double amplitude = c->patch_landmark + (1.0 - c->patch_landmark) * fraction;
#endif'''


def isolated_source(native_source):
    """Replace exactly the amplitude subexpression; every other native byte is preserved."""
    if native_source.count(NATIVE_RATE_LINES) != 1 or 'RESOURCE_OBSERVATION_AMPLITUDE' in native_source:
        raise ValueError('native patch-rate source differs')
    result = native_source.replace(NATIVE_RATE_LINES, RENDERER_RATE_LINES)
    if result.replace(RENDERER_RATE_LINES, NATIVE_RATE_LINES) != native_source:
        raise ValueError('renderer edit escaped amplitude lines')
    return result


def compile_library(mode, fast):
    from src.life import build

    if mode not in AMPLITUDES:
        raise ValueError('undeclared renderer mode')
    folder = STUDY / 'build-cache'
    folder.mkdir(parents=True, exist_ok=True)
    diagnostics = STUDY / 'compiler_diagnostics'
    diagnostics.mkdir(parents=True, exist_ok=True)
    label = f'{mode}_{"fast" if fast else "full"}'
    output = folder / f'{mode}_{"fast" if fast else "full"}.so'
    if output.exists():
        raise ValueError('fresh attempt must not reuse local compiled library')
    flags = list(build.flags(fast))
    if AMPLITUDES[mode] is not None:
        flags += [f'-DRESOURCE_OBSERVATION_AMPLITUDE={AMPLITUDES[mode]!r}']
    command = ['gcc', *flags, '-o', str(output), str(STUDY / 'inputs/renderer.c'), '-lm']
    save(diagnostics / f'{label}.command.json', dict(command=command), exclusive=True)
    result = subprocess.run(command, capture_output=True, text=True,
                            env=dict(os.environ, TMPDIR=str(folder)))
    (diagnostics / f'{label}.stdout.txt').write_text(result.stdout)
    (diagnostics / f'{label}.stderr.txt').write_text(result.stderr)
    save(diagnostics / f'{label}.result.json', dict(returncode=result.returncode), exclusive=True)
    if result.returncode:
        raise RuntimeError(f'isolated renderer compiler failed: {result.returncode}')
    library = ctypes.CDLL(str(output))
    build._declare(library)
    sizes = (ctypes.c_int32 * 10)()
    library.life_sizes(sizes)
    if library.life_abi_version() != 6 or list(sizes) != list(build.KERNEL.SIZES.values()):
        raise ValueError('isolated library ABI differs')
    return library, dict(path=str(output.relative_to(STUDY)), sha256=sha(output), command=command)


def run_c(library, world, packed, seed, fast):
    """Use the unchanged packing adapter with one explicit isolated library, then restore it."""
    from src.life import build, spec

    original = build.load
    try:
        build.load = lambda fast=False: library
        return build.run(world, [seed], genomes=packed[None], abi=spec.V6, threads=1,
                         fast=fast, raster_cap=0, fate_cap=0)
    finally:
        build.load = original


def constant_rate(amplitude):
    """Independent Python renderer: only Gaussian locations/width and fixed amplitude are read."""
    if amplitude not in (1.0, 0.55):
        raise ValueError('only the two declared constants are permitted')

    def rate(accountant, px, py):
        from src.life import spec

        life = accountant.life
        total, signal = life.lam_bg, 0.0
        for slot in range(life.patch_count):
            patch = accountant.patches[slot]
            contribution = life.lam_s * (amplitude * spec.halo(px - patch.x, py - patch.y, life.sigma))
            total = total + contribution
            signal = signal + contribution
        return total, signal
    return rate


@contextmanager
def python_renderer(mode):
    from src.life import reference

    if mode not in ('constant1', 'constant055'):
        raise ValueError('Python engineering only uses declared constant renderers')
    original = reference._Accountant._patch_rate
    try:
        reference._Accountant._patch_rate = constant_rate(AMPLITUDES[mode])
        yield
    finally:
        reference._Accountant._patch_rate = original


def run_python(mode, world, packed, seed):
    from src.life import reference, spec

    lat, unit = spec.V6.lattice_tables(world.lattice)
    with python_renderer(mode):
        return reference.run_life(spec.V6.pack_world(world), lat, unit, genome_table=packed,
            seeds=(seed, 0, 0, 0), abi=spec.V6, raster_cap=0, fate_cap=0)
