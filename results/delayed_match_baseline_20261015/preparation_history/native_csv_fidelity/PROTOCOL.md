# Frozen AO endpoints on delayed matching

Prepared only; root launches after source/input review. Source milestone: `968bb81`.

All six roles in public `results/retained_depth_20261015/endpoints.json` are fixed:
AM_reference, AN_start, unchanged8, unchanged24, balanced8, balanced24. Exact genotype
file/raw hashes are checked and retained with the packed inputs. No evolution,
endpoint replacement, screening, or hand-built body gate occurs.

Each role runs the exact ABI5 `catch_delayed_match_l4` preset at T85 and T1024 on
the same 32 fresh development seeds, 52,430,000–52,430,031. Only T changes. Physical
prices, cell constants, task timings, target geometry, and interventions remain the
preset defaults. Block 143 is reserved for development, never later confirmation.
The namespace audit found zero seed-payload overlaps; literal matches are prior
half-open range endpoints, source hashes, or a disjoint older 43-million namespace.

The fixed order is T85 then T1024, public role order, ascending seeds: 384 one-life
C-fast calls. Six C-full calls then repeat T85/52,430,000, one per role, with fate
capacity 65,536. Total: **390 calls/lives**. Builds and startup run zero lives.
There is one attempt, no automatic retries, top-ups, or additional validation lives.

The monitor owns one one-thread worker pinned to one available CPU, bounds the whole
build/run/analysis process tree to 600 CPU seconds and 900 wall seconds, stops at
2 GiB summed RSS or below 4 GiB host-available memory, and gives the worker an 8 GiB
address-space limit. It uses the published AO subreaper, parent-death binding,
PID/start-time identity and descendant cleanup pattern. All runtime records are local.

Every ledger/status is retained. Analysis checks each life's integer, nonnegative
class counts and conservation; income = 500 × correct; native cost/F against the
ABI5 physical reconstruction; and all six full/fast ledgers byte for byte. Guard
and extinction outcomes remain in the tables. Accounting/capacity/log corruption,
truncated fates, missing planned rows, or replay mismatch prevent valid completion.

Outputs include every ledger in per-life CSV/raw NPZ, both sample-class ×
narrow/broad/no-completed-choice tables, choice coverage, conditional accuracy,
correct per opportunity, timeouts, unfinished counts, physical cost components,
F, and all status flags. F uses default physical accounting and guard charge;
there is no extra selection extinction surcharge. Positive F alone cannot establish
matching: a blind resolved choice has +225 expected gross reward before costs.

Six predetermined full logs reconstruct inclusive post-event occupancy at t14/15/25
and first/cumulative off-center sensory births. Here “off-center sensory” means
z=0 and (a,b)≠(0,0), in body coordinates. This measures physical sensory-plane
development, not nonzero/current receptor gain or actual cue information. Motion
changes the relation to the sample field. One seed per role is descriptive, and
the full 32-seed baseline is not the plan0.4 512-seed information-payoff test. Body
state can legitimately retain context; no neural-memory or prediction claim follows.

After root binds `release.json` to the final `protocol.json` hash, launch with:

```sh
PYTHONDONTWRITEBYTECODE=1 /home/jgon/project/ml/cell-dev/.venv/bin/python outputs/delayed_match_baseline_20261015/monitor.py --run
```

`worker.py`, `analyze.py`, and `monitor.py` are source-only without their explicit
execution flags. Reanalysis reads retained files and runs zero lives. Runtime
failure retains progress and outputs; unfinished scheduled work remains missing.
