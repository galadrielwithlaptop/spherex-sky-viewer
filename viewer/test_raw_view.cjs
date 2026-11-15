const fs=require('node:fs'),vm=require('node:vm'),assert=require('node:assert/strict');
async function scenario(ok=true){
 const nodes=new Map(),links=[{textContent:'Provenance JSON',href:'/processed/manifest.json',hidden:false},{textContent:'Download blink GIF',href:'/processed/blink.gif',hidden:false}],draws=[],timers=[];
 const node=s=>{if(!nodes.has(s))nodes.set(s,{value:'',textContent:'',hidden:false});return nodes.get(s);};node('#display-source').value='raw';node('#mode').value='frame';
 const draw=()=>{};draw.token=0;
 const scope={Map,JSON,Image:class{set src(v){this._src=v;this.onload?.();}get src(){return this._src;}},manifest:null,indices:[0],at:0,job:'a'.repeat(24),draw,$:node,ctx:{clearRect(){},drawImage(img){draws.push(img.src);}},performance:{now:()=>1},recordLatency(){},paintOverlay(){},firstFrameSince:null,stop(){},message(s){node('#status').textContent=s;},clearTimeout(){},setTimeout(fn,ms){timers.push(ms);},document:{querySelector:()=>links[0],querySelectorAll:()=>links},fetch:async()=>({ok,json:async()=>({processing:'Archive IMAGE',stretch:{low:1,high:10},frames:[{id:'frame',image:'/products/raw/0.png',valid_fraction:1}]})})};
 vm.createContext(scope);vm.runInContext(fs.readFileSync(__dirname+'/web/raw-view.js','utf8'),scope);scope.manifest={frames:[{id:'frame',image:'/processed/0.png',utc:'date',wavelength_um:3.4,fits_key:'fits',valid_fraction:.8}],groups:[]};
 return {scope,nodes,node,links,draws,timers};
}
(async()=>{
 let s=await scenario();await s.scope.drawArchiveFrame();assert.deepEqual(s.draws,['/products/raw/0.png']);assert.match(s.links[0].href,/raw\/manifest.json$/);assert.equal(s.links[1].hidden,true);const info=JSON.parse(s.node('#provenance').textContent);assert.equal(info.psf_applied,false);assert.equal(info.zodi_subtracted,false);assert.equal(info.quality_mask_applied,false);
 s=await scenario();s.node('#mode').value='coadd';await s.scope.drawArchiveFrame();assert.equal(s.node('#mode').value,'frame');assert.ok(!s.draws.some(x=>x.includes('processed')));
 s=await scenario(false);await s.scope.drawArchiveFrame();assert.equal(s.draws.length,0);assert.equal(s.timers.length,1);
 s=await scenario();s.node('#display-source').value='processed';s.node('#display-source').onchange();assert.equal(s.links[1].hidden,false);assert.ok(!s.links[0].href.includes('/raw/'));
 console.log('4 archive-IMAGE display regressions passed (fixture-backed logic; no processed-image fallback)');
})().catch(e=>{console.error(e);process.exitCode=1;});
