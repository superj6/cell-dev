"""Record completed engineering evidence; no builds or simulation."""
import hashlib
import json
from pathlib import Path

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[1]
PATHS = [
    'src/life/'+name for name in (
        'spec.py', 'build.py', 'kernel.c', 'reference.py', 'readouts.py', 'probe.py', 'evaluate.py', 'analysis.py')
] + [
    'tests/'+name for name in (
        'test_life_spec_abi6.py', 'test_abi6_boundaries.py', 'test_abi6_kernel_reference.py', 'test_abi6_legacy.py',
        'test_checkpoint.py', 'test_abi5_kernel_boundaries.py', 'test_life_kernel_smoke.py')
] + [
    'results/atlas/play/'+name for name in (
        'lifesim.js', 'resource_patches_view.js', 'test_resource_patches.js', 'test_resource_patches_view.js',
        'bodies.json')
]


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


budgets = {p.parent.name: json.loads(p.read_text()) for p in sorted((HERE/'validation').glob('*/budget.json'))}
assert len(budgets) == 7
assert all(b['terminal_cleanup']['all_owned_groups_exited'] and
           b['terminal_cleanup']['all_worker_identities_exited'] and not b['running'] and not b['queued']
           for b in budgets.values())
final = dict(
    status='engineering_complete', source_pins={name: sha(ROOT/name) for name in PATHS},
    contract_sha256=sha(HERE/'DRAFT_CONTRACT.md'), archive_truth_path='validation/truth',
    archive_preview_paths=['resource_patches_preview.html'],
    source_validation=dict(default_pytest_passed=1086, default_pytest_fixture_style_failures=2,
                           corrected_affected_checks_passed=2, slow_tests_deselected=127,
                           C_boundary_cases=71, truth_cases=8, truth_C_full=8, truth_C_fast=8, truth_Python=8,
                           JS_patch_checks=20, JS_patch_advanced_lives=22, JS_patch_truth_lives=16,
                           new_UI_supplied_state_mounts=2, new_UI_simulator_calls=0,
                           real_browser_tested=False, ABI6_checkpoint_resume='passed'),
    runtime=dict(cpu_seconds=sum(b['cpu_seconds'] for b in budgets.values()),
                 wall_seconds=sum(b['wall_seconds'] for b in budgets.values()),
                 peak_owned_rss_bytes=max(b['peak_owned_rss_bytes'] for b in budgets.values()),
                 all_owned_processes_clear=True, batches=list(budgets),
                 allowance_cpu_seconds=1800, allowance_wall_seconds=3600,
                 note='Includes failed engineering commands; excludes static inspection/archive packaging.'),
    scientific_patch_lives=0, evolved_patch_behavior_established=False, information_payoff_established=False,
    hygiene=dict(ruff='passed', maintained_diff_check='passed'),
)
with (HERE/'finalization.json').open('x') as stream:
    json.dump(final, stream, indent=2, allow_nan=False)
    stream.write('\n')
print(json.dumps(final['runtime'], indent=2))
