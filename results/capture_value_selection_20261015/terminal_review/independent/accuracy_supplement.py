"""AM terminal-only descriptive capture/click accuracy; no independent-click inference."""
from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path

import numpy as np

PROTOCOL_SHA = '9210e218d92d912f8b63822980de7fab868ad8904417d0f438a55e2b42922294'
ANALYZER_SHA = '3c22015e7415467e273ace9cf8248b53b4ecf37f4584c406e73807fe196ed474'
ROLES = ('AI_control_start', 'AL_mixture_start', 'current_value_final', 'high_value_final')
WORLDS = ('pool', 'persistent', 'blink80_5', 'turn100_blink80_5')


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def read(path):
    return json.loads(Path(path).read_text())


def describe_counts(captures, misses, clicks):
    arrays = tuple(np.asarray(x) for x in (captures, misses, clicks))
    if (any(x.ndim != 1 or x.size == 0 or not np.isfinite(x).all()
            or np.any(x < 0) or np.any(x != np.floor(x)) for x in arrays)
            or len({x.shape for x in arrays}) != 1
            or not np.array_equal(arrays[0] + arrays[1], arrays[2])):
        raise ValueError('finite nonnegative integer captures + misses = clicks required')
    captures, misses, clicks = arrays
    total_captures, total_misses, total_clicks = (int(x.sum()) for x in arrays)
    return {'lives':len(clicks), 'total_captures':total_captures, 'total_misses':total_misses,
            'total_clicks':total_clicks,
            'aggregate_capture_fraction':total_captures / total_clicks if total_clicks else None,
            'mean_captures_per_life':float(captures.mean()),
            'mean_clicks_per_life':float(clicks.mean()), 'mean_misses_per_life':float(misses.mean()),
            'clickless_lives':int(np.count_nonzero(clicks == 0)),
            'clickless_fraction':float(np.mean(clicks == 0))}


def supplement(study, budget_sha, clearance_sha, summary_sha):
    study = Path(study).resolve()
    files = {'protocol.json':PROTOCOL_SHA, 'analyze.py':ANALYZER_SHA, 'budget.json':budget_sha,
             'terminal_review/host_clearance.json':clearance_sha, 'analysis_result/summary.json':summary_sha}
    if any(sha(study/name) != expected for name,expected in files.items()):
        raise ValueError('root-reviewed terminal/source pins differ')
    budget = read(study/'budget.json')
    clearance = read(study/'terminal_review/host_clearance.json')
    if (budget['status'] != 'complete' or budget['exit_code'] != 0 or budget['worker_exit_code'] != 0
            or clearance['status'] != 'cleared' or clearance['budget_sha256'] != budget_sha
            or clearance['pid_namespace'] != budget['pid_namespace']
            or clearance['remaining_identities'] or clearance['remaining_group_members']):
        raise ValueError('whole-study terminal completion and root clearance required')
    summary = read(study/'analysis_result/summary.json')
    protocol = read(study/'protocol.json')
    if (summary['status'] != 'complete' or summary['protocol_sha256'] != PROTOCOL_SHA
            or summary['paired_arrays'] != 4064 or summary['total_calls'] != 28756
            or summary['raw_rows'] != 16 or summary['raw_confirmation_lives'] != 8192
            or protocol['roles'] != list(ROLES) or tuple(protocol['worlds']) != WORLDS):
        raise ValueError('complete unchanged canonical analysis required')
    index = read(study/'row_index.json')
    if sha(study/'row_index.json') != summary['input_pins']['row_index.json']:
        raise ValueError('completed-reader row index changed')
    expected_paths = {f'raw/{world}/row_{i:02d}.npz' for world in WORLDS for i in range(len(ROLES))}
    if set(index) != expected_paths:
        raise ValueError('all16 fixed confirmation rows required')
    rows, raw_pins = {}, {}
    for world in WORLDS:
        definition = protocol['worlds'][world]
        if definition['world']['b2_amp'] != 0 or definition['world']['b2_value'] != 0:
            raise ValueError('capture/miss/click relation requires these zero-decoy worlds')
        rows[world] = {}
        for i, role in enumerate(ROLES):
            name = f'raw/{world}/row_{i:02d}.npz'
            digest = sha(study/name)
            if (digest != index[name]['sha256'] or digest != summary['input_pins'][name]
                    or index[name]['lives'] != 512):
                raise ValueError('raw hash/count differs from completed reader')
            raw_pins[name] = digest
            with np.load(study/name, allow_pickle=False) as raw:
                ledger = raw['ledger']
                if (ledger.dtype != np.float64 or ledger.shape != (512, 57 if definition['abi'] == 3 else 58)
                        or str(raw['role']) != role or str(raw['world_name']) != world
                        or str(raw['protocol_sha256']) != PROTOCOL_SHA
                        or raw['seeds'].dtype != np.uint64 or raw['seeds'].tolist() != protocol['seeds']):
                    raise ValueError('literal row schema/identity differs')
                rows[world][role] = describe_counts(ledger[:,35], ledger[:,36], ledger[:,37])
            reported = summary['absolute'][world][role]
            for metric, key in (('captures','mean_captures_per_life'),('misses','mean_misses_per_life'),
                                ('clicks','mean_clicks_per_life')):
                if reported[metric]['mean'] != rows[world][role][key]:
                    raise ValueError('count mean differs from completed canonical analysis')
    if any(sha(study/name) != digest for name,digest in {**files, **raw_pins}.items()):
        raise ValueError('input changed during supplement')
    return {'status':'complete_descriptive_supplement', 'protocol_sha256':PROTOCOL_SHA,
            'source_sha256':sha(Path(__file__)), 'terminal_and_reader_pins':files, 'raw_pins':raw_pins,
            'rows':rows, 'raw_rows':16, 'raw_lives':8192,
            'definition':'Aggregate capture fraction = sum(captures) / sum(clicks); null if no clicks.',
            'limitations':['Descriptive ratio, not a new primary outcome or success criterion.',
                'Clicks within a life are not independent replicates; no binomial standard error is reported.',
                'The pooled fraction weights lives by their number of clicks; it is not the mean of per-life fractions.',
                'A higher fraction can result from fewer attempts, so capture, miss and click counts remain visible.',
                'One paired evolution does not establish reproducible policy effects or sophisticated computation.'],
            'new_simulations':0,'builds':0,'genetic_draws':0}


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--study',type=Path,required=True)
    parser.add_argument('--out',type=Path,required=True)
    parser.add_argument('--budget-sha256',required=True)
    parser.add_argument('--clearance-sha256',required=True)
    parser.add_argument('--summary-sha256',required=True)
    args=parser.parse_args()
    result=supplement(args.study,args.budget_sha256,args.clearance_sha256,args.summary_sha256)
    args.out.mkdir(parents=True,exist_ok=False)
    (args.out/'accuracy.json').write_text(json.dumps(result,indent=2,allow_nan=False)+'\n')
    print(json.dumps({'status':result['status'],'raw_rows':16,'raw_lives':8192,
                      'output_sha256':sha(args.out/'accuracy.json')}))


if __name__ == '__main__':
    main()
