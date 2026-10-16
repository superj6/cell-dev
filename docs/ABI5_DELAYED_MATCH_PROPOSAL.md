Status: implemented and integrated after isolated C/Python/JavaScript validation. On 2026-10-15, the user
replied to this concrete proposal: "you don't need my permission for these things". Bounded environment/ABI
extensions of this kind are covered by their autonomy instruction. Engineering evidence is in
`results/abi5_delayed_match_20261015/`; AO's original source pins and results are archived unchanged.
Information-payoff measurement and evolution are separate next steps; no matching behavior is claimed.

I recommend **delayed matching by cue shape** as the next environment. The organism sees a narrow or broad
glow, the glow disappears, and later two choices appear. Choosing the shape seen earlier pays. The same current
choice scene can therefore require different actions depending on earlier information. This moves beyond
continually chasing whichever target is visible. Evolution remains responsible for discovering the behavior.

This is a first step toward richer interactions, not the full destination. It can support later tests of longer
sequences and context-dependent action while reusing the existing sensory and motor system. Perfect retention,
optimal cost penalties and a complete explanation of current circuits are not prerequisites for this exploration.

The exposure audit found that independently renewing reward/harm targets and equal food targets already exist
in earlier studies. Repeating those would add less than a new temporal decision structure. See the
[decoy continuation](../results/decoy_evolution_20261014/README.md) and
[earlier niche map](../results/taskvar_study/nichemap/table.csv).

### World contract

Each life contains successive trials. The tissue, its motion and all cellular state persist across trials.
The first sample starts at `t0`. There is no organism reset, phase input, shared cell tick or reward input.

| Phase | Initial preset |
|---|---|
| Sample | Draw narrow/broad independently with probability 1/2. Show one stationary Gaussian at the body's position at sample onset, width 0.6 or 1.2, for an independent uniform 15–25 time units. |
| Blank | Remove the sample completely; background pings continue for an independent uniform 20–40 time units. |
| Choice | Show both widths on opposite ends of a fresh random axis around the body's position at choice onset, at a common uniform distance 2–4. Randomize which end holds each width. Both capture radii are 1. |
| Resolution | The first click hitting either choice consumes the whole opportunity: +500 for matching the sample, otherwise a charge of 50. After 50 time units without a hit, the choice times out. |
| Reset gap | Background only for 5 time units, then a new independently drawn sample. |

Each Gaussian component has peak rate 2; background is 0.05. Choice signals add through the existing scalar
receptor field. Equal component peaks do not mean equal total signal at the centers: the tails overlap, and
the broader cue supplies more integrated signal. Width or intensity can identify a choice; neither identifies
which choice pays on this trial without the sample. A stationary receptor exactly at sample center gets the
same rate for both classes; off-center receptors or movement can distinguish them. This is available sensory
information, not evidence that the present lineage uses it.

Clicks outside an active choice, or missing both choices, cost 10 and never advance the trial. All ordinary
cell, action, message, receptor, growth, guard and extinction charges remain. Only one outcome may be paid per
trial, including simultaneous records. Resolution takes effect for eligibility immediately; physical removal
is deferred until the end of the existing timestamp group. Later clicks in that group are misses. No next
sample starts in that group because the reset gap is positive. Other receptor records retain left-limit
semantics; do not clear pending events or cellular traces at a phase boundary.

World events continue to be simulator bookkeeping. `world_to(t)` consumes phase transitions strictly before
`t`; events exactly at a deadline see the preceding phase. Thus a click exactly at the choice timeout may
resolve that opportunity before timeout processing. Phase transitions strictly before life end are processed;
the right endpoint is excluded. Sample, blank and reset transitions use the scheduled time, not the time of
the next cell event. World scheduling adds no cell-visible clock. Normal consequences of this individual's
clicks and position are allowed; the world never adapts to population performance.

### Limited ABI extension

Add explicit ABI 5 and preserve current caller defaults and explicit ABI 2/3/4 behavior. Append seven world
fields after index 69: `task_mode`, `sample_min`, `sample_max`, `blank_min`, `blank_max`, `choice_T`, `reset_T`.
Mode 0 is legacy with all six appended durations zero; mode 1 is delayed matching. Durations are finite,
positive and within existing time bounds, ordered min/max; require `blank_min > d_min` so raw sample receptor
deliveries have arrived before choice onset. Persistent local traces are allowed.

Mode 1 initially requires CATCH, neutral visibility, stationary targets (`v_t=tau_turn=t_resp=0`),
`b2_amp=b2_p=1`, `b2_mode=0`, distinct ordered widths, equal capture radii and
`2*R_min > rho_c+b2_rho`. Existing `R_min/R_max` supply choice distance. `R_cap` supplies correct reward and
negative `b2_value` supplies the wrong-choice charge **regardless of which physical slot was chosen**.
Reject incompatible combinations explicitly. The initial preset uses the numbers above and otherwise inherits
current SPECK cell physics and prices. There is no new genome field, receptor modality, gene input or message.

Use appended counter-hash streams for sample class, durations, choice axis/distance and width assignment,
keyed by trial index with separate purposes. They do not share draw counters with cells or legacy world streams.
No stream is indexed by correctness. Phase/choice records are observable in hashes and viewer traces only.
Keep a constant receptor-candidate bound sufficient for two components throughout all phases.

Append sample-class-specific readouts for choice opportunities opened, choice carry-in at accounting-window
start, correct choices, wrong choices, timeouts and unfinished choices. For each class, enforce
`opportunities + carry_in = correct + wrong + timeouts + unfinished`. A counted open choice interrupted by
actual life end or a guard is unfinished, not dropped. Preserve existing CATCH extinction semantics: the world
continues through `T`, including subsequent opportunities and timeouts, even after all cells die. Extinction
alone does not terminate a choice. Record sample starts and terminal phase in the world trace. Outcomes and
charges use the existing half-open accounting window; pre-window actions still change world state. Include
boundary fixtures for opportunities that cross `t_open`.

Existing `captures` and `b2_clicks` retain physical slot-hit meanings; they no longer determine correctness in
mode 1. Both the kernel and Python scorer must use the new correctness counts for conditional income/cost,
without changing mode-0 formulas. `low_light_captures` is zero in this mode. Mode-specific distance/zone
readouts must refer to the nearest active choice and count only choice scenes, with this distinction documented.
The viewer must label slot hits separately from correct choices.

### What would count as progress

Fresh placement makes the choice scene independent of sample class **conditional on the body's current
state**. It prevents solving the task simply by parking at the sample location. The earlier cue can still change
motion, morphology, chemical state or neural activity. These are legitimate forms of retained information;
successful matching alone would not locate the memory or prove a new neural circuit.

A sample-blind chooser earns an expected 225 per resolved opportunity before physical costs at these prices.
Positive reward is therefore insufficient. Report sample class × {narrow choice, broad choice, no completed
choice}, coverage, timeouts, unfinished opportunities, reward per opportunity, costs and ordinary fitness.
Distinguish gains on both sample classes from a policy that responds only to one. Measure fixed preferences
and use of current cues as alternatives to retained sample information.

After engineering validation, prepare a bounded information-payoff measurement using only the same receptor
pings and ordinary actions at matched footprints. An external instrument may retain sample information;
comparisons remove that information and include fixed preferences and do-less controls. Such instruments
remain measurements and never enter evolved tissue. Keep tuning separate from at least 512 fresh paired
lives for the admission measurement in plan 0.4. A smaller pilot, if needed, is diagnostic only. Freeze exact
arms, seeds, total calls across backends, and CPU/memory limits before launch; report the budget beforehand.
Failure of a hand-built body is never a world-admission gate.

Then test ordinary evolution from the continuing population, measuring new capability and old tasks in the
same fixed descendants. Reserve delay/geometry combinations for transfer before using them to guide selection.
This proposal does not preselect an evolutionary winner or promise that delayed matching will emerge.

### Implementation and validation scope

The approval covers world dynamics, ABI packing/loading/export/scoring, C/Python/JS parity, focused compatibility
tests and a watchable automatic-mode presentation. JS currently rejects two-blob worlds, so this includes
mode-specific two-choice rendering and physics; it does not silently enable all historical second-blob modes.
Interactive target dragging is rejected for this task until separately specified.

Test legacy-neutral byte/hash behavior, full/fast agreement, C/Python/JS truth, thread/scheduler determinism,
checkpoint/resume, rate bounds, all phase boundaries, both classes/slots, misses/repeated hits, window boundaries,
timeout/click ties and incomplete lives. Use bodies as execution fixtures without requiring a winning body.
Preserve pinned historical sources and study inputs. Isolate implementation while any old pinned run is active.

The earlier [ABI 4 approval](ABI4_VISIBILITY_PROPOSAL.md) covered flash/blink only. The user's 2026-10-15
clarification authorizes proceeding autonomously with this delayed-match extension and its compatibility work,
superseding the earlier requirement to ask for environment/ABI work of this kind. Report experiment budgets
before substantial runs. Paid compute, population-responsive worlds and changes to cell rules remain separate
from this proposal.
