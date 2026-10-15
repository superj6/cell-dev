## 2026-10-15 — AI complete: the reserve advantage reverses; ordinary selection improves captures

The unchanged exploratory-reserve comparison was repeated with an independent search seed from the same
deliberately chosen AE L92 founder. Both four-generation searches shared their initialization and life schedule;
the final endpoints were fixed before confirmation. The world, task fitness, prices, genetic operators and local
asynchronous organism rules stayed fixed.

**Fresh confirmation, 512 paired lives; mean ± paired SE:**

| Fixed contrast | Captures per life | Fitness F | Capture-income contribution to F | Ordinary cost saving in F |
|---|---:|---:|---:|---:|
| Reserve − control (primary) | **−0.513672 ± 0.119015** | **−0.274444 ± 0.057401** | −0.250816 ± 0.058113 | −0.023628 ± 0.007421 |
| Control − start | **+0.695313 ± 0.127998** | +1.477951 ± 0.063427 | +0.339508 ± 0.062499 | +1.138443 ± 0.012923 |
| Reserve − start | +0.181641 ± 0.126883 | +1.203507 ± 0.063512 | +0.088692 ± 0.061955 | +1.114815 ± 0.012963 |

Reserve loses to control in both captures and F by the fixed three-SE criterion. Its lower capture income and
slightly higher ordinary costs both contribute. This reverses AH's relative advantage (+0.556641 ± 0.110184
captures): the two independent search pairs give **no consistent reserve-policy advantage**. They share one
chosen starting genome; evaluation lives are not independent evolutionary repetitions, and two pairs cannot
establish broad policy reliability. No pooled life-level policy test is reported.

Ordinary control improves captures over its own start beyond three SE. Mean captures rise
**4.027344 → 4.722656**, while reserve reaches **4.208984**. Mean F changes **−0.750661 → +0.727290 / +0.452846**
for start → control / reserve. Both fitness gains still come mainly from economy. Mean terminal cells shrink
**108.775391 → 64.400391 / 63.857422**, and mean spikes fall **2512.343750 → 972.757813 / 1074.375000**.
These measurements establish a modest ordinary capture improvement, without identifying prediction, memory
or a richer algorithm. A longer ordinary continuation is the next design candidate; no new run is released here.

**Integrity and resources.** Both shared initial populations and their first 256 candidate genomes/base fitness
match exactly. Recorded-operation replay reconstructs all 896 sexual offspring and 1,854 point additions per
arm, including initialization, plus all 24 ranking calls and both final populations. There is no structural mutation;
eight genes remain active. Five of the six protected children were outside their ordinary initial top64;
ID656 was already inside. All six were outside their treatment shortlist's ordinary pooled top32. This describes
actual retention, not a full counterfactual ordinary search or a necessary stepping stone. No AI ancestry claim
is made.

All **9,804 research plus six golden calls** complete in **1,068.361098 CPU-seconds** and **305.364878 wall seconds**.
Search uses 923.782077 CPU-seconds; confirmation and cleanup use 144.579021, within unchanged caps of 5,400
total and 3,400 search, with 2,000 reserved for confirmation. All 1,536 confirmation ledgers have zero status and
no guard/extinction contribution. Native initial-search logs retain **three guarded lives in each arm**, with
penalties; full per-life native ledgers are not retained. Four process leaders and three groups have exited;
**210 local / 35 production release pins** are unchanged. There was no retry, resume, extension or paid compute.

The frozen reader, independent literal-ledger accountant and full genetic/policy replay agree on all
**219 paired vectors**; independently regenerated summary and vector archive bytes match exactly. Numerical
identity checks include all six goldens and the external selection adapter. Prospective publication was commit
`cae942b`; original preparation and failed administrative/source-check attempts remain preserved.

**Artifacts.** `results/exploratory_reserve_replication_20261014/` contains the complete prospective and terminal
record, raw confirmation, populations, readers, independent checks, resource receipts and a four-panel figure.
Fixed endpoint IDs are control **668**, reserve **887**; raw genotype hashes begin `657326d5…` / `7944ce86…`.
Protocol `0dc38519…b6dff00`; budget `e8e7f316…4e098d`; summary `a070f5b9…c3f2f9`.
