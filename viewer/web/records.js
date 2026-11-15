(() => {
  let page=0,checked=new Set(),auditRows=new Map(),states=new Map(),busy=false,cancel=false,fieldTask=null,metadataReady=false,followLive=true,latestSequence=null;const preparedJobs=new Map();
  const tools=document.querySelector('#record-tools'),summary=document.querySelector('#record-summary');
  tools.innerHTML='<div class="controls"><label>Find an observation<input id="record-filter" placeholder="Observation ID, detector, release or status"></label><label>Records per page<select id="record-size"><option>25</option><option>50</option><option>100</option></select></label></div><div class="row record-actions"><button type="button" id="record-selected" class="secondary">Load selected cutouts</button><button type="button" id="record-mosaic" class="secondary">Build spatial mosaic from selected</button><button type="button" id="record-all" class="secondary">Load every result progressively</button><button type="button" id="record-stop" class="secondary" disabled>Stop after current cutout</button><button type="button" id="record-follow" class="secondary">Show latest assembled timeline</button><button type="button" id="record-audit" class="secondary">Review cached metadata & coverage</button></div><p class="small">Loading retrieves real pixel regions for this field. Every result can be requested; different wavelengths remain exploratory. Stop prevents further requests after the current cutout. The field download persists on the server if you close the tab; reopen its URL to inspect it. Load every result also resumes an interrupted job for the same records. This does not download the all-sky archive.</p>';
  const text=(tag,value)=>{const el=document.createElement(tag);el.textContent=value;return el;};
  const getState=r=>states.get(r.id)||auditRows.get(r.id)?.status||'not_attempted';
  function render(){
    const out=document.querySelector('#results');out.replaceChildren();if(!metadataReady){out.textContent='Loading the observation list…';summary.textContent='Loading metadata; the record count is not known yet.';return;}
    const needle=document.querySelector('#record-filter').value.toLowerCase(),size=Number(document.querySelector('#record-size').value);
    const filtered=rows.slice().sort((a,b)=>Number(a.t_min)-Number(b.t_min)).filter(r=>[r.obs_id,r.energy_bandpassname,r.obs_collection,getState(r)].join(' ').toLowerCase().includes(needle));
    page=Math.min(page,Math.max(0,Math.ceil(filtered.length/size)-1));
    summary.textContent=`${rows.length} metadata records returned · ${filtered.length} listed by current text filter · ${checked.size} selected · ${rows.filter(r=>getState(r)==='prepared').length} prepared for this field. Not attempted is not a failed image.`;
    const table=document.createElement('table'),head=table.insertRow();
    for(const label of ['Select','UTC / observation','Detector / release','Target wavelength','Status / reason','Image'])head.append(text('th',label));
    for(const r of filtered.slice(page*size,(page+1)*size)){
      const tr=table.insertRow(),pick=document.createElement('input');pick.type='checkbox';pick.checked=checked.has(r.id);pick.setAttribute('aria-label','Select '+r.obs_id+' '+r.energy_bandpassname);pick.onchange=()=>{pick.checked?checked.add(r.id):checked.delete(r.id);render();};tr.insertCell().append(pick);
      tr.insertCell().textContent=new Date((Number(r.t_min)-40587)*86400000).toISOString()+' · '+r.obs_id;
      tr.insertCell().textContent=r.energy_bandpassname+' · '+r.obs_collection;
      const a=auditRows.get(r.id);tr.insertCell().textContent=a?.target_wavelength_um?`${a.target_wavelength_um.toFixed(4)} µm`:'Not checked; can still request image';
      tr.insertCell().textContent=getState(r).replaceAll('_',' ')+(states.get(r.id)==='prepared'?' · Loaded in this session':a?.reason?' · '+a.reason:'');
      const button=text('button','View / load cutout');button.className='secondary';button.disabled=busy&&getState(r)!=='prepared';button.onclick=()=>getState(r)==='prepared'?viewPrepared(r):load([r]);tr.insertCell().append(button);
    }
    out.append(table);const pager=document.createElement('div');pager.className='row';
    const prev=text('button','Previous records'),next=text('button','Next records');prev.className=next.className='secondary';prev.disabled=page===0;next.disabled=(page+1)*size>=filtered.length;prev.onclick=()=>{page--;render();};next.onclick=()=>{page++;render();};pager.append(prev,text('span',`Page ${page+1} / ${Math.max(1,Math.ceil(filtered.length/size))}`),next);out.append(pager);
  }
  // Keep the existing metadata search; replace only its capped presentation.
  renderRows=()=>{metadataReady=true;checked.clear();auditRows.clear();states.clear();page=0;render();};
  async function review(){
    summary.textContent='Reviewing every indexed overlapping record using saved metadata and headers only…';
    try {const p=values(),data=await api('/api/v1/field-audit?'+new URLSearchParams({ra:p.ra,dec:p.dec,fov_arcmin:p.fov}));metadataReady=true;auditRows=new Map(data.records.map(r=>[r.id,r]));for(const r of data.records)if(r.prepared)preparedJobs.set(r.id,r.prepared.job);if(!rows.length){rows=data.records.map(r=>r.source_record);catalogue={collections:[{rows}],coverage:data.coverage};$('#export').disabled=!rows.length;$('#prepare').disabled=!rows.length;}render();}
    catch(e){summary.textContent='Metadata review failed: '+e.message;}
  }
  function wait(ms){return new Promise(resolve=>setTimeout(resolve,ms));}
  async function load(selected){
    if(busy||!selected.length)return;
    if(!validateViewerInputs())return;
    busy=true;cancel=false;const dialog=document.querySelector('#advanced-dialog');if(dialog.open)dialog.close();const rev=revision,p=values(),combined=[],preparationJobs=[];let complete=0,assembled=0;
    for(const id of ['record-selected','record-all','record-mosaic'])document.querySelector('#'+id).disabled=true;
    document.querySelector('#record-stop').disabled=false;render();
    async function merge(){
      let m=combined[0],id=preparationJobs[0];
      if(preparationJobs.length>1){
        const assembly=await api('/api/v1/assemblies',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({job_ids:preparationJobs})});id=assembly.job_id;
        let r;do{r=await api('/api/v1/sequences/'+id);if(['complete','failed'].includes(r.state))break;await wait(1000);}while(rev===revision);
        if(rev!==revision)return;if(r.state==='failed')throw Error(r.error);m=r.manifest;
      }
      manifest=m;job=id;rememberJob(job);$('#sequence').value='all';loadManifest();at=0;draw();assembled=complete;
    }
    try{
      for(const row of selected){
        if(cancel||rev!==revision)break;
        states.set(row.id,'loading');render();message(`Loading real cutout ${complete+1}/${selected.length}. Other records remain available; ${complete} completed.`);
        try{
          const request=await api('/api/prepare',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({...p,ids:[row.id],match:false})});
          let result;
          do{result=await api('/api/jobs/'+request.job);if(['complete','failed'].includes(result.state))break;message(`${result.progress||result.state} · observation ${complete+1}/${selected.length}`);await wait(1800);}while(rev===revision);
          if(rev!==revision)break;
          if(result.state==='failed')throw Error(result.error);
          preparationJobs.push(request.job);combined.push(result.manifest);complete++;states.set(row.id,'prepared');
          if(complete<=2||(complete&(complete-1))===0||row===selected[selected.length-1]||cancel){
            await merge();
          }
          message(`${complete}/${selected.length} requested observations prepared. ${manifest?.frames.length||0} frames in the common-stretch sequence; loading continues progressively.`);
        }catch(e){states.set(row.id,'failed: '+e.message);}
        render();
      }
      if(complete>assembled&&rev===revision)await merge();
    }finally{busy=false;fieldTask=null;for(const id of ['record-selected','record-all','record-mosaic'])document.querySelector('#'+id).disabled=false;document.querySelector('#record-stop').disabled=true;render();if(rev===revision)message(`${complete}/${selected.length} requested observations prepared${cancel?' · stopped by you':''}. Failed records show their individual reasons. All wavelengths are exploratory; choose matching groups before interpreting changes.`);}
  }
  async function viewPrepared(row){
    try{
      const id=preparedJobs.get(row.id)||auditRows.get(row.id)?.prepared?.job;
      if(!id)return load([row]);
      const r=await api('/api/v1/sequences/'+id);if(r.state!=='complete')throw Error('Prepared result is not currently available');
      followLive=false;manifest=r.manifest;job=id;$('#sequence').value='all';loadManifest();at=Math.max(0,indices.findIndex(i=>manifest.frames[i].id===row.id));draw();rememberJob(job);message('Viewing '+row.obs_id+' '+row.energy_bandpassname+'. Field loading continues independently; Show latest assembled timeline returns to the growing sequence.');
    }catch(e){summary.textContent='Could not open prepared observation: '+e.message;}
  }
  document.querySelector('#record-follow').onclick=async()=>{
    followLive=true;if(!latestSequence){summary.textContent='No assembled field sequence is available yet.';return;}
    const r=await api('/api/v1/sequences/'+latestSequence);if(r.state==='complete'){manifest=r.manifest;job=latestSequence;$('#sequence').value='all';loadManifest();rememberJob(job);}
  };
  async function monitorField(data){
    busy=true;fieldTask=data.id;const rev=revision;let shown=null;
    for(const id of ['record-selected','record-all','record-mosaic'])document.querySelector('#'+id).disabled=true;
    document.querySelector('#record-stop').disabled=false;
    try{
      while(rev===revision){
        for(const item of data.records){states.set(item.id,item.state==='prepared'?'prepared':item.state==='failed'?'failed: '+item.error:item.state==='loading'?'loading':'not_attempted');if(item.state==='prepared')preparedJobs.set(item.id,item.job_id);}latestSequence=data.sequence_id;
        render();
        summary.textContent=`${data.requested} observations in persistent field job · ${data.counts.prepared} prepared · ${data.counts.failed} failed · ${data.counts.loading} loading · ${data.counts.pending} pending · ${data.state}. Current: ${data.current_observation||'waiting'} ${data.records.find(r=>r.state==='loading')?.detector||''}. Timeline rebuilds in batches; open any prepared record immediately.`;
        if(followLive&&data.sequence_id&&data.sequence_id!==shown){
          const r=await api('/api/v1/sequences/'+data.sequence_id);
          if(rev!==revision)return;
          if(r.state==='complete'){manifest=r.manifest;job=data.sequence_id;loadManifest();rememberJob(job);shown=data.sequence_id;}
        }
        const q=new URLSearchParams(values());q.set('batch_id',data.id);if(job)q.set('job',job);history.replaceState(null,'','?'+q);
        if(!['queued','running'].includes(data.state)){
          message(`Field job ${data.state}: ${data.counts.prepared}/${data.requested} prepared, ${data.counts.failed} failed, ${data.counts.pending} pending. ${data.error||'Per-observation outcomes remain in the record list.'}`);break;
        }
        await wait(1800);data=await api('/api/v1/field-downloads/'+data.id);
      }
    }catch(e){summary.textContent='Field status connection lost: '+e.message+'. The server job persists; reopen this URL to inspect it.';}
    finally{busy=false;fieldTask=null;for(const id of ['record-selected','record-all','record-mosaic'])document.querySelector('#'+id).disabled=false;document.querySelector('#record-stop').disabled=true;}
  }
  async function startField(selected){
    if(busy||!validateViewerInputs())return;
    const dialog=document.querySelector('#advanced-dialog');if(dialog.open)dialog.close();
    try{const p=values(),r=await api('/api/v1/field-downloads',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({ra:Number(p.ra),dec:Number(p.dec),fov_arcmin:Number(p.fov),observation_ids:selected.map(r=>r.id)})});await monitorField(r);}
    catch(e){summary.textContent='Field job could not start: '+e.message;}
  }
  window.tryOpenCachedField=async()=>{
    const rev=revision,p=values();
    const response=await api('/api/v1/prepared?'+new URLSearchParams({...p,detector:$('#detector').value,from:$('#from').value,through:$('#through').value}));
    if(rev!==revision||!response.job_id)return false;
    manifest=response.manifest;job=response.job_id;loadManifest();rememberJob(job);
    message(`${response.cached_frames} cached archive IMAGE frames opened from this server. No image download was needed.`);
    return true;
  };
  // Search prepares a progressively delivered initial selection, never substitutes
  // a small cached sequence for a larger requested selection.
  prepareSequence=async(reuse=false)=>{
    if(!validateViewerInputs()||busy)return;
    if(reuse&&await window.tryOpenCachedField())return;
    await review();
    const start=$('#from').value?Date.parse($('#from').value):-Infinity,end=$('#through').value?Date.parse($('#through').value)+86400000:Infinity;
    const eligible=rows.filter(r=>($('#detector').value==='all'||r.energy_bandpassname===$('#detector').value)&&((Number(r.t_min)-40587)*86400000>=start)&&((Number(r.t_min)-40587)*86400000<end));
    const warm=eligible.filter(r=>auditRows.get(r.id)?.status==='prepared'),cold=eligible.filter(r=>auditRows.get(r.id)?.status!=='prepared');
    const selected=[...warm,...cold].slice(0,Number($('#count').value));
    if(!selected.length)return message('No observations match the selected detector and dates. All returned records remain browsable in Data & downloads.');
    await startField(selected);
  };
  document.querySelector('#record-filter').oninput=()=>{page=0;render();};document.querySelector('#record-size').onchange=()=>{page=0;render();};
  document.querySelector('#record-audit').onclick=review;
  document.querySelector('#record-selected').onclick=()=>{const selected=rows.filter(r=>checked.has(r.id));if(!selected.length){summary.textContent='Select at least one observation using its checkbox, then click Load selected cutouts.';return;}startField(selected);};
  document.querySelector('#record-all').onclick=()=>{if(!rows.length){summary.textContent='Find observations first to list the records for this sky field.';return;}startField(rows.slice().sort((a,b)=>Number(a.t_min)-Number(b.t_min)));};
  document.querySelector('#record-mosaic').onclick=async()=>{
    const selected=rows.filter(r=>checked.has(r.id));
    if(selected.length<2||selected.length>24){summary.textContent='Select 2–24 overlapping observations from one detector and release. The mosaic explicitly mixes their epochs and local wavelengths.';return;}
    if(!validateViewerInputs()||busy)return;
    busy=true;const rev=revision;
    try{
      const p=values(),request=await api('/api/v1/mosaics',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({ra:Number(p.ra),dec:Number(p.dec),fov_arcmin:Number(p.fov),observation_ids:selected.map(r=>r.id),match_wavelengths:false})});
      let result;
      do{result=await api('/api/v1/sequences/'+request.job_id);if(['complete','failed'].includes(result.state))break;summary.textContent='Preparing spatial mosaic: '+(result.progress||result.state);await wait(1800);}while(rev===revision);
      if(rev!==revision)return;if(result.state==='failed')throw Error(result.error);
      manifest=result.manifest;job=request.job_id;rememberJob(job);loadManifest();$('#mode').value='mosaic';draw();message(manifest.mosaic.warning);summary.textContent='Spatial mosaic ready from '+manifest.frames.length+' real cutouts. Gaps remain missing; this is an exploratory mixed-epoch image.';
    }catch(e){summary.textContent='Mosaic preparation failed: '+e.message;}finally{busy=false;}
  };
  document.querySelector('#record-stop').onclick=async()=>{if(fieldTask){await api('/api/v1/field-downloads/'+fieldTask+'/stop',{method:'POST',headers:{'Content-Type':'application/json'},body:'{}'});message('Stopping after the current cutout; completed observations remain available.');}else cancel=true;};
  const batchId=new URLSearchParams(location.search).get('batch_id');
  const initialReview=(new URLSearchParams(location.search).has('job')||batchId)?review():Promise.resolve();
  if(batchId)initialReview.then(()=>api('/api/v1/field-downloads/'+batchId)).then(monitorField).catch(e=>{summary.textContent=e.message;});
})();
