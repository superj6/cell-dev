"""Recompute fixed trace readouts from saved tables without simulating lives."""
from __future__ import annotations

import argparse
import json
import shutil
from dataclasses import asdict
from pathlib import Path

import numpy as np

import measure as M

HERE = Path(__file__).resolve().parent
SEARCH_KEYS = ('silent_time', 'silent_distance', 'total_distance', 'capture_zone_sample_share',
               'clicks', 'captures', 'clicks_per_capture')
RELAY_KEYS = ('rec', 'tonic', 'resid', 'unknown', 'deep', 'relayed', 'relayed_2plus', 'rec_other_col')


def stats(values):
    if len(values) != 4:
        raise ValueError("need exactly four fixed-life values")
    if any(value is None for value in values):
        return dict(n=len(values), mean=None, se=None, reason='at least one undefined per-life measurement')
    a = np.asarray(values, dtype=np.float64)
    if a.shape != (4,) or not np.isfinite(a).all():
        raise ValueError('need four finite fixed-life values')
    return dict(n=4, mean=float(a.mean()), se=float(a.std(ddof=1) / 2))


def subtract(a, b):
    if len(a) != len(b):
        raise ValueError("paired arrays differ in length")
    return [None if x is None or y is None else x-y for x, y in zip(a, b)]


def arrays(readouts, label, start):
    records = [readouts[(label, seed)] for seed in M.SEEDS]
    values = {'search.' + key: [item['search'][str(start)][key] for item in records] for key in SEARCH_KEYS}
    for group in ('K', 'M', 'all'):
        for key in RELAY_KEYS:
            values['relay.' + group + '.' + key] = []
            for item in records:
                groups = {row['cls']: row for row in item['relay'][str(start)]['lives'][0]['groups']}
                values['relay.' + group + '.' + key].append(groups.get(group, {}).get(key))
    return values


def audit(study):
    from src.life import spec
    from src.life.readouts import json_safe

    protocol = json.loads((study / 'protocol.json').read_text())
    budget_path = study / ('budget.json' if (study / 'budget.json').exists() else 'operations/budget.json')
    budget = json.loads(budget_path.read_text())
    if budget['status'] != 'complete' or budget.get('running') or budget.get('queued'):
        raise ValueError('study not complete')
    cpu = float(budget['cpu_seconds'])
    if (not np.isfinite(cpu) or not 0 <= cpu < 1800 or budget.get('cap_cpu_seconds') != 1800
            or budget.get('exit_code') != 0):
        raise ValueError('budget or process failed')
    ready_path = study / ('ready.json' if (study / 'ready.json').exists() else 'operations/ready.json')
    ready = json.loads(ready_path.read_text())
    if ready != budget['ready']:
        raise ValueError('budget readiness differs')
    for name, digest in ready['files'].items():
        if M.sha(study / name) != digest:
            raise ValueError('released file changed: ' + name)
    for name, digest in protocol['source_identity'].items():
        if M.sha(M.ROOT / name) != digest:
            raise ValueError('readout source differs: ' + name)
    for name, item in protocol['inputs'].items():
        if M.sha(study / name) != item['sha256']:
            raise ValueError('input changed')
    report = json.loads((study / 'measurement/report.json').read_text())
    expected = [(label, seed) for seed in M.SEEDS for label in M.LABELS]
    manifest = json.loads((study / 'measurement/manifest.json').read_text())
    if (manifest['protocol_sha256'] != M.sha(study / 'protocol.json') or manifest['ready'] != ready
            or manifest['numerical_identity'] != protocol['numerical_identity']
            or manifest['order'] != [list(item) for item in expected]):
        raise ValueError('measurement manifest differs')
    actual = [(row['label'], row['seed']) for row in report['lives']]
    if report['status'] != 'complete' or actual != expected:
        raise ValueError('trace coverage/order differs')
    if report['reference_lives'] != 12 or report['kernel_validation_lives'] != 12:
        raise ValueError('life counts differ')
    readouts = {}
    for row in report['lives']:
        path = study / 'measurement' / row['trace']
        if M.sha(path) != row['sha256']:
            raise ValueError('raw trace changed')
        trace, ledger = M.load_trace(path)
        if trace.meta['seed'] != row['seed'] or trace.meta['org'] != row['label']:
            raise ValueError('trace identity differs')
        if asdict(trace.meta['world']) != asdict(spec.world('catch_speck_l4', **M.WORLD)):
            raise ValueError('trace world differs')
        statuses = M.validate_match(trace, ledger)
        if statuses != row['status_counts'] or row['ledger_columns_bitwise_equal'] != 57:
            raise ValueError('trace validation receipt differs')
        observed = json_safe(M.describe(trace))
        saved = json.loads((study / 'measurement' / row['readout']).read_text())
        if observed != saved:
            raise ValueError('saved readout does not reproduce')
        readouts[(row['label'], row['seed'])] = observed
    summary = dict(status='complete', reference_lives=12, kernel_validation_lives=12,
                   worker_cpu_seconds=budget['cpu_seconds'], seeds=M.SEEDS, world=M.WORLD,
                   paired_descriptions={}, per_genotype={},
                   estimand='mean of per-life values; clicks_per_capture is a mean of per-life ratios',
                   limitations=protocol['limitations'], significance_tests='none; four descriptive seeds')
    for start in (0, 800):
        per_label = {label: arrays(readouts, label, start) for label in M.LABELS}
        summary['per_genotype'][str(start)] = {
            label: {key: stats(value) for key, value in items.items()} for label, items in per_label.items()}
        summary['paired_descriptions'][str(start)] = {
            label: {key: stats(subtract(value, per_label[M.LABELS[0]][key])) for key, value in items.items()}
            for label, items in per_label.items() if label != M.LABELS[0]}
    return summary


def render(summary):
    lines = ['# Fixed continuation traces', '',
             'Twelve fixed T1536 fast-POOL reference traces, with twelve C validation lives. Every one of the 57',
             'ledger columns matches bitwise. Raw event tables reproduce all saved readouts without simulation.', '',
             'Four shared descriptive seeds per genotype; the values below are paired means ± SE over those four',
             'lives. Clicks per capture averages per-life ratios, rather than pooling counts. No significance or',
             'new-algorithm claim is made.', '',
             '| Descendant minus row38, full life | D51089 | D51090 |', '|---|---:|---:|']
    def display(value):
        return 'undefined' if value['mean'] is None else f"{value['mean']:+.4f} ± {value['se']:.4f}"
    for key in SEARCH_KEYS:
        vals = [summary['paired_descriptions']['0'][label]['search.' + key] for label in M.LABELS[1:]]
        lines.append('| ' + key + ' | ' + ' | '.join(display(value) for value in vals) + ' |')
    lines += ['', 'Full and800..1536 search/relay descriptions are in summary.json; each original per-life',
              'readout and raw table is under measurement/. Largest-input paths omit subthreshold integration.',
              'Silence movement alone does not show that silence is used as evidence. Tissues keep their different',
              'growth, footprints and state. Missing ratios remain null, with no missing-life deletion.', '',
              f"Budget: {summary['worker_cpu_seconds']:.6f} of1,800 worker CPU-seconds; one simulation worker.", '',
              'Recompute with `.venv/bin/python results/traces_20261014/analyze.py --check` from a checkout with',
              'the pinned src files. The shared source archive preserves their bytes; this tool is not standalone.', '']
    return '\n'.join(lines)


def export(study, target):
    summary = audit(study)
    if (target / 'measurement').exists():
        raise ValueError('completed archive already exists')
    prelaunch = target / 'prelaunch'
    prelaunch.mkdir(exist_ok=False)
    for path in list(target.iterdir()):
        if path == prelaunch:
            continue
        dest = prelaunch / path.name
        shutil.copytree(path, dest) if path.is_dir() else shutil.copyfile(path, dest)
    for name in ('analyze.py', 'test_analysis.py', 'measure.py', 'run_budgeted.py', 'protocol.json', 'PREREG.md'):
        shutil.copyfile(study / name, target / name)
    shutil.copytree(study / 'measurement', target / 'measurement')
    (target / 'operations').mkdir()
    for name in ('budget.json', 'ready.json', 'run.log'):
        shutil.copyfile(study / name, target / 'operations' / name)
    (target / 'summary.json').write_text(json.dumps(summary, indent=2, allow_nan=False) + '\n')
    (target / 'README.md').write_text(render(summary))
    if audit(target) != summary:
        raise ValueError('public archive does not reproduce working summary')
    artifacts = {str(path.relative_to(target)): dict(sha256=M.sha(path), bytes=path.stat().st_size)
                 for path in sorted(target.rglob('*')) if path.is_file() and path != target / 'provenance.json'}
    (target / 'provenance.json').write_text(json.dumps(dict(status='complete', artifacts=artifacts), indent=2)+'\n')
    return summary


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--export', type=Path)
    parser.add_argument('--check', action='store_true')
    args = parser.parse_args()
    if args.export:
        summary = export(HERE, args.export)
    else:
        summary = audit(HERE)
        if args.check:
            provenance = json.loads((HERE / 'provenance.json').read_text())
            for name, item in provenance['artifacts'].items():
                if M.sha(HERE / name) != item['sha256'] or (HERE / name).stat().st_size != item['bytes']:
                    raise ValueError('archive file changed: ' + name)
            if summary != json.loads((HERE / 'summary.json').read_text()):
                raise ValueError('summary differs')
            if render(summary) != (HERE / 'README.md').read_text():
                raise ValueError('README differs')
    print(json.dumps(dict(status='verified', reference_lives=summary['reference_lives'])))


if __name__ == '__main__':
    main()
