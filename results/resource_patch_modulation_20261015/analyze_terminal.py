"""Analyze saved modulation rows and explicitly reused native rows; never compile or simulate."""
from __future__ import annotations

import argparse
import csv
import sys

from common import ROOT, STUDY, checked_protocol, read, save, sha

sys.dont_write_bytecode = True
sys.path.insert(0, str(ROOT))

from baseline_accounting import METRICS, moments, validate_life  # noqa: E402


def load_raw(path, seed, protocol_sha256, fast):
    import numpy as np

    from src.life import spec

    with np.load(path, allow_pickle=False) as data:
        if set(data.files) != {'ledger', 'hashes', 'seed', 'protocol_sha256'}:
            raise ValueError('raw native schema differs')
        if (data['seed'].dtype != np.uint64 or data['seed'].shape != (1,) or int(data['seed'][0]) != seed or
                data['protocol_sha256'].item() != protocol_sha256):
            raise ValueError('raw seed/protocol binding differs')
        ledger, hashes = data['ledger'].copy(), data['hashes'].copy()
    if ledger.shape != (1, 107) or ledger.dtype != np.float64 or hashes.shape != (1, 5) or hashes.dtype != np.uint64:
        raise ValueError('raw ABI6 shapes/dtypes differ')
    if fast and not np.all(hashes == spec.HASH_INIT):
        raise ValueError('fast hashes must remain constants')
    return ledger, hashes


def analyze():
    from src.life import spec

    protocol, index = checked_protocol(), read(STUDY / 'row_index.json')
    reuse = read(STUDY / 'inputs/reuse.json')
    if set(index) != {item['path'] for item in protocol['schedule']} or len(index) != 148:
        raise ValueError('exact148 returned rows required')
    records, parity = [], {}
    native_matches = []

    def record(item, ledger, origin):
        world = spec.World(**protocol['worlds'][item['world']]['world'])
        computed = validate_life(ledger, world)
        return dict(group=item['group'], role=item['role'], mode=item['mode'], world=item['world'], seed=item['seed'],
            backend=item['backend'], raw_path=item['path'], origin=origin,
            **{name: float(ledger[0, i]) for name, i in spec.V6.L.items()}, **computed)

    for item in protocol['schedule']:
        path, pin = STUDY / item['path'], index[item['path']]
        if any(pin[key] != value for key, value in item.items()) or sha(path) != pin['sha256']:
            raise ValueError('new raw row binding differs')
        ledger, hashes = load_raw(path, item['seed'], sha(STUDY / 'protocol.json'), item['backend'] == 'C_fast')
        records.append(record(item, ledger, 'new'))
        if item['group'] == 'native_equivalence':
            old_ledger, old_hashes = load_raw(STUDY / item['comparison'], item['seed'],
                                             reuse['baseline_protocol_sha256'], item['backend'] == 'C_fast')
            matched = ledger.tobytes() == old_ledger.tobytes() and hashes.tobytes() == old_hashes.tobytes()
            native_matches.append(dict(index=item['index'], identical=matched))
        elif item['group'] == 'constant_parity':
            parity.setdefault(item['pair'], {})[item['backend']] = (ledger.tobytes(), hashes.tobytes())
    parity_checks = []
    for pair, values in parity.items():
        match = set(values) == {'C_full', 'C_fast', 'Python'}
        match = match and values['C_full'][0] == values['C_fast'][0] == values['Python'][0]
        match = match and values['C_full'][1] == values['Python'][1]
        parity_checks.append(dict(pair=pair, identical=match))
    if (len(native_matches) != 8 or len(parity_checks) != 4 or not all(x['identical'] for x in native_matches) or
            not all(x['identical'] for x in parity_checks)):
        raise ValueError('native or constant-renderer engineering checks failed')
    for item in reuse['native_rows']:
        if sha(STUDY / item['copied_path']) != item['sha256']:
            raise ValueError('reused native row changed')
        ledger, _ = load_raw(STUDY / item['copied_path'], item['seed'], reuse['baseline_protocol_sha256'], True)
        fields = dict(group='science', role=item['role'], mode='native', world='patch', seed=item['seed'],
                      backend='C_fast', path=item['copied_path'])
        records.append(record(fields, ledger, 'reused_baseline'))
    scientific = [r for r in records if r['group'] == 'science']
    if len(scientific) != 192:
        raise ValueError('exact192 new+reused scientific rows required')
    metrics = METRICS + ('rec_cand', 'rec_accept', 'rec_events', 'rec_gain', 'births', 'deaths', 'n_peak',
                         'total_patch_stock_open', 'total_patch_stock_end')
    groups, paired = {}, {}
    for role in ('AO_rank0', 'AM_reference'):
        groups[role], paired[role] = {}, {}
        by_mode = {}
        for mode in ('native', 'constant1', 'constant055'):
            rows = [r for r in scientific if r['role'] == role and r['mode'] == mode]
            if len(rows) != 32 or sorted(r['seed'] for r in rows) != protocol['seeds']:
                raise ValueError('exact32 paired rows per genotype/renderer required')
            by_mode[mode] = {r['seed']: r for r in rows}
            groups[role][mode] = {key: moments([r[key] for r in rows]) for key in metrics}
        for mode in ('constant1', 'constant055'):
            paired[role]['native_minus_' + mode] = {
                key: moments([by_mode['native'][seed][key] - by_mode[mode][seed][key] for seed in protocol['seeds']])
                for key in metrics}
    status_counts = {}
    for row in records:
        key = str(int(row['status']))
        status_counts[key] = status_counts.get(key, 0) + 1
    summary = dict(status='complete', valid=True, protocol_sha256=sha(STUDY / 'protocol.json'),
        row_index_sha256=sha(STUDY / 'row_index.json'), new_backend_calls=148, new_scientific_lives=128,
        new_engineering_lives=20, reused_scientific_lives=64, combined_scientific_rows=192,
        new_native_ledger_values=148*107, new_native_hash_values=148*5, status_counts=status_counts,
        engineering_checks_passed=True, native_equivalence=native_matches, constant_parity=parity_checks,
        groups=groups, paired_native_minus_constant=paired, interpretation=protocol['interpretation'])
    with (STUDY / 'per_life.csv').open('w', newline='') as stream:
        writer = csv.DictWriter(stream, fieldnames=list(records[0]))
        writer.writeheader()
        writer.writerows(records)
    save(STUDY / 'summary.json', summary)
    return summary


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--saved-data-only', action='store_true')
    if parser.parse_args().saved_data_only:
        analyze()
