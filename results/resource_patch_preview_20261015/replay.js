'use strict';
const fs = require('fs'), path = require('path'), crypto = require('crypto');
const here = __dirname, read = name => JSON.parse(fs.readFileSync(path.join(here, name), 'utf8'));
const sha = name => crypto.createHash('sha256').update(fs.readFileSync(path.join(here, name))).digest('hex');
const save = (name, value) => fs.writeFileSync(path.join(here, name), JSON.stringify(value, null, 2) + '\n');
const check = (condition, message) => { if (!condition) throw new Error(message); };
const bits = value => { const b = Buffer.alloc(8); b.writeDoubleLE(Number(value)); return b.toString('hex'); };
const same = (a, b) => JSON.stringify(a) === JSON.stringify(b);
const record = read('execution_record.json'), pin = sha('execution_record.json');
check(process.ppid === Number(process.env.CELLDEV_MONITOR_PID) &&
  process.env.CELLDEV_PROTOCOL_SHA256 === pin && process.env.CELLDEV_ATTEMPT_PATH ===
  path.join(here, 'execution/attempt.json'), 'use the owned one-attempt monitor');
for (const key of ['source_pins', 'input_pins'])
  for (const [name, digest] of Object.entries(record[key])) check(sha(name) === digest, 'changed input ' + name);
check(record.JS_replays === 1 && record.seed === 42000000, 'exact fixed case required');
check(!fs.existsSync(path.join(here, 'replay_result.json')), 'no second replay attempt');
const fixture = read('inputs/fixture.json'), LifeSim = require('./inputs/lifesim.js');
let result = { status:'started', JS_replays:1, record_sha256:pin, seed:42000000 };
save('replay_result.json', result);
try {
  const sim = LifeSim.create(fixture.doc, { body:0, seed:42000000, abi:6, mode:'auto', hashes:true, raster:0 });
  let steps = 0;
  while (!sim.ended) {
    sim.advance(.37, 1500); sim.state();
    check(++steps < 200000, 'step cap exceeded');
  }
  result = { ...result, status:'returned', steps, ledger:Array.from(sim.life.led), hashes:Object.values(sim.hashes()) };
  save('replay_result.json', result);
  check(result.ledger.length === 107 && same(result.ledger.map(bits), fixture.truth.ledger.map(bits)),
    'one or more of107 ledger float bits differ');
  check(same(result.hashes, fixture.truth.hashes), 'one or more of5 full hashes differ');
  // This module uses a supplied fake simulator in its own VM: zero further LifeSim constructions.
  require('./inputs/test_resource_patches_view.js');
  const script = name => {
    const source = fs.readFileSync(path.join(here, name), 'utf8');
    check(!source.toLowerCase().includes('</script'), 'embedded script termination');
    return source;
  };
  const payload = JSON.stringify({ seed:fixture.seed, doc:fixture.doc }).replaceAll('<', '\\u003c');
  const page = fs.readFileSync(path.join(here, 'template.html'), 'utf8')
    .replace('__FIXTURE__', () => payload)
    .replace('__ENGINE__', () => script('inputs/lifesim.js'))
    .replace('__VIEW__', () => script('inputs/resource_patches_view.js'));
  fs.writeFileSync(path.join(here, 'resource_patch_AO.html'), page, { flag:'wx' });
  save('validation.json', { status:'passed', JS_replays:1, new_C_lives:0, new_Python_lives:0, builds:0,
    record_sha256:pin, ledger_bits_checked:107, full_hashes_checked:5,
    supplied_state_UI_mounts:2, additional_UI_simulator_calls:0, real_browser_tested:false,
    raster_comparison:false, raster_note:'Saved C row had zero logging caps; full event hashes were compared.',
    html_sha256:sha('resource_patch_AO.html'), replay_result_sha256:sha('replay_result.json') });
  console.log(JSON.stringify({ status:'passed', ledger_bits_checked:107, full_hashes_checked:5 }));
} catch (error) {
  save('validation.json', { status:'failed', JS_replays:1, record_sha256:pin,
    error:String(error), replay_result_sha256:sha('replay_result.json'), new_C_lives:0, new_Python_lives:0, builds:0 });
  throw error;
}
