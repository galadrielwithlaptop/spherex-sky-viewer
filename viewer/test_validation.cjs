const fs=require('node:fs'),vm=require('node:vm'),assert=require('node:assert/strict');
const scope={};vm.createContext(scope);vm.runInContext(fs.readFileSync(__dirname+'/web/validation.js','utf8').split('function validateViewerInputs')[0],scope);
const base={ra:'133.7951291667',dec:'-7.2451472222',fov:'5',target:'WISE0855',detector:'SPHEREx-D4',sequence:'matched',count:'12',from:'',through:''};
assert.equal(scope.viewerInputIssues(base).length,0);
const bad={ra:['','-1','360','Infinity','NaN','08h55m'],dec:['','-91','91','Infinity'],fov:['0','NaN','61'],target:['unknown'],detector:['SPHEREx-D7'],sequence:['bad'],count:['0','25','1.5'],from:['2025-02-30','bad'],through:['2025-13-01']};let n=1;
for(const [key,values] of Object.entries(bad))for(const value of values){assert.ok(scope.viewerInputIssues({...base,[key]:value}).some(x=>x.key===key),key+'='+value);n++;}
for(const [ra,dec] of [['0','-90'],['359.999999999','90']]){assert.equal(scope.viewerInputIssues({...base,ra,dec}).length,0);n++;}
assert.ok(scope.viewerInputIssues({...base,from:'2025-10-31',through:'2025-05-01'}).some(x=>x.key==='through'));n++;
assert.equal(scope.viewerInputIssues({...base,from:'2025-05-01',through:'2025-05-01'}).length,0);n++;
console.log(n+' input-validation cases passed');
