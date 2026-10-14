"""Pure and mocked tests for S initialization, paired policy comparison, and pre-search reference freezing."""
import hashlib
import importlib.util
import json
import os
import shutil
import sys
from pathlib import Path
from types import SimpleNamespace

import numpy as np
import pytest
import torch
from omegaconf import OmegaConf

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[1]
sys.path.insert(0, str(ROOT))


def module(name, path):
    loader = importlib.util.spec_from_file_location(name, path)
    result = importlib.util.module_from_spec(loader)
    sys.modules[name] = result
    loader.loader.exec_module(result)
    return result


def worker(monkeypatch, tmp_path):
    module('run_budgeted', HERE / 'run_budgeted.py')
    m = module('S_measure_test', HERE / 'measure.py')
    p = json.loads((HERE / 'protocol.json').read_text())
    monkeypatch.setattr(m, 'STUDY', tmp_path)
    monkeypatch.setattr(m, 'check_protocol', lambda: p)
    monkeypatch.setattr(m, 'check_ready', lambda: {'synthetic': True})
    monkeypatch.setenv('CELLDEV_SCORING_BUDGET_MONITOR_PID', str(os.getppid()))
    return m, p


def test_exact_p_initialization_and_only_registered_configuration_changes():
    from src.evolve import fill, setup
    from src.genome import Layout

    torch.set_num_threads(2)
    prep = module('S_prepare_test', HERE / 'prepare.py')
    protocol = json.loads((HERE / 'protocol.json').read_text())
    receipt = json.loads((HERE / 'initialization.json').read_text())
    previous_receipt = json.loads((HERE / 'inputs/P_preparation/initialization.json').read_text())
    assert protocol['planned_genome_lives'] == 37484 and receipt['simulated_lives'] == 0
    assert protocol['selection_genome_lives'] == 32768
    assert protocol['selection_T1024_equivalent_lives'] == 37888
    assert protocol['periodic_valid_genome_lives'] == 96
    for seed, old in zip((52091, 52092), (51089, 51090), strict=True):
        cfg = OmegaConf.load(HERE / f'configs/s{seed}.yaml')
        previous = OmegaConf.load(HERE / f'inputs/P_preparation/configs/s{seed}.yaml')
        assert prep.differences(OmegaConf.to_container(previous), OmegaConf.to_container(cfg)) == prep.ALLOWED
        assert cfg.evolve.generations == 8 and cfg.life.lives == 6 and cfg.evolve.recheck_lives == 8
        assert cfg.life.valid_lives == 16 and cfg.evolve.heldout_every == 4 and list(cfg.life.heldout) == []
        _, founder = Layout.load(HERE / f'inputs/founder_D{old}.json')
        _, layout, _, _ = setup(cfg)
        generator = torch.Generator().manual_seed(seed)
        before = hashlib.sha256(generator.get_state().numpy().tobytes()).hexdigest()
        operations = []
        raw = fill(founder[None], 32, layout, generator, cfg.evolve, ops=operations).numpy()
        saved = np.load(HERE / receipt['runs'][str(seed)]['population_file'], allow_pickle=False)
        previous_raw = np.load(HERE / 'inputs/P_preparation' / receipt['runs'][str(seed)]['population_file'])
        assert raw.tobytes() == saved.tobytes() == previous_raw.tobytes()
        assert receipt['runs'][str(seed)] == previous_receipt['runs'][str(seed)]
        assert receipt['runs'][str(seed)]['generator_before_sha256'] == before
        assert receipt['runs'][str(seed)]['generator_after_sha256'] == hashlib.sha256(
            generator.get_state().numpy().tobytes()).hexdigest()
        assert [item['ops'] for item in receipt['runs'][str(seed)]['copies']] == operations
        assert len(operations) == 31 and sum(len(item['mut']) for item in operations) == 62
        assert 2 * sum(protocol['selection_durations'][str(seed)]) == 18944


def test_all_s_seeds_and_only_intentional_p_overlap():
    prep = module('S_seed_test', HERE / 'prepare.py')
    helper = prep.seed_helpers()
    audit = json.loads((HERE / 'seed_audit.json').read_text())
    generated = {str(seed): prep.run_life_seeds(seed) for seed in (52091, 52092)}
    assert generated == audit['run_life_seeds']
    own = {value for values in generated.values() for value in values}
    p = {value for seed in (52091, 52092) for value in helper.run_life_seeds(seed)}
    old = helper.pilot_life_seeds()
    old.update(value for seed in (51089, 51090, 51891, 51892) for value in helper.run_life_seeds(seed))
    assert len(own) == 328 and len(own & p) == 184 and len(own - p) == 144
    assert sorted(own & p) == audit['intentional_shared_P_ids']
    assert not own & old
    assert audit['confirm_seeds'] == list(range(52_050_000, 52_050_256))
    assert not set(audit['confirm_seeds']) & (own | p | old)


def reference_fixture(monkeypatch, tmp_path, status='complete'):
    from src import checkpoint
    from src.genome import Layout
    from src.life import build

    m, p = worker(monkeypatch, tmp_path / 'S')
    m.STUDY.mkdir()
    (m.STUDY / 'inputs').mkdir()
    p['P_study'] = 'P'
    monkeypatch.setattr(m, 'ROOT', tmp_path)
    (m.STUDY / 'protocol.json').write_text(json.dumps(p))
    peer = tmp_path / 'P'
    peer.mkdir()
    budget = {'status': status, 'running': {}, 'queued': []}
    (peer / 'budget.json').write_text(json.dumps(budget))
    for name in ('protocol.json', 'run_budgeted.py', 'ready.json', 'initialization.json',
                 'seed_audit.json', 'search_health.json'):
        (peer / name).write_text('{}')
    p['P_pins'] = {name: m.sha(peer / name) for name in ('protocol.json', 'run_budgeted.py')}
    searches, checkpoints = {}, {}
    for seed, old in zip(m.RUNS, m.MAPPING.values(), strict=True):
        shutil.copyfile(HERE / f'inputs/founder_D{old}.json', m.STUDY / f'inputs/founder_D{old}.json')
        layout, founder = Layout.load(HERE / f'inputs/founder_D{old}.json')
        founder[0] += .1
        folder = peer / f'runs/s{seed}'
        folder.mkdir(parents=True)
        layout.save(founder, folder / 'best_genome.json')
        for name in ('checkpoint.pt', 'lineage.jsonl', 'curves.jsonl'):
            (folder / name).write_text(name)
        for name in (f'configs/s{seed}.yaml', f'initialization/s{seed}.npy'):
            file = peer / name
            file.parent.mkdir(exist_ok=True)
            file.write_text(name)
        checkpoints[str(seed)] = {'logs': {name: {'sha256': m.sha(folder / name),
                                                 'bytes': (folder / name).stat().st_size}
                                          for name in ('lineage.jsonl', 'curves.jsonl')}}
        searches[str(seed)] = {'checkpoint_sha256': m.sha(folder / 'checkpoint.pt'),
                              'raw_genome_sha256': hashlib.sha256(founder.numpy().tobytes()).hexdigest()}
    summary = {'status': 'complete', 'completed_genome_lives': 37548, 'searches': searches, 'resources': budget}
    calls = []

    def audit(path):
        calls.append(path)
        return summary, {}

    monkeypatch.setattr(m, 'load_p_auditor', lambda protocol: SimpleNamespace(analyze=audit))
    monkeypatch.setattr(checkpoint, 'load', lambda path: checkpoints[path.parent.name.removeprefix('s')])
    monkeypatch.setattr(checkpoint, 'numerical_identity', lambda: pytest.fail('golden simulation in reference phase'))
    monkeypatch.setattr(build, 'run', lambda *a, **k: pytest.fail('simulated a life'))
    monkeypatch.setattr(m, 'check_references', lambda protocol: {'mock': True})
    return m, p, peer, summary, calls


def test_reference_phase_freezes_both_p_endpoints_atomically_without_lives(monkeypatch, tmp_path):
    m, p, peer, _, calls = reference_fixture(monkeypatch, tmp_path)
    m.freeze_references()
    report = json.loads((m.STUDY / 'references/report.json').read_text())
    assert report['status'] == 'complete' and report['simulated_lives'] == 0
    assert report['runs'] == [52091, 52092] and report['mapping'] == m.MAPPING
    assert report['labels'] == m.LABELS[:4] and calls == [peer]
    assert not (m.STUDY / 'references.pending').exists()
    assert np.load(m.STUDY / 'references/genotypes.npy', allow_pickle=False).shape == (4, 875)
    for relative, expected in report['files'].items():
        assert m.sha(m.STUDY / 'references' / relative) == expected
    with pytest.raises(ValueError, match='cannot resume'):
        m.freeze_references()


def test_incomplete_p_gate_precedes_audit_or_reference_writes(monkeypatch, tmp_path):
    m, _, _, _, calls = reference_fixture(monkeypatch, tmp_path, status='running')
    with pytest.raises(ValueError, match='all confirmation must be complete'):
        m.freeze_references()
    assert calls == [] and not (m.STUDY / 'references.pending').exists()


@pytest.mark.parametrize('kind', ['audit_incomplete', 'checkpoint', 'genome', 'log', 'ready'])
def test_reference_audit_changes_fail_before_complete_receipt(monkeypatch, tmp_path, kind):
    m, _, _, summary, _ = reference_fixture(monkeypatch, tmp_path)
    if kind == 'audit_incomplete':
        summary['completed_genome_lives'] = 1
    elif kind == 'checkpoint':
        summary['searches']['52091']['checkpoint_sha256'] = 'wrong'
    elif kind == 'genome':
        summary['searches']['52091']['raw_genome_sha256'] = 'wrong'
    elif kind == 'log':
        from src import checkpoint
        monkeypatch.setattr(checkpoint, 'load',
                            lambda path: {'logs': {'lineage.jsonl': {'sha256': 'wrong', 'bytes': 1}}})
    else:
        values = iter([{'synthetic': True}, {'changed': True}])
        monkeypatch.setattr(m, 'check_ready', lambda: next(values))
    with pytest.raises(ValueError):
        m.freeze_references()
    assert not (m.STUDY / 'references').exists()


def confirmation_fixture(monkeypatch, tmp_path, generation=8, invalid=0):
    from src import checkpoint
    from src.genome import Layout
    from src.life import build

    m, p = worker(monkeypatch, tmp_path)
    (tmp_path / 'protocol.json').write_text(json.dumps(p))
    (tmp_path / 'references').mkdir()
    layout, founder = Layout.load(HERE / 'inputs/founder_D51089.json')
    genomes = []
    for i, name in enumerate(p['reference_files']):
        g = founder.clone()
        g[0] += i * .1
        genomes.append(g.numpy())
        layout.save(g, tmp_path / 'references' / name)
    np.save(tmp_path / 'references/genotypes.npy', np.stack(genomes))
    states = {}
    for i, seed in enumerate(m.RUNS):
        folder = tmp_path / f'runs/s{seed}'
        folder.mkdir(parents=True)
        endpoint = founder.clone()
        endpoint[0] += (i + 1) * .125
        layout.save(endpoint, folder / 'best_genome.json')
        (folder / 'checkpoint.pt').write_text('synthetic checkpoint')
        states[str(seed)] = {'state': {'generation': generation, 'population': endpoint[None], 'curves': [
            {'gen': g, 'pop_invalid': invalid, 'pop_mismatch': 0, 'recheck_invalid': 0} for g in range(generation)]}}
    monkeypatch.setattr(m, 'check_references', lambda *args: {'synthetic': True})
    monkeypatch.setattr(checkpoint, 'load', lambda path: states[path.parent.name.removeprefix('s')])
    monkeypatch.setattr(checkpoint, 'validate', lambda *args: None)
    monkeypatch.setattr(checkpoint, 'numerical_identity', lambda: p['expected_numerical_identity'])
    monkeypatch.setattr(build, 'run', lambda *args, **kwargs: pytest.fail('simulated a life'))
    return m, p


def test_all_six_confirmation_roles_frozen_before_any_score_and_both_signs_retained(monkeypatch, tmp_path):
    from scripts import taskvar_confirm

    m, p = confirmation_fixture(monkeypatch, tmp_path)
    calls = []

    def score(out, index, genomes, world, seeds, evaluator, threads):
        manifest = json.loads((tmp_path / 'confirmation/manifest.json').read_text())
        assert manifest['labels'] == m.LABELS and manifest['seed_block'] == 105
        assert (tmp_path / 'confirmation/genotypes.npz').exists()
        assert genomes.shape == (6, 875) and threads == 2
        assert seeds == list(range(52_050_000, 52_050_256))
        assert world.t_fork == world.t_open == world.fork_flags == 0
        calls.append((int(world.T), index))
        row = {key: np.zeros(256) for key in taskvar_confirm.COLS}
        row['F'][:] = (1, 2, 3, 5, 4, 4)[index]
        row['F_kernel'][:] = row['F']
        row['income'][:] = 10000 + row['F'] * world.T
        row['cost'][:] = 10000
        row['window'][:], row['t_end'][:] = world.T, world.T
        out.mkdir(parents=True, exist_ok=True)
        taskvar_confirm.atomic_npz(out / f'row_{index:04d}.npz', **row)
        return row

    monkeypatch.setattr(taskvar_confirm, 'score_row', score)
    m.confirm_endpoints()
    assert calls == [(t, i) for t in (768, 1024, 1536) for i in range(6)]
    report = json.loads((tmp_path / 'confirmation/report.json').read_text())
    assert report['status'] == 'complete'
    assert report['planned_genome_lives'] == report['completed_genome_lives'] == report['genome_lives'] == 4608
    assert report['primary'][m.LABELS[4]]['mean'] == 1
    assert report['primary'][m.LABELS[5]]['mean'] == -1
    assert [report['secondary'][m.LABELS[i] + '__vs__' + m.LABELS[j]]['mean'] for i, j in m.SECONDARY] == [3, 2, 2, 3]
    with pytest.raises(ValueError, match='cannot restart'):
        m.confirm_endpoints()


@pytest.mark.parametrize('generation,invalid', [(7, 0), (8, 1)])
def test_incomplete_invalid_s_endpoint_never_reaches_scoring(monkeypatch, tmp_path, generation, invalid):
    from scripts import taskvar_confirm

    m, _ = confirmation_fixture(monkeypatch, tmp_path, generation, invalid)
    monkeypatch.setattr(taskvar_confirm, 'score_row', lambda *a, **k: pytest.fail('scored invalid endpoint'))
    with pytest.raises(ValueError, match='incomplete|invalid'):
        m.confirm_endpoints()
    assert not (tmp_path / 'confirmation/manifest.json').exists()


def test_duration_average_preserves_paired_covariance_and_negative_values(monkeypatch, tmp_path):
    m, _ = worker(monkeypatch, tmp_path)
    common = np.arange(256.)
    rows = {str(t): {0: {'F': common}, 1: {'F': common + offset}, 2: {'F': common - 1}}
            for t, offset in [(768, 1), (1024, 3), (1536, 2)]}
    assert np.array_equal(m.duration_mixture(rows, 1, 0), np.full(256, 2.))
    assert np.array_equal(m.duration_mixture(rows, 2, 0), np.full(256, -1.))
    with pytest.raises(ValueError, match='three registered'):
        m.duration_mixture({'1024': rows['1024']}, 1, 0)


@pytest.mark.parametrize('command', ['freeze_references', 'confirm_endpoints'])
def test_exact_parent_required_before_audit_or_golden_checks(monkeypatch, tmp_path, command):
    m, _ = worker(monkeypatch, tmp_path)
    monkeypatch.delenv('CELLDEV_SCORING_BUDGET_MONITOR_PID')
    monkeypatch.setattr(m, 'check_protocol', lambda: pytest.fail('pins before parent guard'))
    with pytest.raises(RuntimeError, match='exact budget monitor parent'):
        getattr(m, command)()


def test_missing_confirmation_row_cannot_make_complete_report(monkeypatch, tmp_path):
    from scripts import taskvar_confirm

    m, _ = confirmation_fixture(monkeypatch, tmp_path)
    monkeypatch.setattr(taskvar_confirm, 'score_row',
                        lambda *a, **k: (_ for _ in ()).throw(RuntimeError('row failure')))
    with pytest.raises(RuntimeError, match='row failure'):
        m.confirm_endpoints()
    assert not (tmp_path / 'confirmation/report.json').exists()
    assert json.loads((tmp_path / 'confirmation/manifest.json').read_text())['labels'] == m.LABELS
