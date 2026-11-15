/* Frame selection lives in the overlay tab; it never downloads new observations. */
(() => {
  const panel=document.querySelector('[data-feature="overlays"]');if(!panel)return;
  const label=document.createElement('label');label.textContent='Image observation';
  const picker=document.createElement('select');picker.id='overlay-observation';picker.disabled=true;label.append(picker);panel.insertBefore(label,panel.children[1]||null);
  let previous='';
  function sync(){
    const ready=manifest&&indices.length,frames=ready?indices.map(i=>manifest.frames[i]):[];
    const key=(job||'')+'|'+frames.map(f=>f.id).join(',');
    if(key!==previous){previous=key;picker.replaceChildren();if(!frames.length)picker.add(new Option('Load a cached field first',''));
      frames.forEach((frame,i)=>picker.add(new Option(`${i+1}/${frames.length} · ${frame.utc} · ${frame.detector} · ${frame.wavelength_reference==='target'?frame.wavelength_um.toFixed(4)+' µm':'wavelength not measured'}`,frame.id)));
    }
    picker.disabled=!ready;if(ready)picker.value=manifest.frames[indices[at]].id;
  }
  picker.onchange=()=>{if(!manifest)return;const index=indices.findIndex(i=>manifest.frames[i].id===picker.value);if(index<0)return;stop();at=index;draw();};
  window.addEventListener('sky-view-selection',sync);setInterval(sync,500);sync();
})();
