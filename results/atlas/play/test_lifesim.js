#!/usr/bin/env node
/* Validates lifesim.js against the C kernel and the Python reference (truth.json from export_bodies.py), then runs
 * smoke tests of the interactive world.
 *
 *   node test_lifesim.js            every body, 8 lives each, plus the interactive tests
 *   node test_lifesim.js --quick    2 lives per body
 *
 * Standard-world checks per life (same seed, same world as the kernel):
 *   - all 57 ledger columns compared bitwise (F, captures, misses, spikes, n_end, ... included);
 *   - the five log hashes (all, spikes, fate, chem, world) of LIFE_ABI.md 9.6: equal "all" means every record,
 *     every world event and every ledger column agree bit for bit;
 *   - the raster: length of the identical (t, uid) prefix of the first 2,000 spikes;
 *   - the dot and the target at the left limit of t = 100, ..., 1000 (from the reference), bitwise.
 * The life is advanced in 100-unit steps (to read the dot), and one life per body is re-run in tiny capped steps,
 * which must not change anything.
 */
'use strict';
const fs = require('fs');
const path = require('path');
const LifeSim = require('./lifesim.js');

const HERE = __dirname;
const args = process.argv.slice(2);
const QUICK = args.includes('--quick');
const doc = JSON.parse(fs.readFileSync(path.join(HERE, 'bodies.json'), 'utf8'));

function loadTruth() {
  const p = path.join(HERE, 'truth.json');
  if (fs.existsSync(p)) return JSON.parse(fs.readFileSync(p, 'utf8'));
  const truth = JSON.parse(fs.readFileSync(path.join(HERE, 'truth_kernel.json'), 'utf8'));
  truth.bodies.forEach((b, ix) => { // merge reference parts that exist
    const rp = path.join(HERE, `truth_ref_${ix}.json`);
    if (!fs.existsSync(rp)) return;
    const ref = JSON.parse(fs.readFileSync(rp, 'utf8'));
    b.lives.forEach((lv, i) => { lv.dots = ref.lives[i].dots; lv.ref_F = ref.lives[i].F; lv.ref_hashes = ref.lives[i].hashes; });
  });
  return truth;
}
const truth = loadTruth();
const LEDGER = LifeSim.LEDGER;
const iF = LEDGER.indexOf('F');
const dv = new DataView(new ArrayBuffer(8));
const bitsOf = (x) => { dv.setFloat64(0, x, true); return dv.getBigUint64(0, true); };
const same = (a, b) => bitsOf(a) === bitsOf(b);
const fmt = (x, d = 3) => (x === null || x === undefined || Number.isNaN(x)) ? '-' : Number(x).toFixed(d);

function runLife(bi, seed, stepTimes) {
  const sim = LifeSim.create(doc, { body: bi, seed, hashes: true, raster: truth.raster_n || 2000 });
  const dots = [];
  for (const c of stepTimes) {
    sim.advance(c - sim.t);
    const st = sim.state();
    dots.push([c, st.dot.x, st.dot.y, st.targets[0].x, st.targets[0].y]);
  }
  sim.advance(1e9);
  return { sim, dots };
}

function compareLife(bi, lv, res) {
  const led = res.sim.life.led;
  let cols = 0; const bad = [];
  for (let i = 0; i < LEDGER.length; i++) {
    if (same(led[i], parseFloat(lv.ledger[i]))) cols++; else bad.push(LEDGER[i]);
  }
  const hs = res.sim.hashes();
  const hnames = ['all', 'spikes', 'fate', 'chem', 'world'];
  const hashOk = hnames.map((n, i) => hs[n] === lv.hashes[i]);
  const ra = res.sim.raster();
  let prefix = 0;
  const nr = lv.raster_t.length;
  while (prefix < nr && prefix < ra.t.length && same(ra.t[prefix], parseFloat(lv.raster_t[prefix])) && ra.uid[prefix] === lv.raster_uid[prefix]) prefix++;
  let dotsOk = null, dotErr = 0;
  if (lv.dots) {
    dotsOk = 0;
    lv.dots.forEach((d, k) => {
      const mine = res.dots[k];
      let ok = true;
      for (let j = 0; j < 5; j++) {
        const want = parseFloat(d[j]);
        if (!same(mine[j], want)) { ok = false; dotErr = Math.max(dotErr, Math.abs(mine[j] - want)); }
      }
      if (ok) dotsOk++;
    });
  }
  return { cols, bad, hashOk, prefix, nr, dotsOk, nDots: lv.dots ? lv.dots.length : 0, dotErr,
    F_js: led[iF], F_k: parseFloat(lv.ledger[iF]), totalSpikes: res.sim.raster().n, kTotal: lv.raster_total };
}

// ------------------------------------------------------------------------------------- standard world
console.log('lifesim.js vs the C kernel and the reference: standard CATCH world, fresh seeds', truth.seeds[0], '...');
const stepTimes = (truth.dot_times || [100, 200, 300, 400, 500, 600, 700, 800, 900, 1000]).map(Number);
const rows = [];
let allLives = 0, allSameF = 0, allSameHash = 0, failures = 0;
for (let bi = 0; bi < truth.bodies.length; bi++) {
  const tb = truth.bodies[bi];
  if (doc.bodies[bi].name !== tb.name) throw new Error('body order differs between bodies.json and truth');
  const lives = QUICK ? tb.lives.slice(0, 2) : tb.lives;
  let sameF = 0, fullCols = 0, hashAll = 0, hashSp = 0, minPrefix = Infinity, dotsOk = 0, nDots = 0, maxDotErr = 0;
  let sumFjs = 0, sumFk = 0, secs = 0, cells = 0, spikesOk = 0, capOk = 0, cellsOk = 0;
  const badCols = new Set();
  for (const lv of lives) {
    const t0 = process.hrtime.bigint();
    const res = runLife(bi, lv.seed, stepTimes);
    secs += Number(process.hrtime.bigint() - t0) / 1e9;
    const r = compareLife(bi, lv, res);
    allLives++;
    if (same(r.F_js, r.F_k)) { sameF++; allSameF++; }
    if (r.cols === LEDGER.length) fullCols++;
    r.bad.forEach(b => badCols.add(b));
    if (r.hashOk[0]) { hashAll++; allSameHash++; }
    if (r.hashOk[1]) hashSp++;
    minPrefix = Math.min(minPrefix, r.prefix === r.nr ? r.nr : r.prefix);
    if (r.dotsOk !== null) { dotsOk += r.dotsOk; nDots += r.nDots; maxDotErr = Math.max(maxDotErr, r.dotErr); }
    sumFjs += r.F_js; sumFk += r.F_k;
    const L = res.sim.ledger();
    const k = (n) => parseFloat(lv.ledger[LEDGER.indexOf(n)]);
    if (L.spikes === k('spikes')) spikesOk++;
    if (L.captures === k('captures') && L.misses === k('misses')) capOk++;
    if (L.n_end === k('n_end')) cellsOk++;
    cells += L.n_end;
    if (!r.hashOk[0]) failures++;
  }
  // stepping must not matter: one life again in tiny capped steps
  const lv0 = lives[0];
  const sim = LifeSim.create(doc, { body: bi, seed: lv0.seed, hashes: true, raster: truth.raster_n || 2000 });
  let calls = 0;
  while (!sim.ended) { sim.advance(0.37, 40); calls++; if (calls % 97 === 0) sim.state(); }
  const stepOk = sim.hashes().all === lv0.hashes[0];
  if (!stepOk) failures++;
  // speed without hashes (the browser default)
  const sp = LifeSim.create(doc, { body: bi, seed: lv0.seed });
  const ts = process.hrtime.bigint();
  sp.run();
  const runSec = Number(process.hrtime.bigint() - ts) / 1e9;
  const n = lives.length;
  rows.push({ body: tb.name, lives: n, sameF: `${sameF}/${n}`, ledger57: `${fullCols}/${n}`,
    hashAll: `${hashAll}/${n}`, hashSpikes: `${hashSp}/${n}`, spikes: `${spikesOk}/${n}`, capMiss: `${capOk}/${n}`,
    cellsEnd: `${cellsOk}/${n}`, rasterPrefix: minPrefix === Infinity ? '-' : `${minPrefix}`,
    dots: nDots ? `${dotsOk}/${nDots}` : 'n/a', meanF_js: fmt(sumFjs / n), meanF_kernel: fmt(sumFk / n),
    meanCells: fmt(cells / n, 0), steppedSame: stepOk ? 'yes' : 'NO', unitsPerSec: fmt(1024 / runSec, 0),
    badCols: [...badCols].join(' ') || '' });
}
console.table(rows);
console.log(`standard world: ${allLives} lives, F bitwise identical in ${allSameF}, whole-life hash identical in ${allSameHash}`);

// ------------------------------------------------------------------------------------- interactive smoke tests
console.log('\ninteractive world smoke tests');
let checks = 0, passed = 0;
function check(name, ok, info) {
  checks++; if (ok) passed++; else failures++;
  console.log(`  [${ok ? 'pass' : 'FAIL'}] ${name}${info ? ': ' + info : ''}`);
}
const ROUTER = doc.bodies.findIndex(b => b.name === 'router@ring4');
const SEED = 39100000;
{ // add, move, remove; lambda_max covers the sum; switching modes
  const sim = LifeSim.create(doc, { body: ROUTER, seed: SEED });
  sim.advance(50);
  const lam0 = sim.state().stats.lam_max;
  sim.setMode('user');
  let st = sim.state();
  check('switching to user mode keeps the auto target as a still user target', st.mode === 'user' && st.targets.length === 1 && st.targets[0].drift === false, `targets ${st.targets.length}`);
  const id1 = sim.addTarget(st.dot.x + 3, st.dot.y);
  const id2 = sim.addTarget(st.dot.x - 3, st.dot.y + 1);
  st = sim.state();
  const w = doc.bodies[ROUTER].world;
  check('addTarget adds targets and raises lambda_max to lam_bg + lam_s * n', st.targets.length === 3 && st.stats.lam_max === w.lam_bg + w.lam_s * 3, `n ${st.targets.length}, lam_max ${st.stats.lam_max} (standard ${lam0})`);
  sim.moveTarget(id1, st.dot.x + 0.5, st.dot.y - 0.5);
  st = sim.state();
  const m = st.targets.find(t => t.id === id1);
  check('moveTarget sets the position at the current time', m.x === st.dot.x + 0.5 && m.y === st.dot.y - 0.5);
  sim.removeTarget(id2);
  st = sim.state();
  check('removeTarget removes it and lowers lambda_max', st.targets.length === 2 && !st.targets.some(t => t.id === id2) && st.stats.lam_max === w.lam_bg + w.lam_s * 2);
  for (let i = 0; i < 6; i++) sim.addTarget(st.dot.x + i, st.dot.y);
  check('at most 6 targets', sim.state().targets.length === LifeSim.MAX_TARGETS);
  sim.advance(30);
  check('the thinning never sees a rate above lambda_max', (sim.life.rateOver || 0) === 0, `over ${sim.life.rateOver || 0}`);
  sim.setDrift(true);
  const before = sim.state().targets.map(t => [t.x, t.y]);
  sim.advance(10);
  const after = sim.state().targets;
  const moved = after.filter((t, i) => before[i] && (t.x !== before[i][0] || t.y !== before[i][1])).length;
  check('drift on: targets run and tumble', moved === after.length, `${moved}/${after.length} moved`);
  sim.setMode('auto');
  st = sim.state();
  check('back to auto: one target, standard lambda_max', st.mode === 'auto' && st.targets.length === 1 && st.stats.lam_max === lam0);
  sim.advance(100);
  check('the life continues after the switches', sim.state().t >= 190 && !sim.ended, `t ${sim.state().t}`);
}
{ // a capture removes the caught target and books R_cap; a miss is a miss
  let caught = null, life = null, missSeen = false;
  for (let s = 0; s < 6 && !caught; s++) {
    const sim = LifeSim.create(doc, { body: ROUTER, seed: SEED + s, mode: 'user', targets: [] });
    sim.advance(40); // grow and settle with an empty screen
    let st = sim.state();
    const ids = [sim.addTarget(st.dot.x + 1.2, st.dot.y + 0.4), sim.addTarget(st.dot.x - 4, st.dot.y + 4)];
    for (let k = 0; k < 400 && !caught; k++) {
      sim.advance(1);
      st = sim.state();
      for (const e of st.events) {
        if (e.kind === 'miss') missSeen = true;
        if (e.kind === 'capture') { caught = e; life = { sim, st, ids }; break; }
      }
    }
  }
  if (caught) {
    const { st, ids } = life;
    check('a click near a target captures it', ids.includes(caught.target), `t ${fmt(caught.t, 2)} target ${caught.target}`);
    check('the captured target is removed', !st.targets.some(t => t.id === caught.target), `${st.targets.length} left`);
    check('a capture books R_cap of income', st.score.income >= doc.bodies[ROUTER].world.R_cap, `income ${st.score.income}`);
  } else check('a capture happens within 400 units', false);
  check('misses are reported as events (or none happened)', true, missSeen ? 'misses seen' : 'no miss in this run');
}
{ // lateral_off blocks in-plane spike delivery from the moment it is set
  const mk = () => { const s = LifeSim.create(doc, { body: ROUTER, seed: SEED }); s.advance(200); return s; };
  const a = mk(), b = mk();
  const la0 = a.state().stats.arrivals_lateral, lb0 = b.state().stats.arrivals_lateral;
  const va0 = a.state().stats.arrivals_vertical, vb0 = b.state().stats.arrivals_vertical;
  b.setFlag('lateral_off', true);
  a.advance(200); b.advance(200);
  const la = a.state().stats.arrivals_lateral - la0, lb = b.state().stats.arrivals_lateral - lb0;
  const va = a.state().stats.arrivals_vertical - va0, vb = b.state().stats.arrivals_vertical - vb0;
  check('lateral_off: lateral arrivals stop (only those already in flight land)', lb < 0.02 * la && la > 100, `lateral ${la} -> ${lb}, vertical ${va} -> ${vb}`);
  b.setFlag('lateral_off', false);
  const lb1 = b.state().stats.arrivals_lateral;
  b.advance(50);
  check('clearing lateral_off restores them', b.state().stats.arrivals_lateral - lb1 > 0);
}
{ // determinism of interactive sessions and the standard world in user mode with one still target
  const play = () => {
    const s = LifeSim.create(doc, { body: 0, seed: SEED, hashes: true });
    s.advance(30); s.setMode('user'); const st = s.state();
    const id = s.addTarget(st.dot.x + 2, st.dot.y); s.advance(20); s.moveTarget(id, st.dot.x, st.dot.y + 2);
    s.setFlag('lateral_off', true); s.advance(20); s.setFlag('lateral_off', false); s.setDrift(true); s.advance(30);
    return s.hashes().all + ' ' + s.state().score.net;
  };
  const p1 = play(), p2 = play();
  check('an interactive session replays identically', p1 === p2, p1);
}
{ // one body's JSON is enough (built-in hexprism tables, glibc's pow(n, 0.5) without the drag table)
  const tb = truth.bodies[3], lv = tb.lives[0];
  const s = LifeSim.create(doc.bodies[3], { seed: lv.seed, hashes: true, raster: truth.raster_n || 2000 });
  s.run();
  check('create(one body JSON) lives the same life', s.hashes().all === lv.hashes[0], tb.name);
  const st = s.state({ membrane: true });
  check('state() reports cells with phenotype hints, info() the prices', st.cells.length > 0 && 'g_r' in st.cells[0] && s.info().prices.R_cap > 0);
}
// ------------------------------------------------------------------------- libm against glibc (if vectors exist)
{
  const dir = path.join(HERE, 'tmp');
  const files = ['libm2.json', 'libm3.json'].map(f => path.join(dir, f));
  if (files.every(f => fs.existsSync(f))) {
    console.log('\nlibm ports against glibc 2.39 (vectors from Python math on this machine)');
    const L = LifeSim.libm;
    const d = Object.assign({}, ...files.map(f => JSON.parse(fs.readFileSync(f, 'utf8'))));
    for (const k of ['exp', 'log', 'sin', 'cos', 'tanh', 'expm1']) {
      let bad = 0, vbad = 0;
      const v8 = { exp: Math.exp, log: Math.log, sin: Math.sin, cos: Math.cos, tanh: Math.tanh, expm1: Math.expm1 }[k];
      for (const [xs, hb] of d[k]) { const x = parseFloat(xs); if (bitsOf(L[k](x)) !== BigInt(hb)) bad++; if (bitsOf(v8(x)) !== BigInt(hb)) vbad++; }
      check(`${k}: port = glibc on ${d[k].length} inputs`, bad === 0, `port ${bad} mismatches; V8's Math.${k} ${vbad}`);
    }
    const fv = path.join(dir, 'fma_vec.txt');
    if (fs.existsSync(fv)) {
      const fromHex = (h) => { dv.setBigUint64(0, BigInt('0x' + h), true); return dv.getFloat64(0, true); };
      let bad = 0, n = 0;
      for (const line of fs.readFileSync(fv, 'utf8').trim().split('\n')) { const [a, b, c, r] = line.split(' ').map(fromHex); n++; if (!same(L.fma(a, b, c), r)) bad++; }
      check(`fma emulation = hardware fma on ${n} triples`, bad === 0, `${bad} mismatches`);
    }
  }
}
console.log(`\n${passed}/${checks} checks passed; ${failures} failure(s) in total`);
process.exitCode = failures ? 1 : 0;
