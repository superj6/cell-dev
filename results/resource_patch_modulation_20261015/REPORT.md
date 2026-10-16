# Inherited pursuit benefits from depletion cues

The unchanged AO genome collects substantially more food when each patch's brightness follows its available
stock. It collects **21.4375 packets per life** with native cues, versus **16.1875** at constant amplitude 0.55
and **13.15625** at constant amplitude 1. The older AM genome also benefits. Neither genome was evolved in
this environment. This supports useful reuse of inherited sensory behavior before new resource adaptation.

These are 32 deliberately reused development lives per genome and condition, not fresh confirmation or
independent evolutionary replicates. The experiment changes sensory amplitude throughout development and
life. It establishes a whole-life contribution of stock modulation, without identifying memory, a stock
estimator, a mature circuit, visit order or formal world admission.

## Food and fitness

Entries are mean ± standard error across the 32 shared life seeds. Replenished food is a subset of total food.

| Fixed genome | Sensory amplitude | Total food | Replenished food | Production F |
|---|---|---:|---:|---:|
| AO | Native stock modulation | 21.4375 ±0.8636 | 15.5000 ±0.8531 | 8.171171 ±0.428789 |
| AO | Constant 0.55 | 16.1875 ±0.6436 | 11.0938 ±0.6435 | 5.247046 ±0.320447 |
| AO | Constant 1 | 13.1563 ±0.6826 | 8.5625 ±0.5406 | 3.540639 ±0.346009 |
| AM | Native stock modulation | 16.3438 ±1.1462 | 10.9063 ±1.0154 | 5.320797 ±0.557371 |
| AM | Constant 0.55 | 12.3438 ±0.8372 | 7.9688 ±0.6389 | 3.124758 ±0.376389 |
| AM | Constant 1 | 11.0313 ±0.6230 | 6.9688 ±0.5360 | 2.224130 ±0.313756 |

| Paired native minus constant | Extra food | Extra replenished food | F advantage |
|---|---:|---:|---:|
| AO minus 0.55 | 5.2500 ±0.9103 | 4.4063 ±0.8612 | 2.924125 ±0.455617 |
| AO minus 1 | 8.2813 ±0.9527 | 6.9375 ±0.8447 | 4.630532 ±0.471862 |
| AM minus 0.55 | 4.0000 ±1.3236 | 2.9375 ±1.1053 | 2.196039 ±0.638725 |
| AM minus 1 | 5.3125 ±1.2168 | 3.9375 ±1.0970 | 3.096667 ±0.597779 |

For AO versus constant 0.55, extra food contributes **2.563477 F** and lower physical costs contribute
**0.360649 F**: 87.67% of the mean fitness advantage comes from acquisition. Against constant 1, acquisition
contributes 4.043579 F and savings 0.586953 F, or 87.32% from acquisition. AM's corresponding acquisition
shares are 88.94% and 83.77%. These are decompositions of observed trajectories, not separate interventions.

AO makes 7.6563 empty-patch clicks with native cues, versus 26.8125 at 0.55 and 27.2500 at 1. Native minus
0.55 is **−19.1563 ±2.2869 empty clicks**, **−18.0000 ±2.8131 geometric misses**, and **−89.3627 ±8.6863**
distance travelled. Physical costs fall **369.3042 ±45.0008 energy**. Initial-origin food also improves
0.8438 ±0.2338 packets; the effect is not confined to replenishment. Offered source arrivals are identical
by seed, but admitted stock, spill and subsequent actions can differ. Native AO spills 4.9063 ±0.7833 fewer
packets than constant 0.55; spilled food is not automatically attainable profit.

Two fixed brightness controls reduce, but do not eliminate, ambiguity between information and sensory dose.
AO's native versus 0.55 receptor-delivery difference is −577.8438 ±329.7252 events. AM receives more events
with native cues than with 0.55 (+922.3750 ±523.2857), while also gaining food. Realized tissue differs:
AO ends with 81.7813 cells natively versus 80.5938 at 0.55 and 81.4688 at 1. These are not matched realized
footprints or equal-event-dose controls. All actual receptor activity and physical costs remain charged.

## Design and execution

The frozen protocol is `435d8439a33cc160ecdc4150e22fd845fb2ff8e31fdc532b570c4c2a568209c1`. Both fixed
genotypes, 64 native scientific rows, eight native engineering references and seeds 52,480,000–52,480,031
come from the completed inherited baseline. No genotype, endpoint or brightness level is selected here.

An isolated C renderer changes only the two lines computing per-patch amplitude. Native amplitude is
`0.1 + 0.9 * stock_left / 2`; the alternatives are exactly 1 and 0.55. Constant 1 agrees with native cues
until first depletion. Positions, widths, source laws, physical harvest, candidate envelopes and random
streams, cell rules, prices and available actions remain fixed. Actual acceptances, development and actions
can change causally. Own history can still support depletion inference, so this is not complete stock blindness.
No controller, new organism input or production code change is introduced.

All **148 new calls** returned: 128 scientific and 20 engineering, with 64 native scientific rows reused.
All 212 combined CSV rows have status 0. Eight native-hook rows reproduce saved baseline ledgers and hashes
bitwise; four constant-renderer triples agree on all 107 C-full/C-fast/Python ledger values and all five
C-full/Python hashes. Fast hashes retain their declared constants. The six isolated builds and all calls ran
in **31.042736 CPU /30.724609 wall seconds**, peak owned RSS **334.42 MiB**, with every owned process cleared.

After the last return, the original analysis failed because file metadata `path` collided with native movement
distance `path`. The invalid completion marker, incomplete monitor status, logs, original analyzer and all raw
rows are preserved. A separately reviewed analyzer changes exactly one metadata keyword to `raw_path`.
Saved-data recovery took **0.933887 CPU /0.936767 wall seconds**, with **zero additional lives or builds**.
`terminal_recovery.json` binds this recovery to the original failure; it does not rewrite execution history.

Independent saved-data accounting passes: 148 new and 72 copied raw files; all 212 CSV rows, 22,684 native
CSV values checked bitwise, 28,408 CSV numeric values, and 2,166 summary numbers; all engineering equalities
and the original-failure/recovery chain. Its separate external cost is 0.20 CPU /0.20 wall seconds.
The 600 CPU /1,200 wall package reserved 90 CPU /120 wall for preparation and publication. Charging that
whole reserve plus monitored execution gives **121.042736 CPU /150.724609 wall seconds allocated**; recovery,
review, audit and publication consume that reserved allowance, not additional scientific execution.

## Next decision

The result answers a useful first question: inherited pursuit can exploit action-dependent resource feedback,
and the gain includes more food. It does not answer whether new evolution can improve that use while retaining
older abilities. A short ordinary continuation from all 32 AO survivors, with old tasks retained in selection
and one fixed endpoint tested on a reserved resource combination, is the next priority. Keep ordinary prices
for this pilot: the measured cue advantage is predominantly acquisition, not a reason to reshape rewards.

This requires an explicit narrow revision separating bounded exploratory selection from formal section 0.4
admission. The present 32 reused comparisons do not satisfy its fresh 512-pair, strongest-reflex, footprint or
do-less requirements. Preserve those criteria for the stronger admission claim; do not manufacture a passing
claim or require a handwritten resource allocator before testing cumulative evolutionary accessibility.
