# Lateral dependence with tissue held fixed

Positive added lateral dependence in the frozen descendant tissue.

Primary interaction: **+1.6922 ± 0.1782 F** (512 paired lives).

| Contrast | Mean ± SE |
|---|---:|
| unfrozen gain | +0.9883 ± 0.1596 |
| frozen gain | +0.9445 ± 0.1589 |
| unfrozen lateral off gain | -1.5093 ± 0.0843 |
| frozen lateral off gain | -0.7477 ± 0.0899 |
| unfrozen lateral interaction | +2.4976 ± 0.1744 |
| frozen lateral interaction | +1.6922 ± 0.1782 |
| gain lost under freeze | +0.0439 ± 0.2038 |
| interaction change under freeze | +0.8055 ± 0.2170 |
| parent frozen lateral loss | +5.5052 ± 0.1310 |
| parent unfrozen lateral loss | +5.7935 ± 0.1363 |
| winner frozen lateral loss | +7.1974 ± 0.1535 |
| winner unfrozen lateral loss | +8.2911 ± 0.1472 |

Scientific genome-lives: 4,096. Monitored CPU: 1216.191 seconds. The separate 16-life preparation validation is not included in these estimates.

Both genotypes retain their own frozen tissue footprints. Freeze changes gene regulation as well as development. These comparisons do not establish a new algorithm, mature tissue, or matched-footprint information use. A small or unresolved interaction is not evidence of exact zero.

All four arms use the same 736-unit accounting window. Production guard/extinction charges remain in fitness; constant-tissue integration checks use only complete guard-free pairs. Whole-life end counts, path and last-birth descriptors are labelled separately from windowed fitness/captures/costs.

At t=768, the lateral lesion suppresses creation of new in-plane spike arrival messages; already scheduled messages, vertical spikes and chemical transport continue. The accounting window starts at 800 after pending structural claims and messages have settled. Prior dynamic state is retained.

[Preparation and validation](PREPARATION.md) · [Frozen protocol](protocol_excerpt.md)

```bash
.venv/bin/python results/frozen_20261013/analyze.py --study results/frozen_20261013
```
