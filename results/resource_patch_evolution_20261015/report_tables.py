"""Render complete saved-summary tables only after terminal completion; never simulate or build."""
from __future__ import annotations

import argparse
import hashlib
import json
import math
import resource
import signal
import time
from pathlib import Path

STUDY = Path(__file__).resolve().parent
ROLES = ('AO_start', 'mixed4', 'mixed8')
WORLDS = ('patch', 'pool', 'persistent', 'blink80_20', 'transfer')
CONTRASTS = ('mixed8_minus_AO_start', 'mixed8_minus_mixed4', 'mixed4_minus_AO_start')


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def read(path):
    return json.loads(path.read_text())


def fmt(record):
    mean, se = record['mean'], record['se']
    if not math.isfinite(mean) or not math.isfinite(se) or se < 0 or record['n'] != 512:
        raise ValueError('finite512-life summary statistic required')
    return f'{mean:.6f} ± {se:.6f}'


def table(headers, rows):
    return ['| ' + ' | '.join(headers) + ' |', '| ' + ' | '.join(['---'] * len(headers)) + ' |',
            *['| ' + ' | '.join(map(str, row)) + ' |' for row in rows], '']


def component_row(world, label, metrics, is_patch):
    keys = ('initial_income_contribution', 'refill_income_contribution', 'ordinary_cost_contribution',
            'guard_contribution', 'extinction_contribution')
    income = metrics['income_contribution']
    if is_patch:
        if not math.isclose(income['mean'], sum(metrics[k]['mean'] for k in keys[:2]), abs_tol=1e-8, rel_tol=1e-9):
            raise ValueError('patch food origins do not reconstruct total income')
        other = dict(n=512, mean=0., se=0.)
    else:
        if any(metrics[k]['mean'] != 0 or metrics[k]['se'] != 0 for k in keys[:2]):
            raise ValueError('older world has patch-specific food origins')
        other = income
    total = other['mean'] + math.fsum(metrics[k]['mean'] for k in keys)
    if not math.isclose(total, metrics['F']['mean'], abs_tol=1e-8, rel_tol=1e-9):
        raise ValueError('food/cost contributions do not reconstruct productionF')
    return [world, label, *(fmt(metrics[k]) for k in keys[:2]), fmt(other),
            *(fmt(metrics[k]) for k in keys[2:]), fmt(metrics['F'])]


def generate(study):
    started, cpu_start = time.monotonic(), time.process_time()
    # Check completion markers before opening outcomes or the saved summary.
    budget, complete, measurement = (read(study / name) for name in
                                    ('budget.json', 'study_complete.json', 'measurement_complete.json'))
    if any(item['status'] != 'complete' for item in (budget, complete, measurement)):
        raise ValueError('complete budget, study and measurement markers required before report reading')
    if complete['total_calls'] != 28222 or measurement['research_lives'] != 7680 or measurement['rows'] != 15:
        raise ValueError('fixed complete scientific inventory required')
    for name in ('TABLES.md', 'tables_receipt.json'):
        if (study / name).exists():
            raise ValueError('fresh saved-summary output required: ' + name)
    protocol, summary = read(study / 'protocol.json'), read(study / 'summary.json')
    protocol_sha = sha(study / 'protocol.json')
    if (tuple(protocol['roles']) != ROLES or tuple(protocol['worlds']) != WORLDS or
            summary['status'] != 'complete' or summary['research_lives'] != 7680 or
            summary['paired_life_clusters'] != 512 or
            any(item['protocol_sha256'] != protocol_sha for item in (budget, complete, measurement, summary)) or
            summary['row_index_sha256'] != sha(study / 'row_index.json') or
            summary['endpoints_sha256'] != sha(study / 'endpoints.json')):
        raise ValueError('summary/protocol/endpoint binding differs')
    lines = ['# Complete saved-summary tables', '',
        'All entries are means ± SE over512 shared life clusters. F means production fitness, including the',
        'established extinction surcharge; nativeF is shown separately. Physical cost is energy per life.',
        'Generation8 is primary; generation4 is observational. Tables include all prespecified worlds/endpoints.',
        'These tables make no threshold, memory, admission or broad-generalization claim.', '',
        '## Absolute acquisition and fitness', '']
    keys = ('F', 'native_F', 'captures', 'total_patch_initial_harvest', 'total_patch_refill_harvest')
    rows = [[world, role, *(fmt(summary['absolute'][world][role][key]) for key in keys)]
            for world in WORLDS for role in ROLES]
    lines += table(['World', 'Endpoint', 'ProductionF', 'NativeF', 'Captures', 'Initial food', 'Refill food'], rows)
    lines += ['## Absolute costs, misses and retained outcomes', '']
    keys = ('physical_cost', 'misses', 'total_patch_empty', 'patch_geometric_misses', 'guarded', 'extinct')
    rows = [[world, role, *(fmt(summary['absolute'][world][role][key]) for key in keys)]
            for world in WORLDS for role in ROLES]
    lines += table(['World', 'Endpoint', 'Physical cost', 'Misses', 'Empty clicks', 'Geometric misses',
                    'Guard fraction', 'Extinct fraction'], rows)
    lines += ['## All fixed paired comparisons', '', 'Differences use paired whole-life values, not independent SEs.', '']
    keys = ('F', 'captures', 'total_patch_initial_harvest', 'total_patch_refill_harvest',
            'physical_cost', 'misses', 'total_patch_empty')
    rows = [[world, contrast, *(fmt(summary['paired'][world][contrast][key]) for key in keys)]
            for world in WORLDS for contrast in CONTRASTS]
    lines += table(['World', 'Comparison', 'ΔProductionF', 'ΔCaptures', 'ΔInitial', 'ΔRefill',
                    'ΔPhysical cost', 'ΔMisses', 'ΔEmpty clicks'], rows)
    lines += ['## Older-world capture retention', '',
        'Margin = candidate captures −0.9×AO_start captures. Ratios are descriptive ratios of means;',
        'paired margin uncertainty is reported without converting this diagnostic into a selection gate.', '']
    rows = []
    for world in ('pool', 'persistent', 'blink80_20'):
        for role in ('mixed4', 'mixed8'):
            record = summary['old_world_retention'][world][role + '_vs_AO_start']
            ratio = record['mean_capture_ratio']
            margin = record['retained_90_percent_margin']
            rows.append([world, role, fmt(record['captures_difference']),
                'undefined' if ratio is None else f'{100*ratio:.3f}%', fmt(margin),
                f"[{margin['lower_3se']:.6f}, {margin['upper_3se']:.6f}]"])
    lines += table(['World', 'Endpoint', 'ΔCaptures vs start', 'Capture ratio', '90% margin',
                    'Margin mean±3SE'], rows)
    for kind, labels, title in (('absolute', ROLES, 'Absolute food/cost contributions to F'),
                                ('paired', CONTRASTS, 'Paired food/cost contributions to F gains')):
        lines += ['## ' + title, '',
            'Signed mean contributions sum to productionF (or its paired difference). Their SEs are correlated;',
            'the total SE comes directly from F and is not the sum or quadrature of component SEs.',
            'Other-food income is ordinary target income in older worlds; it is identically zero in patch worlds.', '']
        rows = [component_row(world, label, summary[kind][world][label],
                              bool(protocol['worlds'][world]['world']['patch_count']))
                for world in WORLDS for label in labels]
        lines += table(['World', 'Endpoint/comparison', 'Initial foodF', 'Refill foodF', 'Other foodF',
                        '−Physical costF', '−GuardF', '−ExtinctionF', 'ProductionF'], rows)
    lines += ['## Source binding', '', f'- Protocol SHA256: `{protocol_sha}`.',
              f"- Summary SHA256: `{sha(study / 'summary.json')}`.",
              '- This is saved-summary formatting only: zero additional lives, builds or random draws.', '']
    with (study / 'TABLES.md').open('x') as stream:
        stream.write('\n'.join(lines))
    receipt = dict(status='complete_saved_summary_tables', protocol_sha256=protocol_sha,
        summary_sha256=sha(study / 'summary.json'), tables_sha256=sha(study / 'TABLES.md'),
        generator_sha256=sha(Path(__file__)), row_index_sha256=sha(study / 'row_index.json'),
        budget_sha256=sha(study / 'budget.json'), study_complete_sha256=sha(study / 'study_complete.json'),
        measurement_complete_sha256=sha(study / 'measurement_complete.json'),
        world_endpoint_rows=15, paired_rows=15, retention_rows=6, decomposition_rows=30,
        cpu_seconds=time.process_time()-cpu_start, wall_seconds=time.monotonic()-started,
        peak_rss_bytes=resource.getrusage(resource.RUSAGE_SELF).ru_maxrss*1024,
        additional_lives=0, builds=0, random_draws=0)
    with (study / 'tables_receipt.json').open('x') as stream:
        json.dump(receipt, stream, indent=2, allow_nan=False)
        stream.write('\n')
    print(json.dumps(receipt))


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--study', type=Path, default=STUDY)
    parser.add_argument('--write', action='store_true')
    args = parser.parse_args()
    if args.write:
        resource.setrlimit(resource.RLIMIT_CPU, (10, 10))
        resource.setrlimit(resource.RLIMIT_AS, (1024**3, 1024**3))
        signal.alarm(30)
        available = next(int(line.split()[1])*1024 for line in Path('/proc/meminfo').read_text().splitlines()
                         if line.startswith('MemAvailable:'))
        if available < 4*1024**3:
            raise ValueError('4GiB host headroom required')
        generate(args.study.resolve())
    else:
        print('Source only; no outcomes read. Use --write after complete markers and saved summary exist.')
