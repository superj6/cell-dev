"""Record narrow source/test evidence for AM; no scientific input or engine calls."""
import ast
import hashlib
import json
from pathlib import Path
import xml.etree.ElementTree as ET

ROOT = Path(__file__).resolve().parents[2]
AUDIT = Path(__file__).resolve().parent
STUDY = ROOT / 'outputs/autonomous_capture_value_selection_20261015'
AL = ROOT / 'outputs/autonomous_retention_selection_20261015'

def sha(p):
    return hashlib.sha256(p.read_bytes()).hexdigest()

def funcs(p):
    return {n.name: ast.dump(n) for n in ast.parse(p.read_text()).body if isinstance(n, ast.FunctionDef)}

unchanged = {}
for file, names in {
    'analyze.py': ['identical', 'stats', 'prices', 'physical_costs', 'validate_row', 'reconstruct', 'verify_startup'],
    'measure.py': ['parent_check', 'validate_search_state', 'check_visibility_truth'],
    'native_replay.py': ['sha', 'raw_sha', 'definitions', 'initial_population', 'replay_first'],
}.items():
    old, new = funcs(AL/file), funcs(STUDY/file)
    assert all(old[n] == new[n] for n in names)
    unchanged[file] = names
assert (AL/'replay_ops.py').read_bytes() == (STUDY/'replay_ops.py').read_bytes()
old = (AL/'native_replay.py').read_text().replace('persistent_control', 'current_value').replace(
    'balanced_mixture', 'high_value').replace('AL_recorded_ops', 'AM_recorded_ops')
assert old == (STUDY/'native_replay.py').read_text()
suite = ET.parse(AUDIT/'reader_tests.xml').getroot().find('testsuite')
assert int(suite.attrib['tests']) == 12
assert all(int(suite.attrib[k]) == 0 for k in ('failures', 'errors', 'skipped'))
owned = ['measure.py','analyze.py','native_replay.py','replay_ops.py']
result = {
 'status':'approved_source_only',
 'study':'AM capture-value selection',
 'reader_sources': {n:sha(STUDY/n) for n in owned},
 'source_origins': {str((AL/n).relative_to(ROOT)):sha(AL/n) for n in owned},
 'producer_interfaces_reviewed': {n:sha(STUDY/n) for n in ['selection.py','search.py','population_loader.py','common.py']},
 'exact_function_AST_reuse':unchanged,
 'exact_file_reuse':['replay_ops.py'],
 'native_helper_diff':'Only paired arm labels and import-module label change; original imported-population reference remains row zero.',
 'coverage':{'roles':['AI_control_start','AL_mixture_start','current_value_final','high_value_final'],
   'confirmation_rows':16,'confirmation_lives':8192,'native_research_lives':20556,
   'startup_lives':8,'total_calls':28756,'contrast_groups':54,'metrics_per_group':75,
   'retention_pairs':7,'retention_vectors':14,'paired_arrays':4064},
 'scientific_checks':[
   'All confirmation physics and capture reward remain the original R_cap500; selection identity permits only arm-specific gen reward500/2000.',
   'Both generation4 rank0 endpoints and both references freeze before fresh confirmation; duplicate bytes retain all four role slots.',
   'Two co-primary high-minus-current capture effects require strict unrounded lower3SE>0 in both POOL and persistent.',
   'Each endpoint versus AL-mixture start is reported separately; relative advantage cannot imply own-start gain.',
   'Seven fixed paired conventional90% retention comparisons remain separate from strict capture gains.',
   'Phase CPU is cumulative; sequential10800/7200/3600 caps and5400wall plus4GiBRSS/8GiBaddress/4GiBavailable checked.',
   'First256 genetic rows replay from recorded operations only; no genetic draws or engine calls.'
 ],
 'resolved_peer_finding': {
   'finding':'Inherited load_rows coverage still expected three roles despite four-role measurement.',
   'resolution':'Require range(len(ROLES)) and exact16-row matrix; in-memory complete16row/8192life regression and missing-fourth-role rejection added.',
   'history_file':'history/analyze.before_four_role_coverage_fix.py',
   'history_sha256':sha(AUDIT/'history/analyze.before_four_role_coverage_fix.py')},
 'tests': {'tests':12,'failures':0,'errors':0,'skipped':0,
   'source_sha256':sha(AUDIT/'test_confirmation_reader.py'),
   'junit_sha256':sha(AUDIT/'reader_tests.xml'),'log_sha256':sha(AUDIT/'reader_tests.log')},
 'limitations':['One evolutionary pair;512 confirmation lives are environment replicates, not evolutionary replicates.',
   'Raw search ledgers and exact initial ranking/tie evidence are not complete; full recorded genetic replay remains a separate terminal audit.',
   'Current preparation is source only; root prepare/monitor and actual input bindings remain pending.'],
 'engines_imported':False,'simulations':0,'genetic_draws':0,'inputs_copied':False,
}
(AUDIT/'reader_source_review.json').write_text(json.dumps(result,indent=2)+'\n')
print(json.dumps({'receipt_sha256':sha(AUDIT/'reader_source_review.json'),'sources':result['reader_sources']}))
