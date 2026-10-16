# Independent watchdog and preparation source review

The reviewed common/monitor/preparation source implements the declared resource
and ownership contract. Acceptance of the complete study still requires the
materialized input/protocol review. Exact reviewed source hashes are in
`watchdog_source_review.json`; no lives, builds, random draws or subprocess tests
were run by this review.

The monitor requires the exact budget dictionary before launch. The 120 CPU/120
wall preparation allocation leaves 10,680 CPU/7,080 wall seconds, with 8,280 CPU
seconds for search and at most 2,400 further CPU seconds for confirmation. The
second phase ceiling is an absolute cumulative CPU ceiling because measurement
includes monitor CPU, reaped children and active descendants; it is not a fresh
10,680-second allowance. A ten-second margin permits shutdown and cleanup.

There is one owned session worker with two kernel threads, one BLAS thread,
8 GiB address-space limit, combined monitor/descendant RSS stop at 4 GiB, and a
4 GiB host-availability floor. The child has CPU/address-space limits and a
parent-death kill binding. Subreaping, namespace/start-tick identity checks,
pidfd checks for descendant signaling, retained wait4 receipts and final empty
group/identity/descendant checks support ownership and cleanup. Prior attempts
and runtime artifacts are rejected; failed phases stop without retry or reduction
of confirmation.

Workers bind their parent PID, process group, namespace, monitor start ticks,
phase attempt, protocol and release hashes. Every phase rechecks source/input
pins, plus the explicit seed-audit and reservation hashes. Both the initial and
confirmation paths require the registered scope and recorded call inventory.

Preparation source copies all 32 ordered AO balanced24 genotypes and compares
them bitwise with the completed checkpoint and rank-zero endpoint. The imported
genetic material receives fresh IDs and the new native seed; prior scores and RNG
state are not resumed. It constructs the exact matching preset and inherited
POOL/persistent worlds, fixed seven-world confirmation definitions and fixed
generation-eight/final observations. The startup identity is predeclared from
retained evidence; its validation lives are counted in the registered eight
startup calls, not run during preparation.

The requested namespace-pin checks, exact budget-dictionary check, inclusion of
monitor RSS, and preparation wall allowance are present in the reviewed source.
No remaining material watchdog/source blocker was found. This is source review,
not a claim that a new watchdog fault-injection test was executed.
