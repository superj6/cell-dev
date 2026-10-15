"""Append the cleared complete Z run; default dry run performs no outcome reads.

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
STUDY = ROOT / 'outputs/autonomous_visibility_continuation_20261014'
ARCHIVE = ROOT / 'results/visibility_continuation_20261014'
PRELAUNCH_SHA = '01d407c2a5a5cd387026d7941cfe2145849fafd967f11f950306b91adc1edd8d'
READY_SHA = 'ff38bbbecf3f7257bcdb2dc7dbe5231cb7fda97361b1cc3704546b53c49d15d5'
HELPER_SHA = 'c2fd99e075d44422a8ea7a1424b78820c4a02ad90aa08ebbf2bc47b59c4b9c2d'
PINS = {
    'budget.json': '60d8116811b2181b81d6eec55391953754376d938821de7727a365ebbbbd24cb',
    'terminal_process_clearance.json': '77cacb5c504c1c8164c94aa2eead5dddc6547552e71e3aafcbb1432958d161f8',
    'terminal_review/raw_analysis_review.json': 'c283a8d04f68a6460ed4e506032dcced09302db89107918b06026646fb5ab189',
    'terminal_review/native_replay.json': 'f19c75f18d086f2e3fe7a79e1dc320a798b14d736fda29859ff3718bb0cdb841',
    'terminal_review/root_reanalysis.json': '67ee7935e23822e2740837a139656076a86c49114605e6c471b2cc55cf74890d',
    'analysis_result/summary.json': '018afd5f2a51ac776c0125848abca90efbf8c22ec80c140fe9aec5263431049d',
    'analysis_result/paired_vectors.npz': '92f1d341bff7c8cde27e3a490f49059e2206a4f9ba85b066d6c6b9316ce4048b',
}


def run():
    import numpy as np

    spec = importlib.util.spec_from_file_location('reviewed_Z_archive', AUDIT / 'archive.py')
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
    if len(ready['source_pins']) != 97 or len(ready['production_pins']) != 35:
        raise ValueError('released source closure differs')
    result = a.read(STUDY / 'analysis_result/summary.json')
    if (result.get('status') != 'complete' or result.get('protocol_sha256') != a.PROTOCOL_SHA
            or (result.get('research_lives'), result.get('startup_validation_lives'), result.get('total_lives')) != (11340, 6, 11346)
            or result['resources']['total_cpu_seconds'] != budget['cpu_seconds']):
        raise ValueError('independent complete analysis differs from terminal scope')
    prior = a.read(ARCHIVE / 'prelaunch/manifest.json')
    plan = a.make_plan(ROOT, STUDY, AUDIT, 'terminal')
    plan.update(status='complete_independently_reconciled', scientific_lives_completed=11346,
                research_lives=11340, validation_lives=6,
                compiled_libraries=len(list((STUDY / 'build-cache').rglob('*.so'))),
                cpu_seconds=budget['cpu_seconds'], scientific_outcomes_claimed=True,
                prelaunch_manifest_sha256=PRELAUNCH_SHA,
                scientific_scope='Two fixed four-generation conditional lineages; fitness gains mainly reduce ordinary costs, without established capture-algorithm or memory improvement.')

    def add(path, relative):
        item = {'source': str(path), 'sha256': a.sha(path), 'bytes': path.stat().st_size,
                'origin': str(path.relative_to(ROOT))}
        if relative in plan['artifacts'] and plan['artifacts'][relative]['sha256'] != item['sha256']:
            raise ValueError('terminal destination collision: ' + relative)
        plan['artifacts'][relative] = item

    add(Path(__file__).resolve(), 'terminal_review/archive_terminal.py')
    status = AUDIT / 'ARCHIVE.md'
    status.write_text(
        '# Z terminal archive\n\n'
        f'Z completed 11,340 research lives and six existing ABI3 startup compatibility lives in {budget["cpu_seconds"]:.6f} CPU-seconds, including compilation and cleanup. '
        'Two fixed Y-selected lineages each received four native generations; six original, starting and final genotypes then received 512 fresh paired lives.\n\n'
        'The [summary](analysis_result/summary.json) and [450 paired arrays](analysis_result/paired_vectors.npz) reproduce with '
        '`python analysis/analyze.py --study . --out NEW_DIRECTORY`. The frozen reader passed unchanged. '
        'Recorded genetic operations and shortlist ranking reproduce both final populations; no random draws or life simulations are replayed.\n\n'
        'Both continuations improved fitness mainly through lower ordinary costs. Neither primary capture change is positive beyond three standard errors; '
        'the L92 continuation reduced low-light captures. This does not establish memory, prediction or a more sophisticated capture algorithm. '
        'Life-level uncertainty does not estimate reliability across independent evolutionary searches.\n\n'
        'All owned processes have exited. [prelaunch/manifest.json](prelaunch/manifest.json) preserves all 186 prepared artifacts; '
        'all 97 released local and 35 production source pins remain unchanged. [manifest.json](manifest.json) covers the appended native checkpoints/logs, '
        'six raw confirmation rows, binaries, resource receipts, independent reviews and figures. Search summaries retain eight initial-evaluation guards; '
        'all 3,072 raw confirmation statuses are zero. Per-life search/periodic-validation/final-diagnostic ledgers were not retained.\n\n'
        'Packaging and offline analysis execute no new lives or kernel builds.\n')
    add(status, 'ARCHIVE.md')
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
    (AUDIT / 'terminal_force_add_paths.txt').write_text(''.join(name + '\n' for name in force))
    receipt = {'status': 'verified_complete_portable_analysis', 'protocol_sha256': a.PROTOCOL_SHA,
               'prelaunch_manifest_sha256': PRELAUNCH_SHA, 'terminal_manifest_sha256': a.sha(ARCHIVE / 'manifest.json'),
               'copied_artifacts': len(plan['artifacts']), 'total_files': len(actual), 'prepared_artifacts_preserved': len(prior['artifacts']),
               'released_local_pins_unchanged': 97, 'released_production_pins_unchanged': 35,
               'cpu_seconds': budget['cpu_seconds'], 'research_lives': 11340, 'startup_validation_lives': 6,
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
                          'compilation_calls': 0, 'requires': 'reviewed complete Z and root terminal clearance'}))
