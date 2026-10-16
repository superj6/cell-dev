/* Fixed observed lineage cases; no target dragging, world editing, or seed search. */
'use strict';
(() => {
  const data = JSON.parse(document.getElementById('comparison-data').textContent);
  const get = id => document.getElementById(id);
  const roles = ['AO_start', 'mixed8', 'mixed24'];
  if (data.roles.join(',') !== roles.join(',') || data.seeds.length !== 4 || data.bodies.length !== 3)
    throw new Error('Expected three fixed genomes and the first four confirmation seeds');
  let mounted = null;
  for (const [i, role] of roles.entries()) {
    const option = document.createElement('option'); option.value = String(i); option.textContent = role;
    get('role').append(option);
  }
  for (const seed of data.seeds) {
    const option = document.createElement('option'); option.value = String(seed); option.textContent = String(seed);
    get('seed').append(option);
  }
  function reset() {
    get('error').textContent = '';
    try {
      const body = Number(get('role').value), seed = Number(get('seed').value);
      if (!Number.isInteger(body) || body < 0 || body >= 3 || !data.seeds.includes(seed))
        throw new Error('Choose one of the fixed exported cases');
      if (mounted) mounted.destroy();
      mounted = DelayedMatchView.mount(get('viewer'), data, { body, seed, abi: 5, mode: 'auto', speed: 6,
        hashes: false, raster: 0 });
      const record = data.recorded.find(row => row.role === roles[body] && row.seed === seed);
      if (!record) throw new Error('Missing retained confirmation result');
      get('recorded').textContent = 'Recorded endpoint for this case: native F ' + record.native_F.toFixed(4) +
        ' · production F ' + record.production_F.toFixed(4) + ' · extinction surcharge ' +
        record.extinct_charge.toFixed(4) + ' F · native status ' + record.status + '.';
      get('genome').textContent = 'Genome ' + roles[body] + ' · SHA256 ' + data.bodies[body].genotype_sha256;
    } catch (error) { get('error').textContent = error.message; }
  }
  get('role').addEventListener('change', reset);
  get('seed').addEventListener('change', reset);
  reset();
})();
