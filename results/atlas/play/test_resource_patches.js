#!/usr/bin/env node
/* Fixed ABI-6 engineering fixtures. No seed search or behavioral success criterion.
 * --truth FILE adds two complete replays per saved case; --truth-only skips the default boundary fixtures.
 */
'use strict';
const assert = require('assert/strict'), fs = require('fs');
const LifeSim = require('./lifesim.js'), doc = require('./bodies.json');
let checks = 0, created = 0, completeRuns = 0;
const test = (name, fn) => { fn(); checks++; console.log('pass: ' + name); };
const clone = value => JSON.parse(JSON.stringify(value));
const buf = new DataView(new ArrayBuffer(8));
const bits = x => { buf.setFloat64(0, Number(x), true); return buf.getBigUint64(0, true); };
const nextup = x => { const b = bits(x); buf.setBigUint64(0, b + (x < 0 ? -1n : 1n), true); return buf.getFloat64(0, true); };
const MASK = (1n << 64n) - 1n;
function sm(x) {
  let z = (x + 0x9e3779b97f4a7c15n) & MASK;
  z = ((z ^ (z >> 30n)) * 0xbf58476d1ce4e5b9n) & MASK;
  z = ((z ^ (z >> 27n)) * 0x94d049bb133111ebn) & MASK;
  return z ^ (z >> 31n);
}
function draw(seed, stream, slot, purpose) {
  const h = sm(sm(sm(BigInt(seed) ^ sm(BigInt(stream))) ^ BigInt(slot)) ^ BigInt(purpose));
  return Number((h >> 11n) | 1n) * 2 ** -53;
}
function fold(h, words) { for (const w of words) h = sm(h ^ w); return h.toString(16).padStart(16, '0'); }
const patchWorld = { T: 64, t0: 0, t_open: 0, task_mode: 0, sample_min: 0, sample_max: 0,
  blank_min: 0, blank_max: 0, choice_T: 0, reset_T: 0, visibility_mode: 0, visibility_on: 0,
  visibility_off: 0, visibility_low: 1, patch_count: 3, patch_capacity: 2, patch_refill_fast: 8,
  patch_refill_slow: 16, patch_landmark: .1, v_t: 0, tau_turn: 0, t_resp: 0,
  b2_amp: 0, b2_value: 0, b2_mode: 0, b2_p: 1, sigma: .6, rho_c: 1, R_min: 2, R_max: 4 };
function body(world = {}, abi = 6) {
  const b = clone(doc.bodies[6]); b.abi = abi; Object.assign(b.world, patchWorld, world); return b;
}
function make(world = {}, opts = {}) {
  created++; return LifeSim.create(body(world), { seed: 42000000, hashes: true, ...opts });
}
function run(sim) { sim.run(); completeRuns++; return sim; }
function onPatch(life, slot, t) {
  life.X = life.patches[slot].x; life.Y = life.patches[slot].y; life.t_x = t; life.Fx = life.Fy = 0;
}
function click(life, slot, t) {
  life.worldTo(t); life.patchGroupBegin(); onPatch(life, slot, t);
  life.click(t, t >= life.t_open_abs); life.patch_group = false;
}
function conservation(ledger, n) {
  let h = 0, empty = 0;
  for (let i = 0; i < 4; i++) {
    const get = stem => ledger['patch_' + stem + '_' + i];
    assert.equal(get('source'), get('supply') + get('spill'));
    assert.equal(get('stock_open') + get('supply'), get('harvest') + get('stock_end'));
    assert.equal(get('harvest'), get('initial_harvest') + get('refill_harvest'));
    h += get('harvest'); empty += get('empty');
    if (i >= n) for (const stem of ['stock_open', 'source', 'supply', 'spill', 'harvest', 'empty',
      'stock_end', 'initial_harvest', 'refill_harvest']) assert.equal(get(stem), 0);
  }
  assert.equal(ledger.captures, h); assert.equal(ledger.misses, empty + ledger.patch_geometric_misses);
  assert.equal(ledger.clicks, ledger.captures + ledger.misses);
}
if (!process.argv.includes('--truth-only')) {
  test('ABI6 appends exact columns and rejects incompatible or invalid worlds', () => {
    assert.equal(LifeSim.LEDGER_V6.length, 107); assert.deepEqual(LifeSim.LEDGER_V6.slice(0, 70), LifeSim.LEDGER_V5);
    assert.equal(LifeSim.LEDGER_V6[98], 'patch_geometric_misses');
    assert.equal(LifeSim.LEDGER_V6[106], 'patch_refill_harvest_3');
    for (const world of [{ patch_count: -1 }, { patch_count: 5 }, { patch_count: .5 }, { patch_count: 0 },
      { patch_capacity: 0 }, { patch_capacity: 1.5 }, { patch_refill_fast: 0 }, { patch_refill_slow: 4 },
      { patch_landmark: 1 }, { patch_landmark: NaN }, { b2_value: -1 }, { v_t: .1 }, { t_resp: 1 },
      { rho_c: 0 }, { R_min: 1.9 }, { R_max: Infinity }, { lam_s: 400 }, { T: 2 ** 30 },
      { t0: NaN }, { t0: .5 }, { t0: 2 ** 30 + 1 }, { t0: Infinity },
      { t_open: NaN }, { t_open: -1 }, { t_open: 64 }, { t_open: Infinity }])
      assert.throws(() => make(world), /patch/);
    assert.throws(() => make({ t_open: 32 }, { T: 16 }), /time\/window/);
    created++; assert.throws(() => LifeSim.create(body({}, 5)), /ABI 6/);
    assert.throws(() => make({}, { mode: 'user' }), /automatic/);
    assert.throws(() => make({}, { targets: [] }), /automatic/);
  });
  test('independent streams and count1 through4 geometry obey the contract', () => {
    for (const n of [1, 2, 3, 4]) {
      const life = make({ patch_count: n }).life, angle = 2 * Math.PI * draw(42000000, 31, 0, 0);
      assert.equal(life.lam_max, .05 + 2 * n);
      for (const p of life.patches) {
        const theta = angle + (2 * Math.PI * p.id) / n, r = 2 + 2 * draw(42000000, 31, p.id, 1);
        assert.equal(bits(p.x), bits(r * LifeSim.libm.cos(theta)));
        assert.equal(bits(p.y), bits(r * LifeSim.libm.sin(theta)));
        assert.equal(p.period, draw(42000000, 32, p.id, 0) < .5 ? 8 : 16);
        assert.equal(bits(p.first), bits(p.period * draw(42000000, 33, p.id, 0)));
        for (const q of life.patches) if (q.id !== p.id) assert.ok((p.x-q.x)**2 + (p.y-q.y)**2 > 4);
      }
    }
  });
  test('manual editing is rejected and observer reads are pure', () => {
    const sim = make(), before = sim.hashes(), stocks = sim.life.patches.map(p => p.stock);
    for (const edit of [() => sim.setMode('user'), () => sim.addTarget(0, 0), () => sim.moveTarget(0, 1, 1),
      () => sim.removeTarget(0), () => sim.setDrift(true)]) assert.throws(edit, /patch/);
    sim.state(); sim.state(); sim.life.patchRate(0, 0); sim.life.patchNearest(0, 0);
    assert.deepEqual(sim.hashes(), before); assert.deepEqual(sim.life.patches.map(p => p.stock), stocks);
    const view = sim.state(); view.patches[0].stock = 99; assert.equal(sim.life.patches[0].stock, 2);
  });
  test('source deadline left limit, spill and exact source hashes', () => {
    const sim = make({ patch_count: 1 }), life = sim.life, p = life.patches[0], t = p.next;
    life.worldTo(t); assert.equal(p.arrival_index, 0); const before = sim.hashes();
    life.worldTo(nextup(t)); assert.equal(p.stock, 2); assert.equal(sim.ledger().patch_spill_0, 1);
    const words = [19n, bits(t), 0n, 0n, 2n, 2n, 0n];
    assert.equal(sim.hashes().world, fold(BigInt('0x' + before.world), words));
    assert.equal(bits(p.next), bits(p.first + p.period));
  });
  test('direct source serialization retains the high32 bits of the arrival index', () => {
    // Synthetic serialization boundary: accepted lives have a much smaller bounded source inventory.
    const sim = make({ patch_count: 1 }), life = sim.life, p = life.patches[0];
    p.arrival_index = 2 ** 32 + 3; p.next = p.first + p.arrival_index * p.period;
    const t = p.next, before = sim.hashes(), index = p.arrival_index;
    life.worldTo(nextup(t));
    const words = [19n, bits(t), 0n, BigInt(index), 2n, 2n, 0n];
    for (const family of ['world', 'all'])
      assert.equal(sim.hashes()[family], fold(BigInt('0x' + before[family]), words));
    assert.equal(p.arrival_index, index + 1);
    assert.equal(sim.ledger().patch_source_0, 1);
  });
  test('same-group harvests reserve stock while receptors keep the left-limit field', () => {
    const sim = make({ patch_count: 1 }), life = sim.life, t = 0, p = life.patches[0];
    life.worldTo(t); life.patchGroupBegin(); onPatch(life, 0, t);
    const rate = life.rate(p.x, p.y, t), next = p.next;
    life.click(t, true); life.click(t, true); life.click(t, true);
    assert.equal(p.stock, 0); assert.equal(p.initial_remaining, 0); assert.equal(p.next, next);
    assert.equal(life.rate(p.x, p.y, t), rate); life.patch_group = false;
    assert.equal(life.rate(p.x, p.y, t), life.lam_bg + life.lam_s * .1);
    assert.equal(sim.ledger().captures, 2); assert.equal(sim.ledger().patch_empty_0, 1);
    assert.equal(sim.ledger().patch_initial_harvest_0, 2); assert.equal(sim.ledger().income, 1000);
    life.X = life.Y = 100; life.click(t, true); assert.equal(sim.ledger().patch_geometric_misses, 1);
    life.worldTo(nextup(next)); assert.equal(p.stock, 1); click(life, 0, nextup(next));
    assert.equal(sim.ledger().patch_refill_harvest_0, 1);
    life.close(next + 1, 0); conservation(sim.ledger(), 1);
  });
  test('opening-stock and FIFO provenance survive pre-window harvests and boundary supply', () => {
    const sim = make({ patch_count: 1, t_open: 4 }), life = sim.life, p = life.patches[0];
    p.first = p.next = 4; p.period = 8; click(life, 0, 1);
    click(life, 0, 4); assert.equal(sim.ledger().patch_stock_open_0, 1);
    assert.equal(sim.ledger().patch_initial_harvest_0, 1); assert.equal(p.stock, 0);
    life.worldTo(nextup(4)); assert.equal(sim.ledger().patch_source_0, 1); assert.equal(p.stock, 1);
    click(life, 0, 5); life.close(8, 0); conservation(sim.ledger(), 1);
    assert.equal(sim.ledger().patch_refill_harvest_0, 1); assert.equal(sim.ledger().captures, 2);
  });
  test('endpoint exclusion and close at/before opening retain physical terminal stock only', () => {
    for (const end of [3, 4]) {
      const sim = make({ patch_count: 1, t_open: 4 }), life = sim.life;
      life.patches[0].next = life.patches[0].first = end; click(life, 0, 1);
      const before = sim.hashes(); life.close(end, 0);
      assert.ok(Array.from(life.led.slice(70)).every(v => v === 0));
      assert.equal(sim.hashes().world, fold(BigInt('0x'+before.world), [21n,bits(end),0n,1n,1n]));
    }
  });
  test('injected per-slot imbalance is flagged even when aggregate counts cancel', () => {
    const sim = make(), life = sim.life; life.worldTo(0);
    life.led[LifeSim.LEDGER_V6.indexOf('patch_source_0')] = 1;
    life.led[LifeSim.LEDGER_V6.indexOf('patch_spill_1')] = 1;
    life.close(1, 0); assert.ok(sim.ledger().status & 64);
  });
  test('actual extinction and guard keep world/window conservation', () => {
    const extinct = run(make({ T: 32, kill_t: 1, kill_frac: 1 }));
    assert.equal(extinct.life.t_end, 32); assert.equal(extinct.ledger().n_end, 0);
    assert.ok(extinct.ledger().patch_source_0 > 0); conservation(extinct.ledger(), 3);
    const guarded = run(make({ t_open: 8 }, { e_max: 0 }));
    assert.ok(guarded.life.t_end <= 8); assert.ok(Array.from(guarded.life.led.slice(70)).every(v => v === 0));
  });
  test('neutral V6 preserves V5 full records and appends only37 zero close folds', () => {
    const b = clone(doc.bodies[6]); b.world.T = 16;
    const old = LifeSim.create({ ...b, abi: 5 }, { seed: 42000000, hashes: true });
    const current = LifeSim.create({ ...b, abi: 6 }, { seed: 42000000, hashes: true }); created += 2;
    run(old); run(current);
    assert.deepEqual(Array.from(current.life.led.slice(0,70)).map(bits), Array.from(old.life.led).map(bits));
    assert.ok(Array.from(current.life.led.slice(70)).every(v => v === 0));
    for (const family of ['world','fate','spikes','chem']) assert.equal(current.hashes()[family], old.hashes()[family]);
    assert.equal(current.hashes().all, fold(BigInt('0x'+old.hashes().all), Array(37).fill(0n)));
  });
  test('source processing is invariant to capped stepping and observer polling', () => {
    const full = run(make({ T: 32 })), stepped = make({ T: 32 });
    while (!stepped.ended) { stepped.advance(.37, 40); stepped.state(); stepped.life.patchRate(0, 0); }
    completeRuns++; assert.deepEqual(stepped.hashes(), full.hashes());
    assert.deepEqual(Array.from(stepped.life.led).map(bits), Array.from(full.life.led).map(bits));
    conservation(full.ledger(), 3);
  });
}
const arg = process.argv.indexOf('--truth');
if (arg >= 0) {
  const truth = JSON.parse(fs.readFileSync(process.argv[arg+1], 'utf8'));
  assert.equal(truth.status, 'complete'); assert.equal(truth.abi, 6);
  for (const item of truth.cases) test('C/Python/JS truth: ' + item.name, () => {
    const full = LifeSim.create(item.body, { seed: item.seed, hashes: true, raster: truth.raster_cap }); created++;
    run(full); assert.deepEqual(Array.from(full.life.led).map(bits), item.ledger.map(bits));
    assert.deepEqual(Object.values(full.hashes()), item.hashes);
    const raster = full.raster(); assert.equal(raster.n, item.raster_total);
    assert.deepEqual(raster.t.map(bits), item.raster_t.map(bits)); assert.deepEqual(raster.uid, item.raster_uid);
    conservation(full.ledger(), item.body.world.patch_count);
    const stepped = LifeSim.create(item.body, { seed: item.seed, hashes: true, raster: truth.raster_cap }); created++;
    while (!stepped.ended) { stepped.advance(.37, 40); stepped.state(); }
    completeRuns++; assert.deepEqual(stepped.hashes(), full.hashes());
    assert.deepEqual(Array.from(stepped.life.led).map(bits), Array.from(full.life.led).map(bits));
  });
}
console.log(JSON.stringify({ checks, construction_attempts: created, complete_runs: completeRuns }));
