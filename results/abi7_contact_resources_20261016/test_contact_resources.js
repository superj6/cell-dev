#!/usr/bin/env node
/* Fixed ABI7 engineering boundaries; no seed search or behavioral success gate.
 * Default includes two neutral completed lives. --truth FILE adds two replays per supplied case.
 * --truth-only skips default fixtures. Direct helpers are counted separately from complete replays.
 */
'use strict';
const assert = require('assert/strict'), fs = require('fs');
const LifeSim = require('../../results/atlas/play/lifesim.js');
const doc = require('../../results/atlas/play/bodies.json');
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
function fold(h, words) { for (const w of words) h = sm(h ^ w); return h.toString(16).padStart(16, '0'); }
const patchWorld = { T: 64, t0: 0, t_open: 0, task_mode: 0, sample_min: 0, sample_max: 0,
  blank_min: 0, blank_max: 0, choice_T: 0, reset_T: 0, visibility_mode: 0, visibility_on: 0,
  visibility_off: 0, visibility_low: 1, patch_count: 1, patch_capacity: 2, patch_refill_fast: 16,
  patch_refill_slow: 32, patch_landmark: .1, patch_contact_delay: 4, v_t: 0, tau_turn: 0, t_resp: 0,
  b2_amp: 0, b2_value: 0, b2_mode: 0, b2_p: 1, sigma: .6, rho_c: 1, R_min: 2, R_max: 4 };
function body(world = {}, abi = 7) {
  const b = clone(doc.bodies[6]); b.abi = abi; Object.assign(b.world, patchWorld, world); return b;
}
function make(world = {}, opts = {}) {
  created++; return LifeSim.create(body(world), { seed: 42000000, hashes: true, ...opts });
}
function direct(world = {}) {
  const sim = make(world);
  for (const p of sim.life.patches) p.next = p.first = 1000;
  return sim;
}
function onPatch(life, slot, t) {
  life.X = life.patches[slot].x; life.Y = life.patches[slot].y; life.t_x = t; life.Fx = life.Fy = 0;
}
function click(life, slot, t, n = 1) {
  life.worldTo(t); life.patchGroupBegin(); onPatch(life, slot, t);
  for (let i = 0; i < n; i++) life.click(t, t >= life.t_open_abs);
  life.patch_group = false;
}
function conservation(ledger) {
  let h = 0, empty = 0;
  for (let i = 0; i < 4; i++) {
    const g = stem => ledger['patch_' + stem + '_' + i];
    assert.equal(g('source'), g('supply') + g('spill'));
    assert.equal(g('stock_open') + g('supply'), g('harvest') + g('stock_end'));
    assert.equal(g('harvest'), g('initial_harvest') + g('refill_harvest'));
    assert.equal(g('contact_pending_open') + g('contact_starts'), g('contact_maturities') + g('contact_pending_end'));
    assert.equal(g('contact_maturities'), g('contact_supply') + g('contact_spill'));
    assert.equal(g('contact_stock_open') + g('contact_supply'), g('contact_harvest') + g('contact_stock_end'));
    assert.ok(g('contact_harvest') <= g('refill_harvest')); assert.ok(g('contact_starts') <= g('empty'));
    h += g('harvest'); empty += g('empty');
  }
  assert.equal(ledger.captures, h); assert.equal(ledger.misses, empty + ledger.patch_geometric_misses);
  assert.equal(ledger.clicks, ledger.captures + ledger.misses); assert.equal(ledger.status & 64, 0);
}
if (!process.argv.includes('--truth-only')) {
  test('ABI7 appends exact layout and rejects enabled old ABI, invalid delay and bounds', () => {
    assert.equal(LifeSim.LEDGER_V7.length, 143); assert.deepEqual(LifeSim.LEDGER_V7.slice(0,107), LifeSim.LEDGER_V6);
    assert.equal(LifeSim.LEDGER_V7[107], 'patch_contact_starts_0');
    assert.equal(LifeSim.LEDGER_V7[142], 'patch_contact_stock_end_3');
    for (const delay of [-1, NaN, Infinity, 2 ** -11, 2 ** 30 + 1])
      assert.throws(() => make({ patch_contact_delay: delay }), /contact/);
    assert.throws(() => make({}, { abi: 6 }), /ABI 7/);
    assert.throws(() => make({ patch_count: 0, patch_capacity: 0, patch_refill_fast: 0,
      patch_refill_slow: 0, patch_landmark: 0 }), /disabled patches/);
    assert.throws(() => make({ T: 1024, patch_contact_delay: 2 ** -10 }), /combined source/);
  });
  test('only empty clicks start, repeated taps do not reset, geometry miss does not start', () => {
    const sim = direct(), l = sim.life, p = l.patches[0];
    click(l, 0, 0, 2); assert.equal(p.stock, 0); assert.equal(p.contact_pending, false);
    click(l, 0, 1); assert.equal(p.contact_due, 5); assert.equal(p.contact_starts, 1);
    click(l, 0, 2, 3); assert.equal(p.contact_due, 5); assert.equal(p.contact_starts, 1);
    l.X = l.Y = 100; l.t_x = 2; l.click(2, true);
    assert.equal(sim.ledger().patch_geometric_misses, 1); assert.equal(sim.ledger().patch_contact_starts_0, 1);
    assert.equal(sim.ledger().misses, 5); assert.equal(sim.ledger().income, 1000);
    l.close(3, 0); conservation(sim.ledger());
  });
  test('pending jobs have no cue, same-group candidates retain left stock, observers are pure', () => {
    const sim = direct(), l = sim.life, p = l.patches[0];
    l.worldTo(0); l.patchGroupBegin(); onPatch(l, 0, 0); const full = l.patchRate(p.x,p.y);
    l.click(0,true); l.click(0,true); l.click(0,true);
    assert.equal(l.patchRate(p.x,p.y),full); l.patch_group=false;
    assert.equal(l.patchRate(p.x,p.y),l.lam_bg+l.lam_s*.1);
    const hashes=sim.hashes(), due=p.contact_due; sim.state(); sim.state(); sim.info(); l.patchRate(0,0);
    assert.deepEqual(sim.hashes(),hashes); assert.equal(p.contact_due,due); assert.equal(p.contact_starts,1);
    assert.throws(()=>sim.addTarget(0,0),/patch/);
  });
  test('exact maturity click uses prior stock and pending job, strictly later maturity admits', () => {
    const sim=direct(), l=sim.life,p=l.patches[0]; click(l,0,0,3);
    click(l,0,4); assert.equal(p.stock,0); assert.equal(p.contact_starts,1); assert.equal(p.contact_pending,true);
    l.worldTo(nextup(4)); assert.equal(p.stock,1); assert.equal(p.contact_pending,false);
    click(l,0,5); assert.equal(sim.ledger().patch_contact_harvest_0,1); assert.equal(p.contact_starts,1);
    click(l,0,6); assert.equal(p.contact_due,10); l.close(7,0); conservation(sim.ledger());
  });
  test('FIFO alternation and ring wrap preserve passive/contact provenance', () => {
    const sim=direct(),l=sim.life,p=l.patches[0]; click(l,0,0,3); p.first=p.next=2; p.period=1000;
    l.worldTo(5); assert.equal(p.stock,2); assert.equal(p.contact_stock,1);
    click(l,0,5); assert.equal(sim.ledger().patch_contact_harvest_0,0);
    click(l,0,5); assert.equal(sim.ledger().patch_contact_harvest_0,1);
    click(l,0,5); p.first=p.next=10; p.arrival_index=0;
    l.worldTo(11); click(l,0,11); assert.equal(sim.ledger().patch_contact_harvest_0,2);
    click(l,0,11); assert.equal(sim.ledger().patch_refill_harvest_0,4);
    l.close(12,0); conservation(sim.ledger());
  });
  test('world ties are slot then passive/contact; full maturity spills and clears without restart', () => {
    const sim=direct({patch_count:2}), l=sim.life;
    for(let i=0;i<2;i++) { click(l,i,0,3); const p=l.patches[i];p.first=p.next=4;p.period=1000; }
    sim.state(); l.worldTo(5);
    assert.deepEqual(sim.state().events.map(e=>[e.slot,e.kind]),
      [[0,'patch_source'],[0,'patch_contact_mature'],[1,'patch_source'],[1,'patch_contact_mature']]);
    const p=l.patches[0]; click(l,0,5,3); p.first=p.next=6;p.arrival_index=0;p.period=1;
    l.worldTo(10); assert.equal(p.stock,2); assert.equal(p.contact_pending,false);
    assert.equal(sim.ledger().patch_contact_spill_0,1); assert.equal(p.contact_starts,2);
    l.close(10,0); conservation(sim.ledger());
  });
  test('prewindow jobs and contact stock retain provenance at opening', () => {
    for(const opening of [2,5]) {
      const sim=direct({t_open:opening}),l=sim.life;click(l,0,0,3);l.worldTo(6);click(l,0,6);
      l.close(7,0);conservation(sim.ledger());
      assert.equal(sim.ledger().patch_contact_starts_0,0);
      assert.equal(sim.ledger().patch_contact_pending_open_0,opening===2?1:0);
      assert.equal(sim.ledger().patch_contact_stock_open_0,opening===5?1:0);
      assert.equal(sim.ledger().patch_contact_harvest_0,1);
    }
  });
  test('window and terminal ties exclude maturity; all21 records precede all24', () => {
    const sim=direct({patch_count:2,t_open:4}),l=sim.life;
    for(let i=0;i<2;i++)click(l,i,0,3);
    const before=sim.hashes();l.close(4,0);
    assert.ok(Array.from(l.led.slice(70)).every(x=>x===0));
    const words=[21n,bits(4),0n,0n,0n,21n,bits(4),1n,0n,0n,
      24n,bits(4),0n,1n,bits(4),0n,1n,24n,bits(4),1n,1n,bits(4),0n,1n];
    assert.equal(sim.hashes().world,fold(BigInt('0x'+before.world),words));
  });
  test('start/maturity/end hashes retain full uint64 job indices', () => {
    const sim=direct(),l=sim.life,p=l.patches[0];click(l,0,0,2);
    p.contact_starts=2**32+3;const index=p.contact_starts,before=sim.hashes();click(l,0,1);
    const words=[22n,bits(1),0n,BigInt(index),bits(5),20n,bits(1),2n,0n,0n,0n,0n,
      11n,bits(1),0n,bits(p.x),bits(p.y)];
    assert.equal(sim.hashes().world,fold(BigInt('0x'+before.world),words));
    const mid=sim.hashes();l.worldTo(6);
    assert.equal(sim.hashes().world,fold(BigInt('0x'+mid.world),[23n,bits(5),0n,BigInt(index),0n,1n,1n]));
    const end=sim.hashes();l.close(6,0);
    assert.equal(sim.hashes().world,fold(BigInt('0x'+end.world),
      [21n,bits(6),0n,1n,0n,24n,bits(6),0n,0n,0n,1n,BigInt(index+1)]));
    conservation(sim.ledger());
  });
  test('injected counter/ring corruption flags ledger mismatch', () => {
    for(const corrupt of [l=>{l.led[107]=1;},l=>{l.patches[0].origin_count=1;},
      l=>{l.led[127]=1;},l=>{l.patches[0].contact_due=3;}]) {
      const sim=direct();sim.life.worldTo(0);corrupt(sim.life);sim.life.close(1,0);
      assert.ok(sim.ledger().status&64);
    }
  });
  test('neutral ABI7 preserves ABI6 physics and hashes plus36 zero ledger folds', () => {
    const b=body({T:16,patch_contact_delay:0});
    const old=LifeSim.create(b,{abi:6,seed:42000000,hashes:true});created++;
    const current=LifeSim.create(b,{abi:7,seed:42000000,hashes:true});created++;
    old.run();current.run();completeRuns+=2;
    assert.deepEqual(Array.from(current.life.led.slice(0,107)).map(bits),Array.from(old.life.led).map(bits));
    assert.ok(Array.from(current.life.led.slice(107)).every(x=>x===0));
    for(const family of ['world','fate','spikes','chem'])assert.equal(current.hashes()[family],old.hashes()[family]);
    assert.equal(current.hashes().all,fold(BigInt('0x'+old.hashes().all),Array(36).fill(0n)));
  });
}
const arg=process.argv.indexOf('--truth');
if(arg>=0) {
  const truth=JSON.parse(fs.readFileSync(process.argv[arg+1],'utf8'));
  assert.equal(truth.status,'complete');assert.equal(truth.abi,7);
  for(const item of truth.cases)test('C/Python/JS truth: '+item.name,()=>{
    const full=LifeSim.create(item.body,{seed:item.seed,hashes:true,raster:truth.raster_cap});created++;
    full.run();completeRuns++;assert.deepEqual(Array.from(full.life.led).map(bits),item.ledger.map(bits));
    assert.deepEqual(Object.values(full.hashes()),item.hashes);const raster=full.raster();
    assert.equal(raster.n,item.raster_total);assert.deepEqual(raster.t.map(bits),item.raster_t.map(bits));
    assert.deepEqual(raster.uid,item.raster_uid);conservation(full.ledger());
    const stepped=LifeSim.create(item.body,{seed:item.seed,hashes:true,raster:truth.raster_cap});created++;
    while(!stepped.ended){stepped.advance(.37,40);stepped.state();}
    completeRuns++;assert.deepEqual(stepped.hashes(),full.hashes());
    assert.deepEqual(Array.from(stepped.life.led).map(bits),Array.from(full.life.led).map(bits));
  });
}
console.log(JSON.stringify({checks,construction_attempts:created,complete_runs:completeRuns}));
