### R. Ongoing phenotype and effective receive-weight updates (prepared 2026-10-14)

Full freeze holds gene state, decoded cell properties and effective incoming spike weights fixed at once.
R separates these existing operations with three controls. The design was fixed before O outcome inspection;
no O result chooses a genotype, condition or comparison. This is external measurement with existing ABI 3
interventions; it adds no organism behavior, channel, clock, price or population-responsive world.

All three genotypes are fixed: s5 row 38 and both D generation-16 final population rank-0 endpoints, search seeds
51089 and 51090. Their raw genotype hashes, completed checkpoints, health records and full recorded genetic
replay are pinned. Both descendants remain in every comparison regardless of sign or morphology.

The nine arms cross those genotypes with three conditions, all activated at the common experimental fork 768:

- S: division_off + apoptosis_off (flags 12), holding structure fixed after pending claims settle.
- C: S + identity_clamp + pheno_fixed (flags 204), also holding gene state and decoded phenotype fixed while
  locally modulated effective receive weights continue updating.
- F: existing freeze (flags 16), additionally holding those effective receive weights fixed.

All arms share 512 fresh block 104 seeds, 52,040,000 through 52,040,511, giving 4,608 research genome-lives.
The world is unchanged fast POOL: d0=.5, d_min=.25, sigma=.4, lam_s=4 and T1536. Fitness and additive ledger
counts use the common 800..1536 accounting interval, 736 time units. All other physics and prices match D/E/H.
Whole-life counters such as path and terminal cell counts are distinguished from interval capture/cost data.

For each D endpoint, the primary contrast is `(D-row38)C - (D-row38)F`, computed per seed before its mean and SE.
It asks whether ongoing local effective receive-weight updates contribute more to that endpoint's advantage
than to its founder's, conditional on fixed phenotype. Secondary contrasts are each endpoint's analogous added
S-minus-C effect, all six endpoint gains in S/C/F, and each genotype's own C-minus-F and S-minus-C effects. All
16 paired vectors and all 60 raw ledger columns are retained. The added S-minus-C and C-minus-F vectors telescope
to gainS-minus-gainF, but their SEs must not be added: they share seeds and covariance. Three-SE flags are
only descriptive. Negative and unresolved effects remain; unresolved is not equivalence. Life-level SE concerns
these fixed descendants, not repeatability over evolutionary searches.

The source proof is preserved in semantic_proof/. In GRN mode, C and F skip the same gene update, phenotype
readout, new division and tick apoptosis branches. Their remaining cell-physics update difference is derive(),
which recomputes quantized receive weights from the fixed phenotype and local chemical/contact state. Its other
output only affects disabled division placement. Incoming spikes use the cached weights at arrival time.
Chemistry, receptors, membrane dynamics, spike generation and ordinary charges continue in every arm.

C-minus-F is a conditional ongoing effective receive-weight update effect, including early transient carryover
and subsequent changes in spikes, movement, captures and costs. It is not a pure memory or learning test. The
weight update does not directly read activity or receptor traces; with fixed secretion and phenotype,
its evolution can reflect autonomous chemical relaxation from the pre-fork state. A positive C-minus-F alone
does not demonstrate sensory adaptation, learned weights or use of changing evidence. There
is no modeled GRN/readout/derive computation fee; host CPU changes are separate from organism fitness. S-minus-C
includes continuing gene/phenotype updates and readout catch-up: pre-fork division partitions the mother's genes
after phenotype decoding, so a later readout may change phenotype even without a new gene-update step. This is
why identity_clamp alone is not the chosen control. Network feedback prevents additive mechanistic attribution.

Claims copy daughter genes at send time, never reread the mother at resolution, and still resolve after the
fork. Pending birth can occur before 768.25; associated presence notices settle before 768.75. Birth decodes
phenotype and initializes weights unconditionally in C and F. Every existing cell's first post-fork tick occurs
before 770.969690, latest pending newborn tick before 771.219690, and pre-fork spike arrivals before 771.002166.
These bounds precede accounting open 800. Chemistry continues indefinitely; settling does not erase membrane
states, past chemistry, cached weights or moving-world history. Early differences may persist into measurement.
No claim of adult maturity, a new algorithm or matching footprints across genotypes is made.

All nine arms must have zero measured births/deaths and last_birth < 800. Within each genotype, complete,
guard-free matched S/C/F triplets must have equal terminal total/sense/motor/hidden counts, t_end 1536, and
live_time equal to 736 times terminal count within integration tolerance. Guard/extinct rows stay in fitness;
only their structural-check exclusion is counted. Capacity and ledger mismatch are implementation failures
that leave the study incomplete. Income, every cost and ordinary guard/extinction penalties are retained.

The fixed cap is 3,600 cumulative CPU-seconds with two simulation threads, no extension or automatic reset.
The monitor counts its own CPU, including waiting, plus worker and descendant CPU; it stops at 3,588 seconds,
then sends TERM and KILL with a bounded two-second wait. Child limits and exact-parent death termination provide
independent safeguards. R waits only for Q to report complete with empty active and queued jobs. Q's results
never change R; an abnormal Q stop requires operational review before launch.

Preparation runs only source checks, saved D genetic replay and pure/mock tests. Existing fixed-window checks
are reused. The two standard numerical-identity startup goldens run only after worker release, reuse seed 11
at T200, are separate from 4,608 research lives, and count toward the same CPU cap. No extra validation lives,
readiness marker or launch is created by preparation.
