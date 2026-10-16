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
check(record.JS_replays === 4 && record.seed === 52500000 &&
  same(record.roles, ['AO_start', 'patch8_start', 'mean4', 'pareto4']), 'exact fixed cases required');
check(!fs.existsSync(path.join(here, 'replay_result.json')), 'no second replay attempt');
const fixture = read('inputs/fixture.json'), LifeSim = require('./inputs/lifesim.js');
const result = { status:'started', JS_replays:0, record_sha256:pin, seed:52500000, cases:[] };
save('replay_result.json', result);
try {
  for (let i = 0; i < 4; i++) {
    const truth = fixture.cases[i];
    check(truth.role === record.roles[i] && truth.body === i && truth.seed === 52500000, 'case order');
    const one = { role:truth.role, body:i, seed:52500000, status:'started' };
    result.cases.push(one); result.JS_replays++; save('replay_result.json', result);
    const sim = LifeSim.create(fixture.doc, { body:i, seed:52500000, abi:6, mode:'auto', hashes:false, raster:0 });
    let steps = 0;
    while (!sim.ended) {
      sim.advance(.37, 1500); sim.state();
      check(++steps < 200000, 'step cap exceeded');
    }
    Object.assign(one, { status:'returned', steps,
      ledger:Array.from(sim.life.led, value => Object.is(value, -0) ? '-0' : String(value)) });
    save('replay_result.json', result); // Preserve returned native values before a comparison can fail.
    check(one.ledger.length === 107 && same(one.ledger.map(bits), truth.ledger.map(bits)),
      truth.role + ': one or more of107 ledger float bits differ');
    one.status = 'passed'; save('replay_result.json', result);
  }
  require('./inputs/test_resource_patches_view.js'); // Supplied fake simulator: zero new lives.
  require('./test_page.js'); // Supplied viewer dispatch only: zero new lives.
  const script = name => {
    const source = fs.readFileSync(path.join(here, name), 'utf8');
    check(!source.toLowerCase().includes('</script'), 'embedded script termination');
    return source;
  };
  const payload = JSON.stringify({ seed:fixture.seed, doc:fixture.doc, roles:fixture.roles }).replaceAll('<', '\\u003c');
  const page = fs.readFileSync(path.join(here, 'template.html'), 'utf8')
    .replace('__FIXTURE__', () => payload)
    .replace('__ENGINE__', () => script('inputs/lifesim.js'))
    .replace('__VIEW__', () => script('inputs/resource_patches_view.js'))
    .replace('__PAGE__', () => script('page.js'));
  fs.writeFileSync(path.join(here, 'resource_patch_selection.html'), page, { flag:'wx' });
  result.status = 'passed'; save('replay_result.json', result);
  save('validation.json', { status:'passed', JS_replays:4, new_C_lives:0, new_Python_lives:0, builds:0,
    record_sha256:pin, ledger_bits_checked:428, ledger_values_per_role:107, full_hashes_checked:0,
    hash_note:'Saved fast-C hashes are constant. No full-C trajectory hash or raster proof is available.',
    supplied_state_UI_mounts:2, supplied_page_mounts:4, additional_UI_simulator_calls:0, real_browser_tested:false,
    raster_comparison:false, html_sha256:sha('resource_patch_selection.html'),
    replay_result_sha256:sha('replay_result.json') });
  console.log(JSON.stringify({ status:'passed', JS_replays:4, ledger_bits_checked:428, full_hashes_checked:0 }));
} catch (error) {
  save('validation.json', { status:'failed', JS_replays:result.JS_replays, record_sha256:pin,
    error:String(error), replay_result_sha256:sha('replay_result.json'), new_C_lives:0, new_Python_lives:0, builds:0 });
  throw error;
}
