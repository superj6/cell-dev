# N: fixed information payoff at two durations

The unchanged default C4 controller and five fixed reflex references were measured on 512 shared
seeds per world and duration. No controller tuning or organism change was involved.

| World/duration | C4 − frozen reflex | C4 − retained retuned reflex |
| --- | ---: | ---: |
| base_T768 | +13.403 ± 0.223 | +13.257 ± 0.223 |
| pool_T768 | +13.784 ± 0.205 | +13.547 ± 0.204 |
| base_T1536 | +13.128 ± 0.166 | +13.112 ± 0.168 |
| pool_T1536 | +13.335 ± 0.146 | +13.218 ± 0.151 |

Values are mean paired F difference ± one SE; every fixed comparison and sign is retained.
The original headline d0=0.5/d_min=0.25 worlds are retained; only duration changes.
The four cells are separate comparisons. Distinct duration seed blocks do not support paired duration claims.

Research lives: 12,288; bounded validation lives: 40; monitored CPU: 1385.716 / 3,600 seconds.

See `summary.json` for all 57-column means, all fixed contrasts, cost decomposition and limitations.
`PREREG.md` and `prelaunch/` preserve the prospective design. This is an external information-payoff
measurement, not a world-admission decision or a claim about evolved capability.

```sh
.venv/bin/python results/information_duration_20261014/analyze.py --study results/information_duration_20261014 --check
```
