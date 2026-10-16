'use strict';
const fs = require('fs');
const path = require('path');
const api = require(path.resolve(__dirname, '../worktree/results/atlas/play/lifesim.js'));
const original = api.create;
const calls = [];
api.create = function (...args) {
  const row = { index: calls.length, constructed: false, run_calls: 0, advance_calls: 0,
    completed_via_advance: false, direct_close_calls: 0 };
  calls.push(row);
  const sim = original.apply(this, args), life = sim.life;
  Object.assign(row, { constructed: true, seed: life.seed, abi: life.abi, T: life.T, initial_mode: life.mode });
  const advance = life.advance, run = life.run, close = life.close;
  let advancing = 0;
  life.advance = function (...values) {
    row.advance_calls++; advancing++;
    try { return advance.apply(this, values); }
    finally { advancing--; if (this.ended) row.completed_via_advance = true; }
  };
  life.run = function (...values) { row.run_calls++; return run.apply(this, values); };
  life.close = function (...values) {
    if (!advancing) row.direct_close_calls++;
    return close.apply(this, values);
  };
  return sim;
};
process.on('exit', code => {
  const result = { exit_code: code, attempts: calls.length, constructed: calls.filter(c => c.constructed).length,
    completed_via_advance: calls.filter(c => c.completed_via_advance).length,
    direct_close_calls: calls.reduce((n, c) => n + c.direct_close_calls, 0), calls };
  if (process.env.LIFE_JS_CALL_LOG) fs.writeFileSync(process.env.LIFE_JS_CALL_LOG, JSON.stringify(result, null, 2) + '\n');
  console.log('JS call inventory:', JSON.stringify({ ...result, calls: undefined }));
});
