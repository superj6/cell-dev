/* Diagnostic-only wrapper. Original engine and viewer bytes remain unchanged. */
'use strict';
(() => {
  const originalCreate=LifeSim.create, sims=[];
  const record={status:'initializing',initializations:0,advance_calls:0,run_calls:0,times:[],errors:[]};
  const fail=message=>{record.errors.push(String(message));throw Error(message);};
  window.addEventListener('error',event=>{record.errors.push(event.message||'browser error');});
  LifeSim.create=(...args)=>{
    if(record.initializations>=3)fail('more than three initializations');
    const sim=originalCreate(...args);record.initializations++;sims.push(sim);
    const blocked=name=>()=>{record[name+'_calls']++;fail('paused diagnostic forbids '+name);};
    sim.advance=blocked('advance');sim.run=blocked('run');
    sim.life.advance=blocked('advance');sim.life.run=blocked('run');
    return sim;
  };
  window.__AI_PAUSED_DIAGNOSTIC={finish(){
    record.times=sims.map(sim=>sim.t);
    record.aggregates=['reserve-control','control-start','reserve-start'].map(id=>({
      contrast:id,captures:document.getElementById(id+'-captures').textContent,
      fitness:document.getElementById(id+'-fitness').textContent}));
    record.status=record.initializations===3&&record.times.every(t=>t===0)&&
      record.advance_calls===0&&record.run_calls===0&&record.errors.length===0&&
      record.aggregates.every(row=>row.captures.includes('±')&&row.fitness.includes('±'))&&
      document.getElementById('error').hidden?'passed':'failed';
    document.getElementById('play').disabled=true;
    document.getElementById('restart').disabled=true;
    document.getElementById('speed').disabled=true;
    const banner=document.createElement('p');banner.id='paused-diagnostic';
    banner.style.cssText='margin:0;padding:10px 24px;background:#e5eee8;color:#203438;font:14px system-ui';
    banner.textContent='PAUSED DIAGNOSTIC · '+record.status+' · '+record.initializations+
      ' initializations · t = '+record.times.join(', ')+' · '+record.advance_calls+
      ' advance calls · '+record.run_calls+' run calls';
    document.body.prepend(banner);
    window.dump('AI_PAUSED_GUARD '+JSON.stringify(record)+'\n');
  }};
})();
