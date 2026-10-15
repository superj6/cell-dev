"""Condense the complete frozen AN summary for root's post-experiment review."""
import hashlib
import json
from pathlib import Path

HERE = Path(__file__).resolve().parent
path = HERE.parent / 'analysis_result/summary.json'
s = json.loads(path.read_text())
assert s['status'] == 'complete' and s['total_calls'] == 28222
worlds = ['pool','persistent','blink80_5','blink80_20','turn100_blink80_20']
roles = ['AM_current_start','generation4','generation8']
metrics = ['captures','F','ordinary_cost','low_light_captures','bright_captures',
           'clicks','misses','n_end','n_H_end','live_time','contact_events','spikes']
def short(value):
    return {k:value[k] for k in ('mean','se','lower_3se','upper_3se')}
r = {'summary_sha256':hashlib.sha256(path.read_bytes()).hexdigest(),
     'primary':s['primary'],'retention':s['retention'],'absolute':{},'paired':{},'interactions':{},
     'accuracy':s['capture_accuracy'],'health':s['health']}
for w in worlds:
    r['absolute'][w] = {role:{k:short(s['absolute'][w][role][k]) for k in metrics} for role in roles}
    r['paired'][w] = {f'{new}_minus_{old}':{k:short(s['contrasts'][f'within__{w}__{new}_minus_{old}'][k])
                         for k in metrics} for new,old in [('generation4','AM_current_start'),
                         ('generation8','AM_current_start'),('generation8','generation4')]}
    if w != 'persistent':
        r['interactions'][w] = {role:{k:short(s['contrasts'][f'interaction__{w}_minus_persistent__{role}_minus_AM_current_start'][k])
                                      for k in ['captures','F','low_light_captures']}
                                  for role in roles[1:]}
out=HERE/'root_result_extract.json'
with out.open('x') as f:f.write(json.dumps(r,indent=2)+'\n')
for w in worlds:
    print(w, 'captures', [s['absolute'][w][role]['captures']['mean'] for role in roles])
    for new,old in [('generation4','AM_current_start'),('generation8','AM_current_start'),('generation8','generation4')]:
        m=r['paired'][w][f'{new}_minus_{old}']
        print(new,'minus',old,{k:m[k] for k in ['captures','F','ordinary_cost','low_light_captures']})
print('retention', {k:(v['passes_conventional_10_percent_diagnostic'],v['retained_90_percent_vector']) for k,v in s['retention'].items()})
print('primary',s['primary'])
