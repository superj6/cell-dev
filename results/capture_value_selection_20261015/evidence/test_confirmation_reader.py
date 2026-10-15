"""Focused AM changes: unchanged arithmetic, 4 roles, capture criteria and inclusive caps."""
import ast
import copy
import hashlib
import importlib.util
import json
import sys
from pathlib import Path

import numpy as np
import pytest

ROOT = next(p for p in Path(__file__).resolve().parents if (p / 'src/life/spec.py').is_file())
STUDY = ROOT / 'outputs/autonomous_capture_value_selection_20261015'
AL = ROOT / 'outputs/autonomous_retention_selection_20261015'


def load(name, path):
    spec = importlib.util.spec_from_file_location(name, path)
    result = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(result)
    return result


M = load('am_reader', STUDY / 'analyze.py')


def functions(path):
    return {n.name: n for n in ast.parse(path.read_text()).body if isinstance(n, ast.FunctionDef)}


def test_physics_accountant_truth_and_genetic_operations_unchanged():
    for filename, names in (
            ('analyze.py', ('identical', 'stats', 'prices', 'physical_costs', 'validate_row', 'reconstruct', 'verify_startup')),
            ('measure.py', ('parent_check', 'validate_search_state', 'check_visibility_truth'))):
        old, new = functions(AL / filename), functions(STUDY / filename)
        assert all(ast.dump(old[name]) == ast.dump(new[name]) for name in names)
    assert (AL / 'replay_ops.py').read_bytes() == (STUDY / 'replay_ops.py').read_bytes()
    old = (AL / 'native_replay.py').read_text().replace('persistent_control', 'current_value').replace(
        'balanced_mixture', 'high_value').replace('AL_recorded_ops', 'AM_recorded_ops')
    assert old == (STUDY / 'native_replay.py').read_text()


def rows():
    fixture = load('retained_test_row', ROOT / 'outputs/cumulative_capability_20261015/design/test_retention_analyze.py')
    values, _ = M.reconstruct(*fixture.row(n=512))
    return {w: {r: copy.deepcopy(values) for r in M.ROLES} for w in M.WORLDS}


def flat_captures(data, value=10.):
    for world in M.WORLDS:
        for role in M.ROLES:
            data[world][role]['captures'][:] = value


def test_54_contrast_groups_14_retention_vectors_and_covariance():
    data = rows()
    noise = np.arange(512, dtype=float)
    data['persistent'][M.ROLES[3]]['captures'] += noise
    data['turn100_blink80_5'][M.ROLES[3]]['captures'] += noise + 2
    reports, arrays = M.contrasts(data)
    retention, extra = M.retention_diagnostics(data)
    assert len(reports) == 54 and len(retention) == 7
    assert len(arrays) == 4050 and len(extra) == 14
    assert len(set(arrays) | set(extra)) == 4064
    key = 'interaction__turn100_blink80_5_minus_persistent__high_value_final_minus_AL_mixture_start'
    np.testing.assert_array_equal(arrays[key + '__captures'], np.full(512, 2.))
    assert reports[key]['captures']['se'] == 0
    # Duplicated genomes are allowed and their fixed role comparisons remain present.
    key = 'within__pool__AL_mixture_start_minus_AI_control_start__captures'
    np.testing.assert_array_equal(arrays[key], np.zeros(512))


def test_joint_primary_requires_both_worlds_and_is_not_own_start_gain():
    data = rows()
    flat_captures(data)
    for world in ('pool', 'persistent'):
        data[world][M.ROLES[2]]['captures'][:] = 5
        data[world][M.ROLES[3]]['captures'][:] = 9
    result = M.verdicts(data)
    assert result['joint_primary_capture_advantage']
    assert not any(result['strict_simultaneous_capture_gain_over_AL_start'].values())
    data['persistent'][M.ROLES[3]]['captures'][:] = 5
    assert not M.verdicts(data)['joint_primary_capture_advantage']
    assert result['confirmation_capture_value'] == 500
    assert result['evolutionary_replicate_pairs'] == 1


def test_primary_uses_unrounded_strict_three_se():
    data = rows()
    flat_captures(data)
    v = np.tile([-1., 1.], 256)
    boundary = 3 * M.stats(v)['se']
    for world in ('pool', 'persistent'):
        data[world][M.ROLES[3]]['captures'] = 10 + v + boundary + 1e-10
    assert M.verdicts(data)['joint_primary_capture_advantage']
    data['persistent'][M.ROLES[3]]['captures'] -= 2e-10
    assert not M.verdicts(data)['joint_primary_capture_advantage']


def test_all_seven_retention_pairs_and_exact_margin_boundary():
    assert M.RETENTION == ((1, 0, 'persistent'), (2, 0, 'persistent'), (3, 0, 'persistent'),
                           (2, 1, 'pool'), (2, 1, 'persistent'), (3, 1, 'pool'), (3, 1, 'persistent'))
    data = rows()
    flat_captures(data)
    data['persistent'][M.ROLES[0]]['captures'][:] = 100
    data['persistent'][M.ROLES[1]]['captures'][:] = 90
    data['pool'][M.ROLES[1]]['captures'][:] = 90
    for role in M.ROLES[2:]:
        for world in ('pool', 'persistent'):
            data[world][role]['captures'][:] = 81
    reports, arrays = M.retention_diagnostics(data)
    for candidate, reference, world in M.RETENTION:
        key = f'{M.ROLES[candidate]}_vs_{M.ROLES[reference]}__{world}'
        expected = data[world][M.ROLES[candidate]]['captures'] - .9 * data[world][M.ROLES[reference]]['captures']
        np.testing.assert_array_equal(arrays['retention__' + key + '__ninety_percent_reference'], expected)
        assert not reports[key]['passes_conventional_10_percent_diagnostic']


def test_confirmation_reference_order_and_startup_count(monkeypatch):
    monkeypatch.syspath_prepend(str(STUDY))
    worker = load('am_measure', STUDY / 'measure.py')
    assert worker.ROLES == M.ROLES and worker.ARMS == M.ARMS
    source = ast.parse((STUDY / 'measure.py').read_text())
    calls = [n for n in ast.walk(source) if isinstance(n, ast.Call)]
    assert sum(isinstance(n.func, ast.Attribute) and n.func.attr == 'numerical_identity' for n in calls) == 1
    fn = functions(STUDY / 'measure.py')['freeze_endpoints']
    references = next(n.value for n in fn.body if isinstance(n, ast.Assign)
                      and any(isinstance(t, ast.Name) and t.id == 'references' for t in n.targets))
    assert [x.slice.value for x in references.elts] == ['ancestral_reference', 'reference']
    measure = functions(STUDY / 'measure.py')['measure']
    freeze = next(n.lineno for n in ast.walk(measure) if isinstance(n, ast.Call)
                  and isinstance(n.func, ast.Name) and n.func.id == 'freeze_endpoints')
    assert freeze < min(n.lineno for n in ast.walk(measure) if isinstance(n, ast.For))
    assert not any(n.startswith(('src.life.build', 'src.run', 'src.evolve')) for n in sys.modules)


def terminal_fixture(monkeypatch):
    base = Path("/synthetic_AM")
    docs = {}
    def put(name, value):
        docs[str(base / name)] = value
    def digest(path):
        return hashlib.sha256(json.dumps(docs[str(path)], sort_keys=True).encode()).hexdigest()
    monkeypatch.setattr(M, "read", lambda path: copy.deepcopy(docs[str(path)]))
    monkeypatch.setattr(M, "sha", digest)
    namespace = "pid:[4026531836]"
    budget_spec = {"cpu_seconds": 10800, "wall_seconds": 5400, "search_cpu_seconds": 7200,
                   "confirmation_cpu_seconds": 3600, "threads": 2, "workers": 1,
                   "cleanup_margin_seconds": 10, "rss_bytes": 4 * 1024**3,
                   "minimum_available_bytes": 4 * 1024**3, "address_space_bytes": 8 * 1024**3}
    protocol = {"budget": budget_spec}
    put("protocol.json", protocol)
    pd = digest(base / "protocol.json")
    put("release.json", {"status": "released", "protocol_sha256": pd, "pid_namespace": namespace})
    rd = digest(base / "release.json")
    monitor = {"pid": 100, "ppid": 90, "pgid": 100, "start_ticks": 1000}
    phases = (*M.ARMS, "confirmation")
    commands = {p: ["python", p] for p in phases}
    put("attempt.json", {"monitor": monitor, "pid_namespace": namespace, "protocol_sha256": pd,
                         "release_sha256": rd, "commands": commands, "budget": budget_spec})
    cleanup = {"pid_namespace": namespace, "checked_in_monitor": True, "same_pid_namespace": True,
               "all_owned_groups_exited": True, "all_worker_identities_exited": True,
               "remaining_group_members": [], "remaining_worker_identities": [], "remaining_descendants": []}
    workers, all_receipts, records = [], [], {}
    for i, phase in enumerate(phases):
        worker = {"pid": 101 + i, "ppid": 100, "pgid": 101 + i, "start_ticks": 1001 + i, "name": phase}
        workers.append(worker)
        cap = 7200 if i < 2 else 3810
        pb = {"cpu_seconds": cap, "wall_seconds": 5400 - i * 100, "threads": 2, "workers": 1,
              "cleanup_margin_seconds": 10, "rss_bytes": 4 * 1024**3,
              "minimum_available_bytes": 4 * 1024**3, "address_space_bytes": 8 * 1024**3}
        put(f"execution/{phase}/attempt.json", {"monitor": monitor, "pid_namespace": namespace,
             "protocol_sha256": pd, "release_sha256": rd, "command": commands[phase], "budget": pb})
        receipts = [{"pid": worker["pid"], "wait_status": 0, "exit_code": 0,
                     "user_cpu_seconds": 45., "system_cpu_seconds": 5.}]
        all_receipts.extend(receipts)
        record = {"status": "complete", "exit_code": 0, "worker_exit_code": 0,
                  "running": {}, "queued": [], "reason": None, "error": None, "cleanup_error": None,
                  "cpu_seconds": 100 * (i + 1), "wall_seconds": 90, "cap_cpu_seconds": cap,
                  "cap_wall_seconds": pb["wall_seconds"], "pid_namespace": namespace,
                  "protocol_sha256": pd, "release_sha256": rd,
                  "attempt_sha256": digest(base / f"execution/{phase}/attempt.json"),
                  "process_identities": [{**monitor, "name": "monitor"}, {**worker, "name": "worker"}],
                  "owned_process_groups": [worker["pid"]], "terminal_cleanup": copy.deepcopy(cleanup),
                  "wait4_receipts": receipts, "cap_rss_bytes": 4 * 1024**3,
                  "minimum_available_bytes": 4 * 1024**3, "worker_address_space_bytes": 8 * 1024**3,
                  "peak_owned_rss_bytes": 100000}
        name = f"execution/{phase}/budget.json"
        put(name, record)
        records[phase] = {"path": name, "sha256": digest(base / name)}
    global_record = {**copy.deepcopy(record), "cpu_seconds": 310., "wall_seconds": 300.,
                     "cap_cpu_seconds": 10800, "cap_wall_seconds": 5400,
                     "search_cpu_cap": 7200, "confirmation_cpu_cap": 3600,
                     "search_cpu_seconds": 210., "confirmation_cpu_seconds": 100.,
                     "phase": "confirmation", "attempt_sha256": digest(base / "attempt.json"),
                     "process_identities": [{**monitor, "name": "monitor"}, *workers],
                     "owned_process_groups": [w["pid"] for w in workers],
                     "phase_records": records, "wait4_receipts": all_receipts}
    put("budget.json", global_record)
    put("measurement_complete.json", {"fixture": True})
    for arm in M.ARMS:
        put(f"runs/{arm}/search_complete.json", {"fixture": arm})
    put("study_complete.json", {"status": "complete", "research_lives": 28748, "startup_lives": 8,
        "total_calls": 28756, "protocol_sha256": pd,
        "measurement_complete_sha256": digest(base / "measurement_complete.json"),
        "search_complete_pins": {a: digest(base / f"runs/{a}/search_complete.json") for a in M.ARMS}})
    return base, protocol, docs, digest


def test_actual_three_phase_terminal_contract(monkeypatch):
    base, protocol, _, _ = terminal_fixture(monkeypatch)
    assert M.verify_terminal(base, protocol)["cpu_seconds"] == 310


@pytest.mark.parametrize("kind", ["reserve", "rss", "reaping"])
def test_concrete_terminal_corruptions(monkeypatch, kind):
    base, protocol, docs, digest = terminal_fixture(monkeypatch)
    budget = docs[str(base / "budget.json")]
    path = "execution/confirmation/budget.json"
    phase = docs[str(base / path)]
    if kind == "missing_phase":
        del budget["phase_records"]["high_value"]
    elif kind == "reserve":
        budget["confirmation_cpu_seconds"] = 3600.
    elif kind == "wrong_parent":
        phase["process_identities"][1]["ppid"] += 1
    elif kind == "cleanup":
        phase["terminal_cleanup"]["remaining_descendants"] = [999]
    elif kind == "rss":
        phase["peak_owned_rss_bytes"] = 4 * 1024**3
    elif kind == "address":
        phase["worker_address_space_bytes"] = 16 * 1024**3
    else:
        phase["wait4_receipts"][0]["wait_status"] = 1
    budget["phase_records"]["confirmation"]["sha256"] = digest(base / path)
    with pytest.raises(ValueError):
        M.verify_terminal(base, protocol)


@pytest.mark.parametrize('missing_fourth_role', [False, True])
def test_actual_four_role_raw_coverage_in_memory(monkeypatch, missing_fourth_role):
    from contextlib import contextmanager

    base = Path('/synthetic_AM_rows')
    fixture = load('retained_row_schema', ROOT / 'outputs/cumulative_capability_20261015/design/test_retention_analyze.py')
    payloads, index, worlds = {}, {}, {}
    for world in M.WORLDS:
        abi = 4 if world in M.WORLDS[2:] else 3
        for i, role in enumerate(M.ROLES):
            raw, rec, seeds = fixture.row(abi=abi, n=512)
            raw.update({k: np.asarray(v) for k, v in {'role': role, 'world_name': world,
                'protocol_sha256': 'pin', 'genome_raw_sha256': f'genome_{i}',
                'endpoints_sha256': 'pin'}.items()})
            name = f'raw/{world}/row_{i:02d}.npz'
            payloads[str(base / name)] = raw
            index[name] = {'sha256': 'pin', 'lives': 512, 'abi': abi,
                           'cpu_seconds': 1., 'wall_seconds': .6}
            worlds[world] = rec
    protocol = {'worlds': worlds, 'seeds': seeds}
    endpoints = {'genomes': [{'raw_sha256': f'genome_{i}'} for i in range(4)]}
    complete = {'status': 'complete', 'research_lives': 8192, 'startup_lives': 4, 'rows': 16,
                'protocol_sha256': 'pin', 'row_index_sha256': 'pin', 'endpoints_sha256': 'pin'}
    if missing_fourth_role:
        del index['raw/pool/row_03.npz']
    monkeypatch.setattr(M, 'sha', lambda _: 'pin')
    monkeypatch.setattr(M, 'read', lambda p: index if p.name == 'row_index.json' else complete)
    monkeypatch.setattr(Path, 'rglob', lambda _self, _glob: iter(Path(k) for k in payloads))

    class Raw(dict):
        @property
        def files(self):
            return tuple(self)

    @contextmanager
    def load_raw(path, allow_pickle):
        assert allow_pickle is False
        yield Raw(payloads[str(path)])

    monkeypatch.setattr(M.np, 'load', load_raw)
    if missing_fourth_role:
        with pytest.raises(ValueError, match='16-row'):
            M.load_rows(base, protocol, endpoints)
    else:
        values, health, cpu = M.load_rows(base, protocol, endpoints)
        assert cpu == 16
        assert sum(r['all_fitness_rows_retained'] for w in health.values() for r in w.values()) == 8192
        assert all(tuple(values[w]) == M.ROLES for w in M.WORLDS)
