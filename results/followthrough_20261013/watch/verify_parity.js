'use strict';
const fs = require('fs'), path = require('path'), vm = require('vm'), assert = require('assert');
const html = fs.readFileSync(path.join(__dirname, 'watch.html'), 'utf8');
const engine = [...html.matchAll(/<script>([\s\S]*?)<\/script>/g)][0][1];
const context = {console}; vm.runInNewContext(engine, context);
const data = JSON.parse(fs.readFileSync(path.join(__dirname, 'bodies.json'), 'utf8'));
const truth = JSON.parse(fs.readFileSync(path.join(__dirname, 'truth_T32.json'), 'utf8'));
const bits = value => {const b = Buffer.alloc(8); b.writeDoubleLE(value); return b.toString('hex');};
const cases = [];
for (const expected of truth) {
 const body = data.bodies.find(item => item.name === expected.body);
 const sim = context.LifeSim.create({...body, world:{...data.worlds[expected.world], T:expected.T}},
  {seed:expected.seed, T:expected.T, mode:'auto', hashes:true});
 while (!sim.ended) {sim.advance(0.5, 1200); sim.state();}
 const got = sim.ledger(), hashes = sim.hashes();
 for (const [key, value] of Object.entries(expected.ledger)) {
  assert.strictEqual(bits(got[key]), bits(Number(value)), expected.world + '/' + body.name + '/' + key);
 }
 for (const [key, value] of Object.entries(expected.hashes)) {
  assert.strictEqual(hashes[key], value, expected.world + '/' + body.name + '/' + key);
 }
 cases.push({world:expected.world, body:body.name, seed:expected.seed, T:expected.T,
  ledger_columns:Object.keys(got).length, matching_hashes:Object.keys(hashes).length});
}
console.log(JSON.stringify({status:'passed', comparison:'bitwise', stepped_and_state_read:true, cases}, null, 2));
