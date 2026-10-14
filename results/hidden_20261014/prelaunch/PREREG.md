### H. Hidden and lateral spike dependence of fixed continuation endpoints (prepared 2026-10-14)

The completed D study found further gains in both fixed final descendants of s5 row38. H asks whether those
additional gains rely more on spike messages sent by hidden-plane cells after tissue growth has been held fixed.
Hidden cells are those at lattice height z >= 2. This measurement adds no behavior, world response, organism
channel, clock, price or ABI change. It uses existing ABI 3 interventions only.

All three genotypes are fixed before scoring: row38, D seed 51089 final population rank 0, and D seed 51090 final
population rank 0, each from generation 16. Raw genotype hashes and their completed D checkpoint hashes are pinned.
Both endpoints remain in every comparison, irrespective of sign; there is no selection by H scores or morphology.

The twelve arms are three genotypes crossed with normal, freeze, freeze+lateral_off and freeze+hidden_off.
All arms share 512 fresh seeds 51,940,000 through 51,940,511 (block94), giving 6,144 research genome-lives.
The world is POOL with fast conduction (d0=.5, d_min=.25, sigma=.4, lam_s=4), T1536. Interventions start at 768;
fitness and additive counts use the common accounting interval 800..1536 (736 time units), including normal arms.
All other physics and prices match D and E. Whole-life counters such as path and terminal tissue counts are
labeled separately from interval fitness/capture/cost accounting.

The primary contrast for each D endpoint is
`(D-row38)freeze - (D-row38)freeze+hidden_off`, computed within each life before mean and SE across 512 seeds.
Secondary contrasts report the analogous added lateral dependence, each endpoint's gain in every condition,
normal gain minus frozen gain, and each genotype's own hidden/lateral lesion loss. Both positive and negative
effects are retained. Three-SE flags are descriptive; an unresolved effect is not zero. Both descendants were
selected by D evolution, not by H, but their life-level SE does not measure uncertainty over search replicates.
Full ledgers preserve income, every cost and production guard/extinction penalties; guards are not censored.
Invalid capacity or accounting-mismatch failures stop the measurement as incomplete.

`hidden_off` prevents creation of new spike-arrival messages from senders at z >= 2, in all directions. Incoming
messages to hidden cells and already emitted messages still arrive. Hidden cells continue firing, and their
spikes and would-be outgoing messages pay the ordinary charge. Their chemical secretion/transport continues.
The effect can be indirect, through other cells in the remaining network. `lateral_off` similarly suppresses
new in-plane spike sends while retaining charges; vertical sends and chemistry continue.

`freeze` suppresses subsequent GRN/phenotype/effective-weight updates and new division/death decisions, while
membrane activity, receptors, spike generation and chemical transport continue. Claims already sent before 768
can resolve before 768.25; associated presence notices finish before 768.75. Under these fixed physics, pre-fork
spike arrivals finish by 771.002166. Opening accounting at 800 provides a settling interval, without erasing past
membrane states, chemical states or world trajectories. No adult-maturity claim is made.

For each genotype, all three frozen arms must have zero measured births/deaths and last_birth < 800. Complete,
guard-free triplets must have equal terminal total/sense/motor/hidden cell counts, t_end 1536, and live_time equal
to 736 times terminal cell count within integration tolerance. Benign wall/chemical flags are allowed. Guard or
extinct rows remain in the fitness comparisons and their exclusion from the structural check is counted.
Different genotypes may have different frozen tissue and state; this is not a matched-footprint experiment.
Freeze also changes computation, so normal-minus-freeze does not isolate development. A positive hidden or
lateral interaction establishes conditional message dependence; it does not establish a new algorithm.

The fixed cap is 3,600 worker CPU-seconds, two simulation threads, with no extension or automatic reset. The
monitor counts worker/descendant CPU, stops at 3,588 seconds, sends TERM and then KILL after at most two wall
seconds; child CPU limits and parent-death termination are independent safeguards. H waits until G's resource
record is complete with no active or queued jobs. G's scientific outcome does not change the protocol. An
abnormal G stop requires operational review before H can launch. No readiness marker or process is created by
preparation. Existing E validation supports the fixed accounting window; H preparation tests synthetic rows
and mocked processes only. Numerical-identity startup golden checks run after worker release; they are separate
from the 6,144 research lives and their CPU is included in the cap. No extra validation lives are scheduled.
