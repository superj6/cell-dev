# N — fixed information/reference comparison at two durations

Prepared on 2026-10-14, before any N simulation or score. This document fixes a
measurement of the retained external C4 controller and existing reflex bodies.
It does not change an organism, an ABI, an evolutionary selection world, or any
in-life rule. The external controller remains an instrument for measuring the
value of sensory information.

## Question and fixed inputs

Does the recovered default C4 controller's advantage over fixed reflex bodies
remain at T=768 and T=1536 in the original headline base and POOL worlds?

The original headline used **d0=0.5 and d_min=0.25**. Those values are retained in
both worlds. POOL additionally has sigma=0.4 and lam_s=4; all other world values
and prices are the original `catch_speck_l4` values. Consequently this is a
duration transfer relative to those headline worlds, not relative to the old
conduction settings of experiment F. Full world dictionaries are frozen in
`protocol.json`.

Every world/duration cell has exactly these six fixed candidates:

1. Default C4, built-in controller id 5, with its exact recovered 21 parameters
   and hollow3 footprint (56 cells). The retained separately tuned C4 parameters
   are archived for provenance but are never used.
2. Frozen hollow3 reflex (56 cells).
3. The retained per-world retuned hollow3 reflex (56 cells).
4. Frozen hollow2 reflex (32 cells).
5. The same retained per-world retuned knobs transferred to hollow2 (32 cells).
6. The retained per-world retuned hollow3 reflex with the existing `K.t_ref=8`
   quieter setting.

All parameters, exact program hashes and body cells are fixed before scoring.
There is no retuning, body search, candidate replacement, winner follow-up, or
new controller behavior. The original recovered C4 source and replay wrapper
are copied byte-for-byte. Controller action costs, relay charges and delivery
latency use the existing measurement harness; computation is free.

## Samples, counts and comparisons

All six candidates receive the same ordered 512 seeds in both worlds for each
duration. T=768 uses block 40, seeds **51,400,000–51,400,511**. T=1536 uses block
41, seeds **51,410,000–51,410,511**. The prospective namespace audit found no
overlap with retained earlier smoke/validation samples or the enumerated pilot,
D/G and L training/validation seeds. Its source receipts are archived. Distinct
duration blocks mean that duration changes are not paired across durations.

Research count is **6 × 2 worlds × 2 durations × 512 = 12,288 candidate lives**.
Every fixed comparison is retained, including negative effects. Primary
comparisons are C4 minus frozen reflex and C4 minus retuned reflex, separately
in each of the four world/duration cells. Means and SEs are calculated from
within-seed differences; no life or candidate is selected away.

All three smaller/quieter contrasts against the best whole frozen/retuned
reference are also reported, along with all five C4-minus-reference contrasts.
“Best” means greatest mean fitness over the whole 512-life candidate, never the
best reference separately for each life. Exact mean ties use listed candidate
order. The fixed comparisons carry the primary interpretation. Best-reference
SEs reuse the scored sample and are descriptive, without selection correction.

For continuity with the plan, report whether the C4 gap over the best whole
frozen/retuned reference exceeds three SEs and reaches 1 F, and whether the best
smaller/quieter gain is below one quarter of that gap. These are descriptive
checks, not a world-admission decision. Also retain full income, poison/miss,
cost, cell and event accounting for every contrast. This narrow measurement
does not establish full G5 across capability worlds or what evolution can use.

## Bounded validation inside the same resource cap

Before research scoring, run exactly **40 T=64 validation lives** at one worker,
using seeds 51,099,000–51,099,003 (block 9, offset 9000). They are separate from
the previous block-9 smoke seeds and all research samples. No validation seed
or case is replaced if it fails.

For each world, two seeds compare built-in C4 with its unchanged logged copy.
Each copy's retained ping sequence is then replayed with real receptors disabled
in the same life, another life, and the existing altered-world leak check;
recorded actions must be byte-identical. Closed-loop controls on two different
seeds must establish sensitivity to changed ping input. This accounts for 12
controller lives per world. Two scratch reflex and two production reflex lives
check world parity, and two null-controller and two inert-body lives check world
stream parity, bringing the count to 20 per world and 40 total.

The existing scratch harness uses historical diagnostics in ledger columns
21/22; these columns and the combined all-state hash are excluded only from the
documented scratch-versus-production identity check. Every other ledger column
and component hash must match. Controller-copy checks compare every ledger
column, all five hashes and the first 12 diagnostic columns. Replay retains
every ping and action; an empty, truncated or oversized log fails validation.

The research fast library and full validation library are built from unchanged
pinned source. Generated C/library hashes are recorded before research rows.
Full per-life validation arrays, logs and all research arrays are retained.

## Failure, resource and scheduling rules

The total hard allocation is **3,600 CPU-seconds and at most two workers**,
including compilation, validation, monitor work and research. The monitor stops
at a 3,588-second threshold to leave termination room; it accounts for live
compiler/worker descendants, binds worker lifetime to its exact parent process,
and applies the remaining CPU limit before launch. No automatic retry, resource
reset or cap extension is allowed. A failed or incomplete study remains so.

The queue waits only for exact pinned L completion with no active or queued
work. It can then share the four-worker allocation with another two-worker
measurement. Readiness is a separate explicit release artifact. Preparation,
pure mocks and dry runs create no readiness or scientific work.

Guards, capacity failures, source/ABI/numerical mismatches or incomplete lives
fail the entire affected candidate and study. No failed life is omitted from an
otherwise scored candidate. Each 512-life row is validated and saved atomically;
source and release pins are rechecked before each row and before completion.
The final monitor requires all 12,288 research lives and all 40 validation lives,
as well as successful process exit and unchanged pins. No outcome determines
additional samples or a change of direction within this experiment.

## Reproducibility and checks before release

`protocol.json` freezes worlds, candidates, seeds, source hashes, numerical
identity and the L dependency. `input_sources.json` identifies recovered
artifacts; `inputs/` and `sources/` retain their bytes. The release template
additionally pins the scientific scripts, this preregistration and the pure
science tests. The public preparation preserves the numerical source snapshot.

The pure test suite covers the complete 24-row workflow, complete 40-life
validation workflow, fixed sample/candidate mapping, retained negative effects,
failure handling, exact-parent binding, cumulative CPU accounting, dependency
and source checks, no restart, and final actual-count enforcement. These tests
use synthetic arrays and mocked launch functions; they simulate no lives.
