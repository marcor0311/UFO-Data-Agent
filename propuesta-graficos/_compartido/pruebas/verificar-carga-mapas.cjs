// Loading lifecycle only. SDK/canvas are doubles; this is not a browser/GPU test.
const fs=require('node:fs'),assert=require('node:assert/strict');
const prefix=fs.readFileSync('verificar-experiencia.cjs','utf8').split('(async()=>')[0];
const {context,document,El,rafs}=new Function('require',prefix+'\nreturn {context,document,El,rafs};')(require);
const checks=[];
function check(name,fn){fn();checks.push(name);console.log('OK · '+name)}
class FakeMap {
  static overlayFault=false;
  constructor(options){this.options=options;this.controls=[];this.sources={};this.pitch=options.pitch||0;this.elevation=null;this.events={};this.canvas=new El('canvas');this.canvas.addEventListener=()=>{};this.dragPan={enable(){},disable(){}};this.boxZoom={disable(){}};}
  on(type,fn){(this.events[type]||=[]).push(fn);return this}
  once(type,fn){return this.on(type,fn)}
  emit(type,event){for(const fn of this.events[type]||[])fn(event)}
  addControl(control){this.controls.push(control);if(control instanceof FakeOverlay&&FakeMap.overlayFault)throw Error('Overlay integration failed')}
  addSource(id,spec){this.sources[id]=spec} addLayer(){} setTerrain(value){this.terrain=value} setSky(){} fitBounds(){} easeTo(value){if(value.pitch!==undefined)this.pitch=value.pitch} resize(){} remove(){}
  getStyle(){return {sources:{},layers:[]}} getPitch(){return this.pitch} getZoom(){return 6}
  getCenter(){return{lng:-106,lat:34}} getBearing(){return 0} getCanvas(){return this.canvas}
  queryTerrainElevation(){return this.elevation} triggerRepaint(){this.emit('render')}
}
class FakeOverlay{constructor(props){this.props=props}setProps(props){Object.assign(this.props,props)}finalize(){}}
class FakeLayer{constructor(props){this.props=props}}
context.window.maplibregl={Map:FakeMap,getVersion:()=> '5.24.0',setWorkerCount(){},NavigationControl:class{},ScaleControl:class{}};
context.window.deck={MapLibreOverlay:FakeOverlay,ScatterplotLayer:FakeLayer,TextLayer:FakeLayer,PathLayer:FakeLayer,LineLayer:FakeLayer,SimpleMeshLayer:FakeLayer};
async function mount(extra={}){const host=new El('div'),runtime=context.window.UAPGeo.mount({container:host,records:[{id:1,lat:34,lon:-106,city:'SDK test'}],...extra});await new Promise(resolve=>setImmediate(resolve));return{host,runtime,map:runtime.map}}
(async()=>{
  const normal=await mount();
  check('No se declara listo antes del render',()=>{assert(normal.map);assert(!normal.runtime.loaded);assert(!normal.host.querySelector('.geo-loading').hidden)});
  check('El mapa nace dentro del área con caché acotada y sin copias mundiales',()=>{assert.deepEqual(normal.map.options.bounds,normal.runtime.areaBounds);assert.equal(normal.map.options.renderWorldCopies,false);assert.equal(normal.map.options.maxTileCacheSize,96);const b=normal.map.options.maxBounds;assert(b[1][0]-b[0][0]<1);assert(b[1][1]-b[0][1]<1)});
  normal.map.emit('load');
  check('El DEM queda limitado al margen geográfico del área',()=>assert.deepEqual(normal.map.sources['uap-terrain'].bounds,normal.map.options.maxBounds.flat()));
  check('El primer render completa la carga',()=>{assert(normal.runtime.loaded);assert(normal.host.querySelector('.geo-loading').hidden)});
  normal.map.emit('error',{error:Error('Worker failed to load')});
  check('Un error tardío deja de ocultarse y revoca el estado listo',()=>{assert(!normal.runtime.loaded);assert(!normal.host.querySelector('.geo-loading').hidden);assert(normal.host.querySelector('.geo-loading').innerHTML.includes('Worker failed to load'))});normal.runtime.destroy();
  const geo=context.window.UAPGeo;
  check('El área explícita prevalece sobre referencias lejanas sin cambiar registros',()=>{const requested=[[-107,33.9],[-106.8,34.2]],area=geo.areaFor([{id:1,lat:34,lon:-106.9}],[{lat:35,lon:-105}],requested);assert.deepEqual(JSON.parse(JSON.stringify(area)),requested);assert.notEqual(area,requested);const single=geo.areaFor([{lat:34,lon:-106}]);assert(single[0][0]<single[1][0]&&single[0][1]<single[1][1])});
  const requested=[[-107,33.9],[-106.8,34.2]],focused=await mount({areaBounds:requested});check('El área solicitada llega al motor antes de cargar el estilo',()=>assert.deepEqual(JSON.parse(JSON.stringify(focused.map.options.bounds)),requested));focused.runtime.destroy();
  const changes=[],recovered=await mount({representation:'models',records:[{id:8,lat:34,lon:-106,shape:'triangle'}],onRepresentationChange:value=>changes.push(value)});recovered.map.emit('load');const overlay=recovered.map.controls.find(c=>c.props?.onError);overlay.props.onError(Error("initialization of SimpleMeshLayer({id: 'uap-solid-triangle'}): bad model"),{id:'uap-solid-triangle'});
  check('Un fallo de un modelo conserva el mapa y sus registros como puntos',()=>{assert(recovered.runtime.loaded);assert(recovered.host.querySelector('.geo-loading').hidden);assert.equal(recovered.runtime.representation,'points');assert.equal(recovered.host.querySelector('[data-geo-representation]').value,'points');assert.equal(recovered.runtime.layers.find(l=>l.props.id==='uap-events').props.data.length,1);assert(!recovered.runtime.layers.some(l=>l.props.id.startsWith('uap-solid-')));assert.deepEqual(changes,['points']);assert(recovered.host.querySelector('.geo-status').textContent.includes('misma área'))});recovered.runtime.destroy();
  FakeMap.overlayFault=true;const failed=await mount();failed.map.emit('load');
  check('Un fallo al integrar capas muestra el error y el respaldo',()=>{assert(!failed.runtime.loaded);assert(!failed.host.querySelector('.geo-loading').hidden);assert(failed.host.querySelector('.geo-loading').innerHTML.includes('Overlay integration failed'));assert(failed.host.querySelector('[data-geo-fallback]'))});failed.runtime.destroy();
  fs.writeFileSync('verificacion-experiencia/carga-mapas.json',JSON.stringify({scope:'Map loading lifecycle with SDK doubles. No browser, tiles or GPU.',passed:checks},null,2)+'\n');
})().catch(error=>{console.error(error);process.exitCode=1});
