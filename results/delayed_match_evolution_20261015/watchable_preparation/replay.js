/* Exactly twelve stepped ABI5 replays after terminal scientific completion, under a separate monitor. */
'use strict';
const fs = require('fs'), path = require('path'), crypto = require('crypto');
const args = process.argv.slice(2), here = __dirname, artifact = path.join(here, 'artifact');
const read = file => JSON.parse(fs.readFileSync(file, 'utf8'));
const sha = file => crypto.createHash('sha256').update(fs.readFileSync(file)).digest('hex');
const requireTrue = (value, message) => { if (!value) throw new Error(message); };
const save = (name, value) => {
  const file = path.join(artifact, name), temporary = file + '.tmp';
  fs.writeFileSync(temporary, JSON.stringify(value, null, 2) + '\n', { flag: 'wx' }); fs.renameSync(temporary, file);
};
if (!args.includes('--replay-child')) {
  console.log(JSON.stringify({ status: 'source_only', JS_replay_lives: 0 }));
} else {
  const recordIndex = args.indexOf('--record');
  requireTrue(recordIndex >= 0 && args[recordIndex + 1], '--record is required');
  const recordPath = path.resolve(args[recordIndex + 1]), record = read(recordPath);
  const root = path.resolve(here, '../../..'), study = path.dirname(here);
  requireTrue(record.status === 'registered_fixed_delayed_match_viewer' && record.C_full_lives === 12 &&
    record.JS_replay_lives === 12, 'fixed monitored scope differs');
  const execution = path.join(here, 'execution'), attemptPath = path.join(execution, 'attempt.json');
  const workerPath = path.join(execution, 'worker_identity.json'), digest = sha(recordPath);
  const identity = pid => {
    const stat = fs.readFileSync('/proc/' + pid + '/stat', 'utf8');
    const fields = stat.slice(stat.lastIndexOf(')') + 1).trim().split(/\s+/);
    return { pid, ppid: Number(fields[1]), pgid: Number(fields[2]), start_ticks: Number(fields[19]) };
  };
  const monitorPid = Number(process.env.CELLDEV_MONITOR_PID);
  const workerPid = Number(process.env.CELLDEV_WATCHABLE_WORKER_PID);
  requireTrue(monitorPid > 1 && workerPid > 1 && process.ppid === workerPid &&
    process.env.CELL_DEV_WATCHABLE_RECORD_SHA256 === digest, 'use the owned pipeline worker');
  requireTrue(process.env.CELLDEV_ATTEMPT_PATH === attemptPath &&
    process.env.CELLDEV_ATTEMPT_SHA256 === sha(attemptPath) &&
    process.env.CELLDEV_WATCHABLE_WORKER_SHA256 === sha(workerPath), 'changed execution bindings');
  const attempt = read(attemptPath), worker = read(workerPath);
  const actualMonitor = identity(monitorPid), actualWorker = identity(workerPid), actualSelf = identity(process.pid);
  const namespace = fs.readlinkSync('/proc/self/ns/pid');
  requireTrue(Object.keys(actualMonitor).every(key => attempt.monitor[key] === actualMonitor[key]) &&
    Object.keys(actualWorker).every(key => worker[key] === actualWorker[key]) &&
    actualWorker.ppid === monitorPid && actualWorker.pgid === workerPid && actualSelf.pgid === workerPid &&
    Number(process.env.CELLDEV_MONITOR_START_TICKS) === actualMonitor.start_ticks &&
    Number(process.env.CELLDEV_WATCHABLE_WORKER_START_TICKS) === actualWorker.start_ticks &&
    attempt.pid_namespace === namespace && worker.pid_namespace === namespace &&
    process.env.CELLDEV_PID_NAMESPACE === namespace && attempt.protocol_sha256 === digest &&
    attempt.release_sha256 === digest && process.env.CELLDEV_PROTOCOL_SHA256 === digest &&
    worker.record_sha256 === digest && worker.attempt_sha256 === sha(attemptPath),
  'owned monitor, worker, namespace or record differs');
  requireTrue(['OMP_NUM_THREADS', 'OMP_THREAD_LIMIT', 'MKL_NUM_THREADS', 'OPENBLAS_NUM_THREADS',
    'NUMEXPR_NUM_THREADS'].every(key => process.env[key] === '1'), 'one-thread environment required');
  for (const [name, digest] of Object.entries(record.source_pins))
    requireTrue(sha(path.join(here, name)) === digest, 'changed viewer source ' + name);
  for (const [name, digest] of Object.entries(record.study_pins))
    requireTrue(sha(path.join(study, name)) === digest, 'changed completed study ' + name);
  const budget = read(path.join(study, 'budget.json'));
  requireTrue(budget.status === 'complete' && budget.terminal_cleanup.all_owned_groups_exited &&
    budget.terminal_cleanup.all_worker_identities_exited && !budget.terminal_cleanup.remaining_descendants.length,
    'scientific study must be complete and cleared');
  const receipt = read(path.join(artifact, 'export_receipt.json'));
  requireTrue(receipt.status === 'complete' && receipt.C_full_lives === 12 &&
    receipt.record_sha256 === sha(recordPath), 'complete bound C export required');
  for (const [file, key] of [['bodies.json', 'bodies_sha256'], ['truth.json', 'truth_sha256'],
    ['C_calls.json', 'C_calls_sha256']]) requireTrue(sha(path.join(artifact, file)) === receipt[key], 'changed ' + file);
  const data = read(path.join(artifact, 'bodies.json')), truth = read(path.join(artifact, 'truth.json'));
  requireTrue(data.roles.join(',') === 'AO_start,mixed8,mixed24' && data.seeds.join(',') ===
    '52460000,52460001,52460002,52460003' && truth.cases.length === 12, 'fixed case inventory differs');
  for (const name of ['JS_calls.json', 'replay_receipt.json'])
    requireTrue(!fs.existsSync(path.join(artifact, name)), 'first attempt refuses existing ' + name);
  const engine = path.join(root, 'results/atlas/play/lifesim.js');
  requireTrue(sha(engine) === record.dependency_pins['results/atlas/play/lifesim.js'], 'changed engine');
  const LifeSim = require(engine), calls = [];
  const bits = value => { const buffer = Buffer.alloc(8); buffer.writeDoubleLE(Number(value)); return buffer.toString('hex'); };
  const same = (a, b) => JSON.stringify(a) === JSON.stringify(b);
  try {
    for (let index = 0; index < 12; index++) {
      const body = Math.floor(index / 4), seed = data.seeds[index % 4], wanted = truth.cases[index];
      requireTrue(wanted.body_index === body && wanted.role === data.roles[body] && wanted.seed === seed,
        'case order differs');
      requireTrue(sha(path.join(artifact, wanted.native_file)) === wanted.native_file_sha256, 'changed C output');
      const call = { index, role: wanted.role, seed, status: 'started' }; calls.push(call); save('JS_calls.json', calls);
      const sim = LifeSim.create(data, { body, seed, abi: 5, mode: 'auto', hashes: true, raster: truth.raster_cap });
      let steps = 0;
      while (!sim.ended) {
        sim.advance(.37, 1500); sim.state();
        if (++steps > 100000) throw new Error('step limit exceeded');
      }
      const ledger = Array.from(sim.life.led), hashes = Object.values(sim.hashes()), raster = sim.raster();
      call.status = 'returned'; call.steps = steps; call.ledger = ledger; call.hashes = hashes;
      save('JS_calls.json', calls);
      requireTrue(ledger.length === 70 && same(ledger.map(bits), wanted.ledger.map(bits)), 'ledger bits differ');
      requireTrue(same(hashes, wanted.hashes), 'one or more full hash families differ');
      requireTrue(raster.n === wanted.raster_total && same(raster.t.map(bits), wanted.raster_t.map(bits)) &&
        same(raster.uid, wanted.raster_uid), 'spike raster differs');
      const named = sim.ledger();
      for (const cls of ['narrow', 'broad']) requireTrue(
        named['choice_opportunities_' + cls] + named['choice_carry_in_' + cls] ===
        named['correct_choices_' + cls] + named['wrong_choices_' + cls] + named['choice_timeouts_' + cls] +
        named['unfinished_choices_' + cls], 'class conservation differs');
      call.status = 'validated'; call.ledger_values_equal = 70; call.hash_families_equal = 5;
      call.raster_spikes_equal = raster.n; save('JS_calls.json', calls);
    }
    const result = { status: 'complete', JS_replay_lives: 12, C_full_lives_in_export: 12, new_research_cases: 0,
      record_sha256: sha(recordPath), calls_sha256: sha(path.join(artifact, 'JS_calls.json')),
      ledger_values_checked: 840, hash_families_checked: 60, real_browser_tested: false };
    save('replay_receipt.json', result); console.log(JSON.stringify(result));
  } catch (error) {
    save('replay_receipt.json', { status: 'incomplete', JS_constructions_attempted: calls.length,
      validated: calls.filter(call => call.status === 'validated').length, error: String(error),
      calls_sha256: sha(path.join(artifact, 'JS_calls.json')), record_sha256: sha(recordPath) });
    throw error;
  }
}
