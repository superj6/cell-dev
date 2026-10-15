"""Append the cleared complete AC run; default dry run performs no outcome reads.

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
STUDY = ROOT / 'outputs/autonomous_visibility_flash_gradient_20261014'
ARCHIVE = ROOT / 'results/visibility_flash_gradient_20261014'
PRELAUNCH_SHA = '07c5224224219e945d5c53a8e2da61c0e84f475a4e93c6a5f35887e89aca69e4'
READY_SHA = 'ce9d784dc19cc9d69fd8880d1d3762862f7912f29623098ec9edcdc0cfe972d6'
HELPER_SHA = '8d989d6af08b936a9d5b36f176687e66c166c09bb41312a5a7eca738c220ddd7'
# Bound only after root terminal clearance and independent complete analysis.
PINS = {
    'budget.json': '75107349982d8551ec914feb9223c3f15e118dc9b3b6e2dc9694c108d7baa5b2',
    'terminal_process_clearance.json': '5af01429104cae73b5982ec5aa9d94ca58126d46ef5c0891dd6883f225368ce3',
    'terminal_review/raw_analysis_review.json': '0d893d836e28c642dabea0ded897463d08aadfad488fc293485ee511d03a9f61',
    'terminal_review/root_reanalysis.json': 'f3d0c5377c32c727734c90159b4191d133f6ef6cee4034b13f08bb3f50e5684f',
    'analysis_result/summary.json': 'f70691e072f070d0dee8e3bdf55e1c78c409e6d3dd4e746118c651ba499b10ed',
    'analysis_result/paired_vectors.npz': '6509e8ab4c9ddeb10655090d612608ec4de56d0ba4c34db2ecdde21f653f51ff',
}


def run():
    if not PINS:
        raise ValueError("terminal review pins are unset; no packaging before root clearance and final analysis")
    import numpy as np

    spec = importlib.util.spec_from_file_location('reviewed_AC_archive', AUDIT / 'archive.py')
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
    if len(ready['source_pins']) != 204 or len(ready['production_pins']) != 35:
        raise ValueError('released source closure differs')
    result = a.read(STUDY / 'analysis_result/summary.json')
    if (result.get('status') != 'complete' or result.get('protocol_sha256') != a.PROTOCOL_SHA
            or (result.get('research_lives'), result.get('validation_lives'), result.get('total_lives')) != (10304, 10, 10314)
            or result['resources']['total_cpu_seconds'] != budget['cpu_seconds']):
        raise ValueError('independent complete analysis differs from terminal scope')
    prior = a.read(ARCHIVE / 'prelaunch/manifest.json')
    plan = a.make_plan(ROOT, STUDY, AUDIT, 'terminal')
    plan.update(status='complete_independently_reconciled', scientific_lives_completed=10314,
                research_lives=10304, validation_lives=10,
                compiled_libraries=len(list((STUDY / 'build-cache').rglob('*.so'))),
                cpu_seconds=budget['cpu_seconds'], scientific_outcomes_claimed=True,
                prelaunch_manifest_sha256=PRELAUNCH_SHA,
                scientific_scope='Retained complete Y panels screened in flash; six fixed P/B/H roles confirmed in both flash and blink with shared seeds. Two fixed backgrounds; no isolated memory or prediction claim.')

    def add(path, relative):
        item = {'source': str(path), 'sha256': a.sha(path), 'bytes': path.stat().st_size,
                'origin': str(path.relative_to(ROOT))}
        if relative in plan['artifacts'] and plan['artifacts'][relative]['sha256'] != item['sha256']:
            raise ValueError('terminal destination collision: ' + relative)
        plan['artifacts'][relative] = item

    add(Path(__file__).resolve(), 'terminal_review/archive_terminal.py')
    status = AUDIT / 'ARCHIVE.md'
    status.write_text(
        '# AC terminal archive\n\n'
        f'AC completed 10,304 research lives, eight flash calibration lives and two existing ABI3 compatibility lives in {budget["cpu_seconds"]:.6f} CPU-seconds, including compilation and cleanup. '
        'The unchanged two 65-row Y panels were screened in flash; parent, historical blink winner and new flash winner remain explicit for each background in both worlds, including duplicates.\n\n'
        'The frozen [summary](analysis_result/summary.json) and [1,200 paired arrays](analysis_result/paired_vectors.npz) reproduce with '
        '`python analysis/analyze.py --study . --out NEW_DIRECTORY`. Recorded-operation replay verifies the original 130 panel rows without fresh draws or simulated lives.\n\n'
        'Both selected flash mutants improve fitness over their parents. D90 saves costs while losing captures; L92’s primary capture change narrowly misses the fixed three-SE threshold. Its secondary H−B capture interaction resolves while the corresponding fitness interaction does not. '
        'These fixed-background comparisons describe world-specific payoff. Flash and blink jointly differ in cue strength, schedule and placement resets; the comparison does not isolate memory or prediction. '
        'Capture income, ordinary costs and paid guard/extinction charges remain separate in every contrast.\n\n'
        'All owned processes/groups are covered by the root terminal clearance. [prelaunch/manifest.json](prelaunch/manifest.json) preserves all 285 prepared artifacts; '
        'all 204 released local and 35 production pins remain unchanged. [manifest.json](manifest.json) covers all 146 raw rows, startup library bytes, '
        'phase bindings, process/resource receipts, independent reviews and final figures.\n\n'
        'Packaging and offline analysis execute no new lives or kernel builds.\n')
    add(status, 'ARCHIVE.md')
    add(AUDIT / 'doc_claim_review.json', 'terminal_review/doc_claim_review.json')
    add(AUDIT / 'check_doc_claims.py', 'terminal_review/check_doc_claims.py')
    add(AUDIT / 'terminal_preflight.json', 'terminal_review/archive_preflight.json')
    add(AUDIT / 'actual_ready_mapping_review.json', 'terminal_review/actual_ready_mapping_review.json')
    for name, item in prior['artifacts'].items():
        if (plan['artifacts'].get(name, {}).get('sha256') != item['sha256']
                or a.sha(ARCHIVE / name) != item['sha256']):
            raise ValueError('prepared artifact changed or omitted: ' + name)
    a.write_archive(ARCHIVE, plan)
    output = AUDIT / 'public_terminal_reanalysis'
    env = dict(os.environ, PYTHONDONTWRITEBYTECODE='1', OPENBLAS_NUM_THREADS='1', OMP_NUM_THREADS='1', MKL_NUM_THREADS='1')
    # Force every external scientific/production dependency to resolve inside
    # the public bundle; the frozen reader itself is unchanged.
    command = """import importlib.util, pathlib, sys
base = pathlib.Path(sys.argv[1]).resolve()
sys.path.insert(0, str(base / 'analysis'))
spec = importlib.util.spec_from_file_location('public_ac_reader', base / 'analysis/analyze.py')
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
        if set(left.files) != set(right.files) or len(left.files) != 1200:
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
               'released_local_pins_unchanged': 204, 'released_production_pins_unchanged': 35,
               'cpu_seconds': budget['cpu_seconds'], 'research_lives': 10304, 'startup_validation_lives': 10,
               'new_lives': 0, 'new_compilations': 0, 'frozen_reader_unchanged': True,
               'public_summary_byte_identical': True, 'paired_arrays_byte_identical': 1200,
               'paired_npz_byte_identical': a.sha(output / 'paired_vectors.npz') == PINS['analysis_result/paired_vectors.npz'],
               'archive_only_external_resolution': True, 'outside_repository_working_directory': '/',
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
                          'compilation_calls': 0, 'requires': 'reviewed complete AC and root terminal clearance'}))
