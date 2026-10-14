#!/usr/bin/env node
/* ABI-4 visibility boundaries; optionally compare complete C/Python truth from export_visibility.py. */
'use strict';
const assert = require('assert/strict');
const fs = require('fs');
const path = require('path');
const LifeSim = require('./lifesim.js');
const doc = require('./bodies.json');
let checks = 0;
const test = (name, fn) => { fn(); checks++; console.log(`pass: ${name}`); };
const clone = x => JSON.parse(JSON.stringify(x));
const buffer = new ArrayBuffer(8), dv = new DataView(buffer);
const bits = x => { dv.setFloat64(0, x, true); return dv.getBigUint64(0, true); };
const nextup = x => { const b = bits(x); dv.setBigUint64(0, b + 1n, true); return dv.getFloat64(0, true); };
const body = (world = {}, abi = 4) => {
  const b = clone(doc.bodies[7]);
  b.abi = abi;
  Object.assign(b.world, { T: 96, visibility_mode: 1, visibility_on: 5, visibility_off: 0, visibility_low: 0.25 }, world);
  return b;
};
const make = (world = {}, opts = {}) => LifeSim.create(body(world), { seed: 55040000, hashes: true, ...opts });
const neutral = { visibility_mode: 0, visibility_on: 0, visibility_off: 0, visibility_low: 1 };
const renewal = { visibility_mode: 2, visibility_on: 20, visibility_off: 20, visibility_low: 0 };
const MASK = (1n << 64n) - 1n;
function sm(x) { // Independent integer form of the specified SplitMix fold.
  let z = (x + 0x9e3779b97f4a7c15n) & MASK;
  z = ((z ^ (z >> 30n)) * 0xbf58476d1ce4e5b9n) & MASK;
  z = ((z ^ (z >> 27n)) * 0x94d049bb133111ebn) & MASK;
  return z ^ (z >> 31n);
}
function fold(h, words) { for (const w of words) h = sm(h ^ w); return h.toString(16).padStart(16, '0'); }
function hash(seed, stream, ...keys) {
  let h = sm(BigInt(seed) ^ sm(BigInt(stream)));
  for (const k of keys) h = sm(h ^ BigInt(k));
  return h;
}
function visibilityNext(seed, k, previous, mean) {
  const u = Number((hash(seed, 26, 0, k) >> 11n) | 1n) * 2 ** -53;
  return previous - mean * LifeSim.libm.log(u);
}

test('ABI 3 remains the default with 57 columns; explicit ABI 4 adds exactly one', () => {
  const legacy = LifeSim.create(doc.bodies[7], { seed: 55040000 });
  const modern = make(neutral);
  assert.equal(legacy.life.abi, 3);
  assert.equal(Object.keys(legacy.ledger()).length, 57);
  assert.equal(Object.keys(modern.ledger()).length, 58);
  assert.deepEqual(LifeSim.LEDGER_V4.slice(0, 57), LifeSim.LEDGER);
  assert.equal(LifeSim.LEDGER_V4[57], 'low_light_captures');
  assert.equal(LifeSim.create({ abi: 4, bodies: [body()] }).life.abi, 4);
  assert.throws(() => LifeSim.create(body(), { abi: 3 }), /requires ABI 4/);
});

test('visibility validation rejects malformed and unsupported worlds', () => {
  for (const w of [
    { visibility_mode: -1 }, { visibility_mode: 3 }, { visibility_mode: 1.5 }, { visibility_mode: NaN },
    { visibility_on: 0 }, { visibility_on: 2 ** -11 }, { visibility_on: 2 ** 30 + 1 },
    { visibility_on: Infinity }, { visibility_off: 1 }, { visibility_low: -0.01 },
    { visibility_low: 1.01 }, { visibility_low: NaN }, { visibility_mode: 0 },
    { ...renewal, visibility_off: 0 }, { ...renewal, visibility_off: Infinity },
    { ...renewal, visibility_off: 2 ** -11 }, { ...renewal, visibility_off: 2 ** 30 + 1 },
    { b2_amp: 1 }, { world_kind: 0 },
  ]) assert.throws(() => make(w), /visibility|single-target/);
  for (const von of [2 ** -10, 2 ** 30]) make({ visibility_on: von });
  for (const voff of [2 ** -10, 2 ** 30]) make({ ...renewal, visibility_off: voff });
});

test('enabled visibility refuses both initial and later user-target mode without mutation', () => {
  assert.throws(() => make({}, { mode: 'user' }), /user-target/);
  const sim = make();
  const before = JSON.stringify(sim.state());
  assert.throws(() => sim.setMode('user'), /user-target/);
  // state() drains display events, so compare simulator state and hashes directly.
  assert.equal(sim.life.mode, 'auto');
  assert.equal(sim.life.visibility_bright, true);
  assert.equal(sim.t, 0);
  assert.ok(before.includes('auto'));
  const legacy = make(neutral); legacy.setMode('user'); assert.equal(legacy.life.mode, 'user');
});

test('flash starts bright at nonzero t0 and changes strictly after its deadline', () => {
  const sim = make({ t0: 32, t_resp: 0, tau_turn: 0 });
  const life = sim.life;
  assert.equal(life.visibility_next, 37);
  assert.equal(life.visibility_k, 0);
  const before = sim.hashes();
  life.worldTo(37);
  assert.equal(life.visibility_bright, true);
  assert.deepEqual(sim.hashes(), before);
  life.worldTo(nextup(37));
  assert.equal(life.visibility_bright, false);
  assert.equal(life.visibility_next, Infinity);
  const words = [14n, bits(37), 0n, 0n];
  assert.equal(sim.hashes().world, fold(BigInt('0x' + before.world), words));
  assert.equal(sim.hashes().all, fold(BigInt('0x' + before.all), words));
  assert.equal(life.evlog.filter(x => x.kind === 'visibility').length, 1);
});

test('flash placement before or at expiry replaces the deadline without a visibility event', () => {
  for (const t of [4, 5]) {
    const life = make({ t_resp: 0, tau_turn: 0 }).life;
    life.worldTo(t); life.place(life.blobs[0], 1, t);
    life.worldTo(nextup(5));
    assert.equal(life.visibility_bright, true);
    assert.equal(life.visibility_next, t + 5);
    assert.equal(life.evlog.filter(x => x.kind === 'visibility').length, 0);
  }
});

test('timer placement at old flash expiry resets before the transition', () => {
  const life = make({ t_resp: 10, tau_turn: 0 }).life;
  life.blobs[0].r = 5;
  life.worldTo(5); assert.equal(life.blobs[0].q, 1);
  life.worldTo(nextup(5));
  assert.equal(life.blobs[0].q, 2);
  assert.equal(life.visibility_next, 10);
  assert.equal(life.visibility_bright, true);
  assert.equal(life.evlog.filter(x => x.kind === 'visibility').length, 0);
});

test('equal-time renewal events are timer then turn then visibility', () => {
  const life = make(renewal).life, calls = [];
  life.blobs[0].r = life.blobs[0].tau = life.visibility_next = 5;
  for (const method of ['timer', 'turn', 'visibilityTransition']) {
    const original = life[method];
    life[method] = function (...args) { calls.push(method); return original.apply(this, args); };
  }
  life.worldTo(5); assert.deepEqual(calls, []);
  life.worldTo(nextup(5));
  assert.deepEqual(calls, ['timer', 'turn', 'visibilityTransition']);
});

test('renewal uses stream 26 and retains its counter/deadline through placements', () => {
  const life = make({ ...renewal, t0: 32, t_resp: 0, tau_turn: 0 }).life;
  const first = visibilityNext(55040000, 0, 32, 20);
  assert.equal(bits(life.visibility_next), bits(first));
  life.place(life.blobs[0], 1, 33);
  assert.equal(life.visibility_next, first); assert.equal(life.visibility_k, 1);
  life.worldTo(first); assert.equal(life.visibility_bright, true);
  life.worldTo(nextup(first));
  assert.equal(life.visibility_bright, false);
  assert.equal(bits(life.visibility_next), bits(visibilityNext(55040000, 1, first, 20)));
  const second = life.visibility_next;
  life.place(life.blobs[0], 2, first);
  assert.equal(life.visibility_next, second); assert.equal(life.visibility_k, 2);
  life.worldTo(nextup(second)); assert.equal(life.visibility_bright, true);
});

test('low light changes only the target signal and stays below the bright candidate bound', () => {
  for (const low of [0, 0.25, 1]) {
    const life = make({ visibility_low: low, t_resp: 0, tau_turn: 0 }).life;
    life.worldTo(6);
    const bl = life.blobs[0];
    const rate = life.rate(life.blobX(bl, 6), life.blobY(bl, 6), 6);
    assert.equal(bits(rate), bits(life.lam_bg + low * life.lam_s));
    assert.ok(rate <= life.lam_max);
    assert.equal(life.lam_max, life.lam_bg + life.lam_s);
  }
});

test('low-light capture count uses pre-replacement state and the accounting window', () => {
  const life = make({ t_resp: 0, tau_turn: 0, t_open: 6 }).life;
  life.worldTo(6);
  const bl = life.blobs[0];
  const capture = (t, counted) => {
    bl.x = bl.y = bl.vx = bl.vy = 0; bl.t = t;
    life.click(t, counted);
  };
  capture(5.5, false);
  assert.equal(life.led[57], 0);
  capture(6, true);
  assert.equal(life.led[57], 1);
  assert.equal(life.visibility_bright, false);
  assert.equal(life.defer_place.length, 2);
  life.place(bl, 1, 6);
  assert.equal(life.visibility_bright, true);
  assert.equal(life.visibility_next, 11);
  assert.equal(life.led[57], 1);
});

test('visibility transition exactly at end is outside the half-open life', () => {
  const sim = make({ T: 8, visibility_on: 8, t_resp: 0, tau_turn: 0 });
  sim.run();
  assert.equal(sim.life.visibility_bright, true);
  assert.equal(sim.life.evlog.filter(x => x.kind === 'visibility').length, 0);
});

test('neutral ABI 4 equals ABI 3 except the one additional close-hash fold', () => {
  const legacy = LifeSim.create(body(neutral, 3), { seed: 55040000, T: 16, hashes: true });
  const modern = make(neutral, { T: 16 });
  legacy.run(); modern.run();
  assert.deepEqual(Array.from(modern.life.led.slice(0, 57)).map(bits), Array.from(legacy.life.led).map(bits));
  assert.equal(modern.ledger().low_light_captures, 0);
  for (const family of ['spikes', 'fate', 'chem', 'world']) assert.equal(modern.hashes()[family], legacy.hashes()[family]);
  assert.equal(modern.hashes().all, fold(BigInt('0x' + legacy.hashes().all), [0n]));
  assert.equal(modern.life.evlog.filter(x => x.kind === 'visibility').length, 0);
});

const arg = process.argv.indexOf('--truth');
if (arg >= 0) {
  if (!process.argv[arg + 1]) throw new Error('--truth requires an explicit fixture file');
  const truth = JSON.parse(fs.readFileSync(process.argv[arg + 1], 'utf8'));
  assert.equal(truth.status, 'complete');
  assert.equal(truth.cases.length, 16);
  assert.equal(truth.C_lives, truth.cases.length);
  assert.equal(truth.Python_lives, truth.cases.length);
  for (const item of truth.cases) test('C/Python/JS truth: ' + item.name, () => {
    const sim = LifeSim.create(item.body, { seed: item.seed, hashes: true, raster: truth.raster_cap });
    sim.run();
    assert.ok(item.ledger.every(x => Number.isFinite(Number(x))));
    assert.deepEqual(Array.from(sim.life.led).map(bits), item.ledger.map(x => bits(Number(x))), 'every ledger byte');
    assert.deepEqual(Object.values(sim.hashes()), item.hashes, 'all five hashes');
    const raster = sim.raster();
    assert.equal(raster.n, item.raster_total);
    assert.deepEqual(raster.t.map(bits), item.raster_t.map(x => bits(Number(x))));
    assert.deepEqual(raster.uid, item.raster_uid);
    const stepped = LifeSim.create(item.body, { seed: item.seed, hashes: true, raster: truth.raster_cap });
    while (!stepped.ended) { stepped.advance(0.37, 40); stepped.state(); }
    assert.deepEqual(stepped.hashes(), sim.hashes(), 'capped stepping invariance');
  });
}
console.log(`${checks} visibility checks passed`);
