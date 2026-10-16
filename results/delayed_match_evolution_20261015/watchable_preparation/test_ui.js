/* Supplied-state UI smoke. This file never imports the simulator or advances a physical life. */
'use strict';
const fs = require('fs'), vm = require('vm'), path = require('path'), assert = require('assert/strict');
const here = __dirname, created = [];
let document;
class Element {
  constructor(tag) { this.tagName = tag; this.children = []; this.style = {}; this.listeners = {}; this.value = ''; }
  get ownerDocument() { return document; }
  append(...items) {
    this.children.push(...items);
    if (this.tagName === 'select' && this.value === '' && items.length) this.value = items[0].value;
  }
  replaceChildren(...items) { this.children = items; }
  setAttribute() {}
  addEventListener(name, callback) { this.listeners[name] = callback; }
  getContext() { return new Proxy({}, { get: (_, key) => key === 'createRadialGradient' ?
    () => ({ addColorStop() {} }) : () => {} }); }
}
const roles = ['AO_start', 'mixed8', 'mixed24'], seeds = [52460000, 52460001, 52460002, 52460003];
const data = { roles, seeds, bodies: roles.map(role => ({ role, genotype_sha256: '0'.repeat(64) })),
  recorded: roles.flatMap(role => seeds.map(seed => ({ role, seed, native_F: 1, production_F: .9,
    extinct_charge: .1, status: 0 }))) };
const nodes = Object.fromEntries(['comparison-data', 'role', 'seed', 'viewer', 'recorded', 'genome', 'error']
  .map(id => [id, new Element(id === 'role' || id === 'seed' ? 'select' : 'div')]));
nodes['comparison-data'].textContent = JSON.stringify(data);
document = { createElement: tag => new Element(tag), getElementById: id => nodes[id] };
const ledger = {};
for (const cls of ['narrow', 'broad']) for (const name of ['choice_opportunities', 'choice_carry_in',
  'correct_choices', 'wrong_choices', 'choice_timeouts', 'unfinished_choices']) ledger[name + '_' + cls] = 0;
const LifeSim = { create: (_, opts) => {
  created.push(opts);
  return { state: () => ({ t: 0, ended: false, task: { phase: 'SAMPLE', sample_class: 'narrow', trial: 0, remaining: 15 },
    score: { correct_choices: 0, wrong_choices: 0, slot_hits: { narrow: 0, broad: 0 }, misses: 0,
      income: 0, cost: 0, F: 0 }, targets: [], cells: [], events: [], dot: { x: 0, y: 0 } }),
    info: () => ({ R_max: 4, b2_sigma: 1.2, task_mode: 1 }), ledger: () => ledger };
} };
const context = vm.createContext({ document, LifeSim, requestAnimationFrame: () => 1, cancelAnimationFrame() {} });
vm.runInContext(fs.readFileSync(path.join(here, 'delayed_match_view.js'), 'utf8'), context);
vm.runInContext(fs.readFileSync(path.join(here, 'viewer.js'), 'utf8'), context);
const flatten = node => [node, ...node.children.flatMap(flatten)];
assert.equal(nodes.role.children.length, 3); assert.equal(nodes.seed.children.length, 4);
const texts = flatten(nodes.viewer).map(node => node.textContent).filter(Boolean);
for (const label of ['Opportunities', 'Correct', 'Wrong', 'Narrow hits', 'Broad hits']) assert(texts.includes(label));
assert(!texts.some(text => text.includes('Next seed')));
assert(texts.some(text => text.includes('native F')));
for (let body = 0; body < 3; body++) for (const seed of seeds) {
  nodes.role.value = String(body); nodes.seed.value = String(seed); nodes.role.listeners.change();
  assert.equal(nodes.error.textContent, '');
  assert.equal(created.at(-1).body, body); assert.equal(created.at(-1).seed, seed);
  assert.equal(created.at(-1).mode, 'auto');
}
console.log(JSON.stringify({ status: 'passed', supplied_state_mounts: created.length,
  actual_simulator_calls: 0, builds: 0, random_draws: 0, real_browser_tested: false }));
