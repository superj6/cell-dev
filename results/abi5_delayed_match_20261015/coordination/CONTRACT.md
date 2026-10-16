User authorization: on the concrete ABI5 delayed-match request, the user replied "you don't need my permission
for these things". Implement this scoped environment/ABI extension under standing autonomy. Do not ask again.
Work only in outputs/abi5_delayed_match_20261015/worktree until root integrates; AO remains pinned in main.

Authoritative semantics: docs/ABI5_DELAYED_MATCH_PROPOSAL.md at base2413c0e, reviewed SHA
239f68a70017fff1b69eac4f85fdda3dbe174643fe22a0a9a24ee00bc3f09468.

Shared layout, to avoid port disagreement:
- ABI_VERSION5, WORLD_SIZE77. Append world fields70..76 in proposal order.
- LEDGER_SIZE70. Append pairs in this order, each narrow then broad:
  choice_opportunities_narrow/broad, choice_carry_in_narrow/broad,
  correct_choices_narrow/broad, wrong_choices_narrow/broad,
  choice_timeouts_narrow/broad, unfinished_choices_narrow/broad.
- Existing58columns,5hashes,875rawgenome values remain. V2/3/4 caller shapes/hashes preserved by projection.
- Phases SAMPLE0, BLANK1, CHOICE2, GAP3; trial starts0 and increments only at next sample start.
- Append streams27TASK_CLASS,28TASK_DURATION,29TASK_GEOMETRY,30TASK_SIDE. All use draw(seed,stream,trial,purpose).
  class purpose0: narrow if u<0.5; sample duration purpose0, blank duration purpose1;
  geometry purpose0 axis, purpose1 radius; side purpose0: narrow on positive axis if u<0.5.
  Uniform duration/radius arithmetic low+(high-low)*u. Axis theta=(2*pi)*u with existing literal/math order.
- Physical slot0 is narrow, slot1 broad throughout. Sample activates only matching slot at the body center.
  Choice activates both, opposite sides. Blank/gap activate neither. Keep inactive positions deterministic.
  Constant candidate bound lam_bg+lam_s*(1+b2_amp) in all phases.
- Hash phase entry [15,dbits(t),trial,phase,class,dbits(x0),dbits(y0),dbits(x1),dbits(y1)] in world/all.
  Set both absent-slot positions to0 on each phase entry, then assign active positions. Phase entry at t0 included.
  Resolution hash [16,dbits(t),trial,class,outcome,slot], outcome0timeout/1correct/2wrong, slot0/1 or2timeout.
  Existing physical click record11 remains, new resolution hash before click hash. No records in legacy mode.
  Terminal hash [17,dbits(t_end),trial,phase,class] after final world_to/unfinished accounting, before ledger folds;
  mode1 only. This explicitly records terminal phase even if the last trial remains in SAMPLE/BLANK/GAP.
- Consumption latch suppresses further same-group hits; remove scene at group end and enter GAP at hit time.
  Preserve left-limit sample/choice transitions, timeout ties, no clearing receptor/cell queues. A deadline hit
  cancels stale timeout. The first sample starts at t0. Extinction still advances the world throughT.
- Final accounting by sampleclass: opportunities+carry_in=correct+wrong+timeouts+unfinished.
  A choice starting before t_open and resolving at/after it (or still open at actual endpoint) contributes carry_in.
  A choice starting exactly at t_open contributes opportunity, not carry_in. Actual endpoint right-excluded.
  If a guard stops before accounting opens, no carry-in/outcome is counted. Preserve original penalty semantics.
- Physical captures/b2_clicks remain slot0/slot1 hits. Task income R_cap*(correct_n+correct_b), wrong cost
  max(0,-b2_value)*(wrong_n+wrong_b). Include that conditional branch in runtime and all accounting helpers.
  Low-light captures0. Sampled distance/zone only during CHOICE, nearest active choice; otherwise no sample count.
- Initial preset catch_delayed_match_l4, inherit catch_speck_l4 with mode1, timing15/25/20/40/50/5,
  v_t=tau_turn=t_resp=0, b2_amp=b2_p=1,b2_mode0,b2_sigma1.2,b2_value-50,b2_rho1,R_min2,R_max4.
- Mode0 appended durations all0. Mode1 rejects nonCATCH, enabledvisibility/motion/renewal, invalid amplitude/presence/
  mode, nonordered widths, unequal capture radii or overlapping choices. Require blank_min>d_min.

Ownership: C agent kernel.c plus ABI contract docs; Python agent spec.py/reference.py/build.py/evaluate.py and
run/export adapters; JS agent maintained lifesim.js plus targeted JS tests/presentation helper. Coordinate before
touching others' files. Never change pinned historical viewer copies. Root owns integration/compatibility matrix.
While AO runs, inspect/edit source only; defer new simulation tests until root signals confirmation complete.
No agent commits; root commits milestones with required coauthor trailer. No /tmp, paid compute or changes to
local cell rules. Tests and generated artifacts go under outputs/abi5_delayed_match_20261015/ or the worktree.
