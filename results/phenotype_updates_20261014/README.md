# Quantized phenotype changes after time 800 in completed K traces

Nearly all cells already alive at 800 later changed a quantized neural property in these saved normal
growing lives. The pattern is present in the founder and both D descendants. No post-800 emission-channel
switches were observed in that cohort. These are descriptive traces, not a causal intervention.

| Genotype | Mean alive-at 800 cells | Mean neural changes/life | Mean fraction changing neural knob |
|---|---:|---:|---:|
| row38 | 116.00 | 1858.50 | 96.78% |
| D51089 | 152.50 | 3292.75 | 98.21% |
| D51090 | 172.50 | 3807.00 | 97.71% |

Each genotype has four fixed saved life seeds. The table averages the four per-life fractions;
it does not pool cells into independent replicates. Neural knobs are w0, w1, b, tau_m, t_ref, emit0,
emit1, delta and g_r. A change is an actual logged grid switch: no arbitrary continuous-drift threshold
is applied. Event counts include repeated reversals, so they are not counts of persistent changes.

| Genotype | Seed | At800 | Later births | Changed neural cells | Neural switches | Late switches* |
|---|---:|---:|---:|---:|---:|---:|
| row38 | 51890000 | 117 | 5 | 112 | 1844 | 725 |
| row38 | 51890001 | 108 | 10 | 105 | 1302 | 218 |
| row38 | 51890002 | 120 | 12 | 115 | 2652 | 689 |
| row38 | 51890003 | 119 | 18 | 117 | 1636 | 578 |
| D51089 | 51890000 | 153 | 29 | 151 | 3750 | 1202 |
| D51089 | 51890001 | 143 | 40 | 142 | 2358 | 724 |
| D51089 | 51890002 | 151 | 46 | 146 | 4097 | 1308 |
| D51089 | 51890003 | 163 | 49 | 160 | 2966 | 1063 |
| D51090 | 51890000 | 183 | 22 | 177 | 3893 | 1648 |
| D51090 | 51890001 | 175 | 6 | 173 | 3846 | 1463 |
| D51090 | 51890002 | 172 | 24 | 166 | 3311 | 1056 |
| D51090 | 51890003 | 160 | 0 | 158 | 4178 | 1501 |

*Late means 1280<t<=1536, still only cells alive at 800. Later births are counted separately and
never inflate the primary cohort. Per-life age bins 0..32, 32..128 and 128+ at 800, and deaths affecting
exposure, are preserved in summary.json. The populations mostly contain old cells, but normal growth
continues and can affect contacts and local signals. No adult-maturity inference follows.

| Quantized knob | row38 cells changed | D51089 cells changed | D51090 cells changed |
|---|---:|---:|---:|
| w0 | 31.20% | 28.66% | 27.78% |
| w1 | 42.69% | 42.51% | 41.95% |
| b | 88.38% | 93.99% | 94.09% |
| tau_m | 0.42% | 1.80% | 0.29% |
| t_ref | 2.61% | 5.26% | 2.28% |
| emit0 | 0.00% | 0.00% | 0.00% |
| emit1 | 0.00% | 0.00% | 0.00% |
| delta | 0.00% | 0.00% | 0.00% |
| kappa | 0.00% | 0.00% | 0.00% |
| p_div | 9.91% | 8.64% | 7.26% |
| p_die | 0.00% | 0.00% | 0.00% |
| phi | 10.53% | 8.95% | 6.57% |
| pol0 | 97.79% | 91.97% | 87.81% |
| pol1 | 98.93% | 93.87% | 98.71% |
| tau_tr | 36.68% | 40.55% | 37.77% |
| a0 | 85.24% | 78.96% | 59.24% |
| a1 | 76.72% | 85.60% | 95.34% |
| chi | 20.25% | 80.42% | 20.75% |
| zeta | 67.50% | 56.25% | 95.50% |
| g_r | 70.14% | 70.53% | 76.25% |

Fractions again average the four lives. summary.json preserves every per-life knob count, change
magnitude, endpoint-versus-t800 count, age and time bin. Some properties switch repeatedly and finish
at their t800 value. Each full logged transition chain was checked against its preceding old value
and the exact terminal phenotype for all 20 gridded knobs in all 12 traces.

The observer logs every gridded phenotype switch at a local tick. Continuous asym, sec0 and sec1
updates are intentionally unlogged; this analysis makes no claim about their stability. Effective
incoming spike weights recomputed by derive are separate from these phenotype knobs. Normal K lives
also differ from the tissue-clamped H/R controls. Counts establish ongoing quantized updates, not
their fitness value, cause, learning, or use of changing evidence.

Only the completed public K archive was read. All original manifest hashes and sizes were verified
before analysis. No simulator, engine changes, new lives or active-study outcome reads were used.
Eleven synthetic tests cover boundary/cohort conventions, late births, deaths, reversibility, corrupt
chains and empty cohorts. Reproduce from the repository root:

```sh
.venv/bin/python results/phenotype_updates_20261014/analyze.py --archive results/traces_20261014 \
  --out outputs/phenotype_reproduction
.venv/bin/python results/phenotype_updates_20261014/write_readme.py --out outputs/phenotype_reproduction
```
