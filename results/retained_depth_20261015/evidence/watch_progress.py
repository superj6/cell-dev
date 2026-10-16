"""Read AO progress and safety counters without displaying scientific outcomes."""
import json
from pathlib import Path

STUDY = Path(__file__).resolve().parents[1] / 'autonomous_retained_depth_20261015'
main = json.loads((STUDY / 'budget.json').read_text())
phase_path = STUDY / 'execution' / main['phase'] / 'budget.json'
phase = json.loads(phase_path.read_text()) if phase_path.exists() else {}
report = {'study_status': main['status'], 'phase': main['phase'], 'branches': {}}
for arm in ('unchanged', 'balanced'):
    path = STUDY / 'runs' / arm / 'curves.jsonl'
    lines = path.read_text().splitlines(keepends=True) if path.exists() else []
    rows = [json.loads(line) for line in lines if line.endswith('\n') and line.strip()]
    report['branches'][arm] = {
        'generations_completed': len(rows),
        **{key: sum(row[key] for row in rows)
           for key in ('pop_invalid', 'pop_mismatch', 'recheck_invalid')},
        'completion_marker_exists': (path.parent / 'search_complete.json').is_file(),
    }
report['active_phase'] = {key: phase.get(key) for key in (
    'status', 'cpu_seconds', 'wall_seconds', 'peak_owned_rss_bytes',
    'available_memory_bytes', 'reason', 'error', 'cleanup_error')}
report['complete_marker_exists'] = (STUDY / 'study_complete.json').is_file()
index_path = STUDY / 'row_index.json'
report['confirmation_rows_completed'] = len(json.loads(index_path.read_text())) if index_path.exists() else 0
report['monitor_stderr_bytes'] = (STUDY / 'monitor_stderr.txt').stat().st_size
if main['status'] != 'running':
    report['terminal_budget'] = {key: main.get(key) for key in (
        'status', 'cpu_seconds', 'wall_seconds', 'search_cpu_seconds',
        'confirmation_cpu_seconds', 'reason', 'error', 'cleanup_error')}
print(json.dumps(report, indent=2))
