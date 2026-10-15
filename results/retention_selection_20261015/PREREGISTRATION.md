# AL: fixed two-context retention selection

The user authorized this local comparison and subsequent useful local experiments. The question is whether
rehearsing an ancestral task during selection can recover acquisition there without sacrificing the more recent
persistent-target gain. This is a first small selection-policy comparison, not a test of a new cell model.

Both branches import all 32 ordered AI ordinary-control survivors, including duplicate genomes, with fresh
selection scores and RNG state. The ordinary control uses only the exact persistent-target world. The mixture
allocates half its selection lives to exact ancestral POOL and half to persistent. There is no context label
available to cells. World dynamics do not respond to the population. Physical prices and native raw mean F
remain unchanged; no separate capture or retention bonus is introduced.

Each branch runs four native generations: 32 parents plus 224 offspring, four initial lives, top 64 rechecked
on four additional lives, and pooled F chooses the 32 survivors. The fixed mixture uses even draw indices for
POOL and odd indices for persistent in both stages. Genetics and tie-breaking initially share seed 53229;
the first 224 offspring must reconstruct bytewise identically before confirmation. Later populations may diverge.
Validation and final native reports stay persistent-only and do not choose the confirmation endpoint. Structural
mutation is off, matching the continuing lineage. The final population rank 0 genome is frozen in each branch.

AI start and both endpoints receive 256 fresh shared seeds per world in fixed order: POOL, persistent,
irregular blink80_5, and combined turn100+blink80_5. The first three contexts are development cases. The combined
case is excluded from selection and endpoint choice. Its result tests this one nearby transfer case, not broad
generalization. This chosen lineage and single paired search do not estimate general policy reliability.

The primary contrast is mixture minus control POOL captures. Actual partial recovery additionally requires
mixture minus AI start POOL captures above three paired standard errors. Persistent retention uses the lower
three-SE bound of endpoint minus 0.9×AI start captures. This conventional tolerance permits a 10% loss and is
diagnostic only; a statistically unresolved loss does not establish retention. Strict simultaneous improvement
requires positive lower three-SE bounds for own-start capture gains in both training worlds. All within-world
pairs, environment contrasts, interactions, fitness, capture income and physical costs are retained. No fresh
L92 reference is included, so full ancestral restoration is not tested. Economy alone is not richer computation.

The exact scope is 5158 research plus 2 existing startup lives per search and 3072 research plus 4 existing truth
lives for confirmation: 13388 research,8 startup,13396 total calls. Native unique life IDs are derived from 53229
and intentionally shared across arms. Confirmation uses 52390000–52390255 in reserved block 139 at base 51 M.
AJ 53228/block 137 remain held. Existing startup truth seeds 11/55040000 are explicit reuse.

One two-thread worker runs at a time. Caps are 5400 cumulative CPU-seconds, including 3600 for both searches and
1800 reserved for confirmation, and 3600 wall seconds overall. The worker has an 8 GiB address-space limit;
the watchdog stops on 4 GiB aggregate owned RSS or host available memory below 4 GiB. These limits include
compilation/startup and cleanup. There is no retry, resume, scope reduction, extension or paid compute.
Prior process clearance, deterministic source/input identities and exact prospective publication precede launch.
The reader independently reconstructs physical accounting from retained ledgers; full genetics/selection replay
follows the run. Native search retains aggregate guard/invalid fields, not all per-life ledgers, limiting its audit.
