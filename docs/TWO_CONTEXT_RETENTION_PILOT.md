# AL: can two-context selection reduce the observed capability tradeoff?

Authorized by the user's instruction to continue on our judgment (2026-10-15), followed by explicit permission
for local experiments with safe memory use. This bounded comparison proceeds as AL. The original proposal is
preserved in `results/retention_selection_proposal_20261015/`.


I recommend one small matched continuation to test whether keeping the ancestral task in selection reduces forgetting. AK found that the AI-control lineage gained captures on persistent targets and both nearby variants, while losing about 39% of ancestral POOL captures. There is therefore an observed retention problem to address; AK did not establish a new-edge weakness.

The proposed change is outside the cells: one branch continues to earn its ordinary score on persistent targets; the other earns the average of that same score from equally many POOL and persistent lives. Cells, prices, physical rules and local asynchronous execution stay unchanged. Neither world reacts to the population, and organisms receive no shared channel or clock.

## Authorization and scope

The earlier raw-F family-fitness question no longer blocks this work. The authorized pilot uses a fixed 50/50
selection average within 5,400 CPU-seconds. Continue useful local follow-up experiments on our judgment; stop
and report if substantial progress appears to require more resources. Physical prices and local asynchronous
organism rules stay fixed. No rented compute or spending is authorized.

## Concrete comparison

Both branches start from **all 32 final AI-control survivors**, in their saved order, retaining duplicate genomes. Import their genomes, with an old-to-new ID crosswalk, and start fresh genetic and tie-breaking RNG streams; do not import prior scores or resume state. Both arms use the same newly allocated run seed and identical initial population.

Use the ordinary 32-parent + 224-offspring search for four generations, with structural mutation off. Every candidate receives four initial lives; the ordinary top 64 receive four more, and the ordinary top 32 by the pooled raw mean F survive. Both branches use exactly this 4+4 budget and the existing ranking/tie calls. The first 224 offspring must match byte for byte before selection. Later populations may diverge because their parents differ.

| Branch | Initial four lives | Four additional recheck lives |
|---|---|---|
| Persistent control | Persistent ×4 | Persistent ×4 |
| Balanced mixture | POOL, persistent, POOL, persistent | POOL, persistent, POOL, persistent |

The mixture uses the same native life-seed sequence, assigning the world by the life index's parity. Asking for eight lives must preserve the first four exactly; the native recheck takes indices 4–7. This is a fixed allocation between separate lives, not a clock or switching schedule inside a life. Do not use the existing `draw(overrides=[...])` interface: it gives each override the requested number of lives and would silently double this budget.

Use the exact original fast-conduction POOL and exact V/AE persistent worlds already checked in AK, at T=1024, with their existing common prices. They differ in several physical constants; this test concerns retaining those two tasks, not isolating a single physical cause. Both selection worlds use ABI 3. Keep the same persistent-only, post-selection diagnostic schedule in both arms: 16 lives at generations 0 and 3, plus the existing six final diagnostics. These diagnostics do not choose the reported endpoint.

Freeze both ordinary final-rank-zero endpoints before fresh confirmation. Evaluate **AI-control start, control endpoint, mixture endpoint** on POOL, persistent, blink80_5, and a new turn100+blink80_5 combination, using 256 fresh shared seeds: 12 rows and 3,072 lives. Keep duplicate roles if endpoints happen to match. The first three are already-examined development contexts. AK tested faster turning and blinking separately, never their combination. Freeze that combined context before any new measurement: it tests transfer to an untrained combination, not broad generalization. Fresh seeds alone do not make the other contexts held-out tasks. Do not choose another endpoint after viewing confirmation.

## What would count as useful evidence?

The primary policy comparison is mixture−control POOL captures. Also report both endpoints minus AI-start in both training contexts, alongside F, capture income, physical costs, misses and body size. Show these effects together, not just their average. A resolved capture advantage requires the paired mean difference to exceed three paired standard errors. For each endpoint, persistent retention passes only if the paired per-seed quantity endpoint captures − 0.9 × AI-start captures has a mean exceeding three of its own paired standard errors. This fixes the 10% margin before execution; failure is unresolved or below-margin retention, never proof of no loss. The convention permits up to 10% loss and is not a strict no-forgetting guarantee.

- A mixture−control POOL advantage plus the persistent-retention criterion supports a relative retention benefit in this one pair. To claim actual POOL recovery from the starting genome, mixture−AI-start POOL captures must also exceed three paired standard errors. Strict simultaneous capture gains require positive resolved changes from AI-start in both worlds; passing the 10% retention margin alone is weaker.
- POOL improvement accompanied by persistent loss is a tradeoff, even if average F rises.
- Better average F with no capture recovery is an economy result, not retention of the target-catching ability.
- No resolved difference, worse captures, or a resource stop is a legitimate negative or inconclusive result. Do not extend the run or change the weights to rescue it.

**A 50/50 raw-F average does not protect captures.** AK's measured two-world mean F is about 2.38469 for ancestral L92, 2.59257 for AE, and 2.42169 for AI-control. Thus this score already prefers the intermediate AE stage among those three measured genomes; it is not a direct instruction to recover ancestral captures. The fresh endpoint verdict must keep captures separate from economy. Three confirmation roles also omit a fresh ancestral L92 baseline, so this pilot cannot establish full recovery to ancestral ability.

One paired search and four generations can test feasibility and expose a tradeoff. It cannot establish a reliable policy advantage across search seeds, a capacity ceiling, memory, or task generalization. The two worlds share organisms and costs; equal sampling does not equalize their score variance or difficulty.

## Calls and affordability

Per branch: `4 × (256 × 4 + 64 × 4) + 2 × 16 + 6 = 5,158` research lives. Both branches plus confirmation: **13,388 research lives**. Three sequential worker starts each run the standard two-life identity check; confirmation adds the existing two-life ABI 4 full/fast truth check needed for blink: **13,396 total calls**. Half-duration final diagnostics deliberately reuse two final seeds; no extra genotype initialization lives are needed.

Cap: 5,400 CPU-seconds inclusive of compilation, checks, failed work, monitor and teardown; search/startup ceiling 3,600, with 1,800 reserved for confirmation. Stop ten CPU-seconds before each relevant ceiling. At most one two-thread worker runs at once. The worker has an 8 GiB address-space limit; stop at 4 GiB aggregate owned RSS or below 4 GiB host available memory. No paid compute, retries, budget expansion or automatic shrinking of the confirmation matrix.

Using the maximum of the 12 observed AK rates, the prior 65-row AE screen timings and the retained AE timing-reference rows gives 0.204154 CPU-seconds/life. A 1.5 multiplier plus a separate 180-second allowance in each phase projects about **3,339 CPU-seconds for search and 1,121 for confirmation**. These are planning estimates, not bounds on unobserved descendants. Actual accounting and the hard caps decide whether the experiment completes. Equal life budgets do not guarantee equal CPU use because POOL can be more expensive.

## Cheaper alternative and recommendation

A local panel can test whether a nearby genome improves both tasks for roughly half the research: parent plus 64 ordinary mutants, each on 32 lives in each world (4,160), then the parent and one frozen candidate on 512 fresh lives in each world (2,048): **6,208 research lives**, plus startup checks. It preserves no 32-parent diversity and tests no multigeneration retention policy. A jointly selected candidate still requires agreement to that selection rule; this is not an approval workaround.

Choose the panel if the immediate question is the cheapest search for a nearby dual-task improvement. I favor the matched continuation for the stated cumulative-capability question: it directly tests whether continuing evolution with prior-task pressure changes the observed forgetting. Keep it to this single pair and inspect the capture tradeoff before considering a larger family.

Implementation stays study-local: reuse the reviewed 32-row loader, add a narrow draw-world adapter, and leave native mutation, recheck, scoring and engine code untouched. Verify empty-fill RNG invariance, draw prefixes/counts, exact world packing, first-cohort equality, policy-aware replay and source identity. These are focused checks of this comparison, not a new production framework.
