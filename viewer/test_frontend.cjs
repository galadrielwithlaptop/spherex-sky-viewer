// Browser-independent regression checks of the actual application script.
// Metadata/DOM stubs are test fixtures; no fixture imagery is shown to users.
const assert = require('node:assert/strict');
const fs = require('node:fs');
const vm = require('node:vm');
const path = require('node:path');

async function scenario(kind) {
  const nodes = new Map(), calls = [], draws = [], posts=[],created=[],exports=[],timers=new Map(),markers=[],pendingOverlays=[];
  function element(value = '') {
    return { value, hidden: false, disabled: false, textContent: '', children: [], listeners: {},
      append(...items) { this.children.push(...items); },
      replaceChildren(...items) { this.children = items; if (items[0]?.value) this.value = items[0].value; },
      insertRow() { const row = element(); this.append(row); return row; },
      insertCell() { const cell = element(); this.append(cell); return cell; },
      add(item) { this.append(item); }, addEventListener(name, callback) { this.listeners[name] = callback; },
      click(){this.onclick?.();},scrollIntoView() {}, reportValidity() { return kind!=='invalid'; }, style: {},
      getContext() { return { clearRect() {}, drawImage(image) { draws.push(image.src); },beginPath(){},arc(){markers.push('circle');},rect(){markers.push('square');},stroke(){} }; }
    };
  }
  function node(selector) { if (!nodes.has(selector)) nodes.set(selector, element()); return nodes.get(selector); }
  const form = node('#search');
  form.elements = { ra: element('133.7951291667'), dec: element('-7.2451472222'), fov: element('5') };
  node('#detector').value = 'SPHEREx-D4'; node('#sequence').value = 'matched'; node('#count').value = '12';node('#speed').value='700';node('#overlay').value='none';
  const frames = [0, 1].map(i => ({id: String(i), mjd: 60800 + i * 180, utc: `epoch-${i}`, wavelength_um: 3.45, valid_fraction: .97, image: `/products/test/${i}.png`, fits_key: `fits-${i}`}));
  const manifest = { parameters: {ra: 133.7951291667, dec: -7.2451472222, fov: 5}, frames, groups: [{indices: [0, 1], wavelength_um: 3.45,coadd:'/products/test/coadd-0.png',difference:'/products/test/difference-0.png',animation:'/products/test/blink-0.gif'}], errors: [] };
  const rows = kind === 'empty' ? [] : Array.from({length:kind==='many'?30:2},(_,i)=>i).map(i => ({id: String(i), t_min: String(60800 + i * (kind==='many'?3:180)), energy_bandpassname: 'SPHEREx-D4', obs_collection: 'spherex_dr1', obs_id: `obs-${i}`, access_url: 'https://irsa.ipac.caltech.edu/test.fits'}));
  const location = {protocol: 'http:', search:kind==='resume'?'?ra=133.7951291667&dec=-7.2451472222&fov=5&job=0123456789abcdef01234567&batch_id=abcdef0123456789abcdef01':''};
  const ready=['cached','many','resume','image_fail','overlay_race'].includes(kind);
  const context = {
    document: {querySelector: node, createElement: () => {const el=element();created.push(el);Object.defineProperty(el,'id',{set(id){nodes.set('#'+id,el);}});return el;}},
    location, history: {replaceState(a, b, value) {location.search = value.slice(value.indexOf('?'));}},
    URLSearchParams, Date, Math, JSON, Number, String, Object, Map, Set,Blob,performance,
    URL:{createObjectURL(blob){exports.push(blob);return 'blob:test';},revokeObjectURL(){}},
    FormData: class { constructor() {this.data = Object.entries(form.elements).map(([k, v]) => [k, v.value]);} [Symbol.iterator]() {return this.data[Symbol.iterator]();} },
    Option: function(text, value) {return {...element(value), textContent: text};},
    Image: class {set src(value) {this.url = value;queueMicrotask(()=>kind==='image_fail'?this.onerror?.():this.onload?.());} get src() {return this.url;}},
    setTimeout() {return 1;}, clearTimeout() {}, setInterval(fn,ms) {const id=timers.size+1;timers.set(id,{fn,ms});return id;}, clearInterval(id) {timers.delete(id);},
    fetch: async (url, options) => {
      calls.push(url);
      let payload;
      if (url === '/api/health') payload = {catalogue: {exposures: 2}};
      else if (url.startsWith('/api/search?')) payload = {collections: [{rows}], catalogue: {exposures: 2, queries: 1}};
      else if (url.startsWith('/api/ready?')) payload = {job: ready ? 'saved' : null};
      else if (url === '/api/prepare') { posts.push(JSON.parse(options.body));payload = {job: 'new'}; }
      else if (url.startsWith('/api/jobs/')) payload = ready ? {state: 'complete', manifest} : {state: 'queued', progress: 'Waiting for image worker', errors: []};
      else if(url.startsWith('/api/resolve?')){const name=new URLSearchParams(url.split('?')[1]).get('name');const r=JSON.parse(fs.readFileSync(path.join(__dirname,'evidence/target-coverage.json'),'utf8')).find(r=>r.name===name);payload={ra:r.ra,dec:r.dec,provenance:'Saved resolver fixture'};}
      else if(url.startsWith('/api/overlay?')){const name=new URLSearchParams(url.split('?')[1]).get('catalogue');if(kind==='overlay_race')await new Promise(resolve=>pendingOverlays.push({name,resolve}));payload={catalogue:name==='gaia'?'gaia_dr3_source':'allwise_p3as_psd',rows:[{ra:'133.7951291667',dec:'-7.2451472222',pmra:'0',pmdec:'0',ref_epoch:'2016'}],warning:'Fixture epoch caveat'};}
      else throw Error(`Unexpected request: ${url}`);
      return {ok: true, json: async () => payload};
    }
  };
  vm.runInNewContext(fs.readFileSync(path.join(__dirname, 'web/app.js'), 'utf8'), context);
  if(kind!=='resume')form.listeners.submit({preventDefault() {}});
  for (let i = 0; i < 8; i++) await new Promise(setImmediate);
  return {nodes, calls, draws, location,posts,created,exports,timers,markers,form,pendingOverlays};
}

(async () => {
  const results=[];const check=async(name,fn)=>{const start=performance.now();await fn();results.push({option:name,status:'pass',logic_test_duration_ms:performance.now()-start});};
  await check('one_click_cached_images',async()=>{
  const cached = await scenario('cached');
  assert.ok(cached.calls.some(c => c.startsWith('/api/ready?')));
  assert.ok(cached.draws.length > 0, 'A single Find observations click must draw cached imagery');
  assert.equal(cached.nodes.get('#empty').hidden, true);
  assert.match(cached.nodes.get('#search-feedback').textContent, /2 real frames ready/);
  });await check('first_load_queue_and_refreshable_job',async()=>{
  const first = await scenario('first');
  assert.ok(first.calls.includes('/api/prepare'), 'First search must automatically start image preparation');
  assert.match(first.nodes.get('#search-feedback').textContent, /queued/);
  assert.match(first.nodes.get('#empty p').textContent, /queued/);
  assert.match(first.location.search, /job=new/, 'In-progress work must survive a page refresh');
  });await check('empty_metadata_result',async()=>{
  const empty = await scenario('empty');
  assert.match(empty.nodes.get('#search-feedback').textContent, /No archive images/);
  assert.ok(!empty.calls.includes('/api/prepare'));
  });
  await check('invalid_coordinate_form',async()=>{const s=await scenario('invalid');assert.ok(!s.calls.some(c=>c.startsWith('/api/search?')));});
  await check('resume_coordinate_job_url',async()=>{const s=await scenario('resume');assert.match(s.location.search,/batch_id=abcdef0123456789abcdef01/);assert.ok(s.draws.length);assert.ok(!s.calls.some(c=>c.startsWith('/api/search?')));});
  await check('image_error_is_visible',async()=>{const s=await scenario('image_fail');assert.match(s.nodes.get('#search-feedback').textContent,/unavailable/);assert.equal(s.nodes.get('#empty').hidden,false);});
  for(const name of ['WISE0855',"Barnard's Star",'eps Ind B','RW Aur','R Dra'])await check('preset_'+name,async()=>{const s=await scenario('cached');s.nodes.get('#target').value=name;await s.nodes.get('#target').onchange();assert.equal(s.nodes.get('#submit').disabled,false);assert.ok(Number.isFinite(Number(s.form.elements.ra.value)));assert.ok(Number.isFinite(Number(s.form.elements.dec.value)));if(name==="Barnard's Star")assert.equal(s.nodes.get('#detector').value,'SPHEREx-D1');});
  await check('field_of_view_and_coordinate_invalidation',async()=>{const s=await scenario('cached');s.form.elements.fov.value='10';s.form.listeners.input({target:{name:'fov'}});assert.equal(s.nodes.get('#empty').hidden,false);assert.ok(s.nodes.get('#archive').href.includes('sr=5m'));s.form.elements.ra.value='5';s.form.listeners.input({target:{name:'ra'}});assert.equal(s.nodes.get('#target').value,'custom');});
  await check('detector_filter_empty_result',async()=>{const s=await scenario('cached');s.nodes.get('#detector').value='SPHEREx-D2';await s.nodes.get('#prepare').onclick();assert.match(s.nodes.get('#search-feedback').textContent,/No observations match/);});
  await check('date_range_and_reversed_dates',async()=>{const s=await scenario('cached');s.nodes.get('#from').value='2025-06-01';s.nodes.get('#through').value='2025-05-01';await s.nodes.get('#prepare').onclick();assert.match(s.nodes.get('#search-feedback').textContent,/From date/);s.nodes.get('#from').value='2025-09-01';s.nodes.get('#through').value='';await s.nodes.get('#prepare').onclick();assert.equal(s.posts.at(-1).ids.length,1);});
  for(const count of [6,12,24])await check('sample_size_'+count,async()=>{const s=await scenario('many');s.nodes.get('#count').value=String(count);await s.nodes.get('#prepare').onclick();assert.equal(s.posts.at(-1).ids.length,count);});
  await check('wavelength_match_toggle',async()=>{const s=await scenario('cached');s.nodes.get('#sequence').value='all';await s.nodes.get('#prepare').onclick();assert.equal(s.posts.at(-1).match,false);});
  await check('previous_next_timeline_keyboard',async()=>{const s=await scenario('cached');s.nodes.get('#next').onclick();assert.match(s.nodes.get('#date').textContent,/epoch-1/);s.nodes.get('#prev').onclick();assert.match(s.nodes.get('#date').textContent,/epoch-0/);s.nodes.get('#timeline').oninput({target:{value:'1'}});assert.match(s.nodes.get('#date').textContent,/epoch-1/);s.nodes.get('#sky').listeners.keydown({key:'ArrowLeft',preventDefault(){}});assert.match(s.nodes.get('#date').textContent,/epoch-0/);});
  await check('play_pause_and_all_speed_options',async()=>{const s=await scenario('cached');for(const value of ['1400','700','300']){s.nodes.get('#speed').value=value;s.nodes.get('#play').onclick();assert.equal([...s.timers.values()][0].ms,Number(value));[...s.timers.values()][0].fn();s.nodes.get('#play').onclick();assert.equal(s.timers.size,0);}});
  for(const mode of ['coadd','difference'])await check(mode,async()=>{const s=await scenario('cached');s.nodes.get('#mode').value=mode;s.nodes.get('#mode').onchange();await new Promise(setImmediate);assert.ok(s.draws.at(-1).includes(mode+'-0.png'));});
  await check('mixed_wavelength_comparison_guard',async()=>{const s=await scenario('cached');s.nodes.get('#group').value='all';s.nodes.get('#group').onchange();s.nodes.get('#mode').value='difference';s.nodes.get('#mode').onchange();assert.equal(s.nodes.get('#mode').value,'frame');assert.match(s.nodes.get('#search-feedback').textContent,/narrow wavelength/);});
  for(const overlay of ['gaia','wise'])await check('overlay_'+overlay,async()=>{const s=await scenario('cached');s.nodes.get('#overlay').value=overlay;await s.nodes.get('#overlay').onchange();await new Promise(setImmediate);assert.ok(s.markers.includes(overlay==='gaia'?'circle':'square'));s.nodes.get('#overlay').value='none';await s.nodes.get('#overlay').onchange();});
  await check('overlay_out_of_order_response_guard',async()=>{const s=await scenario('overlay_race');s.nodes.get('#overlay').value='gaia';const a=s.nodes.get('#overlay').onchange();s.nodes.get('#overlay').value='wise';const b=s.nodes.get('#overlay').onchange();s.pendingOverlays[1].resolve();await b;await new Promise(setImmediate);s.pendingOverlays[0].resolve();await a;await new Promise(setImmediate);assert.match(s.nodes.get('#overlay-note').textContent,/allwise/);assert.equal(s.markers.at(-1),'square');});
  await check('brightness_is_display_only',async()=>{const s=await scenario('cached'),date=s.nodes.get('#date').textContent;s.nodes.get('#brightness').value='140';s.nodes.get('#brightness').oninput();assert.equal(s.nodes.get('#sky').style.filter,'brightness(140%)');assert.equal(s.nodes.get('#date').textContent,date);});
  await check('metadata_gif_and_fits_exports',async()=>{const s=await scenario('cached');s.nodes.get('#export').onclick();assert.ok((await s.exports[0].text()).includes('obs-0'));assert.ok(s.created.some(a=>a.href?.endsWith('blink-0.gif')));assert.equal(s.nodes.get('#cutout-download').href,'/cutouts/fits-0');s.nodes.get('#next').onclick();assert.equal(s.nodes.get('#cutout-download').href,'/cutouts/fits-1');});
  await check('explicit_archive_refresh',async()=>{const s=await scenario('cached');await s.nodes.get('#refresh').onclick();for(let i=0;i<4;i++)await new Promise(setImmediate);assert.ok(s.calls.some(c=>c.includes('refresh=1')));});
  fs.writeFileSync(path.join(__dirname,'frontend-regression-results.json'),JSON.stringify({measurement:'Fixture-backed logic test duration, not real browser or archive latency',results},null,2));
  console.log(`${results.length} frontend option regressions passed (fixture-backed logic; not browser timings)`);
})().catch(error => {console.error(error); process.exitCode = 1;});

