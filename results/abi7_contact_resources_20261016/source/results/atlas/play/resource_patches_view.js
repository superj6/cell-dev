/* Automatic ABI-6/7 presentation. Patch identities, stocks, periods and pending jobs are observer labels.
 * mount(element, bodyOrDoc, {seed, body, speed}) starts paused and exposes only playback of that fixed case.
 */
(function (root, factory) {
  const api = factory(typeof module === 'object' && module.exports ? require('./lifesim.js') : root.LifeSim);
  if (typeof module === 'object' && module.exports) module.exports = api;
  else root.ResourcePatchesView = api;
})(typeof globalThis !== 'undefined' ? globalThis : this, function (LifeSim) {
'use strict';
function summary(state, ledger) {
  if (!state.patches) throw new Error('resource patch observer state required');
  const rows = state.patches.map(p => {
    const get = stem => ledger['patch_' + stem + '_' + p.slot] || 0;
    return { slot: p.slot, stock: p.stock, capacity: p.capacity, period: p.period,
      source: get('source'), supply: get('supply'), spill: get('spill'), harvest: get('harvest'),
      initial: get('initial_harvest'), refill: get('refill_harvest'), empty: get('empty'),
      contact: get('contact_harvest'), passive: get('refill_harvest') - get('contact_harvest'),
      starts: get('contact_starts'), maturities: get('contact_maturities'), contactSpill: get('contact_spill'),
      pending: !!p.contact_pending, due: p.contact_due };
  });
  const sum = key => rows.reduce((total, row) => total + row[key], 0);
  return { rows, harvest: sum('harvest'), initial: sum('initial'), refill: sum('refill'),
    empty: sum('empty'), geometric: ledger.patch_geometric_misses,
    source: sum('source'), supply: sum('supply'), spill: sum('spill'), contact: sum('contact'),
    passive: sum('passive'), starts: sum('starts'), maturities: sum('maturities'), contactSpill: sum('contactSpill') };
}
function mount(element, bodyOrDoc, opts = {}) {
  if (!LifeSim) throw new Error('Load lifesim.js before the resource-patch viewer');
  if (!Number.isSafeInteger(opts.seed)) throw new Error('A fixed safe-integer seed is required');
  const seed = opts.seed, speed = opts.speed === undefined ? 8 : opts.speed;
  let sim, playing = false, frame = null, previous = null, destroyed = false, contactColumns = false;
  const recent = [], rows = [];
  const el = (tag, text) => {
    const node = element.ownerDocument.createElement(tag);
    if (text !== undefined) node.textContent = text;
    return node;
  };
  element.replaceChildren();
  const title = el('h2', 'Persistent food patches');
  const note = el('p', 'A harvest removes one packet. Fixed sources refill the patches; full patches spill. ' +
    'Cells receive only local receptor pings. Patch IDs, stock and source periods are observer information.');
  const controls = el('div'), play = el('button', 'Play'), replay = el('button', 'Replay this case');
  controls.append(play, replay);
  const status = el('p'), canvas = el('canvas'), score = el('p'), table = el('table'), feed = el('p');
  status.setAttribute('role', 'status');
  canvas.width = 760; canvas.height = 560;
  canvas.style.cssText = 'width:100%;height:auto;background:#111c29;border-radius:12px';
  canvas.setAttribute('aria-label', 'Growing tissue and stationary food patches; brightness reflects stock');
  const caption = el('caption', 'Current physical stock; harvest/source/action counts use the accounting window');
  const head = el('thead'), header = el('tr'), tbody = el('tbody');
  for (const text of ['Patch', 'Stock', 'Source period', 'Harvests', 'Initial food', 'Refill food',
    'Source', 'Admitted', 'Spilled', 'Empty clicks']) header.append(el('th', text));
  head.append(header); table.append(caption, head, tbody);
  element.append(title, note, controls, status, canvas, score, table, feed);
  const ctx = canvas.getContext('2d');
  function draw() {
    const state = sim.state(), info = sim.info(), s = summary(state, sim.ledger());
    const contact = info.patch_contact_delay > 0;
    if (contact !== contactColumns) {
      contactColumns = contact; header.replaceChildren(); tbody.replaceChildren(); rows.length = 0;
      for (const text of ['Patch', 'Stock', 'Passive period', 'Harvests', 'Initial food', 'Passive food',
        'Total source', 'Admitted', 'Spilled', 'Empty clicks', 'Contact food', 'Starts', 'Maturities',
        'Contact spills', 'Pending (observer only)']) header.append(el('th', text));
    }
    if (contact) note.textContent = `An empty-site tap starts one packet due ${info.patch_contact_delay} time units later; ` +
      'repeated taps cannot accelerate it. Harvests do not start growth. Passive refill continues. ' +
      'Cells receive only local stock-dependent receptor pings. Pending jobs, deadlines, food origins and patch IDs ' +
      'are observer information, never cell inputs.';
    status.textContent = `Seed ${seed} · t ${state.t.toFixed(2)} · ${state.ended ? 'life ended' : 'automatic world'}`;
    play.textContent = playing ? 'Pause' : 'Play'; play.disabled = state.ended;
    const food = contact ? `${s.initial} initial, ${s.passive} passive, ${s.contact} contact-grown` :
      `${s.initial} initial, ${s.refill} replenished`;
    score.textContent = `Food harvested ${s.harvest} (${food}) · ` +
      (contact ? `growth starts ${s.starts} · matured ${s.maturities} · contact spills ${s.contactSpill} · ` : '') +
      `empty clicks ${s.empty} · geometric misses ${s.geometric} · source ${s.source} · spilled ${s.spill} · ` +
      `income ${state.score.income.toFixed(1)} · energy costs ${state.score.cost.toFixed(1)} · ` +
      `native F ${state.score.F.toFixed(2)}`;
    while (rows.length < s.rows.length) {
      const tr = el('tr'), cells = Array.from({ length: contact ? 15 : 10 }, () => el('td'));
      tr.append(...cells); tbody.append(tr); rows.push(cells);
    }
    s.rows.forEach((p, i) => [p.slot + 1, `${p.stock}/${p.capacity}`, p.period, p.harvest, p.initial,
      contact ? p.passive : p.refill, p.source, p.supply, p.spill, p.empty,
      ...(contact ? [p.contact, p.starts, p.maturities, p.contactSpill,
        p.pending ? `due ${p.due.toFixed(2)}` : 'none'] : [])]
      .forEach((value, j) => { rows[i][j].textContent = value; }));
    for (const event of state.events) if (event.kind === 'patch_click')
      recent.push(`${event.t.toFixed(2)}: ${event.outcome}` +
        (event.slot === null ? '' : ` at patch ${event.slot + 1}`) +
        (event.outcome === 'harvest' ? ` (${event.origin} food)` : ''));
    else if (event.kind === 'patch_contact_start')
      recent.push(`${event.t.toFixed(2)}: patch ${event.slot + 1} starts growth; due ${event.due.toFixed(2)} (observer)`);
    else if (event.kind === 'patch_contact_mature')
      recent.push(`${event.t.toFixed(2)}: patch ${event.slot + 1} contact packet ${event.admitted ? 'ready' : 'spilled'}`);
    if (recent.length > 6) recent.splice(0, recent.length - 6);
    feed.textContent = recent.join(' · ');
    ctx.clearRect(0, 0, canvas.width, canvas.height);
    let extent = Math.max(8, info.R_max + 4 * info.sigma);
    for (const p of state.patches) extent = Math.max(extent,
      Math.abs(p.x - state.dot.x) + 4 * p.sigma, Math.abs(p.y - state.dot.y) + 4 * p.sigma);
    for (const c of state.cells) extent = Math.max(extent, Math.abs(c.x) + 2, Math.abs(c.y) + 2);
    const scale = Math.min(canvas.width, canvas.height) / (2 * extent);
    const sx = x => canvas.width / 2 + (x - state.dot.x) * scale;
    const sy = y => canvas.height / 2 - (y - state.dot.y) * scale;
    for (const p of state.patches) {
      const x = sx(p.x), y = sy(p.y), radius = 4 * p.sigma * scale;
      const glow = ctx.createRadialGradient(x, y, 0, x, y, radius);
      for (const r of [0, 0.25, 0.5, 0.75, 1])
        glow.addColorStop(r, `rgba(118,213,233,${0.7 * p.amplitude * Math.exp(-8 * r * r)})`);
      ctx.fillStyle = glow; ctx.beginPath(); ctx.arc(x, y, radius, 0, 2 * Math.PI); ctx.fill();
      ctx.setLineDash([5, 5]); ctx.strokeStyle = p.stock > 0 ? '#d6e4ee' : '#71818c'; ctx.lineWidth = 1;
      ctx.beginPath(); ctx.arc(x, y, p.capture_radius * scale, 0, 2 * Math.PI); ctx.stroke(); ctx.setLineDash([]);
      ctx.fillStyle = '#e3f7ff'; ctx.font = '14px system-ui';
      ctx.fillText(`Patch ${p.slot + 1}: ${p.stock}/${p.capacity}`, x + 7, y - p.sigma * scale - 8);
    }
    for (const c of state.cells) {
      const x = sx(state.dot.x + c.x), y = sy(state.dot.y + c.y);
      ctx.fillStyle = state.t - c.lastSpike < 1.2 ? '#fff2aa' : ['#77d5bf', '#edb97b', '#bd9ce8'][Math.min(c.z, 2)];
      ctx.globalAlpha = c.z === 0 ? 0.9 : 0.65;
      ctx.beginPath(); ctx.arc(x + c.z * 2, y - c.z * 2, Math.max(2, scale * 0.23), 0, 2 * Math.PI); ctx.fill();
    }
    ctx.globalAlpha = 1; ctx.strokeStyle = '#ffffff'; ctx.lineWidth = 1.5;
    ctx.beginPath(); ctx.arc(sx(state.dot.x), sy(state.dot.y), 4, 0, 2 * Math.PI); ctx.stroke();
  }
  function reset() {
    playing = false; previous = null; recent.length = 0;
    const which = opts.body === undefined ? 0 : opts.body;
    const body = bodyOrDoc.bodies ? (typeof which === 'string' ?
      bodyOrDoc.bodies.find(b => b.name === which) : bodyOrDoc.bodies[which]) : bodyOrDoc;
    const abi = opts.abi === undefined ? (body && body.abi !== undefined ? body.abi :
      bodyOrDoc.abi === undefined ? 6 : bodyOrDoc.abi) : opts.abi;
    sim = LifeSim.create(bodyOrDoc, { ...opts, seed, abi, mode: 'auto' });
    if (!(sim.info().patch_count > 0)) throw new Error('The automatic viewer requires an ABI-6/7 patch body');
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
  replay.addEventListener('click', reset);
  reset(); frame = requestAnimationFrame(tick);
  return { get simulator() { return sim; }, replay: reset,
    destroy: () => { destroyed = true; cancelAnimationFrame(frame); element.replaceChildren(); } };
}
return { mount, summary };
});
