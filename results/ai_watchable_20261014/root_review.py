"""Verify the viewer against published AI data without executing a simulator."""
from pathlib import Path
import hashlib
import json
import sys

import numpy as np

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[1]
PUBLIC = ROOT / 'results/exploratory_reserve_replication_20261014'
sys.path.insert(0, str(ROOT))
from src.life import spec


def read(path):
    return json.loads(path.read_text())


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def main():
    data = read(HERE / 'bodies.json')
    truth = read(HERE / 'truth.json')
    summary = read(PUBLIC / 'analysis_result/summary.json')
    protocol = read(PUBLIC / 'protocol.json')
    assert data['summary'] == summary['contrasts']
    assert data['source_summary_sha256'] == sha(PUBLIC / 'analysis_result/summary.json')
    assert data['seed'] == truth['seed'] == protocol['confirmation']['seeds'][0] == 52360000
    assert len(data['bodies']) == len(truth['cases']) == 3
    with np.load(PUBLIC / 'confirmation/genotypes.npz', allow_pickle=False) as rows:
        raw, labels = rows['genomes'], rows['labels'].tolist()
    packed = spec.V3.pack_genomes(raw, 'hexprism')
    for i, body in enumerate(data['bodies']):
        assert body['name'] == truth['cases'][i]['role'] == labels[i]
        assert body['abi'] == 3 and body['mode'] == 'grn'
        assert np.asarray(body['genome'], dtype=np.float64).tobytes() == packed[i].tobytes()
        assert body['genotype_sha256'] == hashlib.sha256(raw[i].tobytes()).hexdigest()
        assert body['world'] == {key: protocol['world'][key] for key in spec.V3.WORLD_KEYS}
        path = PUBLIC / f'confirmation/persistent/row_{i:04d}.npz'
        with np.load(path, allow_pickle=False) as saved:
            assert np.asarray(truth['cases'][i]['ledger'], dtype=np.float64).tobytes() == saved['ledger'][0].tobytes()
            assert truth['cases'][i]['source_sha256'] == sha(path)
    authorization = read(HERE / 'root_authorization.json')
    for name, digest in authorization['source_pins'].items():
        assert sha(HERE / name) == digest
    text = (HERE / 'exploratory_reserve_replication.html').read_text()
    assert '<script>' + (ROOT / 'results/atlas/play/lifesim.js').read_text() + '</script>' in text
    assert '<script>' + (HERE / 'viewer.js').read_text() + '</script>' in text
    assert json.loads(text.split('<script id="comparison-data" type="application/json">')[1].split('</script>')[0]) == data
    budget = read(HERE / 'validation_budget.json')
    replay = read(HERE / 'replay_stdout.json')
    assert budget['status'] == replay['status'] == 'complete'
    assert budget['js_replay_lives'] == replay['js_replay_lives'] == 3
    assert budget['all_processes_exited'] and not budget['cleanup_error']
    assert budget['stdout_sha256'] == sha(HERE / 'replay_stdout.json')
    assert sum(row['ledger_columns_bitwise_equal'] for row in replay['rows']) == 171
    assert read(HERE / 'ui_check.json')['assertions'] == 84
    browser = read(HERE / 'paused_browser/execution.json')
    assert browser['status'] == 'incomplete_no_retry' and browser['all_processes_exited']
    guard = browser['guard']
    assert guard['status'] == 'passed' and guard['initializations'] == 3
    assert guard['advance_calls'] == guard['run_calls'] == 0 and guard['times'] == [0, 0, 0]
    assert not guard['errors'] and len(guard['aggregates']) == 3
    assert browser['screenshot_sha256'] == sha(HERE / 'paused_browser/paused_firefox.png')
    result = {'status': 'passed_data_and_layout_review_with_browser_exit_limitation',
              'summary_sha256': data['source_summary_sha256'], 'genotypes_verified': 3,
              'raw_C_ledger_values_verified': 171, 'unchanged_engine_and_UI_embedded': True,
              'node_replay_lives': 3, 'node_replay_cpu_seconds': budget['cpu_seconds'],
              'paused_browser_initializations': 3, 'paused_browser_completed_lives': 0,
              'paused_browser_advance_calls': 0, 'paused_browser_runtime_status': browser['status'],
              'desktop_screenshot_visually_reviewed': True, 'all_validation_processes_exited': True,
              'new_research_lives': 0, 'new_C_lives': 0, 'new_compilations': 0,
              'root_review_script_sha256': sha(Path(__file__))}
    with (HERE / 'root_review.json').open('x') as stream:
        stream.write(json.dumps(result, indent=2) + '\n')
    print(json.dumps(result, indent=2))


if __name__ == '__main__':
    main()
