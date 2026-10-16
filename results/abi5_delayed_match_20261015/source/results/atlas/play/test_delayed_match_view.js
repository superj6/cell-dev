#!/usr/bin/env node
/* DOM/canvas stub smoke; this does not claim real-browser or visual rendering validation. */
'use strict';
const assert = require('assert/strict');
const fs = require('fs');
const vm = require('vm');
const path = require('path');
const View = require('./delayed_match_view.js');
const fixturePath = process.argv[2];
if (!fixturePath) throw new Error('pass the fixed truth.json path');
const truth = JSON.parse(fs.readFileSync(fixturePath, 'utf8'));
assert.equal(truth.status, 'complete');
const item = truth.cases[0];
const drawings = [];
const context = new Proxy({}, { get: (target, key) => {
  if (key === 'createRadialGradient') return () => ({ addColorStop: () => {} });
  return (...args) => drawings.push([key, ...args]);
}, set: (target, key, value) => { target[key] = value; return true; } });
class Element {
  constructor(tag) { this.tagName = tag; this.children = []; this.textContent = ''; this.style = {}; this.listeners = {}; this.attrs = {}; this.ownerDocument = document; }
  append(...children) { this.children.push(...children); }
  replaceChildren(...children) { this.children = children; }
  setAttribute(key, value) { this.attrs[key] = value; }
  addEventListener(kind, handler) { this.listeners[kind] = handler; }
  getContext() { return context; }
  click() { return this.listeners.click(); }
}
const document = { createElement: tag => new Element(tag) };
let id = 0;
const frames = new Map();
global.requestAnimationFrame = callback => { frames.set(++id, callback); return id; };
global.cancelAnimationFrame = frame => frames.delete(frame);
const frame = now => { const [key, callback] = frames.entries().next().value; frames.delete(key); callback(now); };
const mount = new Element('main');
const viewer = View.mount(mount, item.body, { seed: item.seed });
const [title, note, controls, status, canvas, score, table] = mount.children;
assert.match(title.textContent, /Delayed matching/);
assert.match(note.textContent, /only receptor pings/);
assert.match(note.textContent, /observer/);
assert.match(status.textContent, /sample/);
assert.match(score.textContent, /physical narrow-slot hits/);
assert.match(score.textContent, /Correct matches/);
assert.deepEqual(Object.keys(canvas.listeners), [], 'there are no canvas editing handlers');
assert.equal(table.children[2].children.length, 2, 'one row for each earlier sample class');
assert.ok(drawings.some(call => call[0] === 'arc'));
controls.children[0].click(); frame(1000); frame(1100);
assert.ok(viewer.simulator.t > 0, 'play advances the same LifeSim instance');
const life = viewer.simulator.life;
viewer.simulator.advance(life.task_next - viewer.simulator.t + 0.001);
controls.children[0].click();
assert.match(status.textContent, /blank/);
assert.equal(viewer.simulator.state().targets.length, 0);
viewer.simulator.advance(life.task_next - viewer.simulator.t + 0.001);
controls.children[0].click();
assert.match(status.textContent, /choice/);
assert.deepEqual(viewer.simulator.state().targets.map(target => target.shape), ['narrow', 'broad']);
controls.children[1].click(); assert.equal(viewer.simulator.life.seed, item.seed);
controls.children[2].click(); assert.equal(viewer.simulator.life.seed, item.seed + 1);
viewer.destroy(); assert.equal(mount.children.length, 0); assert.equal(frames.size, 0);
const html = fs.readFileSync(path.join(__dirname, 'delayed_match.html'), 'utf8');
for (const match of html.matchAll(/<script[^>]*>([\s\S]*?)<\/script>/g)) new vm.Script(match[1]);
console.log('Automatic viewer DOM/canvas stub smoke passed; 3 partial JS lives, no real-browser claim');
