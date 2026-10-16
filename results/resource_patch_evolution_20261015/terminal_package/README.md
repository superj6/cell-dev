# Terminal archive preparation

These helpers are prepared source. They have not packaged, verified or published a terminal result.
They import no simulator, build system, numerical library or random generator.

After the owned study has completed, independent accounting and recorded-genetics replay must pass.
The expected independent receipt is `reviews/independent_accounting.json`, bound to protocol, summary,
row index and all 15 raw /15 scored batch hashes. The genetics receipt is `native_replay_result.json`.
All eight startup calls remain represented by the two four-call startup identities and their retained
ABI6 full/fast truth returns; golden identity calls do not acquire invented raw ledgers.

Stage into a new outputs directory, using terminal prose supplied by the root agent:

```sh
PYTHONDONTWRITEBYTECODE=1 /usr/bin/time -v -o <separate-packaging-resource-log> \
  .venv/bin/python outputs/resource_patch_evolution_20261015/terminal_package/pack.py \
  --out outputs/resource_patch_evolution_terminal_stage_20261015 \
  --readme <terminal-README.md> --report <terminal-REPORT.md>
```

The helper refuses incomplete terminal markers, changed prospective evidence and existing destinations.
It preserves the original prospective README, verifier and manifest in `registration_history/`; every
other prospective artifact remains at its original relative path. It copies all native run files,
generation-four and final checkpoints, checkpoint-bound logs, startup records, phase attempts/budgets,
15 raw and 15 scored NPZ files, the canonical summary, independent accounting and genetics receipts.
The zero-call launcher failure, original release, namespace correction and launcher source remain explicit.
Every original returned confirmation NPZ is kept unchanged, separately from scored outputs. Build caches,
compiled libraries and new pure-test temporary directories are excluded; any already-published
prospective fixtures remain intact. Extra terminal evidence can be
included with repeated `--include <study-relative-path>` arguments. A failure leaves its partial stage
and failure receipt; it does not retry or change the published archive.

The default verifier checks production source hashes against git revision
`52e390ae0b39b6c954e414ae07a0386b8ccc075f`. `--snapshot-production` instead embeds every source named by the
protocol's production pins; a verifier seeing this directory requires the complete pinned set.
Namespace references remain bound to the repository's historical public evidence.

Verify the final stage or public copy with no simulations:

```sh
PYTHONDONTWRITEBYTECODE=1 .venv/bin/python <archive>/verify.py
```

Verification checks hashes and cross-links, not independent arithmetic or genetic RNG reproduction.
Those narrower guarantees come from the retained accounting and recorded-operation replay receipts.
The packaging helper writes only a fresh `outputs/` directory. Root reviews and publishes the result;
preparing these sources neither launches another life nor changes the frozen study.
