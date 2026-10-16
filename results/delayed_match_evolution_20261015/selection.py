"""Fixed mixed ABI5 matching selection; only generation draw-world allocation changes."""
from __future__ import annotations

import copy
import hashlib
from contextlib import contextmanager
from dataclasses import asdict, replace
from pathlib import Path

STUDY = Path(__file__).resolve().parent
ARMS = ('mixed',)
PATTERNS = {'mixed': ('match85', 'pool', 'match85', 'persistent') * 2}
RULE = ('gen fixed matching4/pool2/persistent2 per8 repeated for recheck; '
        'diagnostics=matchingT85; final index0/lives2 T42.5 mapped to integer growthT42; '
        'native F with unchanged extinction surcharge; R_cap500')


def expected_worlds():
    """Exact admitted matching world and the two inherited AO physical worlds; no lives."""
    from src.life import spec

    return {
        'match85': asdict(spec.world('catch_delayed_match_l4', T=85.)),
        'pool': asdict(spec.world('catch_speck_l4', T=1024., d0=.5, d_min=.25,
                                 sigma=.4, lam_s=4., v_t=.1, tau_turn=20.)),
        'persistent': asdict(spec.world('catch_speck_l4', T=1024., d0=1., d_min=.5,
                                       v_t=.3, tau_turn=200.)),
    }


def selection_identity(arm, worlds):
    if arm not in ARMS or worlds != expected_worlds():
        raise ValueError('exact fixed ABI5 matching85 / AO POOL / AO persistent worlds required')
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
    """Retain native seeds; map only the otherwise-invalid T85 growth diagnostic to T42."""
    from omegaconf import OmegaConf

    from src.life import spec

    if configured != selection_identity(configured['arm'], configured['worlds']):
        raise ValueError('selection source/configuration identity differs')
    worlds = {name: spec.World(**values) for name, values in configured['worlds'].items()}
    for world in worlds.values():
        spec.V5.validate_world(world)
    original = evaluator_class.draw

    def draw(self, purpose, index, lives=None, T=None, overrides=None, envelope=None):
        if OmegaConf.to_container(self.cfg.retention_selection, resolve=True) != configured:
            raise ValueError('evaluator selection configuration differs')
        count = self.lives if lives is None else int(lives)
        if purpose == 'final' and T == 42.5:
            # Native growth_at_half passes exactly these arguments for its two T85/2 lives.
            # The ABI requires integer T; this declared readout is t42, not an exact half-life.
            if (index != 0 or lives != 2 or count != 2 or overrides is not None or envelope is not None
                    or self.abi.version != 5 or self.T != 85. or self.T_choices or self.has_envelope
                    or self.envelope.get('enabled', False)
                    or asdict(self.world()) != configured['worlds']['match85']):
                raise ValueError('only the two exact native final growth diagnostics may map T42.5 to T42')
            return original(self, purpose, index, lives=lives, T=42., overrides=None, envelope=None)
        if purpose != 'gen':
            return original(self, purpose, index, lives=lives, T=T, overrides=overrides, envelope=envelope)
        if (self.abi.version != 5 or count not in (8, 16) or int(index) != index or index not in range(24)
                or (T is not None and T != 85.) or overrides is not None or envelope not in (None, False)
                or self.T_choices or self.has_envelope or self.envelope.get('enabled', False)
                or not self.extinct_charge
                or asdict(self.world()) != configured['worlds']['match85']):
            raise ValueError('fixed 8+8 ABI5 mixed selection with matching85 base and ordinary extinction charge required')
        result = original(self, purpose, index, lives=lives, T=T, overrides=overrides, envelope=envelope)
        if result.n != count or len(result.worlds) != count:
            raise ValueError('native draw length differs')
        return replace(result, worlds=tuple(worlds[configured['pattern'][i % 8]] for i in range(count)))

    evaluator_class.draw = draw
    try:
        yield
    finally:
        evaluator_class.draw = original
