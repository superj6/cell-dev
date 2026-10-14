"""Read-only, completed D/G/L selection diagnostic. No simulator imports or calls."""
from __future__ import annotations

import argparse
import csv
import hashlib
import json
from pathlib import Path

import numpy as np
import yaml

STUDIES = {
    'D': ('results/continuation_20261013', (51089, 51090)),
    'G': ('results/structural_20261013', (51089, 51090)),
    'L': ('results/s7_continuation_20261014', (51891, 51892)),
}
CAVEATS = [
    'Every candidate was shortlisted using its initial three-life mean; the observed score changes are conditional.',
    'Four recheck lives use fresh shared seeds at the same T. World difficulty and common seeds correlate candidates.',
    'Repeated and related genomes, sequential selection, and varying T prevent treating candidate rows as independent.',
    'D and G use matched run/life seeds; their records are not independent replicates.',
    'Logged changed counts use the recheck shortlist ranking, not the separate earlier one-stage tie draw.',
    'Recorded survivor order and pooled fitness are authoritative; saved stage means are only a consistency audit.',
    'Missing per-life scores prevent an exact pooling-error bound; the reconstruction tolerance is empirical.',
    'Exact top-score sets are shown among logged candidates; a full tied set may extend beyond a recorded cutoff.',
    'Mean, median, RMS and rank summaries describe conditional disagreement, not an unconditional noise sigma or SE.',
    'No individual training-life scores are in these lineage records; per-genotype life variance is not recoverable.',
    'Parent or leader turnover does not establish improved fresh fitness or equal-compute search efficiency.',
    'No active P outcomes, research simulations, new protocol, source changes, or new selection policy were used.',
]


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def read_json(path):
    return json.loads(Path(path).read_text())


def write_json(path, value):
    Path(path).write_text(json.dumps(value, indent=2, allow_nan=False) + '\n')


def need(condition, message):
    if not condition:
        raise ValueError(message)


def describe(values):
    x = np.asarray(values, dtype=np.float64)
    need(x.ndim == 1 and x.size > 0 and np.isfinite(x).all(), 'finite nonempty descriptor input')
    return dict(n=int(x.size), mean=float(x.mean()), median=float(np.median(x)),
                rms=float(np.sqrt(np.mean(x * x))), mean_absolute=float(np.mean(abs(x))),
                minimum=float(x.min()), maximum=float(x.max()),
                p10=float(np.quantile(x, .1)), p90=float(np.quantile(x, .9)))


def average_ranks(values):
    x = np.asarray(values)
    # Equality on the recorded means; no arbitrary index ordering within a tie.
    return np.array([1 + np.sum(x < v) + .5 * (np.sum(x == v) - 1) for v in x], dtype=float)


def rank_diagnostics(base, repeat):
    a, b = np.asarray(base), np.asarray(repeat)
    ra, rb = average_ranks(a), average_ranks(b)
    rho = float(np.corrcoef(ra, rb)[0, 1]) if np.std(ra) and np.std(rb) else None
    i, j = np.triu_indices(len(a), 1)
    da, db = a[i] - a[j], b[i] - b[j]
    strict = (da != 0) & (db != 0)
    return dict(spearman_average_ties=rho, pair_count=len(i),
                tied_base_pairs=int(np.sum(da == 0)), tied_recheck_pairs=int(np.sum(db == 0)),
                strict_comparable_pairs=int(strict.sum()),
                strict_reversed_pairs=int(np.sum(strict & (np.sign(da) != np.sign(db)))))


def generation(study, run, row, curve):
    rc = row['recheck']
    ids, survivors = rc['ids'], row['survivors']
    a, b, actual = (np.asarray(x, dtype=np.float64) for x in (rc['F_base'], rc['F_recheck'], row['fitness']))
    need(len(ids) == len(set(ids)) == 64 and len(survivors) == len(set(survivors)) == 32, 'candidate counts')
    need(a.shape == b.shape == (64,) and actual.shape == (32,), 'score shapes')
    need(all(np.isfinite(x).all() for x in (a, b, actual)), 'finite saved fitness')
    need(np.all(np.diff(a) <= 0) and np.all(np.diff(actual) <= 0), 'recorded descending ranks')
    need(rc['key'] == 'all', 'pooled selection policy')
    need(len(row['seeds']) == 3 and len(rc['seeds']) == 4
         and len(set(row['seeds'] + rc['seeds'])) == 7, 'seven distinct within-generation seeds')
    need(set(survivors) <= set(ids), 'survivors must be shortlisted')
    need(row['gen'] == curve['gen'] and row['T'] == curve['T'], 'curve generation/T match')
    positions = {v: i for i, v in enumerate(ids)}
    picked = np.array([positions[v] for v in survivors])
    pooled = (3 * a + 4 * b) / 7
    # Tolerance is an audit/ambiguity bound, never used to invent a rank or identify an exact tie.
    tol = 64 * np.finfo(np.float64).eps * max(1., float(np.max(abs(pooled))), float(np.max(abs(actual))))
    error = float(np.max(abs(pooled[picked] - actual)))
    need(error <= tol, 'saved mean pooling mismatch')
    nonpicked = np.array([i for i in range(64) if i not in set(picked)])
    need(float(pooled[nonpicked].max()) <= float(actual[-1]) + 2 * tol, 'unselected strict score exceeds cutoff')
    changed = 32 - len(set(survivors) & set(ids[:32]))
    need(changed == rc['changed'] == curve['recheck_changed'], 'recorded parent changes mismatch')
    need(curve['best_id'] == survivors[0] and curve['fitness'] == actual[0], 'curve leading candidate mismatch')
    for key, expected in [('recheck_F_base', a[picked].mean()), ('recheck_F', b[picked].mean()),
                          ('mean_fitness', actual.mean())]:
        need(abs(curve[key] - expected) <= tol, f'curve {key} mismatch')
    need(curve['recheck_k'] == 64, 'curve shortlist count')
    base_top = [ids[i] for i in np.flatnonzero(a == a[0])]
    pooled_top = [survivors[i] for i in np.flatnonzero(actual == actual[0])]
    top_complete = actual[-1] < actual[0]
    shared_top = sorted(set(base_top) & set(pooled_top))
    # If the recorded cutoff is below the maximum, every pooled maximum must have survived.
    # An unselected base leader is bounded by that recorded cutoff, without reconstructing its score.
    base_top_upper_bounds = [float(actual[survivors.index(v)]) if v in survivors else float(actual[-1])
                             for v in base_top]
    strict_top_displacement = not shared_top and bool(top_complete)
    displacement_margin = float(actual[0] - max(base_top_upper_bounds)) if strict_top_displacement else None
    if strict_top_displacement:
        top_relation = 'strict_displacement'
    elif shared_top:
        top_relation = 'overlap_with_exact_recorded_top_set'
    else:
        top_relation = 'cutoff_incomplete_top_set'
    winner_position = positions[survivors[0]]
    winner_base = a[winner_position]
    elapsed = [float(curve[k]) for k in ('t_eval', 't_recheck')]
    need(all(np.isfinite(x) and x >= 0 for x in elapsed) and sum(elapsed) > 0, 'elapsed evaluation times')
    output = dict(study=study, run=run, gen=row['gen'], T=row['T'], changed_parents=changed,
                  changed_fraction=changed / 32, base_first_id=ids[0], pooled_first_id=survivors[0],
                  leader_identity_changed=ids[0] != survivors[0], base_top_ids=base_top,
                  recorded_pooled_top_ids=pooled_top, pooled_top_set_complete=bool(top_complete),
                  base_top_set_may_extend_past_shortlist=bool(a[-1] == a[0]),
                  top_sets_overlap_ids=shared_top, top_relation=top_relation,
                  strict_displacement_recorded_margin_lower_bound=displacement_margin,
                  initial_first_survives=ids[0] in survivors,
                  any_initial_top_survives=bool(set(base_top) & set(survivors)),
                  final_first_in_initial_top=survivors[0] in base_top,
                  final_first_base_recorded_rank=winner_position + 1,
                  final_first_base_rank_min=1 + int(np.sum(a > winner_base)),
                  final_first_base_rank_max=int(np.sum(a >= winner_base)),
                  base_parent_cutoff_tied=bool(a[31] == a[32]),
                  pooled_parent_cutoff_ambiguous=bool(np.any(abs(pooled[nonpicked] - actual[-1]) <= 2 * tol)),
                  pooled_reconstruction_max_abs_error=error, pooled_numerical_audit_tolerance=tol,
                  recheck_minus_base=describe(b - a), rank=rank_diagnostics(a, b),
                  base_elapsed_seconds=elapsed[0], recheck_elapsed_seconds=elapsed[1],
                  recheck_elapsed_fraction=elapsed[1] / sum(elapsed),
                  initial_population_guard_fraction=curve['pop_guard'],
                  initial_population_invalid_fraction=curve['pop_invalid'],
                  recheck_invalid_fraction=curve['recheck_invalid'])
    candidates = []
    for i, genome_id in enumerate(ids):
        candidates.append(dict(study=study, run=run, gen=row['gen'], T=row['T'], genome_id=genome_id,
                               base_recorded_rank=i + 1, F_base=float(a[i]), F_recheck=float(b[i]),
                               F_recheck_minus_base=float(b[i] - a[i]),
                               F_pooled_approx=float(pooled[i]), selected=genome_id in survivors,
                               selected_rank=survivors.index(genome_id) + 1 if genome_id in survivors else None,
                               F_pooled_recorded=float(actual[survivors.index(genome_id)])
                               if genome_id in survivors else None))
    return output, candidates


def aggregate(rows, candidates):
    changed = [r['changed_parents'] for r in rows]
    correlations = [r['rank']['spearman_average_ties'] for r in rows
                    if r['rank']['spearman_average_ties'] is not None]
    a = sum(r['base_elapsed_seconds'] for r in rows)
    b = sum(r['recheck_elapsed_seconds'] for r in rows)
    comparable = sum(r['rank']['strict_comparable_pairs'] for r in rows)
    reversed_pairs = sum(r['rank']['strict_reversed_pairs'] for r in rows)
    return dict(generations=len(rows), candidate_pairs=len(candidates), parent_slots=32 * len(rows),
                replaced_parent_slots=sum(changed), replaced_parent_fraction=sum(changed) / (32 * len(rows)),
                changed_parent_count=describe(changed), generations_with_parent_change=sum(x > 0 for x in changed),
                leader_identity_changes=sum(r['leader_identity_changed'] for r in rows),
                strict_top_displacements=sum(r['top_relation'] == 'strict_displacement' for r in rows),
                top_set_overlap_generations=sum(bool(r['top_sets_overlap_ids']) for r in rows),
                top_set_ambiguous_generations=sum(r['top_relation'] == 'cutoff_incomplete_top_set' for r in rows),
                initial_top_tied_generations=sum(len(r['base_top_ids']) > 1 for r in rows),
                recorded_pooled_top_tied_generations=sum(len(r['recorded_pooled_top_ids']) > 1 for r in rows),
                incomplete_pooled_top_sets=sum(not r['pooled_top_set_complete'] for r in rows),
                identity_changes_with_top_set_overlap=sum(r['leader_identity_changed']
                                                         and bool(r['top_sets_overlap_ids']) for r in rows),
                minimum_strict_displacement_recorded_margin_lower_bound=min(
                    (r['strict_displacement_recorded_margin_lower_bound'] for r in rows
                     if r['strict_displacement_recorded_margin_lower_bound'] is not None), default=None),
                initial_first_survives=sum(r['initial_first_survives'] for r in rows),
                any_initial_top_survives=sum(r['any_initial_top_survives'] for r in rows),
                final_first_in_initial_top=sum(r['final_first_in_initial_top'] for r in rows),
                final_first_base_rank=describe([r['final_first_base_recorded_rank'] for r in rows]),
                generations_with_base_parent_cutoff_tie=sum(r['base_parent_cutoff_tied'] for r in rows),
                generations_with_pooled_cutoff_ambiguity=sum(r['pooled_parent_cutoff_ambiguous'] for r in rows),
                recheck_minus_base=describe([c['F_recheck_minus_base'] for c in candidates]),
                within_generation_spearman=describe(correlations) if correlations else None,
                strict_comparable_pairs=comparable, strict_reversed_pairs=reversed_pairs,
                strict_pair_reversal_fraction=reversed_pairs / comparable if comparable else None,
                base_elapsed_seconds=a, recheck_elapsed_seconds=b, recheck_elapsed_fraction=b / (a + b),
                max_pooled_reconstruction_error=max(r['pooled_reconstruction_max_abs_error'] for r in rows))


def verify_archive(root):
    # Gate before reading outcome-bearing files. These are the three fixed completed public archives only.
    budget = read_json(root / 'operations/budget.json')
    need(budget['status'] == 'complete' and not budget.get('running') and not budget.get('queued'),
         'completed empty-budget gate')
    manifest = read_json(root / 'provenance.json')
    need(manifest.get('status', 'complete') == 'complete', 'archive completion status')
    for rel, expected in manifest['artifacts'].items():
        file = root / rel
        need(file.is_file() and file.stat().st_size == expected['bytes'] and sha(file) == expected['sha256'],
             f'archive artifact changed: {file}')
    for rel in ['operations/budget.json', 'protocol.json', 'sources/src/evolve.py']:
        need(rel in manifest['artifacts'], f'critical artifact missing from provenance: {rel}')
    return manifest


def analyze(repo):
    rows, candidates, sources = [], [], {}
    evolve_hash = None
    matched_draws, checked_matched_draws = {}, 0
    for study, (relative, runs) in STUDIES.items():
        root = repo / relative
        manifest = verify_archive(root)
        source = root / 'sources/src/evolve.py'
        if evolve_hash is None:
            evolve_hash = sha(source)
        need(sha(source) == evolve_hash, 'different selection implementation across studies')
        protocol = read_json(root / 'protocol.json')
        need(protocol['runs'] == list(runs) and protocol['generations'] == 16, 'fixed registered search scope')
        source_files = ['provenance.json', 'operations/budget.json', 'protocol.json', 'sources/src/evolve.py']
        for run in runs:
            prefix = f'runs/s{run}'
            for name in ['lineage.jsonl', 'curves.jsonl', 'config.yaml']:
                need(f'{prefix}/{name}' in manifest['artifacts'], 'raw record not bound by completed archive')
                source_files.append(f'{prefix}/{name}')
            cfg = yaml.safe_load((root / prefix / 'config.yaml').read_text())
            e, life = cfg['evolve'], cfg['life']
            need(e['mu'] == 32 and e['lam'] == 224 and e['recheck_k'] == 64 and e['recheck_lives'] == 4
                 and e['recheck_key'] == 'all' and life['lives'] == 3, 'scoring policy changed')
            lineage = [json.loads(line) for line in (root / prefix / 'lineage.jsonl').read_text().splitlines()]
            lineage = [line for line in lineage if 'gen' in line]
            curves = [json.loads(line) for line in (root / prefix / 'curves.jsonl').read_text().splitlines()]
            need([r['gen'] for r in lineage] == list(range(16)) == [r['gen'] for r in curves], 'generation coverage')
            for line, curve in zip(lineage, curves, strict=True):
                if study in ('D', 'G'):
                    key = (run, line['gen'])
                    draw = (line['T'], line['seeds'], line['recheck']['seeds'])
                    if study == 'D':
                        matched_draws[key] = draw
                    else:
                        need(draw == matched_draws[key], 'D/G matched duration and life-seed draws')
                        checked_matched_draws += 1
                result, pairs = generation(study, run, line, curve)
                rows.append(result)
                candidates.extend(pairs)
        sources[study] = dict(path=relative, verified_artifacts=len(manifest['artifacts']),
                              files={f: dict(sha256=sha(root / f), bytes=(root / f).stat().st_size)
                                     for f in source_files})
    need(len(rows) == 96 and len(candidates) == 6144, 'fixed total record count')
    need(checked_matched_draws == 32, 'complete D/G matching verification')
    by_run, by_run_T = {}, {}
    for study, (_, runs) in STUDIES.items():
        for run in runs:
            group = [r for r in rows if r['study'] == study and r['run'] == run]
            pairs = [c for c in candidates if c['study'] == study and c['run'] == run]
            by_run[f'{study}_s{run}'] = aggregate(group, pairs)
            for duration in sorted({r['T'] for r in group}):
                by_run_T[f'{study}_s{run}_T{int(duration)}'] = aggregate(
                    [r for r in group if r['T'] == duration], [c for c in pairs if c['T'] == duration])
    summary = dict(status='complete_descriptive_audit', simulated_lives=0, active_outcomes_read=False,
                   selection_implementation_sha256=evolve_hash,
                   matched_D_G_generation_draws_verified=checked_matched_draws,
                   initial_lives_per_genome=3, extra_lives_per_shortlisted_genome=4,
                   base_genome_lives=96 * 256 * 3, recheck_genome_lives=96 * 64 * 4,
                   recheck_fraction_of_selection_lives=.25,
                   all_records_descriptive=aggregate(rows, candidates), by_run=by_run, by_run_T=by_run_T,
                   caveats=CAVEATS)
    return summary, rows, candidates, sources


def markdown(summary):
    lines = ['# Selection resampling diagnostic: completed D, G and L', '',
             'This audit compares the saved initial three-life mean with the four fresh recheck lives, and the',
             'actual parents chosen from their pooled seven-life mean. It covers all 96 generations in six',
             'completed searches, retaining every one of the 6,144 shortlisted candidate records.', '',
             '| Run | Replaced parent slots | Mean replaced / 32 | Leader IDs changed | Strict top displacement |',
             '| --- | ---: | ---: | ---: | ---: |']
    for run, s in summary['by_run'].items():
        lines.append(f"| {run} | {s['replaced_parent_slots']} / {s['parent_slots']} | "
                     f"{s['changed_parent_count']['mean']:.2f} | {s['leader_identity_changes']} / 16 | "
                     f"{s['strict_top_displacements']} / 16 |")
    lines += ['', '“Strict top displacement” means no original maximum-score candidate shares the recorded pooled',
              'maximum, and the recorded last survivor scores below the maximum. In that case all pooled maxima',
              'are present among the saved survivors; an unselected candidate is bounded by the recorded cutoff.',
              'This classification uses actual saved pooled scores, not reconstructed means.',
              'Identity changes with overlapping top-score sets are reported separately;',
              'they are not treated as clear winner reversals. Parent replacements use the exact logged shortlist',
              'order and survivor set, including their actual random tie decisions.', '',
              '| Run | Recheck − base mean | Median | RMS | Mean within-generation rank correlation |',
              '| --- | ---: | ---: | ---: | ---: |']
    for run, s in summary['by_run'].items():
        d = s['recheck_minus_base']
        corr = s['within_generation_spearman']
        text = f"{corr['mean']:.3f}" if corr else 'NA'
        lines.append(f"| {run} | {d['mean']:+.3f} | {d['median']:+.3f} | {d['rms']:.3f} | {text} |")
    lines += ['', 'Life-duration breakdown (all groups retained):', '',
              '| Run and T | Generations | Mean replaced / 32 | Strict top displacements | Recheck − base mean |',
              '| --- | ---: | ---: | ---: | ---: |']
    for key, s in summary['by_run_T'].items():
        lines.append(f"| {key} | {s['generations']} | {s['changed_parent_count']['mean']:.2f} | "
                     f"{s['strict_top_displacements']} | {s['recheck_minus_base']['mean']:+.3f} |")
    all_rows = summary['all_records_descriptive']
    lines += ['', f"Across these records, {all_rows['replaced_parent_slots']} of 3,072 parent slots changed "
              f"({100 * all_rows['replaced_parent_fraction']:.1f}%). "
              f"There were {all_rows['strict_top_displacements']} strict top displacements, "
              f"{all_rows['identity_changes_with_top_set_overlap']} changed leader IDs with overlapping top sets, "
              f"and {all_rows['top_set_ambiguous_generations']} unresolved top-set comparisons.", '',
              "The smallest strict displacement margin, using actual recorded scores or the survivor cutoff as",
              "an upper bound for an unselected initial leader, is",
              f"{all_rows['minimum_strict_displacement_recorded_margin_lower_bound']:.6f} F.", '',
              'These are descriptive totals, not independent replicate estimates. `summary.json` also reports every',
              'run separately by life duration; `generations.json` preserves tie sets and rank intervals;',
              '`candidates.csv` preserves the exact saved means, signed differences and actual selected ranks.', '',
              'The recheck used 24,576 of the 98,304 selection genome-lives (25%). Logged evaluation wall time',
              f"attributes {100 * all_rows['recheck_elapsed_fraction']:.1f}% to rechecking. This elapsed-time ratio",
              'is not a CPU-budget measurement and does not predict the cost of another policy.', '',
              'The logs establish that finite life samples often change immediate selection. They cannot tell us',
              'whether those changes improve later independent fitness, or whether spending the same compute on',
              'more candidates or generations would do better. A future fixed-budget comparison could test that;',
              'these diagnostics alone do not justify increasing the scoring budget.', '', '## Limits', '']
    lines += [f'- {c}' for c in CAVEATS]
    lines += ['', '## Reproduce', '', 'From the repository root:', '', '```sh',
              '.venv/bin/python results/selection_noise_20261014/analyze.py --out outputs/selection_noise_reanalysis',
              '```', '',
              'Only completed public D/G/L archives are read. Every artifact in each original provenance manifest',
              'is checked before lineage analysis. No simulation or engine import is performed.', '']
    return '\n'.join(lines)


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--repo', type=Path, default=Path.cwd())
    parser.add_argument('--out', type=Path, default=Path(__file__).resolve().parent)
    args = parser.parse_args()
    summary, rows, candidates, sources = analyze(args.repo)
    args.out.mkdir(parents=True, exist_ok=True)
    write_json(args.out / 'summary.json', summary)
    write_json(args.out / 'generations.json', rows)
    with (args.out / 'candidates.csv').open('w', newline='') as stream:
        writer = csv.DictWriter(stream, fieldnames=list(candidates[0]))
        writer.writeheader()
        writer.writerows(candidates)
    (args.out / 'README.md').write_text(markdown(summary))
    artifacts = ['summary.json', 'generations.json', 'candidates.csv', 'README.md']
    write_json(args.out / 'provenance.json', dict(status='complete_descriptive_audit', simulated_lives=0,
               sources=sources, analysis_sha256=sha(__file__),
               tests_sha256=sha(Path(__file__).with_name('test_analyze.py')),
               artifacts={f: dict(sha256=sha(args.out / f), bytes=(args.out / f).stat().st_size) for f in artifacts}))
    print(json.dumps({k: summary['all_records_descriptive'][k] for k in
                      ['generations', 'replaced_parent_slots', 'leader_identity_changes', 'strict_top_displacements']}))


if __name__ == '__main__':
    main()
