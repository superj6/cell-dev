"""AC source-only preparation; copying retained inputs requires later root registration.

This program never generates a genotype, compiles a kernel or calls a life.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import math
import os
import sys
from dataclasses import asdict
from pathlib import Path

os.environ.setdefault('ATEN_CPU_CAPABILITY', 'avx2')
sys.dont_write_bytecode = True
STUDY = Path(__file__).resolve().parent
ROOT = STUDY.parents[1]
sys.path.insert(0, str(ROOT))

from common import read, sha, verify_pins  # noqa: E402
from measure import BLINK_ROWS, PARENTS, ROLES, SCOPE, WORLDS, stage_seeds  # noqa: E402

Y = ROOT / 'results/visibility_gradient_20261014'
Y_PROTOCOL = '1880ff6e21b4689031e892d9dc6765a8d9673a35efeefb213acf268f5370adf4'
Y_SOURCE_MAP = {'budget.json': 'operations/budget.json'}
PANEL_PINS = {'D90': '97ff2d0ee7ef3af4964b1a0fd357a618cb4d0193baa320cd86c2d06f7a8b9cb9',
              'L92': '6ad24101c26541bbc67ff505be2e846e49df30cc253e72d5932d6b0e64d97c01'}


def historical_source(canonical_name):
    """Public Y places its runtime budget under operations; copied inputs keep a stable name."""
    return Y / Y_SOURCE_MAP.get(canonical_name, canonical_name)


def freeze(path, data):
    path.parent.mkdir(parents=True, exist_ok=True)
    if path.exists():
        raise ValueError('one-time preparation refuses an existing input: ' + str(path))
    with path.open('xb') as stream:
        stream.write(data)
        stream.flush()
        os.fsync(stream.fileno())


def freeze_json(path, value):
    freeze(path, (json.dumps(value, indent=2, allow_nan=False) + '\n').encode())


def registration():
    item = read(STUDY / 'registration.json')
    if (item.get('status') != 'registered' or item.get('roles') != ROLES
            or item.get('panel_policy') != 'entire_Y_panels_unchanged_regardless_of_AB_outcomes'):
        raise ValueError('root registration of the fixed retained-panel design required')
    seeds = stage_seeds(item)
    audit = read(STUDY / 'seed_audit.json')
    if (sha(STUDY / 'seed_audit.json') != item['seed_audit_sha256']
            or audit.get('status') != 'passed' or audit.get('seeds') != seeds):
        raise ValueError('reviewed exact stage namespace required')
    dependency = item['AB_terminal']
    verify_pins(dependency['file_pins'], ROOT)
    budget_name = 'outputs/autonomous_visibility_precision_20261014/budget.json'
    if budget_name not in dependency['file_pins']:
        raise ValueError('terminal AB budget must be pinned')
    budget = read(ROOT / budget_name)
    if (budget.get('status') not in ('complete', 'incomplete', 'cpu_budget_exhausted', 'job_failed',
                                    'interrupted', 'monitor_failed')
            or budget.get('running') or budget.get('queued') or budget.get('cleanup_error')):
        raise ValueError('AB must have a clean terminal budget; scientific success is not required')
    return item, audit


def prepare():
    forbidden = ('protocol.json', 'inputs', 'configs', 'preparation_claim.json', 'ready.json',
                 'attempt.json', 'budget.json', 'measurement', 'logs', 'build-cache')
    if any((STUDY / name).exists() for name in forbidden):
        raise ValueError('first preparation refuses previous inputs or runtime work')
    reg, audit = registration()
    if sha(Y / 'protocol.json') != Y_PROTOCOL:
        raise ValueError('retained Y protocol differs')
    yp = read(Y / 'protocol.json')
    # Public Y stores production definitions under production/; also bind current runtime definitions.
    verify_pins(yp['file_pins'], Y)
    verify_pins(yp['production_pins'], ROOT)
    summary, budget = read(Y / 'analysis_result/summary.json'), read(historical_source('budget.json'))
    if summary.get('status') != 'complete' or budget.get('status') != 'complete':
        raise ValueError('complete reviewed Y panels required')
    from numerical import check
    check(yp['numerical_identity'])  # Metadata only; no checkpoint.numerical_identity call here.
    import numpy as np
    from omegaconf import OmegaConf

    from src.genome import Layout
    from src.life import spec
    from src.life.evaluate import LifeEvaluator

    worlds = {key: spec.world(preset, T=1024) for key, preset in WORLDS.items()}
    if asdict(worlds['blink']) != yp['world']:
        raise ValueError('unchanged historical blink world required')
    selected = read(Y / 'selection.json')
    if {p: selected[p]['genome_row'] for p in PARENTS} != BLINK_ROWS:
        raise ValueError('fixed historical blink selections changed')
    copy_names = ['protocol.json', 'budget.json', 'selection.json', 'startup_identity.json',
                  'analysis_result/summary.json', 'analysis/genetic_replay.py', 'analysis/genetic_replay.json']
    rates, configs, row_pins = {}, {}, {}
    for p in PARENTS:
        prefix = Y / 'inputs' / p
        table = np.load(prefix / 'genomes.npy', allow_pickle=False)
        manifest = read(prefix / 'panel_manifest.json')
        layout, founder = Layout.load(prefix / 'parent.json')
        def raw(x):
            return hashlib.sha256(x.tobytes()).hexdigest()
        if (sha(prefix / 'genomes.npy') != PANEL_PINS[p] or table.shape != (65, 875)
                or table.dtype != np.float32 or not np.isfinite(table).all()
                or table[0].tobytes() != founder.numpy().tobytes()
                or [raw(row) for row in table] != yp['panel_genotype_sha256'][p]
                or manifest['genomes_sha256'] != raw(table) or manifest['mutants'] != 64
                or manifest['parent_sha256'] != sha(prefix / 'parent.json')
                or manifest['config_sha256'] != sha(prefix / 'config.yaml')
                or manifest['mutation_ops_sha256'] != sha(prefix / 'mutation_ops.json')
                or selected[p]['raw_sha256'] != raw(table[BLINK_ROWS[p]])):
            raise ValueError('all retained panel, parent, operation and selected-row bytes must agree')
        copy_names.extend(f'inputs/{p}/{name}' for name in
                          ('genomes.npy', 'parent.json', 'mutation_ops.json', 'panel_manifest.json', 'config.yaml'))
        oldcfg = OmegaConf.load(prefix / 'config.yaml')
        for w, world in worlds.items():
            cfg = OmegaConf.create(OmegaConf.to_container(oldcfg, resolve=True))
            cfg.life.world = WORLDS[w]  # The sole configuration change; physics comes from the approved preset.
            evaluator = LifeEvaluator(cfg, layout)
            if (cfg.life.abi != 4 or cfg.threads != 2 or evaluator.abi.version != 4
                    or not evaluator.extinct_charge or not evaluator.fast or evaluator.T_choices
                    or evaluator.has_envelope or asdict(evaluator.world()) != asdict(world)):
                raise ValueError('retained scoring and exact approved visibility world required')
            configs[f'{w}_{p}'] = OmegaConf.to_yaml(cfg, resolve=True).encode()
        index = read(Y / f'measurement/{p}/row_index.json')
        copy_names.append(f'measurement/{p}/row_index.json')
        rates[p] = []
        for i in range(65):
            name = f'measurement/{p}/screen/row_{i:04d}.npz'
            path = Y / name
            info = index[f'screen/row_{i:04d}.npz']
            if sha(path) != info['sha256']:
                raise ValueError('historical blink timing row hash differs')
            with np.load(path, allow_pickle=False) as row:
                identity = {'protocol_sha256': Y_PROTOCOL, 'background': p, 'stage': 'screen',
                            'genome_index': i, 'genome_sha256': raw(table[i]), 'seeds': yp['seeds']['screen']}
                cpu, wall = float(row['cpu_seconds']), float(row['wall_seconds'])
                if (json.loads(str(row['identity'])) != identity or row['ledger'].shape != (32, 58)
                        or row['seeds'].tolist() != yp['seeds']['screen'] or int(row['genome_index']) != i
                        or cpu != info['cpu_seconds'] or not math.isfinite(cpu) or cpu <= 0
                        or not math.isfinite(wall) or wall < 0):
                    raise ValueError('exact 32-life historical timing row identity required')
                rates[p].append(cpu / 32)
            row_pins[name] = sha(path)
            copy_names.append(name)
    # Claim only after read-only verification; any partial write requires a new reviewed study, not a retry.
    freeze_json(STUDY / 'preparation_claim.json', {'registration_sha256': sha(STUDY / 'registration.json'),
        'genetic_draws': 0, 'retained_panel_rows': 130, 'simulation_calls': 0, 'compiled_libraries': 0})
    for name in copy_names:
        freeze(STUDY / 'inputs/Y' / name, historical_source(name).read_bytes())
    for key, data in configs.items():
        freeze(STUDY / 'configs' / (key + '.yaml'), data)
    freeze_json(STUDY / 'inputs/historical_blink_costs.json', {'source_protocol_sha256': Y_PROTOCOL,
        'source_pins': row_pins, 'cpu_per_life': rates, 'lives_per_row': 32})
    startup = read(Y / 'startup_identity.json')['identity']
    metadata = {k: v for k, v in startup.items() if k not in ('kernels', 'golden')}
    if metadata != yp['expected_startup_metadata']:
        raise ValueError('historical startup metadata changed')
    pinned = [path for folder in ('inputs', 'configs') for path in (STUDY / folder).rglob('*') if path.is_file()]
    pinned += list(STUDY.glob('*.py')) + [STUDY / name for name in
        ('README.md', 'PREREG.md', 'SCHEMA.md', 'registration.json', 'seed_audit.json', 'preparation_claim.json')]
    protocol = {'study': 'AC retained-panel flash gradient', 'world_decision': 'complete',
        'worlds': {key: asdict(world) for key, world in worlds.items()}, 'monitor_scope': SCOPE,
        'roles': ROLES, 'blink_selected_rows': BLINK_ROWS, 'seeds': reg['seeds'],
        'panel_policy': reg['panel_policy'], 'Y_protocol_sha256': Y_PROTOCOL,
        'panel_genotype_sha256': yp['panel_genotype_sha256'], 'historical_blink_cpu_per_life': rates,
        'expected_numerical_identity': startup, 'expected_startup_metadata': metadata,
        'numerical_identity': yp['numerical_identity'], 'production_pins': yp['production_pins'],
        'selection': {'rows': list(range(1, 65)), 'statistic': 'mean_production_F', 'tie': 'lowest_row_index'},
        'primary_contrasts': ['within__flash__H_D90_minus_P_D90', 'within__flash__H_L92_minus_P_L92'],
        'interaction_orientation': 'flash_minus_blink',
        'file_pins': {str(path.relative_to(STUDY)): sha(path) for path in sorted(pinned)}}
    freeze_json(STUDY / 'protocol.json', protocol)
    print(json.dumps({'status': 'prepared_unreleased', 'simulation_calls': 0, 'compiled_libraries': 0,
                      'genetic_draws': 0, 'copied_panel_rows': 130, 'historical_timing_rows': 130,
                      'configs': 4, 'protocol_sha256': sha(STUDY / 'protocol.json')}))


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--prepare', action='store_true')
    args = parser.parse_args()
    if not args.prepare:
        print(json.dumps({'status': 'source_only_unregistered', 'research_lives': 10304, 'startup_validation_lives': 10,
                          'simulation_calls': 0, 'compiled_libraries': 0, 'genetic_draws': 0,
                          'requires': 'clean AB terminal clearance, root registration and approved input copying'}))
        return
    prepare()


if __name__ == '__main__':
    main()
