'use strict';
try {
  const fixture = JSON.parse(document.getElementById('fixture').textContent);
  const select = document.getElementById('role');
  let current;
  const show = () => {
    const body = Number(select.value);
    if (!Number.isInteger(body) || body < 0 || body > 3) throw new Error('Unknown fixed genome');
    if (current) current.destroy();
    document.getElementById('description').textContent = fixture.roles[body].description;
    current = ResourcePatchesView.mount(document.getElementById('viewer'), fixture.doc,
      { body, seed:fixture.seed, hashes:false, speed:8 });
  };
  select.addEventListener('change', show);
  show();
} catch (cause) { document.getElementById('error').textContent = cause.message; }
