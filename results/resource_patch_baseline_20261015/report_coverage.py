"""Post hoc descriptive patch coverage from retained counters; no strategy inference or new lives."""
import csv
import json
from pathlib import Path

HERE = Path(__file__).resolve().parent
rows = list(csv.DictReader((HERE/'per_life.csv').open()))
result = {}
for role in ('AO_rank0', 'AM_reference'):
    subset = [r for r in rows if r['group'] == 'reference' and r['world'] == 'patch' and r['role'] == role]
    counts = [sum(float(row[f'patch_harvest_{i}']) > 0 for i in range(3)) for row in subset]
    result[role] = dict(lives=len(subset), harvested_patch_count_histogram={str(n): counts.count(n) for n in range(4)})
result['interpretation'] = 'Post hoc descriptive coverage; totals do not specify visit order, revisits or memory.'
with (HERE/'patch_coverage.json').open('x') as stream:
    json.dump(result, stream, indent=2)
    stream.write('\n')
