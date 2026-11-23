// State/adapter contracts only; no browser or GPU.
const fs=require('node:fs'),assert=require('node:assert/strict');
const prefix=fs.readFileSync('verificar-experiencia.cjs','utf8').split('(async()=>')[0];
const {context}=new Function('require',prefix+'\nreturn {context};')(require);
const exp=context.window.dataAgentExperience,journey=context.window.dataAgentCaseExperience;
const calls=[],checks=[],area=[[-120,33],[-116,38]];
context.window.UAPGeo.mount=options=>{calls.push(options);return {destroy(){}}};
function check(name,fn){fn();checks.push(name);console.log('OK · '+name)}
exp.ask('Mostrame el mapa 2D.');const ids=calls.at(-1).records.slice(0,5).map(r=>r.id);calls.at(-1).onSelect(ids,area);exp.ask('Mostrame el mapa 3D.');
check('Archivo conserva límites e IDs del área al pasar a 3D',()=>{assert.deepEqual(calls.at(-1).areaBounds,area);assert.deepEqual(calls.at(-1).records.map(r=>r.id),ids);assert.equal(calls.at(-1).pitch,60)});
exp.choose(ids,'Selección del gráfico');exp.ask('Mostrame el mapa 2D.');
check('Una selección nueva del gráfico vuelve al área de California y descarta límites anteriores',()=>{assert.deepEqual(JSON.parse(JSON.stringify(calls.at(-1).areaBounds)),[[-124.6,32.4],[-114.1,42.1]]);assert.equal(calls.at(-1).areaLabel,'California · área de trabajo')});
for(const c of journey.journeys){journey.open(c.id,false);journey.ask('Mostrame el mapa 2D.');const rows=calls.at(-1).records,ids=rows.slice(0,5).map(r=>r.id),selectedArea=context.window.UAPGeo.areaFor(rows.slice(0,5));calls.at(-1).onSelect(ids,selectedArea);journey.ask('Mostrame el mapa 3D.');check(c.name+' conserva área e IDs entre 2D y 3D',()=>{assert.deepEqual(JSON.parse(JSON.stringify(calls.at(-1).areaBounds)),JSON.parse(JSON.stringify(selectedArea)));assert.deepEqual(JSON.parse(JSON.stringify(calls.at(-1).records.map(r=>r.id))),JSON.parse(JSON.stringify(ids)));assert.equal(calls.at(-1).pitch,60)});journey.ask('Quitá los filtros y analizá el contexto completo.');journey.ask('Mostrame el mapa 2D.');check(c.name+' permite volver al contexto regional',()=>assert.equal(calls.at(-1).areaBounds,null));journey.exit()}
fs.writeFileSync('verificacion-experiencia/area-investigacion.json',JSON.stringify({scope:'State and mapping adapter contracts; no browser/GPU.',passed:checks},null,2)+'\n');exp.reset();
