# Prepared terminal accounting audit

Source only until the complete monitor receipt and canonical `summary.json` are available. The script refuses an
incomplete execution. It imports neither the frozen measurement reader nor its analyzer and runs no simulator,
kernel build or random draw. Frozen study sources and inputs remain unchanged.

`audit_accounting.py` independently reconciles all 20 × 512 native ledgers, physical costs, guard/extinction
charges, stock/source/FIFO conservation, acquisition and fitness decomposition. It derives all absolute metrics,
six paired contrasts and the two endpoints' old-world retention margins using scalar `math.fsum` and sample
variances. It binds the 30,808-call inventory, three owned phases, cleanup, current launcher/source-review history,
three four-call startup receipts and all source/genome/raw/scored hashes.

After scalar accounting it invokes the already reviewed recorded-operation replay once. That replay reconstructs
1,792 offspring and 3,584 point additions, both complete final populations, every scored candidate, the shared first
cohort and cached endpoint selection. This reused module is explicitly separate from independent accounting and
the independently implemented selection mathematics audit under `terminal_selection_audit/`.

Run from the repository root only after terminal authorization:

```bash
ulimit -t 45
ulimit -v 8388608
/usr/bin/time -v -o outputs/resource_patch_selection_20261015/terminal_audit/resources.txt \
  env OMP_NUM_THREADS=1 OPENBLAS_NUM_THREADS=1 MKL_NUM_THREADS=1 PYTHONDONTWRITEBYTECODE=1 \
  timeout 75 .venv/bin/python \
  outputs/resource_patch_selection_20261015/terminal_audit/audit_accounting.py --run \
  > outputs/resource_patch_selection_20261015/terminal_audit/stdout.txt \
  2> outputs/resource_patch_selection_20261015/terminal_audit/stderr.txt
```

The outputs are `reviews/independent_accounting.json` and `native_replay_result.json`. Both are created only after
successful verification; existing replay evidence must match exactly. Existing accounting receipts are never
overwritten. The audit can also run against an archive with `--study PATH` when its `production/` snapshot exists.
No active scientific outcomes were opened while preparing this audit.
