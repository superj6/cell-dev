#!/usr/bin/env node
/* Supplied-state DOM/canvas smoke only: no engine import, simulator, build or random draw. */
'use strict';
const assert = require('assert/strict'), fs = require('fs'), vm = require('vm'), path = require('path');
const draws = [], made = [];
const ctx = new Proxy({}, { get: (target, key) => key === 'createRadialGradient' ?
  () => ({ addColorStop() {} }) : (...args) => draws.push([key, ...args]),
set: (target, key, value) => { target[key] = value; return true; } });
class Element {
  constructor(tag) {
    this.tagName = tag; this.children = []; this.textContent = ''; this.style = {}; this.listeners = {};
    this.attrs = {}; this.ownerDocument = document;
  }
  append(...nodes) { this.children.push(...nodes); }
  replaceChildren(...nodes) { this.children = nodes; }
  setAttribute(key, value) { this.attrs[key] = value; }
  addEventListener(key, fn) { this.listeners[key] = fn; }
  getContext() { return ctx; }
  click() { return this.listeners.click(); }
}
const document = { createElement: tag => new Element(tag) }, frames = new Map(); let frameId = 0;
const patches = [0,1,2].map(i => ({ id:i,slot:i,x:i*3,y:0,stock:i,capacity:2,period:i?160:80,
  next:80,sigma:.6,amplitude:.1+.9*i/2,capture_radius:1,initial_remaining:i }));
const ledger = { patch_geometric_misses: 2 };
for (let i=0; i<4; i++) for (const stem of ['source','supply','spill','harvest','initial_harvest','refill_harvest','empty'])
  ledger['patch_'+stem+'_'+i] = i < 3 ? ({ source:3,supply:2,spill:1,harvest:2,initial_harvest:1,
    refill_harvest:1,empty:1 })[stem] : 0;
const LifeSim = { create: (_, opts) => {
  const sim = { t:0,ended:false,opts,advance(dt) { this.t+=dt; },
    state() { return { t:this.t,ended:false,patches:JSON.parse(JSON.stringify(patches)),dot:{x:0,y:0},
      cells:[{x:0,y:0,z:0,lastSpike:-100}],events:[],score:{income:3000,cost:100,F:2.9} }; },
    info() { return { patch_count:3,R_max:4,sigma:.6 }; },ledger() { return ledger; } };
  made.push(sim); return sim;
} };
const scope = vm.createContext({ document,LifeSim,
  requestAnimationFrame: fn => { frames.set(++frameId,fn); return frameId; },
  cancelAnimationFrame: id => frames.delete(id) });
vm.runInContext(fs.readFileSync(path.join(__dirname,'resource_patches_view.js'),'utf8'),scope);
const mount = new Element('main'), View = scope.ResourcePatchesView;
assert.throws(() => View.mount(mount,{}),/fixed safe-integer seed/);
const viewer = View.mount(mount,{}, {seed:42000000});
const [title,note,controls,status,canvas,score,table] = mount.children;
assert.match(title.textContent,/Persistent food/); assert.match(note.textContent,/observer/);
assert.match(note.textContent,/only local receptor/); assert.match(status.textContent,/42000000/);
assert.match(score.textContent,/6 \(3 initial, 3 replenished\)/); assert.match(score.textContent,/geometric misses 2/);
assert.match(score.textContent,/native F/); assert.equal(controls.children.length,2);
assert.deepEqual(Object.keys(canvas.listeners),[]); assert.equal(table.children[2].children.length,3);
assert.ok(draws.some(row=>row[0]==='arc')); assert.equal(made[0].opts.mode,'auto');
assert.equal(made[0].opts.abi,6);
controls.children[0].click();
for (const now of [1000,1100]) { const [id,fn]=frames.entries().next().value; frames.delete(id); fn(now); }
assert.ok(viewer.simulator.t>0); controls.children[1].click();
assert.equal(made.length,2); assert.equal(viewer.simulator.opts.seed,42000000);
viewer.destroy(); assert.equal(mount.children.length,0); assert.equal(frames.size,0);
console.log(JSON.stringify({status:'passed',supplied_state_mounts:made.length,actual_simulator_calls:0,
  builds:0,random_draws:0,real_browser_tested:false}));
