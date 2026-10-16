"""Independent all-row terminal arithmetic; never imports a study reader or simulation module."""
from __future__ import annotations

import argparse
import collections
import hashlib
import json
import math
import os
import resource
import signal
import threading
import time
import traceback
from pathlib import Path

ROLES = ('AM_reference', 'AO_start', 'mixed8', 'mixed24')
WORLDS = ('match85', 'pool', 'persistent', 'blink80_20', 'match1024', 'short_blank', 'transfer')
PAIRS = (('mixed24', 'AO_start'), ('mixed24', 'mixed8'), ('mixed8', 'AO_start'), ('mixed24', 'AM_reference'))
TASK = ('choice_opportunities', 'choice_carry_in', 'correct_choices', 'wrong_choices',
        'choice_timeouts', 'unfinished_choices')
BASE = ('income live_time sec_int spikes kappa_sum contact_events claims births rejects rejects_wall deaths kills '
        'cost guard_charge net F n_end n_peak t_end status events beats P_int arrivals arrivals_dropped packets '
        'morph_secreted morph_decayed morph_lost morph_content_end morph_inflight_end chem_clamps last_birth ticks '
        't_ext captures misses clicks b2_clicks respawns nudges rec_cand rec_accept rec_events rec_gain samples '
        'dist_sum zone_samples path X_end Y_end n_S_end n_M_end n_H_end live_S live_M live_H low_light_captures').split()
LEDGER = BASE + [f'{name}_{cls}' for name in TASK for cls in ('narrow', 'broad')]
COUNTS = ('spikes contact_events claims births rejects rejects_wall deaths kills n_end n_peak events beats arrivals '
          'arrivals_dropped packets chem_clamps ticks captures misses clicks b2_clicks respawns nudges rec_cand '
          'rec_accept rec_events samples zone_samples n_S_end n_M_end n_H_end low_light_captures status').split()
COUNTS += LEDGER[58:]
SIGNED = {'net', 'F', 't_end', 'last_birth', 't_ext', 'X_end', 'Y_end'}
PRICES = {'maintenance': ('c_live', 'live_time'), 'spikes': ('c_spike', 'spikes'),
          'twitch': ('c_tw', 'kappa_sum'), 'messages': ('c_msg', 'contact_events'),
          'division': ('c_div', 'claims'), 'secretion': ('c_sec', 'sec_int'),
          'misses': ('c_miss', 'misses'), 'receptors': ('c_rec', 'rec_gain')}
RATIOS = ('completion_coverage', 'correct_per_opportunity', 'accuracy_among_completed',
          'narrow_given_completed', 'narrow_per_opportunity')
RESPONSES = RATIOS[-2:]
LIMITS = dict(cpu_seconds=60, wall_seconds=120, address_space_bytes=2*1024**3,
              rss_bytes=512*1024**2, available_floor_bytes=4*1024**3)


def read(path):
    return json.loads(Path(path).read_text())


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def save(path, value):
    with Path(path).open('x') as stream:
        json.dump(value, stream, indent=2, allow_nan=False)
        stream.write('\n')


def need(condition, message):
    if not condition:
        raise ValueError(message)


def describe(values):
    # Independent scalar summation and unbiased central second moment.
    x = [float(item) for item in values]
    count = len(x)
    need(count == 512 and all(math.isfinite(v) for v in x), 'invalid paired-life sample')
    average = math.fsum(x)/count
    se = math.sqrt(math.fsum((v-average)**2 for v in x)/(count*(count-1)))
    return dict(n=count, mean=average, se=se, lower_3se=average-3*se, upper_3se=average+3*se,
                positive_above_3se=average > 3*se, bounds_are_descriptive=True)


def ratio(numerator, denominator):
    n, d = list(map(float, numerator)), list(map(float, denominator))
    nsum, dsum = math.fsum(n), math.fsum(d)
    if not dsum:
        return None, None
    value = nsum/dsum
    influence = [(a-value*b)*512/dsum for a, b in zip(n, d)]
    return dict(estimate=value, se=describe(influence)['se'], numerator=nsum, denominator=dsum,
                uncertainty='life-cluster delta-method SE'), influence


def delta(left, right):
    return [float(a)-float(b) for a, b in zip(left, right)]


def contrast(new, old, new_if, old_if):
    if new is None or old is None:
        return None
    value = new['estimate']-old['estimate']
    se = describe(delta(new_if, old_if))['se']
    return dict(estimate=value, se=se, lower_3se=value-3*se, upper_3se=value+3*se,
                uncertainty='paired life-cluster delta-method SE', descriptive_only=True)


def choices(cols):
    byclass, influences = {}, {}
    for cls in ('narrow', 'broad'):
        values = {metric: cols[f'{metric}_{cls}'] for metric in TASK}
        opportunities = values['choice_opportunities']+values['choice_carry_in']
        correct, wrong = values['correct_choices'], values['wrong_choices']
        completed = correct+wrong
        narrow = correct if cls == 'narrow' else wrong
        entry = {name: int(math.fsum(array)) for name, array in values.items()}
        entry.update(narrow_hits=int(math.fsum(narrow)), broad_hits=int(math.fsum(completed-narrow)))
        arguments = ((completed, opportunities), (correct, opportunities), (correct, completed),
                     (narrow, completed), (narrow, opportunities))
        for name, (num, den) in zip(RATIOS, arguments):
            entry[name], influences[f'{cls}/{name}'] = ratio(num, den)
        byclass[cls] = entry
    response = {}
    for name in RESPONSES:
        a, b = byclass['narrow'][name], byclass['broad'][name]
        if a is None or b is None:
            response[name], influences[name] = None, None
        else:
            influences[name] = delta(influences[f'narrow/{name}'], influences[f'broad/{name}'])
            response[name] = dict(estimate=a['estimate']-b['estimate'], se=describe(influences[name])['se'],
                                  uncertainty='paired life-cluster delta-method SE')
    return dict(classes=byclass, narrow_choice_response_to_narrow_cue=response,
                scope='native class counters; observer readout, no phase/class input and no memory-mechanism claim'), influences


def checked_relative(study, name):
    relative = Path(name)
    need(not relative.is_absolute() and '..' not in relative.parts, 'unsafe recorded path')
    path = study/relative
    need(path.resolve().is_relative_to(study.resolve()) and not path.is_symlink(), 'path escaped study')
    return path


def run(study, summary_path, out):
    import numpy as np

    # No outcome file is opened until all three required terminal statuses are complete.
    gate_names = ('budget.json', 'study_complete.json', 'measurement_complete.json')
    gates = {name: read(study/name) for name in gate_names}
    need(all(value.get('status') == 'complete' for value in gates.values()), 'terminal gate is not complete')
    p = read(study/'protocol.json')
    ph = sha(study/'protocol.json')
    need(ph == '2941610e25eb55f5e3b4ca2f0be91db46931573b24788bb85709c5b8464d9345', 'protocol changed')
    need(all(g['protocol_sha256'] == ph for g in gates.values()), 'terminal protocol binding')
    budget, completed, measured = [gates[name] for name in gate_names]
    need((completed['research_lives'], completed['startup_lives'], completed['total_calls']) == (75894,8,75902),
         'whole-study call count')
    need((measured['research_lives'], measured['startup_lives'], measured['rows']) == (14336,4,28), 'confirmation count')
    need(completed['measurement_complete_sha256'] == sha(study/'measurement_complete.json'), 'measurement pin')
    need(measured['row_index_sha256'] == sha(study/'row_index.json'), 'index pin')
    need(measured['endpoints_sha256'] == sha(study/'endpoints.json'), 'endpoints pin')
    need(budget['cpu_seconds'] < 10680 and budget['wall_seconds'] < 7080, 'whole runtime cap')
    need(budget['search_cpu_seconds'] < 8280 and budget['confirmation_cpu_seconds'] < 2400, 'phase CPU caps')
    cleanup = budget['terminal_cleanup']
    need(cleanup['all_owned_groups_exited'] and cleanup['all_worker_identities_exited']
         and not cleanup['remaining_descendants'] and not cleanup['remaining_group_members']
         and not cleanup['remaining_worker_identities'], 'terminal cleanup')
    need(not budget['running'] and not budget['queued'] and budget['exit_code'] == 0, 'terminal worker status')
    for phase, meta in budget['phase_records'].items():
        path = checked_relative(study, meta['path'])
        need(sha(path) == meta['sha256'] and read(path)['status'] == 'complete', 'phase budget binding: '+phase)
    for arm, digest in completed['search_complete_pins'].items():
        path = study/'runs'/arm/'search_complete.json'
        need(sha(path) == digest and read(path)['status'] == 'complete', 'search completion binding')
    for category, base in (('source_pins',study), ('input_pins',study), ('production_pins',study.parents[1])):
        for name, digest in p[category].items():
            need(sha(checked_relative(base,name)) == digest, category+': '+name)
    need(sha(study/'namespace/seed_audit.json') == p['seed_audit_sha256'], 'seed audit pin')
    need(sha(study/'reservation.json') == p['reservation_sha256'], 'reservation pin')
    need(tuple(p['roles']) == ROLES and tuple(p['worlds']) == WORLDS and p['extinct_charge'], 'matrix scope')
    need(p['seeds'] == list(range(52460000,52460512)), 'exact confirmation IDs')
    index = read(study/'row_index.json')
    expected_paths = {f'raw/{world}/row_{i:02d}.npz' for world in WORLDS for i in range(4)}
    need(set(index) == expected_paths, 'exact28 batch paths')
    endpoints = read(study/'endpoints.json')
    need(len(endpoints['genomes']) == 4, 'endpoint count')
    for endpoint in endpoints['genomes']:
        need(sha(checked_relative(study,endpoint['path'])) == endpoint['file_sha256'], 'endpoint bytes')
    summary = read(summary_path)
    need(summary['status'] == 'complete' and summary['protocol_sha256'] == ph
         and summary['row_index_sha256'] == sha(study/'row_index.json'), 'summary binding')
    need((summary['research_lives'],summary['startup_lives'],summary['paired_life_clusters']) == (14336,4,512),
         'summary complete scope')
    pins = {name: sha(study/name) for name in (*gate_names,'protocol.json','row_index.json','endpoints.json')}
    pins['summary'] = sha(summary_path)
    save(out/'attempt.json', dict(status='started', pins=pins, helper_sha256=sha(__file__), limits=LIMITS,
         summary_path=str(summary_path), simulator_calls=0, builds=0, random_draws=0))
    allcols, absolute, health, choice, influences, manifest = {}, {}, {}, {}, {}, {}
    largest_error = collections.defaultdict(float)

    def reconcile(actual, expected, label):
        for a, b in zip(actual, expected):
            error = abs(float(a)-float(b))
            largest_error[label] = max(largest_error[label], error)
            need(error <= 1e-9*max(1.,abs(float(b))), 'accounting: '+label)

    for world in WORLDS:
        allcols[world], absolute[world], health[world], choice[world], influences[world] = {}, {}, {}, {}, {}
        definition = p['worlds'][world]
        w = definition['world']
        need(definition['abi'] == 5 and definition['ledger_columns'] == LEDGER, 'ABI/schema')
        need(w['t_open'] == 0 and w['t0'] == 0 and w['world_kind'] == 1, 'full-life CATCH assumption')
        for i, role in enumerate(ROLES):
            raw_path = f'raw/{world}/row_{i:02d}.npz'
            entry = index[raw_path]
            scored_path = f'scored/{world}/row_{i:02d}.npz'
            need(entry['status'] == 'validated' and entry['lives'] == 512 and entry['role'] == role
                 and entry['world'] == world and entry['abi'] == 5 and entry['requested_lives'] == 512,
                 'index identity')
            need(entry['scored_path'] == scored_path, 'paired scored path')
            for name, digest in ((raw_path,entry['sha256']),(scored_path,entry['scored_sha256'])):
                need(sha(checked_relative(study,name)) == digest, 'raw/scored checksum')
                manifest[name] = digest
            with np.load(study/raw_path,allow_pickle=False) as archive:
                raw = {key: archive[key] for key in archive.files}
            with np.load(study/scored_path,allow_pickle=False) as archive:
                score = {key: archive[key] for key in archive.files}
            need(raw['ledger'].shape == (512,70) and raw['ledger'].dtype == np.float64
                 and np.isfinite(raw['ledger']).all(), 'finite70-column ledger')
            need(raw['seeds'].dtype == np.uint64 and raw['seeds'].shape == (512,)
                 and raw['seeds'].tolist() == p['seeds'], 'paired seed order')
            need(raw['hashes'].shape == (512,5) and raw['hashes'].dtype == np.uint64
                 and np.all(raw['hashes'] == 0x243F6A8885A308D3), 'fast hash schema')
            for field, expected in (('role',role),('world_name',world),('protocol_sha256',ph),
                ('endpoints_sha256',pins['endpoints.json']),('genome_raw_sha256',endpoints['genomes'][i]['raw_sha256'])):
                need(raw[field].shape == () and raw[field].item() == expected, 'row identity '+field)
            need(score['raw_sha256'].item() == entry['sha256'], 'scored-to-raw binding')
            for field in ('cpu_seconds','wall_seconds'):
                need(raw[field].shape == () and math.isfinite(float(raw[field])) and float(raw[field]) >= 0,
                     'row timing')
            c = {name: raw['ledger'][:,k] for k,name in enumerate(LEDGER)}
            for name in LEDGER:
                need(name in SIGNED or np.all(c[name] >= 0), 'negative '+name)
            for name in COUNTS:
                need(np.all(c[name] == np.floor(c[name])), 'noninteger '+name)
            status = c['status'].astype(np.int64)
            need(np.all(status <= 511) and not np.any(status & (8|16|64|128)), 'invalid status')
            guarded, extinct = (status & 6) != 0, (status & 1) != 0
            need(np.all((c['t_end'] >= 0)&(c['t_end'] <= w['T'])), 'end bounds')
            need(np.all((guarded|extinct)|(c['t_end'] == w['T'])), 'early nonterminal life')
            need(np.all(np.where(extinct,(c['t_ext'] >= 0)&(c['t_ext'] <= c['t_end'])&(c['n_end'] == 0),
                                     c['t_ext'] == -1)), 'extinction consistency')
            need(np.all((c['last_birth'] >= 0)&(c['last_birth'] <= c['t_end'])), 'birth time')
            for a,b in (('zone_samples','samples'),('rec_accept','rec_cand'),('rec_events','rec_accept'),
                        ('n_end','n_peak'),('low_light_captures','captures')):
                need(np.all(c[a] <= c[b]), 'counter ordering')
            for a,b,label in ((c['captures']+c['b2_clicks']+c['misses'],c['clicks'],'physical clicks'),
                (c['n_S_end']+c['n_M_end']+c['n_H_end'],c['n_end'],'plane census'),
                (1+c['births']-c['deaths']-c['kills'],c['n_end'],'one-cell population census')):
                need(np.array_equal(a,b),label)
            reconcile(c['live_S']+c['live_M']+c['live_H'],c['live_time'],'plane live time')
            reconcile(c['morph_decayed']+c['morph_lost']+c['morph_content_end']+c['morph_inflight_end'],
                      c['morph_secreted'],'morphogen conservation')
            if w['task_mode']:
                need(w['task_mode'] == 1,'task mode')
                for cls in ('narrow','broad'):
                    need(np.all(c['choice_carry_in_'+cls] == 0),'full-life carry-in must be zero')
                    opportunity = c['choice_opportunities_'+cls]+c['choice_carry_in_'+cls]
                    accounted = sum(c[name+'_'+cls] for name in TASK[2:])
                    need(np.array_equal(opportunity,accounted),'class conservation')
                need(np.array_equal(c['captures'],c['correct_choices_narrow']+c['wrong_choices_broad']),
                     'narrow physical slot/class coupling')
                need(np.array_equal(c['b2_clicks'],c['wrong_choices_narrow']+c['correct_choices_broad']),
                     'broad physical slot/class coupling')
                correct = c['correct_choices_narrow']+c['correct_choices_broad']
                wrong = c['wrong_choices_narrow']+c['wrong_choices_broad']
            else:
                need(w['b2_amp'] == 0 and all(np.all(c[key] == 0) for key in LEDGER[58:]),'neutral old-world task')
                correct, wrong = c['captures'], c['b2_clicks']
            if not w['visibility_mode']:
                need(np.all(c['low_light_captures'] == 0),'neutral visibility')
            parts = {name:w[price]*c[counter] for name,(price,counter) in PRICES.items()}
            parts['wrong_choices' if w['task_mode'] else 'decoy_hits'] = max(0.,-w['b2_value'])*wrong
            cost = np.array([math.fsum(values) for values in zip(*parts.values())])
            income = w['R_cap']*correct
            guard = np.array([w['c_live']*w['n_max']*(w['T']-end) if yes else 0.
                              for yes,end in zip(guarded,c['t_end'])])
            surcharge = np.array([w['c_live']*(w['T']-max(0.,ext))/w['T'] if yes else 0.
                                  for yes,ext in zip(extinct,c['t_ext'])])
            net = income-cost-guard
            for key, expected in (('income',income),('cost',cost),('guard_charge',guard),('net',net),('F',net/w['T'])):
                reconcile(c[key],expected,key)
            production = c['F']-surcharge
            for key,expected in (('native_F',c['F']),('extinct_charge',surcharge),('production_F',production)):
                need(score[key].shape == (512,) and score[key].dtype == np.float64 and np.isfinite(score[key]).all(),
                     'scored array schema')
                reconcile(score[key],expected,'scored_'+key)
            metrics = dict(c,F=production,native_F=c['F'],extinct_charge=surcharge,
                income_contribution=income/w['T'],ordinary_cost_contribution=-cost/w['T'],
                guard_contribution=-guard/w['T'],extinction_contribution=-surcharge)
            metrics.update({'cost__'+key:value for key,value in parts.items()})
            allcols[world][role] = metrics
            absolute[world][role] = {key:describe(value) for key,value in metrics.items()}
            statuses = collections.Counter(map(int,status))
            health[world][role] = dict(status_counts={str(key):statuses[key] for key in sorted(statuses)},
                guarded=int(guarded.sum()),extinct=int(extinct.sum()),all_fitness_rows_retained=512,
                hashes_are_fast_constants_not_trajectory_evidence=True)
            need(entry['health'] == health[world][role],'saved health')
            if w['task_mode']:
                choice[world][role],influences[world][role] = choices(c)
    paired,cue_paired,class_paired,retention = {},{},{},{}
    for world in WORLDS:
        paired[world],cue_paired[world],class_paired[world] = {},{},{}
        for new,old in PAIRS:
            label = new+'_minus_'+old
            paired[world][label] = {key:describe(delta(value,allcols[world][old][key]))
                                    for key,value in allcols[world][new].items()}
            if choice[world]:
                cue_paired[world][label] = {name:contrast(
                    choice[world][new]['narrow_choice_response_to_narrow_cue'][name],
                    choice[world][old]['narrow_choice_response_to_narrow_cue'][name],
                    influences[world][new][name],influences[world][old][name]) for name in RESPONSES}
                class_paired[world][label] = {cls:{name:contrast(choice[world][new]['classes'][cls][name],
                    choice[world][old]['classes'][cls][name],influences[world][new][cls+'/'+name],
                    influences[world][old][cls+'/'+name]) for name in RATIOS} for cls in ('narrow','broad')}
    for world in ('pool','persistent','blink80_20'):
        retention[world] = {}
        for candidate in ('mixed8','mixed24'):
            for reference in ('AO_start','AM_reference'):
                new,old = allcols[world][candidate]['captures'],allcols[world][reference]['captures']
                margin = describe([float(a)-.9*float(b) for a,b in zip(new,old)])
                retention[world][candidate+'_vs_'+reference] = dict(captures_difference=describe(delta(new,old)),
                    retained_90_percent_margin=margin,
                    mean_capture_ratio=None if math.fsum(old) == 0 else math.fsum(new)/math.fsum(old),
                    lower_3se_positive=margin['lower_3se'] > 0,diagnostic_only_not_a_gate=True)
    reconstructed = dict(absolute=absolute,paired=paired,health=health,choice_readouts=choice,
        paired_cue_response=cue_paired,paired_class_rates=class_paired,old_world_retention=retention)
    save(out/'reconstructed.json',reconstructed)
    save(out/'raw_manifest.json',manifest)
    mismatches,number_count,max_summary_error = [],0,0.

    def compare(actual,expected,path):
        nonlocal number_count,max_summary_error
        if isinstance(expected,dict):
            if not isinstance(actual,dict) or set(actual) != set(expected):
                mismatches.append(path+': keys/type')
                return
            for key,value in expected.items():
                compare(actual[key],value,path+'/'+key)
        elif isinstance(expected,(int,float)) and not isinstance(expected,bool):
            number_count += 1
            if not isinstance(actual,(int,float)) or isinstance(actual,bool) or not math.isfinite(actual):
                mismatches.append(path+': numeric type')
                return
            error = abs(float(actual)-float(expected))
            max_summary_error = max(max_summary_error,error)
            if error > 1e-10*max(1.,abs(expected)):
                mismatches.append(path+': numeric mismatch')
        elif actual != expected:
            mismatches.append(path+': value')
    for name, value in reconstructed.items():
        compare(summary[name],value,name)
    receipt = dict(status='passed' if not mismatches else 'failed',pins=pins,
        helper_sha256=sha(__file__),raw_manifest_sha256=sha(out/'raw_manifest.json'),
        reconstructed_sha256=sha(out/'reconstructed.json'),batches=28,lives=14336,
        paired_seeds=512,raw_and_scored_files=56,all_rows_retained=True,
        numeric_summary_values_checked=number_count,max_summary_absolute_error=max_summary_error,
        max_accounting_absolute_errors=dict(largest_error),mismatches=mismatches,
        simulator_calls=0,builds=0,random_draws=0,
        independence='NumPy only decodes retained arrays. Scalar math.fsum means, variances, ratios, paired influences and physical repricing; no frozen analyzer or production module imported.',
        limits=LIMITS,resources=dict(cpu_seconds_before_shutdown=time.process_time(),
            wall_seconds_before_shutdown=time.monotonic()-BEGIN,maximum_rss_kib=resource.getrusage(resource.RUSAGE_SELF).ru_maxrss),
        limitations=['Fast hashes are constants, not trajectory replay evidence.',
            'No independent genetic replay or new search-reliability estimate is supplied by this all-row accounting audit.',
            'Cue-conditioned response does not isolate neural memory; body and developmental state remain possible memory carriers.',
            'Retention and transfer are diagnostic, not endpoint replacement or admission gates.'])
    save(out/'audit_receipt.json',receipt)
    save(out/'class_tables.json',choice)
    (out/'REPORT.md').write_text('# Independent retained-row audit\n\n'
        +('Passed' if not mismatches else 'Failed')+' all-row arithmetic review of 28 batches / 14,336 lives on 512 paired seeds. '
        +'Raw and scored hashes, physical costs, guard charges, native and production fitness, class conservation, '
        +'physical-slot coupling, all absolute/paired statistics, life-cluster conditional ratios, cue-response contrasts '
        +'and old-world retention margins were independently recomputed.\n\n'
        +f'Compared {number_count:,} numeric summary values; maximum absolute difference {max_summary_error:.6g}. '
        +'Exact pins and every retained discrepancy are in `audit_receipt.json`; independent arithmetic is in '
        +'`reconstructed.json`. No simulation, build, genetic or world draw occurred. '
        +'This is saved-data accounting, not a claim of neural-memory mechanism or independent search replication.\n')
    need(not mismatches,'summary discrepancies retained in receipt')
    print(json.dumps(dict(status='passed',lives=14336,numeric_checks=number_count,
                          receipt_sha256=sha(out/'audit_receipt.json'))))


def main():
    global BEGIN
    BEGIN = time.monotonic()
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--study',type=Path,required=True)
    parser.add_argument('--summary',type=Path,required=True)
    args = parser.parse_args()
    study = args.study.resolve()
    out = Path(__file__).resolve().parent
    need(out.parent == study,'audit must run in the registered study terminal_audit directory')
    need(not (out/'attempt.json').exists() and not (out/'failure.json').exists(), 'one retained audit attempt; no automatic retry')
    resource.setrlimit(resource.RLIMIT_CPU,(58,60))
    resource.setrlimit(resource.RLIMIT_AS,(LIMITS['address_space_bytes'],LIMITS['address_space_bytes']))
    reason = ['resource signal']

    def interrupted(signum,frame):
        raise RuntimeError(reason[0]+' ('+str(signum)+')')

    for sig in (signal.SIGALRM,signal.SIGXCPU,signal.SIGUSR1):
        signal.signal(sig,interrupted)
    signal.alarm(120)

    def monitor():
        while True:
            available = next(int(line.split()[1])*1024 for line in Path('/proc/meminfo').read_text().splitlines()
                             if line.startswith('MemAvailable:'))
            rss = next(int(line.split()[1])*1024 for line in Path('/proc/self/status').read_text().splitlines()
                       if line.startswith('VmRSS:'))
            if available < LIMITS['available_floor_bytes'] or rss > LIMITS['rss_bytes']:
                reason[0] = 'host headroom or audit RSS limit'
                os.kill(os.getpid(),signal.SIGUSR1)
                return
            time.sleep(.1)

    threading.Thread(target=monitor,daemon=True).start()
    try:
        run(study,args.summary.resolve(),out)
    except BaseException as error:
        if not (out/'failure.json').exists():
            save(out/'failure.json',dict(status='failed',error=type(error).__name__+': '+str(error),
                traceback=traceback.format_exc(),simulator_calls=0,builds=0,random_draws=0,
                helper_sha256=sha(__file__),limits=LIMITS))
        raise
    finally:
        signal.alarm(0)


if __name__ == '__main__':
    main()
