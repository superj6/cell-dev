# ABI 6 resource patches: engineering evidence

Persistent food patches now work in C, Python and JavaScript. Harvest removes a packet while leaving the patch
in place; independently scheduled sources replenish it. Available stock changes the ordinary local sensory
field. Only collected food minus existing physical costs pays. The genome, cell inputs, local asynchronous
rules, messages and prices are unchanged. Use explicit `spec.V6` and `catch_resource_patches_l4`; caller defaults
and explicit older ABI output shapes remain unchanged.

This environment follows the cumulative-capability direction: familiar pursuit can obtain initial food,
while reacting to depletion and continuing supply could add value without completing a prescribed sequence.
Those opportunities are hypotheses. No new evolved patch behavior, information payoff or accessible mutation
gradient is established by this engineering milestone. The next measurement is an inherited-population
baseline; external information controls and any evolution remain separate studies.

| Check | Result |
| --- | --- |
| Default Python regression | 1,086 passed, two fixture/style failures, 127 slow tests deselected. The ABI-version assertion and two overlong lines were corrected; both affected tests then passed. |
| Checkpoint/resume | New ABI6 three generations plus resumed three matches uninterrupted six byte-for-byte, including population and deterministic logs. |
| World boundaries | 71 direct C cases check exact event ordering, simultaneous harvests, frozen sensory snapshots, source spills, observation windows, provenance, extinction, guards and invalid worlds. |
| Fixed cross-language truth | Eight cases, each C full/C fast/Python, agree on all 107 ledger values; C/Python also match all five hashes and complete spike/fate records. |
| JavaScript | Eight whole and eight capped-stepping truth cases agree; the complete new suite has 20 checks and 22 advanced lives. Existing legacy/wound, visibility and matching checks pass. |
| Observer/UI | Python observer purity checks pass. The new viewer passes two supplied-state mounts with zero simulator calls; embedded preview scripts pass syntax checks. No real-browser rendering test is claimed. |
| Hygiene | Ruff and maintained-code whitespace checks pass. |

The seven monitored batches used **168.893127 CPU /144.450141 wall seconds**, with maximum owned RSS
654,729,216 bytes (624.40 MiB). This includes failed engineering commands and their limited corrections,
compilers and checkpoint subprocesses. All owned processes are clear. The announced allowance was 1,800 CPU /
3,600 wall seconds, one worker, at most two CPU threads, 4 GiB owned RSS, 8 GiB address space and 4 GiB host
memory reserve. Static inspection and archive packaging are separate from these measured runtime batches.

Original failures remain in the archive. The first focused pass had six fixture errors: five old full/fast
comparisons used different raster capacities, changing truncation status, and one expected the wrong exception
type. No trajectory or status masking was used. The broader pass exposed the outdated ABI-version assertion
and formatting only. The JS batch omitted required truth-file arguments for two old fixtures; both then passed
with those arguments, with preceding successful tests preserved. Source review also added a provenance bound,
JS time-window validation and full-width source-counter hashing before cross-language execution.

Python instrumentation counts wrapper invocations, including rejected calls and checkpoint subprocess calls;
raw-C fixture invocations bypass it. These counts are engineering inventories, not a count of independent
scientific lives. JS inventories distinguish rejected construction, direct-world fixtures and advanced lives.
The 24 raw NPZ outputs are exactly the eight declared full/fast/reference truth triples.

Open the [paused automatic preview](resource_patches_preview.html) for a fixed existing body in the three-patch
world. It uses historical s5, seed 42000002 and T128, the declared `grn_count3_preset` engineering case.
It is an implementation illustration, not a patch-selected genome. Stock and source overlays are for readers
and never enter the cells. No external network dependency is required.

The exact contract is [ABI6_RESOURCE_PATCHES.md](../../docs/ABI6_RESOURCE_PATCHES.md). Verify retained evidence
and installed source hashes without simulations:

```sh
.venv/bin/python results/abi6_resource_patches_20261015/verify.py
```

After later source edits, use `--archive-only` to check the immutable evidence. `finalization.json` records the
tested source pins and validation scope. The archive includes original failed fixtures, command logs, budget
and cleanup receipts, the fixed truth triples, preview, and the source-only publisher/verifier. Replaying
simulations is separate from this hash-only verification.
