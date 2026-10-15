"""Append the cleared complete AB run; default dry run performs no outcome reads.

Uses the immutable published helper, preserves preparation and released source,
and checks portable offline reanalysis. No simulation, compile, mutation or Git write.
"""
from __future__ import annotations

import argparse
import importlib.util
import json
import os
from pathlib import Path
import subprocess
import sys

AUDIT = Path(__file__).resolve().parent
ROOT = AUDIT.parents[1]
STUDY = ROOT / 'outputs/autonomous_visibility_precision_20261014'
ARCHIVE = ROOT / 'results/visibility_precision_20261014'
PRELAUNCH_SHA = '9443d1a0470b19db213c7cece5e8cac685618b1de1a900cebdf617345dbf097f'
READY_SHA = '6ffa386848ec6461e18a647db37403f490004921a39ca74a8daaba4196ab4c81'
HELPER_SHA = 'e9ba7a7ef3e715bf7993ba7ac5d7c188795771b534cccb3a8e4f3d067fd5c45c'
PINS = {'budget.json': '4d0bc330805576b85d5a42ceb5ffd08834eaedb2509273c9a34764734a0c71c4', 'terminal_process_clearance.json': 'ffbfe92aa1a904b53595ea5125af4e4fd23c020c8a9db939a7fe49280cec92f1', 'terminal_review/raw_analysis_review.json': 'a846ca7b82c87ac9c7da1d66b36697f6bc3a4c444f290c2487cd485dec7fd545', 'terminal_review/native_replay.json': '805e935112a9cd1773bdca9e08e86055862659f32078335c475fedc8011cdbce', 'terminal_review/native_output_check.json': 'f23b6b3e16d59ada2c035167b9dc8e74c962918bfa76c09af171814102bed665', 'terminal_review/root_reanalysis.json': '4af6f97f401ef7fe5713c61e4bce59739307dbb178da8796607f7022cff1cece', 'analysis_result/summary.json': '684be74b306a79cccffd5f9528b50760421f7f8aae155ff75c31d3cd7a650279', 'analysis_result/paired_vectors.npz': 'ba34381ce1f62403f7274410949c4634f9250312c041ea1f629a53ee369b8167'}


def run():
    import numpy as np

    spec = importlib.util.spec_from_file_location('reviewed_AB_archive', AUDIT / 'archive.py')
    a = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(a)
    if (a.sha(AUDIT / 'archive.py') != HELPER_SHA
            or a.sha(ARCHIVE / 'prelaunch/manifest.json') != PRELAUNCH_SHA
            or a.sha(STUDY / 'ready.json') != READY_SHA):
        raise ValueError('published helper/preparation or released identity changed')
    for name, digest in PINS.items():
        if a.sha(STUDY / name) != digest:
            raise ValueError('reviewed terminal artifact differs: ' + name)
    budget, ready = a.read(STUDY / 'budget.json'), a.read(STUDY / 'ready.json')
    clearance = a.read(STUDY / 'terminal_process_clearance.json')
    if (budget.get('status') != 'complete' or budget.get('exit_code') != 0
            or budget.get('running') or budget.get('queued') or budget.get('cleanup_error')):
        raise ValueError('complete settled first attempt required')
    if (clearance.get('status') != 'cleared' or clearance.get('all_processes_exited') is not True
            or clearance.get('budget_sha256') != PINS['budget.json']):
        raise ValueError('root clearance does not bind terminal budget')
    identities = {(p['pid'], p['start_ticks']) for p in budget['process_identities']}
    if (identities != {(p['pid'], p['start_ticks']) for p in clearance['processes']}
            or set(clearance['process_groups']) != set(budget['owned_process_groups'])):
        raise ValueError('root clearance omits owned processes/groups')
    for table, base in ((ready['source_pins'], STUDY), (ready['production_pins'], ROOT)):
        for name, digest in table.items():
            if a.sha(a.inside(base, name)) != digest:
                raise ValueError('released source changed: ' + name)
    if len(ready['source_pins']) != 79 or len(ready['production_pins']) != 35:
        raise ValueError('released source closure differs')
    result = a.read(STUDY / 'analysis_result/summary.json')
    if (result.get('status') != 'complete' or result.get('protocol_sha256') != a.PROTOCOL_SHA
            or (result.get('research_lives'), result.get('startup_validation_lives'), result.get('total_lives')) != (19576, 10, 19586)
            or result['resources']['total_cpu_seconds'] != budget['cpu_seconds']):
        raise ValueError('independent complete analysis differs from terminal scope')
    prior = a.read(ARCHIVE / 'prelaunch/manifest.json')
    plan = a.make_plan(ROOT, STUDY, AUDIT, 'terminal')
    plan.update(status='complete_independently_reconciled', scientific_lives_completed=19586,
                research_lives=19576, validation_lives=10,
                compiled_libraries=len(list((STUDY / 'build-cache').rglob('*.so'))),
                cpu_seconds=budget['cpu_seconds'], scientific_outcomes_claimed=True,
                prelaunch_manifest_sha256=PRELAUNCH_SHA,
                scientific_scope='Two fixed Z backgrounds, four 3+4-life generations versus one 12+16-life generation, equal selection calls. No resolved primary fitness advantage for precision; D90 depth saves costs while losing captures. No own-start capture gain or algorithmic improvement established.')

    def add(path, relative):
        item = {'source': str(path), 'sha256': a.sha(path), 'bytes': path.stat().st_size,
                'origin': str(path.relative_to(ROOT))}
        if relative in plan['artifacts'] and plan['artifacts'][relative]['sha256'] != item['sha256']:
            raise ValueError('terminal destination collision: ' + relative)
        plan['artifacts'][relative] = item

    add(Path(__file__).resolve(), 'terminal_review/archive_terminal.py')
    status = AUDIT / 'ARCHIVE.md'
    status.write_text(
        '# AB terminal archive\n\n'
        f'AB completed 19,576 research lives and ten existing ABI3 startup compatibility lives in {budget["cpu_seconds"]:.6f} CPU-seconds, including compilation and cleanup. '
        'Both fixed Z endpoints received four 3+4-life generations and one 12+16-life generation, with 4,096 selection calls per branch. '
        'Four fixed final endpoints and two starts then received 512 shared fresh confirmation lives.\n\n'
        'The [summary](analysis_result/summary.json) and [450 paired arrays](analysis_result/paired_vectors.npz) reproduce with '
        '`python analysis/analyze.py --study . --out NEW_DIRECTORY`. The frozen reader passed unchanged. '
        'Recorded-operation replay verifies both matched 256-genome first cohorts and all four final 32-genome populations; it samples no new randomness or lives.\n\n'
        'Precision-minus-depth F is -0.17843 +/-0.07883 for D90 and -0.13330 +/-0.07509 for L92; neither clears three standard errors. '
        'D90 precision catches 0.95117 +/-0.16147 more than depth, but its own-start gain is unresolved. '
        'D90 depth improves F 0.37224 +/-0.07738 through ordinary cost savings 0.72510 +/-0.01305 while losing 0.72266 +/-0.16122 captures. '
        'No endpoint establishes an own-start capture or dark-capture gain. This trades precision against depth, with only two founder/run pairs; '
        'it does not isolate precision, match CPU, or establish memory or a more sophisticated algorithm.\n\n'
        'All six processes and five owned groups exited. [prelaunch/manifest.json](prelaunch/manifest.json) preserves all 176 prepared artifacts; '
        'all 79 released local and 35 production pins remain unchanged. [manifest.json](manifest.json) covers four native run directories, six raw confirmation rows, '
        'library bytes, process/resource receipts, independent reviews and figures. Twenty-one initial-search guarded evaluation calls retain penalties; '
        'all 3,072 raw confirmation statuses are zero. Per-life search ledgers were not retained.\n\n'
        'Packaging and offline analysis execute no new lives or kernel builds.\n')
    add(status, 'ARCHIVE.md')
    add(AUDIT / 'doc_claim_review.json', 'terminal_review/doc_claim_review.json')
    add(AUDIT / 'terminal_preflight.json', 'terminal_review/archive_preflight.json')
    add(AUDIT / 'actual_ready_mapping_review.json', 'terminal_review/actual_ready_mapping_review.json')
    for name, item in prior['artifacts'].items():
        if (plan['artifacts'].get(name, {}).get('sha256') != item['sha256']
                or a.sha(ARCHIVE / name) != item['sha256']):
            raise ValueError('prepared artifact changed or omitted: ' + name)
    a.write_archive(ARCHIVE, plan)
    output = AUDIT / 'public_terminal_reanalysis'
    env = dict(os.environ, PYTHONDONTWRITEBYTECODE='1', OPENBLAS_NUM_THREADS='1', OMP_NUM_THREADS='1', MKL_NUM_THREADS='1')
    execution = subprocess.run([sys.executable, str(ARCHIVE / 'analysis/analyze.py'), '--study', str(ARCHIVE), '--out', str(output)],
                               cwd='/', env=env, capture_output=True, text=True, check=True)
    (AUDIT / 'public_terminal_reanalysis_console.json').write_text(execution.stdout)
    summary = json.loads(execution.stdout)
    if (summary['status'] != 'complete'
            or (output / 'summary.json').read_bytes() != (STUDY / 'analysis_result/summary.json').read_bytes()):
        raise ValueError('portable complete summary differs')
    with np.load(output / 'paired_vectors.npz', allow_pickle=False) as left, np.load(STUDY / 'analysis_result/paired_vectors.npz', allow_pickle=False) as right:
        if set(left.files) != set(right.files) or len(left.files) != 450:
            raise ValueError('portable paired array names differ')
        for name in left.files:
            if left[name].shape != right[name].shape or left[name].dtype != right[name].dtype or left[name].tobytes() != right[name].tobytes():
                raise ValueError('portable paired array bytes differ: ' + name)
    expected = set(plan['artifacts']) | {'manifest.json', 'prelaunch/manifest.json'}
    actual = {str(p.relative_to(ARCHIVE)) for p in ARCHIVE.rglob('*') if p.is_file()}
    if actual != expected or a.sha(ARCHIVE / 'prelaunch/manifest.json') != PRELAUNCH_SHA:
        raise ValueError('exact manifest coverage or preparation changed')
    for name, item in plan['artifacts'].items():
        if a.sha(ARCHIVE / name) != item['sha256']:
            raise ValueError('copied terminal bytes differ: ' + name)
    files = {str((ARCHIVE / name).relative_to(ROOT)) for name in expected}
    def git_paths(*args):
        value = subprocess.run(['git', 'ls-files', *args, '-z', '--', str(ARCHIVE.relative_to(ROOT))],
                               cwd=ROOT, capture_output=True, text=True, check=True)
        return set(value.stdout.split('\0')) - {''}
    tracked, visible = git_paths(), git_paths('--others', '--exclude-standard')
    force = sorted(files - tracked - visible)
    (AUDIT / 'terminal_all_files.txt').write_text(''.join(name + '\n' for name in sorted(files)))
    (AUDIT / 'terminal_force_add_paths.txt').write_text(''.join(name + '\n' for name in force))
    receipt = {'status': 'verified_complete_portable_analysis', 'protocol_sha256': a.PROTOCOL_SHA,
               'prelaunch_manifest_sha256': PRELAUNCH_SHA, 'terminal_manifest_sha256': a.sha(ARCHIVE / 'manifest.json'),
               'copied_artifacts': len(plan['artifacts']), 'total_files': len(actual), 'prepared_artifacts_preserved': len(prior['artifacts']),
               'released_local_pins_unchanged': 79, 'released_production_pins_unchanged': 35,
               'cpu_seconds': budget['cpu_seconds'], 'research_lives': 19576, 'startup_validation_lives': 10,
               'new_lives': 0, 'new_compilations': 0, 'frozen_reader_unchanged': True,
               'public_summary_byte_identical': True, 'paired_arrays_byte_identical': 450,
               'paired_npz_byte_identical': a.sha(output / 'paired_vectors.npz') == PINS['analysis_result/paired_vectors.npz'],
               'exact_manifest_coverage': True, 'git_tracked': len(tracked), 'git_visible_untracked': len(visible),
               'git_force_add_required': force}
    (AUDIT / 'terminal_archive_verification.json').write_text(json.dumps(receipt, indent=2) + '\n')
    print(json.dumps(receipt, indent=2))


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--write', action='store_true')
    if parser.parse_args().write:
        run()
    else:
        print(json.dumps({'status': 'dry_run_no_outcome_reads', 'writes': False, 'simulation_calls': 0,
                          'compilation_calls': 0, 'requires': 'reviewed complete AB and root terminal clearance'}))
