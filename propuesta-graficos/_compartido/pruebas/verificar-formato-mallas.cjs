// Runs the exact shipped deck.gl normalizer and luma Geometry code, without browser/GPU.
const fs=require('node:fs'),path=require('node:path'),vm=require('node:vm'),assert=require('node:assert/strict');
const args=process.argv.slice(2),htmlIndex=args.indexOf('--html'),htmlPath=htmlIndex>=0?path.resolve(args[htmlIndex+1]):path.join(__dirname,'observatorio.html'),html=fs.readFileSync(htmlPath,'utf8');
const payload=id=>{const match=html.match(new RegExp('<script id="'+id+'"[^>]*>([\\s\\S]*?)<\\/script>'));assert(match,'Missing embedded SDK '+id);return Buffer.from(match[1],'base64')};
for(const [id,file]of [['uap-sdk-deck','deck.gl-9.4.0.min.js'],['uap-sdk-maplibre','maplibre-gl-5.24.0.js']])assert(payload(id).equals(fs.readFileSync(path.join(__dirname,'assets/vendor',file))),'Embedded SDK differs: '+id);
const sdk={exports:{}};new Function('module','exports',payload('uap-sdk-deck').toString('utf8'))(sdk,sdk.exports);const deck=sdk.exports;
assert.equal(deck.VERSION,'9.4.0');
const app=html.match(/<script id="data-agent-app">([\s\S]*?)<\/script>/)?.[1];assert(app,'Missing application payload');new vm.Script(app,{filename:'embedded-data-agent-app.js'});
const start=app.indexOf('/* Shared map semantics:'),end=app.indexOf('/* Geographic runtime.',start);assert(start>=0&&end>start,'Missing embedded map semantics');
const target={};new Function('window',app.slice(start,end))(target);
const T=target.UAPMapTools,checks=[];
function bounds(mesh,id){const layer=new deck.SimpleMeshLayer({id,mesh,_instanced:false});layer.state={positionBounds:null};return layer.getBounds()}
function check(name,fn){fn();checks.push(name);console.log('OK · '+name)}
check('Se reproduce el error del formato anterior con el SDK real',()=>{const m=T.mesh('triangle');assert.throws(()=>bounds({positions:m.positions,normals:m.normals},'legacy-triangle'),/Cannot read properties of undefined \(reading 'length'\)/)});
assert.equal(T.MODEL_FORMS.length,28);
for(const {kind} of T.MODEL_FORMS)for(const detail of ['low','medium','high'])check(kind+' / '+detail+': normalización real y límites finitos',()=>{const m=T.mesh(kind,detail);assert.equal(m.attributes.POSITION.size,3);assert.equal(m.attributes.NORMAL.size,3);assert.equal(m.attributes.POSITION.value,m.positions);assert.equal(m.attributes.NORMAL.value,m.normals);assert.equal(m.vertexCount,m.positions.length/3);const b=bounds(m,'sdk-'+kind+'-'+detail);assert.equal(b.length,2);assert(b.flat().every(Number.isFinite));assert(b[0].every((value,i)=>value<b[1][i]));assert.equal(m,T.mesh(kind,detail))});
if(!args.includes('--no-report'))fs.writeFileSync(path.join(__dirname,'verificacion-experiencia/formato-mallas-sdk.json'),JSON.stringify({htmlSha256:require('node:crypto').createHash('sha256').update(html).digest('hex'),deckVersion:deck.VERSION,scope:'Real shipped SimpleMeshLayer.getBounds -> mesh normalizer -> luma Geometry and attribute formats. No WebGL/shader/browser certification.',legacyErrorReproduced:true,passed:checks},null,2)+'\n');
