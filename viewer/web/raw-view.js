const archiveDisplayCache=new Map();
let archiveDisplayRetry=null,archiveImageOnCanvas=false;
async function drawArchiveFrame(){
  if(!manifest||!indices.length)return;
  const token=++draw.token,start=performance.now(),sequence=job,frame=manifest.frames[indices[at]],mode=$('#mode').value;
  if(mode!=='frame'){
    $('#mode').value='frame';
    message('Archive IMAGE display shows individual observations. To explicitly view the retained coadd, difference or mosaic products, choose Analysis products in Advanced settings.');
  }
  clearTimeout(archiveDisplayRetry);
  try{
    let raw=archiveDisplayCache.get(sequence);
    if(!raw){
      const response=await fetch(`/products/${sequence}/raw/manifest.json`,{cache:'no-cache'});
      if(!response.ok)throw Error('Archive IMAGE preview is being prepared from the cached science pixels.');
      raw=await response.json();archiveDisplayCache.set(sequence,raw);
      if(archiveDisplayCache.size>30)archiveDisplayCache.delete(archiveDisplayCache.keys().next().value);
    }
    if(token!==draw.token||job!==sequence)return;
    const source=raw.frames.find(f=>f.id===frame.id);
    if(!source)throw Error('Archive IMAGE frame is not ready.');
    const picture=new Image();
    picture.onload=()=>{
      if(token!==draw.token||job!==sequence)return;
      ctx.clearRect(0,0,512,512);ctx.drawImage(picture,0,0,512,512);archiveImageOnCanvas=true;paintOverlay(frame);$('#empty').hidden=true;
      recordLatency('archive_IMAGE_frame_ready',start,'Archive IMAGE preview fetch/decode and sky-aligned display; no ZODI subtraction or PSF processing');
      if(firstFrameSince!==null){recordLatency(firstFrameAction,firstFrameSince);firstFrameSince=null;}
    };
    picture.onerror=()=>{archiveDisplayCache.delete(sequence);archiveDisplayRetry=setTimeout(()=>draw(),1500);};picture.src=source.image;
    $('#timeline').value=at;
    const detectorRange=frame.wavelength_reference?.startsWith('Detector-wide')&&frame.wavelength_bounds_um;
    const wavelengthLabel=detectorRange?`${frame.wavelength_bounds_um.map(v=>v.toFixed(2)).join('–')} µm detector range; target wavelength not measured`:`${frame.wavelength_um.toFixed(4)} µm`;
    $('#date').textContent=`${at+1}/${indices.length} · ${frame.utc} · ${wavelengthLabel} · ${(100*source.valid_fraction).toFixed(0)}% finite coverage · archive IMAGE${frame.wavelength_reference?.startsWith('cutout centre')?' · wavelength at cutout centre; target not covered':''}`;
    $('#display-policy').textContent='Archive calibrated IMAGE · no zodiacal subtraction, quality-flag masking or PSF/ePSF processing. Sky alignment and common display stretch only. Flagged artifacts may be visible.';
    $('#provenance').textContent=JSON.stringify({...frame,image:source.image,valid_fraction:source.valid_fraction,processing:raw.processing,mask_policy:'No quality-flag mask applied; finite and in-bounds archive IMAGE pixels only',quality_mask_applied:false,zodi_subtracted:false,psf_applied:false,stretch:raw.stretch},null,2);
    const provenance=document.querySelector('#downloads a');if(provenance){provenance.href=`/products/${sequence}/raw/manifest.json`;provenance.textContent='Archive IMAGE display provenance';}
    for(const link of document.querySelectorAll('#downloads a'))if(link.textContent.includes('blink GIF'))link.hidden=true;
    const cutout=$('#cutout-download');if(cutout)cutout.href=source.native_fits||frame.native_fits||'/cutouts/'+frame.fits_key;
  }catch(e){
    if(token!==draw.token||job!==sequence)return;
    if(!archiveImageOnCanvas)ctx.clearRect(0,0,512,512);$('#display-policy').textContent=e.message+' Existing analysis products remain intact and are not used as a fallback.';
    archiveDisplayRetry=setTimeout(()=>draw(),1500);
  }
}
$('#display-source').onchange=()=>{
  clearTimeout(archiveDisplayRetry);stop();if($('#display-source').value==='processed')archiveImageOnCanvas=false;
  $('#display-policy').textContent=$('#display-source').value==='raw'?'Archive IMAGE display selected.':'Analysis products selected explicitly: IMAGE − ZODI, conservative quality mask and sky reprojection. No PSF/ePSF processing.';
  if($('#display-source').value==='processed'){const provenance=document.querySelector('#downloads a');if(provenance){provenance.href=`/products/${job}/manifest.json`;provenance.textContent='Analysis provenance JSON';}for(const link of document.querySelectorAll('#downloads a'))link.hidden=false;}
  draw();
};
if(manifest)draw();
