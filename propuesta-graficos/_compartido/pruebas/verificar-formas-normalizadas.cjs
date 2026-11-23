const fs=require('fs'),vm=require('vm'),assert=require('assert');
const html=fs.readFileSync('observatorio.html','utf8'),start=html.indexOf('const cases=archiveRecords.map('),stop=html.indexOf('\n',start),mapping=html.slice(start,stop);
assert(start>=0);assert(!mapping.includes('raw.shape'));
const fixtures=[{id:1,shape:'Triangle',standardized_shape:null},{id:2,shape:'Ball',standardized_shape:'Sphere'},{id:3,shape:'Domedisc',standardized_shape:'Disc'},{id:4,shape:'other free text',standardized_shape:'Unknown'}].map(r=>({...r,date_event:'1997-01-01',duration_seconds:null}));
const ctx={archiveRecords:fixtures,coreFields:[],seed:()=>0};vm.createContext(ctx);vm.runInContext(mapping+'\nglobalThis.result=cases;',ctx);
assert.deepEqual(Array.from(ctx.result,r=>r.shape),['Sin clasificar','Sphere','Disc','Unknown']);assert.strictEqual(ctx.result[0].raw.shape,'Triangle');assert.equal(ctx.result.length,4);
const source=fs.readFileSync('investigaciones-eda.js','utf8'),line=source.split('\n').find(l=>l.includes('return caseContext[c.id].records.map('));assert(line);const guided={caseContext:{test:{records:fixtures}},c:{id:'test'}};vm.createContext(guided);vm.runInContext('globalThis.result=(()=>{'+line+'})();',guided);assert.deepEqual(Array.from(guided.result,r=>r.shape),['Sin clasificar','Sphere','Disc','Unknown']);assert.strictEqual(guided.result[0].raw.shape,'Triangle');
console.log('OK: mapeos reales del HTML y casos guiados usan standardized_shape; faltantes no heredan forma libre, originales e IDs conservados.');
