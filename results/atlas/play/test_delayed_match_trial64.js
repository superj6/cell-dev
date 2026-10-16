#!/usr/bin/env node
/* Direct large-trial hash fixture; no life is advanced or seed searched. */
'use strict';
const assert = require('assert/strict');
const fs = require('fs');
const LifeSim = require('./lifesim.js');
const truth = JSON.parse(fs.readFileSync(process.argv[2], 'utf8'));
const item = truth.cases[0], sim = LifeSim.create(item.body, { seed: item.seed, hashes: true }), life = sim.life;
const dv = new DataView(new ArrayBuffer(8));
const bits = x => { dv.setFloat64(0, x, true); return dv.getBigUint64(0, true); };
const mask = (1n << 64n) - 1n;
function sm(x) {
  let z = (x + 0x9e3779b97f4a7c15n) & mask;
  z = ((z ^ (z >> 30n)) * 0xbf58476d1ce4e5b9n) & mask;
  z = ((z ^ (z >> 27n)) * 0x94d049bb133111ebn) & mask;
  return z ^ (z >> 31n);
}
function fold(h, words) { for (const word of words) h = sm(h ^ word); return h.toString(16).padStart(16, '0'); }
life.task_trial = 2 ** 32 + 7;
let before = BigInt('0x' + sim.hashes().world);
life.taskEnter(0, 0);
let words = [15n, bits(0), BigInt(life.task_trial), 0n, BigInt(life.task_class),
  ...life.blobs.flatMap(blob => [bits(blob.x), bits(blob.y)])];
assert.equal(sim.hashes().world, fold(before, words), 'phase record must retain all trial bits');
life.taskEnter(2, 40);
before = BigInt('0x' + sim.hashes().world);
life.taskResolve(41, 2);
words = [16n, bits(41), BigInt(life.task_trial), BigInt(life.task_class), 0n, 2n];
assert.equal(sim.hashes().world, fold(before, words), 'resolution record must retain all trial bits');
life.taskEnter(3, 41);
before = BigInt('0x' + sim.hashes().world);
life.close(42, 0);
words = [17n, bits(42), BigInt(life.task_trial), 3n, BigInt(life.task_class)];
assert.equal(sim.hashes().world, fold(before, words), 'terminal record must retain all trial bits');
console.log('ABI5 full-width trial hashes passed; one constructed direct-world fixture, zero advanced lives');
