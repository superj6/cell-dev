"""Write the descriptive table from saved phenotype counts; no life simulation."""
import argparse
import hashlib
import json
import shutil
from pathlib import Path

HERE = Path(__file__).resolve().parent
parser = argparse.ArgumentParser(description=__doc__)
parser.add_argument('--out', type=Path, required=True)
args = parser.parse_args()
OUT = args.out.resolve()
s = json.loads((OUT / 'summary.json').read_text())
labels = ('founder_row38', 'd_s51089_final_rank0', 'd_s51090_final_rank0')
short = ('row38', 'D51089', 'D51090')
lines = ['# Quantized phenotype changes after time 800 in completed K traces', '',
         'Nearly all cells already alive at 800 later changed a quantized neural property in these saved normal',
         'growing lives. The pattern is present in the founder and both D descendants. No post-800 emission-channel',
         'switches were observed in that cohort. These are descriptive traces, not a causal intervention.', '',
         '| Genotype | Mean alive-at 800 cells | Mean neural changes/life | Mean fraction changing neural knob |',
         '|---|---:|---:|---:|']
for label, name in zip(labels, short):
    p = s['genotype_summary'][label]['per_life']
    lines.append(f"| {name} | {p['alive_at800_cells']['mean']:.2f} | {p['neural_events']['mean']:.2f} | "
                 f"{100 * p['neural_changed_fraction']['mean']:.2f}% |")
lines += ['', 'Each genotype has four fixed saved life seeds. The table averages the four per-life fractions;',
          'it does not pool cells into independent replicates. Neural knobs are w0, w1, b, tau_m, t_ref, emit0,',
          'emit1, delta and g_r. A change is an actual logged grid switch: no arbitrary continuous-drift threshold',
          'is applied. Event counts include repeated reversals, so they are not counts of persistent changes.', '',
          '| Genotype | Seed | At800 | Later births | Changed neural cells | Neural switches | Late switches* |',
          '|---|---:|---:|---:|---:|---:|---:|']
for label, name in zip(labels, short):
    for r in (r for r in s['rows'] if r['genotype'] == label):
        lines.append(f"| {name} | {r['seed']} | {r['alive_at800_cells']} | {r['later_born_cells']} | "
                     f"{r['neural_changed_cells']} | {r['neural_events']} | {r['time_bins'][-1]['neural_events']} |")
lines += ['', '*Late means 1280<t<=1536, still only cells alive at 800. Later births are counted separately and',
          'never inflate the primary cohort. Per-life age bins 0..32, 32..128 and 128+ at 800, and deaths affecting',
          'exposure, are preserved in summary.json. The populations mostly contain old cells, but normal growth',
          'continues and can affect contacts and local signals. No adult-maturity inference follows.', '',
          '| Quantized knob | row38 cells changed | D51089 cells changed | D51090 cells changed |',
          '|---|---:|---:|---:|']
for knob in s['genotype_summary'][labels[0]]['per_knob']:
    values = [s['genotype_summary'][label]['per_knob'][knob]['fraction_cohort_changed']['mean'] for label in labels]
    lines.append('| ' + knob + ' | ' + ' | '.join(f'{100 * x:.2f}%' for x in values) + ' |')
lines += ['', 'Fractions again average the four lives. summary.json preserves every per-life knob count, change',
          'magnitude, endpoint-versus-t800 count, age and time bin. Some properties switch repeatedly and finish',
          'at their t800 value. Each full logged transition chain was checked against its preceding old value',
          'and the exact terminal phenotype for all 20 gridded knobs in all 12 traces.', '',
          'The observer logs every gridded phenotype switch at a local tick. Continuous asym, sec0 and sec1',
          'updates are intentionally unlogged; this analysis makes no claim about their stability. Effective',
          'incoming spike weights recomputed by derive are separate from these phenotype knobs. Normal K lives',
          'also differ from the tissue-clamped H/R controls. Counts establish ongoing quantized updates, not',
          'their fitness value, cause, learning, or use of changing evidence.', '',
          'Only the completed public K archive was read. All original manifest hashes and sizes were verified',
          'before analysis. No simulator, engine changes, new lives or active-study outcome reads were used.',
          'Eleven synthetic tests cover boundary/cohort conventions, late births, deaths, reversibility, corrupt',
          'chains and empty cohorts. Reproduce from the repository root:', '', '```sh',
          '.venv/bin/python results/phenotype_updates_20261014/analyze.py --archive results/traces_20261014 \\',
          '  --out outputs/phenotype_reproduction',
          '.venv/bin/python results/phenotype_updates_20261014/write_readme.py --out outputs/phenotype_reproduction',
          '```', '']
(OUT / 'README.md').write_text('\n'.join(lines))
artifacts = {}
for name in ('analyze.py', 'test_analysis.py', 'write_readme.py', 'summary.json', 'README.md'):
    p = OUT / name
    if name in ('analyze.py', 'test_analysis.py', 'write_readme.py') and p != HERE / name:
        shutil.copyfile(HERE / name, p)
    artifacts[name] = {'sha256': hashlib.sha256(p.read_bytes()).hexdigest(), 'bytes': p.stat().st_size}
for p in sorted((HERE / 'review').glob('*.json')):
    target = OUT / 'review' / p.name
    target.parent.mkdir(parents=True, exist_ok=True)
    if p != target:
        shutil.copyfile(p, target)
    artifacts[str(target.relative_to(OUT))] = {'sha256': hashlib.sha256(target.read_bytes()).hexdigest(),
                                              'bytes': target.stat().st_size}
(OUT / 'provenance.json').write_text(json.dumps({'status': 'exploratory_completed_data_only',
    'artifacts': artifacts, 'simulated_lives': 0, 'source_provenance_sha256': s['provenance_sha256']}, indent=2) + '\n')
