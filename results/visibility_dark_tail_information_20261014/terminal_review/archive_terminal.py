"""Append the cleared complete AD run; default dry run performs no outcome reads.

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
STUDY = ROOT / 'outputs/autonomous_visibility_dark_tail_information_20261014'
ARCHIVE = ROOT / 'results/visibility_dark_tail_information_20261014'
PRELAUNCH_SHA = 'ac74fdfd50c8434efb1b7600980088ca09ac42a0792148c8fd4a7adb601b8b47'
READY_SHA = '9dce23cb43535eddee8d73e43cfd4db33dcd6d02a9b54e4bfbe4ffbd223f964f'
HELPER_SHA = 'd1630762a677fa62b6799ebdabf29efe86855e6bea9b3b5f3b9fd2b8814227d1'
# Bound only after root terminal clearance and independent complete analysis.
PINS = {
    'budget.json': 'efde24e31dffa6c8569b47ebab24739905e1e6605efeb662b0c36bf75c0915c2',
    'terminal_process_clearance.json': '38b58dbc1d22b7822dc54c8fe6835b8cb5fb58c8ee868d0b8446afc1a57bedae',
    'terminal_review/independent_terminal_raw_review.json': '1c98e5c1735d7ed99c1e1521edf06e3195ffdd544ad195d240f22b4592ad3309',
    'analysis_result/summary.json': '7f8bd355cc6cdc6417c351a5be381f226e712a37865673cc102fad1a63ae52ea',
    'analysis_result/paired_vectors.npz': '96a340fbb48af933c1963c623f093b454a757987e6bbae47b75dcd816c29d276',
}
EXPECTED_ARRAY_COUNT = 836


def run():
    if not PINS or EXPECTED_ARRAY_COUNT is None:
        raise ValueError("terminal review pins are unset; no packaging before root clearance and final analysis")
    import numpy as np

    spec = importlib.util.spec_from_file_location('reviewed_AD_archive', AUDIT / 'archive.py')
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
    if len(ready['source_pins']) != 140 or len(ready['production_pins']) != 56:
        raise ValueError('released source closure differs')
    result = a.read(STUDY / 'analysis_result/summary.json')
    if (result.get('status') != 'complete' or result.get('protocol_sha256') != a.PROTOCOL_SHA
            or (result.get('research_lives'), result.get('simulation_calls')) != (6656, 6732)
            or result.get('validation', {}).get('simulation_calls') != 76
            or result['resources']['total_cpu_seconds'] != budget['cpu_seconds']):
        raise ValueError('independent complete analysis differs from terminal scope')
    prior = a.read(ARCHIVE / 'prelaunch/manifest.json')
    plan = a.make_plan(ROOT, STUDY, AUDIT, 'terminal')
    plan.update(status='complete_independently_reconciled', scientific_lives_completed=6732,
                research_lives=6656, validation_lives=76,
                compiled_libraries=len(list((STUDY / 'build-cache').rglob('*.so'))) + len(list((STUDY / 'validation/build').rglob('*.so'))),
                cpu_seconds=budget['cpu_seconds'], scientific_outcomes_claimed=True,
                prelaunch_manifest_sha256=PRELAUNCH_SHA,
                scientific_scope='Fully dark flash information diagnostic using thirteen retained X2 instruments and unchanged bodies. Only world low amplitude and the I/B physical-description parameter change to zero; no evolved behavior or isolated memory claim.')

    def add(path, relative):
        item = {'source': str(path), 'sha256': a.sha(path), 'bytes': path.stat().st_size,
                'origin': str(path.relative_to(ROOT))}
        if relative in plan['artifacts'] and plan['artifacts'][relative]['sha256'] != item['sha256']:
            raise ValueError('terminal destination collision: ' + relative)
        plan['artifacts'][relative] = item

    add(Path(__file__).resolve(), 'terminal_review/archive_terminal.py')
    status = AUDIT / 'TERMINAL_README.md'
    status.write_text(
        '# AD complete: information still pays after the flash becomes fully dark\n\n'
        'The retained information instrument beats the better whole reflex by **4.672776 ± .095271 F** and **9.310547 ± .199257 captures** on 512 paired lives. '
        'The broad model and idle-action ablations lose .964021 ± .097439 and 3.647503 ± .089657 F, respectively. The model effect is below the separate 1-F magnitude threshold. '
        'Information-payoff and do-less checks pass; this does not establish an evolved algorithm, isolated memory or local attainability. See the frozen [summary](analysis_result/summary.json) and [figure](figures/information_payoff.png).\n\n'
        f'All **6,732 calls** completed in **{budget["cpu_seconds"]:.6f} CPU-seconds**: 6,656 research, 70 scratch validation, four production bridge and two recorded identity lives. '
        'All 6,730 retained raw statuses are zero. Validation used 57.698988 CPU-seconds. The three recorded leaders and two owned groups exited; nested identity/compiler children are accounted through those groups. '
        'The unchanged reader and independent raw review reproduce all **836 paired arrays**. No new lives or builds were used for packaging.\n\n'
        '[prelaunch/manifest.json](prelaunch/manifest.json) preserves all 249 prospective artifacts; all 140 local and 56 production release pins remain unchanged. '
        'The archive retains the six new runtime libraries, generated sources, complete rows, root release/clearance checks and independent review. The separate older bridge library remains provenance only. '
        'Run `python analysis/analyze.py --study . --out NEW_DIRECTORY` for offline scientific reanalysis. Full historical namespace proof additionally requires the five committed objects explicitly listed in '
        '[NAMESPACE_PROVENANCE.md](NAMESPACE_PROVENANCE.md); scientific inputs are bundled and the portability check disables live-source fallback.\n')
    add(status, 'TERMINAL_README.md')
    add(AUDIT / 'doc_claim_review.json', 'terminal_review/doc_claim_review.json')
    if (AUDIT / 'check_doc_claims.py').is_file():
        add(AUDIT / 'check_doc_claims.py', 'terminal_review/check_doc_claims.py')
    for name in ('release_study.py', 'root_release_receipt.json', 'check_public_preparation.py',
                 'archive_verification.json', 'public_preparation_check.stdout.json', 'public_preparation_check.stderr.txt'):
        add(AUDIT / name, 'terminal_review/' + name)
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
spec = importlib.util.spec_from_file_location('public_ad_reader', base / 'analysis/analyze.py')
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
        if set(left.files) != set(right.files) or len(left.files) != EXPECTED_ARRAY_COUNT:
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
               'released_local_pins_unchanged': 140, 'released_production_pins_unchanged': 56,
               'cpu_seconds': budget['cpu_seconds'], 'research_lives': 6656, 'startup_validation_lives': 76,
               'new_lives': 0, 'new_compilations': 0, 'frozen_reader_unchanged': True,
               'public_summary_byte_identical': True, 'paired_arrays_byte_identical': EXPECTED_ARRAY_COUNT,
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
                          'compilation_calls': 0, 'requires': 'reviewed complete AD and root terminal clearance'}))
