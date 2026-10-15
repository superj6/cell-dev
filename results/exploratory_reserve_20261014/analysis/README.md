# AH independent analysis

This reader is bound to protocol
`0a9e505969ed11cd8f240f9404bbff2adf9a91d91d5387252fd9595874c61be4`.
It was prepared before release and makes no measurement outcome claim. Actual input
verification checked 102 study pins, 35 production pins, two configurations, the
66-value ABI3 world and all 65 historical AE L92 timing rows. The single shared
32-row initialization replayed bit for bit from 62 recorded point additions.

The terminal entrypoint is:

```sh
PYTHONDONTWRITEBYTECODE=1 python analysis/analyze.py --study <archive> --out <new-output>
```

It requires complete first-attempt resource and source evidence. It checks both
native searches, including the separate reserve lottery, every recorded ranking
input and tie-stream transition, the first 256 candidate genotypes, extended
checkpoint identities and final rank-zero endpoints. Recorded genetic arithmetic
uses pinned definitions; it performs no new genetic draws or life simulations.
Unretained per-life search ledgers cannot be reconstructed from the native logs.

Three full 512-life ABI3 confirmation rows produce 219 paired vectors: reserve
minus control, control minus start, and reserve minus start. Capture count in the
first contrast is the primary behavioral estimate. Unchanged F, capture income,
ordinary costs and guard/extinction penalties remain explicit. One deliberately
chosen background and one matched search pair do not estimate policy reliability.
Capture improvement with worse F is a tradeoff; neither result demonstrates a
memory mechanism or a more sophisticated algorithm by itself.

`reader_source_review.json` and its historical peer preserve the source-only
state. The distinct bound reviews and actual-input receipts establish the later
prepared state. Binding changes only the protocol literal. `selection.py` is the
new independent policy checker; the whole-life accountant and genetic arithmetic
helper are unchanged from AF. Historical AF readers and the ordinary selector are
retained under `history/`.

The focused suite passed 47 checks. A further single import/lottery check passed
after test-only archive-root handling was corrected. Synthetic fitness tests
exercise control equivalence, protected exclusions, ties, accumulated four-generation
state and corruption rejection; the three confirmation test rows stay in memory.
The earlier test failures are preserved: one purported corruption initially wrote
an unchanged value, and four accumulated-state fixtures omitted `curve.gen`.
No engine was called. Producer-side restart checks use synthetic data only; the
scientific pilot permits no resume. The as-run `verify_preparation.py` retains its
original workspace-relative helper locations; portable verification uses
`analyze.verify_protocol()` and `native_audit.initialization_audit()` directly.
