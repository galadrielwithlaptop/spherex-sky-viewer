/* Adds explicit intent and exact prepared-view restoration without new downloads. */
(() => {
  const host=document.createElement('section');host.className='notes';host.id='view-intent-controls';
  host.innerHTML='<h2>What would you like to explore?</h2><div class="controls"><label>Viewing mode<select id="view-intent"><option value="time">Watch through time</option><option value="colour" selected>Explore infrared colours</option></select></label><label>Comparable wavelength group<select id="time-band"></select></label></div><p id="view-intent-note" role="status">Load observations to explore a field.</p>';
  document.querySelector('.stage').before(host);
  const recovery=document.createElement('button');recovery.type='button';recovery.id='show-available-images';recovery.textContent='Show available infrared images';recovery.hidden=true;
  host.append(recovery);
  const refreshCached=document.createElement('button');refreshCached.type='button';refreshCached.className='secondary';refreshCached.textContent='Refresh cached images & metadata';host.append(refreshCached);
  refreshCached.onclick=async()=>{refreshCached.disabled=true;try{if(!await window.tryOpenCachedField())message('No prepared images are currently cached for these coordinates and field size.');}catch(error){message('Cached images could not be refreshed: '+error.message);}finally{refreshCached.disabled=false;}};
  recovery.onclick=()=>{node('view-intent').value='colour';node('group').value='all';node('detector').value='all';node('from').value='';node('through').value='';node('mode').value='frame';rejectedView=null;window.applyViewerSelection();};
  let saved=null,restoring=false,rejectedView=null;
  const originalURL=new URLSearchParams(location.search),encoded=originalURL.get('view');
  try{if(encoded)saved=SkyViewState.parse(encoded);}catch(e){rejectedView=e.message;$('#view-intent-note').textContent='Saved view rejected: '+e.message;}
  const node=id=>document.querySelector('#'+id);
  function filterState(){return {intent:node('view-intent').value,timeBand:node('time-band').value,detector:node('detector').value,from:node('from').value,through:node('through').value};}
  function empty(messageText){stop();++draw.token;indices=[];at=0;ctx.clearRect(0,0,512,512);$('#date').textContent=messageText;for(const id of ['play','prev','next','timeline'])node(id).disabled=true;node('view-intent-note').textContent=messageText;recovery.hidden=!manifest?.frames?.length;$('#empty').hidden=false;$('#empty h3').textContent='No images in this selection';$('#empty p').textContent=messageText;}
  function apply(options={}){
    if(!manifest)return;
    stop();const state=filterState(),g=node('group').value;
    let pool=manifest.frames;
    if(g!=='all')pool=manifest.groups[Number(g)]?.indices.map(i=>manifest.frames[i])||[];
    const result=SkyViewState.displaySelect(pool,state,!restoring&&!options.frameIds),band=node('time-band'),oldBand=state.timeBand;
    if(result.fallback){state.intent='colour';node('view-intent').value='colour';}
    band.replaceChildren();for(const group of result.groups){const option=document.createElement('option');option.value=group.key;option.textContent=`${group.centre.toFixed(4)} µm · ${group.frames.length} frames`;band.append(option);}
    if(result.groups.some(g=>g.key===oldBand))band.value=oldBand;
    else if(result.frames.length&&state.intent==='time')band.value=result.groups.find(g=>g.frames.some(f=>f.id===result.frames[0].id))?.key||'';
    band.disabled=state.intent!=='time'||!result.groups.length;
    let frames=result.frames;
    if(options.frameIds){
      const allowed=new Set(frames.map(f=>f.id));
      if(!options.frameIds.every(id=>allowed.has(id)))throw Error('Saved frames conflict with available data, filters or wavelength checks.');
      frames=options.frameIds.map(id=>manifest.frames.find(f=>f.id===id));
    }
    if(!frames.length)return empty(state.intent==='time'?'No comparable time-separated pair in this prepared selection. Try another wavelength group or Explore infrared colours.':'No prepared images satisfy these filters.');
    if(state.intent==='time'&&!frames.some((a,i)=>frames.slice(i+1).some(b=>SkyViewState.independent(a,b))))return empty('At least two independent, time-separated observations are needed.');
    indices=frames.map(f=>manifest.frames.findIndex(a=>a.id===f.id));at=Math.max(0,frames.findIndex(f=>f.id===options.current));
    recovery.hidden=true;$('#empty').hidden=true;
    node('timeline').max=indices.length-1;node('timeline').value=at;
    for(const id of ['play','prev','next','timeline'])node(id).disabled=indices.length<2;
    node('view-intent-note').textContent=result.fallback?`A wavelength-matched time comparison is unavailable. Showing ${frames.length} available cached images in Explore infrared colours instead. Target-position wavelength metadata may be missing; brightness changes are not established.`:state.intent==='time'?'Chronological playback of approximately comparable responses. Matching is a metadata screen, not proof of equal PSFs, alignment or source variability.':'Wavelength-ordered playback. Dates remain visible: brightness differences may be spectral, temporal or instrumental.';
    const mode=node('mode').value;
    if(mode==='mosaic'&&(node('display-source').value==='raw'||!manifest.mosaic?.image||indices.length!==manifest.frames.length))throw Error('The saved spatial mosaic is unavailable for this image source or filtered selection.');
    if(mode!=='frame'&&mode!=='mosaic'){
      const all=manifest.groups[Number(g)]?.indices||[];
      if(!manifest.groups[Number(g)]?.[mode])throw Error('This cached comparison product is unavailable.');
      if(node('display-source').value==='raw'||indices.length!==all.length||!indices.every(i=>all.includes(i)))throw Error('This cached coadd/difference does not represent the selected frames or image source. Select individual frames.');
    }
    window.dispatchEvent(new CustomEvent('sky-view-selection'));
    draw();
  }
  window.applyViewerSelection=()=>{try{apply();}catch(e){node('mode').value='frame';empty(e.message);}};
  const oldRemember=rememberJob;rememberJob=function(id){oldRemember(id);if(encoded&&id===originalURL.get('job')){const q=new URLSearchParams(location.search);q.set('view',encoded);history.replaceState(null,'','?'+q);}};
  const oldSetGroup=setGroup;setGroup=function(){oldSetGroup();if(!restoring)window.applyViewerSelection();};
  const oldLoad=loadManifest;loadManifest=function(){
    oldLoad();
    if(rejectedView){empty('Saved view rejected: '+rejectedView+' Choose a viewing mode to begin a new selection.');return;}
    if(saved){
      const state=saved;saved=null;restoring=true;
      try{
        for(const[id,value]of Object.entries({'view-intent':state.intent,'time-band':state.timeBand,detector:state.detector,from:state.from,through:state.through,'display-source':state.source,overlay:state.overlay,speed:state.speed,brightness:state.brightness,count:state.count,sequence:state.sequence})){
          if(id==='time-band')continue;node(id).value=String(value);
        }
        if(state.group!=='all'&&!manifest.groups[Number(state.group)])throw Error('Saved wavelength group is unavailable.');
        node('group').value=state.group;oldSetGroup();node('mode').value=state.mode;
        // Build band options using restored filters before restoring its ID.
        apply();if(state.timeBand){if(![...node('time-band').options].some(o=>o.value===state.timeBand))throw Error('Saved comparable band is unavailable.');node('time-band').value=state.timeBand;}
        if(state.evidenceA)originalURL.set('evidence_a',state.evidenceA);if(state.evidenceB)originalURL.set('evidence_b',state.evidenceB);
        window.restoredEvidencePair=[state.evidenceA,state.evidenceB];
        node('brightness').oninput();apply({frameIds:state.frames,current:state.current});node('display-source').onchange();
        node('tab-'+state.tab).click();if(state.overlay!=='none')node('overlay').onchange();
        node('view-intent-note').textContent+=' Saved view restored (playback stays paused).';
      }catch(e){empty('Saved view cannot be restored exactly: '+e.message);}finally{restoring=false;}
    }else window.applyViewerSelection();
  };
  for(const id of ['view-intent','time-band','from','through','detector'])node(id).addEventListener('change',()=>{rejectedView=null;window.restoredEvidencePair=null;node('mode').value='frame';window.applyViewerSelection();});
  node('mode').onchange=()=>{try{apply();}catch(e){node('mode').value='frame';message(e.message);}};
  window.captureSkyView=()=>SkyViewState.validate({v:1,intent:node('view-intent').value,timeBand:node('time-band').value||'',source:node('display-source').value,mode:node('mode').value,overlay:node('overlay').value,sequence:node('sequence').value,speed:node('speed').value,count:node('count').value,brightness:Number(node('brightness').value),detector:node('detector').value,from:node('from').value,through:node('through').value,group:node('group').value,frames:indices.map(i=>manifest.frames[i].id),current:indices.length?manifest.frames[indices[at]].id:'',tab:document.querySelector('[data-tab][aria-selected="true"]')?.dataset.tab||'playback',evidenceA:node('evidence-a')?.value||'',evidenceB:node('evidence-b')?.value||''});
  window.skyViewURL=()=>{const url=new URL(location.href);url.search=new URLSearchParams({...values(),job,view:SkyViewState.serialize(window.captureSkyView()),evidence_a:node('evidence-a')?.value||'',evidence_b:node('evidence-b')?.value||''});return url.href;};
  window.useEvidencePair=(a,b)=>{
    if(node('view-intent').value==='time'&&(!SkyViewState.compatible(a,b)||!SkyViewState.independent(a,b))){message('This pair is not eligible for Watch through time. Switch to Explore infrared colours to inspect it.');return;}
    try{node('mode').value='frame';apply({frameIds:[a,b].sort((x,y)=>node('view-intent').value==='time'?x.mjd-y.mjd:x.wavelength_um-y.wavelength_um).map(f=>f.id)});node('tab-playback').click();}catch(e){message(e.message);}
  };
})();
