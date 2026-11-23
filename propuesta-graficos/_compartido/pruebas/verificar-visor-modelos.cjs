const fs=require('fs'),vm=require('vm'),assert=require('assert');
let draws=0,deleted=0,disconnected=0,frame=0,dialog;const callbacks=new Map();
const gl=new Proxy({getShaderParameter:()=>true,getProgramParameter:()=>true,getAttribLocation:()=>0,createBuffer:()=>({}),createShader:()=>({}),createProgram:()=>({}),getUniformLocation:()=>({}),drawArrays:()=>draws++,deleteBuffer:()=>deleted++},{get:(o,k)=>k in o?o[k]:(/^[A-Z_]+$/.test(k)?1:()=>{})});
function el(){return{hidden:false,value:'1',style:{},classList:{toggle(){}},getBoundingClientRect:()=>({width:800,height:500}),setPointerCapture(){},setAttribute(){}}}
const canvas={...el(),getContext:()=>gl},children=Object.fromEntries(['.model-viewer-labels','[data-model-close]','[data-model-error]','[data-model-kind]','[data-model-zoom]','[data-model-reset]'].map(k=>[k,el()]));
const document={querySelector:()=>null,body:{append(){}},createElement:()=>{dialog={...el(),querySelector:s=>s==='canvas'?canvas:children[s],showModal(){this.open=true},addEventListener(k,f){this[k]=f},close(){this.open=false;this.closeEvent?.()},remove(){this.removed=true}};dialog.addEventListener=(k,f)=>dialog.closeEvent=f;return dialog}};
const context={window:{},document,devicePixelRatio:1,requestAnimationFrame:f=>{callbacks.set(++frame,f);return frame},cancelAnimationFrame:id=>callbacks.delete(id),ResizeObserver:class{observe(){}disconnect(){disconnected++}},console};vm.createContext(context);for(const f of ['mapas-analiticos.js','visor-modelos.js'])vm.runInContext(fs.readFileSync(f,'utf8'),context);
const flush=()=>{const list=[...callbacks.values()];callbacks.clear();list.forEach(f=>f())};
context.window.UAPModelViewer.open();assert(dialog.open);assert.equal(context.window.UAPModelViewer.forms.length,28);flush();assert.equal(draws,28);
children['[data-model-kind]'].onchange({target:{value:'disc'}});flush();assert.equal(draws,29);
canvas.onkeydown({key:'ArrowRight',preventDefault(){}});flush();assert.equal(draws,30);
canvas.onpointerdown({clientX:10,clientY:10,pointerId:1});canvas.onpointermove({clientX:30,clientY:40});canvas.onpointerup();flush();assert.equal(draws,31);
children['[data-model-zoom]'].oninput({target:{value:'1.5'}});flush();assert.equal(draws,32);
children['[data-model-reset]'].onclick();flush();assert.equal(draws,33);assert.equal(children['[data-model-zoom]'].value,'1');
for(const [id,label] of context.window.UAPModelViewer.forms){children['[data-model-kind]'].onchange({target:{value:id}});flush();assert(children['.model-viewer-labels'].innerHTML.includes(label));}assert.equal(draws,61);
children['[data-model-close]'].onclick();assert(dialog.removed);assert.equal(deleted,84);assert.equal(disconnected,1);assert.equal(callbacks.size,0);
canvas.getContext=()=>null;context.window.UAPModelViewer.open();assert(!children['[data-model-error]'].hidden);assert(canvas.hidden);dialog.close();
console.log('OK: 28 categorías compartidas con el mapa, forma individual, rotación, zoom, restablecer, cierre/liberación y ausencia de WebGL. Contratos con GPU simulada; no render real.');
