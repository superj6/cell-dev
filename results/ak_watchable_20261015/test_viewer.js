/* UI control checks use a small deterministic mock; no engine lives are run. */
'use strict';
const fs=require('fs'),path=require('path'),vm=require('vm'),assert=require('assert');
// Synthetic values only: no AK file, genotype or real simulator is read.
const metric=mean=>({mean,se:.1});
const absolute={},contrasts={};
for(const world of ['pool','persistent']){
  absolute[world]={};
  for(const role of ['L92','AE_L92','AI_control'])absolute[world][role]={captures:metric(5),F:metric(1),ordinary_cost:metric(-2)};
  for(const [newer,older] of [['AE_L92','L92'],['AI_control','L92'],['AI_control','AE_L92']])contrasts['within__'+world+'__'+newer+'_minus_'+older]={captures:metric(world==='pool'?-.4:.6),F:metric(.2),capture_income:metric(.3),ordinary_cost:metric(-.1)};
}
const data={abi:3,seed:52380000,bodies:['pool','persistent'].flatMap(world=>['L92','AE_L92','AI_control'].map(role=>({name:world+'__'+role}))),world_groups:{pool:[0,1,2],persistent:[3,4,5]},summary:{absolute,contrasts}};
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
    check(doc.seed===52380000&&opts.seed===52380000,'fixed existing seed');check(opts.abi===3&&opts.mode==='auto','unchanged world mode');
    check(!('flags' in opts)&&!('targets' in opts),'no world interventions');
    const sim={t:0,ended:false,advance(dt){this.t=Math.min(4,this.t+dt);this.ended=this.t===4;},state(){return {t:this.t,ended:this.ended,dot:{x:this.t/4,y:0},targets:[{x:3+this.t/4,y:2}],
      cells:[0,1,2,3].map(z=>({z,x:z%2,y:0,lastSpike:-100})),events:[],score:{captures:Math.floor(this.t)},stats:{n:4,spikes:Math.floor(this.t*10)}};}};
    created.push({body:opts.body,sim});return sim;}};
  const ctx=vm.createContext({LifeSim:fake,document:{hidden:false,getElementById:node,addEventListener:(k,v)=>documentEvents[k]=v},
    window:{devicePixelRatio:2,addEventListener:(k,v)=>windowEvents[k]=v},performance:{now:()=>now+=.1},
    requestAnimationFrame:fn=>{queue.push(fn);return queue.length;},console});
  vm.runInContext(source,ctx);
  check(created.map(x=>x.body).join(',')==='0,1,2','fixed lineage order in initial POOL world');
  check(node('play').textContent==='Play'&&node('play').attrs['aria-pressed']==='false','starts paused');
  check(node('contrast-pool-AI_control_minus_L92-captures').textContent==='−0.400 ± 0.300','negative aggregate effect remains visible');
  check(node('contrast-persistent-AI_control_minus_AE_L92-captures').textContent==='+0.600 ± 0.300','positive persistent effect remains visible');
  check(node('absolute-pool-L92-ordinary_cost').textContent==='+2.000 ± 0.300','absolute physical cost is positive');
  function frame(){const fn=queue.shift();if(fn)fn(now+=17);}
  node('play').events.click();frame();frame();check(created.every(x=>x.sim.t>0),'play advances all three views');
  node('play').events.click();const paused=created[0].sim.t;frame();check(created[0].sim.t===paused,'pause stops progress');
  node('play').events.click();ctx.document.hidden=true;documentEvents.visibilitychange();frame();check(node('play').attrs['aria-pressed']==='false','hidden tab pauses');
  ctx.document.hidden=false;node('restart').events.click();check(created.slice(-3).map(x=>x.body).join(',')==='0,1,2','restart preserves all fixed roles');
  node('tab-persistent').events.click();
  check(created.slice(-3).map(x=>x.body).join(',')==='3,4,5','world switch uses the same three roles in persistent world');
  check(node('tab-persistent').attrs['aria-pressed']==='true'&&node('tab-pool').attrs['aria-pressed']==='false','world selection is announced');
  check(created.slice(-3).every(x=>x.sim.t===0),'world change starts paused at time zero');
  check(node('contrast-pool-AI_control_minus_L92-captures').textContent==='−0.400 ± 0.300','world tab does not hide negative aggregate');
  windowEvents.resize();check(node('world0').width===width*2,'canvas adapts to screen width');
  node('play').events.click();for(let i=0;i<30&&queue.length;i++)frame();check(node('play').disabled,'completed life disables play');
  node('restart').events.click();check(!node('play').disabled&&node('captures0').textContent==='0','restart resets displayed life');
  check(numericCalls>100,'world and all tissue panels draw');
  return {width,numericCanvasArgumentsChecked:numericCalls,createdMockLives:created.length};
}
const layouts=[run(540),run(330)];console.log(JSON.stringify({status:'passed',assertions,layouts,realEngineLives:0},null,2));
