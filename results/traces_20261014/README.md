# Fixed continuation traces

Twelve fixed T1536 fast-POOL reference traces, with twelve C validation lives. Every one of the 57
ledger columns matches bitwise. Raw event tables reproduce all saved readouts without simulation.

Four shared descriptive seeds per genotype; the values below are paired means ± SE over those four
lives. Clicks per capture averages per-life ratios, rather than pooling counts. No significance or
new-algorithm claim is made.

| Descendant minus row38, full life | D51089 | D51090 |
|---|---:|---:|
| silent_time | -139.4138 ± 31.6826 | -160.1912 ± 41.4054 |
| silent_distance | -28.3592 ± 3.1130 | -15.5771 ± 7.2281 |
| total_distance | +0.6245 ± 27.7669 | +163.9918 ± 36.1475 |
| capture_zone_sample_share | +0.0140 ± 0.0064 | +0.0166 ± 0.0179 |
| clicks | -4.5000 ± 5.9090 | +24.0000 ± 8.9350 |
| captures | +6.2500 ± 4.9896 | +10.5000 ± 5.9090 |
| clicks_per_capture | -0.4657 ± 0.1570 | +0.0803 ± 0.2172 |

Full and800..1536 search/relay descriptions are in summary.json; each original per-life
readout and raw table is under measurement/. Largest-input paths omit subthreshold integration.
Silence movement alone does not show that silence is used as evidence. Tissues keep their different
growth, footprints and state. Missing ratios remain null, with no missing-life deletion.

Budget: 786.219558 of1,800 worker CPU-seconds; one simulation worker.

Recompute with `.venv/bin/python results/traces_20261014/analyze.py --check` from a checkout with
the pinned src files. The shared source archive preserves their bytes; this tool is not standalone.
