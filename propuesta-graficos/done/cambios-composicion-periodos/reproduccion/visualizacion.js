/* Renderizador recuperado de DB Test/sketchbook-integrado.js. */
(function(root){'use strict';
const {A,esc,f,txt,line,svg,pick,sel,frame,blue,gray,grid,colors,memo,keyOf}=root.UAPSketchbookDrawing;
function temporal(id,rows,o={}){
 if(id==='D12'){const years=rows.map(r=>r.year).filter(Boolean),split=Math.floor((Math.min(...years)+Math.max(...years))/2),early=rows.filter(r=>r.year<=split),late=rows.filter(r=>r.year>split),defs=A.group(rows,'shape').slice(0,12).map(g=>[g.key,r=>r.shape===g.key]);let body='';const groups=new Map();defs.forEach(([name,test],i)=>{const x=210+early.filter(test).length/Math.max(1,early.length)*540,X=210+late.filter(test).length/Math.max(1,late.length)*540,y=42+i*28,rs=rows.filter(test);groups.set(String(i),{key:name,rows:rs});body+=pick(txt(195,y+4,name,'text-anchor="end"')+line(x,y,X,y,'stroke="#7c91aa" stroke-width="2"')+`<circle cx="${x}" cy="${y}" r="5" fill="${gray}"/><circle cx="${X}" cy="${y}" r="5" fill="${blue}"/>`+txt(805,y+4,f((late.filter(test).length/Math.max(1,late.length)-early.filter(test).length/Math.max(1,early.length))*100)+' pp','text-anchor="end"'),i,name)});for(let i=0;i<=4;i++)body+=txt(210+i*135,defs.length*28+60,i*25+'%','text-anchor="middle"');return frame(id,rows,{body,groups,height:defs.length*28+90,note:`Gris: hasta ${split}, N=${early.length}; azul: después de ${split}, N=${late.length}. Porcentaje dentro de cada período; sin deduplicación.`})}
}
A.renderers['D12']=(rows,o={})=>rows.length?temporal('D12',rows,o):frame('D12',rows,{lead:'No hay registros en este alcance.'});
})(window);
