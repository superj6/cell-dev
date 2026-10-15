## 2026-10-14 — AH complete: a temporary offspring reserve improves the endpoint relative to matched ordinary selection

**Question.** In the persistent-target world, does briefly keeping two randomly chosen new offspring help search
retain useful alternatives? This was one deliberately chosen AE L92 starting genome and one matched pair of
four-generation searches. Generations 0–2 protected two uniformly sampled fresh offspring through recheck and
breeder selection; generation 3 used ordinary selection in both arms. Task fitness, prices, world, mutation,
crossover and local asynchronous organism rules stayed fixed. No behavior was prescribed.

**Fresh confirmation, 512 paired lives; mean ± paired SE:**

| Fixed contrast | Captures per life | Fitness F | Capture-income contribution to F | Ordinary cost saving in F |
|---|---:|---:|---:|---:|
| Reserve − control (primary) | **+0.556641 ± 0.110184** | **+0.254917 ± 0.054269** | +0.271797 ± 0.053801 | −0.016880 ± 0.007637 |
| Control − start | −0.218750 ± 0.115289 | +1.094887 ± 0.057418 | −0.106812 ± 0.056293 | +1.201699 ± 0.011916 |
| Reserve − start | +0.337891 ± 0.115967 | +1.349804 ± 0.057343 | +0.164986 ± 0.056625 | +1.184818 ± 0.012074 |

Reserve beats control by the fixed three-SE criterion for both captures and F. Extra capture income explains
the relative advantage; mean ordinary costs are slightly higher, with their difference unresolved at three SE.
Reserve's capture gain over the starting genome narrowly misses that criterion (3 SE = 0.347902); control's
capture change is also unresolved. Both large fitness gains over the start come mainly from ordinary cost savings.
No guard or extinction difference contributes to these contrasts.

Mean captures are **3.525391 → 3.306641 / 3.863281** for start → control / reserve; mean F is
**−0.979188 → +0.115699 / +0.370616**. Mean terminal cells shrink **108.908203 → 60.976563 / 60.035156**.
Reserve fires **192.001953 ± 15.684410** more spikes per life than control while ending with
**0.941406 ± 0.281649** fewer cells. These are descriptive organism differences, not identified computation.

**What the experiment establishes.** The fixed reserve endpoint performs better than the fixed control endpoint
on fresh lives. The 512-life uncertainty concerns those endpoints; a single evolutionary pair does not establish
that the policy works reliably across search seeds. It also does not show a necessary low-fitness stepping stone,
memory, prediction or a new algorithm. A second independent matched pair with the unchanged policy is the most
direct next experiment. A longer ordinary continuation after early body contraction remains a separate candidate.

**Integrity and resources.** The shared initial population and all first 256 candidate genomes match bytewise,
as do their first base-fitness values. Independent recorded-operation replay reproduces both complete final
populations: 896 sexual offspring and 1,854 point additions including initialization per arm, no structural
mutation, eight active genes throughout. All 24 ranking calls and the six protected IDs reproduce exactly.
All six protected offspring lay outside both the ordinary initial top64 and their treatment shortlist's ordinary
pooled top32. This describes actual retention, not the unobserved full ordinary counterfactual for later treatment
cohorts. The final generation contains no protected slots.

All **9,804 research plus six golden calls** complete in **862.767205 CPU-seconds** and **257.302628 wall seconds**.
Search consumes 720.896357 CPU-seconds; confirmation and cleanup consume 141.870848. The hard caps remain
5,400 total, 3,400 search and 2,000 confirmation reserve. All 1,536 retained confirmation ledgers have zero status.
Initial-search logs retain **12 control / 18 reserve guarded lives** with penalties; complete per-life native search
ledgers are not retained, so there is no all-search-health claim. All four process leaders and three owned groups
have exited; **208 released local / 35 production pins** are unchanged. No retry, resume, extension or paid compute.

The unchanged frozen reader, separate literal-ledger accountant and complete genetic/policy reanalysis agree on
all **219 paired vectors**. Raw accounting uses every confirmation life and includes all costs and penalties.
Numerical identities cover the six goldens and bind the external selection adapter in addition to production code.

**Post hoc lineage check.** The reserve winner has no genealogical descent from any of the six protected
children. Protected ID329 has descendants in three of the final 32 population members; the other five have none.
The changed selection can still redirect later breeding by displacing or reordering parents. These observations
rule out a protected-ancestor explanation for this particular winner, but do not identify which policy consequence
caused its behavioral advantage. They do not establish necessary stepping stones or retained functional alleles.

**Artifacts.** `results/exploratory_reserve_20261014/` preserves prospective preparation, raw confirmation,
both native populations and logs, exact readers, independent checks, terminal resource evidence and the four-panel
figure. Fixed endpoint IDs are control **870**, reserve **895**; raw genome hashes begin `4bf7a2b2…` / `3cc5a0db…`.
Protocol `0a9e5059…4c61be4`; budget `24dadeb2…8a76ce6`; summary `fc097ab9…132aa26`.
The prospective protocol was published at `e7246f2` before release. Historical failed source-test outputs remain
preserved alongside passing final reviews; none is rewritten as a success.
