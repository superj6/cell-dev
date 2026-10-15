'use strict';
const fs=require('fs'),path=require('path');
const root=path.resolve(__dirname,'../..');
const LifeSim=require(path.join(root,'results/atlas/play/lifesim.js'));
const data=JSON.parse(fs.readFileSync(path.join(__dirname,'bodies.json'),'utf8'));
const truth=JSON.parse(fs.readFileSync(path.join(__dirname,'truth.json'),'utf8'));
const bits=x=>{const b=Buffer.alloc(8);b.writeDoubleLE(x);return b.toString('hex');};
const rows=[];
for(let body=0;body<4;body++){
  const sim=LifeSim.create(data,{body,seed:data.seed,abi:3,mode:'auto',hashes:false,raster:0});
  let frames=0;
  while(!sim.ended){sim.advance(2,3000);sim.state();if(++frames>100000)throw Error('unexpected frame limit');}
  const raw=Array.from(sim.life.led),wanted=truth.cases[body].ledger;
  const bad=truth.ledger.filter((name,i)=>bits(raw[i])!==bits(wanted[i]));
  if(bad.length)throw Error(data.bodies[body].name+' ledger mismatch '+bad.join(','));
  rows.push({role:data.bodies[body].name,seed:data.seed,ledger_columns_bitwise_equal:raw.length,frames,
             captures:sim.ledger().captures,status:sim.ledger().status});
}
console.log(JSON.stringify({status:'complete',js_replay_lives:4,new_C_lives:0,new_research_lives:0,rows},null,2));
