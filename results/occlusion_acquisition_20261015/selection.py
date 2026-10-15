"""AN fixed acquisition mixture; only draw-world allocation changes ordinary evolution."""
from __future__ import annotations

import copy
import hashlib
from contextlib import contextmanager
from dataclasses import asdict, replace
from pathlib import Path

STUDY = Path(__file__).resolve().parent
ARMS = ('acquisition',)
PATTERN = ('pool', 'persistent', 'blink80_20', 'blink80_20') * 2
RULE = 'gen fixed 2pool/2persistent/4blink80_20 per8 repeated for recheck; diagnostics=persistent neutral; R_cap500'


def selection_identity(arm, worlds):
    if (arm not in ARMS or set(worlds) != {'pool', 'persistent', 'blink80_20'}
            or any(w['R_cap'] != 500 or w['T'] != 1024 for w in worlds.values())):
        raise ValueError('exact AN acquisition arm and three 500-price worlds required')
    neutral = {'visibility_mode': 0, 'visibility_on': 0., 'visibility_off': 0., 'visibility_low': 1.}
    if any(any(worlds[name][key] != value for key, value in neutral.items())
           for name in ('pool', 'persistent')):
        raise ValueError('old selection contexts must have neutral visibility')
    if worlds['blink80_20'] != {**worlds['persistent'], 'visibility_mode': 2,
                               'visibility_on': 80., 'visibility_off': 20., 'visibility_low': 0.}:
        raise ValueError('acquisition context may change only the four declared visibility fields')
    return {'version': 1, 'arm': arm, 'worlds': copy.deepcopy(worlds), 'rule': RULE,
            'pattern': list(PATTERN),
            'source_pins': {'selection.py': hashlib.sha256((STUDY / 'selection.py').read_bytes()).hexdigest()}}


def extended_identity(base, configured):
    result = copy.deepcopy(base)
    if 'retention_selection' in result:
        raise ValueError('base identity already contains retention selection')
    result['retention_selection'] = copy.deepcopy(configured)
    return result


@contextmanager
def installed(evaluator_class, configured):
    """Patch only draw(), restoring the original even when the run fails."""
    from omegaconf import OmegaConf

    from src.life import spec

    if configured != selection_identity(configured['arm'], configured['worlds']):
        raise ValueError('selection source/configuration identity differs')
    worlds = {name: spec.World(**values) for name, values in configured['worlds'].items()}
    for world in worlds.values():
        spec.V4.validate_world(world)
        if world.T != 1024:
            raise ValueError('AN selection duration must be 1024')
    original = evaluator_class.draw

    def draw(self, purpose, index, lives=None, T=None, overrides=None, envelope=None):
        if OmegaConf.to_container(self.cfg.retention_selection, resolve=True) != configured:
            raise ValueError('evaluator selection configuration differs')
        if purpose != 'gen':
            return original(self, purpose, index, lives=lives, T=T, overrides=overrides, envelope=envelope)
        count = self.lives if lives is None else int(lives)
        if (self.abi.version != 4 or count not in (8, 16) or int(index) != index or index not in range(8)
                or (T is not None and T != 1024) or overrides is not None or envelope not in (None, False)
                or self.T_choices or self.has_envelope or self.envelope.get('enabled', False)
                or asdict(self.world()) != configured['worlds']['persistent']):
            raise ValueError('AN requires exact fixed 8+8 ABI4 persistent500 base without overrides or envelope')
        result = original(self, purpose, index, lives=lives, T=T, overrides=overrides, envelope=envelope)
        if result.n != count or len(result.worlds) != count:
            raise ValueError('native draw length differs')
        return replace(result, worlds=tuple(worlds[PATTERN[i % 8]] for i in range(count)))

    evaluator_class.draw = draw
    try:
        yield
    finally:
        evaluator_class.draw = original
