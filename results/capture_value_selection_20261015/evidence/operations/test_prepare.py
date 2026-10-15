"""Focused AM configuration and namespace checks; no engines, bodies or genetic draws."""
import ast
import importlib.util
import json
import os
from pathlib import Path
import subprocess
import sys

from omegaconf import OmegaConf

ROOT = Path(__file__).resolve().parents[3]
STUDY = ROOT / 'outputs/autonomous_capture_value_selection_20261015'
OLD = ROOT / 'outputs/autonomous_retention_selection_20261015'


def functions(path):
    return {n.name: n for n in ast.parse(path.read_text()).body if isinstance(n, ast.FunctionDef)}


def load_source(name):
    spec = importlib.util.spec_from_file_location('am_test_' + name, STUDY / (name + '.py'))
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def test_default_is_inert():
    before = sorted(str(p.relative_to(STUDY)) for p in STUDY.rglob('*') if p.is_file())
    result = subprocess.run([str(ROOT / '.venv/bin/python'), str(STUDY / 'prepare.py')],
        env=dict(os.environ, PYTHONDONTWRITEBYTECODE='1'), cwd=ROOT, capture_output=True, text=True)
    assert result.returncode == 0 and not result.stderr
    assert json.loads(result.stdout) == {'status': 'source_only', 'research_lives': 28748, 'startup_lives': 8}
    assert before == sorted(str(p.relative_to(STUDY)) for p in STUDY.rglob('*') if p.is_file())


def test_actual_template_yields_only_declared_config_differences(monkeypatch):
    # Read a committed config and world metadata only; no genotype data is loaded.
    monkeypatch.setitem(sys.modules, 'population_loader', load_source('population_loader'))
    monkeypatch.setitem(sys.modules, 'selection', load_source('selection'))
    namespace = {'AL': ROOT / 'results/retention_selection_20261015', 'STUDY': STUDY}
    node = functions(STUDY / 'prepare.py')['search_config']
    exec(compile(ast.Module(body=[node], type_ignores=[]), '<search_config>', 'exec'), namespace)
    worlds = json.loads((OLD / 'protocol.json').read_text())['selection_worlds']
    record = {'population_file': 'inputs/input_population.json', 'marker': 'synthetic metadata'}
    configs = [namespace['search_config'](53230, record, arm, worlds) for arm in ('current_value', 'high_value')]
    for cfg, arm, price in zip(configs, ('current_value', 'high_value'), (500., 2000.), strict=True):
        assert cfg.seed == 53230 and cfg.threads == 2
        assert (cfg.evolve.mu, cfg.evolve.lam, cfg.evolve.generations) == (32, 224, 4)
        assert (cfg.life.lives, cfg.evolve.recheck_lives, cfg.evolve.recheck_k) == (8, 8, 64)
        assert (cfg.life.valid_lives, cfg.life.final_lives, cfg.life.final_top) == (16, 2, 1)
        assert cfg.evolve.dup_rate == cfg.evolve.del_rate == 0 and not cfg.evolve.dup_split
        assert cfg.life.abi == 3 and cfg.life.T == 1024 and cfg.life.t_open == 0
        assert cfg.retention_selection.selection_capture_value == price
        assert cfg.retention_selection.arm == arm
        assert OmegaConf.to_container(cfg.retention_selection.worlds, resolve=True) == worlds
        assert all(w['R_cap'] == 500 for w in worlds.values())
        assert not cfg.clones.every and not cfg.clones.conditions and not cfg.life.size_curve
    plain = [OmegaConf.to_container(cfg, resolve=True) for cfg in configs]
    for cfg in plain:
        cfg['logging']['output_dir'] = '<arm>'
        cfg['retention_selection']['arm'] = '<arm>'
        cfg['retention_selection']['selection_capture_value'] = '<price>'
    assert plain[0] == plain[1]


def test_schedule_matches_independent_production_hash_reconstruction():
    path = Path(__file__).parent / 'audit_namespace.py'
    spec = importlib.util.spec_from_file_location('am_namespace', path)
    audit = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(audit)
    records, values = audit.derive_native_ids()
    lookup = {(r['purpose'], r['index'], r['life']): r['seed'] for r in records}
    namespace = {'life_seed': lambda seed, purpose, index, life: lookup[(purpose, index, life)]}
    node = functions(STUDY / 'prepare.py')['planned_search_seeds']
    node.body = [n for n in node.body if not isinstance(n, ast.ImportFrom)]
    exec(compile(ast.Module(body=[node], type_ignores=[]), '<planned_search_seeds>', 'exec'), namespace)
    planned = namespace['planned_search_seeds'](53230)
    assert planned == [r['seed'] for r in records]
    assert len(planned) == len(values) == 100
    assert sum(r['purpose'] == 'gen' for r in records) == 64
    assert sum(r['purpose'] == 'valid' for r in records) == 32
    assert sum(r['purpose'] == 'final' for r in records) == 4


def test_prior_evidence_paths_are_real_and_have_current_schema():
    base = ROOT / 'results/retention_selection_20261015'
    for name in ('runs/balanced_mixture/config.yaml', 'runs/balanced_mixture/checkpoint.pt',
                 'runs/balanced_mixture/population.json', 'runs/balanced_mixture/best_genome.json',
                 'inputs/AI_control_start.json', 'inputs/startup_identity.json', 'inputs/visibility_truth.json',
                 'inputs/persistent_protocol.json'):
        assert (base / name).is_file()
    prior = json.loads((base / 'terminal_review/native/complete_native_audit.json').read_text())
    assert prior['status'] == 'passed'
    run = prior['runs']['balanced_mixture']
    assert run['all_32_final_rows_bound'] and run['genetic_replay']['raw_population_replay_bitwise']
    assert json.loads((base / 'analysis_result/summary.json').read_text())['status'] == 'complete'


def test_watchdog_lifecycle_is_unchanged():
    old, new = functions(OLD / 'monitor.py'), functions(STUDY / 'monitor.py')
    assert old.keys() == new.keys()
    for name in old.keys() - {'main'}:
        assert ast.dump(old[name], include_attributes=False) == ast.dump(new[name], include_attributes=False)
    before = (OLD / 'common.py').read_text()
    expected = before.replace('"persistent_control", "balanced_mixture", "confirmation"',
                              '"current_value", "high_value", "confirmation"')
    assert expected == (STUDY / 'common.py').read_text()
