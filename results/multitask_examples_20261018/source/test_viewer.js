'use strict';
const assert = require('assert');
const V = require('./viewer.js');
const frames = [{t:0,x:0,y:0,targets:[]},{t:8,x:1,y:2,targets:[{x:3,y:4}]},{t:16,x:2,y:1,targets:[]}];
assert.strictEqual(V.frameAt(frames, 0), frames[0]);
assert.strictEqual(V.frameAt(frames, 7.9), frames[0]);
assert.strictEqual(V.frameAt(frames, 8), frames[1]);
assert.strictEqual(V.frameAt(frames, 999), frames[2]);
const examples = [25,0,75].map(generation => ({generation,lineage:'speck_s6',task:'pool',frames,
  cells:[{id:1,a:0,b:0,z:0,x:0,y:0}]}));
assert.deepStrictEqual(V.groupExamples(examples, 'speck_s6', 'pool').map(x => x.generation), [0,25,75]);
assert.deepStrictEqual(V.groupExamples(examples, 'AO_s7', 'pool'), []);
const bounds = V.worldBounds(examples);
assert(Number.isFinite(bounds.x) && Number.isFinite(bounds.y) && bounds.span >= 12);
assert.strictEqual(V.number(undefined), '—');
assert.strictEqual(V.number(0), '0');
assert.strictEqual(V.phaseText({task_state:{phase:'blank',sample_class:'narrow'}}),
  'blank · earlier cue: narrow (observer label)');
assert.strictEqual(V.phaseText({task_state:null}), '');

// Exercise all three task displays and controls using a tiny supplied-state DOM.
const fs = require('fs'), vm = require('vm');
class Element {
  constructor(tag) { this.tag = tag; this.children = []; this.value = ''; this.style = {}; this.handlers = {}; this.textContent = ''; }
  append(...children) { this.children.push(...children); }
  replaceChildren(...children) { this.children = children; }
  addEventListener(name, fn) { this.handlers[name] = fn; }
  setAttribute() {}
  getContext() { return new Proxy({}, { get: (_, key) => key === 'createRadialGradient' ?
    () => ({addColorStop() {}}) : () => {}, set: () => true }); }
}
const elements = {};
for (const id of ['lineage','task','play','restart','speed','timeline','clock','cards','task-note','validation','error','example-data'])
  elements[id] = new Element(id === 'cards' ? 'main' : 'div');
elements.speed.value = '32';
const supplied = [];
for (const task of ['pool','contact_food','matching']) for (const generation of [0,25,75]) {
  supplied.push({key:task+generation,lineage:'speck_s6',task,generation,id:generation,T:16,world:{sigma:.6,rho_c:.5},
    cells:[{id:1,a:0,b:0,z:0,x:0,y:0,born:0,died:null}],frames:frames.map(f => ({...f,
      alive:[1],fired:[1],score:{captures:2,misses:3,correct_choices:7,wrong_choices:4,
        initial_harvests:1,refill_harvests:5,contact_harvests:2,income:100,cost:10},
      stats:{n:1,n_S:1,n_M:0,n_H:0},task_state:task === 'matching' ? {phase:'choice',sample_class:'narrow'} : null,
      events:[{t:f.t,kind:'capture',x:f.x,y:f.y}]}))});
}
elements['example-data'].textContent = JSON.stringify({examples:supplied,validation:'Supplied test data'});
const context = {document:{createElement: tag => new Element(tag),getElementById:id=>elements[id]},
  location:{search:'',pathname:'/preview.html'},history:{replaceState(){}},URLSearchParams,
  requestAnimationFrame() {}, console};
vm.runInNewContext(fs.readFileSync(require.resolve('./viewer.js'),'utf8'), context);
assert.strictEqual(elements.error.style.display, undefined, elements.error.textContent);
assert.strictEqual(elements.cards.children.length, 3);
assert.strictEqual(elements.lineage.value, 'speck_s6');
elements.task.value = 'matching'; elements.task.handlers.change();
let metricRow = elements.cards.children[0].children[2];
assert.strictEqual(metricRow.children[0].children[0].textContent, '7');
assert.strictEqual(metricRow.children[0].children[1].textContent, 'Correct choices');
elements.task.value = 'contact_food'; elements.task.handlers.change();
assert(elements.cards.children[0].children[3].textContent.includes('3 passive refill · 2 contact-grown'));
elements.restart.handlers.click();
assert.strictEqual(elements.clock.textContent, '0 / 16');
elements.play.handlers.click(); assert.strictEqual(elements.play.textContent, 'Pause');
elements.timeline.value = '8'; elements.timeline.handlers.input(); assert.strictEqual(elements.play.textContent, 'Play');
assert.strictEqual(elements.clock.textContent, '8 / 16');
if (process.argv[2]) {
  const input = fs.readFileSync(process.argv[2], 'utf8');
  const realData = JSON.parse(input.startsWith('<!doctype') ?
    input.match(/<script id="example-data" type="application\/json">([\s\S]*?)<\/script>/)[1] : input);
  for (const element of Object.values(elements)) { element.replaceChildren(); element.textContent = ''; element.style = {}; }
  elements['example-data'].textContent = JSON.stringify(realData);
  vm.runInNewContext(fs.readFileSync(require.resolve('./viewer.js'),'utf8'), context);
  assert.strictEqual(elements.error.style.display, undefined, elements.error.textContent);
  let groups = 0, displayed = 0;
  for (const lineage of [...new Set(realData.examples.map(e => e.lineage))])
    for (const task of [...new Set(realData.examples.map(e => e.task))]) {
      elements.lineage.value = lineage; elements.task.value = task; elements.task.handlers.change();
      assert.strictEqual(elements.cards.children.length, 3);
      const selected = V.groupExamples(realData.examples, lineage, task);
      for (const t of [0,128,512,1024]) {
        elements.timeline.value = String(t); elements.timeline.handlers.input();
        selected.forEach((example, i) => {
          const frame = V.frameAt(example.frames, t);
          const row = elements.cards.children[i].children[2];
          const expected = task === 'matching' ? frame.score.correct_choices : frame.score.captures;
          assert.strictEqual(row.children[0].children[0].textContent, V.number(expected));
          assert.strictEqual(row.children[2].children[0].textContent, V.number(frame.stats.n));
          displayed++;
        });
      }
      groups++;
    }
  console.log(`Actual saved data: ${groups} population/task groups, ${displayed} card/time displays checked.`);
}
console.log('Saved-frame selection, boundary, matching-label and mocked display/control checks passed; no simulator calls.');
