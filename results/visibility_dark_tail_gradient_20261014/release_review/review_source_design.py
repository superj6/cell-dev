"""Independent AG source/world/timing review; no engine, draws or input copies."""
from pathlib import Path
import ast
import hashlib
import json
import math
import sys

import numpy as np

ROOT = Path(__file__).resolve().parents[2]
OUT = Path(__file__).resolve().parent
STUDY = ROOT / 'outputs/autonomous_visibility_dark_tail_gradient_20261014'
AC = ROOT / 'results/visibility_flash_gradient_20261014'
AD = ROOT / 'results/visibility_dark_tail_information_20261014'
AE = ROOT / 'results/prediction_gradient_20261014'
Y = ROOT / 'results/visibility_gradient_20261014'
sys.path.insert(0, str(ROOT))
from src.life import spec


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def read(path):
    return json.loads(path.read_text())


def functions(path):
    return {n.name: n for n in ast.parse(path.read_text()).body if isinstance(n, ast.FunctionDef)}


def main():
    forbidden = ('registration.json', 'seed_audit.json', 'inputs', 'configs', 'protocol.json',
                 'preparation_claim.json', 'ready.json', 'attempt.json', 'budget.json',
                 'measurement', 'logs', 'build-cache')
    assert all(not (STUDY / name).exists() for name in forbidden)
    lifecycle = ('own_cpu', 'child_cpu', 'proc_table', 'active_cpu', 'consumed_cpu',
                 'child_limit', 'send_signal', 'enable_subreaper', 'cleanup_group',
                 'cleanup', 'interrupt', 'process_identity')
    old, new = functions(AE / 'monitor.py'), functions(STUDY / 'monitor.py')
    assert all(ast.dump(old[n], include_attributes=False) == ast.dump(new[n], include_attributes=False)
               for n in lifecycle)
    assert sha(STUDY / 'scoring.py') == sha(Y / 'scoring.py')
    assert sha(STUDY / 'numerical.py') == sha(AE / 'numerical.py')
    for filename, count in (('prepare.py', 0), ('monitor.py', 0), ('measure.py', 1)):
        calls = [n for n in ast.walk(ast.parse((STUDY / filename).read_text()))
                 if isinstance(n, ast.Call) and ((isinstance(n.func, ast.Name) and n.func.id == 'numerical_identity')
                    or (isinstance(n.func, ast.Attribute) and n.func.attr == 'numerical_identity'))]
        assert len(calls) == count
    ad, ac = read(AD / 'protocol.json'), read(AC / 'protocol.json')
    world_dict = ad['worlds']['flash5_dark']['production']['world']
    world = spec.World(**world_dict)
    from dataclasses import asdict
    preset = asdict(spec.world('catch_speck_flash5_dim25_l4', T=1024))
    assert {k: v for k, v in world_dict.items() if preset[k] != v} == {'visibility_low': 0.0}
    packed = spec.V4.pack_world(world)
    assert packed.dtype == np.float64 and packed.shape == (70,)
    assert (spec.V4.LEDGER_SIZE, spec.V4.GENOME_SIZE) == (58, 875)
    assert (world.visibility_mode, world.visibility_on, world.visibility_off, world.visibility_low) == (1, 5, 0, 0)
    assert (world.T, world.d0, world.d_min, world.v_t, world.tau_turn) == (1024, 1, .5, .1, 20)
    summary = read(AC / 'analysis_result/summary.json')
    historical = read(OUT / 'historical_AC_timing_review.json')
    rates, evidence = {}, {}
    for background in ('D90', 'L92'):
        rates[background] = []
        index_name = f'measurement/screen/{background}/row_index.json'
        index = read(AC / index_name)
        assert sha(AC / index_name) == summary['input_pins'][index_name] == historical['source_pins'][index_name]
        evidence[index_name] = sha(AC / index_name)
        for i in range(65):
            local = f'screen/row_{i:04d}.npz'
            name = f'measurement/screen/{background}/{local}'
            path = AC / name
            digest = sha(path)
            assert digest == summary['input_pins'][name] == historical['source_pins'][name] == index[local]['sha256']
            with np.load(path, allow_pickle=False) as row:
                cpu, wall = float(row['cpu_seconds']), float(row['wall_seconds'])
                identity = json.loads(str(row['identity']))
                assert math.isfinite(cpu) and cpu > 0 and math.isfinite(wall) and wall >= 0
                assert cpu == index[local]['cpu_seconds']
                assert row['seeds'].dtype == np.uint64 and row['seeds'].tolist() == ac['seeds']['screen']
                assert int(row['genome_index']) == i
                assert identity == {'protocol_sha256': sha(AC / 'protocol.json'), 'background': background,
                    'world': 'flash', 'stage': 'screen', 'genome_index': i,
                    'genome_sha256': ac['panel_genotype_sha256'][background][i], 'seeds': ac['seeds']['screen']}
            rates[background].append(cpu / 32)
            evidence[name] = digest
    assert rates == historical['cpu_per_life']
    screen = 180 + 1.5 * 32 * sum(sum(x) for x in rates.values())
    confirm = 180 + 1.5 * 512 * sum(x[0] + max(x) for x in rates.values())
    assert screen == historical['planning_floor_with_180_startup_allowance']['screen']
    assert confirm == historical['planning_floor_with_180_startup_allowance']['confirmation']
    assert screen < 3390 and confirm < 1990
    assert all(name not in sys.modules for name in ('src.life.build', 'src.evolve', 'src.checkpoint'))
    source_pins = {str(p.relative_to(ROOT)): sha(p) for p in sorted(STUDY.iterdir()) if p.is_file()}
    for path in (Path(__file__), ROOT / 'src/life/spec.py', ROOT / 'src/life/kernel.c',
                 ROOT / 'src/life/evaluate.py', ROOT / 'src/checkpoint.py', AD / 'protocol.json',
                 AC / 'protocol.json', AC / 'analysis_result/summary.json', AE / 'monitor.py',
                 AE / 'numerical.py', Y / 'scoring.py', OUT / 'historical_AC_timing_review.json'):
        source_pins[str(path.relative_to(ROOT))] = sha(path)
    receipt = {
        'status': 'passed_source_design', 'registered': False, 'reserved': False,
        'source_pins': source_pins,
        'world': {'exact_AD_production_world': True, 'abi': 4, 'packed_fields': 70,
                  'ledger_fields': 58, 'genome_fields': 875,
                  'packing_sha256': hashlib.sha256(packed.tobytes()).hexdigest(),
                  'only_preset_override': {'visibility_low': 0.0}},
        'reused_components': {'AE_monitor_lifecycle_AST_identical': list(lifecycle),
                              'Y_ABI4_scorer_byte_identical': True, 'AE_numerical_byte_identical': True},
        'calls': {'calibration': 8, 'identity_invocations': 1, 'identity_goldens': 2,
                  'screen': 4160, 'confirmation': 2048, 'research': 6208, 'total': 6218},
        'source_timing_pins': evidence,
        'historical_planning_floor_with_180_startup_allowance': {'screen': screen, 'confirmation': confirm},
        'cost_contract': [
            'Current calibration is parent row0 plus one mutant row1, each on two seeds, in both fixed backgrounds.',
            'Each of130 screen rates is max(current lineage calibration max, its own historical AC rate). Startup uses acknowledged actual aggregate CPU.',
            'Initial parent rate uses its own calibration/history; unknown selected mutant uses max(current lineage calibration max, all65 historical rates).',
            'After both winners are frozen, each of four roles uses max(its actual32-life screen rate, its own historical rate), retaining duplicate genotypes as separate roles.',
            'Both projected gates use1.5 margin; screen<=3390, confirmation180+projected<=1990. Timings already include both threads.',
            'One persistent two-thread worker; monitor cumulative stops170/3390/5390 inside180/3400/5400 caps. Its RLIMIT covers remaining total, not only the early phase.',
            'Startup, compilation, failed work and descendant teardown remain in total CPU. The2000 reserve is minimum remaining capacity, not an independent confirmation hard cap.',
            'Dim-flash rates are cost floors, not predictions or guarantees for dark-world work; unmeasured calibration may reject the fixed scope.'
        ],
        'scientific_question': 'Can ordinary mutations already present in both complete Y panels improve physical capture success in the approved fully dark-tail flash world?',
        'selection_contract': 'Every retained parent+64 mutant rows screened; highest whole production-F mean among1..64 wins even if below its parent, ties lowest row. Freeze both winners before fresh paired512 confirmations.',
        'scientific_limits': [
            'No hand-built controller success threshold selects this world or a background. Prior information-payoff evidence motivates the question; it does not choose organism behavior.',
            'Fixed original panels avoid adapting genotype eligibility to AF outcomes. Two backgrounds are not independent evolutionary replicates.',
            'Report F, total/bright/dark captures, capture income and physical cost savings. A positive F gain alone can be economy only.',
            'A dark capture can result from motion persistence, body geometry or delayed actuation after the flash. It does not isolate memory, prediction or a learned internal model.',
            'Target motion and replacement remain unchanged; low0 removes current target-rate modulation after the flash but background sensory events remain.',
            'No fresh paired dim-versus-dark comparison is included; historical AC outcomes cannot supply that causal interaction.'
        ],
        'authorization_scope': 'Source-only review of already approved ABI4 world constants and unchanged production prices. Registration, input copying, readiness and execution remain root-owned and unperformed.',
        'no_runtime_paths': list(forbidden), 'simulation_calls': 0, 'compilation_calls': 0,
        'genetic_draws': 0, 'scientific_input_copies': 0,
    }
    destination = OUT / 'independent_source_design_review.json'
    destination.write_text(json.dumps(receipt, indent=2) + '\n')
    print(json.dumps({'status': receipt['status'], 'receipt_sha256': sha(destination),
                      'screen_floor': screen, 'confirmation_floor': confirm, 'timing_rows_checked': 130,
                      'simulation_calls': 0, 'compilation_calls': 0}))


if __name__ == '__main__':
    main()
