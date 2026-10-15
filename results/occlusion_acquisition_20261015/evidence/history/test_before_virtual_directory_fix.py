"""AN focused changes only: checkpoint prefixes, 8+4+4 calls and fixed 3×5 matrix."""
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
STUDY = ROOT / 'outputs/autonomous_occlusion_acquisition_20261015'
AM = ROOT / 'outputs/autonomous_capture_value_selection_20261015'


def load(name, path):
    spec = importlib.util.spec_from_file_location(name, path)
    result = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(result)
    return result

M = load("an_reader", STUDY / "analyze.py")

def functions(path):
    return {n.name: n for n in ast.parse(path.read_text()).body if isinstance(n, ast.FunctionDef)}

def rows():
    fixture = load('retained_test_row', ROOT / 'outputs/cumulative_capability_20261015/design/test_retention_analyze.py')
    values, _ = M.reconstruct(*fixture.row(n=512))
    return {w: {r: copy.deepcopy(values) for r in M.ROLES} for w in M.WORLDS}

def flat_captures(data, value=10.):
    for world in M.WORLDS:
        for role in M.ROLES:
            data[world][role]['captures'][:] = value

def test_physics_truth_genetic_core_unchanged():
    for filename, names in (
            ('analyze.py', ('identical', 'stats', 'prices', 'physical_costs', 'validate_row', 'reconstruct', 'json_genome')),
            ('measure.py', ('parent_check', 'check_visibility_truth')),
            ('native_replay.py', ('sha', 'raw_sha', 'definitions', 'initial_population', 'replay_first'))):
        old, new = functions(AM / filename), functions(STUDY / filename)
        assert all(ast.dump(old[name]) == ast.dump(new[name]) for name in names)
    assert (AM / 'replay_ops.py').read_bytes() == (STUDY / 'replay_ops.py').read_bytes()
    old = functions(ROOT / 'outputs/audit_capture_value_selection_20261015/terminal_review/accuracy_supplement.py')
    assert ast.dump(old['describe_counts']) == ast.dump(functions(STUDY / 'analyze.py')['describe_counts'])


def test_39_groups_8_retention_vectors_covariance_duplicates():
    data = rows()
    noise = np.arange(512, dtype=float)
    data['persistent'][M.ROLES[2]]['captures'] += noise
    data['turn100_blink80_20'][M.ROLES[2]]['captures'] += noise + 2
    reports, arrays = M.contrasts(data)
    retention, extra = M.retention_diagnostics(data)
    assert (len(reports), len(arrays), len(retention), len(extra)) == (39, 2925, 4, 8)
    assert len(set(arrays) | set(extra)) == 2933
    key = 'interaction__turn100_blink80_20_minus_persistent__generation8_minus_AM_current_start'
    np.testing.assert_array_equal(arrays[key+'__captures'], np.full(512, 2.))
    assert reports[key]['captures']['se'] == 0
    np.testing.assert_array_equal(arrays['within__pool__generation4_minus_AM_current_start__captures'], np.zeros(512))


def test_fixed_final_primary_is_not_best_midpoint_and_strict_3se():
    data = rows(); flat_captures(data)
    data['blink80_20'][M.ROLES[1]]['captures'][:] = 100
    assert not M.verdicts(data)['primary_capture_gain_above_3se']
    values = np.tile([-1., 1.], 256)
    boundary = 3 * M.stats(values)['se']
    data['blink80_20'][M.ROLES[2]]['captures'] = 10 + values + boundary + 1e-10
    assert M.verdicts(data)['primary_capture_gain_above_3se']
    data['blink80_20'][M.ROLES[2]]['captures'] -= 2e-10
    assert not M.verdicts(data)['primary_capture_gain_above_3se']


def test_four_retention_pairs_strict_margin():
    assert M.RETENTION == ((1,0,'pool'), (1,0,'persistent'), (2,0,'pool'), (2,0,'persistent'))
    data=rows(); flat_captures(data, 100.)
    for world in ('pool','persistent'):
        for role in M.ROLES[1:]: data[world][role]['captures'][:] = 90
    report, arrays=M.retention_diagnostics(data)
    assert all(not value['passes_conventional_10_percent_diagnostic'] for value in report.values())
    assert all(np.all(value == 0) for key,value in arrays.items() if key.endswith('ninety_percent_reference'))


def test_aggregate_accuracy_zero_and_weighting():
    assert M.describe_counts(np.zeros(2), np.zeros(2), np.zeros(2))['aggregate_capture_fraction'] is None
    result=M.describe_counts(np.array([1.,1.]), np.array([0.,8.]), np.array([1.,9.]))
    assert result['aggregate_capture_fraction'] == .2
    with pytest.raises(ValueError): M.describe_counts(np.array([1.]), np.array([1.]), np.array([1.]))


def test_fixed_checkpoint_scope_and_one_confirmation_identity(monkeypatch):
    monkeypatch.syspath_prepend(str(STUDY))
    worker=load('an_measure', STUDY/'measure.py')
    assert worker.ROLES==M.ROLES and worker.ARMS==M.ARMS
    for generation in (4,8):
        state={'generation':generation, 'curves':[{'gen':g,'pop_invalid':0,'pop_mismatch':0,'recheck_invalid':0} for g in range(generation)]}
        assert worker.validate_search_state(state,generation)==dict(pop_invalid=0.,pop_mismatch=0.,recheck_invalid=0.)
        with pytest.raises(ValueError): worker.validate_search_state(state,6)
    tree=ast.parse((STUDY/'measure.py').read_text())
    assert sum(isinstance(n,ast.Call) and isinstance(n.func,ast.Attribute) and n.func.attr=='numerical_identity' for n in ast.walk(tree))==1
    fn=functions(STUDY/'measure.py')['measure']
    freeze=next(n.lineno for n in ast.walk(fn) if isinstance(n,ast.Call) and isinstance(n.func,ast.Name) and n.func.id=='freeze_endpoints')
    assert freeze < min(n.lineno for n in ast.walk(fn) if isinstance(n,ast.For))
    assert not any(n.startswith(('src.life.build','src.run','src.evolve')) for n in sys.modules)


def terminal_fixture(monkeypatch):
    base = Path("/synthetic_AN")
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
        cap = 7200 if i == 0 else 3710
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
    global_record = {**copy.deepcopy(record), "cpu_seconds": 210., "wall_seconds": 200.,
                     "cap_cpu_seconds": 10800, "cap_wall_seconds": 5400,
                     "search_cpu_cap": 7200, "confirmation_cpu_cap": 3600,
                     "search_cpu_seconds": 110., "confirmation_cpu_seconds": 100.,
                     "phase": "confirmation", "attempt_sha256": digest(base / "attempt.json"),
                     "process_identities": [{**monitor, "name": "monitor"}, *workers],
                     "owned_process_groups": [w["pid"] for w in workers],
                     "phase_records": records, "wait4_receipts": all_receipts}
    put("budget.json", global_record)
    put("measurement_complete.json", {"fixture": True})
    for arm in M.ARMS:
        put(f"runs/{arm}/search_complete.json", {"fixture": arm})
    put("study_complete.json", {"status": "complete", "research_lives": 28214, "startup_lives": 8,
        "total_calls": 28222, "protocol_sha256": pd,
        "measurement_complete_sha256": digest(base / "measurement_complete.json"),
        "search_complete_pins": {a: digest(base / f"runs/{a}/search_complete.json") for a in M.ARMS}})
    return base, protocol, docs, digest

def test_two_phase_cumulative_cpu():
    with pytest.MonkeyPatch.context() as mp:
        base, protocol, docs, digest=terminal_fixture(mp)
        assert M.verify_terminal(base,protocol)['cpu_seconds']==210
        docs[str(base/'budget.json')]['confirmation_cpu_seconds']=3600
        with pytest.raises(ValueError): M.verify_terminal(base,protocol)


@pytest.mark.parametrize("missing_final", [False,True])
def test_five_world_three_role_coverage(monkeypatch, missing_final):
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
    endpoints = {'genomes': [{'raw_sha256': f'genome_{i}'} for i in range(3)]}
    complete = {'status': 'complete', 'research_lives': 7680, 'startup_lives': 4, 'rows': 15,
                'protocol_sha256': 'pin', 'row_index_sha256': 'pin', 'endpoints_sha256': 'pin'}
    if missing_final:
        del index['raw/pool/row_02.npz']
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
    if missing_final:
        with pytest.raises(ValueError, match='15-row'):
            M.load_rows(base, protocol, endpoints)
    else:
        values, health, cpu = M.load_rows(base, protocol, endpoints)
        assert cpu == 15
        assert sum(r['all_fitness_rows_retained'] for w in health.values() for r in w.values()) == 7680
        assert all(tuple(values[w]) == M.ROLES for w in M.WORLDS)


def endpoint_fixture(monkeypatch):
    """Compact virtual JSON/checkpoint archive: no files, random draws or engine calls."""
    import io
    from types import SimpleNamespace

    base=Path('/synthetic_AN_endpoints')
    docs, blobs, genomes={}, {}, {}
    def key(path): return str(path if isinstance(path,Path) else base/path)
    def put(name,value): docs[key(name)]=value
    def payload(path):
        k=key(path)
        if k in blobs: return blobs[k]
        return json.dumps(docs[k],sort_keys=True).encode()
    def digest(path): return hashlib.sha256(payload(path)).hexdigest()
    def raw(value): return hashlib.sha256(np.asarray(value).tobytes()).hexdigest()
    def put_lines(name,values): blobs[key(name)]=b''.join((json.dumps(v)+'\n').encode() for v in values)
    put('protocol.json', {'synthetic':True}); put('release.json',{'status':'released'})
    for name in ('population_loader.py','selection.py','search.py'):
        blobs[key(name)]=name.encode()
    pd,rd=digest('protocol.json'),digest('release.json')
    start=np.zeros(875,np.float32); mid=np.ones(875,np.float32); table=np.stack([np.full(875,i+2,np.float32) for i in range(32)])
    prefix='runs/acquisition/'
    for path,genome in [('inputs/AM_current_start.json',start),(prefix+'generation4/best_genome.json',mid),(prefix+'best_genome.json',table[0])]:
        put(path,{'synthetic_genome':raw(genome)}); genomes[key(path)]=genome
    for name in ('checkpoint.pt','generation4/checkpoint.pt','config.yaml'):
        blobs[key(prefix+name)]=name.encode()
    curves=[dict(gen=g,evals=320*(g+1),recheck_k=64,pop_invalid=0,pop_mismatch=0,recheck_invalid=0,pop_guard=0,fitness=1.,mean_fitness=1.) for g in range(8)]
    for g in (0,4,7): curves[g]['valid']=1.
    lineage=[dict(event='founders',ids=list(range(32)),copies=[])]
    for g in range(8):
        lineage.append(dict(gen=g,children=[dict(id=32+224*g+i,pa=0,pb=1,mask=0,ops={'mut':[]}) for i in range(224)],
                            seeds=list(range(8)),recheck={'seeds':list(range(8,16)),'ids':list(range(64))},
                            survivors=list(range(32)),fitness=[1.]*32))
    log_pins,mid_pins={},{}
    for name,values,mid_values in [('curves.jsonl',curves,curves[:4]),('lineage.jsonl',lineage,lineage[:5]),('clones.jsonl',[],[])]:
        put_lines(prefix+name,values)
        data=payload(prefix+name)
        partial=b''.join((json.dumps(v)+'\n').encode() for v in mid_values)
        log_pins[name]={'bytes':len(data),'sha256':raw(np.frombuffer(data,dtype=np.uint8))}
        mid_pins[name]={'bytes':len(partial),'sha256':hashlib.sha256(partial).hexdigest()}
    population=dict(dims={},genomes=[{'synthetic':i+2} for i in range(32)],fitness=[1.]*32,ids=list(range(32)))
    put(prefix+'population.json',population)
    popstart={'population_raw_sha256':'initial32','row_sha256':['initialrow']*32}
    identity={'identity':'base'}
    extended={**identity,'population_start':{'version':1,**popstart,'source_pins':{n:digest(n) for n in ('population_loader.py','search.py')}},
        'retention_selection':{'version':1,'arm':'acquisition','worlds':{},
        'rule':'gen fixed 2pool/2persistent/4blink80_20 per8 repeated for recheck; diagnostics=persistent neutral; R_cap500',
        'pattern':['pool','persistent','blink80_20','blink80_20']*2,'source_pins':{'selection.py':digest('selection.py')}}}
    put(prefix+'determinism.json',extended)
    diagnostic=dict(seed=123,abi=4,generations=8,evals=2560,lives=2,founders_sampled=0,top_best_rank=0,invalid_lives=0,mismatch_lives=0,forks={},heldout_score=None)
    put_lines(prefix+'results.jsonl',[diagnostic])
    put(prefix+'search_startup.json',{'startup_lives':4})
    health=dict(pop_invalid=0.,pop_mismatch=0.,recheck_invalid=0.)
    common=dict(rank=0,rank_zero_id=0,search_health=health,numerical_identity=extended)
    final={**common,'generation':8,'checkpoint_sha256':digest(prefix+'checkpoint.pt'),'log_prefix_pins':log_pins,
        'genome_file_sha256':digest(prefix+'best_genome.json'),'genome_raw_sha256':raw(table[0]),
        'population_raw_sha256':raw(table),'population_file_sha256':digest(prefix+'population.json'),
        'determinism_sha256':digest(prefix+'determinism.json'),'results_sha256':digest(prefix+'results.jsonl')}
    snapshot=dict(status='complete',generation=4,rank=0,rank_zero_id=0,
        checkpoint_sha256=digest(prefix+'generation4/checkpoint.pt'),genome_file_sha256=digest(prefix+'generation4/best_genome.json'),
        genome_raw_sha256=raw(mid),population_raw_sha256='midpoint32',identity=extended,log_prefix_pins=mid_pins,
        protocol_sha256=pd,release_sha256=rd,added_lives=0,random_draws=0)
    put(prefix+'generation4/snapshot.json',snapshot)
    midpoint={**common,'generation':4,'checkpoint_sha256':snapshot['checkpoint_sha256'],'log_prefix_pins':mid_pins,
        'genome_file_sha256':snapshot['genome_file_sha256'],'genome_raw_sha256':raw(mid),
        'population_raw_sha256':'midpoint32','snapshot_sha256':digest(prefix+'generation4/snapshot.json')}
    names=('checkpoint.pt','config.yaml','determinism.json','curves.jsonl','lineage.jsonl','population.json','best_genome.json','results.jsonl',
           'search_startup.json','generation4/checkpoint.pt','generation4/best_genome.json','generation4/snapshot.json')
    marker=dict(status='complete',arm='acquisition',research_lives=20534,startup_lives=4,protocol_sha256=pd,release_sha256=rd,
        count_proof=dict(selection=20480,valid=48,final=6,half_duration=2,native_evals=2560,generations=8,children_per_generation=224,midpoint_added_lives=0),
        output_pins={n:digest(prefix+n) for n in names},checkpoint_log_pins=log_pins,midpoint=snapshot,
        health={k:[r[k] for r in curves] for k in (*health,'pop_guard')})
    put(prefix+'search_complete.json',marker)
    sig=[{k:c[k] for k in ('id','pa','pb','mask','ops')} for c in lineage[1]['children']]
    proof=dict(status='passed',protocol_sha256=pd,initial_rows=32,offspring_per_arm=224,initial_population_raw_sha256='initial32',
        initial_row_sha256=popstart['row_sha256'],recorded_first_256_replayed=True,simulated_lives=0,random_draws=0,
        runs={'acquisition':dict(genetic_signature_sha256=hashlib.sha256(json.dumps(sig,sort_keys=True,separators=(',',':'),allow_nan=False).encode()).hexdigest(),
             lineage_sha256=digest(prefix+'lineage.jsonl'),candidate_row_sha256=['initialrow']*32+['child']*224)})
    put('first_cohort_replay.json',proof)
    paths=['inputs/AM_current_start.json',prefix+'generation4/best_genome.json',prefix+'best_genome.json']
    manifest=dict(protocol_sha256=pd,roles=list(M.ROLES),searches={'acquisition':final},midpoint=midpoint,
        genomes=[dict(role=role,path=path,file_sha256=digest(path),raw_sha256=raw(genomes[key(path)])) for role,path in zip(M.ROLES,paths)],
        first_cohort_replay_sha256=digest('first_cohort_replay.json'),
        selection='Generation4 and generation8 population rank0 endpoints fixed before confirmation; final is never replaced by midpoint.')
    put('endpoints.json',manifest)
    protocol=dict(reference=dict(path=paths[0],raw_sha256=raw(start)),population_start=popstart,selection_worlds={},native_seed=123)
    monkeypatch.setattr(M,'read',lambda p:copy.deepcopy(docs[key(p)]))
    monkeypatch.setattr(M,'sha',digest)
    monkeypatch.setattr(M,'json_genome',lambda p:np.full(875,p['params']['synthetic'],np.float32) if isinstance(p,dict) else genomes[key(p)].copy())
    monkeypatch.setattr(M,'json_lines',lambda p:[json.loads(line) for line in payload(p).decode().splitlines()])
    original_stat,original_open=Path.stat,Path.open
    monkeypatch.setattr(Path,'stat',lambda p,*args,**kwargs:SimpleNamespace(st_size=len(payload(p))) if str(p).startswith(str(base)) else original_stat(p,*args,**kwargs))
    monkeypatch.setattr(Path,'open',lambda p,*args,**kwargs:io.BytesIO(payload(p)) if str(p).startswith(str(base)) else original_open(p,*args,**kwargs))
    return base,protocol,identity,docs,blobs,digest


def test_complete_midpoint_and_final_endpoint_contract(monkeypatch):
    base,protocol,identity,_,_,_=endpoint_fixture(monkeypatch)
    _,review=M.verify_endpoints(base,protocol,identity)
    assert review['midpoint_generation']==4 and review['midpoint_added_lives']==0
    assert review['searches']['acquisition']['generation']==8


@pytest.mark.parametrize('corruption',['midpoint_prefix','midpoint_role','extra_startup','midpoint_replaces_final'])
def test_endpoint_corruption_fails(monkeypatch,corruption):
    base,protocol,identity,docs,blobs,digest=endpoint_fixture(monkeypatch)
    manifest=docs[str(base/'endpoints.json')]
    if corruption=='midpoint_prefix':
        manifest['midpoint']['log_prefix_pins']['lineage.jsonl']['bytes']-=1
    elif corruption=='midpoint_role':
        manifest['midpoint']['generation']=5
    elif corruption=='extra_startup':
        docs[str(base/'runs/acquisition/search_complete.json')]['startup_lives']=6
    else:
        manifest['genomes'][2]=copy.deepcopy(manifest['genomes'][1])
        manifest['genomes'][2]['role']='generation8'
    with pytest.raises(ValueError): M.verify_endpoints(base,protocol,identity)
