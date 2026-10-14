# What the copied genes can affect

This proof applies to the archived, fixed G endpoints and the pinned ABI3 engine. It is a statement about
physical trajectories and task-fitness observables, not equality of private GRN state or diagnostic hashes.
The executable audit uses the original eight genomes preserved in `../superseded_4096/` in the public archive.
It performs packing and readout arithmetic only, with no kernel build or life simulation.

## G51089: disconnected copy implies zero physical and fitness effect

The active copied gene is slot 14, innovation origin 56. Its extant source is slot 5, origin 5. In both the
intact genome and source-knockout genome, all 16 packed entries in W[:,14] and all 23 in A[:,14] are exact
positive zero. Deleting the copy changes only its own incoming W row and its private b, lambda, initial state,
Q and active-mask entries. Every other packed parameter is byte-identical. This checks the actual packed
coefficients after inactive masking and rate decoding, rather than assuming raw zeros survive packing.

The kernel updates gene k from its own old value, its decoded rate, and W[k,:] applied to genes and local
inputs. Since every outgoing coefficient of gene 14 is zero, no other gene update depends on its value.
All phenotype readouts are affine sums A[p,:] times the gene vector plus a0[p]. Their entire copy column is
zero, so all readout values and all decoded physical knobs are unchanged by the copy state. This includes
continuous, quantized and binary knobs. Nonzero private bias or lambda can change the copy's state but cannot
create a missing outgoing channel.

An induction over asynchronous physical events then gives the result. Initially every physical state and
every non-copy gene state is equal. At a GRN update, equality of local inputs and the remaining genes preserves
their equality and the phenotype. Spike delivery, secretion, movement, resource accounting and structural
decisions consequently use identical physical state and knobs. At division, Q partitions each gene component
independently; changing the copy's private Q cannot change another component. Gene loops and keyed random
draws do not depend on active-gene count, and the task does not charge a direct active-gene-count cost.
Thus the next physical event and its accounting remain equal. The same argument applies with source slot 5
deleted, because the packed premises were independently checked in that background too.

For the same legal world, seed and existing physical interventions, this implies
`F(intact) = F(copyKO)` and `F(sourceKO) = F(doubleKO)`, hence the four-arm fitness interaction is exactly zero.
The proof covers the engine's physical and ledger semantics, including physical-event guards. Host execution
cost and an external CPU budget are outside the equivalence claim. Diagnostic recording may retain different private gene values.
No claim is made that full private state, diagnostic snapshots or event hashes are identical.

Relevant pinned source: `src/life/spec.py` packing/inactive masks, rate decoding and phenotype decoding;
`src/life/kernel.c` readout, set_theta, GRN update, division, fire and accounting;
`src/genome.py` duplicate/delete/pack. Source digests and exact outgoing columns appear in the adjacent receipt.

## G51090: no universal disconnection proof

The copied gene is slot 9, origin 21; the extant source is slot 0, origin 0. W[:,9] is zero, but A[6,9] is
exactly +0.17784759402275085. Readout 6 is emit1, decoded by the strict test y6 > 0. There is no quantization
interval that automatically erases this coefficient. The copy's packed initial state is 0.5260494315364311
and its decoded rate is 0.125; its bias and Q are also private, nonzero parameters.

Over the permitted componentwise gene cube [0,1]^16, emit1 readout bounds are:

| Background | With copy | Without copy |
| --- | --- | --- |
| Source present | [-0.6037581562995911, 5.506271511316299] | [-0.6037581562995911, 5.328423917293549] |
| Source deleted | [-0.3063688278198242, 5.506271511316299] | [-0.3063688278198242, 5.328423917293549] |

These bounds alone do not prove that either sign is reached during a real life. They also do not support a
universal fixed sign. A direct bounded-state counterexample is stronger: in the source-deleted background,
set every gene to zero except gene 4 = 0.7 and gene 9 = its packed initial value. The serial readout is
+0.05339564789536658 with the copy and -0.040160977840423495 without it. Only decoded emit1 changes, from 1 to 0.
All other 22 decoded knobs remain equal. Reachability of this state has not been established.

This disproves a universal decoder-invariance argument while making no positive claim about actual effect
size, conditional usefulness, an adult mechanism or expanded computation. Fresh whole-life measurement of
the four G51090 arms can still resolve whether deleting the source reveals a copy effect in the registered task.
