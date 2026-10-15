"""Append the cleared complete AA run; default dry run performs no outcome reads.

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
STUDY = ROOT / 'outputs/autonomous_visibility_lateral_20261014'
ARCHIVE = ROOT / 'results/visibility_lateral_20261014'
PRELAUNCH_SHA = '3a9afd99c8881cd3750a385abea4f5fdf87d3ac29a7c2e5ca8119191227c4ca3'
READY_SHA = 'f19eb5720222c5e57e5e0f18e685898f9fc9377fa50635b03a7e73243f611ffe'
HELPER_SHA = 'fef076bddd75c3099a011d55a642f4c07065afd1331a0cf559171bce4488038f'
PINS = {'budget.json': '0d62b29e7cd96d70a583016c05ee6bcb5d72a596b67ea7497167492e960abd72', 'terminal_process_clearance.json': '6386f8d7201a6bfbf0911451c5a8b37624f2ef71078aeec52470f1247e4e45ea', 'terminal_review/raw_analysis_review.json': '71396165c1142522adf003722bf751265da94a974fdc291e73bd2d7e70253355', 'terminal_review/root_reanalysis.json': 'f1cb38504ef6b61a5160c1c76eca9250bcb0edb0bde4537c41a1f7a40281686d', 'analysis_result/summary.json': '9aae62226dfdacdcd1cc5f57acb72a75d79b635c95a9ca44e57946bb4456aa90', 'analysis_result/paired_vectors.npz': '85e35f495c2bda834c5c500f0606c28c444844ef99e7f62c01b7315407ff7243'}


def run():
    import numpy as np

    spec = importlib.util.spec_from_file_location('reviewed_AA_archive', AUDIT / 'archive.py')
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
    if len(ready['source_pins']) != 69 or len(ready['production_pins']) != 35:
        raise ValueError('released source closure differs')
    result = a.read(STUDY / 'analysis_result/summary.json')
    if (result.get('status') != 'complete' or result.get('protocol_sha256') != a.PROTOCOL_SHA
            or (result.get('research_lives'), result.get('startup_validation_lives'), result.get('total_lives')) != (2304, 2, 2306)
            or result['resources']['total_cpu_seconds'] != budget['cpu_seconds']):
        raise ValueError('independent complete analysis differs from terminal scope')
    prior = a.read(ARCHIVE / 'prelaunch/manifest.json')
    plan = a.make_plan(ROOT, STUDY, AUDIT, 'terminal')
    plan.update(status='complete_independently_reconciled', scientific_lives_completed=2306,
                research_lives=2304, validation_lives=2,
                compiled_libraries=len(list((STUDY / 'build-cache').rglob('*.so'))),
                cpu_seconds=budget['cpu_seconds'], scientific_outcomes_claimed=True,
                prelaunch_manifest_sha256=PRELAUNCH_SHA,
                scientific_scope='Six fixed original/Y/Z genotypes under normal, freeze and freeze+lateral_off. Conditional lateral communication helps frozen D90 tissue; the Z step reduces that capture-income contribution. Broad freeze and body differences prevent isolated memory or new-algorithm claims.')

    def add(path, relative):
        item = {'source': str(path), 'sha256': a.sha(path), 'bytes': path.stat().st_size,
                'origin': str(path.relative_to(ROOT))}
        if relative in plan['artifacts'] and plan['artifacts'][relative]['sha256'] != item['sha256']:
            raise ValueError('terminal destination collision: ' + relative)
        plan['artifacts'][relative] = item

    add(Path(__file__).resolve(), 'terminal_review/archive_terminal.py')
    status = AUDIT / 'ARCHIVE.md'
    status.write_text(
        '# AA terminal archive\n\n'
        f'AA completed 2,304 research lives and two existing ABI3 startup compatibility lives in {budget["cpu_seconds"]:.6f} CPU-seconds, including compilation and cleanup. '
        'All six original/Y/Z genotypes were measured on 128 shared fresh seeds under normal, freeze and freeze+lateral_off. '
        'Existing controls activate at age 512; accounting spans 544..1024.\n\n'
        'The [summary](analysis_result/summary.json) and [2,700 paired arrays](analysis_result/paired_vectors.npz) reproduce with '
        '`python analysis/analyze.py --study . --out NEW_DIRECTORY`. The frozen reader passed unchanged, and an independent raw reconstruction matched all 36 contrasts. '
        'All 2,304 research statuses are zero; all 768 frozen genotype-seed pairs retain matched cell composition and expected live-time integrals.\n\n'
        'Lateral sends help frozen D90 tissue: disabling them loses 2.602 / 3.133 / 1.766 mean captures in original/Y/Z roles. '
        'The Z-minus-Y change in this capture-income contribution is -1.42415 +/- 0.28322 F for D90 and an unresolved +0.49642 +/- 0.18665 F for L92. '
        'Neither Y step adds a resolved capture-income contribution. Broad freeze sharply increases L92 firing; different genotypes still develop different bodies. '
        'These conditional effects establish neither memory nor a new algorithm.\n\n'
        'All owned processes have exited. [prelaunch/manifest.json](prelaunch/manifest.json) preserves all 153 prepared artifacts; '
        'all 69 released local and 35 production pins remain unchanged. [manifest.json](manifest.json) covers raw rows, startup/library bytes, '
        'monitor/process receipts, independent reviews and figures. Frozen README/SCHEMA preparation wording is retained as historical evidence; '
        'this terminal status and the appended records describe the completed run.\n\n'
        'Packaging and offline analysis execute no new lives or kernel builds.\n')
    add(status, 'ARCHIVE.md')
    add(AUDIT / 'doc_claim_review.json', 'terminal_review/doc_claim_review.json')
    add(AUDIT / 'terminal_preflight.json', 'terminal_review/archive_preflight.json')
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
        if set(left.files) != set(right.files) or len(left.files) != 2700:
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
               'released_local_pins_unchanged': 69, 'released_production_pins_unchanged': 35,
               'cpu_seconds': budget['cpu_seconds'], 'research_lives': 2304, 'startup_validation_lives': 2,
               'new_lives': 0, 'new_compilations': 0, 'frozen_reader_unchanged': True,
               'public_summary_byte_identical': True, 'paired_arrays_byte_identical': 2700,
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
                          'compilation_calls': 0, 'requires': 'reviewed complete AA and root terminal clearance'}))
