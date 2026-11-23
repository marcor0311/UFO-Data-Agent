/* Renderizador recuperado de DB Test/sketchbook-integrado.js. */
(function(root){'use strict';
const {A,esc,f,txt,line,svg,pick,sel,frame,blue,gray,grid,colors,memo,keyOf}=root.UAPSketchbookDrawing;
function temporal(id,rows,o={}){
 if(id==='D13'){const rs=rows.filter(r=>r.duration!==null).sort((a,b)=>a.duration-b.duration),groups=new Map(),max=Math.max(1,...rs.map(r=>r.duration)),x=v=>65+Math.log1p(v)/Math.log1p(max)*700;let path='M65 275';rs.forEach((r,i)=>path+=`H${x(r.duration)}V${275-(i+1)/Math.max(1,rs.length)*230}`);let body=`<path d="${path}" fill="none" stroke="${blue}" stroke-width="2"/>`;for(const t of [1,5,15,60].filter(t=>t<=max)){const matches=rs.filter(r=>r.duration<=t);groups.set(String(t),{key:'Hasta '+t+' min',rows:matches});body+=pick(`<circle cx="${x(t)}" cy="${275-matches.length/Math.max(1,rs.length)*230}" r="7" fill="${blue}"/>`+txt(x(t),305,t+' min','text-anchor="middle"'),t,t+' min: '+f(matches.length/Math.max(1,rs.length)*100)+'%')}[0,25,50,75,100].forEach(p=>body+=txt(50,280-p*2.3,p+'%','text-anchor="end"'));return frame(id,rows,{body,groups,note:`${rs.length} duraciones válidas / ${rows.length}. Eje X log(1+minutos); acumulación exacta sin bins.`})}
}
A.renderers['D13']=(rows,o={})=>rows.length?temporal('D13',rows,o):frame('D13',rows,{lead:'No hay registros en este alcance.'});
})(window);
