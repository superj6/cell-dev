# AB: blink selection precision versus depth

Source-only preparation, unregistered and unreleased. No endpoint extraction, initialization, library build or
simulation has been performed for AB. Root must register the exact paired namespaces and authorize preparation
before `prepare.py --prepare`; root alone supplies readiness after final review/publication.

From both fixed Z endpoints, compare four native generations at 3 + 4 selection lives with one generation at 12 + 16.
Both policies spend 4,096 selection lives per background and share the initial population and first offspring
cohort. This tests allocation between scoring and depth, not isolated precision or equal CPU. It does not reopen S.

Dry-run commands, from the repository root:

```sh
PYTHONDONTWRITEBYTECODE=1 ATEN_CPU_CAPABILITY=avx2 .venv/bin/python outputs/autonomous_visibility_precision_20261014/prepare.py
PYTHONDONTWRITEBYTECODE=1 ATEN_CPU_CAPABILITY=avx2 .venv/bin/python outputs/autonomous_visibility_precision_20261014/run_budgeted.py
```

Only a later root release permits `run_budgeted.py --run`. That monitor owns every build, golden and research life,
with at most two two-thread search workers, then one two-thread confirmation worker. No automatic resume/extension.
The sole confirmation subprocess invokes one standard numerical identity pair; each native search invokes one.
Scoring/numerical/common are unchanged Z copies. Other scripts narrowly adapt Z's preparation, monitor and raw rows.

Scope: 19,576 research calls plus ten existing ABI3 goldens; 9,000 cumulative CPU-seconds, search/startup ceiling 7,200,
confirmation reserve 1,800. Fixed source/data provenance, native genetic replay and raw 58-column accounting remain
required before complete inference. See PREREG.md and SCHEMA.md for exact roles, counts and interpretation.
