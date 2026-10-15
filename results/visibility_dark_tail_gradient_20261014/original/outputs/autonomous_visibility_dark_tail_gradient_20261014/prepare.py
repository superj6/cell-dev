"""AG source-only preparation; copying retained inputs requires later root registration.

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

from world_contract import AC_PROTOCOL_SHA256, AD_PROTOCOL_SHA256, check_world  # noqa: E402

from common import read, sha, verify_pins  # noqa: E402
from measure import PARENTS, ROLES, SCOPE, WORLDS, stage_seeds  # noqa: E402

AD = ROOT / 'results/visibility_dark_tail_information_20261014'
AC = ROOT / 'results/visibility_flash_gradient_20261014'
Y = ROOT / 'results/visibility_gradient_20261014'
Y_PROTOCOL = '1880ff6e21b4689031e892d9dc6765a8d9673a35efeefb213acf268f5370adf4'
Y_SOURCE_MAP = {'budget.json': 'operations/budget.json'}
AC_SOURCE_MAP = {'budget.json': 'operations/budget.json'}
PANEL_PINS = {'D90': '97ff2d0ee7ef3af4964b1a0fd357a618cb4d0193baa320cd86c2d06f7a8b9cb9',
              'L92': '6ad24101c26541bbc67ff505be2e846e49df30cc253e72d5932d6b0e64d97c01'}


def historical_source(canonical_name):
    """Public Y places its runtime budget under operations; copied inputs keep a stable name."""
    return Y / Y_SOURCE_MAP.get(canonical_name, canonical_name)


def cost_source(name):
    return AC / AC_SOURCE_MAP.get(name, name)


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
            or item.get('panel_policy') != 'entire_Y_panels_unchanged_regardless_of_AF_outcomes'):
        raise ValueError('root registration of the fixed retained-panel design required')
    seeds = stage_seeds(item)
    audit = read(STUDY / 'seed_audit.json')
    if (sha(STUDY / 'seed_audit.json') != item['seed_audit_sha256']
            or audit.get('status') != 'passed' or audit.get('seeds') != seeds):
        raise ValueError('reviewed exact stage namespace required')
    dependency = item['AF_terminal']
    verify_pins(dependency['file_pins'], ROOT)
    budget_name = 'outputs/autonomous_prediction_continuation_20261014/budget.json'
    if budget_name not in dependency['file_pins']:
        raise ValueError('terminal AF budget must be pinned')
    budget = read(ROOT / budget_name)
    if (budget.get('status') not in ('complete', 'incomplete', 'cpu_budget_exhausted', 'job_failed',
                                    'interrupted', 'monitor_failed')
            or budget.get('running') or budget.get('queued') or budget.get('cleanup_error')):
        raise ValueError('AF must have a clean terminal budget; scientific success is not required')
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

    if sha(AD / 'protocol.json') != AD_PROTOCOL_SHA256:
        raise ValueError('exact archived AD protocol required')
    dp = read(AD / 'protocol.json')
    if read(AD / 'analysis_result/summary.json').get('status') != 'complete':
        raise ValueError('complete AD information-payoff evidence required')
    dark_world = dp['worlds']['flash5_dark']['production']['world']
    world = spec.World(**dark_world)
    check_world(asdict(world), dark_world)
    worlds = {'flash5_dark': world}
    packed = spec.V4.pack_world(world)
    if packed.dtype != np.float64 or packed.shape != (70,):
        raise ValueError('explicit ABI4 world packing required')
    preset = asdict(spec.world('catch_speck_flash5_dim25_l4', T=1024))
    overrides = {k: v for k, v in dark_world.items() if preset[k] != v}
    if overrides != {'visibility_low': 0.0}:
        raise ValueError('only the already approved dark-tail amplitude override is allowed')
    if sha(AC / 'protocol.json') != AC_PROTOCOL_SHA256:
        raise ValueError('exact archived AC timing source required')
    acp, acsummary = read(AC / 'protocol.json'), read(AC / 'analysis_result/summary.json')
    if (acsummary.get('status') != 'complete' or read(cost_source('budget.json')).get('status') != 'complete'
            or acp['panel_genotype_sha256'] != yp['panel_genotype_sha256']):
        raise ValueError('complete AC timings from the identical Y panel rows required')
    cost_names = ['protocol.json', 'budget.json', 'analysis_result/summary.json']
    copy_names = ['protocol.json', 'budget.json', 'startup_identity.json',
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
                or manifest['mutation_ops_sha256'] != sha(prefix / 'mutation_ops.json')):
            raise ValueError('all retained panel, parent, operation and selected-row bytes must agree')
        copy_names.extend(f'inputs/{p}/{name}' for name in
                          ('genomes.npy', 'parent.json', 'mutation_ops.json', 'panel_manifest.json', 'config.yaml'))
        oldcfg = OmegaConf.load(prefix / 'config.yaml')
        for w, world in worlds.items():
            cfg = OmegaConf.create(OmegaConf.to_container(oldcfg, resolve=True))
            cfg.life.world = WORLDS[w]
            cfg.life.abi = 4
            cfg.world = overrides  # Match the complete approved AD production world.
            evaluator = LifeEvaluator(cfg, layout)
            if (cfg.life.abi != 4 or cfg.threads != 2 or evaluator.abi.version != 4
                    or not evaluator.extinct_charge or not evaluator.fast or evaluator.T_choices
                    or evaluator.has_envelope or asdict(evaluator.world()) != asdict(world)):
                raise ValueError('retained scoring and exact archived AD world required')
            configs[f'{w}_{p}'] = OmegaConf.to_yaml(cfg, resolve=True).encode()
        index_name = f'measurement/screen/{p}/row_index.json'
        index = read(AC / index_name)
        if acsummary['input_pins'][index_name] != sha(AC / index_name):
            raise ValueError('historical AC timing index differs from complete review')
        cost_names.append(index_name)
        rates[p] = []
        for i in range(65):
            name = f'measurement/screen/{p}/screen/row_{i:04d}.npz'
            path = AC / name
            info = index[f'screen/row_{i:04d}.npz']
            if sha(path) != info['sha256'] or acsummary['input_pins'][name] != sha(path):
                raise ValueError('historical dim-flash timing row hash differs')
            with np.load(path, allow_pickle=False) as row:
                identity = {'protocol_sha256': AC_PROTOCOL_SHA256, 'background': p, 'world': 'flash', 'stage': 'screen',
                            'genome_index': i, 'genome_sha256': raw(table[i]), 'seeds': acp['seeds']['screen']}
                cpu, wall = float(row['cpu_seconds']), float(row['wall_seconds'])
                if (json.loads(str(row['identity'])) != identity or row['ledger'].shape != (32, 58)
                        or row['seeds'].tolist() != acp['seeds']['screen'] or int(row['genome_index']) != i
                        or cpu != info['cpu_seconds'] or not math.isfinite(cpu) or cpu <= 0
                        or not math.isfinite(wall) or wall < 0):
                    raise ValueError('exact 32-life historical timing row identity required')
                rates[p].append(cpu / 32)
            row_pins[name] = sha(path)
            cost_names.append(name)
    # Claim only after read-only verification; any partial write requires a new reviewed study, not a retry.
    freeze_json(STUDY / 'preparation_claim.json', {'registration_sha256': sha(STUDY / 'registration.json'),
        'genetic_draws': 0, 'retained_panel_rows': 130, 'simulation_calls': 0, 'compiled_libraries': 0})
    for name in copy_names:
        freeze(STUDY / 'inputs/Y' / name, historical_source(name).read_bytes())
    for name in cost_names:
        freeze(STUDY / 'inputs/AC' / name, cost_source(name).read_bytes())
    for name in ('protocol.json', 'analysis_result/summary.json'):
        freeze(STUDY / 'inputs/AD' / name, (AD / name).read_bytes())
    for key, data in configs.items():
        freeze(STUDY / 'configs' / (key + '.yaml'), data)
    freeze_json(STUDY / 'inputs/historical_flash_costs.json', {'source_protocol_sha256': AC_PROTOCOL_SHA256,
        'source_pins': row_pins, 'cpu_per_life': rates, 'lives_per_row': 32})
    startup = read(Y / 'startup_identity.json')['identity']
    metadata = {k: v for k, v in startup.items() if k not in ('kernels', 'golden')}
    if metadata != yp['expected_startup_metadata']:
        raise ValueError('historical startup metadata changed')
    pinned = [path for folder in ('inputs', 'configs') for path in (STUDY / folder).rglob('*') if path.is_file()]
    pinned += list(STUDY.glob('*.py')) + [STUDY / name for name in
        ('README.md', 'PREREG.md', 'SCHEMA.md', 'registration.json', 'seed_audit.json', 'preparation_claim.json')]
    protocol = {'study': 'AG retained-panel dark-flash gradient', 'abi': 4, 'world_decision': 'complete',
        'world': dark_world, 'AD_protocol_sha256': AD_PROTOCOL_SHA256, 'AC_protocol_sha256': AC_PROTOCOL_SHA256, 'monitor_scope': SCOPE,
        'world_packing': {'abi': 4, 'keys': list(spec.V4.WORLD_KEYS), 'values': packed.tolist(),
                          'raw_sha256': hashlib.sha256(packed.tobytes()).hexdigest()},
        'configuration_changes': {'life.world': 'catch_speck_flash5_dim25_l4', 'life.abi': 4, 'world': overrides},
        'roles': ROLES, 'seeds': reg['seeds'],
        'panel_policy': reg['panel_policy'], 'Y_protocol_sha256': Y_PROTOCOL,
        'panel_genotype_sha256': yp['panel_genotype_sha256'], 'historical_flash_cpu_per_life': rates,
        'expected_numerical_identity': startup, 'expected_startup_metadata': metadata,
        'numerical_identity': yp['numerical_identity'], 'production_pins': yp['production_pins'],
        'selection': {'rows': list(range(1, 65)), 'statistic': 'mean_production_F', 'tie': 'lowest_row_index'},
        'primary_contrasts': ['H_D90_minus_P_D90', 'H_L92_minus_P_L92'],
        'file_pins': {str(path.relative_to(STUDY)): sha(path) for path in sorted(pinned)}}
    freeze_json(STUDY / 'protocol.json', protocol)
    print(json.dumps({'status': 'prepared_unreleased', 'simulation_calls': 0, 'compiled_libraries': 0,
                      'genetic_draws': 0, 'copied_panel_rows': 130, 'historical_timing_rows': 130,
                      'configs': 2, 'protocol_sha256': sha(STUDY / 'protocol.json')}))


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--prepare', action='store_true')
    args = parser.parse_args()
    if not args.prepare:
        print(json.dumps({'status': 'source_only_unregistered', 'research_lives': 6208, 'startup_validation_lives': 10,
                          'simulation_calls': 0, 'compiled_libraries': 0, 'genetic_draws': 0,
                          'requires': 'clean AF terminal clearance, root registration and approved input copying'}))
        return
    prepare()


if __name__ == '__main__':
    main()
