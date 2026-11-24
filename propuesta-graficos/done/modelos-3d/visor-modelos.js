/* Local morphology viewer. Shares the map meshes; no SDK, network or records required. */
(() => {
 const forms=window.UAPMapTools.MODEL_FORMS.map(f=>[f.kind,f.label]);
 function open(){
  document.querySelector('#modelViewer')?.close();
  const dialog=document.createElement('dialog');dialog.id='modelViewer';dialog.setAttribute('aria-labelledby','modelViewerTitle');
  dialog.innerHTML='<div class="model-viewer-heading"><h2 id="modelViewerTitle">Modelos 3D</h2><button data-model-close aria-label="Cerrar visor">Cerrar</button></div><p>28 categorías de standardized_shape, con una representación propia. Changing, Formation, Cloud, Light, Fireball, Flash, Star, Other y Unknown usan símbolos interpretativos; no reconstruyen objetos verificados.</p><div class="model-viewer-toolbar"><label>Forma <select data-model-kind><option value="all">Todas · 28 categorías</option>'+forms.map(([id,label])=>'<option value="'+id+'">'+label+'</option>').join('')+'</select></label><label>Acercamiento <input data-model-zoom type="range" min="0.7" max="1.6" step="0.05" value="1" aria-label="Acercamiento del modelo"></label><button data-model-reset>Restablecer vista</button></div><div class="model-viewer-stage"><canvas tabindex="0" aria-label="Modelos 3D interactivos. Arrastrá para rotar o usá las flechas del teclado."></canvas><div class="model-viewer-labels" aria-hidden="true"></div><p data-model-error hidden></p></div><p class="model-viewer-help">Arrastrá para rotar · flechas para girar · seleccioná una forma para verla en detalle.</p>';
  document.body.append(dialog);dialog.showModal();
  const canvas=dialog.querySelector('canvas'),gl=canvas.getContext('webgl',{antialias:true,alpha:false}),labels=dialog.querySelector('.model-viewer-labels');
  let yaw=.4,pitch=.75,zoom=1,kind='all',drag=null,frame=0,dead=false,observer;const buffers=[],shaders=[];let program;
  function dispose(){if(dead)return;dead=true;cancelAnimationFrame(frame);observer?.disconnect();if(gl){buffers.forEach(b=>gl.deleteBuffer(b));shaders.forEach(s=>gl.deleteShader(s));if(program)gl.deleteProgram(program)}dialog.remove()}
  dialog.addEventListener('close',dispose);dialog.querySelector('[data-model-close]').onclick=()=>dialog.close();
  const error=message=>{const p=dialog.querySelector('[data-model-error]');p.hidden=false;p.textContent=message;canvas.hidden=true};
  if(!gl){error('Este visor requiere WebGL. Las formas siguen disponibles como puntos en el mapa.');return}
  try{
   function shader(type,source){const s=gl.createShader(type);shaders.push(s);gl.shaderSource(s,source);gl.compileShader(s);if(!gl.getShaderParameter(s,gl.COMPILE_STATUS))throw Error(gl.getShaderInfoLog(s));return s}
   program=gl.createProgram();gl.attachShader(program,shader(gl.VERTEX_SHADER,'attribute vec3 position;attribute vec3 normal;attribute vec3 color;uniform mat3 rotation;uniform vec2 scale;varying vec3 n;varying vec3 pigment;void main(){vec3 p=rotation*position;n=rotation*normal;pigment=color;gl_Position=vec4(p.x*scale.x,p.y*scale.y,-p.z*.18,1.0);}'));
   gl.attachShader(program,shader(gl.FRAGMENT_SHADER,'precision mediump float;varying vec3 n;varying vec3 pigment;void main(){vec3 v=normalize(n);float light=max(0.0,dot(v,normalize(vec3(-.4,.7,1.0))));float spec=pow(max(0.0,dot(v,normalize(vec3(-.2,.35,1.0)))),28.0);gl_FragColor=vec4(pigment*(.48+.52*light)+vec3(spec*.18),1.0);}'));
   gl.linkProgram(program);if(!gl.getProgramParameter(program,gl.LINK_STATUS))throw Error(gl.getProgramInfoLog(program));gl.useProgram(program);gl.enable(gl.DEPTH_TEST);gl.clearColor(.965,.968,.977,1);
   const attributes=['position','normal','color'].map(name=>gl.getAttribLocation(program,name)),rotation=gl.getUniformLocation(program,'rotation'),scale=gl.getUniformLocation(program,'scale');
   const meshes=new Map(forms.map(([id])=>{const mesh=window.UAPMapTools.mesh(id,'medium'),data=[mesh.positions,mesh.normals,mesh.colors].map(values=>{const b=gl.createBuffer();buffers.push(b);gl.bindBuffer(gl.ARRAY_BUFFER,b);gl.bufferData(gl.ARRAY_BUFFER,values,gl.STATIC_DRAW);return b});return[id,{data,count:mesh.vertexCount}]}));
   function draw(){frame=0;if(dead)return;const rect=canvas.getBoundingClientRect(),dpr=Math.min(devicePixelRatio||1,2),w=Math.max(1,Math.round(rect.width*dpr)),h=Math.max(1,Math.round(rect.height*dpr));if(canvas.width!==w||canvas.height!==h){canvas.width=w;canvas.height=h}gl.clear(gl.COLOR_BUFFER_BIT|gl.DEPTH_BUFFER_BIT);
    const cy=Math.cos(yaw),sy=Math.sin(yaw),cp=Math.cos(pitch),sp=Math.sin(pitch);gl.uniformMatrix3fv(rotation,false,new Float32Array([cy,sy*sp,-sy*cp,-sy,cy*sp,-cy*cp,0,cp,sp]));
    const visible=kind==='all'?forms:forms.filter(f=>f[0]===kind);labels.innerHTML=visible.map(([,label])=>'<span>'+label+'</span>').join('');labels.classList.toggle('single',kind!=='all');const columns=kind==='all'?4:1,rowCount=Math.ceil(visible.length/columns);labels.style.gridTemplateColumns='repeat('+columns+',1fr)';labels.style.gridTemplateRows='repeat('+rowCount+',1fr)';
    visible.forEach(([id],i)=>{const cols=columns,rows=rowCount,vw=Math.floor(w/cols),vh=Math.floor(h/rows),x=(i%cols)*vw,y=h-(Math.floor(i/cols)+1)*vh;gl.viewport(x,y,vw,vh);gl.uniform2f(scale,.57*zoom*Math.min(1,vh/vw),.57*zoom*Math.min(1,vw/vh));const mesh=meshes.get(id);mesh.data.forEach((b,j)=>{gl.bindBuffer(gl.ARRAY_BUFFER,b);gl.enableVertexAttribArray(attributes[j]);gl.vertexAttribPointer(attributes[j],3,gl.FLOAT,false,0,0)});gl.drawArrays(gl.TRIANGLES,0,mesh.count)});
   }
   function schedule(){if(!dead&&!frame)frame=requestAnimationFrame(draw)}
   canvas.onpointerdown=e=>{drag=[e.clientX,e.clientY];canvas.setPointerCapture(e.pointerId)};canvas.onpointermove=e=>{if(!drag)return;yaw+=(e.clientX-drag[0])*.009;pitch=Math.max(-1.4,Math.min(1.4,pitch+(e.clientY-drag[1])*.009));drag=[e.clientX,e.clientY];schedule()};canvas.onpointerup=canvas.onpointercancel=()=>{drag=null};
   canvas.onkeydown=e=>{if(!['ArrowLeft','ArrowRight','ArrowUp','ArrowDown'].includes(e.key))return;e.preventDefault();yaw+=(e.key==='ArrowRight'?.12:e.key==='ArrowLeft'?-.12:0);pitch=Math.max(-1.4,Math.min(1.4,pitch+(e.key==='ArrowUp'?.12:e.key==='ArrowDown'?-.12:0)));schedule()};
   dialog.querySelector('[data-model-kind]').onchange=e=>{kind=e.target.value;schedule()};dialog.querySelector('[data-model-zoom]').oninput=e=>{zoom=Number(e.target.value);schedule()};dialog.querySelector('[data-model-reset]').onclick=()=>{yaw=.4;pitch=.75;zoom=1;dialog.querySelector('[data-model-zoom]').value='1';schedule()};
   observer=new ResizeObserver(schedule);observer.observe(canvas);schedule();
  }catch(e){error('No se pudo iniciar el visor 3D en este dispositivo. '+e.message)}
 }
 window.UAPModelViewer={open,forms};
})();
