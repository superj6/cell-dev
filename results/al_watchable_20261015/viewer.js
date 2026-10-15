/* A fixed-world, fixed-seed illustration; no organism rules or interactive world changes. */
'use strict';
(() => {
  const data=JSON.parse(document.getElementById('comparison-data').textContent);
  const get=id=>document.getElementById(id), colors=['#187c80','#bf6835','#795b97','#795b97'];
  const state={sims:[],views:[],trails:[],playing:false,last:null,frame:null,world:'pool'};
  const number=x=>Math.round(x).toLocaleString('en-US');
  const signed=x=>(x>=0?'+':'−')+Math.abs(x).toFixed(3);
  const estimate=r=>signed(r.mean)+' ± '+(3*r.se).toFixed(3);
  function surface(id,ratio){
    const canvas=get(id),width=canvas.clientWidth||540,height=width/ratio,dpr=window.devicePixelRatio||1;
    if(canvas.width!==Math.round(width*dpr)||canvas.height!==Math.round(height*dpr)){
      canvas.width=Math.round(width*dpr);canvas.height=Math.round(height*dpr);
    }
    const ctx=canvas.getContext('2d');ctx.setTransform(dpr,0,0,dpr,0,0);
    ctx.fillStyle='#fbfcf8';ctx.fillRect(0,0,width,height);return {ctx,width,height};
  }
  function circle(ctx,x,y,r,color){ctx.beginPath();ctx.arc(x,y,r,0,Math.PI*2);ctx.fillStyle=color;ctx.fill();}
  function renderWorld(i,view){
    const {ctx,width:w,height:h}=surface('world'+i,1.45);
    const target=view.targets[0],range=Math.max(9,target?Math.hypot(target.x-view.dot.x,target.y-view.dot.y)+2:9,...view.cells.filter(c=>c.z===0).map(c=>Math.hypot(c.x,c.y)+1));
    const scale=Math.min(w,h)/(2*range),cx=w/2,cy=h/2;
    const point=(x,y)=>[cx+(x-view.dot.x)*scale,cy-(y-view.dot.y)*scale];
    ctx.strokeStyle='#edf1ea';ctx.lineWidth=1;
    for(let x=Math.floor((view.dot.x-range)/2)*2;x<=view.dot.x+range;x+=2){const p=point(x,0);ctx.beginPath();ctx.moveTo(p[0],0);ctx.lineTo(p[0],h);ctx.stroke();}
    for(let y=Math.floor((view.dot.y-range)/2)*2;y<=view.dot.y+range;y+=2){const p=point(0,y);ctx.beginPath();ctx.moveTo(0,p[1]);ctx.lineTo(w,p[1]);ctx.stroke();}
    for(const [key,color] of [['body','#7a908e'],['target','#9bc99c']]){
      const trail=state.trails[i][key];ctx.beginPath();ctx.strokeStyle=color;ctx.lineWidth=1.5;
      trail.forEach((p,j)=>{const xy=point(p.x,p.y);j?ctx.lineTo(...xy):ctx.moveTo(...xy);});ctx.stroke();
    }
    if(target){const p=point(target.x,target.y);circle(ctx,...p,Math.max(3,scale*.6),'#d8ebd2');circle(ctx,...p,Math.max(2.5,scale*.14),'#41994b');}
    for(const cell of view.cells.filter(c=>c.z===0)){
      circle(ctx,cx+cell.x*scale,cy-cell.y*scale,Math.max(1,scale*.35),view.t-cell.lastSpike<1.5?'#dc424e':colors[0]);
    }
    circle(ctx,cx,cy,2,'#203438');
    ctx.fillStyle='#526766';ctx.font='11px system-ui';ctx.textAlign='left';
    ctx.fillText('Camera follows body · width '+(w/scale).toFixed(0)+' world units',12,h-12);
  }
  function renderTissue(i,view){
    const {ctx,width:w,height:h}=surface('tissue'+i,3.9),pw=w/4;
    const radius=Math.max(4,...view.cells.map(c=>Math.max(Math.abs(c.x),Math.abs(c.y))+1));
    const scale=Math.min(pw-12,h-27)/(2*radius),names=['Sensors','Motors','Hidden 2','Hidden 3'];
    for(let z=0;z<4;z++){
      const cells=view.cells.filter(c=>c.z===z),cx=pw*(z+.5),cy=(h-24)/2;
      for(const c of cells)circle(ctx,cx+c.x*scale,cy-c.y*scale,Math.max(1,scale*.36),view.t-c.lastSpike<1.5?'#dc424e':colors[z]);
      ctx.fillStyle='#526766';ctx.font='10px system-ui';ctx.textAlign='center';ctx.fillText(names[z]+' · '+cells.length,cx,h-8);
    }
  }
  function render(){
    state.views.forEach((view,i)=>{
      renderWorld(i,view);renderTissue(i,view);
      get('time'+i).textContent='t = '+Math.floor(view.t);
      get('captures'+i).textContent=number(view.score.captures);get('cells'+i).textContent=number(view.stats.n);
      get('spikes'+i).textContent=number(view.stats.spikes);
    });
  }
  function read(){
    state.views=state.sims.map(sim=>sim.state());
    state.views.forEach((view,i)=>{
      if(view.events.some(event=>event.kind==='place'))state.trails[i].target=[];
      for(const [key,item] of [['body',view.dot],['target',view.targets[0]]]){
        if(!item)continue;const trail=state.trails[i][key],last=trail[trail.length-1];
        if(!last||view.t>last.t){trail.push({t:view.t,x:item.x,y:item.y});while(trail.length>350||trail[0].t<view.t-60)trail.shift();}
      }
    });
  }
  function syncButtons(){
    const ended=state.sims.every(s=>s.ended);get('play').textContent=state.playing?'Pause':'Play';
    get('play').setAttribute('aria-pressed',String(state.playing));get('play').disabled=ended;
    get('status').textContent=ended?'This illustrative life is complete. Restart the same fixed seed.':state.playing?'Running all three lives. The camera follows each body.':'Paused. Press Play to grow all three bodies. The camera follows each body.';
  }
  function fail(error){state.playing=false;get('error').hidden=false;get('error').textContent='The comparison stopped: '+error.message;syncButtons();}
  function frame(now){
    state.frame=null;
    try{
      if(state.playing){
        const dt=state.last===null?0:Math.min(.05,(now-state.last)/1000);
        const target=Math.min(...state.sims.filter(s=>!s.ended).map(s=>s.t))+dt*Number(get('speed').value);
        const start=performance.now();
        for(const sim of state.sims){let loops=0;while(!sim.ended&&sim.t<target&&loops++<10000){sim.advance(Math.min(.5,target-sim.t),1500);if(performance.now()-start>9)break;}}
        read();if(state.sims.every(s=>s.ended))state.playing=false;
      }
      state.last=now;render();syncButtons();if(state.playing)kick();
    }catch(error){fail(error);}
  }
  function kick(){if(state.frame===null)state.frame=requestAnimationFrame(frame);}
  function restart(){
    state.playing=false;state.last=null;get('error').hidden=true;
    const indices=data.world_groups[state.world];
    state.sims=indices.map(body=>LifeSim.create(data,{body,seed:data.seed,abi:3,mode:'auto',hashes:false,raster:0}));
    state.trails=indices.map(()=>({body:[],target:[]}));read();
    const result=data.summary;
    for(const world of ['pool','persistent']){
      for(const role of ['AI_control_start','persistent_control_final','mixture_final']){
        const row=result.absolute[world][role];
        for(const metric of ['captures','F','ordinary_cost']){
          const value=row[metric];
          get('absolute-'+world+'-'+role+'-'+metric).textContent=estimate({mean:metric==='ordinary_cost'?-value.mean:value.mean,se:value.se});
        }
      }
      for(const [newer,older] of [['persistent_control_final','AI_control_start'],['mixture_final','AI_control_start'],['mixture_final','persistent_control_final']]){
        const name=newer+'_minus_'+older,row=result.contrasts['within__'+world+'__'+name];
        for(const metric of ['captures','F','capture_income','ordinary_cost'])get('contrast-'+world+'-'+name+'-'+metric).textContent=estimate(row[metric]);
      }
    }
    for(const world of ['pool','persistent'])get('tab-'+world).setAttribute('aria-pressed',String(world===state.world));
    get('world-description').textContent=state.world==='pool'?
      'Original POOL settings: target speed 0.1, mean interval between turns 20.':
      'Persistent target: speed 0.3, mean interval between turns 200. The target moves faster with longer straight segments; several other physical settings also differ from POOL.';
    render();syncButtons();
  }
  get('play').addEventListener('click',()=>{state.playing=!state.playing;state.last=null;syncButtons();kick();});
  get('restart').addEventListener('click',restart);
  for(const world of ['pool','persistent'])get('tab-'+world).addEventListener('click',()=>{state.world=world;restart();});
  window.addEventListener('resize',()=>render());
  document.addEventListener('visibilitychange',()=>{if(document.hidden){state.playing=false;state.last=null;syncButtons();}});
  try{restart();}catch(error){fail(error);}
})();
