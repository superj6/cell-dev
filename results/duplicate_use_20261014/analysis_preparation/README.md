# Independent J archive analysis, prepared before outcomes

These tools inspect completed data only. They add no candidate, intervention, seed, selection rule or simulation.
They do not change J's pinned protocol, runner or monitor. The completed-data analyzer returns an incomplete status
before reading inputs or G outcomes whenever J's monitor has not completed. It also requires completed G/H/I budgets
without active or queued work.

The analyzer independently replays recorded G genetics in NumPy, including FP32 point changes, whole-gene crossover,
all duplication origins (including discarded children), deletion and every generation's retained origin registry.
It compares each final rank0 to the endpoint JSON and measurement receipt, enumerates every active origin>=16 gene,
and verifies raw deletion bytes and decoded ABI3 runtime tables against canonical active-bit masking.

It reconstructs all57 raw ledger columns and60 production columns, preserving guard and extinction penalties;
checks exact raw/aggregate bytes and seed order; repeats strongest-loss selection with the fixed slot tie break;
checks fresh confirmation and its paired uncertainty; and reconciles income, all priced costs and penalties.
Both empty-branch cases and the all-empty case remain explicit. No sign or pass flag can cause extra scoring.

Checkpoint bytes and the original pinned checkpoint-validation receipt are retained. NumPy analysis independently
replays rank0 genetics but does not deserialize checkpoints or re-run RNG/selection. G's own full checkpoint audit
is a separate stronger source of evidence. A confirmed loss establishes whole-life contribution for the measured
fixed genotype, including development; it does not establish an adult algorithm or expanded computation.

After J finishes, the working command is:

```bash
.venv/bin/python outputs/autonomous_duplicate_use_20261014/analyze.py \
  --study outputs/autonomous_duplicate_use_20261014 --export results/duplicate_use_20261014
```

Export preserves the entire original public preparation under `prelaunch/`, every raw row and decision, exact G
lineages/endpoints/checkpoints, source and dependency pins, CPU receipts, the independent analysis and review tests.
It re-analyzes the exported copy before writing its final hash manifest. Public recomputation needs Python+NumPy:

```bash
python analyze.py --study . --check
```

The synthetic tests use no life simulations. In the repository, optional genome cross-checks use the existing
synthetic G fixture and Layout operators. Ordinary public analysis never imports Torch or production evaluators.
The original single-empty-branch review test is preserved byte-for-byte as text alongside its passed-test receipt.
