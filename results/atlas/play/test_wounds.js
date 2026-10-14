#!/usr/bin/env node
/* ABI-3 wound parity, including unchanged lives, boundary times, growing and fully formed bodies.
 * The committed truth fixture is independently checked C = Python by export_wounds.py.
 * Run: node results/atlas/play/test_wounds.js
 */
'use strict';
const assert = require('assert');
const doc = require('./bodies.json');
const truth = require('./truth_wounds.json');
const LifeSim = require('./lifesim.js');
const dv = new DataView(new ArrayBuffer(8));
function bits(x) { dv.setFloat64(0, Number(x), true); return dv.getBigUint64(0, true); }
function uid(c) { return c.uh.toString(16).padStart(8, '0') + c.ul.toString(16).padStart(8, '0'); }
let regrowth = 0, refills = 0, stale = 0;
for (const fixture of truth.cases) {
  const source = typeof fixture.body === 'number' ? doc.bodies[fixture.body] : fixture.body;
  const body = { ...source, world: { ...source.world, ...fixture.world } };
  for (const stepped of [false, true]) {
    const sim = LifeSim.create({ ...doc, bodies: [body] }, { body: 0, seed: fixture.seed,
      hashes: true, raster: truth.raster_cap });
    if (stepped) {
      let calls = 0;
      while (!sim.ended) { sim.advance(0.37, 40); if (++calls % 97 === 0) sim.state(); }
    } else sim.run();
    const where = `${fixture.name} (${stepped ? 'stepped' : 'whole'})`;
    const ledger = sim.ledger();
    LifeSim.LEDGER.forEach((name, i) => assert.strictEqual(bits(ledger[name]), bits(fixture.ledger[i]), `${where}: ${name}`));
    assert.deepStrictEqual(Object.values(sim.hashes()), fixture.hashes, `${where}: hashes`);
    const raster = sim.raster();
    assert.deepStrictEqual(raster.t.map(bits), fixture.raster_t.map(bits), `${where}: raster times`);
    assert.deepStrictEqual(raster.uid, fixture.raster_uid, `${where}: raster uids`);
    assert.strictEqual(raster.n, fixture.raster_total, `${where}: total spikes`);
    const deaths = sim.life.cells.filter(c => !c.alive).map(c => [bits(c.t_death), uid(c)]);
    const expected = fixture.deaths.map(d => [bits(d[0]), d[1]]);
    const sort = (a, b) => a[1].localeCompare(b[1]);
    assert.deepStrictEqual(deaths.sort(sort), expected.sort(sort), `${where}: dead cells and exact death times`);
  }
  regrowth += fixture.coverage.births_after_wound;
  refills += fixture.coverage.refills;
  stale += fixture.coverage.deaths_before_wound;
}
assert(regrowth > 0 && refills > 0 && stale > 0, 'truth must exercise regrowth, refills and stale wound events');
console.log(`wounds: ${truth.cases.length} lives match C and Python bitwise, with whole and capped stepping`);
