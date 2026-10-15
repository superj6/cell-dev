"""Append the cleared complete AH run; default dry run performs no outcome reads.

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
STUDY = ROOT / 'outputs/autonomous_exploratory_reserve_20261014'
ARCHIVE = ROOT / 'results/exploratory_reserve_20261014'
PRELAUNCH_SHA = '9eb51e8aac3954d54fbb887844572585f84b1fa19aaba39e66312bac0392bf06'
READY_SHA = 'cbb5853a9409f6812fff0933424250566ba7392155c565518b103bf483e9e51a'
HELPER_SHA = 'ea4d952f4be659ff1d0ffb34bfe9da9797dbdd1cc2334495e0832b008f4efb08'
# Bound only after root terminal clearance and independent complete analysis.
PINS = {'budget.json': '24dadeb2d66bb4f4121c801534b40940cd9e1ff09dfbeafab244c9ff38a76ce6', 'terminal_process_clearance.json': '35e8ecbda7b332302406b57e88bea29151df9d48e140b0a7a865b4493b7fba7c', 'terminal_review/independent_terminal_raw_review.json': '6005f8066107f0427a2f60e9f905e134f005e2768029d320fd61e72371c5ff86', 'terminal_review/terminal_execution_review.json': 'ce3eb4916f58cbf08cba9cc24008c056e35dbdd444627fd5bcf4e9342891e021', 'analysis_result/summary.json': 'fc097ab9a104d0211351ab77bc88cce351dee8cba05f0f597c369de6d132aa26', 'analysis_result/paired_vectors.npz': '724478ce3c95c3cdce8f0de374738ef27b2a23f135b77741f91239b068487a16'}


def run():
    if not PINS:
        raise ValueError("terminal review pins are unset; no packaging before root clearance and final analysis")
    import numpy as np

    spec = importlib.util.spec_from_file_location('reviewed_AH_archive', AUDIT / 'archive.py')
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
    if len(ready['source_pins']) != 208 or len(ready['production_pins']) != 35:
        raise ValueError('released source closure differs')
    result = a.read(STUDY / 'analysis_result/summary.json')
    if (result.get('status') != 'complete' or result.get('protocol_sha256') != a.PROTOCOL_SHA
            or (result.get('research_lives'), result.get('startup_validation_lives'), result.get('total_lives')) != (9804, 6, 9810)
            or result['resources']['total_cpu_seconds'] != budget['cpu_seconds']):
        raise ValueError('independent complete analysis differs from terminal scope')
    prior = a.read(ARCHIVE / 'prelaunch/manifest.json')
    plan = a.make_plan(ROOT, STUDY, AUDIT, 'terminal')
    plan.update(status='complete_independently_reconciled', scientific_lives_completed=9810,
                research_lives=9804, validation_lives=6,
                compiled_libraries=len(list((STUDY / 'build-cache').rglob('*.so'))),
                cpu_seconds=budget['cpu_seconds'], scientific_outcomes_claimed=True,
                prelaunch_manifest_sha256=PRELAUNCH_SHA,
                scientific_scope='One matched control/reserve four-generation pair from fixed AE L92 in the unchanged ABI3 V persistent-target world; both final population rank-zero endpoints and the fixed start confirmed on512fresh shared seeds. External reserve is phenotype-independent and inactive in the final generation. One deliberately selected background and paired search do not estimate policy reliability or establish a memory mechanism.')

    def add(path, relative):
        item = {'source': str(path), 'sha256': a.sha(path), 'bytes': path.stat().st_size,
                'origin': str(path.relative_to(ROOT))}
        if relative in plan['artifacts'] and plan['artifacts'][relative]['sha256'] != item['sha256']:
            raise ValueError('terminal destination collision: ' + relative)
        plan['artifacts'][relative] = item

    add(Path(__file__).resolve(), 'terminal_review/archive_terminal.py')
    # The prospective ARCHIVE.md and all frozen evidence remain byte-exact.
    # Root-reviewed final prose is added under a separate filename after terminal authorization.
    add(AUDIT / 'TERMINAL_README.md', 'TERMINAL_README.md')
    for name in ('doc_claim_review.json', 'check_doc_claims.py', 'terminal_preflight.json', 'actual_ready_mapping_review.json',
                 'check_public_preparation.py', 'check_terminal_preflight.py', 'terminal_archive_plan.json', 'archive_verification.json',
                 'public_preparation_check.stdout.json', 'public_preparation_check.stderr.txt',
                 'terminal_copy_receipt.json'):
        add(AUDIT / name, 'terminal_review/' + name)
    for name, item in prior['artifacts'].items():
        if (plan['artifacts'].get(name, {}).get('sha256') != item['sha256']
                or a.sha(ARCHIVE / name) != item['sha256']):
            raise ValueError('prepared artifact changed or omitted: ' + name)
    canonical_count = 0
    for path in STUDY.rglob('*'):
        if not path.is_file() or any(part in a.SKIP for part in path.relative_to(STUDY).parts):
            continue
        name = str(path.relative_to(STUDY))
        relative = 'operations/' + name if name in a.OPERATIONS else name
        item = plan['artifacts'].get(relative, {})
        if item.get('sha256') != a.sha(path) or item.get('origin') != str(path.relative_to(ROOT)):
            raise ValueError('canonical origin mapping differs: ' + name)
        canonical_count += 1
    a.write_archive(ARCHIVE, plan)
    output = AUDIT / 'public_terminal_reanalysis'
    env = dict(os.environ, PYTHONDONTWRITEBYTECODE='1', OPENBLAS_NUM_THREADS='1', OMP_NUM_THREADS='1', MKL_NUM_THREADS='1')
    # Force every external scientific/production dependency to resolve inside
    # the public bundle; the frozen reader itself is unchanged.
    command = """import importlib.util, pathlib, sys
base = pathlib.Path(sys.argv[1]).resolve()
sys.path.insert(0, str(base / 'analysis'))
spec = importlib.util.spec_from_file_location('public_ah_reader', base / 'analysis/analyze.py')
m = importlib.util.module_from_spec(spec)
spec.loader.exec_module(m)
def archive_only(root, name):
    for folder in ('production', 'original'):
        path = m.inside(pathlib.Path(root) / folder, name)
        if path.is_file():
            return path
    raise FileNotFoundError('archive-only dependency absent: ' + name)
m.external = archive_only
sys.argv = ['analyze.py', '--study', str(base), '--out', sys.argv[2]]
m.main()
"""
    execution = subprocess.run([sys.executable, '-c', command, str(ARCHIVE), str(output)],
                               cwd='/', env=env, capture_output=True, text=True, check=True)
    (AUDIT / 'public_terminal_reanalysis_console.json').write_text(execution.stdout)
    summary = json.loads(execution.stdout)
    if (summary['status'] != 'complete'
            or (output / 'summary.json').read_bytes() != (STUDY / 'analysis_result/summary.json').read_bytes()):
        raise ValueError('portable complete summary differs')
    with np.load(output / 'paired_vectors.npz', allow_pickle=False) as left, np.load(STUDY / 'analysis_result/paired_vectors.npz', allow_pickle=False) as right:
        if set(left.files) != set(right.files) or len(left.files) != 219:
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
               'released_local_pins_unchanged': 208, 'released_production_pins_unchanged': 35,
               'cpu_seconds': budget['cpu_seconds'], 'research_lives': 9804, 'startup_validation_lives': 6,
               'new_lives': 0, 'new_compilations': 0, 'frozen_reader_unchanged': True,
               'public_summary_byte_identical': True, 'paired_arrays_byte_identical': 219,
               'paired_npz_byte_identical': a.sha(output / 'paired_vectors.npz') == PINS['analysis_result/paired_vectors.npz'],
               'archive_only_external_resolution': True, 'outside_repository_working_directory': '/',
               'exact_manifest_coverage': True, 'git_tracked': len(tracked), 'git_visible_untracked': len(visible),
               'canonical_files_exact_origin_mapped': canonical_count,
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
                          'compilation_calls': 0, 'requires': 'reviewed complete AH and root terminal clearance'}))
