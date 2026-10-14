"""Exploratory sign/weight descriptions from the twelve completed K traces; no simulation."""
from pathlib import Path
import hashlib
import importlib.util
import json
import sys

import numpy as np

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))
path = ROOT / 'outputs/autonomous_traces_20261014/measure.py'
loader = importlib.util.spec_from_file_location('K_saved_trace_io', path)
m = importlib.util.module_from_spec(loader)
loader.loader.exec_module(m)
study = ROOT / 'results/traces_20261014'
report = json.loads((study / 'measurement/report.json').read_text())
assert report['status'] == 'complete'
rows = []
for life in report['lives']:
    source = study / 'measurement' / life['trace']
    assert hashlib.sha256(source.read_bytes()).hexdigest() == life['sha256']
    tr, _ = m.load_trace(source)
    a = tr.arrivals
    z = tr.cells.z.to_numpy()
    nonrefr = ~tr.steps.refractory.to_numpy()[a.step.to_numpy()]
    for start in (0, 800):
        for label, mask in (
            ('hidden_to_act', (a.sz.to_numpy() >= 2) & (z[a.cid.to_numpy()] == 1)),
            ('act_to_hidden', (a.sz.to_numpy() == 1) & (z[a.cid.to_numpy()] >= 2))):
            values = a.contrib.to_numpy()[nonrefr & mask & (a.t.to_numpy() >= start)]
            rows.append(dict(genotype=life['label'], seed=life['seed'], start=start, path=label,
                             arrivals=len(values), mean=float(values.mean()) if len(values) else None,
                             negative_share=float((values < 0).mean()) if len(values) else None,
                             positive_share=float((values > 0).mean()) if len(values) else None))
summary = dict(status='exploratory_completed_data_only', simulated_lives=0, rows=rows,
               trace_manifest_sha256=hashlib.sha256((study/'provenance.json').read_bytes()).hexdigest(),
               source_sha256={str(path.relative_to(ROOT)): hashlib.sha256(path.read_bytes()).hexdigest()},
               limits=['Normal growing lives, not H frozen interventions.',
                       'Actual nonrefractory arrival contributions; zero contributions retained.',
                       'Descriptive event weights do not identify the mechanism producing a fitness effect.',
                       'Each life is one unit; event counts are not independent replicates.'])
(Path(__file__).parent/'summary.json').write_text(json.dumps(summary,indent=2,allow_nan=False)+'\n')
for genotype in m.LABELS:
    for pathway in ('hidden_to_act','act_to_hidden'):
        subset=[r for r in rows if r['genotype']==genotype and r['start']==800 and r['path']==pathway]
        print(genotype,pathway,[(r['arrivals'], round(r['mean'],4) if r['mean'] is not None else None,
                                round(r['negative_share'],4) if r['negative_share'] is not None else None)
                               for r in subset])
