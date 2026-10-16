/* Automatic ABI-5 presentation. mount(element, bodyOrDoc, { seed, body, T, speed }) returns controls.
 * The phase/sample labels are observer information; LifeSim never supplies them to cells.
 * No seed search, task editing, network calls, or external dependencies.
 */
(function (root, factory) {
  const api = factory(typeof module === 'object' && module.exports ? require('./lifesim.js') : root.LifeSim);
  if (typeof module === 'object' && module.exports) module.exports = api;
  else root.DelayedMatchView = api;
})(typeof globalThis !== 'undefined' ? globalThis : this, function (LifeSim) {
'use strict';
function summary(state, ledger) {
  const rows = ['narrow', 'broad'].map(cls => {
    const correct = ledger['correct_choices_' + cls], wrong = ledger['wrong_choices_' + cls];
    const timeout = ledger['choice_timeouts_' + cls], unfinished = ledger['unfinished_choices_' + cls];
    const opened = ledger['choice_opportunities_' + cls] + ledger['choice_carry_in_' + cls];
    return { sample: cls, correct, wrong, narrow: cls === 'narrow' ? correct : wrong, broad: cls === 'broad' ? correct : wrong,
      timeout, unfinished, opened, resolved: correct + wrong,
      accuracy: correct + wrong ? correct / (correct + wrong) : null,
      coverage: opened ? (correct + wrong) / opened : null };
  });
  return { phase: state.task.phase, sample: state.task.sample_class, trial: state.task.trial + 1,
    remaining: state.task.remaining, ended: state.ended, rows };
}
function mount(element, bodyOrDoc, opts = {}) {
  if (!LifeSim) throw new Error('Load lifesim.js before the delayed-match viewer');
  const seed = opts.seed;
  if (!Number.isSafeInteger(seed)) throw new Error('A fixed exported seed is required');
  let sim, state, playing = false, frame = null, previous = null, destroyed = false;
  const speed = opts.speed === undefined ? 8 : opts.speed;
  const el = (tag, text) => { const n = element.ownerDocument.createElement(tag); if (text !== undefined) n.textContent = text; return n; };
  element.replaceChildren();
  const title = el('h2', 'Delayed matching by cue shape');
  const note = el('p', 'Watch the sample, then the blank interval, then two choices. The cells receive only receptor pings. Phase and sample labels below are for the observer.');
  const controls = el('div'), play = el('button', 'Play'), restart = el('button', 'Replay this seed');
  const status = el('p'), canvas = el('canvas'), score = el('p'), table = el('table'), caption = el('caption');
  const feed = el('p');
  controls.append(play, restart); canvas.width = 760; canvas.height = 560;
  canvas.style.cssText = 'width:100%;height:auto;background:#111c29;border-radius:12px';
  canvas.setAttribute('aria-label', 'Tissue and active narrow or broad light sources');
  status.setAttribute('role', 'status');
  caption.textContent = 'Choices by earlier sample; no completed choice includes timeout and unfinished';
  table.append(caption);
  const header = el('tr');
  for (const text of ['Sample', 'Opportunities', 'Correct', 'Wrong', 'Narrow hits', 'Broad hits', 'Timeout', 'Unfinished', 'Coverage', 'Accuracy']) header.append(el('th', text));
  const head = el('thead'), tbody = el('tbody'); head.append(header); table.append(head, tbody);
  const rows = ['narrow', 'broad'].map(() => {
    const row = el('tr'), cells = Array.from({ length: 10 }, () => el('td'));
    row.append(...cells); tbody.append(row); return cells;
  });
  element.append(title, note, controls, status, canvas, score, table, feed);
  const context = canvas.getContext('2d'), recent = [];
  const percent = x => x === null ? '—' : (100 * x).toFixed(1) + '%';
  function draw() {
    state = sim.state();
    const ledger = sim.ledger(), info = sim.info(), s = summary(state, ledger);
    status.textContent = `Seed ${seed} · t ${state.t.toFixed(2)} · trial ${s.trial} · ${s.phase} · sample ${s.sample} · ` +
      (s.ended ? 'life ended' : `${s.remaining.toFixed(2)} until phase deadline`);
    play.textContent = playing ? 'Pause' : 'Play'; play.disabled = s.ended;
    score.textContent = `Correct matches ${state.score.correct_choices} · wrong choices ${state.score.wrong_choices} · ` +
      `physical narrow-slot hits ${state.score.slot_hits.narrow} · broad-slot hits ${state.score.slot_hits.broad} · ` +
      `misses ${state.score.misses} · reward ${state.score.income.toFixed(1)} · energy cost ${state.score.cost.toFixed(1)} · native F ${state.score.F.toFixed(2)}`;
    s.rows.forEach((row, i) => [row.sample, row.opened, row.correct, row.wrong, row.narrow, row.broad, row.timeout, row.unfinished,
      percent(row.coverage), percent(row.accuracy)].forEach((value, j) => { rows[i][j].textContent = value; }));
    for (const event of state.events) if (event.kind === 'task_resolution' || event.kind === 'slot_hit' || event.kind === 'miss') {
      recent.push(`${event.t.toFixed(2)}: ${event.kind === 'task_resolution' ? event.outcome + ' for ' + event.sample_class + ' sample' :
        event.kind === 'slot_hit' ? (event.slot === 0 ? 'narrow' : 'broad') + ' slot hit' : 'miss'}`);
    }
    if (recent.length > 6) recent.splice(0, recent.length - 6); feed.textContent = recent.join(' · ');
    context.clearRect(0, 0, canvas.width, canvas.height);
    let extent = Math.max(8, info.R_max + 4 * info.b2_sigma);
    for (const target of state.targets) extent = Math.max(extent, Math.abs(target.x - state.dot.x) + 4 * target.sigma,
      Math.abs(target.y - state.dot.y) + 4 * target.sigma);
    for (const cell of state.cells) extent = Math.max(extent, Math.abs(cell.x) + 2, Math.abs(cell.y) + 2);
    const scale = Math.min(canvas.width, canvas.height) / (2 * extent);
    const sx = x => canvas.width / 2 + (x - state.dot.x) * scale;
    const sy = y => canvas.height / 2 - (y - state.dot.y) * scale;
    for (const target of state.targets) {
      const x = sx(target.x), y = sy(target.y), radius = 4 * target.sigma * scale;
      const glow = context.createRadialGradient(x, y, 0, x, y, radius);
      for (const p of [0, 0.25, 0.5, 0.75, 1]) glow.addColorStop(p, `rgba(118,213,233,${0.7 * Math.exp(-8 * p * p)})`);
      context.fillStyle = glow; context.beginPath(); context.arc(x, y, radius, 0, 2 * Math.PI); context.fill();
      if (target.capturable) {
        context.setLineDash([5, 5]); context.strokeStyle = '#d6e4ee'; context.lineWidth = 1;
        context.beginPath(); context.arc(x, y, target.capture_radius * scale, 0, 2 * Math.PI); context.stroke(); context.setLineDash([]);
      }
      context.fillStyle = '#e3f7ff'; context.font = '14px system-ui';
      context.fillText(target.shape, x + 7, y - target.sigma * scale - 8);
    }
    for (const cell of state.cells) {
      const x = sx(state.dot.x + cell.x), y = sy(state.dot.y + cell.y);
      context.fillStyle = state.t - cell.lastSpike < 1.2 ? '#fff2aa' : ['#77d5bf', '#edb97b', '#bd9ce8'][Math.min(cell.z, 2)];
      context.globalAlpha = cell.z === 0 ? 0.9 : 0.65;
      context.beginPath(); context.arc(x + cell.z * 2, y - cell.z * 2, Math.max(2, scale * 0.23), 0, 2 * Math.PI); context.fill();
    }
    context.globalAlpha = 1; context.strokeStyle = '#ffffff'; context.lineWidth = 1.5;
    context.beginPath(); context.arc(sx(state.dot.x), sy(state.dot.y), 4, 0, 2 * Math.PI); context.stroke();
  }
  function reset(newSeed) {
    playing = false; previous = null; if (newSeed !== seed) throw new Error('Replay must retain the fixed seed'); recent.length = 0;
    sim = LifeSim.create(bodyOrDoc, { ...opts, seed, mode: 'auto' });
    if (sim.info().task_mode !== 1) throw new Error('The automatic viewer requires an ABI-5 delayed-match body');
    draw();
  }
  function tick(now) {
    if (destroyed) return;
    if (playing && !sim.ended) {
      const dt = previous === null ? 0 : Math.min((now - previous) / 1000, 0.1) * speed;
      if (dt > 0) sim.advance(dt, 1500);
      if (sim.ended) playing = false;
      draw();
    }
    previous = now; frame = requestAnimationFrame(tick);
  }
  play.addEventListener('click', () => { playing = !playing; previous = null; draw(); });
  restart.addEventListener('click', () => reset(seed));
  reset(seed); frame = requestAnimationFrame(tick);
  return { get simulator() { return sim; }, replay: () => reset(seed),
    destroy: () => { destroyed = true; cancelAnimationFrame(frame); element.replaceChildren(); } };
}
return { mount, summary };
});
