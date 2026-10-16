"""Pure source/rate checks: no engine build, life construction or random draws."""
from __future__ import annotations

import ast
import json
import sys
from pathlib import Path
from types import SimpleNamespace

STUDY = Path(__file__).resolve().parents[1]
sys.dont_write_bytecode = True
sys.path[:0] = [str(STUDY), str(STUDY.parents[1])]

from common import ROOT, read, save, sha  # noqa: E402
from prepare import BASE, RUNTIME  # noqa: E402
from renderer import (  # noqa: E402
    NATIVE_RATE_LINES,
    RENDERER_RATE_LINES,
    constant_rate,
    isolated_source,
    python_renderer,
)

from src.life import reference, spec  # noqa: E402


def main():
    checks = []
    for name in RUNTIME:
        if name.endswith('.py'):
            ast.parse((STUDY / name).read_text(), filename=name)
    checks.append('all runtime Python sources parse')
    native = (ROOT / 'src/life/kernel.c').read_text()
    edited = isolated_source(native)
    assert edited.replace(RENDERER_RATE_LINES, NATIVE_RATE_LINES) == native
    for invalid in (native + NATIVE_RATE_LINES, native.replace(NATIVE_RATE_LINES, ''), edited):
        try:
            isolated_source(invalid)
        except ValueError:
            pass
        else:
            raise AssertionError('changed or duplicate source must be rejected')
    checks.append('isolated source edit confines/reverses exactly and rejects ambiguous input')

    # There are deliberately no stock, capacity, landmark, period or outcome attributes.
    body = SimpleNamespace(life=SimpleNamespace(lam_bg=.05, lam_s=2., patch_count=2, sigma=.6),
                           patches=[SimpleNamespace(x=0., y=0.), SimpleNamespace(x=2., y=-1.)])
    for amplitude in (1., .55):
        rate, signal = constant_rate(amplitude)(body, 0., 0.)
        terms = [2. * (amplitude * spec.halo(0., 0., .6)),
                 2. * (amplitude * spec.halo(-2., 1., .6))]
        assert rate == (.05 + terms[0]) + terms[1]
        assert signal == terms[0] + terms[1]
        assert 0. <= signal <= 4.
    checks.append('both constant renderers require only geometry and rates, with native sum order/bound')
    original = reference._Accountant._patch_rate
    for mode in ('constant1', 'constant055'):
        try:
            with python_renderer(mode):
                assert reference._Accountant._patch_rate is not original
                reference._Accountant._patch_rate(body, 0., 0.)
                raise RuntimeError('intentional restoration check')
        except RuntimeError:
            pass
        assert reference._Accountant._patch_rate is original
    checks.append('Python override restores original method on both normal and exceptional exits')
    with python_renderer('constant1'):
        pass
    assert reference._Accountant._patch_rate is original
    baseline = read(BASE / 'protocol.json')
    assert sha(STUDY / 'baseline_accounting.py') == sha(BASE / 'analyze.py')
    for path, digest in baseline['production_pins'].items():
        assert sha(ROOT / path) == digest
    checks.append('accepted production and copied accounting source bytes unchanged')
    receipt = dict(status='passed', checks=checks, count=len(checks), scientific_calls=0,
        engineering_calls=0, builds=0, life_constructions=0, random_draws=0,
        source_pins={name: sha(STUDY / name) for name in RUNTIME}, checker_sha256=sha(__file__))
    save(STUDY / 'reviews/source_checks.json', receipt, exclusive=True)
    print(json.dumps(receipt))


if __name__ == '__main__':
    main()
