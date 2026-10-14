"""Pure S seed-schedule and exact P-start audit. No active outcomes, compilation, or life simulation."""
from __future__ import annotations

import ast
import hashlib
import json
import os
import sys
from collections import Counter
from pathlib import Path

os.environ.setdefault('ATEN_CPU_CAPABILITY', 'avx2')
ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))

import numpy as np  # noqa: E402
import torch  # noqa: E402
from omegaconf import OmegaConf  # noqa: E402

from src.evolve import fill, setup  # noqa: E402
from src.genome import Layout  # noqa: E402
from src.life import build  # noqa: E402
from src.life.evaluate import life_seed  # noqa: E402

OUT = Path(__file__).resolve().parent
P = ROOT / 'outputs/autonomous_next_step_20261014'
R = ROOT / 'outputs/autonomous_weight_updates_20261014'
HELPER = ROOT / 'outputs/autonomous_s7_20261014/sources/D_prepare.py'
RUNS = (52091, 52092)


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def digest(values):
    return hashlib.sha256(json.dumps(sorted(set(values)), separators=(',', ':')).encode()).hexdigest()


def read(path):
    return json.loads(Path(path).read_text())


def records(run, generations, initial, recheck):
    result = []
    for generation in range(generations):
        for j in range(initial + recheck):
            result.append({'purpose': 'gen', 'index': generation, 'life': j,
                           'stage': 'initial' if j < initial else 'recheck',
                           'seed': life_seed(run, 'gen', generation, j)})
        if generation % 4 == 0 or generation == generations - 1:
            result.extend({'purpose': 'valid', 'index': generation, 'life': j, 'stage': 'diagnostic',
                           'seed': life_seed(run, 'valid', generation, j)} for j in range(16))
    for index in (0, 1):
        result.extend({'purpose': 'final', 'index': index, 'life': j, 'stage': 'diagnostic',
                       'seed': life_seed(run, 'final', index, j)} for j in range(2))
    return result


def pure_helpers():
    tree = ast.parse(HELPER.read_text())
    names = ('run_life_seeds', 'pilot_life_seeds')
    nodes = [n for n in tree.body if isinstance(n, ast.FunctionDef) and n.name in names]
    assert {n.name for n in nodes} == set(names)
    scope = {'life_seed': life_seed}
    exec(compile(ast.Module(body=nodes, type_ignores=[]), str(HELPER), 'exec'), scope)
    return scope


def main():
    # Any accidental evaluator call fails; setup/fill/draw are pure preparation operations.
    def no_life(*args, **kwargs):
        raise AssertionError('S audit attempted a life simulation')

    build.run = no_life
    sources = {}

    def pin(path):
        sources[str(path.relative_to(ROOT))] = sha(path)
        return path

    p_protocol = read(pin(P / 'protocol.json'))
    assert sha(P / 'protocol.json') == '2b4628a0ef6c2bef186641e5302eae9eaa1c41a98c1aa7218e9c95c378c70cfa'
    for relative, expected in p_protocol['source_identity'].items():
        assert sha(pin(ROOT / relative)) == expected, relative
    p_init = read(pin(P / 'initialization.json'))
    assert sha(P / 'initialization.json') == p_protocol['initialization_audit_sha256']
    r_protocol = read(pin(R / 'protocol.json'))
    prior = read(pin(R / 'seed_audit.json'))
    assert sha(R / 'seed_audit.json') == r_protocol['preparation_pins']['seed_audit.json']
    for relative, expected in prior['source_sha256'].items():
        assert sha(pin(ROOT / relative)) == expected, relative
    pin(HELPER)
    helper = pure_helpers()
    pilot = helper['pilot_life_seeds']()
    assert len(pilot) == 58690
    other_hashed = {seed for run in (51089, 51090, 51891, 51892) for seed in helper['run_life_seeds'](run)}
    assert len(other_hashed) == 784
    registrations = {name: value['seeds'] for name, value in prior['registrations'].items()}
    registrations['R_measurement'] = r_protocol['seeds']
    assert len(registrations) == 25
    decimal = {seed for values in registrations.values() for seed in values}
    confirmation = list(range(52_050_000, 52_050_256))
    all_prior = pilot | other_hashed | decimal
    assert not set(confirmation) & all_prior
    seed_lists, overlap_rows, init_rows, schedules, by_run = {}, {}, {}, {}, {}
    all_s, all_p = set(), set()
    for run in RUNS:
        p_records = records(run, 16, 3, 4)
        s_records = records(run, 8, 6, 8)
        pp = {r['seed']: r for r in p_records}
        ss = {r['seed']: r for r in s_records}
        assert len(pp) == 196 and len(ss) == 164
        assert [r['seed'] for r in p_records] == helper['run_life_seeds'](run)
        shared, new = set(ss) & set(pp), set(ss) - set(pp)
        assert len(shared) == 92 and len(new) == 72
        assert not set(ss) & all_prior and not set(confirmation) & (set(ss) | set(pp))
        overlap = []
        for record in s_records:
            if record['seed'] not in pp:
                continue
            old = pp[record['seed']]
            assert (record['purpose'], record['index'], record['life']) == (old['purpose'], old['index'], old['life'])
            overlap.append({'seed': record['seed'], 'purpose': record['purpose'], 'index': record['index'],
                            'life': record['life'], 'P_stage': old['stage'], 'S_stage': record['stage']})
        classes = Counter((r['purpose'], r['P_stage'], r['S_stage']) for r in overlap)
        assert classes == {('gen', 'initial', 'initial'): 24, ('gen', 'recheck', 'initial'): 24,
                           ('gen', 'recheck', 'recheck'): 8, ('valid', 'diagnostic', 'diagnostic'): 32,
                           ('final', 'diagnostic', 'diagnostic'): 4}
        overlap_rows[str(run)] = overlap
        seed_lists[str(run)] = [r['seed'] for r in s_records]
        by_run[str(run)] = {'P_unique_ids': len(pp), 'S_unique_ids': len(ss), 'shared_unique_ids': len(shared),
                            'S_new_unique_ids': len(new), 'S_new_ids': sorted(new),
                            'classes': [{'purpose': key[0], 'P_stage': key[1], 'S_stage': key[2], 'count': count}
                                        for key, count in classes.items()], 'S_records': s_records}
        all_s.update(ss)
        all_p.update(pp)
        cfg_path = pin(P / f'configs/s{run}.yaml')
        assert sha(cfg_path) == p_protocol['configs'][str(run)]['sha256']
        cfg = OmegaConf.load(cfg_path)
        assert cfg.seed == run and cfg.evolve.generations == 16 and cfg.life.lives == 3
        assert cfg.evolve.recheck_lives == 4 and cfg.evolve.recheck_k == 64 and cfg.evolve.heldout_every == 4
        assert cfg.evolve.dup_rate == cfg.evolve.del_rate == 0
        cfg.evolve.generations, cfg.life.lives, cfg.evolve.recheck_lives = 8, 6, 8
        _, layout, _, evaluator = setup(cfg)
        assert evaluator.fast and not evaluator.has_envelope and evaluator.T_choices == (768, 1024, 1536)
        evaluator.__class__.__call__ = no_life
        p_lengths = [evaluator.draw('gen', g).worlds[0].T for g in range(16)]
        assert p_lengths == p_protocol['selection_durations'][str(run)]
        s_lengths = p_lengths[:8]
        assert Counter(s_lengths) == {1536.: 4, 768.: 3, 1024.: 1}
        expected = {1536.: 10, 768.: 4, 1024.: 2} if run == 52091 else {1536.: 7, 768.: 8, 1024.: 1}
        assert Counter(p_lengths) == expected
        for g in range(8):
            assert list(evaluator.draw('gen', g, lives=14).seeds) == [life_seed(run, 'gen', g, j) for j in range(14)]
        schedules[str(run)] = {'S': s_lengths, 'P': p_lengths, 'S_counts': dict(Counter(s_lengths)),
                               'P_counts': dict(Counter(p_lengths)),
                               'S_selection_T1024_equivalent_lives': 2048 * sum(s_lengths) / 1024,
                               'P_selection_T1024_equivalent_lives': 1024 * sum(p_lengths) / 1024}
        founder_path = pin(ROOT / cfg.evolve.seed_genome)
        _, founder = Layout.load(founder_path)
        generator = torch.Generator().manual_seed(run)
        before = hashlib.sha256(generator.get_state().numpy().tobytes()).hexdigest()
        ops = []
        population = fill(founder[None], 32, layout, generator, cfg.evolve, ops=ops).numpy()
        after = hashlib.sha256(generator.get_state().numpy().tobytes()).hexdigest()
        saved = p_init['runs'][str(run)]
        population_path = pin(P / saved['population_file'])
        assert sha(population_path) == saved['file_sha256']
        retained = np.load(population_path, allow_pickle=False)
        assert population.dtype == retained.dtype == np.float32 and population.shape == retained.shape == (32, 875)
        assert population.tobytes() == retained.tobytes()
        assert population[0].tobytes() == founder.numpy().tobytes()
        assert before == saved['generator_before_sha256'] and after == saved['generator_after_sha256']
        assert ops == [r['ops'] for r in saved['copies']] and len(ops) == 31
        assert all(set(o) == {'mut'} and len(o['mut']) == 2 for o in ops)
        init_rows[str(run)] = {'founder_raw_sha256': hashlib.sha256(founder.numpy().tobytes()).hexdigest(),
                              'population_shape': list(population.shape), 'population_dtype': str(population.dtype),
                              'population_raw_sha256': hashlib.sha256(population.tobytes()).hexdigest(),
                              'P_population_file_sha256': sha(population_path),
                              'generator_before_sha256': before, 'generator_after_sha256': after,
                              'all32_rows_bitwise_identical_to_P': True, 'all31_mutation_records_identical': True,
                              'point_mutations': 62, 'pure_config_changes':
                                  {'evolve.generations': [16, 8], 'life.lives': [3, 6], 'evolve.recheck_lives': [4, 8]}}
    assert len(all_s) == 328 and len(all_p) == 392
    assert len(all_s & all_p) == 184 and len(all_s - all_p) == 144
    assert not (all_s - all_p) & (all_prior | all_p)
    assert not set(confirmation) & (all_s | all_p | all_prior)
    envelopes = [(30_000_000, 50_000_000), (51_000_000, 52_050_000)]
    for start, stop in envelopes:
        assert not any(start <= seed < stop for seed in all_s | set(confirmation))
    report = {'status': 'passed', 'simulated_lives': 0, 'active_P_outcomes_read': False,
              'candidate_seeds': confirmation, 'confirm_seeds': confirmation, 'candidate_block': 105,
              'run_life_seeds': seed_lists, 'S_records_by_run': by_run, 'intentional_P_overlap': overlap_rows,
              'unique_S_search_diagnostic_ids': len(all_s), 'unique_P_ids': len(all_p),
              'intentional_shared_P_ids': len(all_s & all_p), 'S_new_unique_ids': len(all_s - all_p),
              'other_study_or_prior_stream_overlap': 0, 'fresh_confirmation_overlaps': 0,
              'pilot_ids_checked': len(pilot), 'D_G_L_ids_checked': len(other_hashed),
              'prior_registered_allocations': {name: {'count': len(values), 'seeds': values,
                                                       'sha256': digest(values)}
                                               for name, values in registrations.items()},
              'historical_decimal_envelopes_half_open': envelopes, 'initialization_audits': init_rows,
              'duration_schedules': schedules, 'helper_sha256': sha(HELPER), 'source_sha256': sources,
              'script_sha256': sha(Path(__file__)),
              'genome_lives': {'selection': 2 * 8 * (256 * 6 + 64 * 8),
                               'periodic_validation': 2 * 3 * 16,
                               'tiny_final': 12, 'fresh_confirmation': 6 * 3 * 256, 'total': 37484},
              'limits': ['P/S share exact starting32 genomes and post-fill RNG; no later shared-population claim.',
                         'Intentional training overlap includes changed initial/recheck roles, '
                         'not independent replicate draws.',
                         'Shared valid generations0/4 and final-purpose IDs are diagnostics only, '
                         'never endpoint selection.',
                         'Final half-duration diagnostics deliberately reuse final index0 IDs; '
                         'distinct duration is retained.',
                         'Equal selection genome-lives is not equal CPU or exact duration-weighted work; '
                         'report actual CPU.',
                         'New S IDs and block105 avoid all other audited seeds; '
                         'startup full/fast seed11 reuse is intentional.',
                         'P endpoints will be fixed by completed generation16 rank0 only; '
                         'this audit reads no active outcomes.']}
    assert sum(report['genome_lives'][k] for k in ('selection', 'periodic_validation', 'tiny_final',
                                                  'fresh_confirmation')) == report['genome_lives']['total']
    path = OUT / 'source_seed_review.json'
    path.write_text(json.dumps(report, indent=2, allow_nan=False) + '\n')
    print(json.dumps({'status': 'passed', 'S_ids': len(all_s), 'P_shared': len(all_s & all_p),
                      'S_new': len(all_s - all_p), 'confirmation': len(confirmation), 'initial_rows_match_P': True,
                      'receipt_sha256': sha(path), 'simulated_lives': 0}))


if __name__ == '__main__':
    main()
