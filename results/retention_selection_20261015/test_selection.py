"""Pure AL adapter and import checks; engine execution is forbidden in this suite."""
from __future__ import annotations

import copy
import hashlib
import importlib.util
import json
import sys
from dataclasses import asdict, replace
from pathlib import Path
from types import SimpleNamespace

import pytest

STUDY = Path(__file__).resolve().parent
ROOT = STUDY.parents[1]
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(STUDY))


def module(name):
    found = importlib.util.spec_from_file_location('AL_test_' + name, STUDY / (name + '.py'))
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
    cfg = OmegaConf.load(ROOT / 'results/exploratory_reserve_replication_20261014/runs/control/config.yaml')
    cfg.life.lives = 4
    cfg.life.T_choices = None
    cfg.seed = 0
    ev = evaluate.LifeEvaluator(cfg, SimpleNamespace(abi=spec.V3))
    persistent = ev.world()
    pool = replace(persistent, d0=.5, d_min=.25, sigma=.4, lam_s=4., v_t=.1, tau_turn=20.)
    worlds = {'pool': asdict(pool), 'persistent': asdict(persistent)}
    monkeypatch.setattr(evaluate, 'life_seed', lambda seed, purpose, g, i: (purpose, g, i))
    return evaluate.LifeEvaluator, ev, worlds


@pytest.mark.parametrize('arm', ('persistent_control', 'balanced_mixture'))
def test_native_draw_prefix_recheck_and_exact_counts(evaluator, arm):
    from src.evolve import recheck_draw

    cls, ev, worlds = evaluator
    adapter = module('selection')
    configured = adapter.selection_identity(arm, worlds)
    ev.cfg.retention_selection = configured
    old = cls.draw
    baseline = ev.draw('gen', 0, lives=8)
    with adapter.installed(cls, configured):
        for g in range(4):
            first, full = ev.draw('gen', g), ev.draw('gen', g, lives=8)
            second = recheck_draw(ev, g, 4, 4)
            assert first.seeds == full.seeds[:4]
            assert first.worlds == full.worlds[:4]
            assert second.seeds == full.seeds[4:] and second.worlds == full.worlds[4:]
            assert first.n == second.n == 4 and full.n == 8
            assert full.seeds == tuple(('gen', g, i) for i in range(8))
            labels = ['pool' if asdict(w) == worlds['pool'] else 'persistent' for w in full.worlds]
            assert labels == (['pool', 'persistent'] * 4 if arm == 'balanced_mixture' else ['persistent'] * 8)
            assert all(asdict(w) == worlds[name] for w, name in zip(full.worlds, labels))
    assert cls.draw is old
    assert ev.draw('gen', 0, lives=8) == baseline


@pytest.mark.parametrize('purpose,lives,T', [('valid', 16, None), ('final', 2, None), ('final', 2, 512)])
def test_diagnostics_unchanged_and_restore_after_failure(evaluator, purpose, lives, T):
    cls, ev, worlds = evaluator
    adapter = module('selection')
    configured = adapter.selection_identity('balanced_mixture', worlds)
    ev.cfg.retention_selection = configured
    original = cls.draw
    expected = ev.draw(purpose, 0, lives=lives, T=T)
    with pytest.raises(RuntimeError, match='synthetic'):
        with adapter.installed(cls, configured):
            assert ev.draw(purpose, 0, lives=lives, T=T) == expected
            raise RuntimeError('synthetic failure')
    assert cls.draw is original


@pytest.mark.parametrize('kwargs', [{'lives': 3}, {'lives': 6}, {'T': 512}, {'overrides': []}, {'envelope': True}])
def test_wrong_selection_draw_contract_rejected(evaluator, kwargs):
    cls, ev, worlds = evaluator
    adapter = module('selection')
    configured = adapter.selection_identity('balanced_mixture', worlds)
    ev.cfg.retention_selection = configured
    with adapter.installed(cls, configured), pytest.raises(ValueError):
        ev.draw('gen', 0, **kwargs)


def test_changed_source_world_config_and_identity_rejected(evaluator):
    from src import checkpoint

    cls, ev, worlds = evaluator
    adapter = module('selection')
    configured = adapter.selection_identity('balanced_mixture', worlds)
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

    cfg = OmegaConf.load(ROOT / 'results/exploratory_reserve_replication_20261014/runs/control/config.yaml')
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
    old = ROOT / 'outputs/autonomous_population_depth_20261015/population_loader.py'
    assert (STUDY / 'population_loader.py').read_bytes() == old.read_bytes()


@pytest.fixture
def completed_native(population, monkeypatch):
    import torch
    from omegaconf import OmegaConf

    from src import checkpoint

    path, layout, table, _, cfg = population
    search = module('search')
    monkeypatch.setattr(search, 'STUDY', path.parent)
    out = path.parent / 'runs/persistent_control'
    out.mkdir(parents=True)
    cfg.logging.output_dir = str(out)
    identity = {'golden': 'synthetic; no engine'}
    for name in ('protocol.json', 'release.json'):
        (path.parent / name).write_text('{}\n')
    OmegaConf.save(cfg, out / 'config.yaml')
    (out / 'determinism.json').write_text(json.dumps(identity))
    curves = [{'gen': g, 'evals': 320 * (g + 1), 'recheck_k': 64,
               'pop_invalid': 0., 'pop_mismatch': 0., 'recheck_invalid': 0.,
               'fitness': -1., 'mean_fitness': -2., 'pop_guard': .125,
               **({'valid': -1.} if g in (0, 3) else {})} for g in range(4)]
    lineage = [{'event': 'founders', 'ids': list(range(32)), 'copies': []}] + [
        {'gen': g, 'children': [{}] * 224, 'seeds': list(range(4)),
         'recheck': {'seeds': list(range(4, 8)), 'ids': list(range(64))}} for g in range(4)]
    for name, rows in [('curves.jsonl', curves), ('lineage.jsonl', lineage)]:
        (out / name).write_text(''.join(json.dumps(row) + '\n' for row in rows))
    checkpoint.save(out / 'checkpoint.pt', cfg=cfg, identity=identity,
                    state={'generation': 4, 'evals': 1024, 'rc_lives': 1024,
                           'population': table, 'ids': torch.arange(32)})
    layout.save(table[0], out / 'best_genome.json')
    (out / 'population.json').write_text(json.dumps({'ids': list(range(32)),
        'genomes': [layout.to_dict(row) for row in table]}))
    final = {'generations': 4, 'evals': 1280, 'lives': 2, 'founders_sampled': 0,
             'top_best_rank': 0, 'invalid_lives': 0, 'mismatch_lives': 0, 'F': -1., 'guard_rate': .5}
    (out / 'results.jsonl').write_text(json.dumps(final) + '\n')
    return search, cfg, identity, out


def test_completion_counts_pins_and_guarded_lives_retained(completed_native):
    search, cfg, identity, _ = completed_native
    result = search.complete_search(cfg, 'persistent_control', identity)
    assert result['research_lives'] == 5158 and result['startup_lives'] == 2
    assert result['count_proof']['selection'] == 5120
    assert result['health']['pop_guard'] == [.125] * 4
    assert result['health']['final_guard_rate'] == .5
    assert len(result['output_pins']) == 8


@pytest.mark.parametrize('kind', ['result_invalid', 'truncated_log', 'wrong_endpoint'])
def test_incomplete_or_corrupted_native_result_refused(completed_native, kind):
    search, cfg, identity, out = completed_native
    if kind == 'result_invalid':
        path = out / 'results.jsonl'
        value = json.loads(path.read_text())
        value['invalid_lives'] = 1
        path.write_text(json.dumps(value) + '\n')
    elif kind == 'truncated_log':
        path = out / 'lineage.jsonl'
        path.write_bytes(path.read_bytes()[:-1])
    else:
        from src.genome import Layout
        layout, best = Layout.load(out / 'best_genome.json')
        best[0] += 1
        layout.save(best, out / 'best_genome.json')
    with pytest.raises(ValueError):
        search.complete_search(cfg, 'persistent_control', identity)
