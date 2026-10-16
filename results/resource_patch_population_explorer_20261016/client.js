'use strict';
(() => {
  const data = JSON.parse(document.getElementById('data').textContent);
  const groups = {
    G8:{name:'G8 survivors · initial 8 generations',short:'G8 survivors',color:'#31688e'},
    mean4:{name:'4 more generations · ordinary selection',short:'Ordinary-selection survivors',color:'#d17613'},
    pareto4:{name:'4 more generations · acquisition-aware selection',short:'Acquisition-aware survivors',color:'#7b3294'},
    AO:{name:'AO · ancestral pursuit reference',short:'AO reference',color:'#17202c'}
  };
  const tasks = {patch:'Trained food patches',pool:'Ancestral food task (POOL)',persistent:'Persistent pursuit',
    blink80_20:'Pursuit with longer cue gaps',transfer:'Revealed two-patch arrangement'};
  const ns='http://www.w3.org/2000/svg', points=[], overlays=[];
  const picker=document.getElementById('row'), details=document.getElementById('details');
  let selected=null, hovered=null, focused=null;
  const rowById = id => id === null ? null : data.rows.find(r=>r.index===id);
  const number = value => Number(value).toFixed(2);
  const stat = value => `${number(value.mean)} ± ${number(value.se)}`;
  const name = row => row.group==='AO' ? 'AO reference' : `${groups[row.group].short} · row ${row.row}`;
  const svg = (tag,attrs={},text=null) => {
    const node=document.createElementNS(ns,tag);
    for(const [key,value] of Object.entries(attrs)) node.setAttribute(key,String(value));
    if(text!==null) node.textContent=text;
    return node;
  };
  function star(x,y,r=7) {
    return Array.from({length:10},(_,i)=>{
      const a=i*Math.PI/5-Math.PI/2, radius=i%2?r*.42:r;
      return `${x+Math.cos(a)*radius},${y+Math.sin(a)*radius}`;
    }).join(' ');
  }
  function range(world) {
    const values=data.rows.map(r=>r.values[world].captures);
    const lo=Math.min(...values.map(v=>v.mean-v.se)),hi=Math.max(...values.map(v=>v.mean+v.se));
    const gap=Math.max((hi-lo)*.08,.15);
    return [Math.max(0,lo-gap),hi+gap];
  }
  const xRange=range('patch');
  for(const [key,group] of Object.entries(groups)) {
    const entry=document.createElement('span');entry.className='key';
    const symbol=document.createElement('span');symbol.className=key==='AO'?'':'dot';
    symbol.style.backgroundColor=key==='AO'?'transparent':group.color;
    if(key==='AO') symbol.textContent='★';
    entry.append(symbol,document.createTextNode(group.name));document.getElementById('legend').append(entry);
    const optionGroup=document.createElement('optgroup');optionGroup.label=group.name;
    for(const row of data.rows.filter(r=>r.group===key)) {
      const option=document.createElement('option');option.value=row.index;
      option.textContent=`${row.label} · native ID ${row.native_id}${row.reported_endpoint?' · historical reference':''}`;
      optionGroup.append(option);
    }
    picker.append(optionGroup);
  }
  const ao=data.rows.find(r=>r.group==='AO');
  for(const world of data.worlds.slice(1)) {
    const box=document.createElement('section');box.className='plot';
    const title=document.createElement('h2');title.textContent=tasks[world];box.append(title);
    const chart=svg('svg',{viewBox:'0 0 430 305',role:'group','aria-label':`Patch captures versus ${tasks[world]} captures`});
    const margin={l:50,r:17,t:16,b:45},W=430-margin.l-margin.r,H=305-margin.t-margin.b,yRange=range(world);
    const X=v=>margin.l+(v-xRange[0])/(xRange[1]-xRange[0])*W;
    const Y=v=>margin.t+H-(v-yRange[0])/(yRange[1]-yRange[0])*H;
    for(let tick=0;tick<=4;tick++) {
      const x=xRange[0]+(xRange[1]-xRange[0])*tick/4,y=yRange[0]+(yRange[1]-yRange[0])*tick/4;
      chart.append(svg('line',{x1:X(x),x2:X(x),y1:margin.t,y2:margin.t+H,class:'grid'}));
      chart.append(svg('line',{x1:margin.l,x2:margin.l+W,y1:Y(y),y2:Y(y),class:'grid'}));
      chart.append(svg('text',{x:X(x),y:margin.t+H+17,'text-anchor':'middle',class:'tick'},x.toFixed(1)));
      chart.append(svg('text',{x:margin.l-8,y:Y(y)+3,'text-anchor':'end',class:'tick'},y.toFixed(1)));
    }
    chart.append(svg('line',{x1:X(ao.values.patch.captures.mean),x2:X(ao.values.patch.captures.mean),
      y1:margin.t,y2:margin.t+H,class:'reference'}));
    chart.append(svg('line',{x1:margin.l,x2:margin.l+W,y1:Y(ao.values[world].captures.mean),
      y2:Y(ao.values[world].captures.mean),class:'reference'}));
    chart.append(svg('text',{x:margin.l+W/2,y:298,'text-anchor':'middle',class:'axis-label'},'Food-patch captures per life'));
    chart.append(svg('text',{transform:`translate(12 ${margin.t+H/2}) rotate(-90)`,'text-anchor':'middle',
      class:'axis-label'},'Task captures per life'));
    for(const row of data.rows) {
      const x=X(row.values.patch.captures.mean),y=Y(row.values[world].captures.mean),group=groups[row.group];
      const g=svg('g',{class:'point',tabindex:0,role:'button','data-row':row.index,
        'aria-label':`${name(row)}, native ID ${row.native_id}; patch ${stat(row.values.patch.captures)}, `+
        `${tasks[world]} ${stat(row.values[world].captures)}. Select to link all plots.`});
      g.append(svg('circle',{cx:x,cy:y,r:9,fill:'transparent'}));
      if(row.reported_endpoint&&row.group!=='AO') g.append(svg('circle',{cx:x,cy:y,r:8,stroke:group.color,class:'fixed'}));
      const marker=row.group==='AO'?svg('polygon',{points:star(x,y),fill:group.color,class:'marker'}):
        svg('circle',{cx:x,cy:y,r:3.6,fill:group.color,'fill-opacity':.7,class:'marker'});
      g.append(marker,svg('title',{},`${row.label} · native ID ${row.native_id}`));
      g.addEventListener('mouseenter',()=>{hovered=row.index;update();});
      g.addEventListener('mouseleave',()=>{hovered=null;update();});
      g.addEventListener('focus',()=>{focused=row.index;update();});
      g.addEventListener('blur',()=>{focused=null;update();});
      const choose=()=>{selected=row.index;picker.value=String(selected);update();};
      g.addEventListener('click',choose);
      g.addEventListener('keydown',event=>{if(event.key==='Enter'||event.key===' '){event.preventDefault();choose();}});
      chart.append(g);points.push({node:g,index:row.index,marker});
    }
    const overlay=svg('g',{'pointer-events':'none'});chart.append(overlay);overlays.push({node:overlay,world,X,Y});
    box.append(chart);document.getElementById('plots').append(box);
  }
  function update() {
    const active=hovered??focused??selected,row=rowById(active);
    for(const point of points) {
      point.node.style.opacity=active===null||point.index===active?'1':'.27';
      point.node.setAttribute('aria-pressed',String(point.index===selected));
    }
    for(const plot of overlays) {
      plot.node.replaceChildren();if(!row) continue;
      const x=row.values.patch.captures,y=row.values[plot.world].captures;
      plot.node.append(svg('line',{x1:plot.X(x.mean-x.se),x2:plot.X(x.mean+x.se),y1:plot.Y(y.mean),
        y2:plot.Y(y.mean),class:'uncertainty'}));
      plot.node.append(svg('line',{x1:plot.X(x.mean),x2:plot.X(x.mean),y1:plot.Y(y.mean-y.se),
        y2:plot.Y(y.mean+y.se),class:'uncertainty'}));
      plot.node.append(svg('circle',{cx:plot.X(x.mean),cy:plot.Y(y.mean),r:10.5,class:'halo'}));
    }
    if(!row) {details.innerHTML='<h2>Follow one genome</h2><p class="empty">Hover or focus a point, or choose a row above. '+
      'Its values and uncertainty appear here while the same genome lights up in every plot.</p>'+
      '<p>All 97 fixed rows remain visible. The menu distinguishes overlapping points and repeated genomes.</p>';return;}
    const historical=row.group==='AO'?'Unchanged ancestral reference':row.reported_endpoint?
      'Historical reporting genome':'Retained survivor · not a historical reporting endpoint';
    const table=(metric,title)=>`<div class="table-wrap"><table><caption>${title} · mean ± SE</caption>`+
      '<thead><tr><th>Task</th><th>Value</th></tr></thead><tbody>'+data.worlds.map(world=>
      `<tr><td>${tasks[world]}</td><td>${stat(row.values[world][metric])}</td></tr>`).join('')+'</tbody></table></div>';
    details.innerHTML=`<h2>${name(row)}</h2><div class="meta">${row.label} · native ID ${row.native_id}</div>`+
      `<div class="badge">${historical}</div>`+table('captures','Food captures per life')+
      `<p><strong>Fresh development rank: ${row.fresh_rank} of ${row.group==='AO'?1:32}.</strong> `+
      (row.cached_rank===null?'Cached selection rank unavailable.':`Cached selection rank: ${row.cached_rank} of 32.`)+
      ` Joint minimum capture fraction: ${row.fresh_joint_minimum.toFixed(3)}. This is a descriptive ranking, `+
      'not a newly certified endpoint.</p><details><summary>Fitness, energy costs and refilled food</summary>'+
      table('F','Ordinary fitness')+table('cost','Physical energy cost')+table('total_patch_refill_harvest','Refilled food packets')+
      `</details><details><summary>Exact genome identity</summary><p>Global row ${row.index}; group ${row.group}; `+
      `local row ${row.row}; native ID ${row.native_id}.</p><code>${row.raw_sha256}</code></details>`;
  }
  picker.addEventListener('change',()=>{selected=picker.value===''?null:Number(picker.value);hovered=focused=null;update();});
  document.getElementById('clear').addEventListener('click',()=>{selected=hovered=focused=null;picker.value='';update();});
  document.addEventListener('keydown',event=>{if(event.key==='Escape'){selected=hovered=focused=null;picker.value='';update();}});
  for(const [file,pin] of Object.entries(data.source_pins)) {
    const paragraph=document.createElement('p');paragraph.textContent=`${file} · SHA256 ${pin}`;
    document.getElementById('provenance').append(paragraph);
  }
  update();
})();
