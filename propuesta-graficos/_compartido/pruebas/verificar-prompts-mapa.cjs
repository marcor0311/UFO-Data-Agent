// Conversation + geographic semantics contracts. Maps are adapters, not browser/GPU.
const fs=require('node:fs'),assert=require('node:assert/strict');
const prefix=fs.readFileSync('verificar-experiencia.cjs','utf8').split('(async()=>')[0];
const {context,document}=new Function('require',prefix+'\nreturn {context,document};')(require);
const exp=context.window.dataAgentExperience,journey=context.window.dataAgentCaseExperience,T=context.window.UAPMapTools,calls=[],checks=[];
context.window.UAPGeo.mount=options=>{calls.push(options);return {destroy(){},areaBounds:context.window.UAPGeo.areaFor(options.records,[],options.areaBounds)}};
function check(name,fn){fn();checks.push(name);console.log('OK · '+name)}
exp.ask('Cargá solo Los Ángeles en un radio de 30 km.');let last=calls.at(-1),ids=last.records.map(r=>r.id),area=last.areaBounds;
check('Un lugar/radio carga un área y filtra los registros por distancia',()=>{assert(last);assert(last.areaBounds);assert(last.records.length>0);assert(last.records.every(r=>T.distance([-118.25,34.052],[r.lon,r.lat])<=30))});
exp.ask('Mostralo con modelos 3D.');
check('El prompt cambia a modelos 3D conservando área, período e IDs',()=>{assert.equal(calls.at(-1).representation,'models');assert.equal(calls.at(-1).pitch,60);assert.deepEqual(calls.at(-1).areaBounds,area);assert.deepEqual(calls.at(-1).records.map(r=>r.id),ids)});
exp.ask('Volvé a puntos en el mapa 2D.');
check('El prompt vuelve a puntos y respeta 2D explícito',()=>{assert.equal(calls.at(-1).representation,'points');assert.equal(calls.at(-1).pitch,0);assert.deepEqual(calls.at(-1).records.map(r=>r.id),ids)});
exp.ask('Cargá solo esta área.');check('Esta área reutiliza el alcance existente sin inventar un lugar',()=>assert.deepEqual(calls.at(-1).areaBounds,area));
exp.ask('Cargá solo el área de latitud 0 longitud 0 en un radio de 1 km.');
check('Un área sin registros sigue mostrando cartografía y no inventa puntos',()=>{assert.equal(calls.at(-1).records.length,0);assert(calls.at(-1).areaBounds[0][0]<0);assert(!document.querySelector('#recoverData'))});
exp.reset();
for(const c of journey.journeys){journey.open(c.id,false);journey.ask('Cargá solo '+c.name+' en un radio de 20 km.');const before=calls.at(-1),ids=before.records.map(r=>r.id);journey.ask('Mostralo con figuras 3D.');check(c.name+': prompt de área seguido por figuras conserva IDs y límites',()=>{assert.equal(calls.at(-1).representation,'models');assert.equal(calls.at(-1).pitch,60);assert.deepEqual(JSON.parse(JSON.stringify(calls.at(-1).areaBounds)),JSON.parse(JSON.stringify(before.areaBounds)));assert.deepEqual(calls.at(-1).records.map(r=>r.id),ids)});journey.ask('Volvé a puntos en mapa 2D.');check(c.name+': puntos y 2D siguen disponibles por prompt',()=>{assert.equal(calls.at(-1).representation,'points');assert.equal(calls.at(-1).pitch,0)});journey.exit()}
check('Un lugar desconocido no usa silenciosamente la ubicación del caso',()=>assert(T.parsePrompt('Cargá solo París en un radio de 10 km',{focus:{lat:34,lon:-106}}).error));
check('Se rechazan radios inválidos antes de transformar el estado',()=>assert(T.parsePrompt('Cargá solo Socorro en un radio de 0 km').error));
exp.ask('Cargá solo Socorro en un radio de 10 km con modelos 3D.');check('Desde inicio, Socorro usa su corpus contextual y salta al mapa solicitado',()=>{assert.equal(journey.session.id,'socorro');assert.equal(calls.at(-1).representation,'models');assert.equal(calls.at(-1).viewKey,'socorro');assert(calls.at(-1).records.every(r=>T.distance([-106.8914,34.0584],[r.lon,r.lat])<=10))});journey.exit();exp.reset();
fs.writeFileSync('verificacion-experiencia/prompts-mapa.json',JSON.stringify({scope:'Prompt parsing, source filters and adapter state. No browser/GPU.',passed:checks},null,2)+'\n');
