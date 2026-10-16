/* Fixed-role dispatch smoke with a supplied viewer; no engine import or simulated life. */
'use strict';
const assert = require('assert/strict'), fs = require('fs'), vm = require('vm'), path = require('path');
const fixture = { seed:52530000, doc:{supplied:true}, roles:[0,1,2,3].map(i => ({description:'role '+i})) };
const elements = Object.fromEntries(['fixture','role','description','viewer','error'].map(id =>
  [id, { value:'0', textContent:'', addEventListener(name, fn) { this[name] = fn; } }]));
elements.fixture.textContent = JSON.stringify(fixture);
const calls = []; let destroyed = 0;
const scope = vm.createContext({ document:{getElementById:id => elements[id]},
  ResourcePatchesView:{mount:(element, doc, options) => {
    assert.equal(element, elements.viewer);
    assert.equal(doc.supplied, true); assert.equal(options.seed, 52530000); assert.equal(options.hashes, false);
    calls.push(options.body); return {destroy:() => destroyed++};
  }} });
vm.runInContext(fs.readFileSync(path.join(__dirname, 'page.js'), 'utf8'), scope);
for (const i of [1,2,3]) { elements.role.value = String(i); elements.role.change(); }
assert.deepEqual(calls, [0,1,2,3]); assert.equal(destroyed, 3);
assert.equal(elements.description.textContent, 'role 3'); assert.equal(elements.error.textContent, '');
console.log(JSON.stringify({status:'passed',supplied_page_mounts:4,actual_simulator_calls:0}));
