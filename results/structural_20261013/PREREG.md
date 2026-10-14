### G. Fixed structural-operator comparison (prepared 2026-10-14)

This study tests whether the already approved silent-duplication and deletion operators help evolution
improve from the fixed eight-gene s5 row38 founder. A silent duplicate copies one gene's incoming regulation
and state while giving the copy no outgoing effect. Evolution can subsequently alter that spare copy.
The experiment supplies no behavior, routing weights, additional organism channel, clock or ABI change.

The two G searches use seeds 51089 and 51090, 16 generations each, and the same fixed founder, initialization,
worlds, life seeds, ordinary selection and diagnostics as the two D searches. The only evolutionary policy
changes are `dup_rate: 0.02` and `del_rate: 0.01`; `dup_split: false` remains fixed. The existing
`n_mut_scale: true` policy is retained. The policy comparison therefore includes deletion and the consequences
of active-gene-scaled mutation, rather than isolating duplication alone.

Each run starts with one exact founder plus 31 ordinary point-mutated copies. Initialization and mutation
generator state match D exactly. Structural operations start with generation-zero offspring; their random
draws then cause the mutation/crossover paths to diverge. Matching run seeds retains common world and life
seeds, not identical subsequent offspring. Selection keeps 32 from a cohort of 256, using three initial lives
and four additional lives for the top 64. There are 32,768 search genome-lives, 160 periodic validation lives,
12 fixed final diagnostic lives, and 4,608 independent confirmation lives: 37,548 research genome-lives total.

Both G endpoints and both D controls are fixed as the final population's rank-zero genome at generation 16.
All four are retained regardless of sign. Endpoints are frozen with their full checkpoint/config/source
identity before confirmation. No outcome from D is read to choose the comparison or its endpoint rule.
The control protocol, configuration and resource monitor are pinned at preparation; D endpoint hashes are
recorded only after D completes. Any invalid or mismatched search-life evidence blocks confirmation and
is reported, without changing endpoints or rerunning a replicate.

Confirmation uses all six fixed genomes in this order: original pilot, row38 founder, D seed51089 endpoint,
D seed51090 endpoint, G seed51089 endpoint, G seed51090 endpoint. Each receives the same 256 fresh seeds
51,930,000 through 51,930,255 (block93) at T=768, 1024 and 1536 in fast-conduction POOL. All measurements use
the full life from t=0. The primary contrasts are each G endpoint minus its matched D endpoint. Secondary
contrasts compare each G endpoint with row38 and the original pilot. For each contrast, the equal-duration
mean is computed within each seed before computing its mean and SE over the 256 seeds; the covariance among
durations is retained. Both signs, all durations and all fixed endpoints are reported. Gains exceeding
three SE and gains at least 0.5 F are identified separately. There is no selection from these results.

Before either G search begins, 18 validation-only full-kernel lives test silent duplication: the unmodified
founder plus one copy of each active source gene0..7 into spare slot8, with `split: false`, on fixed seeds
51,090,000 and 51,090,001 (validation block9), fast POOL T=1024. Every ledger column, event hash, spike time/UID,
and fate integer record must match bitwise. Fate floats may differ only in the added gene's state column,
which must match its source gene bitwise. Recorded status flags must also match; benign wall/chemical-clamp
flags are allowed, but extinction, guards, capacity/mismatch or log overflow fail validation. Fixed log
capacities are 100,000 spikes and 8,192 fates per life. Raw failing evidence is retained and there is no retry.
These 18 lives are outside the research-life count but inside the total CPU cap and have a separate 30-CPU-s cap.

The study has a fixed 14,400 worker-CPU-second cap, including validation, imports/builds, searches and confirmation;
there is no extension. The monitor stops at 14,380 CPU-s, sends TERM, waits at most two wall seconds and then KILL.
The reserve covers polling and shutdown with at most four simulation threads. Child CPU limits and monitor-death
termination provide independent safeguards. Neutrality uses one thread; the two searches use two each;
confirmation uses two. Launch waits for D and E completion and for any already released F work to finish,
independent of their scientific outcomes. No G readiness marker or scientific process is created by preparation.

Two search replicates do not establish general structural-search superiority. Life-level SE measures uncertainty
for these fixed endpoints, not uncertainty across evolutionary searches. A larger active-gene count, expression,
nonzero outgoing weights or duplicate ancestry alone does not establish functional use. Any later claim that
a new gene contributes to fitness requires a separate fixed intervention and independent evidence, with
developmental effects distinguished from computation in held-fixed tissue.
