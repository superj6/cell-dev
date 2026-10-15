"""AO source-only preparation contracts. No dynamics, genetic draws or input copies."""
import ast
import importlib.util
import json
import os
from pathlib import Path
import subprocess
import sys

from omegaconf import OmegaConf

ROOT = Path(__file__).resolve().parents[3]
STUDY = ROOT / 'outputs/autonomous_retained_depth_20261015'
OLD = ROOT / 'outputs/autonomous_occlusion_acquisition_20261015'
PUBLIC = ROOT / 'results/occlusion_acquisition_20261015'
sys.path.insert(0, str(ROOT))


def functions(path):
    return {n.name: n for n in ast.parse(path.read_text()).body if isinstance(n, ast.FunctionDef)}


def load_source(name):
    spec = importlib.util.spec_from_file_location('ao_test_' + name, STUDY / (name + '.py'))
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def world_helper():
    namespace = {}
    node = functions(STUDY / 'prepare.py')['retained_worlds']
    exec(compile(ast.Module(body=[node], type_ignores=[]), '<retained_worlds>', 'exec'), namespace)
    return namespace['retained_worlds']


def test_default_is_inert():
    before = sorted(str(p.relative_to(STUDY)) for p in STUDY.rglob('*') if p.is_file())
    result = subprocess.run([str(ROOT / '.venv/bin/python'), str(STUDY / 'prepare.py')],
        env=dict(os.environ, PYTHONDONTWRITEBYTECODE='1'), cwd=ROOT, capture_output=True, text=True)
    assert result.returncode == 0 and not result.stderr
    assert json.loads(result.stdout) == {'status': 'source_only', 'research_lives': 138476, 'startup_lives': 12}
    assert before == sorted(str(p.relative_to(STUDY)) for p in STUDY.rglob('*') if p.is_file())


def test_public_configs_only_declared_differences(monkeypatch):
    from src.life import spec
    monkeypatch.setitem(sys.modules, 'population_loader', load_source('population_loader'))
    monkeypatch.setitem(sys.modules, 'selection', load_source('selection'))
    namespace = {'AN': PUBLIC, 'STUDY': STUDY}
    node = functions(STUDY / 'prepare.py')['search_config']
    exec(compile(ast.Module(body=[node], type_ignores=[]), '<search_config>', 'exec'), namespace)
    prior = json.loads((PUBLIC / 'protocol.json').read_text())
    worlds = world_helper()(prior, spec)
    selection = {name: worlds[name]['world'] for name in ('pool', 'persistent', 'blink80_20')}
    record = {'population_file': 'inputs/input_population.json', 'marker': 'synthetic metadata'}
    actual_configs = {}
    for arm, pattern in [('unchanged', ['pool', 'persistent', 'blink80_20', 'blink80_20'] * 2),
                         ('balanced', ['pool', 'persistent', 'pool', 'blink80_20'] * 2)]:
        cfg = namespace['search_config'](53232, record, arm, selection)
        assert cfg.seed == 53232 and cfg.threads == 2
        assert (cfg.evolve.mu, cfg.evolve.lam, cfg.evolve.generations, cfg.evolve.heldout_every) == (32, 224, 24, 4)
        assert (cfg.life.lives, cfg.evolve.recheck_lives, cfg.evolve.recheck_k) == (8, 8, 64)
        assert (cfg.life.valid_lives, cfg.life.final_lives, cfg.life.final_top) == (16, 2, 1)
        assert cfg.evolve.dup_rate == cfg.evolve.del_rate == 0 and not cfg.evolve.dup_split
        assert cfg.life.abi == 4 and cfg.life.T == 1024 and cfg.life.t_open == 0
        assert cfg.retention_selection.arm == arm and list(cfg.retention_selection.pattern) == pattern
        assert OmegaConf.to_container(cfg.retention_selection.worlds, resolve=True) == selection
        assert not cfg.clones.every and not cfg.clones.conditions and not cfg.life.size_curve
        actual = OmegaConf.to_container(cfg, resolve=True)
        old = OmegaConf.to_container(OmegaConf.load(PUBLIC / 'runs/acquisition/config.yaml'), resolve=True)
        for key in ('seed', 'population_start', 'retention_selection'):
            old[key] = actual[key]
        old['evolve']['generations'] = 24
        old['evolve']['seed_genome'] = actual['evolve']['seed_genome']
        old['logging']['output_dir'] = actual['logging']['output_dir']
        old['life']['control'] = 'retained_depth_AO'
        assert actual == old
        actual_configs[arm] = actual
    a, b = actual_configs.values()
    a['logging']['output_dir'] = b['logging']['output_dir']
    a['retention_selection']['arm'] = b['retention_selection']['arm']
    a['retention_selection']['pattern'] = b['retention_selection']['pattern']
    assert a == b


def test_worlds_are_exact_prior_development_worlds():
    from src.life import spec
    prior = json.loads((PUBLIC / 'protocol.json').read_text())
    worlds = world_helper()(prior, spec)
    assert worlds == prior['worlds']
    assert list(worlds) == ['pool', 'persistent', 'blink80_5', 'blink80_20', 'turn100_blink80_20']
    for name, item in worlds.items():
        abi = spec.V3 if name in ('pool', 'persistent') else spec.V4
        assert item['abi'] == abi.version
        assert len(item['world_vector']) == abi.WORLD_SIZE
        assert len(item['ledger_columns']) == abi.LEDGER_SIZE
        assert item['world']['R_cap'] == 500
    for name in ('pool', 'persistent'):
        w = spec.World(**worlds[name]['world'])
        assert spec.V4.pack_world(w)[:66].tolist() == worlds[name]['world_vector']
        assert spec.V4.pack_world(w)[66:].tolist() == [0., 0., 0., 1.]


def test_schedule_matches_independent_production_hashes():
    path = Path(__file__).parent / 'audit_namespace.py'
    spec = importlib.util.spec_from_file_location('ao_namespace', path)
    audit = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(audit)
    records, values = audit.derive_native_ids()
    lookup = {(r['purpose'], r['index'], r['life']): r['seed'] for r in records}
    namespace = {'life_seed': lambda seed, purpose, index, life: lookup[(purpose, index, life)]}
    node = functions(STUDY / 'prepare.py')['planned_search_seeds']
    node.body = [n for n in node.body if not isinstance(n, ast.ImportFrom)]
    exec(compile(ast.Module(body=[node], type_ignores=[]), '<planned_search_seeds>', 'exec'), namespace)
    planned = namespace['planned_search_seeds'](53232)
    assert planned == [r['seed'] for r in records]
    assert len(planned) == len(values) == 500
    assert sum(r['purpose'] == 'gen' for r in records) == 384
    assert sum(r['purpose'] == 'valid' for r in records) == 112
    assert sum(r['purpose'] == 'final' for r in records) == 4
    assert 24 * (256 * 8 + 64 * 8) + 7 * 16 + 6 == 61558
    assert 2 * 61558 + 6 * 5 * 512 + 12 == 138488


def test_public_evidence_contract_without_loading_genomes():
    for name in ('runs/acquisition/config.yaml', 'runs/acquisition/checkpoint.pt',
                 'runs/acquisition/population.json', 'runs/acquisition/best_genome.json',
                 'inputs/startup_identity.json', 'inputs/visibility_truth.json',
                 'inputs/persistent_protocol.json', 'inputs/AM_current_start.json'):
        assert (PUBLIC / name).is_file()
    prior = json.loads((PUBLIC / 'terminal_review/native/complete_native_audit.json').read_text())
    assert prior['status'] == 'passed'
    run = prior['runs']['acquisition']
    assert run['all_32_final_rows_bound'] and run['genetic_replay']['raw_population_replay_bitwise']
    assert json.loads((PUBLIC / 'analysis_result/summary.json').read_text())['status'] == 'complete'


def test_watchdog_lifecycle_is_unchanged():
    old, new = functions(OLD / 'monitor.py'), functions(STUDY / 'monitor.py')
    assert old.keys() == new.keys()
    for name in old.keys() - {'main'}:
        assert ast.dump(old[name], include_attributes=False) == ast.dump(new[name], include_attributes=False)
    before = (OLD / 'common.py').read_text()
    expected = before.replace('"acquisition", "confirmation"', '"unchanged", "balanced", "confirmation"')
    assert expected == (STUDY / 'common.py').read_text()
