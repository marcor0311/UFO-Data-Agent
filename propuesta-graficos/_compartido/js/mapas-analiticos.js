/* Shared map semantics: bounded areas and local solid meshes. No network or GPU required. */
(() => {
 const normal=s=>String(s||'').normalize('NFD').replace(/[\u0300-\u036f]/g,'').toLowerCase();
 const places=[['socorro',-106.8914,34.0584],['roswell',-104.523,33.394],['nimitz',-118.3,32.2],['san diego',-117.1611,32.7157],['los angeles',-118.25,34.052],['albuquerque',-106.6504,35.0844]];
 function radiusArea(center,radiusKm,label='Área delimitada'){
  const dy=radiusKm/111.195,dx=dy/Math.cos(center[1]*Math.PI/180);
  return{center:center.slice(),radiusKm,label,bounds:[[Math.max(-180,center[0]-dx),Math.max(-85.05,center[1]-dy)],[Math.min(180,center[0]+dx),Math.min(85.05,center[1]+dy)]]};
 }
 function distance(a,b){const rad=Math.PI/180,dy=(b[1]-a[1])*rad,dx=(b[0]-a[0])*rad,v=Math.sin(dy/2)**2+Math.cos(a[1]*rad)*Math.cos(b[1]*rad)*Math.sin(dx/2)**2;return 6371.0088*2*Math.atan2(Math.sqrt(v),Math.sqrt(Math.max(0,1-v)))}
 function contains(r,area){if(!area)return true;const lat=Number(r.lat),lon=Number(r.lon);if(r.lat==null||r.lon==null||String(r.lat).trim()===''||String(r.lon).trim()===''||!Number.isFinite(lat)||!Number.isFinite(lon))return false;if(area.polygon){let yes=false;const p=area.polygon;for(let i=0,j=p.length-1;i<p.length;j=i++)if((p[i][1]>lat)!==(p[j][1]>lat)&&lon<(p[j][0]-p[i][0])*(lat-p[i][1])/(p[j][1]-p[i][1])+p[i][0])yes=!yes;return yes}if(area.radiusKm)return distance(area.center,[lon,lat])<=area.radiusKm;const b=area.bounds;return lon>=b[0][0]&&lon<=b[1][0]&&lat>=b[0][1]&&lat<=b[1][1]}
 function parsePrompt(text,{area=null,focus=null}={}){
  const n=normal(text),style=/\b(modelos?|figuras?|objetos?)\s*(?:en\s*)?3d\b|formas?\s+(?:con\s+)?volumen/.test(n)?'models':/\bpuntos\b|marcadores simples/.test(n)?'points':null;
  const areaIntent=/(?:carga|cargar|limita|delimita|trabaja|trabajar|mostra|muestra|ver|solo).*\b(area|zona|radio|alrededor)\b|\bsolo\b.*(?:socorro|roswell|nimitz|san diego|los angeles|albuquerque)|\bradio\b.*\bkm\b/.test(n),clearArea=/quita.*(?:area|zona)|restablec.*(?:area|zona)|contexto completo|region completa/.test(n);
  if(clearArea)return{style,clearArea:true};if(!areaIntent)return{style};
  const radius=n.match(/(?:radio(?:\s+de)?\s*|alrededor.*?)(\d+(?:[.,]\d+)?)\s*km\b/),r=radius?Number(radius[1].replace(',','.')):10;
  if(r<.1||r>200)return{error:'Pedí un radio entre 0,1 y 200 km para trabajar con un área acotada.'};
  const coords=n.match(/latitud\s*[:=]?\s*(-?\d+(?:\.\d+)?).*?longitud\s*[:=]?\s*(-?\d+(?:\.\d+)?)/),place=places.find(p=>n.includes(p[0]));
  if(!place&&!coords&&/solo\s+(?!esta\b|este\b|el\b|la\b|los\b|las\b|un\b|una\b)[a-z]/.test(n))return{error:'No tengo coordenadas verificadas de ese lugar en este prototipo. Indicá latitud y longitud con un radio en km.'};
  if(!radius&&!place&&!coords&&/esta|actual|visible|seleccionad/.test(n)&&area?.bounds)return{style,area:{...area,bounds:area.bounds.map(p=>p.slice()),label:area.label||'Área actual'}};
  let center=coords?[Number(coords[2]),Number(coords[1])]:place?[place[1],place[2]]:focus?[focus.lon,focus.lat]:area?.center;
  if(!center&&area?.bounds)center=[(area.bounds[0][0]+area.bounds[1][0])/2,(area.bounds[0][1]+area.bounds[1][1])/2];
  if(!center||!center.every(Number.isFinite)||Math.abs(center[0])>179||Math.abs(center[1])>80)return{error:'Indicá un lugar reconocido o latitud y longitud, junto con un radio en km. También podés dibujar un rectángulo o lazo en el mapa.'};
  return{style,area:radiusArea(center,r,place?place[0].replace(/\b\w/g,c=>c.toUpperCase()):'Área delimitada')};
 }
 function boundary(area){if(!area)return[];if(area.polygon)return area.polygon.concat([area.polygon[0]]);if(!area.radiusKm){const [a,b]=area.bounds;return[a,[b[0],a[1]],b,[a[0],b[1]],a]}const out=[],rad=Math.PI/180,lat=area.center[1]*rad,lon=area.center[0]*rad,d=area.radiusKm/6371.0088;for(let i=0;i<=64;i++){const t=i/64*Math.PI*2,p=Math.asin(Math.sin(lat)*Math.cos(d)+Math.cos(lat)*Math.sin(d)*Math.cos(t)),q=lon+Math.atan2(Math.sin(t)*Math.sin(d)*Math.cos(lat),Math.cos(d)-Math.sin(lat)*Math.sin(p));out.push([q/rad,p/rad])}return out}
 const MODEL_LIMITS=Object.freeze({maxModels:60,maxTriangles:18000,compactModels:30,compactTriangles:9000,cellPixels:40});
 const DETAILS=Object.freeze({low:{longitude:14,latitude:10,radial:16,corner:2},medium:{longitude:20,latitude:12,radial:24,corner:4},high:{longitude:28,latitude:16,radial:40,corner:6}});
 const MODEL_FORMS=Object.freeze([["boomerang", "Boomerang"], ["changing", "Changing"], ["chevron", "Chevron"], ["cigar", "Cigar"], ["circle", "Circle"], ["cloud", "Cloud"], ["cone", "Cone"], ["crescent", "Crescent"], ["cross", "Cross"], ["cube", "Cube"], ["cylinder", "Cylinder"], ["diamond", "Diamond"], ["disc", "Disc"], ["dome", "Dome"], ["egg", "Egg"], ["fireball", "Fireball"], ["flash", "Flash"], ["formation", "Formation"], ["light", "Light"], ["other", "Other"], ["oval", "Oval"], ["rectangle", "Rectangle"], ["saucer", "Saucer"], ["sphere", "Sphere"], ["star", "Star"], ["teardrop", "Teardrop"], ["triangle", "Triangle"], ["unknown", "Unknown"]].map(([kind,label])=>Object.freeze({kind,label,symbolic:['Changing','Formation','Light','Fireball','Flash','Cloud','Star','Other','Unknown'].includes(label)})));
 const meshCache=new Map();
 function mesh(kind,detail='medium'){if(!MODEL_FORMS.some(f=>f.kind===kind))throw Error('Modelo no catalogado: '+kind);if(!Object.hasOwn(DETAILS,detail))detail='medium';const key=kind+':'+detail;if(meshCache.has(key))return meshCache.get(key);const settings=DETAILS[detail];const positions=[],normals=[];
  function tri(a,b,c,smooth=null){const u=b.map((v,i)=>v-a[i]),v=c.map((x,i)=>x-a[i]),n=[u[1]*v[2]-u[2]*v[1],u[2]*v[0]-u[0]*v[2],u[0]*v[1]-u[1]*v[0]],l=Math.hypot(...n);if(l<1e-10)return;for(const p of[a,b,c]){positions.push(...p);const normal=smooth?smooth(p):n.map(x=>x/l);normals.push(...normal)}}
  function append(source,scale=[1,1,1],offset=[0,0,0],angle=0){const c=Math.cos(angle),s=Math.sin(angle);for(let i=0;i<source.positions.length;i+=3){const v=source.positions.slice(i,i+3),n=source.normals.slice(i,i+3),x=v[0]*scale[0],y=v[1]*scale[1];positions.push(c*x-s*y+offset[0],s*x+c*y+offset[1],v[2]*scale[2]+offset[2]);const nx=n[0]/scale[0],ny=n[1]/scale[1],nz=n[2]/scale[2],l=Math.hypot(nx,ny,nz);normals.push((c*nx-s*ny)/l,(s*nx+c*ny)/l,nz/l)}}
  function box(size=[1,1,1],offset=[0,0,0],angle=0){const v=[[-1,-1,-1],[1,-1,-1],[1,1,-1],[-1,1,-1],[-1,-1,1],[1,-1,1],[1,1,1],[-1,1,1]].map(p=>{const x=p[0]*size[0]/2,y=p[1]*size[1]/2;return[x*Math.cos(angle)-y*Math.sin(angle)+offset[0],x*Math.sin(angle)+y*Math.cos(angle)+offset[1],p[2]*size[2]/2+offset[2]]});for(const [a,b,c,d]of [[0,3,2,1],[4,5,6,7],[0,1,5,4],[1,2,6,5],[2,3,7,6],[3,0,4,7]]){tri(v[a],v[b],v[c]);tri(v[a],v[c],v[d])}}
  function surface(fn,nu=settings.radial,nv=settings.latitude,invert=false){const smooth=p=>{return [0,0,1]};for(let j=0;j<nv;j++)for(let i=0;i<nu;i++){const a=i/nu,b=(i+1)/nu,c=j/nv,d=(j+1)/nv;const normalAt=(u,v)=>{const e=.0001,du=fn(u+e,v).map((x,k)=>x-fn(u-e,v)[k]),dv=fn(u,Math.min(1,v+e)).map((x,k)=>x-fn(u,Math.max(0,v-e))[k]),n=[dv[1]*du[2]-dv[2]*du[1],dv[2]*du[0]-dv[0]*du[2],dv[0]*du[1]-dv[1]*du[0]],length=Math.hypot(...n);return length<1e-9?[0,0,v<.5?1:-1]:n.map(x=>x/length*(invert?-1:1))};const points=[[a,c],[b,c],[b,d],[a,d]],at=points.map(([u,v])=>fn(u,v)),normalsAt=points.map(([u,v])=>normalAt(u,v));function face(ids){let k=0;tri(...ids.map(i=>at[i]),()=>normalsAt[ids[k++]])}if(invert){face([0,1,2]);face([0,2,3])}else{face([0,2,1]);face([0,3,2])}}}
  function lathe(profile){for(let j=0;j<profile.length-1;j++)for(let i=0;i<settings.radial;i++){const p=(a,k)=>[profile[k][0]*Math.cos(a),profile[k][0]*Math.sin(a),profile[k][1]],a=i/settings.radial*Math.PI*2,b=(i+1)/settings.radial*Math.PI*2;tri(p(a,j),p(b,j),p(b,j+1));tri(p(a,j),p(b,j+1),p(a,j+1))}}
  function torus(radius=.75,tube=.1,start=0,end=Math.PI*2){surface((u,v)=>{const a=start+u*(end-start),b=v*Math.PI*2;return[(radius+tube*Math.cos(b))*Math.cos(a),(radius+tube*Math.cos(b))*Math.sin(a),tube*Math.sin(b)]},settings.radial,Math.max(6,Math.floor(settings.latitude/2)),true)}
  const ball=(scale=[1,1,1],offset=[0,0,0])=>append(mesh('sphere',detail),scale,offset);
  if(!['disc','sphere','cigar','triangle'].includes(kind)){
   if(kind==='cube')box([1.25,1.25,1.25]);
   else if(kind==='rectangle')box([1.9,.85,.32]);
   else if(kind==='cross'){box([1.8,.38,.26]);box([.38,1.8,.26])}
   else if(kind==='chevron'){box([1.2,.28,.22],[-.43,0,0],Math.PI/4);box([1.2,.28,.22],[.43,0,0],-Math.PI/4)}
   else if(kind==='boomerang'){for(let i=0;i<10;i++){const a=-1.15+i*2.3/9;box([.33,.25,.16],[Math.sin(a),Math.cos(a)-.65,0],-a)}}
   else if(kind==='circle')lathe([[0,-.045],[.95,-.045],[.95,.045],[0,.045]]);
   else if(kind==='cylinder')lathe([[0,-.8],[.38,-.8],[.38,.8],[0,.8]]);
   else if(kind==='cone')lathe([[0,-.65],[.7,-.65],[0,.9]]);
   else if(kind==='dome')lathe([[0,-.12],[.9,-.12],[.88,.12],[.75,.4],[.5,.63],[0,.76]]);
   else if(kind==='saucer')lathe([[0,-.3],[.3,-.26],[.8,-.12],[1,0],[.8,.12],[.3,.26],[0,.3]]);
   else if(kind==='oval')ball([1.5,.8,.55]);
   else if(kind==='egg')surface((u,v)=>{const a=u*Math.PI*2,b=v*Math.PI,z=Math.cos(b);return[.65*Math.sin(b)*(1-.22*z)*Math.cos(a),.65*Math.sin(b)*(1-.22*z)*Math.sin(a),.95*z]});
   else if(kind==='teardrop')lathe([[0,-.65],[.4,-.6],[.6,-.3],[.5,0],[.27,.4],[0,1]]);
   else if(kind==='diamond'){const ring=[[.75,0,0],[0,.75,0],[-.75,0,0],[0,-.75,0]];for(let i=0;i<4;i++){tri([0,0,.85],ring[i],ring[(i+1)%4]);tri([0,0,-.6],ring[(i+1)%4],ring[i])}}
   else if(kind==='crescent')torus(.7,.16,.5,Math.PI*2-.5);
   else if(kind==='light'){ball([.7,.7,.7]);torus(.72,.045)}
   else if(kind==='fireball'){ball([.8,.8,.8],[-.35,0,0]);for(let i=0;i<3;i++)append(mesh('cigar',detail),[.55,.17,.17],[.6,i*.19-.19,0])}
   else if(kind==='flash'){ball([.28,.28,.28]);for(let i=0;i<8;i++){const a=i*Math.PI/4;box([.65,.06,.06],[Math.cos(a)*.6,Math.sin(a)*.6,0],a)}}
   else if(kind==='star'){const ring=Array.from({length:10},(_,i)=>{const a=i*Math.PI/5+Math.PI/2,r=i%2?.4:1;return[Math.cos(a)*r,Math.sin(a)*r]});for(let i=0;i<10;i++){const a=ring[i],b=ring[(i+1)%10];tri([0,0,.13],[...a,.13],[...b,.13]);tri([0,0,-.13],[...b,-.13],[...a,-.13]);tri([...a,-.13],[...b,-.13],[...b,.13]);tri([...a,-.13],[...b,.13],[...a,.13])}}
   else if(kind==='cloud'){for(const [x,y,z,r] of [[-.5,0,0,.6],[0,0,.2,.85],[.55,0,0,.65],[0,.3,-.25,.65]])ball([r,r*.7,r*.7],[x,y,z])}
   else if(kind==='formation'){for(let i=0;i<5;i++)ball([.24,.24,.24],[(i-2)*.44,Math.abs(i-2)*.3,0])}
   else if(kind==='changing')surface((u,v)=>{const a=u*Math.PI*2,b=v*Math.PI,r=.72+.17*Math.sin(a*3+b*2);return[r*Math.sin(b)*Math.cos(a),r*Math.sin(b)*Math.sin(a),r*Math.cos(b)]});
   else if(kind==='other'){box([.16,1.2,.16],[-.55,0,0]);box([.16,1.2,.16],[.55,0,0]);box([1.2,.16,.16],[0,.55,0]);ball([.24,.24,.24],[0,0,0]);box([1.2,.16,.16],[0,-.55,0])}
   else if(kind==='unknown'){torus(.45,.09,-.15,Math.PI*1.35);box([.16,.45,.16],[-.06,-.53,0]);ball([.16,.16,.16],[-.06,-.98,0])}
  }
  else if(kind==='triangle'){
   const corners=[[0,1.1],[-.95,-.65],[.95,-.65]],ring=[];
   for(let i=0;i<3;i++){const v=corners[i],prev=corners[(i+2)%3],next=corners[(i+1)%3],a=v.map((x,k)=>x+(prev[k]-x)*.12),b=v.map((x,k)=>x+(next[k]-x)*.12);for(let j=0;j<settings.corner;j++){const t=j/settings.corner;ring.push(v.map((x,k)=>(1-t)**2*a[k]+2*t*(1-t)*x+t*t*b[k]))}}
   const at=(p,scale,z)=>[p[0]*scale,p[1]*scale,z],rings=[[.92,-.14],[1,-.06],[1,.06],[.92,.16]];
   for(let i=0;i<ring.length;i++){const a=ring[i],b=ring[(i+1)%ring.length];tri([0,0,.16],at(a,.92,.16),at(b,.92,.16));tri([0,0,-.14],at(b,.92,-.14),at(a,.92,-.14));for(let k=0;k<rings.length-1;k++){const [s,z]=rings[k],[t,w]=rings[k+1];tri(at(a,s,z),at(b,s,z),at(b,t,w));tri(at(a,s,z),at(b,t,w),at(a,t,w))}}
  }
  else if(kind==='disc'){const profile=[[0,-.16],[.5,-.14],[.95,-.06],[1,0],[.77,.09],[.4,.12],[.28,.26],[0,.28]];for(let j=0;j<profile.length-1;j++)for(let i=0;i<settings.radial;i++){const point=(r,z,t)=>[r*Math.cos(t),r*Math.sin(t),z],t=i/settings.radial*Math.PI*2,u=(i+1)/settings.radial*Math.PI*2,[r,z]=profile[j],[s,w]=profile[j+1],a=point(r,z,t),b=point(r,z,u),c=point(s,w,u),d=point(s,w,t);const smooth=p=>{const radial=Math.hypot(p[0],p[1]),dz=w-z,dr=s-r,length=Math.hypot(dz,dr);return radial<1e-8?[0,0,z<0?-1:1]:[p[0]/radial*dz/length,p[1]/radial*dz/length,-dr/length]};tri(a,b,c,smooth);tri(a,c,d,smooth)}}
  else{const scales=kind==='cigar'?[1.3,.32,.32]:[.7,.7,.7],p=(a,b)=>[Math.cos(a)*Math.sin(b)*scales[0],Math.sin(a)*Math.sin(b)*scales[1],Math.cos(b)*scales[2]];for(let j=0;j<settings.latitude;j++)for(let i=0;i<settings.longitude;i++){const a=i/settings.longitude*Math.PI*2,b=(i+1)/settings.longitude*Math.PI*2,c=j/settings.latitude*Math.PI,d=(j+1)/settings.latitude*Math.PI;const smooth=v=>{const n=v.map((x,k)=>x/(scales[k]*scales[k])),length=Math.hypot(...n);return n.map(x=>x/length)};tri(p(a,c),p(a,d),p(b,d),smooth);tri(p(a,c),p(b,d),p(b,c),smooth)}}
  // deck.gl 9.4 normalizes attributes before constructing luma Geometry.
  // Its normalizer reads descriptor.value/size, not a naked typed array.
  // CPU aliases and GPU attributes share buffers; geometry is not duplicated.
  const colors=new Float32Array(positions.map((v,i)=>{const z=positions[i-i%3+2],canopy=kind==='disc'&&z>.18;return (canopy?[.055,.14,.34]:[.11,.32,.72])[i%3]}));
  const vertices=new Float32Array(positions),directions=new Float32Array(normals),value={positions:vertices,normals:directions,colors,topology:'triangle-list',vertexCount:vertices.length/3,attributes:{POSITION:{size:3,value:vertices},NORMAL:{size:3,value:directions},COLOR_0:{size:3,value:colors}}};meshCache.set(key,value);return value;
 }
 // Count triangles after instancing, not only the cost of one shared mesh.
 function planModels(candidates,{zoom=0,compact=false}={}){
  const maxModels=compact?MODEL_LIMITS.compactModels:MODEL_LIMITS.maxModels,maxTriangles=compact?MODEL_LIMITS.compactTriangles:MODEL_LIMITS.maxTriangles,eligible=candidates.filter(r=>MODEL_FORMS.some(f=>f.kind===r.kind)).slice(0,maxModels);
  let detail=zoom>=14&&eligible.length<=12?'high':zoom>=11&&eligible.length<=30?'medium':'low';
  const cost=level=>eligible.reduce((sum,r)=>sum+mesh(r.kind,level).positions.length/9,0);
  while(cost(detail)>maxTriangles&&detail!=='low')detail=detail==='high'?'medium':'low';
  let triangles=0;const rows=[];for(const row of eligible){const count=mesh(row.kind,detail).positions.length/9;if(triangles+count>maxTriangles)continue;rows.push(row);triangles+=count}
  return{rows,detail,triangles,maxTriangles,maxModels};
 }
 function shapeKind(shape){const n=normal(shape).trim();return MODEL_FORMS.find(f=>f.kind===n)?.kind||({disk:'disc',disco:'disc',triangulo:'triangle',luz:'light'}[n]??null)}
 const metersPerPixel=(lat,zoom)=>78271.51696402048*Math.cos(Number(lat)*Math.PI/180)/2**zoom;
 // Reference dimensions belong to the visualization, never inferred report facts.
 const metricCache=new Map();
 function modelMetrics(kind){if(metricCache.has(kind))return metricCache.get(kind);const geometry=mesh(kind,'high'),extent=[Infinity,Infinity,Infinity,-Infinity,-Infinity,-Infinity];for(let i=0;i<geometry.positions.length;i++){const k=i%3,v=geometry.positions[i];extent[k]=Math.min(extent[k],v);extent[k+3]=Math.max(extent[k+3],v)}const value={extent,diameter:Math.max(extent[3]-extent[0],extent[4]-extent[1],extent[5]-extent[2])};metricCache.set(kind,value);return value}
 function modelAppearance(zoom,shape,referenceMeters=12){const meters=Number.isFinite(referenceMeters)&&referenceMeters>=2&&referenceMeters<=100?referenceMeters:12;return{meters,clearanceMeters:50,minPixels:18+18*Math.max(0,Math.min(1,(zoom-10)/8))}}
 function layoutModels(candidates,{viewport,zoom,ground=()=>0,maxModels=60,width=900,height=520,referenceMeters=12}={}){
  const occupied=[],result=[];
  for(const row of candidates){if(result.length>=maxModels)break;const metrics=modelMetrics(row.kind),extent=metrics.extent,appearance=modelAppearance(zoom,row.shape,referenceMeters),groundLevel=ground(row);let scale=appearance.meters/metrics.diameter,position,box;
   const measure=()=>{position=[+row.lon,+row.lat,groundLevel-extent[2]*scale+appearance.clearanceMeters];const origin=viewport.projectPosition(position),unit=viewport.getDistanceScales(position).unitsPerMeter,m=viewport.pixelProjectionMatrix;box=[Infinity,Infinity,-Infinity,-Infinity];for(let i=0;i<8;i++){const v=[0,1,2].map(k=>origin[k]+extent[k+((i>>k)&1)*3]*scale*unit[k]),w=m[3]*v[0]+m[7]*v[1]+m[11]*v[2]+m[15];if(w<=0)return false;const x=(m[0]*v[0]+m[4]*v[1]+m[8]*v[2]+m[12])/w,y=(m[1]*v[0]+m[5]*v[1]+m[9]*v[2]+m[13])/w;box=[Math.min(box[0],x),Math.min(box[1],y),Math.max(box[2],x),Math.max(box[3],y)]}return box.every(Number.isFinite)};
   if(!measure())continue;
   // Screen minimum preserves readable symbols without moving their geographic anchor.
   // Twelve metres is a reference, not a measured reconstruction; dense symbols fall back to points.
   // Bounded correction: at most four projections per candidate, no binary search per frame.
   for(let pass=0;pass<3;pass++){
    const span=Math.max(box[2]-box[0],box[3]-box[1]);
    if(span>=appearance.minPixels*.99)break;
    scale*=Math.min(100000,appearance.minPixels/Math.max(.0001,span));
    if(!measure())break;
   }
   if(!box.every(Number.isFinite)||Math.max(box[2]-box[0],box[3]-box[1])<appearance.minPixels*.95)continue;
   if(box[2]<0||box[3]<0||box[0]>width||box[1]>height)continue;
   const padded=[box[0]-7,box[1]-7,box[2]+7,box[3]+7];if(occupied.some(b=>padded[0]<b[2]&&padded[2]>b[0]&&padded[1]<b[3]&&padded[3]>b[1]))continue;
   occupied.push(padded);result.push({...row,modelPosition:position,modelScale:scale,modelBox:box,modelClearance:appearance.clearanceMeters,modelReferenceMeters:appearance.meters});
  }return result;
 }
 window.UAPMapTools={boundary,parsePrompt,radiusArea,distance,contains,mesh,planModels,layoutModels,modelAppearance,modelMetrics,MODEL_FORMS,MODEL_LIMITS,shapeKind,metersPerPixel};
})();
