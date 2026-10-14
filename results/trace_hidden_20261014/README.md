# Hidden-cell inputs in twelve saved traces

This is an exploratory reanalysis of completed K data. It simulates no new lives.

In all four saved D51090 lives, almost all delivered hidden-to-act inputs after t800 are negative.
Act-to-hidden inputs are predominantly positive. This is consistent with inhibitory feedback,
but the founder also has negative hidden-to-act inputs. These signs do not explain the causal
hidden-message fitness effect measured in H: K uses normal growing lives, while H freezes tissue.

Each row below describes one life over t800..1536. Counts include only arrivals outside the
receiver's refractory period. Mean input is the effective membrane contribution; zeros remain
in counts and sign fractions. An arrival is not an independent experimental replicate.

| Genotype | Seed | Hidden → act arrivals | Mean input | Negative | Act → hidden arrivals | Mean input | Positive |
|---|---:|---:|---:|---:|---:|---:|---:|
| founder_row38 | 51890000 | 211 | -1.4805 | 100.0% | 251 | 1.6574 | 100.0% |
| founder_row38 | 51890001 | 119 | -1.4601 | 100.0% | 146 | 1.7945 | 100.0% |
| founder_row38 | 51890002 | 362 | -1.3139 | 100.0% | 432 | 1.9612 | 100.0% |
| founder_row38 | 51890003 | 303 | -1.3750 | 100.0% | 286 | 1.8702 | 100.0% |
| d_s51089_final_rank0 | 51890000 | 322 | -0.9946 | 100.0% | 321 | 1.6032 | 100.0% |
| d_s51089_final_rank0 | 51890001 | 70 | -0.8411 | 82.9% | 67 | 1.5728 | 100.0% |
| d_s51089_final_rank0 | 51890002 | 479 | -0.8304 | 92.1% | 392 | 1.7592 | 100.0% |
| d_s51089_final_rank0 | 51890003 | 226 | -1.1250 | 98.2% | 172 | 1.7987 | 100.0% |
| d_s51090_final_rank0 | 51890000 | 968 | -1.5621 | 95.7% | 757 | 2.1513 | 100.0% |
| d_s51090_final_rank0 | 51890001 | 819 | -1.6482 | 100.0% | 645 | 2.1680 | 100.0% |
| d_s51090_final_rank0 | 51890002 | 536 | -1.7782 | 100.0% | 486 | 2.1422 | 100.0% |
| d_s51090_final_rank0 | 51890003 | 939 | -1.3651 | 99.5% | 642 | 2.2525 | 99.7% |

All 48 per-life descriptions, including full lifetimes, are in `summary.json`.
The analyzer uses NumPy and the unchanged public K archive, with no simulator imports.
From the repository root:

```sh
.venv/bin/python results/trace_hidden_20261014/analyze.py \
  --archive results/traces_20261014 --out outputs/trace_hidden_reanalysis
```

The original exploratory script, its output and the independent review are preserved
under `review/`. The portable analyzer reproduces every descriptive row exactly.
This evidence suggests a mechanism to test; it does not establish memory or an algorithm.
