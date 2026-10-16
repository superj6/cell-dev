# ABI 7 engineering completion

ABI 7 implements empty-site contact as a delayed physical consequence. A miss inside a depleted patch starts
one packet due after `patch_contact_delay` (80 in the new preset). A successful harvest never starts a job.
Repeated taps neither reset nor stack pending work. Maturity admits one packet or spills it if full; ordinary
passive arrivals remain independent. Pending work is invisible to cells. Ready stock changes only the existing
local field. FIFO bookkeeping distinguishes initial, passive and contact packets without changing their reward.

The world vector appends one field (83 total), and the ledger appends 36 counters (143 total). Cell inputs,
genomes, asynchronous rules, movement, receptors, candidate bounds, prices and random streams are unchanged.
The default caller remains ABI 2; explicit ABI 2–6 shapes and hash projections remain available.

Validation completed within the cumulative 900 CPU / 900 wall second allocation: **171.817438 CPU seconds,
157.166482 wall seconds**, peak owned RSS **891,564,032 bytes**. Every owned process group and descendant exited.
The worker policy allowed at most two computational threads, 4 GiB aggregate RSS, 8 GiB address space per
child, and required 4 GiB available host memory. These are measured integration resources; source preparation
and saved-file archival are separate lightweight work.

- The default nonslow Python pass returned 1,167 passes and three failures; 127 slow cases were deselected.
  The failures were an existing direct-C test passing 82 doubles to the new 83-field internal validator.
  Both test packing sites now use the current native layout. All 71 cases in that fixture then passed.
  Across these passes, all **1,170 unique applicable cases** passed, including 42 new direct-world C cases,
  22 new C/Python/observer lives, 24 explicit legacy/neutral C lives, and ABI 7 checkpoint/resume coverage.
- Eight additional fixed cases each ran C full, C fast and Python: **24 lives**. All 143 ledger values matched
  bitwise. C full/Python also matched all five hashes, raster and fate arrays. Cases cover counts 1–4, shifted
  and negative windows, equal periods, no motor, extinction, guards, and the preset delay.
- JavaScript passed 19 focused checks including **18 completed lives** (eight whole/stepped pairs and two neutral
  replays). Existing resource, visibility, matching and legacy suites passed. New resource-view checks mounted
  two supplied states without running a simulator. The existing matching viewer additionally used three partial
  lives in a DOM/canvas stub; this is not a real-browser rendering claim.
- Boundary checks cover empty-before-click initiation, exact-time left limits, same-group stock, repeated taps,
  passive/contact ties, FIFO/ring wrap, spill, window carry-in, right-excluded endpoints, uint64 hashes, neutral
  mode and corruption detection. Pure observer reads preserve clock/hash state.

The full regression inventory is larger than the new feature fixtures: **14,541 C full and 2,418 C fast returned
life rows**, **253 Python `_Life.run` invocations**, and **188 completed JavaScript runs**. Instrumented JS also
records seven partial advanced constructions and direct-world fixtures; the three matching-viewer partial
lives are additional. Native tests deliberately made 126 rejected calls, reported separately. These are
engineering tests, including existing toy search/resume checks, not scientific organism comparisons.

All failures remain visible. After the old C fixture was corrected, the JS counter preload failed because its
relative module path had one extra parent. Two inherited batch commands also omitted their required frozen
truth argument (large-trial hashes and matching viewer). Each failed before its affected JS simulation began;
only the unexecuted command was continued. Production physics did not change after the initial Python pass.

The early C source copy raced the initial parallel edit. Its bytes are retained as an intermediate snapshot;
the exact original from commit `84a0a20a60c0029cb061f5034ed6569563dcc773` is separately preserved. All other listed
early source copies match that commit. The frozen ABI 6 truth was copied independently from its published
archive and remained unchanged.

This establishes implementation agreement and compatibility on the retained engineering cases. It does not
show evolved planning, memory, profitable contact use or better acquisition. No contact baseline, controller
study or evolutionary continuation is released. Navigation with local obstacles is the next substantive
research direction; neither contact evolution nor perfect retention is a gate to it.
