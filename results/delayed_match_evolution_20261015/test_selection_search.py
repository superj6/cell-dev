"""Supplied-input ABI5 adapter and passive snapshot checks; no simulator or RNG draws."""
from __future__ import annotations

import copy
import hashlib
import importlib.util
import json
import sys
from dataclasses import asdict
from pathlib import Path
from types import SimpleNamespace

import pytest

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[1]
STUDY = HERE
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(STUDY))


def module(name):
    found = importlib.util.spec_from_file_location('matching_test_' + name, STUDY / (name + '.py'))
    loaded = importlib.util.module_from_spec(found)
    found.loader.exec_module(loaded)
    return loaded


def digest(data):
    return hashlib.sha256(data).hexdigest()


@pytest.fixture(autouse=True)
def forbid_engine(monkeypatch):
    from src.life import build

    def forbidden(*args, **kwargs):
        raise AssertionError('engine calls or compilation are forbidden in these tests')

    monkeypatch.setattr(build, 'build', forbidden)
    monkeypatch.setattr(build, 'run', forbidden)


@pytest.fixture
def evaluator(monkeypatch):
    from omegaconf import OmegaConf

    from src.life import evaluate, spec

    # Config metadata only; no historical genotype or outcome is loaded.
    cfg = OmegaConf.load(ROOT / 'outputs/autonomous_retained_depth_20261015/runs/balanced/config.yaml')
    cfg.life.lives = 8
    cfg.life.abi = 5
    cfg.life.world = 'catch_delayed_match_l4'
    cfg.life.T = 85.
    cfg.world = {}
    cfg.life.T_choices = None
    cfg.seed = 0
    ev = evaluate.LifeEvaluator(cfg, SimpleNamespace(abi=spec.V3))
    worlds = module('selection').expected_worlds()
    monkeypatch.setattr(evaluate, 'life_seed', lambda seed, purpose, g, i: (purpose, g, i))
    return evaluate.LifeEvaluator, ev, worlds


@pytest.mark.parametrize('arm', ('mixed',))
def test_native_draw_prefix_recheck_and_exact_counts(evaluator, arm):
    from src.evolve import recheck_draw

    cls, ev, worlds = evaluator
    adapter = module('selection')
    configured = adapter.selection_identity(arm, worlds)
    ev.cfg.retention_selection = configured
    old = cls.draw
    baseline = ev.draw('gen', 0, lives=16)
    with adapter.installed(cls, configured):
        for g in range(24):
            first, full = ev.draw('gen', g), ev.draw('gen', g, lives=16)
            second = recheck_draw(ev, g, 8, 8)
            assert first.seeds == full.seeds[:8]
            assert first.worlds == full.worlds[:8]
            assert second.seeds == full.seeds[8:] and second.worlds == full.worlds[8:]
            assert first.n == second.n == 8 and full.n == 16
            assert full.seeds == tuple(('gen', g, i) for i in range(16))
            labels = list(adapter.PATTERNS[arm]) * 2
            assert [asdict(w) for w in full.worlds] == [worlds[name] for name in labels]
            assert labels.count('persistent') == 4
            assert labels.count('pool') == 4
            assert labels.count('match85') == 8
    assert cls.draw is old
    assert ev.draw('gen', 0, lives=16) == baseline




def test_changed_pattern_and_unknown_arm_rejected(evaluator):
    cls, _, worlds = evaluator
    adapter = module('selection')
    with pytest.raises(ValueError):
        adapter.selection_identity('adaptive', worlds)
    configured = adapter.selection_identity('mixed', worlds)
    configured['pattern'][0] = 'pool'
    with pytest.raises(ValueError):
        with adapter.installed(cls, configured):
            pass


@pytest.mark.parametrize('purpose,lives,T', [('valid', 16, None), ('final', 2, None), ('final', 2, 42.)])
def test_diagnostics_unchanged_and_restore_after_failure(evaluator, purpose, lives, T):
    cls, ev, worlds = evaluator
    adapter = module('selection')
    configured = adapter.selection_identity('mixed', worlds)
    ev.cfg.retention_selection = configured
    original = cls.draw
    expected = ev.draw(purpose, 0, lives=lives, T=T)
    with pytest.raises(RuntimeError, match='synthetic'):
        with adapter.installed(cls, configured):
            assert ev.draw(purpose, 0, lives=lives, T=T) == expected
            raise RuntimeError('synthetic failure')
    assert cls.draw is original


def test_only_native_fractional_growth_query_maps_to_t42(evaluator):
    import torch

    cls, ev, worlds = evaluator
    adapter = module('selection')
    configured = adapter.selection_identity('mixed', worlds)
    ev.cfg.retention_selection = configured
    expected = ev.draw('final', 0, lives=2, T=42.)
    with pytest.raises(ValueError, match='integers'):
        ev.draw('final', 0, lives=2, T=42.5)
    before = torch.get_rng_state().clone()
    with adapter.installed(cls, configured):
        actual = ev.draw('final', 0, lives=2, T=42.5)
        assert actual == expected and actual.seeds == (('final', 0, 0), ('final', 0, 1))
        assert all(w.T == 42. and w.task_mode == 1 for w in actual.worlds)
        assert all(w.T == (85. if w.task_mode else 1024.) for w in ev.draw('gen', 0).worlds)
    assert torch.equal(before, torch.get_rng_state())


@pytest.mark.parametrize('kwargs', [{'index': 1}, {'lives': 1}, {'lives': 2.5},
                                  {'overrides': []}, {'envelope': False}, {'envelope': True}])
def test_growth_exception_rejects_other_call_contracts(evaluator, kwargs):
    cls, ev, worlds = evaluator
    adapter = module('selection')
    configured = adapter.selection_identity('mixed', worlds)
    ev.cfg.retention_selection = configured
    request = {'purpose': 'final', 'index': 0, 'lives': 2, 'T': 42.5, **kwargs}
    with adapter.installed(cls, configured), pytest.raises(ValueError):
        ev.draw(**request)


@pytest.mark.parametrize('kwargs', [{'lives': 4}, {'lives': 12}, {'T': 512}, {'overrides': []}, {'envelope': True}])
def test_wrong_selection_draw_contract_rejected(evaluator, kwargs):
    cls, ev, worlds = evaluator
    adapter = module('selection')
    configured = adapter.selection_identity('mixed', worlds)
    ev.cfg.retention_selection = configured
    with adapter.installed(cls, configured), pytest.raises(ValueError):
        ev.draw('gen', 0, **kwargs)


def test_changed_source_world_config_and_identity_rejected(evaluator):
    from src import checkpoint

    cls, ev, worlds = evaluator
    adapter = module('selection')
    configured = adapter.selection_identity('mixed', worlds)
    ev.cfg.retention_selection = configured
    identity = adapter.extended_identity({'golden': 'mock'}, configured)
    saved = {'config': checkpoint.config_identity(ev.cfg), 'identity': identity}
    checkpoint.validate(saved, ev.cfg, identity)
    changed = copy.deepcopy(configured)
    changed['source_pins']['selection.py'] = '0' * 64
    with pytest.raises(ValueError):
        with adapter.installed(cls, changed):
            pass
    with adapter.installed(cls, configured):
        ev.cfg.world.v_t = .4
        with pytest.raises(ValueError):
            ev.draw('gen', 0)
    with pytest.raises(ValueError):
        checkpoint.validate(saved, ev.cfg, identity)
    with pytest.raises(ValueError):
        adapter.extended_identity(identity, configured)






@pytest.fixture
def population(tmp_path):
    import torch
    from omegaconf import OmegaConf

    from src.genome import make_dims, make_layout

    cfg = OmegaConf.load(ROOT / 'outputs/autonomous_retained_depth_20261015/runs/balanced/config.yaml')
    layout = make_layout(make_dims({**OmegaConf.to_container(cfg.genome.life), 'kind': 'life'}))
    table = torch.arange(32 * layout.size, dtype=torch.float32).reshape(32, -1) / 10000
    table[2] = table[1]
    layout.view(table, 'act')[:] = 0
    layout.view(table, 'act')[:, :8] = 1
    old_ids = list(range(1000, 1032))
    path = tmp_path / 'input_population.json'
    path.write_text(json.dumps({'dims': layout.dims.__dict__, 'ids': old_ids,
                               'genomes': [layout.to_dict(row) for row in table],
                               'fitness': ['unused scores'] * 32}))
    hashes = [digest(row.numpy().tobytes()) for row in table]
    record = {'population_file': path.name, 'file_sha256': digest(path.read_bytes()),
              'population_raw_sha256': digest(table.numpy().tobytes()), 'shape': [32, 875],
              'old_ids': old_ids, 'new_ids': list(range(32)), 'row_sha256': hashes,
              'old_to_new': [{'old_id': old, 'new_id': i, 'row': i, 'raw_sha256': hashes[i]}
                             for i, old in enumerate(old_ids)]}
    return path, layout, table, record, cfg


def test_all_32_rows_duplicates_and_empty_fill_rng(population):
    import torch

    from src.evolve import fill

    path, layout, table, record, cfg = population
    loader = module('population_loader')
    result = loader.read_population(path, layout, record)
    gen = torch.Generator().manual_seed(123)
    before = gen.get_state().clone()
    operations = []
    filled = fill(result, 32, layout, gen, cfg.evolve, ops=operations)
    assert filled.numpy().tobytes() == table.numpy().tobytes()
    assert torch.equal(before, gen.get_state()) and operations == []
    assert result[1].numpy().tobytes() == result[2].numpy().tobytes()


@pytest.mark.parametrize('key', ['file_sha256', 'old_ids', 'new_ids', 'old_to_new'])
def test_population_import_mismatch_rejected(population, key):
    path, layout, _, record, _ = population
    changed = copy.deepcopy(record)
    changed[key] = '0' * 64 if key == 'file_sha256' else list(reversed(changed[key]))
    with pytest.raises(ValueError):
        module('population_loader').read_population(path, layout, changed)


def test_loader_scope_restored(population, monkeypatch):
    from omegaconf import OmegaConf

    path, layout, table, record, cfg = population
    loader = module('population_loader')
    monkeypatch.setattr(loader, 'STUDY', path.parent)
    for name in ('population_loader.py', 'search.py'):
        (path.parent / name).write_text('synthetic source only')
    cfg.population_start = loader.loader_identity(record)
    cfg.evolve.seed_genome = str(path)
    original = object()
    native = SimpleNamespace(seed_genome=original)
    with pytest.raises(RuntimeError):
        with loader.installed(native, OmegaConf.to_container(cfg.population_start)):
            assert native.seed_genome(cfg, layout).numpy().tobytes() == table.numpy().tobytes()
            raise RuntimeError('synthetic')
    assert native.seed_genome is original


def test_exactly_one_identity_and_both_extensions():
    search = module('search')
    calls = []
    expected = {'golden': 'mock only'}
    wrapped = search.one_identity(lambda: calls.append(1) or expected, expected, {'population': 'mock'}, {'selection': 'mock'})
    assert wrapped() == {**expected, 'population_start': {'population': 'mock'}, 'retention_selection': {'selection': 'mock'}}
    assert wrapped.calls == 1
    with pytest.raises(ValueError):
        wrapped()
    assert calls == [1] and expected == {'golden': 'mock only'}
    with pytest.raises(ValueError):
        search.one_identity(lambda: {'wrong': True}, expected, {}, {})()


def test_loader_is_exact_reviewed_AJ_source():
    old = ROOT / 'outputs/autonomous_retained_depth_20261015/population_loader.py'
    assert (STUDY / 'population_loader.py').read_bytes() == old.read_bytes()




@pytest.mark.parametrize('field,value', [('v_t', .4), ('R_cap', 2000), ('visibility_off', 40.)])
def test_acquisition_world_cannot_change_other_physics(evaluator, field, value):
    _, _, worlds = evaluator
    worlds['match85'][field] = value
    with pytest.raises(ValueError):
        module('selection').selection_identity('mixed', worlds)


def test_wrong_abi_or_generation_rejected(evaluator):
    from src.life import spec

    cls, ev, worlds = evaluator
    adapter = module('selection')
    configured = adapter.selection_identity('mixed', worlds)
    ev.cfg.retention_selection = configured
    with adapter.installed(cls, configured):
        with pytest.raises(ValueError):
            ev.draw('gen', 24)
        ev.abi = spec.V3
        with pytest.raises(ValueError):
            ev.draw('gen', 0)


@pytest.fixture
def completed_native(population, monkeypatch):
    import torch
    from omegaconf import OmegaConf

    from src import checkpoint

    path, layout, table, _, cfg = population
    search = module('search')
    monkeypatch.setattr(search, 'STUDY', path.parent)

    def save(file, value, *, exclusive=False):
        with Path(file).open('x' if exclusive else 'w') as stream:
            json.dump(value, stream)

    monkeypatch.setitem(sys.modules, 'common', SimpleNamespace(
        read=lambda file: json.loads(Path(file).read_text()),
        sha=lambda file: digest(Path(file).read_bytes()), save=save))
    out = path.parent / 'runs/mixed'
    out.mkdir(parents=True)
    cfg.logging.output_dir = str(out)
    cfg.evolve.generations = 24
    identity = {'golden': 'synthetic; no engine'}
    for name in ('protocol.json', 'release.json'):
        (path.parent / name).write_text('{}\n')
    OmegaConf.save(cfg, out / 'config.yaml')
    (out / 'determinism.json').write_text(json.dumps(identity))
    curves = [{'gen': g, 'evals': 320 * (g + 1), 'recheck_k': 64,
               'pop_invalid': 0., 'pop_mismatch': 0., 'recheck_invalid': 0.,
               'fitness': -1., 'mean_fitness': -2., 'pop_guard': .125,
               **({'valid': -1.} if g in (0, 4, 8, 12, 16, 20, 23) else {})} for g in range(24)]
    lineage = [{'event': 'founders', 'ids': list(range(32)), 'copies': []}] + [
        {'gen': g, 'children': [{}] * 224, 'seeds': list(range(8)),
         'recheck': {'seeds': list(range(8, 16)), 'ids': list(range(64))}} for g in range(24)]
    for name, rows in [('curves.jsonl', curves[:8]), ('lineage.jsonl', lineage[:9])]:
        (out / name).write_text(''.join(json.dumps(row) + '\n' for row in rows))
    (out / 'clones.jsonl').write_text('')
    generator = torch.Generator().manual_seed(123)
    rng_before, global_before = generator.get_state().clone(), torch.get_rng_state().clone()
    before_table = table.numpy().tobytes()
    midpoint = {'generation': 8, 'evals': 2048, 'rc_lives': 4096, 'curves': curves[:8],
                'population': table, 'ids': torch.arange(32), 'generator': generator.get_state()}
    original_save = checkpoint.save
    with search.midpoint_installed(checkpoint, cfg, identity, layout) as tracker:
        checkpoint.save(out / 'checkpoint.pt', cfg=cfg, identity=identity, state=midpoint)
        assert tracker['captures'] == 1
        assert (out / 'checkpoint.pt').read_bytes() == (out / 'generation8/checkpoint.pt').read_bytes()
    assert checkpoint.save is original_save
    assert torch.equal(rng_before, generator.get_state()) and torch.equal(global_before, torch.get_rng_state())
    assert table.numpy().tobytes() == before_table
    final_table = table.clone()
    final_table[0, 0] += 1
    for name, rows in [('curves.jsonl', curves), ('lineage.jsonl', lineage)]:
        (out / name).write_text(''.join(json.dumps(row) + '\n' for row in rows))
    checkpoint.save(out / 'checkpoint.pt', cfg=cfg, identity=identity,
                    state={'generation': 24, 'evals': 6144, 'rc_lives': 12288, 'curves': curves,
                           'population': final_table, 'ids': torch.arange(32)})
    layout.save(final_table[0], out / 'best_genome.json')
    (out / 'population.json').write_text(json.dumps({'ids': list(range(32)),
        'genomes': [layout.to_dict(row) for row in final_table]}))
    final = {'generations': 24, 'evals': 7680, 'lives': 2, 'founders_sampled': 0,
             'top_best_rank': 0, 'invalid_lives': 0, 'mismatch_lives': 0, 'F': -1., 'guard_rate': .5}
    (out / 'results.jsonl').write_text(json.dumps(final) + '\n')
    (out / 'search_startup.json').write_text(json.dumps(
        {'identity': identity, 'matching': {'lives': 2}, 'startup_lives': 4,
         'protocol_sha256': digest((path.parent / 'protocol.json').read_bytes())}))
    return search, cfg, identity, out


def test_uninterrupted_midpoint_and_completion_counts(completed_native):
    search, cfg, identity, out = completed_native
    result = search.complete_search(cfg, 'mixed', identity)
    assert result['research_lives'] == 61558 and result['startup_lives'] == 4
    assert result['count_proof'] == {'selection': 61440, 'valid': 112, 'final': 6, 'growth_t42': 2,
                                   'native_evals': 7680, 'generations': 24,
                                   'children_per_generation': 224, 'midpoint_added_lives': 0}
    assert result['health']['pop_guard'] == [.125] * 24
    assert result['health']['final_guard_rate'] == .5
    assert len(result['output_pins']) == 12
    assert result['midpoint']['genome_file_sha256'] != digest((out / 'best_genome.json').read_bytes())
    assert result['midpoint']['log_prefix_pins']['lineage.jsonl']['bytes'] < (out / 'lineage.jsonl').stat().st_size




@pytest.mark.parametrize('kind', ['midpoint_genome', 'snapshot', 'midpoint_prefix', 'result_invalid', 'startup_count'])
def test_corrupted_midpoint_or_completed_result_refused(completed_native, kind):
    search, cfg, identity, out = completed_native
    if kind == 'midpoint_genome':
        path = out / 'generation8/best_genome.json'
        value = json.loads(path.read_text())
        value['params']['b'][0] += 1
    elif kind == 'snapshot':
        path = out / 'generation8/snapshot.json'
        value = json.loads(path.read_text())
        value['rank_zero_id'] += 1
    elif kind == 'midpoint_prefix':
        path = out / 'lineage.jsonl'
        path.write_text(' ' + path.read_text())
        with pytest.raises(ValueError):
            search.verify_midpoint(out, cfg, identity)
        return
    elif kind == 'startup_count':
        path = out / 'search_startup.json'
        value = json.loads(path.read_text())
        value['startup_lives'] = 2
    else:
        path = out / 'results.jsonl'
        value = json.loads(path.read_text())
        value['invalid_lives'] = 1
    path.write_text(json.dumps(value))
    with pytest.raises(ValueError):
        search.complete_search(cfg, 'mixed', identity)


def test_midpoint_wrapper_restores_after_error(completed_native):
    from src import checkpoint
    from src.genome import Layout

    search, cfg, identity, out = completed_native
    layout, _ = Layout.load(out / 'best_genome.json')
    original = checkpoint.save
    with pytest.raises(RuntimeError, match='synthetic'):
        with search.midpoint_installed(checkpoint, cfg, identity, layout):
            raise RuntimeError('synthetic interruption')
    assert checkpoint.save is original


def test_startup_receipt_callback_uses_only_checked_actual_identity():
    search = module('search')
    events = []
    capture = search.one_identity(lambda: events.append('identity') or {'checked': True},
                                 {'checked': True}, {}, {}, lambda base: events.append(base))
    capture()
    assert events == ['identity', {'checked': True}]
    with pytest.raises(ValueError):
        capture()
    assert len(events) == 2
    with pytest.raises(ValueError):
        search.one_identity(lambda: {}, {'checked': True}, {}, {}, lambda base: events.append(base))()
    assert len(events) == 2






