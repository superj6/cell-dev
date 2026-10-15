"""AL: change only gen-life world allocation; native seeds, F and selection stay intact."""
from __future__ import annotations

import copy
import hashlib
from contextlib import contextmanager
from dataclasses import asdict, replace
from pathlib import Path

STUDY = Path(__file__).resolve().parent
ARMS = ('persistent_control', 'balanced_mixture')
RULE = 'gen indices even=pool odd=persistent; control and diagnostics=persistent'


def selection_identity(arm, worlds):
    if arm not in ARMS or set(worlds) != {'pool', 'persistent'}:
        raise ValueError('exact AL arm and two named selection worlds required')
    return {'version': 1, 'arm': arm, 'worlds': copy.deepcopy(worlds), 'rule': RULE,
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
        spec.V3.validate_world(world)
        if world.T != 1024:
            raise ValueError('AL selection duration must be 1024')
    original = evaluator_class.draw

    def draw(self, purpose, index, lives=None, T=None, overrides=None, envelope=None):
        if OmegaConf.to_container(self.cfg.retention_selection, resolve=True) != configured:
            raise ValueError('evaluator selection configuration differs')
        if purpose != 'gen':
            return original(self, purpose, index, lives=lives, T=T, overrides=overrides, envelope=envelope)
        count = self.lives if lives is None else int(lives)
        if (self.abi.version != 3 or count not in (4, 8) or int(index) != index or index not in range(4)
                or (T is not None and T != 1024) or overrides is not None or envelope not in (None, False)
                or self.T_choices or self.has_envelope or self.envelope.get('enabled', False)
                or asdict(self.world()) != configured['worlds']['persistent']):
            raise ValueError('AL requires exact fixed 4+4 ABI3 persistent base without overrides or envelope')
        result = original(self, purpose, index, lives=lives, T=T, overrides=overrides, envelope=envelope)
        if result.n != count or len(result.worlds) != count:
            raise ValueError('native draw length differs')
        if configured['arm'] == 'persistent_control':
            return result
        return replace(result, worlds=tuple(worlds['pool' if i % 2 == 0 else 'persistent'] for i in range(count)))

    evaluator_class.draw = draw
    try:
        yield
    finally:
        evaluator_class.draw = original
