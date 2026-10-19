(function () {
  'use strict';
  const COLORS = ['#2d9a79', '#e39b42', '#9373b6', '#9373b6'];
  const TASKS = { pool: 'Moving food', contact_food: 'Food patches with regrowth', matching: 'Remember the shape' };
  const LINEAGES = { AO_s7: 'AO · population 7', D90_Z_s5: 'D90 · population 5', speck_s6: 'SPECK · population 6' };
  const NOTES = {
    pool: 'Food moves continuously. The body must approach and tap within capture distance. Successful collection places a new target; extra taps cost energy.',
    contact_food: 'Stationary patches hold food and refill over time. A tap on an empty patch also starts delayed growth. Watch whether the body returns, stays nearby, or leaves; this example alone does not establish planning.',
    matching: 'A narrow or broad cue appears, disappears briefly, then two choices appear. The earlier shape determines the correct choice. Repeatedly favoring the broad shape can earn food without remembering the cue.'
  };
  function frameAt(frames, time) {
    let lo = 0, hi = frames.length - 1;
    while (lo < hi) {
      const mid = Math.ceil((lo + hi) / 2);
      if (frames[mid].t <= time) lo = mid; else hi = mid - 1;
    }
    return frames[lo];
  }
  function groupExamples(examples, lineage, task) {
    return examples.filter(e => e.lineage === lineage && e.task === task)
      .sort((a, b) => a.generation - b.generation);
  }
  function finite(value) { return typeof value === 'number' && Number.isFinite(value); }
  function number(value, digits = 0) {
    return finite(value) ? value.toLocaleString('en-US', { maximumFractionDigits: digits }) : '—';
  }
  function position(c) { return { x: finite(c.x) ? c.x : c.a + .5 * c.b,
    y: finite(c.y) ? c.y : c.b * Math.sqrt(3) / 2 }; }
  function worldBounds(examples) {
    let lowX = Infinity, highX = -Infinity, lowY = Infinity, highY = -Infinity;
    for (const e of examples) {
      let bodyRadius = 1;
      for (const cell of e.cells) { const p = position(cell); bodyRadius = Math.max(bodyRadius, Math.hypot(p.x, p.y)); }
      for (const f of e.frames) {
        lowX = Math.min(lowX, f.x - bodyRadius); highX = Math.max(highX, f.x + bodyRadius);
        lowY = Math.min(lowY, f.y - bodyRadius); highY = Math.max(highY, f.y + bodyRadius);
        for (const target of f.targets || []) {
          if (!finite(target.x) || !finite(target.y)) continue;
          lowX = Math.min(lowX, target.x - 1); highX = Math.max(highX, target.x + 1);
          lowY = Math.min(lowY, target.y - 1); highY = Math.max(highY, target.y + 1);
        }
      }
    }
    const span = Math.max(highX - lowX, (highY - lowY) * 1.4, 12) * 1.1;
    return { x: (lowX + highX) / 2, y: (lowY + highY) / 2, span };
  }
  function phaseText(frame) {
    if (!frame.task_state) return '';
    const task = frame.task_state;
    const cue = task.sample_class === 'narrow' || task.sample_class === 0 ? 'narrow' :
      task.sample_class === 'broad' || task.sample_class === 1 ? 'broad' : '?';
    return `${String(task.phase || 'task')} · earlier cue: ${cue} (observer label)`;
  }
  const api = { frameAt, groupExamples, worldBounds, number, phaseText };
  if (typeof module === 'object' && module.exports) module.exports = api;
  if (typeof document === 'undefined') return;
  const $ = id => document.getElementById(id);
  const node = (tag, className, text) => {
    const n = document.createElement(tag);
    if (className) n.className = className;
    if (text !== undefined) n.textContent = text;
    return n;
  };
  let data, examples, cards = [], bounds, playing = false, time = 128, last = null, duration = 1024;
  function drawWorld(card, frame) {
    const c = card.world, ctx = c.getContext('2d'), e = card.example;
    const scale = (c.width - 36) / bounds.span;
    const x = value => c.width / 2 + (value - bounds.x) * scale;
    const y = value => c.height / 2 - (value - bounds.y) * scale;
    ctx.clearRect(0, 0, c.width, c.height);
    ctx.fillStyle = '#fbfcfd'; ctx.fillRect(0, 0, c.width, c.height);
    ctx.strokeStyle = '#edf1f4'; ctx.lineWidth = 1;
    const spacing = bounds.span > 50 ? 10 : bounds.span > 22 ? 5 : 2;
    for (let a = Math.floor((bounds.x - bounds.span / 2) / spacing) * spacing; a < bounds.x + bounds.span / 2; a += spacing) {
      ctx.beginPath(); ctx.moveTo(x(a), 0); ctx.lineTo(x(a), c.height); ctx.stroke();
    }
    const vspan = c.height / scale;
    for (let b = Math.floor((bounds.y - vspan / 2) / spacing) * spacing; b < bounds.y + vspan / 2; b += spacing) {
      ctx.beginPath(); ctx.moveTo(0, y(b)); ctx.lineTo(c.width, y(b)); ctx.stroke();
    }
    ctx.strokeStyle = '#6590a8'; ctx.lineWidth = 1.5; ctx.beginPath();
    let begun = false;
    for (const f of e.frames) {
      if (f.t > frame.t) break;
      if (!begun) { ctx.moveTo(x(f.x), y(f.y)); begun = true; } else ctx.lineTo(x(f.x), y(f.y));
    }
    ctx.stroke();
    for (const f of e.frames) {
      if (f.t > frame.t) break;
      for (const event of f.events || []) {
        if (!finite(event.x) || !finite(event.y)) continue;
        const collected = event.kind === 'capture' || (event.kind === 'patch_click' && event.outcome === 'harvest') ||
          (event.kind === 'slot_hit' && event.correct);
        const missed = event.kind === 'miss' || (event.kind === 'patch_click' && event.outcome !== 'harvest') ||
          (event.kind === 'slot_hit' && !event.correct);
        if (collected) {
          ctx.fillStyle = '#22866c'; ctx.beginPath(); ctx.arc(x(event.x), y(event.y), 3, 0, Math.PI * 2); ctx.fill();
        } else if (missed && event.t >= frame.t - 8) {
          ctx.strokeStyle = '#b9796a'; ctx.lineWidth = 1; ctx.beginPath();
          ctx.moveTo(x(event.x) - 2, y(event.y) - 2); ctx.lineTo(x(event.x) + 2, y(event.y) + 2);
          ctx.moveTo(x(event.x) - 2, y(event.y) + 2); ctx.lineTo(x(event.x) + 2, y(event.y) - 2); ctx.stroke();
        }
      }
    }
    for (const target of frame.targets || []) {
      const px = x(target.x), py = y(target.y), radius = Math.max(4, (target.sigma || e.world.sigma || .6) * 2.5 * scale);
      const empty = finite(target.stock) && target.stock === 0;
      const grad = ctx.createRadialGradient(px, py, 0, px, py, radius);
      grad.addColorStop(0, empty ? 'rgba(124,147,157,.22)' : 'rgba(78,166,193,.72)');
      grad.addColorStop(1, 'rgba(78,166,193,0)');
      ctx.fillStyle = grad; ctx.beginPath(); ctx.arc(px, py, radius, 0, Math.PI * 2); ctx.fill();
      ctx.strokeStyle = empty ? '#96a9b4' : '#578fa6'; ctx.lineWidth = 1; ctx.setLineDash([4, 3]);
      ctx.beginPath(); ctx.arc(px, py, Math.max(2, (target.capture_radius || e.world.rho_c || .6) * scale), 0, Math.PI * 2); ctx.stroke();
      ctx.setLineDash([]);
      if (e.task !== 'pool') {
        const label = e.task === 'matching' ? (target.shape || (target.id === 0 ? 'narrow' : 'broad')) :
          `patch ${Number(target.slot === undefined ? target.id : target.slot) + 1}: ${number(target.stock)}`;
        ctx.fillStyle = '#38556a'; ctx.font = '12px system-ui'; ctx.fillText(label, px + 7, py - 7);
      }
    }
    const fired = new Set(frame.fired || []), alive = new Set(frame.alive || []);
    for (const cell of e.cells) {
      if (!alive.has(cell.id)) continue;
      const p = position(cell), px = x(frame.x + p.x), py = y(frame.y + p.y);
      ctx.globalAlpha = cell.z === 0 ? .9 : .6;
      ctx.fillStyle = fired.has(cell.id) ? '#fff' : COLORS[Math.min(cell.z, 3)];
      ctx.beginPath(); ctx.arc(px, py, Math.max(1.8, .22 * scale), 0, Math.PI * 2); ctx.fill();
      if (fired.has(cell.id)) { ctx.strokeStyle = '#627789'; ctx.lineWidth = .6; ctx.stroke(); }
    }
    ctx.globalAlpha = 1; ctx.strokeStyle = '#294960'; ctx.lineWidth = 1.6;
    ctx.beginPath(); ctx.arc(x(frame.x), y(frame.y), 3.5, 0, Math.PI * 2); ctx.stroke();
    ctx.fillStyle = '#5b7384'; ctx.font = '11px system-ui';
    ctx.fillText(`Shared scale · grid ${spacing} units`, 12, c.height - 12);
    if (frame.t < 1) ctx.fillText('Single founder cell', 12, 20);
  }
  function drawTissue(card, frame) {
    const c = card.tissue, ctx = c.getContext('2d'), e = card.example;
    ctx.clearRect(0, 0, c.width, c.height);
    const alive = new Set(frame.alive || []), fired = new Set(frame.fired || []);
    const liveCells = e.cells.filter(cell => alive.has(cell.id));
    let radius = 2;
    for (const cell of e.cells) { const p = position(cell); radius = Math.max(radius, Math.abs(p.x), Math.abs(p.y)); }
    const w = c.width / 4, scale = Math.min((w - 18) / (2 * radius + 1), 11);
    for (let z = 0; z < 4; z++) {
      const cx = w * (z + .5), cy = 83;
      ctx.fillStyle = '#637789'; ctx.font = '11px system-ui'; ctx.textAlign = 'center';
      ctx.fillText(['Sense', 'Action', 'Internal 1', 'Internal 2'][z], cx, 20);
      let count = 0;
      for (const cell of liveCells) {
        if (cell.z !== z) continue;
        count++;
        const p = position(cell), x = cx + p.x * scale, y = cy - p.y * scale;
        ctx.fillStyle = fired.has(cell.id) ? '#fff' : COLORS[z];
        ctx.beginPath(); ctx.arc(x, y, Math.max(1.6, scale * .32), 0, Math.PI * 2); ctx.fill();
        ctx.strokeStyle = fired.has(cell.id) ? '#4f687b' : COLORS[z]; ctx.lineWidth = .6; ctx.stroke();
      }
      ctx.fillStyle = '#6b7f8e'; ctx.fillText(`${count} cells`, cx, 152);
    }
    ctx.textAlign = 'left';
  }
  function updateCard(card, frame) {
    const s = frame.score || {}, e = card.example;
    const metrics = e.task === 'matching' ? [
      [s.correct_choices, 'Correct choices'], [s.wrong_choices, 'Wrong choices'], [frame.stats.n, 'Living cells']
    ] : [[s.captures, 'Food collected'], [s.misses, 'Unsuccessful taps'], [frame.stats.n, 'Living cells']];
    metrics.forEach((v, i) => { card.metrics[i][0].textContent = number(v[0]); card.metrics[i][1].textContent = v[1]; });
    card.phase.textContent = phaseText(frame);
    let detail = `Energy cost ${number(s.cost, 1)} · food income ${number(s.income, 1)}`;
    if (e.task === 'contact_food') {
      const contact = s.contact_harvests;
      const passive = finite(s.refill_harvests) && finite(contact) ? s.refill_harvests - contact : undefined;
      detail = `Food: ${number(s.initial_harvests)} initial · ${number(passive)} passive refill · ${number(contact)} contact-grown`;
    }
    card.detail.textContent = detail;
    const events = (frame.events || []).filter(event =>
      ['capture', 'patch_click', 'task_resolution', 'patch_contact_start', 'patch_contact_mature'].includes(event.kind));
    card.feed.textContent = events.slice(-2).map(event => {
      const label = String(event.kind).replaceAll('_', ' ');
      return `${number(event.t, 1)}: ${label}${event.outcome === undefined ? '' : ' · ' + event.outcome}`;
    }).join(' / ') || (frame.t >= duration ? 'This recorded life has ended.' : 'Scrub the timeline to inspect growth and motion.');
    drawWorld(card, frame); drawTissue(card, frame);
  }
  function render() {
    $('timeline').value = time; $('clock').textContent = `${Math.floor(time)} / ${duration}`;
    $('play').textContent = playing ? 'Pause' : 'Play';
    for (const card of cards) updateCard(card, frameAt(card.example.frames, time));
  }
  function makeCard(example, index) {
    const card = { example }, el = node('article', 'card'), head = node('div', 'card-head');
    head.append(node('div', 'stage', index === 0 ? 'Original example' : index === 1 ? 'Early evolution' : 'Latest example'),
      node('h2', '', `Generation ${example.generation}`),
      node('div', 'identity', `Genome ${example.id} · same fixed seed`));
    card.phase = node('p', 'phase'); head.append(card.phase); el.append(head);
    card.world = node('canvas', 'world'); card.world.width = 480; card.world.height = 350;
    card.world.setAttribute('aria-label', `Generation ${example.generation}: organism, food and trajectory`); el.append(card.world);
    const metricRow = node('div', 'metrics'); card.metrics = [];
    for (let i = 0; i < 3; i++) {
      const item = node('div', 'metric'), value = node('strong'), label = node('span');
      item.append(value, label); metricRow.append(item); card.metrics.push([value, label]);
    }
    card.detail = node('div', 'detail'); el.append(metricRow, card.detail, node('div', 'tissue-title', 'Tissue layers · top view'));
    card.tissue = node('canvas', 'tissue'); card.tissue.width = 480; card.tissue.height = 170;
    card.tissue.setAttribute('aria-label', 'Four tissue layers showing living cells and recent firing');
    card.feed = node('div', 'feed'); el.append(card.tissue, card.feed); $('cards').append(el); return card;
  }
  function select() {
    playing = false; last = null;
    examples = groupExamples(data.examples, $('lineage').value, $('task').value);
    if (!examples.length) throw new Error('No saved examples for this selection.');
    bounds = worldBounds(examples); duration = Math.max(...examples.map(e => e.T));
    time = Math.min(time, duration); $('timeline').max = duration; $('task-note').textContent = NOTES[$('task').value];
    $('cards').replaceChildren(); cards = examples.map(makeCard); render();
    const query = new URLSearchParams({ lineage: $('lineage').value, task: $('task').value });
    if (typeof history !== 'undefined' && typeof location !== 'undefined') {
      try { history.replaceState(null, '', `${location.pathname}?${query}`); } catch (_) { /* file URLs may prohibit history writes */ }
    }
  }
  function animate(now) {
    if (playing && last !== null) {
      time = Math.min(duration, time + Math.min((now - last) / 1000, .2) * Number($('speed').value));
      if (time >= duration) playing = false;
      render();
    }
    last = now; requestAnimationFrame(animate);
  }
  try {
    data = JSON.parse($('example-data').textContent);
    if (!data.examples || !data.examples.length) throw new Error('The page has no saved trajectories.');
    for (const example of data.examples) for (const frame of example.frames) {
      if (!frame.alive) frame.alive = example.cells.filter(cell => cell.born <= frame.t &&
        (cell.died === null || cell.died > frame.t)).map(cell => cell.id);
    }
    const query = new URLSearchParams(typeof location === 'undefined' ? '' : location.search);
    const lineages = [...new Set(data.examples.map(e => e.lineage))];
    const tasks = [...new Set(data.examples.map(e => e.task))];
    for (const l of lineages) { const option = node('option', '', LINEAGES[l] || l); option.value = l; $('lineage').append(option); }
    for (const t of tasks) { const option = node('option', '', TASKS[t] || t); option.value = t; $('task').append(option); }
    $('lineage').value = lineages.includes(query.get('lineage')) ? query.get('lineage') :
      lineages.includes('speck_s6') ? 'speck_s6' : lineages[0];
    $('task').value = tasks.includes(query.get('task')) ? query.get('task') : tasks.includes('pool') ? 'pool' : tasks[0];
    $('lineage').addEventListener('change', select); $('task').addEventListener('change', select);
    $('timeline').addEventListener('input', () => { playing = false; time = Number($('timeline').value); render(); });
    $('play').addEventListener('click', () => { if (time >= duration) time = 0; playing = !playing; last = null; render(); });
    $('restart').addEventListener('click', () => { time = 0; playing = false; last = null; render(); });
    $('validation').textContent = typeof data.validation === 'string' ? data.validation :
      (data.validation && data.validation.description) || 'Saved examples are checked against the native simulator; details accompany the published data.';
    select(); requestAnimationFrame(animate);
  } catch (error) {
    $('error').textContent = `Unable to display the saved examples: ${error.message}`;
    $('error').style.display = 'block';
  }
})();
