"""Metadata/source-only AH preparation review; never prepare or evaluate a life."""
from __future__ import annotations

import ast
import hashlib
import importlib.util
import json
import sys
import xml.etree.ElementTree as ET
from pathlib import Path

sys.dont_write_bytecode = True
AUDIT = Path(__file__).resolve().parent
ROOT = AUDIT.parents[1]
STUDY = ROOT / 'outputs/autonomous_exploratory_reserve_20261014'
AF = ROOT / 'results/prediction_continuation_20261014'
AE = ROOT / 'results/prediction_gradient_20261014'


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def save(path, value):
    with path.open('x') as stream:
        stream.write(json.dumps(value, indent=2, allow_nan=False) + '\n')


def function(tree, name):
    return ast.dump(next(x for x in tree.body if isinstance(x, ast.FunctionDef) and x.name == name),
                    include_attributes=False)


def main():
    absent = ['protocol.json', 'registration.json', 'seed_audit.json', 'inputs', 'configs', 'initialization',
              'preparation_claim.json', 'generation_claim.json', 'ready.json', 'attempt.json', 'budget.json',
              'runs', 'confirmation', 'logs', 'build-cache']
    assert all(not (STUDY / name).exists() for name in absent)
    spec = importlib.util.spec_from_file_location('ah_source_prepare', STUDY / 'prepare.py')
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    protocol = json.loads((AE / 'protocol.json').read_text())
    summary = json.loads((AE / 'analysis_result/summary.json').read_text())
    assert sha(AE / 'protocol.json') == module.AE_PROTOCOL and summary['status'] == 'complete'
    rates, pins = module.measured_costs(AE, protocol, summary)
    projection = module.cost_projection(rates)
    assert projection['feasible']
    assert not any(name == 'src' or name.startswith('src.') for name in sys.modules)
    cost = {'status': 'passed_source_only', 'study': 'AH exploratory reserve',
            'source_pins': {str((AE / name).relative_to(ROOT)): digest for name, digest in pins.items()},
            'AE_protocol_sha256': sha(AE / 'protocol.json'),
            'AE_summary_sha256': sha(AE / 'analysis_result/summary.json'),
            'retained_rows': 65, 'historical_lives_per_row': 32,
            'accessed': 'Timing, identity, seeds, index, dtype and shape; no scientific outcome values or genotype arrays.',
            'rates_cpu_per_life': rates, 'maximum_row': max(range(65), key=rates.__getitem__),
            'projection': projection, 'simulation_calls': 0, 'compiled_libraries': 0, 'genetic_draws': 0,
            'limitation': 'Historical same-world timing and conservative allowances are not bounds for new offspring.'}
    save(AUDIT / 'historical_cost_review.json', cost)
    unchanged = ('scoring.py', 'common.py', 'numerical.py', 'world_contract.py')
    for name in unchanged:
        assert (STUDY / name).read_bytes() == (AF / name).read_bytes()
    lifecycle = ('proc_table', 'consumed_cpu', 'enable_subreaper', 'child_limit', 'send_signal',
                 'cleanup_group', 'cleanup', 'interrupt', 'process_identity', 'phase_limit',
                 'budget_reason', 'resource_clearance')
    current = ast.parse((STUDY / 'run_budgeted.py').read_text())
    original = ast.parse((AF / 'run_budgeted.py').read_text())
    assert all(function(current, name) == function(original, name) for name in lifecycle)
    suite = ET.parse(AUDIT / 'source_tests_final.xml').getroot().find('testsuite')
    assert suite.attrib['tests'] == '20' and suite.attrib['errors'] == suite.attrib['failures'] == '0'
    sources = {str(path.relative_to(STUDY)): sha(path) for path in sorted(STUDY.iterdir()) if path.is_file()}
    record = {'status': 'passed_source_only_unregistered', 'producer_source_pins': sources,
              'historical_cost_review_sha256': sha(AUDIT / 'historical_cost_review.json'),
              'source_origins_sha256': sha(AUDIT / 'source_origins.json'),
              'unchanged_AF_helper_bytes': list(unchanged), 'unchanged_AF_lifecycle_function_ASTs': list(lifecycle),
              'tests': {'command': 'PYTHONDONTWRITEBYTECODE=1 .venv/bin/python -m pytest '
                        'outputs/autonomous_exploratory_reserve_20261014/test_source.py -q '
                        '--basetemp=outputs/audit_exploratory_reserve_20261014/test_tmp_final '
                        '--junitxml=outputs/audit_exploratory_reserve_20261014/source_tests_final.xml',
                        'passed': 20, 'junit_sha256': sha(AUDIT / 'source_tests_final.xml'),
                        'log_sha256': sha(AUDIT / 'source_tests_final.log'),
                        'ruff_sha256': sha(AUDIT / 'ruff_final.log'),
                        'scope': 'Synthetic evaluator, source ASTs and pure metadata only; no C lives.'},
              'checks': ['Original control recheck output and tie RNG unchanged, including ties.',
                         'Protected shortlist/survivor exclusion and full-rank ordering; final generation ordinary.',
                         'All three exact ranking inputs and tie states durably recorded.',
                         'Synthetic interrupted/restored parent and RNG state matches uninterrupted execution.',
                         'One original identity call; adapter/policy bound through config and extended identity.',
                         'Exact life/resource counts and first-preparation refusal.',
                         'Metadata-only all-65 historical cost gate; no fixed-body success condition.'],
              'absent_paths': absent, 'prepared_initial_populations': 0, 'simulation_calls': 0,
              'compiled_libraries': 0, 'genetic_draws': 0, 'production_source_edits': 0,
              'limitations': ['Independent reader and namespace reviews remain separate release prerequisites.',
                              'One paired search does not estimate policy reliability.',
                              'No raw ledger is retained for every native search life.',
                              'Source-only readiness does not authorize preparation or execution.']}
    save(AUDIT / 'producer_source_review.json', record)
    print(json.dumps({'status': record['status'], 'source_files': len(sources),
                      'review_sha256': sha(AUDIT / 'producer_source_review.json'),
                      'cost_sha256': sha(AUDIT / 'historical_cost_review.json'),
                      'projection': projection}, indent=2))


if __name__ == '__main__':
    main()
