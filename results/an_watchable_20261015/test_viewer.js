/* UI control checks use a small deterministic mock; no engine lives are run. */
'use strict';
const fs=require('fs'),path=require('path'),vm=require('vm'),assert=require('assert');
// Synthetic values only: no AN file, genotype or real simulator is read.
const metric=mean=>({mean,se:.1});
const absolute={},contrasts={};
for(const world of ['persistent','blink80_20']){
  absolute[world]={};
  for(const role of ['AM_current_start','generation4','generation8'])absolute[world][role]={captures:metric(5),F:metric(1),ordinary_cost:metric(-2)};
  for(const [newer,older] of [['generation4','AM_current_start'],['generation8','AM_current_start'],['generation8','generation4']])contrasts['within__'+world+'__'+newer+'_minus_'+older]={captures:metric(world==='persistent'?-.4:.6),F:metric(.2),capture_income:metric(.3),ordinary_cost:metric(-.1)};
}
const data={abi:4,seed:52410000,bodies:['persistent','blink80_20'].flatMap(world=>['AM_current_start','generation4','generation8'].map(role=>({name:world+'__'+role,abi:world==='persistent'?3:4}))),world_groups:{persistent:[0,1,2],blink80_20:[3,4,5]},summary:{absolute,contrasts}};
const source=fs.readFileSync(path.join(__dirname,'viewer.js'),'utf8');
let assertions=0;
function check(value,message){assert(value,message);assertions++;}
function run(width){
  const ids=new Map(),queue=[],documentEvents={},windowEvents={},created=[];let now=0,numericCalls=0;
  const context=new Proxy({},{get:(o,k)=>{if(k in o)return o[k];return (...args)=>{for(const x of args)if(typeof x==='number'){assert(Number.isFinite(x),'nonfinite canvas coordinate');numericCalls++;}};},set:(o,k,v)=>{o[k]=v;return true;}});
  function node(id){if(!ids.has(id))ids.set(id,{id,textContent:'',value:'',hidden:false,disabled:false,attrs:{},events:{},clientWidth:width,width:0,height:0,
    addEventListener(k,fn){this.events[k]=fn;},setAttribute(k,v){this.attrs[k]=v;},getContext(){return context;}});return ids.get(id);}
  node('comparison-data').textContent=JSON.stringify(data);node('speed').value='120';
  const fake={create(doc,opts){
    check(doc.seed===52410000&&opts.seed===52410000,'fixed existing seed');check(opts.abi===(opts.body<3?3:4)&&opts.mode==='auto','unchanged per-world ABI and mode');
    check(!('flags' in opts)&&!('targets' in opts),'no world interventions');
    const sim={t:0,ended:false,life:{visibility_bright:true},advance(dt){this.t=Math.min(4,this.t+dt);this.ended=this.t===4;this.life.visibility_bright=opts.body<3||this.t<2;},state(){return {t:this.t,ended:this.ended,dot:{x:this.t/4,y:0},targets:[{x:3+this.t/4,y:2}],
      cells:[0,1,2,3].map(z=>({z,x:z%2,y:0,lastSpike:-100})),events:[],score:{captures:Math.floor(this.t)},stats:{n:4,spikes:Math.floor(this.t*10)}};}};
    created.push({body:opts.body,sim});return sim;}};
  const ctx=vm.createContext({LifeSim:fake,document:{hidden:false,getElementById:node,addEventListener:(k,v)=>documentEvents[k]=v},
    window:{devicePixelRatio:2,addEventListener:(k,v)=>windowEvents[k]=v},performance:{now:()=>now+=.1},
    requestAnimationFrame:fn=>{queue.push(fn);return queue.length;},console});
  vm.runInContext(source,ctx);
  check(created.map(x=>x.body).join(',')==='0,1,2','fixed lineage order in initial steady persistent world');
  check(node('play').textContent==='Play'&&node('play').attrs['aria-pressed']==='false','starts paused');
  check(node('contrast-persistent-generation8_minus_AM_current_start-captures').textContent==='−0.400 ± 0.300','negative aggregate effect remains visible');
  check(node('contrast-blink80_20-generation8_minus_generation4-captures').textContent==='+0.600 ± 0.300','positive blinking effect remains visible');
  check(node('absolute-persistent-AM_current_start-ordinary_cost').textContent==='+2.000 ± 0.300','absolute physical cost is positive');
  function frame(){const fn=queue.shift();if(fn)fn(now+=17);}
  node('play').events.click();frame();frame();check(created.every(x=>x.sim.t>0),'play advances all three views');
  node('play').events.click();const paused=created[0].sim.t;frame();check(created[0].sim.t===paused,'pause stops progress');
  node('play').events.click();ctx.document.hidden=true;documentEvents.visibilitychange();frame();check(node('play').attrs['aria-pressed']==='false','hidden tab pauses');
  ctx.document.hidden=false;node('restart').events.click();check(created.slice(-3).map(x=>x.body).join(',')==='0,1,2','restart preserves all fixed roles');
  node('tab-blink80_20').events.click();
  check(created.slice(-3).map(x=>x.body).join(',')==='3,4,5','world switch uses the same three roles in blink80_20 world');
  check(node('tab-blink80_20').attrs['aria-pressed']==='true'&&node('tab-persistent').attrs['aria-pressed']==='false','world selection is announced');
  check(created.slice(-3).every(x=>x.sim.t===0),'world change starts paused at time zero');
  check(node('contrast-persistent-generation8_minus_AM_current_start-captures').textContent==='−0.400 ± 0.300','world tab does not hide negative aggregate');
  windowEvents.resize();check(node('world0').width===width*2,'canvas adapts to screen width');
  node('play').events.click();for(let i=0;i<30&&queue.length;i++)frame();check(node('play').disabled,'completed life disables play');
  check(node('cue0').textContent==='Target signal off · background remains','off-cue annotation is shown without hiding the observer target');
  node('restart').events.click();check(!node('play').disabled&&node('captures0').textContent==='0','restart resets displayed life');
  check(numericCalls>100,'world and all tissue panels draw');
  return {width,numericCanvasArgumentsChecked:numericCalls,createdMockLives:created.length};
}
const layouts=[run(540),run(330)];console.log(JSON.stringify({status:'passed',assertions,layouts,realEngineLives:0},null,2));
