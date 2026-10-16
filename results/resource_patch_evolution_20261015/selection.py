"""Fixed mixed ABI6 resource-patch selection; only generation draw-world allocation changes."""
from __future__ import annotations

import copy
import hashlib
from contextlib import contextmanager
from dataclasses import asdict, replace
from pathlib import Path

STUDY = Path(__file__).resolve().parent
ARMS = ('mixed',)
PATTERNS = {'mixed': ('patch', 'pool', 'patch', 'persistent') * 2}
RULE = ('gen fixed patch4/pool2/persistent2 per8 repeated for recheck; '
        'diagnostics=patchT1024; ordinary half-life growthT512; '
        'native F with unchanged extinction surcharge; R_cap500')


def expected_worlds():
    """Exact exploratory resource world and the two inherited AO physical worlds; no lives."""
    from src.life import spec

    return {
        'patch': asdict(spec.world('catch_resource_patches_l4', T=1024.)),
        'pool': asdict(spec.world('catch_speck_l4', T=1024., d0=.5, d_min=.25,
                                 sigma=.4, lam_s=4., v_t=.1, tau_turn=20.)),
        'persistent': asdict(spec.world('catch_speck_l4', T=1024., d0=1., d_min=.5,
                                       v_t=.3, tau_turn=200.)),
    }


def selection_identity(arm, worlds):
    if arm not in ARMS or worlds != expected_worlds():
        raise ValueError('exact fixed ABI6 resource-patch1024 / AO POOL / AO persistent worlds required')
    return {'version': 1, 'arm': arm, 'worlds': copy.deepcopy(worlds), 'rule': RULE,
            'pattern': list(PATTERNS[arm]),
            'source_pins': {'selection.py': hashlib.sha256((STUDY / 'selection.py').read_bytes()).hexdigest()}}


def extended_identity(base, configured):
    result = copy.deepcopy(base)
    if 'retention_selection' in result:
        raise ValueError('base identity already contains retention selection')
    result['retention_selection'] = copy.deepcopy(configured)
    return result


@contextmanager
def installed(evaluator_class, configured):
    """Retain native seeds and every nonselection draw, including ordinary T512 growth diagnostics."""
    from omegaconf import OmegaConf

    from src.life import spec

    if configured != selection_identity(configured['arm'], configured['worlds']):
        raise ValueError('selection source/configuration identity differs')
    worlds = {name: spec.World(**values) for name, values in configured['worlds'].items()}
    for world in worlds.values():
        spec.V6.validate_world(world)
    original = evaluator_class.draw

    def draw(self, purpose, index, lives=None, T=None, overrides=None, envelope=None):
        if OmegaConf.to_container(self.cfg.retention_selection, resolve=True) != configured:
            raise ValueError('evaluator selection configuration differs')
        count = self.lives if lives is None else int(lives)
        if purpose != 'gen':
            return original(self, purpose, index, lives=lives, T=T, overrides=overrides, envelope=envelope)
        if (self.abi.version != 6 or count not in (8, 16) or int(index) != index or index not in range(8)
                or (T is not None and T != 1024.) or overrides is not None or envelope not in (None, False)
                or self.T_choices or self.has_envelope or self.envelope.get('enabled', False)
                or not self.extinct_charge
                or asdict(self.world()) != configured['worlds']['patch']):
            raise ValueError('fixed 8+8 ABI6 mixed selection with patch1024 base and ordinary extinction charge required')
        result = original(self, purpose, index, lives=lives, T=T, overrides=overrides, envelope=envelope)
        if result.n != count or len(result.worlds) != count:
            raise ValueError('native draw length differs')
        return replace(result, worlds=tuple(worlds[configured['pattern'][i % 8]] for i in range(count)))

    evaluator_class.draw = draw
    try:
        yield
    finally:
        evaluator_class.draw = original
