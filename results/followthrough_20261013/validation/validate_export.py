"""Zero-life audit of independent selector arithmetic and exported summaries."""
from __future__ import annotations

import importlib.util
import json
import sys
from pathlib import Path

import numpy as np

ROOT = next(p for p in Path(__file__).resolve().parents if (p / 'src/genome.py').is_file())
sys.path.insert(0, str(ROOT))


def module(name, path):
    spec = importlib.util.spec_from_file_location(name, path)
    value = importlib.util.module_from_spec(spec)
    sys.modules[name] = value
    spec.loader.exec_module(value)
    return value


def main():
    study = Path(__file__).resolve().parent.parent
    script = study / ('aggregate.py' if (study / 'aggregate.py').exists() else 'analyze.py')
    analysis = module('followthrough_export_analysis', script)
    production = module('followthrough_selector', analysis.source_path(study, 'taskvar_second_step.py'))
    world = analysis.spec.world('catch_speck_l4', T=1024, sigma=.4, lam_s=4, d0=.5, d_min=.25)
    mapping = np.array([0] * 32 + list(range(1, 225)))
    seeds = list(range(51_860_000, 51_860_028))
    rng = np.random.default_rng(13013)
    outlier = rng.normal(size=(225, 28))
    outlier[41, :3] = 10
    outlier[41, 3:7] = -10
    fixtures = {'all_ties': np.zeros((225, 28)), 'integer_ties': rng.integers(-2, 3, (225, 28)),
                'continuous': rng.normal(size=(225, 28)), 'first_stage_outlier': outlier}
    checks = []
    for name, scores in fixtures.items():
        for initial, extra in ((3, 4), (12, 16)):
            observed = analysis.independent_selection(scores, mapping, seeds, initial, extra, 32, 64, 13013)
            expected = production.select_rule(scores, mapping, seeds, world, initial=initial, extra=extra,
                keep=32, shortlist=64, tie_seed=13013)
            for key, value in observed.items():
                assert value == expected[key], (name, initial, key)
            checks.append({'fixture': name, 'initial': initial, 'extra': extra,
                'winner': observed['winner_candidate_row'], 'match': True})
    analysis.self_check()
    analysis.write_json(study / 'validation/independent_selector_analysis.json', {
        'selector_independent_replay_comparisons': len(checks), 'checks': checks, 'simulated_lives': 0,
        'analysis_sha256': analysis.digest(script), 'validator_sha256': analysis.digest(Path(__file__)),
        'selector_source_sha256': analysis.digest(Path(production.__file__))})
    print(json.dumps({'independent_selector_matches': len(checks), 'simulated_lives': 0}))


if __name__ == '__main__':
    main()
