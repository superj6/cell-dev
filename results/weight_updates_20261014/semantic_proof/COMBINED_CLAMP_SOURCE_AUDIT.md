# Source audit: ongoing phenotype and effective spike-weight updates

This is a read-only source proof for the existing GRN-mode POOL simulator. It runs no lives, designs no behavior,
and uses no O outcomes. It assumes the registered fast POOL physics, no exogenous killing or stuck-cell event,
and the same genotype, life seed and pre-fork history. Bounds below use fork 768 and accounting open 800.

Let S be `division_off + apoptosis_off` (flags 12), I be `S + identity_clamp` (76), P be
`S + pheno_fixed` (140), C be `S + identity_clamp + pheno_fixed` (204), and F be `freeze` (16).
All flags start at the same fork; there is no global clock or new biological channel.

The clearest three-arm decomposition is S, C, F. C and F hold both gene state and decoded phenotype fixed and
block new division and tick apoptosis. Their sole cell-physics update difference is that C continues `derive()`
at each local tick while F skips it. With structure held fixed, `derive()` can affect physics only through the
quantized, direction-dependent incoming spike weights. It does not turn chemistry off. C-minus-F therefore
measures the conditional fitness effect of ongoing effective receive-weight updates, using local chemical and
contact state and including early transient carryover and subsequent closed-loop
changes in spikes, movement, captures and costs. It does not establish pure memory, learning, a new algorithm or adult maturity.

## Exact tick-path comparison

`kernel.c:869` skips GRN updates under either identity_clamp or freeze. `kernel.c:906` skips phenotype decoding
under either pheno_fixed or freeze. `kernel.c:907` calls derive unless freeze is active. `kernel.c:911` skips
apoptosis under apoptosis_off or freeze; `kernel.c:965` skips new claims under division_off or freeze.
Thus C and F execute identical code paths except the derive call. They both process the inbox, re-anchor the
membrane using the previous phenotype, preserve traces and receptor inputs, update chemistry, schedule the same
hash-keyed local ticks, and permit ordinary spike firing. The reference implementation agrees at
`reference.py:1051`, `:1074`, `:1085` and `:1123`.

`derive()` (`kernel.c:567`) computes, for each viewed neighbor d,

    s_d = pol0 * (inc[d,0] - m[0]) + pol1 * (inc[d,1] - m[1])
    shat_d = s_d / (max_e abs(s_e) + 1e-6)
    w_eff[d,c] = q8(w_c * (1 + a_c * shat_d))

An unviewed slot has s_d=0. The concentrations and contact view are local; the fixed phenotype supplies pol,
w and a. `s_d` also enters division placement (`kernel.c:978`), but S/C/F disable new division, so that route
cannot affect their post-fork physics. Incoming spike delivery reads `w_eff` at arrival time (`kernel.c:1140`),
not at emission. Effects are consequently network effects and can propagate through other cells.

## Pending claims and births

A claim copies its daughter genes into a claim-owned blob at SEND time (`kernel.c:1007-1018`). Resolution
(`kernel.c:1075-1082`) passes that saved blob to birth; it never rereads the mother's current genes. A later
parent GRN tick cannot change an already-sent daughter's inherited payload. The mother was partitioned when
sending, not when the claim resolves.

All arms still resolve pre-fork claims normally. `birth()` unconditionally copies the saved genes, decodes a
phenotype and derives initial weights (`kernel.c:773-775`), even under freeze. This initialization is identical
in C and F, with empty neighbor view; after birth, their tick update paths differ only by derive as above.
Pending deliveries are not cancelled by a fork (`LIFE_ABI.md:1473`, `kernel.c:1070`). New structural decisions
are blocked, but a claim sent before 768 can produce a birth before 768.25. Born/ack/present notices settle before
768.75. Their shared effects do not invalidate the C/F comparison; subsequent derive calls can incorporate
newly learned contacts, while freeze retains its cached weights.

## Why identity_clamp alone is insufficient for a clean weight contrast

In an ordinary pre-fork tick, the code decodes theta before division. Division can then change the mother's g
by subtracting `asym*Q`, while theta still reflects its earlier g (`kernel.c:906`, `:1014-1016`). Therefore I and
P need not coincide even when no new post-fork divisions/deaths occur. At the first post-fork tick, I decodes the
already-partitioned g; P retains the pre-fork theta. The changed phenotype can persist indefinitely. Allowing a
32-time-unit settling interval does not undo this state difference. Equality is only conditional on theta
already matching the decode of the clamped g (and the GRN-mode assumptions); it is not a general theorem.

S-minus-I does isolate allowing new tick GRN state updates versus suspending them, with both arms retaining
readout/derive and blocking new structure. Its physical effects run through decoded phenotype and subsequent
feedback; it does not specifically isolate receptor/activity inputs or direct GRN energy expenditure. I-minus-F
also permits the first-tick phenotype reset above, so it cannot generally be labeled a pure weight-update effect.

P-minus-F has only private GRN-state differences plus derive under these no-division/no-death conditions:
private genes have no remaining physical output when theta is clamped. However, C is a stronger control because
it also holds that private state fixed and skips the corresponding GRN arithmetic. It avoids relying on a
private-state irrelevance argument. S-minus-C is the conditional effect of continuing GRN/phenotype updates,
including any readout catch-up from a pre-fork partition; C-minus-F is the cleaner weight-update contrast.

## Every outgoing gene-state path and costs

A source search of all `X->g` accesses finds: recurrent GRN input/update (`kernel.c:874-898`); phenotype readout
(`:626-639`); division payload/mother partition (`:1007-1018`); birth initialization (`:773`); and diagnostic gene
snapshots at birth/death (`:730`, `:779`). There is no direct gene-state receptor, membrane, secretion, message,
world or price input outside decoded phenotype. Genome Dm/km are fixed constants, not evolving cell gene states.
The 23 decoded knobs control membrane bias/time/refractoriness, channel sends/delay, twitching, receptor gain,
secretion, polarity/weight modulation, trace time constant and structural choices. C and F retain identical
values of every one of those knobs, including each pending newborn's initialized values.

There is no modeled cost per GRN/readout/derive operation. Tick charging integrates living time and secretion
(`kernel.c:1251-1258`); spikes charge spike, twitch and would-be outgoing-message amounts (`:1645-1652`);
claims charge division (`:1708-1710`); receptor events, misses and decoy clicks retain ordinary charges. Thus
C-minus-F does not save a hidden computation fee. Its changed spikes/messages/twitches, capture/miss outcomes,
receptor events and possible production guard penalties can change F. Living/secretion costs are the same for
complete matched C/F lives with unchanged tissue; no new post-fork claims are charged. Chemical packet count
is not itself a message-cost term. Host CPU differs because derive runs; this matters for the study cap, not
as an in-world gene-computation charge. All guard/extinction penalties must remain in scoring.

## Timing and interpretation limits

The hash-based normal is a bounded Irwin-Hall value in [-6,6) (`kernel.c:130-137`). For P0=2, clock_sd=.05 and
tick_jit=.1, the maximum local tick gap is 2*exp(.3)*1.1 = 2.9696893767. Every existing cell therefore gets its
first post-fork tick before 770.969690; the latest pending newborn's first tick is before 771.219690 using the
same conservative gap bound plus its latest birth. Presence notices settle before 768.75. A spike sent before
768 arrives by 768 + .5*exp(.6)*1.1 +2 =771.00216534 under the existing fast delay and maximum decoded delay.
All these bounds precede800. Chemistry continues indefinitely; there is no bound that removes all future
chemical effects. The settling interval does not reset membrane state, cached weights, past chemical state or
the moving world. Early post-fork differences can persist into the measured interval.

The three arms share a structural history within each genotype, but different genotypes can have different
bodies. Complete, guard-free matched arms should have identical terminal per-layer counts, zero measured
births/deaths, last_birth<800 and integrated cell-time 736*n_end. Guarded rows remain in F. Capacity or ledger
mismatch remains an implementation failure. No equality of complete event hashes or wall-clock/CPU timings is
claimed. A positive added C-minus-F contrast means that keeping these local, chemically modulated receive
weights current contributes more to that fixed endpoint's advantage than to its founder's, conditional on the
fixed post-fork phenotype. Nonlinearity and network feedback prevent additive mechanistic attribution.
