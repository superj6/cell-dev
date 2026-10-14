"""Descriptive gridded phenotype changes from completed K traces only; no simulation."""
from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path

import numpy as np

ROOT = next((p for p in Path(__file__).resolve().parents if (p / 'src/life/probe.py').exists()), None)
DEFAULT_ARCHIVE = ROOT / 'results/traces_20261014' if ROOT else None
K_PROVENANCE_SHA = '6ab3b6a5d4f5f0db561cf5ca37a191a8f824065720583de7e63a6de74e7106ed'
LABELS = ('founder_row38', 'd_s51089_final_rank0', 'd_s51090_final_rank0')
SEEDS = tuple(range(51_890_000, 51_890_004))
START, END = 800., 1536.
CONTINUOUS = ('asym', 'sec0', 'sec1')
NEURAL = ('w0', 'w1', 'b', 'tau_m', 't_ref', 'emit0', 'emit1', 'delta', 'g_r')
EMISSION = ('emit0', 'emit1')
AGE_BINS = ((0., 32.), (32., 128.), (128., None))
TIME_BINS = ((800., 1024.), (1024., 1280.), (1280., 1536.))


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def stats(values):
    values = np.asarray(values, dtype=np.float64)
    return ({'mean': float(values.mean()), 'min': float(values.min()), 'max': float(values.max())}
            if len(values) else None)


def fraction(numerator, denominator):
    return numerator / denominator if denominator else None


def analyze_arrays(arrays, metadata):
    names = metadata['tables']['knobs_birth']
    gridded = [name for name in names if name not in CONTINUOUS]
    cid = np.asarray(arrays['cells__cid'], dtype=np.int64)
    born = np.asarray(arrays['cells__t_birth'], dtype=np.float64)
    died = np.asarray(arrays['cells__t_death'], dtype=np.float64)
    if not np.array_equal(cid, np.arange(len(cid))) or np.any(died < born):
        raise ValueError('invalid cell identity or lifetime')
    current = {name: np.asarray(arrays['knobs_birth__' + name]).copy() for name in gridded}
    baseline = {name: value.copy() for name, value in current.items()}
    t = np.asarray(arrays['pheno_changes__t'])
    cells = np.asarray(arrays['pheno_changes__cid'], dtype=np.int64)
    knobs = np.asarray(arrays['pheno_changes__knob'])
    old, new = np.asarray(arrays['pheno_changes__old']), np.asarray(arrays['pheno_changes__new'])
    if not all(len(x) == len(t) for x in (cells, knobs, old, new)):
        raise ValueError('truncated phenotype table')
    if (not np.isfinite(t).all() or np.any(np.diff(t) < 0) or np.any(t > END)
            or np.any(cells < 0) or np.any(cells >= len(cid))):
        raise ValueError('invalid phenotype event ordering or identity')
    for time, cell, knob, before, after in zip(t, cells, knobs, old, new):
        if knob not in current or not (born[cell] <= time <= died[cell]):
            raise ValueError('unlogged knob or event outside cell lifetime')
        if current[knob][cell] != before or before == after or not np.isfinite([before, after]).all():
            raise ValueError('phenotype transition chain differs')
        current[knob][cell] = after
        if time <= START:
            baseline[knob][cell] = after
    for knob in gridded:
        if not np.array_equal(current[knob], arrays['knobs_end__' + knob]):
            raise ValueError('phenotype trace does not reconstruct terminal values')
    cohort = (born <= START) & (died > START)
    after_birth = born > START
    after = t > START
    denominator = int(cohort.sum())
    cohort_event = after & cohort[cells]
    later_event = after & after_birth[cells]
    changed = np.zeros(len(cid), dtype=bool)
    changed[cells[cohort_event]] = True
    neural_event = cohort_event & np.isin(knobs, NEURAL)
    neural_changed = np.zeros(len(cid), dtype=bool)
    neural_changed[cells[neural_event]] = True
    emit_event = cohort_event & np.isin(knobs, EMISSION)
    emit_changed = np.zeros(len(cid), dtype=bool)
    emit_changed[cells[emit_event]] = True
    per_knob = {}
    for knob in gridded:
        events = cohort_event & (knobs == knob)
        cell_count = len(np.unique(cells[events]))
        terminal_changed = int(np.count_nonzero(cohort & (current[knob] != baseline[knob])))
        age = START - born[np.unique(cells[events])]
        per_knob[knob] = {
            'events': int(events.sum()), 'changed_cells': cell_count,
            'fraction_cohort_changed': fraction(cell_count, denominator),
            'terminal_differs_cells': terminal_changed,
            'fraction_cohort_terminal_differs': fraction(terminal_changed, denominator),
            'absolute_step_change': stats(np.abs(new[events] - old[events])),
            'age_at800_of_changed_cells': stats(age),
            'later_born_events': int(np.count_nonzero(later_event & (knobs == knob))),
            'later_born_changed_cells': len(np.unique(cells[later_event & (knobs == knob)])),
        }
    ages = START - born
    age_rows = []
    for lo, hi in AGE_BINS:
        selected = cohort & (ages >= lo) & ((ages < hi) if hi is not None else True)
        n = int(selected.sum())
        age_rows.append({'min_age': lo, 'max_age_exclusive': hi, 'cells': n,
                         'gridded_changed_cells': int(np.count_nonzero(selected & changed)),
                         'neural_changed_cells': int(np.count_nonzero(selected & neural_changed)),
                         'neural_changed_fraction': fraction(int(np.count_nonzero(selected & neural_changed)), n)})
    time_rows = []
    for lo, hi in TIME_BINS:
        mask = cohort_event & (t > lo) & (t <= hi)
        selected_neural = mask & np.isin(knobs, NEURAL)
        time_rows.append({'start_exclusive': lo, 'end_inclusive': hi, 'gridded_events': int(mask.sum()),
                          'gridded_changed_cells': len(np.unique(cells[mask])),
                          'neural_events': int(selected_neural.sum()),
                          'neural_changed_cells': len(np.unique(cells[selected_neural]))})
    return {'alive_at800_cells': denominator, 'later_born_cells': int(after_birth.sum()),
            'cohort_died_after800': int(np.count_nonzero(cohort & np.isfinite(died))),
            'cohort_age_at800': stats(ages[cohort]), 'gridded_events': int(cohort_event.sum()),
            'gridded_changed_cells': int(changed.sum()),
            'gridded_changed_fraction': fraction(int(changed.sum()), denominator),
            'neural_events': int(neural_event.sum()), 'neural_changed_cells': int(neural_changed.sum()),
            'neural_changed_fraction': fraction(int(neural_changed.sum()), denominator),
            'emission_switches': int(emit_event.sum()), 'emission_switched_cells': int(emit_changed.sum()),
            'emission_switched_fraction': fraction(int(emit_changed.sum()), denominator),
            'per_knob': per_knob, 'age_bins': age_rows, 'time_bins': time_rows,
            'all_logged_transitions': len(t), 'terminal_reconstruction_exact': True}


def validate_pairs(lives):
    pairs = [(r['label'], r['seed']) for r in lives]
    if len(pairs) != len(set(pairs)) or set(pairs) != {(label, seed) for label in LABELS for seed in SEEDS}:
        raise ValueError('fixed K label/seed set differs')


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--archive', type=Path, default=DEFAULT_ARCHIVE)
    parser.add_argument('--out', type=Path, required=True, help='Directory for fresh descriptive outputs')
    args = parser.parse_args()
    if args.archive is None:
        parser.error('--archive is required outside the repository')
    study, out = args.archive.resolve(), args.out.resolve()
    if study == out or study in out.parents:
        raise ValueError('descriptive outputs must be outside the sealed K archive')
    budget = json.loads((study / 'operations/budget.json').read_text())
    if budget['status'] != 'complete' or budget.get('running') or budget.get('queued'):
        raise ValueError('K must be complete before reading data')
    if sha(study / 'provenance.json') != K_PROVENANCE_SHA:
        raise ValueError('fixed completed K provenance differs')
    provenance = json.loads((study / 'provenance.json').read_text())
    if provenance['status'] != 'complete':
        raise ValueError('K archive incomplete')
    for relative, record in provenance['artifacts'].items():
        p = study / relative
        if sha(p) != record['sha256'] or p.stat().st_size != record['bytes']:
            raise ValueError('K archived artifact differs: ' + relative)
    report = json.loads((study / 'measurement/report.json').read_text())
    if report['status'] != 'complete' or len(report['lives']) != 12:
        raise ValueError('K fixed life set incomplete')
    validate_pairs(report["lives"])
    rows = []
    for life in report['lives']:
        path = study / 'measurement' / life['trace']
        if sha(path) != life['sha256']:
            raise ValueError('K trace binding differs')
        with np.load(path, allow_pickle=False) as data:
            metadata = json.loads(str(data['metadata']))
            if metadata['meta']['seed'] != life['seed'] or metadata['meta']['org'] != life['label']:
                raise ValueError('trace identity differs from fixed pair')
            if metadata['ledger']['t_end'] != END:
                raise ValueError('K life did not complete T1536')
            row = analyze_arrays(data, metadata)
        rows.append({'genotype': life['label'], 'seed': life['seed'], 'trace_sha256': life['sha256'], **row})
    groups = {}
    for label in sorted({row['genotype'] for row in rows}):
        selected = [row for row in rows if row['genotype'] == label]
        groups[label] = {'lives': len(selected),
                         'per_life': {key: stats([r[key] for r in selected]) for key in
                         ('alive_at800_cells', 'later_born_cells', 'gridded_events', 'gridded_changed_fraction',
                          'neural_events', 'neural_changed_fraction', 'emission_switches',
                          'emission_switched_fraction')},
                         'per_knob': {knob: {key: stats([r['per_knob'][knob][key] for r in selected]) for key in
                         ('events', 'fraction_cohort_changed', 'fraction_cohort_terminal_differs')}
                         for knob in selected[0]['per_knob']}}
    result = {'status': 'exploratory_completed_data_only', 'simulated_lives': 0, 'rows': rows,
              'genotype_summary': groups, 'definitions': {'cohort': 'born<=800 and died>800; right-limit convention',
              'window': '800<t<=1536', 'continuous_not_logged': CONTINUOUS, 'neural_knobs': NEURAL,
              'emission_knobs': EMISSION, 'unit': 'one life; cells/events are not independent replicates'},
              'provenance_sha256': sha(study / 'provenance.json'), 'analysis_sha256': sha(Path(__file__)),
              'source_sha256': {p: json.loads((study / 'protocol.json').read_text())['source_identity'][p]
                                for p in ('src/life/probe.py', 'src/life/spec.py')},
              'limits': ['Normal growing K lives, not frozen H/R interventions; only four seeds per genotype.',
                         'Post800-born cells are separate; ages at800 and later deaths affect exposure.',
                         'A change is a logged grid switch, not an arbitrarily thresholded continuous drift.',
                         'Continuous asym and secretion updates are not logged; no inference of their stability.',
                         'Gridded phenotype is not the effective incoming spike weights recomputed by derive.',
                         'No counterfactual, fitness attribution, maturity or learning claim follows from '
                         'these counts.',
                         'Final equality can conceal reversible changes; event and endpoint counts are both retained.']}
    out.mkdir(parents=True, exist_ok=True)
    (out / 'summary.json').write_text(json.dumps(result, indent=2, allow_nan=False) + '\n')
    print(json.dumps({'status': result['status'], 'genotype_summary': groups}, indent=2))


if __name__ == '__main__':
    main()
