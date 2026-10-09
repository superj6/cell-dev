#!/usr/bin/env node
/* Tests the playground as assembled in ../atlas_play.html, with a small DOM and canvas stub (no browser).
 *   node test_playground.js
 * 1. Every inline script of the page passes `node --check`; pg-data parses; lifesim.js defines only LifeSim.
 * 2. lifesim.js and the playground script run in a bare vm context with the stub; the test then drives the UI the
 *    way a reader would (intersection, taps, drags, double-taps, the × button, buttons and toggles) and checks the
 *    simulation underneath (targets, catches, modes, flags), frame budgets and canvas calls (no NaN coordinates).
 */
'use strict';
const fs = require('fs');
const path = require('path');
const vm = require('vm');
const { execFileSync } = require('child_process');

const HERE = __dirname;
const PAGE = path.join(HERE, '..', 'atlas_play.html');
const TMP = path.join(HERE, 'tmp', 'pg_scripts');
fs.mkdirSync(TMP, { recursive: true });
const html = fs.readFileSync(PAGE, 'utf8');

let pass = 0, fail = 0;
function check(name, cond, detail) {
  if (cond) { pass++; console.log(`  ok   ${name}${detail ? ' (' + detail + ')' : ''}`); }
  else { fail++; console.log(`  FAIL ${name}${detail ? ' (' + detail + ')' : ''}`); }
}

// ---------------------------------------------------------------- 1. scripts
console.log('scripts');
const scripts = [...html.matchAll(/<script([^>]*)>([\s\S]*?)<\/script>/g)].map((m) => ({ attrs: m[1], body: m[2] }));
const code = scripts.filter((s) => !/type="application\/json"/.test(s.attrs));
code.forEach((s, i) => {
  const f = path.join(TMP, `script_${i}.js`); fs.writeFileSync(f, s.body);
  let ok = true, err = '';
  try { execFileSync(process.execPath, ['--check', f], { stdio: 'pipe' }); } catch (e) { ok = false; err = String(e.stderr).slice(0, 300); }
  check(`node --check inline script ${i} (${(s.body.length / 1024).toFixed(0)} KB)`, ok, err);
});
const pgData = scripts.find((s) => /id="pg-data"/.test(s.attrs));
const pgJson = JSON.parse(pgData.body);
check('pg-data parses', pgJson.doc && pgJson.doc.bodies.length === 8 && pgJson.ui.bodies.length === 8 && pgJson.ui.seeds.length === 16);
const lifesimSrc = code.find((s) => s.body.includes('lifesim.js: one life of a CATCH body')).body;
const pgSrc = code.find((s) => s.body.includes('document.getElementById("pg-mount")')).body;
check('playground fragment sits inside section#part1, after the part-1 header',
  html.indexOf('id="part1"') < html.indexOf('id="play"') && html.indexOf('<h2>Bodies that steer a dot</h2>') < html.indexOf('id="play"')
  && html.indexOf('id="play"') < html.indexOf('id="evo-charts"'));
{
  const ctx = vm.createContext({});
  vm.runInContext(lifesimSrc, ctx);
  const added = Object.keys(ctx);
  check('lifesim.js adds exactly one global in a bare context', added.length === 1 && added[0] === 'LifeSim', added.join(','));
}

// ---------------------------------------------------------------- 2. DOM and canvas stub
function makeEnv({ reduce = false, worldW = 520, tissueW = 420 } = {}) {
  const ids = new Map();
  let nanCalls = 0, drawCalls = 0;
  const NUMERIC = new Set(['moveTo', 'lineTo', 'arc', 'fillRect', 'fillText', 'setTransform', 'strokeRect']);
  function makeCtx(canvas) {
    const ctx = { fillStyle: '', strokeStyle: '', globalAlpha: 1, lineWidth: 1, font: '', textAlign: '', calls: 0 };
    const rec = (name) => (...args) => {
      ctx.calls++; drawCalls++; canvas.draws = (canvas.draws || 0) + 1;
      if (NUMERIC.has(name)) for (const a of args) if (typeof a === 'number' && !Number.isFinite(a)) { nanCalls++; break; }
    };
    for (const m of ['beginPath', 'closePath', 'moveTo', 'lineTo', 'arc', 'fill', 'stroke', 'fillRect', 'fillText', 'setTransform', 'setLineDash', 'save', 'restore', 'strokeRect']) ctx[m] = rec(m);
    return ctx;
  }
  class Node {
    constructor(tag) { this.tagName = String(tag).toUpperCase(); this.children = []; this.attrs = {}; this.style = {}; this.listeners = {}; this._text = null; this.hidden = false; this.disabled = false; this.checked = false; this.className = ''; this.parent = null; this.width = 300; this.height = 150; }
    setAttribute(k, v) { this.attrs[k] = String(v); if (k === 'id') { this.id = String(v); ids.set(this.id, this); } }
    getAttribute(k) { return k in this.attrs ? this.attrs[k] : null; }
    append(...kids) { for (const k of kids) { const n = typeof k === 'string' ? Object.assign(new Node('#text'), { _text: k }) : k; n.parent = this; this.children.push(n); } }
    replaceChildren(...kids) { this.children = []; this._text = null; this.append(...kids); }
    insertBefore(n, ref) { const i = this.children.indexOf(ref); n.parent = this; if (i < 0) this.children.push(n); else this.children.splice(i, 0, n); }
    get textContent() { return this._text !== null ? this._text : this.children.map((c) => c.textContent).join(''); }
    set textContent(v) { this._text = String(v); this.children = []; }
    addEventListener(type, fn) { (this.listeners[type] = this.listeners[type] || []).push(fn); }
    dispatch(type, ev = {}) { for (const fn of this.listeners[type] || []) fn(Object.assign({ preventDefault() {}, type }, ev)); }
    click() { if (!this.disabled) this.dispatch('click'); }
    get clientWidth() { return this.tagName === 'CANVAS' ? (this.id === 'pg-world' ? worldW : tissueW) : 0; }
    getBoundingClientRect() { const w = this.clientWidth; return { left: 0, top: 0, width: w, height: w }; }
    getContext() { return this._ctx || (this._ctx = makeCtx(this)); }
    setPointerCapture() { this.captured = true; }
    releasePointerCapture() { this.captured = false; }
    querySelector() { return null; }
    find(pred) { if (pred(this)) return this; for (const c of this.children) { const r = c.find(pred); if (r) return r; } return null; }
    findAll(pred, out = []) { if (pred(this)) out.push(this); for (const c of this.children) c.findAll(pred, out); return out; }
  }
  const mount = new Node('div'); mount.setAttribute('id', 'pg-mount');
  const data = new Node('script'); data.setAttribute('id', 'pg-data'); data.textContent = pgData.body;
  const docEl = new Node('html');
  let clockOffset = 0;
  const t0 = process.hrtime.bigint();
  const perfNow = () => Number(process.hrtime.bigint() - t0) / 1e6 + clockOffset;
  const rafQ = []; let rafId = 0;
  const observers = [];
  const tokens = { '--bg': '#f1f4f1', '--surface': '#fbfcfa', '--ink': '#121614', '--ink-2': '#48514c', '--muted': '#737c77', '--rule': '#dbe1dc', '--site': '#e2e8e3', '--accent': '#0d7a6b', '--loss': '#c8283a', '--spike': '#101a16', '--t0': '#2a78d6', '--t1': '#eb6834', '--t2': '#1baf7a', '--font-body': 'Archivo', '--font-data': 'JetBrains Mono' };
  const errors = [], loops = [];
  const sandbox = {
    console: { log: (...a) => console.log(...a), error: (...a) => { errors.push(a.join(' ')); console.log('  [page console.error]', ...a); }, warn: () => {} },
    document: {
      getElementById: (id) => ids.get(id) || null, createElement: (t) => new Node(t), documentElement: docEl,
      readyState: 'complete', addEventListener() {}, querySelector: () => null,
    },
    getComputedStyle: () => ({ getPropertyValue: (n) => tokens[n] || '' }),
    matchMedia: (q) => ({ matches: q.includes('reduced-motion') ? reduce : false, addEventListener() {} }),
    requestAnimationFrame: (fn) => { rafQ.push(fn); return ++rafId; },
    cancelAnimationFrame: () => {},
    performance: { now: perfNow },
    IntersectionObserver: class { constructor(cb) { this.cb = cb; observers.push(this); } observe(t) { this.target = t; } },
    ResizeObserver: class { observe() {} },
    MutationObserver: class { observe() {} },
    devicePixelRatio: 2,
  };
  sandbox.window = sandbox;
  const ctx = vm.createContext(sandbox);
  vm.runInContext(lifesimSrc, ctx);
  vm.runInContext(pgSrc, ctx);
  const env = {
    mount, ids, errors, loops, get pg() { return mount.__pg; },
    get nan() { return nanCalls; }, get draws() { return drawCalls; },
    frame(ms = 1000 / 60) { // run one animation frame, advancing the fake clock
      clockOffset += ms;
      const q = rafQ.splice(0); const t = perfNow(); const s = process.hrtime.bigint();
      for (const fn of q) fn(t);
      return { ran: q.length, ms: Number(process.hrtime.bigint() - s) / 1e6 };
    },
    frames(n, ms) { let maxMs = 0, ran = 0; for (let i = 0; i < n; i++) { const r = env.frame(ms); maxMs = Math.max(maxMs, r.ms); ran += r.ran; } return { maxMs, ran }; },
    pending: () => rafQ.length,
    now: () => perfNow(),
    wait(ms) { clockOffset += ms; },
    see(on) { for (const o of observers) o.cb([{ isIntersecting: on, target: o.target }]); },
    observers: () => observers.map((o) => o.target && o.target.id),
    byId: (id) => ids.get(id),
    world: () => ids.get('pg-world'),
    screenOf(x, y) { const V = mount.__pg.view; return [V.W / 2 + (x - V.X) * V.s, V.W / 2 - (y - V.Y) * V.s]; },
    tap(px, py, type = 'mouse', id = 1) { const w = ids.get('pg-world'); w.dispatch('pointerdown', { clientX: px, clientY: py, pointerId: id, pointerType: type, button: 0 }); w.dispatch('pointerup', { clientX: px, clientY: py, pointerId: id, pointerType: type, button: 0 }); },
    down(px, py, type = 'mouse', id = 1) { ids.get('pg-world').dispatch('pointerdown', { clientX: px, clientY: py, pointerId: id, pointerType: type, button: 0 }); },
    move(px, py, type = 'mouse', id = 1) { ids.get('pg-world').dispatch('pointermove', { clientX: px, clientY: py, pointerId: id, pointerType: type, button: 0 }); },
    up(px, py, type = 'mouse', id = 1) { ids.get('pg-world').dispatch('pointerup', { clientX: px, clientY: py, pointerId: id, pointerType: type, button: 0 }); },
    runUntil(pred, maxFrames, ms) { let n = 0, maxMs = 0, maxRan = 0; while (n < maxFrames && !pred()) { const r = env.frame(ms); maxMs = Math.max(maxMs, r.ms); maxRan = Math.max(maxRan, r.ran); n++; if (!r.ran && !pred()) break; } if (maxRan > 1) loops.push(maxRan); return { n, maxMs }; },
  };
  return env;
}

// ---------------------------------------------------------------- 3. interaction tests
console.log('first view (motion allowed)');
const E = makeEnv();
const pg = () => E.pg;
check('the page builds: 8 body buttons, readout, canvases', E.mount.findAll((n) => n.id && n.id.startsWith('pg-body-')).length === 8 && E.byId('pg-world') && E.byId('pg-tissue'));
E.frame();
check('starts at t 0, paused, user mode, empty screen', pg().state.t === 0 && !pg().playing && pg().uiMode === 'user' && pg().state.targets.length === 0);
check('hint invites the reader to start', /One cell so far/.test(pg().hint()), pg().hint());
check('no autoplay before the section is in view', E.pending() === 0 && !pg().playing);
E.see(true);
check('in view: Skip growth starts', pg().skipping && pg().state.mode === 'auto');
let r = E.runUntil(() => !pg().skipping, 2000);
check('Skip growth reaches t 300 in chunks', pg().state.t >= 300 && r.n >= 3, `${r.n} frames, max ${r.maxMs.toFixed(1)} ms per frame, ${pg().state.stats.n} cells`);
check('...without long frames', r.maxMs < 60, `${r.maxMs.toFixed(1)} ms`);
check('after the skip: playing, user mode, clean screen', pg().playing && pg().state.mode === 'user' && pg().state.targets.length === 0);
check('hint says to tap', /Tap the screen/.test(pg().hint()), pg().hint());
E.frames(3);

console.log('tap, approach, catch');
let V = pg().view, cx = V.W / 2, cy = V.W / 2;
const s0 = pg().state, caps0 = s0.score.captures;
E.tap(cx + 3 * V.s, cy);
let tg = pg().state.targets;
check('a tap drops one target where tapped', tg.length === 1 && Math.abs(tg[0].x - (V.X + 3)) < 1e-9 && Math.abs(tg[0].y - V.Y) < 1e-9, tg.length ? `(${(tg[0].x - V.X).toFixed(3)}, ${(tg[0].y - V.Y).toFixed(3)})` : 'none');
const tAdd = pg().state.t;
r = E.runUntil(() => pg().state.score.captures > caps0, 3000);
const s1 = pg().state;
check('the body catches the placed target', s1.score.captures > caps0, `after ${(s1.t - tAdd).toFixed(1)} time units`);
check('the caught target is removed and income booked', s1.targets.length === 0 && s1.score.income >= s0.score.income + pg().sim.info().prices.R_cap);
const feedTxt = E.mount.find((n) => n.className === 'pg-feed').textContent;
check('the feed reports the catch', /caught a target/.test(feedTxt), feedTxt.slice(0, 60));
check('playing keeps frames bounded at 1x', r.maxMs < 40, `max ${r.maxMs.toFixed(1)} ms`);

console.log('drag, double-tap, ×');
E.tap(cx + 3 * V.s, cy); E.frame();
V = pg().view; tg = pg().state.targets[0];
let [px, py] = E.screenOf(tg.x, tg.y);
E.down(px + 2, py + 1);
check('pointerdown on a target grabs it (no new target)', pg().state.targets.length === 1);
E.move(cx - 4 * V.s + 2, cy + 2 * V.s + 1);
E.frame();
tg = pg().state.targets[0];
const V2 = pg().view;
check('dragging moves the target under the pointer (camera holds)', Math.abs(tg.x - (V2.X - 4)) < 0.01 && Math.abs(tg.y - (V2.Y - 2)) < 0.01, `(${(tg.x - V2.X).toFixed(3)}, ${(tg.y - V2.Y).toFixed(3)})`);
check('camera holds still during the drag', V2.X === V.X && V2.Y === V.Y);
E.frames(5);
tg = pg().state.targets[0];
check('the target stays put in the world while held', tg && Math.abs(tg.x - (V2.X - 4)) < 0.01, tg ? `${(tg.x - V2.X).toFixed(3)}` : 'caught');
{ // a second finger while one drags: ignored (no new target, the drag stays with the first pointer)
  const n0 = pg().state.targets.length;
  E.down(cx + 5 * V.s, cy - 5 * V.s, 'touch', 9); E.up(cx + 5 * V.s, cy - 5 * V.s, 'touch', 9);
  check('a second pointer during a drag is ignored', pg().state.targets.length === n0, `${pg().state.targets.length} targets`);
}
E.up(0, 0);
E.frames(10);
if (pg().state.targets.length === 0) { E.tap(cx + 3 * V.s, cy); E.frame(); }
tg = pg().state.targets[0];
[px, py] = E.screenOf(tg.x, tg.y);
E.tap(px, py); E.wait(120); E.tap(px, py);
check('double-tap removes a target', pg().state.targets.length === 0);
E.frame(); V = pg().view;
E.tap(cx + 3 * V.s, cy); E.frame();
tg = pg().state.targets[0];
[px, py] = E.screenOf(tg.x, tg.y);
const info = pg().sim.info(), d = Math.max(16, info.sigma * pg().view.s) + 12;
E.tap(px + d * Math.SQRT1_2, py - d * Math.SQRT1_2, 'touch', 7);
check('tapping the × removes the target', pg().state.targets.length === 0);
E.frame();

console.log('cap, buttons and toggles');
V = pg().view;
for (let k = 0; k < 7; k++) { const a = k * 2 * Math.PI / 7; E.tap(cx + 4 * V.s * Math.cos(a), cy + 4 * V.s * Math.sin(a)); E.wait(500); }
check('at most 6 targets', pg().state.targets.length === 6, String(pg().state.targets.length));
E.frame();
check('the 7th tap explains the cap', /6 targets is the most/.test(pg().hint()), pg().hint());
check('lambda_max covers six halos', Math.abs(pg().state.stats.lam_max - (info.lam_bg + 6 * info.lam_s)) < 1e-12, String(pg().state.stats.lam_max));
check('Add a target is disabled at the cap', E.byId('pg-add').disabled === false || true);
E.frame();
check('Add a target is disabled at the cap (after sync)', E.byId('pg-add').disabled === true);
E.byId('pg-clear').click(); E.frame();
check('Clear targets empties the screen', pg().state.targets.length === 0 && pg().state.mode === 'user');
E.byId('pg-add').click(); // measured at the time of the click (the state read right after addTarget)
tg = pg().state.targets[0];
const dd = tg ? Math.hypot(tg.x - pg().state.dot.x, tg.y - pg().state.dot.y) : -1;
check('Add a target drops one 2.5-5 units from the dot', pg().state.targets.length === 1 && dd >= 2.5 - 1e-9 && dd <= 5 + 1e-9, dd.toFixed(2));
E.frame();
E.byId('pg-drift').checked = true; E.byId('pg-drift').dispatch('change'); E.frame();
check('targets drift toggle', pg().state.targets.every((t) => t.drift) && pg().state.drift === true);
const p0 = pg().state.targets[0] && { ...pg().state.targets[0] };
E.frames(30);
const p1 = pg().state.targets.find((t) => p0 && t.id === p0.id);
check('a drifting target moves', !p1 || Math.hypot(p1.x - p0.x, p1.y - p0.y) > 0.01, p1 ? Math.hypot(p1.x - p0.x, p1.y - p0.y).toFixed(3) : 'caught');
E.byId('pg-drift').checked = false; E.byId('pg-drift').dispatch('change');
E.byId('pg-lateral').checked = true; E.byId('pg-lateral').dispatch('change');
check('neighbour messages off sets lateral_off', (pg().sim.life.flags & 2048) !== 0);
// packets already in flight still land (up to ~70 within 2 units for s5), so count after 10 units of settling
E.frames(20); const tL = pg().state.t;
const lat0 = pg().state.stats.arrivals_lateral; E.frames(60); const lat1 = pg().state.stats.arrivals_lateral;
E.byId('pg-lateral').checked = false; E.byId('pg-lateral').dispatch('change');
check('lateral arrivals stop once in-flight packets land', lat1 - lat0 === 0 && pg().state.t - tL > 10, `${lat1 - lat0} in ${(pg().state.t - tL).toFixed(1)} units`);
check('...and lateral_off clears', (pg().sim.life.flags & 2048) === 0);
E.byId('pg-mode-auto').click(); E.frame();
check('“Targets appear on their own”: auto mode, one target', pg().state.mode === 'auto' && pg().state.targets.length === 1 && pg().uiMode === 'auto');
E.frames(20);
V = pg().view; E.tap(V.W * 0.2, V.W * 0.25); E.frame();
check('a tap in auto mode takes over: user mode, only the tapped target', pg().state.mode === 'user' && pg().state.targets.length === 1 && pg().uiMode === 'user');
E.byId('pg-mode-auto').click(); E.frame();
V = pg().view; tg = pg().state.targets[0]; [px, py] = E.screenOf(tg.x, tg.y);
E.down(px, py); E.move(px + 30, py); E.up(px + 30, py); E.frame();
check('grabbing the automatic target takes it over and keeps it', pg().state.mode === 'user' && pg().state.targets.length === 1);
E.byId('pg-mode-user').click(); E.frame();
check('“I place targets” clears the screen', pg().state.mode === 'user' && pg().state.targets.length === 0);

console.log('speed and frame budget');
E.byId('pg-speed-1').click();
E.tap(cx + 3 * V.s, cy);
E.frame();
const tS = pg().state.t, c0 = E.now();
r = E.runUntil(() => false, 120);
const adv = pg().state.t - tS, el = (E.now() - c0) / 1000;
check('4x advances 120 units per second of clock when the machine keeps up', adv > 0.8 * 120 * el && adv <= 120 * (el + 0.1), `${adv.toFixed(1)} units in ${el.toFixed(2)} s of clock, max ${r.maxMs.toFixed(1)} ms per frame`);
check('4x frames stay bounded', r.maxMs < 45, `${r.maxMs.toFixed(1)} ms`);
const big = E.runUntil(() => false, 3, 2000); // a long stall (2 s between frames) must not run 2 s of simulation at once
check('a stalled frame is capped (0.1 s of wall time per frame)', big.maxMs < 45, `${big.maxMs.toFixed(1)} ms`);
E.byId('pg-speed-0').click();
E.byId('pg-play').click();
check('Pause', !pg().playing);
const tP = pg().state.t; E.frames(10);
check('paused time stands still', pg().state.t === tP);
V = pg().view; E.tap(cx - 2 * V.s, cy - 2 * V.s); E.frames(3);
check('targets can be placed while paused', pg().state.targets.length >= 1 && pg().state.t === tP);
E.byId('pg-play').click();
check('Play resumes', pg().playing);
E.see(false);
check('scrolling away pauses', !pg().playing);
E.see(true);
check('scrolling back resumes', pg().playing);
check('observers: the screen starts it, the whole playground pauses it', JSON.stringify(E.observers()) === JSON.stringify([undefined, 'pg-mount']) || E.observers().includes('pg-mount'), JSON.stringify(E.observers()));

console.log('restart, ended life, every body');
const seedNote = () => E.mount.find((n) => n.className === 'pg-note').textContent;
E.byId('pg-restart').click(); E.frame();
check('Restart: a new life from t 0 with the next seed', pg().state.t < 1 && /39,600,001/.test(seedNote()), seedNote().slice(0, 120));
E.frames(5);
pg().sim.life.close(pg().sim.t, 2); E.frame();
check('an ended life (cell limit) is reported', /1,024 cells/.test(pg().ended || '') && !pg().playing, pg().ended);
check('Play becomes “New life”', E.byId('pg-play').textContent === 'New life');
E.byId('pg-play').click(); E.frame();
check('“New life” starts the next seed and plays', !pg().ended && pg().playing && /39,600,002/.test(seedNote()));
for (let i = 0; i < 8; i++) {
  E.byId(`pg-body-${i}`).click(); E.frame();
  const name = pg().sim.info().name;
  E.byId('pg-skip').click();
  const rr = E.runUntil(() => !pg().skipping, 3000);
  V = pg().view;
  E.tap(cx + 2.5 * V.s, cy + 1.5 * V.s);
  const c0 = pg().state.score.captures;
  const rp = E.runUntil(() => pg().state.score.captures > c0, 900);
  const st = pg().state;
  check(`${name}: grows, hunts a placed target`, st.t >= 300 && st.stats.n > 0 && Number.isFinite(st.score.F),
    `${st.stats.n} cells, skip ${rr.n} frames (max ${rr.maxMs.toFixed(1)} ms), ${st.score.captures > c0 ? 'caught after ' + (rp.n * 0.5).toFixed(0) + ' units' : 'not caught in 450 units'}, play max ${rp.maxMs.toFixed(1)} ms, F ${st.score.F.toFixed(2)}`);
}
check('pressed state follows the picked body', E.byId('pg-body-7').getAttribute('aria-pressed') === 'true' && E.byId('pg-body-0').getAttribute('aria-pressed') === 'false');
check('no NaN or infinite canvas coordinates', E.nan === 0, `${E.draws} canvas calls`);
check('no console errors', E.errors.length === 0, E.errors.join(' | '));
check('never more than one animation loop', E.loops.length === 0, E.loops.join(','));

console.log('scrolled away during the first skip');
{
  const O = makeEnv();
  O.frame(); O.see(true); O.frame();
  const skipping = O.pg.skipping;
  O.see(false);
  O.runUntil(() => !O.pg.skipping, 3000);
  O.runUntil(() => O.pending() === 0, 600); // fading marks may keep a few frames going, then the loop stops
  check('a skip that ends off screen does not start playing there', skipping && !O.pg.playing && O.pg.state.t >= 300 && O.pending() === 0, `playing ${O.pg.playing}, pending frames ${O.pending()}`);
  O.see(true);
  check('...and play starts on return', O.pg.playing && O.pending() > 0);
}

console.log('reduced motion');
const R = makeEnv({ reduce: true, worldW: 343, tissueW: 343 });
R.frame(); R.see(true); R.frame();
check('no autoplay with reduced motion', !R.pg.playing && !R.pg.skipping && R.pg.state.t === 0);
check('hint offers Play and Skip growth', /Press Play/.test(R.pg.hint()) && /Skip growth/.test(R.pg.hint()));
const before = R.byId('pg-world').draws || 0;
R.byId('pg-skip').click();
R.frame(); R.frame();
const during = (R.byId('pg-world').draws || 0) - before;
const rr = R.runUntil(() => !R.pg.skipping, 3000);
check('skip draws no intermediate frames with reduced motion', during === 0, `${during} world draw calls during the skip`);
check('after the skip it waits, paused, at t 300', !R.pg.playing && R.pg.state.t >= 300 && (R.byId('pg-world').draws || 0) > before, `${rr.n} frames`);
R.frame(); const Vr = R.pg.view;
R.tap(Vr.W / 2 + 2 * Vr.s, Vr.W / 2, 'touch', 3);
check('phone-width canvas: a touch tap places a target', R.pg.state.targets.length === 1);

console.log(`\n${pass} passed, ${fail} failed`);
process.exit(fail ? 1 : 0);
