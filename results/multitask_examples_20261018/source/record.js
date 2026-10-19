'use strict';

// Read-only observer: fixed fixture, no seed search, full life, and exact native validation.
const fs = require('fs');
const path = require('path');
const crypto = require('crypto');
const args = process.argv.slice(2);
const options = {};
for (let i = 0; i < args.length; i += 2) {
  if (!args[i].startsWith('--') || !args[i + 1]) throw new Error('expected --name value arguments');
  options[args[i].slice(2)] = args[i + 1];
}
for (const name of ['fixture', 'native', 'sim', 'out']) {
  if (!options[name]) throw new Error(`missing --${name}`);
  options[name] = path.resolve(options[name]);
}
const hash = bytes => crypto.createHash('sha256').update(bytes).digest('hex');
const inputBytes = fs.readFileSync(options.fixture);
const nativeBytes = fs.readFileSync(options.native);
const sourceBytes = fs.readFileSync(options.sim);
const fixture = JSON.parse(inputBytes);
const native = JSON.parse(nativeBytes);
const LifeSim = require(options.sim);
const bind = {fixture_sha256: hash(inputBytes), native_sha256: hash(nativeBytes),
  simulator_sha256: hash(sourceBytes), recorder_sha256: hash(fs.readFileSync(__filename))};
const columns = LifeSim.LEDGER_V7;
if (columns.length !== 143) throw new Error(`unexpected ABI 7 ledger length ${columns.length}`);
if (!fixture.doc || !Array.isArray(fixture.cases) || fixture.cases.length !== 27) {
  throw new Error('expected one fixture doc and exactly 27 fixed cases');
}
const keys = new Set();
for (const entry of fixture.cases) {
  if (!/^[a-zA-Z0-9_.-]+$/.test(entry.key) || keys.has(entry.key)) throw new Error('unsafe or duplicate case key');
  keys.add(entry.key);
  const seed = Number(entry.seed);
  if (!Number.isSafeInteger(seed) || seed < 0 || BigInt(seed) !== BigInt(entry.seed)) {
    throw new Error(`LifeSim needs an exactly represented nonnegative Number seed: ${entry.key}`);
  }
  if (entry.T !== 1024) throw new Error('all saved examples must retain full T=1024');
}
fs.mkdirSync(options.out, {recursive: true});
const cpuStart = process.cpuUsage();
const wallStart = Date.now();
const maxCpu = Number(options['cpu-seconds'] || 600);
const maxWall = Number(options['wall-seconds'] || 600);
let simulated = 0;
const nativeRow = key => Array.isArray(native.cases)
  ? native.cases.find(x => x.key === key) : (native.cases?.[key] || native[key]);
const bits = value => {
  const buffer = Buffer.allocUnsafe(8);
  buffer.writeDoubleLE(value, 0);
  return buffer.toString('hex');
};
const hashNames = ['all', 'spikes', 'fate', 'chem', 'world'];
const normalizedHash = value => {
  const string = String(value).toLowerCase().replace(/^0x/, '');
  if (!/^[0-9a-f]{1,16}$/.test(string)) throw new Error(`invalid 64-bit hash ${value}`);
  return string.padStart(16, '0');
};
const atomic = (name, data) => {
  const target = path.join(options.out, name);
  fs.writeFileSync(`${target}.pending`, JSON.stringify(data));
  fs.renameSync(`${target}.pending`, target);
};
function checkBudget() {
  const used = process.cpuUsage(cpuStart);
  if ((used.user + used.system) / 1e6 > maxCpu || (Date.now() - wallStart) / 1000 > maxWall) {
    throw new Error('recorder budget exceeded; partial receipts preserved, no automatic retry');
  }
  if (process.memoryUsage().rss > 2 * 1024 ** 3) throw new Error('recorder exceeded 2 GiB RSS');
}
function validate(record, entry) {
  if (JSON.stringify(record.binding) !== JSON.stringify(bind) || record.example.key !== entry.key) {
    throw new Error(`saved recording has different input/source binding: ${entry.key}`);
  }
  const expected = nativeRow(entry.key);
  if (!expected || !Array.isArray(expected.ledger) || expected.ledger.length !== columns.length) {
    throw new Error(`missing native ledger for ${entry.key}`);
  }
  const mismatches = columns.flatMap((name, i) => record.ledger_bits[i] === bits(expected.ledger[i])
    ? [] : [{column: name, native: expected.ledger[i], js: record.example.summary[name],
      native_bits: bits(expected.ledger[i]), js_bits: record.ledger_bits[i]}]);
  const expectedHashes = Array.isArray(expected.hashes) ? expected.hashes : hashNames.map(n => expected.hashes[n]);
  const hashMismatches = hashNames.flatMap((name, i) => normalizedHash(record.hashes[name]) === normalizedHash(expectedHashes[i])
    ? [] : [{hash: name, native: expectedHashes[i], js: record.hashes[name]}]);
  const result = {ledger_columns: columns.length, ledger_bitwise_equal: mismatches.length === 0,
    hashes_checked: hashNames.length, hashes_equal: hashMismatches.length === 0, mismatches, hash_mismatches: hashMismatches};
  atomic(`${entry.key}.validation.json`, result);
  if (mismatches.length || hashMismatches.length) {
    throw new Error(`native validation failed for ${entry.key}: ${mismatches.length} ledger and ${hashMismatches.length} hash mismatches`);
  }
  return result;
}
const examples = [];
const validations = [];
for (const entry of fixture.cases) {
  checkBudget();
  const filename = `${entry.key}.json`;
  const savedPath = path.join(options.out, filename);
  const receiptPath = path.join(options.out, `${entry.key}.started.json`);
  let record;
  if (fs.existsSync(savedPath)) {
    record = JSON.parse(fs.readFileSync(savedPath));
  } else {
    if (fs.existsSync(receiptPath)) throw new Error(`partial recording exists for ${entry.key}; explicit review required before retry`);
    fs.writeFileSync(receiptPath, JSON.stringify({binding: bind, key: entry.key, started: new Date().toISOString()}));
    const sim = LifeSim.create(fixture.doc, {body: entry.body, seed: Number(entry.seed), abi: 7,
      mode: 'auto', hashes: true, raster: 0});
    simulated += 1;
    const cells = new Map();
    const frames = [];
    function capture() {
      const state = sim.state({dead: true});
      const ledger = sim.ledger();
      for (const cell of state.cells) cells.set(cell.id, {id: cell.id, a: cell.a, b: cell.b, z: cell.z,
        cls: cell.cls, x: cell.x, y: cell.y, born: cell.born, died: Number.isFinite(cell.died) ? cell.died : null});
      const score = {};
      for (const name of ['captures', 'misses', 'correct_choices', 'wrong_choices', 'initial_harvests',
        'refill_harvests', 'income', 'cost', 'clicks']) score[name] = state.score[name] ?? 0;
      score.contact_harvests = Object.entries(ledger).reduce((sum, [name, value]) =>
        sum + (/^patch_contact_harvest_[0-9]+$/.test(name) ? value : 0), 0);
      frames.push({t: state.t, x: state.dot.x, y: state.dot.y,
        alive: state.cells.filter(c => c.alive).map(c => c.id), fired: [...new Set(state.recentSpikes.map(s => s.id))],
        targets: state.targets, score, stats: {n: state.stats.n, n_S: state.stats.n_S,
          n_M: state.stats.n_M, n_H: state.stats.n_H}, task_state: state.task || null, events: state.events});
    }
    capture();
    while (!sim.ended) {
      checkBudget();
      const before = sim.t;
      const next = Math.min(entry.T, (Math.floor(before / 8) + 1) * 8);
      sim.advance(Math.max(0, next - before), 2000000);
      capture();
      if (!sim.ended && sim.t <= before) throw new Error(`simulation made no progress: ${entry.key}`);
    }
    const ledger = sim.ledger();
    record = {binding: bind, ledger_bits: columns.map(name => bits(ledger[name])), hashes: sim.hashes(),
      example: {...entry, cells: [...cells.values()], frames, summary: ledger}};
    // Persist the full unvalidated result first; a failed comparison must never silently rerun a life.
    atomic(filename, record);
  }
  validations.push({key: entry.key, ...validate(record, entry)});
  examples.push(record.example);
  process.stdout.write(JSON.stringify({key: entry.key, frames: record.example.frames.length,
    captures: record.example.summary.captures, validated: true}) + '\n');
}
if (hash(fs.readFileSync(options.sim)) !== bind.simulator_sha256 || hash(fs.readFileSync(options.fixture)) !== bind.fixture_sha256 ||
    hash(fs.readFileSync(options.native)) !== bind.native_sha256) throw new Error('source or input changed during recording');
const cpu = process.cpuUsage(cpuStart);
const about = {created: new Date().toISOString(), binding: bind,
  method: 'Fixed full-life examples, sampled every 8 simulation time units. Observer snapshots do not provide information to cells.',
  caveat: 'Illustrative paired-seed lives, not a statistical performance test. Target paths may diverge after different captures.',
  simulated_lives_this_invocation: simulated, cpu_seconds: (cpu.user + cpu.system) / 1e6,
  wall_seconds: (Date.now() - wallStart) / 1000, rss_bytes: process.memoryUsage().rss};
atomic('examples.json', {examples, about, validation: {all_passed: true, cases: validations}});
process.stdout.write(JSON.stringify({completed: examples.length, ...about}) + '\n');
