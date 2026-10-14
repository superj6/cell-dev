"""Pure incomplete-archive safeguards; deliberately opaque checkpoint/lineage bytes are never interpreted."""
import importlib.util
import json
from pathlib import Path

import pytest

LOADER = importlib.util.spec_from_file_location('P_incomplete_archive', Path(__file__).with_name('archive_incomplete.py'))
m = importlib.util.module_from_spec(LOADER)
LOADER.loader.exec_module(m)


def fixture(tmp_path):
    study, public = tmp_path / 'work', tmp_path / 'public'
    study.mkdir()
    public.mkdir()
    for name in ('run_budgeted.py', 'measure.py', 'prepare.py', 'test_prepared.py', 'test_monitor.py',
                 'seed_audit.json', 'initialization.json', 'analyze.py', 'test_analyze.py'):
        (study / name).write_text('opaque ' + name)
    protocol = {'planned_genome_lives': 37548, 'prepare_sha256': m.sha(study / 'prepare.py'),
                'source_identity': {}, 'reference_sources': {}, 'template_pins': {}}
    m.write(study / 'protocol.json', protocol)
    ready = {'protocol_sha256': m.sha(study / 'protocol.json'), 'runner_sha256': m.sha(study / 'run_budgeted.py'),
             'measurement_sha256': m.sha(study / 'measure.py'), 'helpers': {}, 'dependencies': {}}
    m.write(study / 'ready.json', ready)
    budget = {'status': 'incomplete', 'running': {}, 'queued': [], 'exit_code': 1, 'cpu_seconds': 14385.5,
              'cap_cpu_seconds': 14400, 'reason': 'cpu_budget_exhausted', 'ready': ready}
    m.write(study / 'budget.json', budget)
    run = study / 'runs/s52091'
    run.mkdir(parents=True)
    (run / 'checkpoint.pt').write_bytes(b'opaque, non-deserializable partial checkpoint\x00')
    (run / 'lineage.jsonl').write_bytes(b'deliberately not JSON: no partial fitness parser should run')
    (public / 'README.md').write_text('original preparation')
    (public / 'protocol.json').write_bytes((study / 'protocol.json').read_bytes())
    original = {'status': 'prepared_not_released', 'artifacts': {
        name: {'sha256': m.sha(public / name), 'bytes': (public / name).stat().st_size}
        for name in ('README.md', 'protocol.json')}}
    m.write(public / 'provenance.json', original)
    bundle = public / 'offline_analysis_preparation'
    bundle.mkdir()
    for name in ('analyze.py', 'test_analyze.py'):
        (bundle / name).write_bytes((study / name).read_bytes())
    m.write(bundle / 'provenance.json', {'status': 'offline_analysis_preparation', 'artifacts': {
        name: {'sha256': m.sha(bundle / name), 'bytes': (bundle / name).stat().st_size}
        for name in ('analyze.py', 'test_analyze.py')}})
    return study, public, budget


def test_terminal_incomplete_preserves_opaque_raw_bytes_and_both_preparations(tmp_path):
    study, public, _ = fixture(tmp_path)
    old = (public / 'provenance.json').read_bytes()
    bundle_before = {str(p.relative_to(public)): p.read_bytes()
                     for p in m.clean_files(public / 'offline_analysis_preparation')}
    result = m.archive(study, public, tmp_path)
    assert result['status'] == 'incomplete' and result['confirmation'] is None
    assert result['completed_genome_lives'] is None and not result['partial_endpoints_compared']
    assert (public / 'prelaunch/provenance.json').read_bytes() == old
    assert (public / 'prelaunch/README.md').read_text() == 'original preparation'
    for name, content in bundle_before.items():
        assert (public / name).read_bytes() == content
    for name in ('checkpoint.pt', 'lineage.jsonl'):
        assert (public / 'runs/s52091' / name).read_bytes() == (study / 'runs/s52091' / name).read_bytes()
    manifest = m.read(public / 'provenance.json')
    assert manifest['status'] == 'incomplete' and manifest['no_confirmed_outcome']
    m.verify_manifest(public, manifest)
    with pytest.raises(ValueError, match='untouched original public preparation'):
        m.archive(study, public, tmp_path)


@pytest.mark.parametrize('status', ['running', 'waiting_for_workers', 'complete', 'not_started'])
def test_active_or_complete_state_rejected_before_any_outcome_or_preparation_read(tmp_path, status):
    study = tmp_path / 'work'
    study.mkdir()
    m.write(study / 'budget.json', {'status': status})
    with pytest.raises(ValueError, match='terminal incomplete'):
        m.archive(study, tmp_path / 'nonexistent_target', tmp_path)


@pytest.mark.parametrize('change', [{'running': {'123': 'search'}}, {'queued': ['confirmation']},
                                   {'exit_code': 0}, {'cap_cpu_seconds': 15000}, {'cpu_seconds': float('inf')}])
def test_invalid_terminal_resource_record_fails_closed(tmp_path, change):
    study, public, budget = fixture(tmp_path)
    budget.update(change)
    (study / 'budget.json').write_text(json.dumps(budget))
    with pytest.raises(ValueError):
        m.archive(study, public, tmp_path)
    assert not (public / 'prelaunch').exists()


@pytest.mark.parametrize('relative', ['README.md', 'offline_analysis_preparation/analyze.py'])
def test_changed_preparation_rejected_before_archival_writes(tmp_path, relative):
    study, public, _ = fixture(tmp_path)
    (public / relative).write_text('changed')
    with pytest.raises(ValueError, match='frozen preparation differs'):
        m.archive(study, public, tmp_path)
    assert not (public / 'prelaunch').exists()


def test_changed_released_source_rejected(tmp_path):
    study, public, _ = fixture(tmp_path)
    (study / 'measure.py').write_text('changed')
    with pytest.raises(ValueError, match='release source changed'):
        m.archive(study, public, tmp_path)
    assert not (public / 'prelaunch').exists()


def test_monitor_failure_is_preserved_without_converting_to_budget_exhaustion(tmp_path):
    study, public, budget = fixture(tmp_path)
    budget.update(status='monitor_failed', reason=None, error='RuntimeError')
    m.write(study / 'budget.json', budget)
    result = m.archive(study, public, tmp_path)
    assert result['resource_status'] == 'monitor_failed'
    assert result['reason'] is None and result['error'] == 'RuntimeError'
    assert result['confirmation'] is None
