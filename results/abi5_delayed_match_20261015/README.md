# ABI 5 delayed matching: engineering evidence

The delayed-matching environment is implemented in the C kernel, Python reference and maintained JavaScript
viewer. A narrow or broad sample disappears, a blank interval follows, then two shapes appear at fresh locations.
The first hit pays only when its shape matches the earlier sample. Genomes, cell inputs, messages and local
asynchronous cell rules are unchanged. There is no phase, class, reward or shared-clock input to cells.

Use explicit `spec.V5` or `life.abi: 5` with `catch_delayed_match_l4`. Caller defaults and explicit ABI 2/3/4
shapes remain unchanged. The exact contract is in [LIFE_ABI.md](../../docs/LIFE_ABI.md) and
[the scoped proposal](../../docs/ABI5_DELAYED_MATCH_PROPOSAL.md). Seven world fields and twelve class-specific
choice counters are appended. Fitness uses conditional correctness; physical slot hits are reported separately.
Each class conserves opened plus carried-in choices across correct, wrong, timed-out and unfinished outcomes.

| Check | Result |
| --- | --- |
| Default regression suite | 945 passed, 127 slow tests deselected; includes ABI5 three generations plus resume three matching uninterrupted six byte-for-byte. |
| Cross-language truth | Eight fixed cases agree on all 70 ledger values and five full hashes; C/Python also match complete spike and fate records. Full and fast C ledgers agree. Full and capped JavaScript stepping agree. |
| Boundary checks | Both classes and slots, exact deadline hits, repeats, misses, carry-in, right-excluded endpoints, extinction, guards, background sensing, independent choice geometry and parameter rejection. |
| Final defensive fix | 85 affected Python/C/readout checks pass; eight C-full/C-fast/Python cases and JavaScript parity rerun after enforcing choice-count reconciliation in C and JS. |
| JavaScript compatibility | Existing legacy and visibility checks pass; a direct trial-index test covers values above 2^32. Viewer DOM smoke checks cover labels, phase transitions, replay and next seed. |
| Code hygiene | Ruff and maintained-code whitespace checks pass. |

The full regression run used 140.40 CPU seconds and at most 593 MiB of owned process-tree memory. The final
conservation follow-up used 14.67 CPU seconds and about 342 MiB. Runs used one CPU/thread with explicit limits.
Detailed batch receipts retain backend counts and their limits: pytest instrumentation counts in-process API
requests, including rejection cases, and excludes subprocess/raw-C calls. It is not a total executed-life count.

The full suite preceded the final defensive C/JS conservation checks. Those checks flag impossible counter
imbalances without changing valid trajectories; targeted injected-counter regressions and fresh-directory
cross-language truth validate the final sources. `finalization.json` binds the installed source snapshots.
Original failures remain: a pytest instrumentation-hook signature prevented collection; lint found import order;
one JS fixture used the disabled-kill sentinel; and a large-trial hash fixture exposed 32-bit truncation, repaired
with explicit 64-bit trial folding. These were engineering checks, not failed or retried scientific evaluations.

Open the [fixed preview](validation/delayed_match_preview.html) to see the first predeclared execution fixture.
It is an existing reflex body, not a selected delayed-matching winner. The earlier preview is retained separately;
the final preview embeds the final engine. No real-browser rendering/playback test is claimed.

Verify archive and installed sources without simulation:

```sh
.venv/bin/python results/abi5_delayed_match_20261015/verify.py
```

After later source changes, `--archive-only` verifies the immutable record. Recheck final JavaScript truth:

```sh
node results/atlas/play/test_delayed_match.js --truth results/abi5_delayed_match_20261015/validation/truth_conservation_fix/truth.json
```

For a bounded fresh C/Python export, pass `--worktree . --out outputs/<fresh-validation>` to the archived
`validation/export_truth.py`; it refuses to overwrite a prior export. Earlier receipts retain their original
source paths and hashes. Historical study kernels and embedded viewers remain archived unchanged.

This milestone establishes implementation agreement and compatibility. It contains no new evolved matching
behavior or scientific world-admission result. The information-payoff proposal is a separate next step: measure
the value of retaining sample evidence at a matched physical footprint, then evolve on informative demands
while checking earlier capabilities and reserving transfer cases.
