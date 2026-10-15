/* Later authorized engineering check only: three existing AI lives, no new evidence. */
'use strict';
const fs=require('fs'),path=require('path'),crypto=require('crypto');
if(process.env.CELL_DEV_VIEWER_VALIDATION!=='AI_three_existing_lives')throw Error('use the authorized bounded validation wrapper');
const root=path.resolve(__dirname,'../..');
const data=JSON.parse(fs.readFileSync(path.join(__dirname,'bodies.json'),'utf8'));
const truth=JSON.parse(fs.readFileSync(path.join(__dirname,'truth.json'),'utf8'));
const origins=JSON.parse(fs.readFileSync(path.join(__dirname,'source_origins.json'),'utf8'));
const engine=path.join(root,origins.unchanged_engine.path);
if(crypto.createHash('sha256').update(fs.readFileSync(engine)).digest('hex')!==origins.unchanged_engine.sha256)throw Error('changed engine');
if(data.seed!==52360000||truth.seed!==52360000||data.bodies.length!==3||truth.cases.length!==3||truth.ledger.length!==57)throw Error('fixed scope differs');
if(data.bodies.map(b=>b.name).join(',')!=='AE_L92,AI_control,AI_reserve')throw Error('role order differs');
const LifeSim=require(engine),bits=x=>{const b=Buffer.alloc(8);b.writeDoubleLE(x);return b.toString('hex');},rows=[];
for(let body=0;body<3;body++){
  if(truth.cases[body].role!==data.bodies[body].name)throw Error('truth role differs');
  const sim=LifeSim.create(data,{body,seed:data.seed,abi:3,mode:'auto',hashes:false,raster:0});
  let frames=0;
  while(!sim.ended){sim.advance(2,3000);sim.state();if(++frames>100000)throw Error('unexpected frame limit');}
  const raw=Array.from(sim.life.led),wanted=truth.cases[body].ledger;
  if(raw.length!==57||wanted.length!==57)throw Error('raw ledger shape differs');
  const bad=truth.ledger.filter((name,i)=>bits(raw[i])!==bits(wanted[i]));
  if(bad.length)throw Error(data.bodies[body].name+' ledger mismatch '+bad.join(','));
  rows.push({role:data.bodies[body].name,seed:data.seed,ledger_columns_bitwise_equal:57,frames,
             captures:sim.ledger().captures,status:sim.ledger().status});
}
console.log(JSON.stringify({status:'complete',js_replay_lives:3,new_C_lives:0,new_research_lives:0,rows},null,2));
