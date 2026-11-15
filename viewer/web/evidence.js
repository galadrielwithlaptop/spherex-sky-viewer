/* Evidence export uses existing prepared products; no image downloads or fitting. */
(() => {
  const panel=document.createElement('section');panel.className='notes';panel.id='evidence-check';
  panel.innerHTML=`<h2>Check what changed</h2><p>A different infrared colour can look like a change through time. Check two observations before interpreting a blink.</p>
  <div class="controls"><label>First observation<select id="evidence-a"></select></label><label>Second observation<select id="evidence-b"></select></label></div>
  <p id="evidence-result" role="status">Load a field to inspect its evidence.</p><div id="evidence-facts"></div>
  <p class="small">A calibrated object-brightness plot is unavailable for this field; the viewer does not infer photometry from display pixels.</p><p class="small">Similar band centres are a screening check, not identical spectral responses. No automatic discovery, calibrated light curve or motion measurement is claimed. Catalogue markers are possible neighbours, not confirmed source identities.</p>
  <div class="row"><button id="evidence-blink" disabled>Inspect these two frames</button><button class="secondary" id="evidence-share" disabled>Copy this comparison link</button><button id="evidence-export" disabled>Download evidence JSON</button></div><p id="evidence-action" role="status"></p><a id="view-permalink" hidden>Open this exact saved view</a>
  <details><summary>Five challenge fields: what is ready?</summary><div id="challenge-readiness">Loading saved field checks...</div></details><p><a href="reproduce.ipynb" download>Download the reproducible notebook (.ipynb)</a> · <a href="notebook-example.zip" download>Offline example images (ZIP)</a> · <a href="challenge-validation.json" download>Five-field test report</a></p>`;
  [...document.querySelectorAll('.notes')].find(n=>n.id!=='view-intent-controls').before(panel);
  const a=panel.querySelector('#evidence-a'),b=panel.querySelector('#evidence-b');let key='',frames=[],selectedA=null,selectedB=null;
  const params=new URLSearchParams(location.search);
  function finite(value){return typeof value==='number'&&Number.isFinite(value);}
  function assess(x,y){
    const notes=[];let level='Not enough metadata';
    if(!x||!y||x.id===y.id)return {level:'Choose two different observations',notes:['A single frame cannot establish change through time.']};
    if(x.wavelength_reference!=='target'||y.wavelength_reference!=='target')notes.push('Wavelength is not confirmed at the target position in both frames.');
    if(finite(x.wavelength_um)&&finite(y.wavelength_um)&&finite(x.bandwidth_um)&&finite(y.bandwidth_um)&&x.bandwidth_um>0&&y.bandwidth_um>0){
      const delta=Math.abs(x.wavelength_um-y.wavelength_um),width=(x.bandwidth_um+y.bandwidth_um)/2;
      const close=typeof SkyViewState!=='undefined'?SkyViewState.compatible(x,y):(delta<=.25*Math.min(x.bandwidth_um,y.bandwidth_um)&&Math.abs(x.bandwidth_um/y.bandwidth_um-1)<=.1&&Math.abs(y.bandwidth_um/x.bandwidth_um-1)<=.1);
      level=close?'Similar wavelengths: candidate for a time comparison':'Different wavelength responses: explore colour first';
      if(close&&typeof SkyViewState!=='undefined'&&!SkyViewState.independent(x,y))level='Same observation or epoch: not a time comparison';
      notes.push(`Centre difference ${delta.toFixed(5)} µm; screening requires ≤25% of the narrower bandwidth, width agreement within10% in both directions, and the same detector/release at the target. This is not a calibrated equivalence test.`);
    }else notes.push('Missing wavelength or bandwidth: comparability cannot be checked.');
    if(finite(x.mjd)&&finite(y.mjd))notes.push(`Time separation: ${Math.abs(y.mjd-x.mjd).toFixed(3)} days.`);
    notes.push('Images are sky-aligned for display, but PSF differences, positional errors and detector artifacts can mimic change.');
    return {level,notes};
  }
  // Export a pure helper for regression tests without changing the viewer model.
  window.assessSkyEvidence=assess;
  function facts(frame){return {id:frame.id,observation:frame.observation,utc:frame.utc,mjd:frame.mjd,wavelength_um:frame.wavelength_um,bandwidth_um:frame.bandwidth_um,wavelength_reference:frame.wavelength_reference,detector:frame.detector,collection:frame.collection,analysis_valid_fraction:frame.valid_fraction,native_flagged_fraction:frame.native_flagged_fraction,flag_counts:frame.flag_counts,source_url:frame.source_url,cutout_sha256:frame.cutout_sha256,fits_key:frame.fits_key};}
  function update(){
    selectedA=frames.find(f=>f.id===a.value);selectedB=frames.find(f=>f.id===b.value);
    const check=assess(selectedA,selectedB);panel.querySelector('#evidence-result').textContent=check.level;
    const box=panel.querySelector('#evidence-facts');box.replaceChildren();
    for(const text of check.notes){const p=document.createElement('p');p.className='small';p.textContent=text;box.append(p);}
    for(const [name,f] of [['First',selectedA],['Second',selectedB]])if(f){const p=document.createElement('p');p.className='small';p.textContent=`${name}: ${f.utc||'Unknown date'} · ${f.wavelength_um??'unknown'} µm · ${f.detector||'unknown detector'} · native flagged fraction ${finite(f.native_flagged_fraction)?(100*f.native_flagged_fraction).toFixed(1)+'%':'unknown'}. Flags describe the cutout, not specifically the selected star.`;box.append(p);}
  }
  a.onchange=b.onchange=update;
  window.addEventListener('sky-view-selection',()=>{if(!frames.length||!indices.length)return;const pair=window.restoredEvidencePair||[manifest.frames[indices[0]].id,manifest.frames[indices[indices.length-1]].id];a.value=pair[0];b.value=pair[1];update();});
  function refresh(){
    const m=typeof manifest==='undefined'?null:manifest;
    const next=m?`${job}|${m.frames.map(f=>f.id).join(',')}`:'';
    if(next===key)return;key=next;frames=m?.frames||[];
    for(const select of [a,b]){select.replaceChildren();frames.forEach(f=>{const option=document.createElement('option');option.value=f.id;option.textContent=`${f.utc||'Unknown date'} · ${Number(f.wavelength_um).toFixed(4)} µm`;select.append(option);});}
    a.value=frames.some(f=>f.id===params.get('evidence_a'))?params.get('evidence_a'):(window.restoredEvidencePair?.[0]||manifest?.frames[indices?.[0]]?.id||frames[0]?.id||'');
    b.value=frames.some(f=>f.id===params.get('evidence_b'))?params.get('evidence_b'):(window.restoredEvidencePair?.[1]||manifest?.frames[indices?.[indices.length-1]]?.id||frames[1]?.id||frames[0]?.id||'');
    panel.querySelector('#evidence-share').disabled=panel.querySelector('#evidence-export').disabled=!frames.length;panel.querySelector('#evidence-blink').disabled=frames.length<2;update();
  }
  panel.querySelector('#evidence-blink').onclick=()=>{
    if(!selectedA||!selectedB||selectedA.id===selectedB.id)return;
    if(window.useEvidencePair)return window.useEvidencePair(selectedA,selectedB);
    stop();indices=[selectedA,selectedB].map(f=>manifest.frames.findIndex(a=>a.id===f.id)).sort((a,b)=>manifest.frames[a].mjd-manifest.frames[b].mjd);at=0;
    $('#mode').value='frame';$('#timeline').max=1;$('#timeline').value=0;$('#tab-playback').click();draw();
    panel.querySelector('#evidence-action').textContent='Timeline now contains these two frames. Press Play to blink. Check the wavelength warning before interpreting changes.';
  };
  fetch('challenge-validation.json').then(r=>{if(!r.ok)throw Error('Saved checks unavailable');return r.json();}).then(report=>{
    const box=panel.querySelector('#challenge-readiness');box.replaceChildren();
    for(const t of report.targets){const p=document.createElement('p');p.className='small';p.textContent=`${t.name}: ${t.metadata_query==='passed'?t.indexed_matches+' indexed overlapping records; '+t.prepared_frames+' prepared frames':'metadata check failed'}. ${t.prepared_frames>=2?'Frames available for inspection; motion/variability not established.':'More frame preparation required.'} Archive coverage is not certified complete.`;box.append(p);if(t.example_url){const a=document.createElement('a');a.href=t.example_url;a.textContent='Open prepared '+t.name+' example';box.append(a);}}
  }).catch(()=>{panel.querySelector('#challenge-readiness').textContent='Saved readiness report unavailable; run the five-field check before claiming coverage.';});
  function shareURL(){if(window.skyViewURL)return window.skyViewURL();const url=new URL(location.href);url.search=new URLSearchParams({...values(),job,evidence_a:a.value,evidence_b:b.value});return url.href;}
  panel.querySelector('#evidence-share').onclick=async()=>{const node=panel.querySelector('#evidence-action'),url=shareURL();const permalink=panel.querySelector('#view-permalink');permalink.href=url;permalink.hidden=false;try{await navigator.clipboard.writeText(url);node.textContent='Comparison link copied. It restores this prepared view, filters, display settings and frame selection on this server; playback resumes paused.';}catch{node.textContent='Copy this link: '+url;}};
  panel.querySelector('#evidence-export').onclick=()=>{
    const payload={schema_version:1,created_utc:new Date().toISOString(),comparison_url:shareURL(),sequence_id:job,parameters:manifest.parameters,display_source:$('#display-source').value,display_view:$('#mode').value,wavelength_group:$('#group').value,exact_view:window.captureSkyView?window.captureSkyView():null,assessment:assess(selectedA,selectedB),observations:[selectedA,selectedB].filter(Boolean).map(facts),sequence_warnings:manifest.warnings,limitations:['Diagnostic evidence, not a confirmed discovery.','Cutout quality fractions do not prove target detection.','Display uses common stretch and sky alignment; not PSF homogenization.','Default archive IMAGE display has no additional quality mask or ZODI subtraction.','No validated NEP redshift results are included.']};
    const url=URL.createObjectURL(new Blob([JSON.stringify(payload,null,2)],{type:'application/json'}));const link=document.createElement('a');link.href=url;link.download='spherex-comparison-evidence.json';link.click();setTimeout(()=>URL.revokeObjectURL(url),1000);
  };
  setInterval(refresh,1000);refresh();
})();
