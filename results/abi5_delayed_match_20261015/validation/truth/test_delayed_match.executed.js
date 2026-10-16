#!/usr/bin/env node
/* ABI-5 delayed-match boundary fixtures; --truth accepts bounded C/Python exporter output.
 * Direct world probes are execution fixtures, not behavior claims or seed selection.
 */
'use strict';
const assert = require('assert/strict');
const fs = require('fs');
const LifeSim = require('./lifesim.js');
const doc = require('./bodies.json');
let checks = 0, created = 0, completeRuns = 0;
const test = (name, fn) => { fn(); checks++; console.log(`pass: ${name}`); };
const clone = x => JSON.parse(JSON.stringify(x));
const dv = new DataView(new ArrayBuffer(8));
const bits = x => { dv.setFloat64(0, x, true); return dv.getBigUint64(0, true); };
const nextup = x => { const b = bits(x); dv.setBigUint64(0, b + 1n, true); return dv.getFloat64(0, true); };
const MASK = (1n << 64n) - 1n;
function sm(x) {
  let z = (x + 0x9e3779b97f4a7c15n) & MASK;
  z = ((z ^ (z >> 30n)) * 0xbf58476d1ce4e5b9n) & MASK;
  z = ((z ^ (z >> 27n)) * 0x94d049bb133111ebn) & MASK;
  return z ^ (z >> 31n);
}
function fold(h, words) { for (const word of words) h = sm(h ^ word); return h.toString(16).padStart(16, '0'); }
function draw(seed, stream, trial, purpose) {
  let h = sm(BigInt(seed) ^ sm(BigInt(stream)));
  h = sm(h ^ BigInt(trial)); h = sm(h ^ BigInt(purpose));
  return Number((h >> 11n) | 1n) * 2 ** -53;
}
const taskWorld = { T: 96, t_open: 0, task_mode: 1, sample_min: 15, sample_max: 25, blank_min: 20,
  blank_max: 40, choice_T: 50, reset_T: 5, visibility_mode: 0, visibility_on: 0, visibility_off: 0,
  visibility_low: 1, v_t: 0, tau_turn: 0, t_resp: 0, b2_amp: 1, b2_p: 1, b2_mode: 0,
  sigma: 0.6, b2_sigma: 1.2, b2_value: -50, rho_c: 1, b2_rho: 1, R_min: 2, R_max: 4 };
const fixed = { sample_min: 2, sample_max: 2, blank_min: 3, blank_max: 3, choice_T: 5, reset_T: 1 };
function body(world = {}, abi = 5) {
  const b = clone(doc.bodies[7]); b.abi = abi;
  Object.assign(b.world, taskWorld, world); return b;
}
function make(world = {}, opts = {}) {
  created++; return LifeSim.create(body(world), { seed: 55050000, hashes: true, ...opts });
}
function run(sim) { sim.run(); completeRuns++; return sim; }
function atChoice(world = {}, opts = {}) {
  const sim = make({ ...fixed, ...world }, opts); sim.life.worldTo(nextup(5 + sim.life.t0)); return sim;
}
function onSlot(life, slot, t) { life.X = life.blobs[slot].x; life.Y = life.blobs[slot].y; life.t_x = t; life.Fx = life.Fy = 0; }
function conservation(ledger) {
  for (const cls of ['narrow', 'broad']) assert.equal(
    ledger['choice_opportunities_' + cls] + ledger['choice_carry_in_' + cls],
    ledger['correct_choices_' + cls] + ledger['wrong_choices_' + cls] +
      ledger['choice_timeouts_' + cls] + ledger['unfinished_choices_' + cls], cls);
}

test('ABI 5 appends twelve columns; explicit older modes and default stay unchanged', () => {
  assert.equal(LifeSim.LEDGER_V5.length, 70);
  assert.deepEqual(LifeSim.LEDGER_V5.slice(0, 58), LifeSim.LEDGER_V4);
  created++;
  assert.throws(() => LifeSim.create(body({}, 4)), /ABI 5/);
  assert.equal(LifeSim.create(doc.bodies[7]).life.abi, 3); created++;
  assert.equal(make().life.abi, 5);
});

test('invalid timing and incompatible second-blob worlds fail explicitly', () => {
  for (const world of [
    { task_mode: -1 }, { task_mode: 2 }, { task_mode: 0 }, { task_mode: NaN },
    { sample_min: 0 }, { sample_min: 26 }, { sample_max: Infinity }, { blank_min: 0.125 },
    { blank_max: 19 }, { choice_T: 2 ** -11 }, { reset_T: 2 ** 30 + 1 },
    { v_t: 0.1 }, { tau_turn: 1 }, { t_resp: 1 }, { b2_amp: 0 }, { b2_p: 0.5 }, { b2_mode: 1 },
    { b2_sigma: 0.6 }, { b2_rho: 2 }, { R_min: 1 }, { R_max: 1 }, { b2_value: NaN }, { b2_value: 0 },
    { world_kind: 0 }, { visibility_mode: 1, visibility_on: 5 },
  ]) assert.throws(() => make(world), /task|delayed|visibility/);
  assert.throws(() => make({ task_mode: 0, sample_min: 0, sample_max: 0, blank_min: 0, blank_max: 0,
    choice_T: 0, reset_T: 0 }), /second blob/);
});

test('interactive edits reject before mutating the delayed-match world', () => {
  for (const opts of [{ mode: 'user' }, { targets: [] }, { drift: true }]) assert.throws(() => make({}, opts), /automatic/);
  const sim = make(), before = sim.hashes();
  for (const edit of [() => sim.setMode('user'), () => sim.addTarget(1, 1), () => sim.moveTarget(0, 1, 1),
    () => sim.removeTarget(0), () => sim.setDrift(true)]) assert.throws(edit, /automatic|interactive/);
  assert.deepEqual(sim.hashes(), before); assert.equal(sim.life.mode, 'auto');
  sim.setMode('auto');
});

test('dedicated trial streams determine class, durations, geometry and side', () => {
  for (let seed = 55050000; seed < 55050004; seed++) {
    const sim = make({}, { seed }), life = sim.life;
    const cls = draw(seed, 27, 0, 0) < 0.5 ? 0 : 1;
    const sampleEnd = 15 + 10 * draw(seed, 28, 0, 0), choiceStart = sampleEnd + (20 + 20 * draw(seed, 28, 0, 1));
    assert.equal(life.task_class, cls); assert.equal(bits(life.task_next), bits(sampleEnd));
    assert.equal(life.blobs[cls].present, true); assert.equal(life.blobs[1 - cls].present, false);
    life.worldTo(nextup(choiceStart));
    assert.equal(life.task_phase, 2); assert.equal(bits(life.task_choice_start), bits(choiceStart));
    const theta = (2 * Math.PI) * draw(seed, 29, 0, 0), radius = 2 + 2 * draw(seed, 29, 0, 1);
    const dx = radius * LifeSim.libm.cos(theta), dy = radius * LifeSim.libm.sin(theta);
    const pos = draw(seed, 30, 0, 0) < 0.5;
    assert.equal(bits(life.blobs[pos ? 0 : 1].x), bits(dx));
    assert.equal(bits(life.blobs[pos ? 0 : 1].y), bits(dy));
    assert.equal(bits(life.blobs[pos ? 1 : 0].x), bits(-dx));
  }
});

test('every phase is left-continuous at its deadline and hashes exact phase records', () => {
  const sim = make({ ...fixed, t0: 32 }), life = sim.life;
  for (const [deadline, beforePhase, afterPhase] of [[34, 0, 1], [37, 1, 2], [42, 2, 3], [43, 3, 0]]) {
    life.worldTo(deadline); assert.equal(life.task_phase, beforePhase);
    const before = sim.hashes(), trial = life.task_trial, cls = life.task_class;
    life.worldTo(nextup(deadline)); assert.equal(life.task_phase, afterPhase);
    let words = beforePhase === 2 ? [16n, bits(deadline), BigInt(trial), BigInt(cls), 0n, 2n] : [];
    words = words.concat([15n, bits(deadline), BigInt(life.task_trial), BigInt(afterPhase), BigInt(life.task_class),
      ...life.blobs.flatMap(bl => [bits(bl.x), bits(bl.y)])]);
    assert.equal(sim.hashes().world, fold(BigInt('0x' + before.world), words));
    assert.equal(sim.hashes().all, fold(BigInt('0x' + before.all), words));
  }
  assert.equal(life.task_trial, 1);
});

test('sample and blank misses cannot resolve a choice; candidate bound never changes', () => {
  const sim = make(fixed), life = sim.life, bound = life.lam_max;
  assert.equal(bound, life.lam_bg + life.lam_s * 2);
  for (const t of [1, 3, 6, 10.5, 11.5]) {
    life.worldTo(t);
    const target = life.blobs.find(bl => bl.present);
    for (const [x, y] of [[0, 0], target ? [target.x, target.y] : [10, 10]]) assert.ok(life.rate(x, y, t) <= bound);
    assert.equal(life.lam_max, bound);
    if (life.task_phase === 1 || life.task_phase === 3) assert.equal(life.rate(0, 0, t), life.lam_bg);
    if (t < 5) { life.click(t, true); assert.equal(life.task_consumed, false); }
  }
  assert.equal(sim.ledger().misses, 2);
});

test('both sample classes pay correctness independently of physical slot; same-group hits consume once', () => {
  for (const cls of [0, 1]) for (const slot of [0, 1]) {
    const sim = atChoice(), life = sim.life; life.task_class = cls; // synthetic boundary fixture, no seed search
    onSlot(life, slot, 6);
    const before = sim.hashes(); life.click(6, true);
    const correct = cls === slot, led = sim.ledger();
    assert.equal(led.captures, slot === 0 ? 1 : 0); assert.equal(led.b2_clicks, slot === 1 ? 1 : 0);
    assert.equal(led['correct_choices_' + (cls ? 'broad' : 'narrow')], correct ? 1 : 0);
    assert.equal(led['wrong_choices_' + (cls ? 'broad' : 'narrow')], correct ? 0 : 1);
    assert.equal(led.income, correct ? life.R_cap : 0); assert.equal(led.cost, correct ? 0 : 50);
    const words = [16n, bits(6), 0n, BigInt(cls), correct ? 1n : 2n, BigInt(slot),
      11n, bits(6), BigInt(slot + 1), bits(life.X), bits(life.Y)];
    assert.equal(sim.hashes().world, fold(BigInt('0x' + before.world), words));
    assert.equal(life.task_next, Infinity);
    assert.ok(life.blobs.every(bl => bl.present));
    const rate = life.rate(life.X, life.Y, 6);
    life.click(6, true); assert.equal(sim.ledger().misses, 1);
    assert.equal(life.rate(life.X, life.Y, 6), rate, 'same-group receptor sees old scene');
    life.group(6, []); assert.equal(life.task_phase, 3); assert.equal(life.task_next, 7);
    assert.ok(life.blobs.every(bl => !bl.present && Object.is(bl.x, 0) && Object.is(bl.y, 0)));
  }
});

test('a deadline click wins the timeout tie and cancels the obsolete timeout', () => {
  const sim = atChoice(), life = sim.life;
  life.worldTo(10); onSlot(life, life.task_class, 10); life.click(10, true); life.group(10, []);
  life.worldTo(nextup(10));
  assert.equal(life.task_phase, 3); assert.equal(life.task_next, 11);
  assert.equal(sim.ledger().choice_timeouts_narrow + sim.ledger().choice_timeouts_broad, 0);
  conservation(sim.ledger());
});

test('choice-only samples use the nearest active slot and both capture zones', () => {
  const sim = make(fixed), life = sim.life;
  life.sample(1); life.sample(3); assert.equal(sim.ledger().samples, 0);
  life.worldTo(6); onSlot(life, 1, 6); life.sample(6);
  assert.equal(sim.ledger().samples, 1); assert.equal(sim.ledger().dist_sum, 0);
  assert.equal(sim.ledger().zone_samples, 1); assert.equal(sim.ledger().low_light_captures, 0);
  life.worldTo(10.5); life.sample(10.5); assert.equal(sim.ledger().samples, 1);
});

test('carry-in includes outcomes at t_open and open opportunities at actual life end', () => {
  for (const [open, end, resolution] of [[6, 9, 'correct'], [6, 9, 'unfinished'], [6, 11, 'timeout'],
    [5, 9, 'unfinished'], [10, 11, 'timeout'], [10, 10, 'unfinished'], [12, 9, 'unfinished']]) {
    const sim = atChoice({ t_open: open, T: end }), life = sim.life;
    if (resolution === 'correct') { onSlot(life, life.task_class, open); life.click(open, true); life.group(open, []); }
    life.close(end, 0);
    conservation(sim.ledger());
    const led = sim.ledger(), carry = led.choice_carry_in_narrow + led.choice_carry_in_broad;
    assert.equal(carry, open > 5 && end > open ? 1 : 0);
  }
});

test('life end excludes phase deadlines; terminal record commits the remaining phase', () => {
  const sim = make({ ...fixed, T: 2 }), life = sim.life, before = sim.hashes();
  life.close(2, 0);
  assert.equal(life.task_phase, 0);
  assert.equal(sim.hashes().world, fold(BigInt('0x' + before.world), [17n, bits(2), 0n, 0n, BigInt(life.task_class)]));
  assert.equal(life.evlog.filter(e => e.kind === 'task_phase').length, 1);
});

test('window guards and extinction preserve conservation and ordinary charge semantics', () => {
  const guarded = run(make({ ...fixed, T: 20, t_open: 8 }, { e_max: 0 }));
  assert.ok(guarded.life.t_end <= 8); conservation(guarded.ledger());
  assert.equal(guarded.ledger().choice_carry_in_narrow + guarded.ledger().choice_carry_in_broad, 0);
  const extinct = run(make({ ...fixed, T: 30, kill_t: 0, kill_frac: 1 }));
  assert.equal(extinct.ledger().n_end, 0); assert.equal(extinct.life.t_end, 30);
  assert.ok(extinct.ledger().choice_timeouts_narrow + extinct.ledger().choice_timeouts_broad >= 2);
  conservation(extinct.ledger());
});

test('ABI 5 neutral mode preserves ABI 4 records and adds only twelve zero close folds', () => {
  const neutral = clone(doc.bodies[7]); neutral.world.T = 16;
  const old = LifeSim.create({ ...neutral, abi: 4 }, { seed: 55050000, hashes: true });
  const modern = LifeSim.create({ ...neutral, abi: 5 }, { seed: 55050000, hashes: true }); created += 2;
  run(old); run(modern);
  assert.deepEqual(Array.from(modern.life.led.slice(0, 58)).map(bits), Array.from(old.life.led).map(bits));
  assert.ok(Array.from(modern.life.led.slice(58)).every(x => x === 0));
  for (const family of ['spikes', 'fate', 'chem', 'world']) assert.equal(modern.hashes()[family], old.hashes()[family]);
  assert.equal(modern.hashes().all, fold(BigInt('0x' + old.hashes().all), Array(12).fill(0n)));
});

test('frame-time phases and capped stepping retain complete-life parity', () => {
  const frame = make({ ...fixed, T: 20 }); frame.advance(2.1); assert.equal(frame.state().task.phase, 'blank');
  const full = run(make({ ...fixed, T: 20 })), stepped = make({ ...fixed, T: 20 });
  while (!stepped.ended) { stepped.advance(0.37, 40); stepped.state(); } completeRuns++;
  assert.deepEqual(stepped.hashes(), full.hashes());
  assert.deepEqual(Array.from(stepped.life.led).map(bits), Array.from(full.life.led).map(bits));
  conservation(full.ledger());
  const state = full.state(); assert.ok(state.task.phase); assert.ok(state.score.slot_hits);
  const displayed = require('./delayed_match_view.js').summary(state, full.ledger());
  assert.equal(displayed.phase, state.task.phase);
  for (const row of displayed.rows) {
    assert.equal(row.narrow + row.broad, row.resolved);
    assert.equal(row.opened, row.resolved + row.timeout + row.unfinished);
  }
});

const arg = process.argv.indexOf('--truth');
if (arg >= 0) {
  if (!process.argv[arg + 1]) throw new Error('--truth requires a fixture file');
  const truth = JSON.parse(fs.readFileSync(process.argv[arg + 1], 'utf8'));
  assert.equal(truth.status, 'complete');
  for (const item of truth.cases) test('C/Python/JS truth: ' + item.name, () => {
    const sim = LifeSim.create(item.body, { seed: item.seed, hashes: true, raster: truth.raster_cap }); created++;
    run(sim);
    assert.deepEqual(Array.from(sim.life.led).map(bits), item.ledger.map(x => bits(Number(x))), 'all ledger bytes');
    assert.deepEqual(Object.values(sim.hashes()), item.hashes, 'all five hashes');
    const raster = sim.raster(); assert.equal(raster.n, item.raster_total);
    assert.deepEqual(raster.t.map(bits), item.raster_t.map(x => bits(Number(x))));
    assert.deepEqual(raster.uid, item.raster_uid);
    const stepped = LifeSim.create(item.body, { seed: item.seed, hashes: true, raster: truth.raster_cap }); created++;
    while (!stepped.ended) { stepped.advance(0.37, 40); stepped.state(); } completeRuns++;
    assert.deepEqual(stepped.hashes(), sim.hashes(), 'capped stepping invariance');
    if (sim.life.task_mode) conservation(sim.ledger());
  });
}
console.log(`${checks} delayed-match checks passed; ${created} construction attempts, ${completeRuns} complete runs`);
