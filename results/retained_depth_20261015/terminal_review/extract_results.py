"""Condense complete AO results for root; no simulations or endpoint selection."""
import hashlib
import json
from pathlib import Path

HERE = Path(__file__).resolve().parent
path = HERE.parent / 'analysis_result/summary.json'
s = json.loads(path.read_text())
assert s['status'] == 'complete' and s['total_calls'] == 138488
worlds = ['pool', 'persistent', 'blink80_5', 'blink80_20', 'turn100_blink80_20']
roles = ['AM_reference', 'AN_start', 'unchanged8', 'unchanged24', 'balanced8', 'balanced24']
metrics = ['captures', 'F', 'capture_income', 'ordinary_cost', 'low_light_captures', 'bright_captures',
           'clicks', 'misses', 'n_end', 'n_H_end', 'live_time', 'contact_events', 'spikes']
pairs = [('unchanged8', 'AN_start'), ('unchanged24', 'AN_start'), ('balanced8', 'AN_start'),
         ('balanced24', 'AN_start'), ('unchanged24', 'unchanged8'), ('balanced24', 'balanced8'),
         ('balanced24', 'unchanged24'), ('unchanged24', 'AM_reference'), ('balanced24', 'AM_reference')]


def short(value):
    return {k: value[k] for k in ('mean', 'se', 'lower_3se', 'upper_3se')}


r = {'summary_sha256': hashlib.sha256(path.read_bytes()).hexdigest(),
     'primary': s['primary'], 'retention': s['retention'], 'verdicts': s['verdicts'],
     'absolute': {}, 'paired': {}, 'accuracy': s['capture_accuracy'], 'health': s['health']}
for world in worlds:
    r['absolute'][world] = {role: {k: short(s['absolute'][world][role][k]) for k in metrics} for role in roles}
    r['paired'][world] = {f'{new}_minus_{old}': {
        k: short(s['contrasts'][f'within__{world}__{new}_minus_{old}'][k]) for k in metrics}
        for new, old in pairs}
    print(world, 'captures', [s['absolute'][world][role]['captures']['mean'] for role in roles])
    for new, old in pairs:
        m = r['paired'][world][f'{new}_minus_{old}']
        print(new, 'minus', old, {k: m[k] for k in ['captures', 'F', 'ordinary_cost', 'low_light_captures']})
with (HERE / 'root_result_extract.json').open('x') as stream:
    stream.write(json.dumps(r, indent=2) + '\n')
print('retention', {k: (v['passes_conventional_10_percent_diagnostic'], v['retained_90_percent_vector'])
                    for k, v in s['retention'].items()})
print('primary', s['primary'])
print('verdicts', s['verdicts'])
