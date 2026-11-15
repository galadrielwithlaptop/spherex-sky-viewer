/* Pure selection/state contract, shared by browser code and regression tests. */
(function(root,factory){const api=factory();if(typeof module==='object'&&module.exports)module.exports=api;else root.SkyViewState=api;})(typeof globalThis!=='undefined'?globalThis:this,function(){
  const finite=x=>typeof x==='number'&&Number.isFinite(x);
  function compatible(a,b){
    return typeof a.detector==='string'&&typeof a.collection==='string'&&a.detector.length>0&&a.collection.length>0&&a.wavelength_reference==='target'&&b.wavelength_reference==='target'&&a.detector===b.detector&&a.collection===b.collection&&finite(a.wavelength_um)&&finite(b.wavelength_um)&&finite(a.bandwidth_um)&&finite(b.bandwidth_um)&&a.bandwidth_um>0&&b.bandwidth_um>0&&Math.abs(a.wavelength_um-b.wavelength_um)<=.25*Math.min(a.bandwidth_um,b.bandwidth_um)&&Math.abs(a.bandwidth_um/b.bandwidth_um-1)<=.1&&Math.abs(b.bandwidth_um/a.bandwidth_um-1)<=.1;
  }
  function independent(a,b){return finite(a.mjd)&&finite(b.mjd)&&Math.abs(a.mjd-b.mjd)>1/86400&&(!a.observation||!b.observation||a.observation!==b.observation);}
  function timeGroups(frames){
    const groups=[];[...frames].sort((a,b)=>a.wavelength_um-b.wavelength_um||a.mjd-b.mjd||a.id.localeCompare(b.id)).forEach(f=>{
      if(f.wavelength_reference!=='target')return;
      let group=groups.find(g=>g.every(a=>compatible(a,f)));
      if(!group){group=[];groups.push(group);}group.push(f);
    });
    return groups.filter(g=>g.some((a,i)=>g.slice(i+1).some(b=>independent(a,b)))).map(g=>({key:g[0].id,frames:g.sort((a,b)=>a.mjd-b.mjd||a.id.localeCompare(b.id)),centre:g.reduce((s,f)=>s+f.wavelength_um,0)/g.length}));
  }
  function select(frames,s){
    let pool=frames.filter(f=>(!s.detector||s.detector==='all'||f.detector===s.detector)&&(!s.from||f.mjd>=Date.parse(s.from)/86400000+40587)&&(!s.through||f.mjd<Date.parse(s.through)/86400000+40588));
    const groups=timeGroups(pool);let chosen;
    if(s.intent==='time'){
      const group=groups.find(g=>g.key===s.timeBand)||[...groups].sort((a,b)=>(b.frames.at(-1).mjd-b.frames[0].mjd)-(a.frames.at(-1).mjd-a.frames[0].mjd)||b.frames.length-a.frames.length)[0];
      chosen=group?.frames||[];
    }else chosen=pool.sort((a,b)=>a.wavelength_um-b.wavelength_um||a.mjd-b.mjd||a.id.localeCompare(b.id));
    return {frames:chosen,groups};
  }
  function displaySelect(frames,state,allowFallback=true){
    const selected=select(frames,state);
    if(state.intent!=='time'||selected.frames.length||!allowFallback)return {...selected,fallback:false};
    const available=select(frames,{...state,intent:'colour'});
    return {...available,fallback:available.frames.length>0};
  }
  const enumFields={intent:['time','colour'],source:['raw','processed'],mode:['frame','coadd','difference','mosaic'],overlay:['none','gaia','wise'],sequence:['matched','all'],speed:['1400','700','300'],count:['6','12','24'],tab:['search','playback','compare','overlays','data','api']};
  function validate(s){
    if(!s||typeof s!=='object'||Array.isArray(s)||s.v!==1)throw Error('Unsupported saved-view version.');
    const fields=new Set(['v',...Object.keys(enumFields),'detector','from','through','brightness','frames','current','timeBand','evidenceA','evidenceB','group']);if(Object.keys(s).some(k=>!fields.has(k)))throw Error('Unknown saved-view setting.');
    for(const[k,allowed]of Object.entries(enumFields))if(!allowed.includes(s[k]))throw Error('Invalid saved setting: '+k);
    if(!['all',...Array.from({length:6},(_,i)=>'SPHEREx-D'+(i+1))].includes(s.detector))throw Error('Invalid detector.');
    for(const k of ['from','through'])if(s[k]!==''&&(!/^\d{4}-\d{2}-\d{2}$/.test(s[k])||!Number.isFinite(Date.parse(s[k]))||new Date(s[k]).toISOString().slice(0,10)!==s[k]))throw Error('Invalid date filter.');
    if(s.from&&s.through&&s.from>s.through)throw Error('Reversed date filters.');
    if(!Number.isFinite(s.brightness)||s.brightness<60||s.brightness>180)throw Error('Invalid display brightness.');
    if(!Array.isArray(s.frames)||s.frames.length>500||new Set(s.frames).size!==s.frames.length||!s.frames.every(x=>typeof x==='string'&&/^[a-f0-9]{24}$/.test(x)))throw Error('Invalid saved frame list.');
    if(typeof s.current!=='string'||(s.current&&!s.frames.includes(s.current)))throw Error('Current frame absent from selection.');
    for(const k of ['timeBand','evidenceA','evidenceB'])if(typeof s[k]!=='string'||(s[k]&&!/^[a-f0-9]{24}$/.test(s[k])))throw Error('Invalid frame identifier.');
    if(typeof s.group!=='string'||!(s.group==='all'||/^\d{1,3}$/.test(s.group)))throw Error('Invalid wavelength group.');
    return s;
  }
  function serialize(s){return JSON.stringify(validate(s));}
  function parse(text){if(text.length>20000)throw Error('Saved view is too large.');return validate(JSON.parse(text));}
  return {compatible,independent,timeGroups,select,displaySelect,validate,serialize,parse};
});
