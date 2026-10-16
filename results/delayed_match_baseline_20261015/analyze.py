"""Read retained ledgers/fates only; never run a life or choose an endpoint."""
from __future__ import annotations

import argparse
import csv
import sys

from common import ROOT, STUDY, checked_protocol, read, save, sha

sys.dont_write_bytecode = True
sys.path.insert(0, str(ROOT))


def moments(values):
    import numpy as np
    a = np.asarray(values, dtype=np.float64)
    return dict(n=len(a), mean=float(a.mean()), sd=float(a.std(ddof=1)) if len(a) > 1 else None,
                min=float(a.min()), max=float(a.max()))


def class_table(ledger, abi):
    out = {}
    for label in ('narrow', 'broad'):
        names = ('choice_opportunities', 'choice_carry_in', 'correct_choices', 'wrong_choices',
                 'choice_timeouts', 'unfinished_choices')
        row = {name: int(ledger[:, abi.L[name + '_' + label]].sum()) for name in names}
        total = row['choice_opportunities'] + row['choice_carry_in']
        correct, wrong = row['correct_choices'], row['wrong_choices']
        unresolved = row['choice_timeouts'] + row['unfinished_choices']
        row.update(total_opportunities=total,
            narrow_choice=correct if label == 'narrow' else wrong,
            broad_choice=correct if label == 'broad' else wrong,
            no_completed_choice=unresolved, conservation=(total == correct + wrong + unresolved),
            choice_coverage=(correct + wrong) / total if total else None,
            correct_per_opportunity=correct / total if total else None,
            accuracy_among_choices=correct / (correct + wrong) if correct + wrong else None)
        out[label] = row
    return out


def validate_life(led, world, abi):
    import numpy as np

    from src.life import spec

    row = led[0]
    status_value = row[abi.L['status']]
    known = sum(spec.STATUS.values())
    if status_value < 0 or status_value != int(status_value) or int(status_value) & ~known:
        raise ValueError('invalid status value')
    status = int(status_value)
    if status & (spec.STATUS['capacity'] | spec.STATUS['ledger_mismatch']
                 | spec.STATUS['raster_overflow'] | spec.STATUS['fate_overflow']):
        raise ValueError('capacity, accounting, or truncated-log status')
    for label in ('narrow', 'broad'):
        vals = [row[abi.L[name + '_' + label]] for name in ('choice_opportunities', 'choice_carry_in',
                'correct_choices', 'wrong_choices', 'choice_timeouts', 'unfinished_choices')]
        if any(v < 0 or v != int(v) for v in vals) or vals[0] + vals[1] != sum(vals[2:]):
            raise ValueError('per-life class counts or conservation failed')
    correct = row[abi.L['correct_choices_narrow']] + row[abi.L['correct_choices_broad']]
    if row[abi.L['income']] != world.R_cap * correct:
        raise ValueError('native income differs from conditional correctness')
    cost = float(abi.column_cost(led, world)[0])
    guard = float(abi.guard_charge(led, world)[0])
    fitness = float(abi.fitness(led, world)[0])
    for name, expected in (('cost', cost), ('guard_charge', guard),
                           ('net', world.R_cap * correct - cost - guard), ('F', fitness)):
        if abs(row[abi.L[name]] - expected) > 1e-9 * max(1, abs(expected)):
            raise ValueError('native ledger reconciliation failed: ' + name)
    terminal = row[abi.L['t_end']]
    guard_mask = spec.STATUS['guard_cells'] | spec.STATUS['guard_events']
    if terminal < world.t0 or terminal > world.t0 + world.T or (not status & (guard_mask | spec.STATUS['extinct'])
                                                              and terminal != world.t0 + world.T):
        raise ValueError('unexplained terminal time')
    if not np.isfinite(row).all():
        raise ValueError('nonfinite ledger')


def development(fi, ff, fate_total, cap):
    """Inclusive post-event snapshots by UID; rejection records do not create cells."""
    import math

    import numpy as np

    if (fi.ndim != 2 or fi.shape[1] != 7 or ff.shape != (len(fi), 18)
            or fate_total != len(fi) or fate_total > cap or not np.isfinite(ff).all()
            or np.any(ff[:, 0] < 0) or np.any(ff[:, 0] >= 85)
            or np.any(np.diff(ff[:, 0]) < 0) or np.any(~np.isin(fi[:, 0], [1, 2, 3]))):
        raise ValueError('incomplete or corrupt fate log')
    live_check = set()
    for row in fi:
        kind, uid = int(row[0]), int(row[1])
        if kind == 1:
            if uid in live_check:
                raise ValueError('duplicate live birth UID')
            live_check.add(uid)
        elif kind == 2:
            if uid not in live_check:
                raise ValueError('death missing prior live birth')
            live_check.remove(uid)

    snapshots = {}
    for cutoff in (14, 15, 25):
        live, birth_times = {}, []
        for ints, floats in zip(fi, ff):
            t = float(floats[0])
            if t > cutoff:
                continue
            kind, uid, _, a, b, _, z = (int(x) for x in ints)
            if kind == 1:
                live[uid] = (a, b, z)
                if z == 0 and (a != 0 or b != 0):
                    birth_times.append(t)
            elif kind == 2:
                live.pop(uid, None)
        sensory = [v for v in live.values() if v[2] == 0]
        off = [v for v in sensory if v[0] != 0 or v[1] != 0]
        snapshots[str(cutoff)] = dict(live_cells=len(live), sense_plane_cells=len(sensory),
            off_center_sense_cells=len(off), off_center_sense_positions=sorted(off),
            cumulative_off_center_sense_births=len(birth_times),
            first_off_center_sense_birth=min(birth_times) if birth_times else None,
            max_body_relative_sense_radius=max((math.sqrt(a*a + a*b + b*b) for a, b, _ in sensory), default=0.0))
    return dict(log_total=int(fate_total), log_saved=len(fi), log_complete=int(fate_total) <= cap,
                snapshots=snapshots)


def analyze(*, require_complete=False):
    import numpy as np

    from src.life import spec

    protocol = checked_protocol()
    protocol_sha = sha(STUDY / 'protocol.json')
    index = read(STUDY / 'row_index.json')
    expected = {item['path']: item for item in protocol['schedule']}
    if set(index) - set(expected) or (require_complete and set(index) != set(expected)):
        raise ValueError('retained row coverage differs from the fixed schedule')
    records, fast_rows, full_rows, development_rows = [], {}, {}, []
    for path, item in expected.items():
        if path not in index:
            continue
        if sha(STUDY / path) != index[path]['sha256']:
            raise ValueError('retained output changed: ' + path)
        with np.load(STUDY / path, allow_pickle=False) as data:
            led = data['ledger']
            if (led.shape != (1, 70) or not np.isfinite(led).all()
                    or data['seeds'].tolist() != [item['seed']]
                    or str(data['protocol_sha256']) != protocol_sha):
                raise ValueError('retained life has invalid shape/value/identity: ' + path)
            world = spec.World(**protocol['worlds'][str(item['T'])]['world'])
            validate_life(led, world, spec.V5)
            cost = spec.V5.column_cost(led, world)
            fitness = spec.V5.fitness(led, world)
            if cost.tobytes() != data['physical_cost'].tobytes() or fitness.tobytes() != data['F'].tobytes():
                raise ValueError('physical cost or F differs from the frozen ABI5 formula')
            key = (item['role'], item['T'], item['seed'])
            if item['fast']:
                fast_rows[key] = led[0].copy()
                record = dict(role=item['role'], T=item['T'], seed=item['seed'],
                    **{name: float(led[0, i]) for i, name in enumerate(spec.V5.LEDGER)})
                record.update(native_F=record['F'], native_guard_charge=record['guard_charge'])
                record.update(physical_cost=float(cost[0]), F=float(fitness[0]),
                    guard_charge=float(data['guard_charge'][0]))
                records.append(record)
            else:
                full_rows[key] = led[0].copy()
                development_rows.append(dict(role=item['role'], T=item['T'], seed=item['seed'],
                    **development(data['fate_i'], data['fate_f'], data['fate_n'][0], protocol['fate_cap'])))
    comparisons = [dict(role=key[0], T=key[1], seed=key[2],
        identical=key in fast_rows and row.tobytes() == fast_rows[key].tobytes())
        for key, row in full_rows.items()]
    groups = []
    for duration in (85, 1024):
        w = spec.World(**protocol['worlds'][str(duration)]['world'])
        for role in protocol['roles']:
            rr = [r for r in records if r['role'] == role and r['T'] == duration]
            if not rr:
                continue
            led = np.array([[r[k] for k in spec.V5.LEDGER] for r in rr])
            costs = {
                'maintenance': w.c_live * led[:, spec.V5.L['live_time']],
                'spikes': w.c_spike * led[:, spec.V5.L['spikes']],
                'motor': w.c_tw * led[:, spec.V5.L['kappa_sum']],
                'messages': w.c_msg * led[:, spec.V5.L['contact_events']],
                'division_claims': w.c_div * led[:, spec.V5.L['claims']],
                'secretion': w.c_sec * led[:, spec.V5.L['sec_int']],
                'misses': w.c_miss * led[:, spec.V5.L['misses']],
                'receptors': w.c_rec * led[:, spec.V5.L['rec_gain']],
                'wrong_choices': spec.b2_cost(w) * (led[:, spec.V5.L['wrong_choices_narrow']] + led[:, spec.V5.L['wrong_choices_broad']]),
            }
            status = led[:, spec.V5.L['status']].astype(np.int64)
            groups.append(dict(role=role, T=duration, n=len(rr),
                class_choice=class_table(led, spec.V5),
                metrics={name: moments([r[name] for r in rr]) for name in
                         ('F', 'physical_cost', 'guard_charge', 'income', 'captures', 'b2_clicks', 'misses',
                          'n_end', 'n_peak', 'live_time', 'births', 'deaths', 'rec_accept', 'rec_gain')},
                costs={name: moments(values) for name, values in costs.items()},
                status_counts={name: int(np.count_nonzero(status & bit)) for name, bit in spec.STATUS.items()}))
    summary = dict(status='complete' if len(index) == 390 else 'partial',
        development_only=True, fast_lives=len(fast_rows), full_repeat_lives=len(full_rows),
        protocol_sha256=protocol_sha, row_index_sha256=sha(STUDY / 'row_index.json'),
        full_fast_comparisons=comparisons,
        full_fast_ledgers_identical=len(comparisons) == 6 and all(row['identical'] for row in comparisons),
        groups=groups, early_development=development_rows,
        limitations=protocol['interpretation'])
    summary['valid'] = summary['status'] == 'complete' and summary['full_fast_ledgers_identical']
    if summary['status'] == 'complete' and not summary['valid']:
        summary['status'] = 'invalid'
    save(STUDY / 'summary.json', summary)
    if records:
        with (STUDY / 'per_life.csv').open('w', newline='') as stream:
            writer = csv.DictWriter(stream, fieldnames=list(records[0]))
            writer.writeheader()
            writer.writerows(records)
    lines = ['# Frozen-endpoint delayed-match developmental baseline', '',
             f"Retained {len(fast_rows)}/384 fast lives and {len(full_rows)}/6 predetermined full repeats.", '',
             '| Role | T | n | Mean F | Mean cost | Correct | Wrong | Timeouts | Unfinished |',
             '|---|---:|---:|---:|---:|---:|---:|---:|---:|']
    for group in groups:
        cc = group['class_choice']
        totals = [sum(row[key] for row in cc.values()) for key in
                  ('correct_choices', 'wrong_choices', 'choice_timeouts', 'unfinished_choices')]
        lines.append(f"| {group['role']} | {group['T']} | {group['n']} | {group['metrics']['F']['mean']:.6g} | "
                     f"{group['metrics']['physical_cost']['mean']:.6g} | " + ' | '.join(map(str, totals)) + ' |')
    lines += ['', 'Full class-by-choice tables, all status flags, costs, and t14/15/25 sensory occupancy are in summary.json.', '']
    lines += [text + '\n' for text in protocol['interpretation']]
    (STUDY / 'REPORT.md').write_text('\n'.join(lines))
    return summary


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--analyze', action='store_true')
    if parser.parse_args().analyze:
        analyze()
    else:
        print('source only: analysis reads retained files and runs zero lives')
