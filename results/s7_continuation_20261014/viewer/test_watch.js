/* Syntax and interaction checks use a synthetic simulator, without running scientific lives. */
'use strict';
const fs = require('fs'), path = require('path'), vm = require('vm'), assert = require('assert');
const crypto = require('crypto');
const root = __dirname, local = path.join(root, 'watch.html');
const html = fs.readFileSync(fs.existsSync(local) ? local : path.join(root, '../watch.html'), 'utf8');
const source = [...html.matchAll(/<script>([\s\S]*?)<\/script>/g)].map(match => match[1]);
assert.strictEqual(source.length, 2);
source.forEach(script => new vm.Script(script));
const data = JSON.parse(html.match(/id="watch-data">([\s\S]*?)<\/script>/)[1]);
assert.strictEqual(crypto.createHash('sha256').update(source[0]).digest('hex'), data.engine_sha256);
assert.strictEqual(data.bodies.length, 4);
const elements = new Map(), callbacks = new Map(), created = [];
let serial = 0, draws = 0, now = 0;
const ctx = new Proxy({}, {get(target, key) {
 if (key in target) return target[key];
 return (...args) => {draws++; for (const value of args) {
  if (typeof value === 'number') assert(Number.isFinite(value), 'non-finite canvas coordinate');
 }};
}});
function element(id) {
 if (!elements.has(id)) elements.set(id, {id, value:'', textContent:'', innerHTML:'', clientWidth:520,
  listeners:{}, addEventListener(name, action) {this.listeners[name] = action;},
  getContext() {return ctx;}, click() {this.listeners.click?.({});},
  dispatch(name, event = {}) {this.listeners[name]?.(event);}});
 return elements.get(id);
}
for (const [id, value] of Object.entries({seed:'51840000', world:'pool', speed:'30',
 left:'founder_row29', right:'s51891_final_rank0'})) element(id).value = value;
element('watch-data').textContent = JSON.stringify(data);
const document = {hidden:false, getElementById:element, listeners:{},
 addEventListener(name, action) {this.listeners[name] = action;}};
const window = {devicePixelRatio:1, addEventListener() {}};
function simulator(body, options) {
 let t = 0;
 const cell = {id:0,z:0,x:0,y:0,born:0,lastSpike:-Infinity};
 const sim = {body, options, get t(){return t;}, get ended(){return t >= 1024;},
  advance(delta) {t = Math.min(1024, t + delta);},
  info() {return {sigma:body.world.sigma,rho_c:body.world.rho_c};},
  ledger() {return {status:0,t_ext:-1};},
  state() {return {t,ended:this.ended,dot:{x:t/100,y:0},targets:[{x:3,y:0}],cells:[cell],events:[],
   score:{captures:Math.floor(t/10),clicks:Math.floor(t/5),misses:Math.floor(t/10),income:t*3,cost:t,F:2},
   stats:{n:1,spikes:Math.floor(t)}};}};
 created.push(sim); return sim;
}
const context = {document, window, console, LifeSim:{create:simulator},
 performance:{now:() => (now += 0.2)}, requestAnimationFrame(fn) {callbacks.set(++serial, fn); return serial;},
 cancelAnimationFrame(id) {callbacks.delete(id);}};
vm.runInNewContext(source[1], context);
function frame() {
 const pending = [...callbacks.values()]; callbacks.clear(); now += 16.67;
 assert(pending.length <= 1, 'more than one animation loop'); pending.forEach(fn => fn(now));
}
assert.strictEqual(created.length, 2);
assert.deepStrictEqual(created.map(sim => sim.body.name), data.default_pair);
assert.match(element('evidence').innerHTML, /0\.900/);
assert.match(element('title1').textContent, /51891/);
assert(created.every(sim => sim.options.seed === 51840000 && sim.options.mode === 'auto'));
assert(created.every(sim => sim.body.world.d0 === 0.5 && sim.body.world.sigma === 0.4));
assert.strictEqual(callbacks.size, 0, 'page must initially stay paused');
element('play').click(); frame(); frame(); frame();
assert(window.__watch.sims.every(sim => sim.t > 0));
element('play').click(); const paused = window.__watch.sims.map(sim => sim.t); frame(); frame();
assert.deepStrictEqual(window.__watch.sims.map(sim => sim.t), paused);
element('reset').click(); assert(window.__watch.sims.every(sim => sim.t === 0));
element('seed').value = '-1'; const good = window.__watch.sims;
element('apply').click(); assert.strictEqual(window.__watch.sims, good);
assert.match(element('status').textContent, /nonnegative/);
element('seed').value = ''; element('apply').click(); assert.strictEqual(window.__watch.sims, good);
element('seed').value = '123'; element('seed').dispatch('keydown', {key:'Enter'});
assert(window.__watch.sims.every(sim => sim.options.seed === 123));
element('world').value = 'base'; element('world').dispatch('change');
assert(window.__watch.sims.every(sim => sim.body.world.sigma === data.worlds.base.sigma));
assert.match(element('evidence').textContent, /transfer illustration/);
element('world').value = 'pool'; element('world').dispatch('change');
element('right').value = 's51892_final_rank0'; element('right').dispatch('change');
assert.strictEqual(window.__watch.sims[1].body.name, 's51892_final_rank0');
assert.match(element('evidence').innerHTML, /1\.072/);
assert.strictEqual(callbacks.size, 0, 'changing a genome must pause and restart');
element('left').value = 's51892_final_rank0'; element('left').dispatch('change');
assert.match(element('evidence').textContent, /same genome/);
assert.strictEqual(JSON.stringify(window.__watch.sims.map(sim => sim.body.genome)),
 JSON.stringify([data.bodies[3].genome, data.bodies[3].genome]));
element('right').value = 'founder_row29'; element('right').dispatch('change');
assert.match(element('evidence').innerHTML, /−1\.072/);
element('left').value = 'pilot_s7'; element('left').dispatch('change');
assert.match(element('title0').textContent, /Original s7/);
assert.match(element('evidence').innerHTML, /0\.367/);
const slowStart = window.__watch.sims[0].t;
element('speed').value = '10'; element('play').click(); frame(); frame(); frame();
element('play').click(); frame();
const slowAdvance = window.__watch.sims[0].t - slowStart;
element('speed').value = '120'; element('play').click(); frame(); frame(); frame();
element('play').click(); frame();
assert(window.__watch.sims[0].t - slowStart - slowAdvance > slowAdvance, 'speed control must affect display progress');
element('grow').click(); for (let i = 0; i < 200; i++) frame();
assert(window.__watch.sims.every(sim => sim.t === 200));
assert.strictEqual(callbacks.size, 0);
element('play').click(); document.hidden = true; document.listeners.visibilitychange(); frame();
assert.match(element('status').textContent, /Paused/);
window.__watch.sims.forEach((sim, i) => {sim.advance(1024); window.__watch.states[i] = sim.state();});
window.__watch.draw();
assert.strictEqual(element('play').textContent, 'Replay');
assert.strictEqual(element('flabel0').textContent, 'Final F');
element('play').click(); assert(window.__watch.sims.every(sim => sim.t === 0));
assert(draws > 0);
console.log(JSON.stringify({syntax:'passed', synthetic_interactions:'passed', finite_canvas_calls:draws,
 scientific_lives_run:0, genome_count:data.bodies.length, default_pair:data.default_pair,
 default_seed:data.default_seed, engine_sha256:data.engine_sha256}, null, 2));
