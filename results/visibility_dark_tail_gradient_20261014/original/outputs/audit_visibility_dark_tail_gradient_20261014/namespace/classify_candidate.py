"""Classify AG candidate ranges and completed AF seed evidence; no reservation."""
from pathlib import Path
import hashlib
import io
import json
import re
import subprocess
import zipfile
import numpy as np

ROOT = Path(__file__).resolve().parents[3]
OUT = Path(__file__).resolve().parent
LOW, HIGH = 52_320_000, 52_350_000
AF = ROOT / 'outputs/autonomous_prediction_continuation_20261014'
PUBLIC = ROOT / 'results/prediction_continuation_20261014'


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def read(path):
    return json.loads(path.read_text())


def main():
    inventory = read(OUT / 'candidate_namespace_inventory.json')
    assert not inventory['NPZ_numeric_matches'] and not inventory['JSON_errors']
    allowed_fields = {'whole_blocks_half_open.0.1', 'whole_block_half_open.1', 'same_whole_blocks_half_open.0.1'}
    assert len(inventory['JSON_numeric_matches']) == 12
    assert all(item['value'] == LOW and item['field'] in allowed_fields
               and 'prediction_continuation_20261014' in item['path'] for item in inventory['JSON_numeric_matches'])
    assert inventory['historical_actual_matches_excluding_prior_endpoint'] == [LOW]
    stages = inventory['stage_seed_lists']
    assert stages == {'calibration': list(range(52320000, 52320002)),
                      'screen': list(range(52330000, 52330032)), 'confirm': list(range(52340000, 52340512))}
    candidate = set(sum(stages.values(), []))
    assert len(candidate) == 546 and 11 not in candidate
    errors = inventory['NPZ_errors']
    assert len(errors) == 8
    resolutions = []
    for number, error in enumerate(errors):
        path = ROOT / error['path']
        assert error['synthetic_fixture'] and error['error'] == 'BadZipFile: File is not a zip file'
        assert path == OUT.parent / f'test_tmp/test_acknowledged_artifact_tam{number}/confirmation_genotypes.npz'
        expected = {'altered': True} if number == 5 else {'frozen': 'confirmation_genotypes.npz'}
        assert read(path) == expected
        resolutions.append({'path': error['path'], 'sha256': sha(path), 'json_contents': expected,
            'classification': 'Known file-hash-only tamper-test JSON placeholder with an NPZ suffix; no seeds or genotype payload. Created by test_acknowledged_artifact_tamper_rejected.'})
    af_audit = read(AF / 'seed_audit.json')
    native = set(sum(af_audit['run_life_seeds'].values(), []))
    confirm = set(af_audit['confirmation_seeds'])
    assert len(native) == 128 and len(confirm) == 512 and not native & confirm
    assert not candidate & (native | confirm) and not any(LOW <= value < HIGH for value in native | confirm)
    raw_pairs = []
    for number in range(4):
        relative = f'confirmation/persistent/row_{number:04d}.npz'
        path, public = AF / relative, PUBLIC / relative
        assert sha(path) == sha(public)
        with zipfile.ZipFile(path) as archive:
            seeds = np.load(io.BytesIO(archive.read('seeds.npy')), allow_pickle=False)
            identity = json.loads(str(np.load(io.BytesIO(archive.read('identity.npy')), allow_pickle=False)))
        assert seeds.dtype == np.uint64 and seeds.tolist() == identity['seeds'] == af_audit['confirmation_seeds']
        raw_pairs.append({'canonical': str(path.relative_to(ROOT)), 'public': str(public.relative_to(ROOT)),
                          'sha256': sha(path), 'life_count': len(seeds)})
    native_recorded = {}
    for run in (53224, 53225):
        name = f'runs/s{run}/lineage.jsonl'
        path = AF / name
        assert sha(path) == sha(PUBLIC / name)
        # Extract only explicitly named seed arrays, never parse fitness/genetic-operation members.
        arrays = [json.loads(x) for x in re.findall(r'"seeds"\s*:\s*(\[[0-9, ]*\])', path.read_text())]
        actual = set(sum(arrays, []))
        assert len(arrays) == 8 and len(actual) == 28 and actual.issubset(af_audit['run_life_seeds'][str(run)])
        native_recorded[str(run)] = {'path': str(path.relative_to(ROOT)), 'sha256': sha(path),
            'recorded_generation_seed_arrays': arrays, 'generation_distinct_ids': 28,
            'full_declared_schedule': af_audit['run_life_seeds'][str(run)],
            'scope': 'Generation3+recheck4 IDs per generation are directly recorded; remaining periodic-validation/final IDs are bound by the complete64-ID registered native schedule and pinned production sources.'}
    older = {}
    for label, folder, count in (('AE', 'prediction_gradient', 546), ('AD', 'visibility_dark_tail_information', 515)):
        path = ROOT / f'outputs/autonomous_{folder}_20261014/seed_audit.json'
        seeds = read(path)['seeds']; union = set(sum(seeds.values(), []))
        assert len(union) == count and not union & candidate and not any(LOW <= value < HIGH for value in union)
        older[label] = {'seed_audit_path': str(path.relative_to(ROOT)), 'sha256': sha(path), 'unique_registered_ids': count}
    commit = '2e41e6976538f74a82ee6f44aac741c6c494304b'
    relative = str((PUBLIC / 'manifest.json').relative_to(ROOT))
    assert hashlib.sha256(subprocess.run(['git', 'show', commit + ':' + relative], cwd=ROOT,
        check=True, capture_output=True).stdout).hexdigest() == sha(PUBLIC / 'manifest.json')
    source_files = [Path(__file__), OUT / 'namespace_audit.py', OUT.parent / 'reader_source_review.json',
        ROOT / 'outputs/autonomous_visibility_dark_tail_gradient_20261014/test_source.py',
        ROOT / 'outputs/autonomous_visibility_dark_tail_gradient_20261014/prepare.py',
        OUT.parent / 'source_preparation_review.json', OUT.parent / 'independent_source_design_review.json']
    review = {'status': 'passed_candidate_pending_final_delta', 'registered': False, 'reserved': False,
        'seeds': stages, 'candidate_unique_life_ids': 546, 'native_run_seeds': [],
        'whole_blocks_half_open': inventory['whole_blocks_half_open'], 'base': 51000000, 'blocks': [132, 133, 134],
        'inventory_sha256': sha(OUT / 'candidate_namespace_inventory.json'),
        'history_references_sha256': sha(OUT / 'history_references.json'),
        'source_pins': {str(path.relative_to(ROOT)): sha(path) for path in source_files},
        'coverage': {key: inventory[key] for key in ('current_npz_paths', 'unchanged_npz_paths',
            'unchanged_seed_members_covered', 'baseline_unique_payloads_reopened', 'unique_payloads_total')},
        'actual_overlap_count': 0, 'real_NPZ_errors': 0, 'unresolved_errors': 0, 'JSON_errors': 0,
        'JSON_matches': inventory['JSON_numeric_matches'],
        'JSON_classification': 'All12 integer hits are AF block131 exclusive upper endpoint52320000, not a member or reservation.',
        'synthetic_errors_classified': resolutions,
        'text_match_sha256': sha(OUT / 'candidate_text_matches.txt'),
        'text_classification': ['AF audit/source/README copies name52320000 only as block131 exclusive upper endpoint.',
            'Other68-line source-query matches are fractional result substrings or hexadecimal hash fragments; no132/133/134 reservation is present.'],
        'AF_terminal_public_commit': commit, 'AF_terminal_manifest_sha256': sha(PUBLIC / 'manifest.json'),
        'AF_confirm_raw_public_pairs': raw_pairs, 'AF_native_recorded_seed_evidence': native_recorded,
        'AF_registered_native_unique': 128, 'AF_registered_confirmation_unique': 512,
        'AF_terminal_pins': {str((AF / name).relative_to(ROOT)): sha(AF / name)
            for name in ('protocol.json', 'registration.json', 'seed_audit.json', 'ready.json', 'budget.json', 'terminal_process_clearance.json')},
        'earlier_registered_schedule_checks': older,
        'intentional_reuse': {'screen': 'Same32fresh seeds across all130 retained parent/mutant rows.',
            'calibration': 'Same2fresh seeds across parent+row1 of both backgrounds.',
            'confirmation': 'Same512fresh seeds across all four fixed H/P roles, retaining duplicates.',
            'golden': 'One standardABI3 seed11/T200 full+fast pair; two intentional existing golden uses.'},
        'limits': ['Every distinct historical unchanged seed payload was reopened for these NEW ranges; earlier no-match conclusions were not reused.',
            'Changed/new NPZ seed-token members were scanned; stat+SHA payload equivalence is not a claim that full unchanged NPZ files were cryptographically rehashed.',
            'Full historical namespace verification needs17 committed repository objects referenced by exact path, commit and SHA; no network fetch or live substitute.',
            'No outcome/genotype arrays loaded by this seed audit. Synthetic malformed placeholders are explicitly classified.',
            'No AG native genetic seeds or draws are needed. Root registration and release remain separate.'],
        'simulation_calls': 0, 'compilation_calls': 0, 'genetic_draws': 0, 'genotype_copies': 0}
    (OUT / 'candidate_namespace_review.json').write_text(json.dumps(review, indent=2) + '\n')
    print(json.dumps({'status': review['status'], 'review_sha256': sha(OUT / 'candidate_namespace_review.json'),
        'inventory_sha256': review['inventory_sha256'], 'actual_overlap_count': 0, 'classified_fixture_errors': len(errors)}))


if __name__ == '__main__':
    main()
