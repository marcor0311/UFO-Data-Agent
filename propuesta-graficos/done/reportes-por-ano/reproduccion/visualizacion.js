/* Renderizador recuperado de DB Test/sketchbook-integrado.js. */
(function(root){'use strict';
const {A,esc,f,txt,line,svg,pick,sel,frame,blue,gray,grid,colors,memo,keyOf}=root.UAPSketchbookDrawing;
function temporal(id,rows,o={}){
 if(id==='D1'){const years=[...new Set(rows.map(r=>r.year).filter(Boolean))].sort(),max=Math.max(1,...years.map(y=>rows.filter(r=>r.year===y).length)),groups=new Map(),w=700/Math.max(1,years.length);let b='';for(let i=0;i<=4;i++)b+=line(65,275-i*235/4,795,275-i*235/4)+txt(52,280-i*235/4,f(max*i/4,0),'text-anchor="end"');years.forEach((y,i)=>{const rs=rows.filter(r=>r.year===y),h=rs.length/max*235;groups.set(String(y),{key:String(y),rows:rs});b+=pick(`<rect x="${70+i*w}" y="${275-h}" width="${w*.65}" height="${h}" rx="3" fill="${blue}"/>`+txt(70+i*w+w*.325,265-h,rs.length,'text-anchor="middle"')+txt(70+i*w+w*.325,298,y,'text-anchor="middle"'),y,y+': '+rs.length)});return frame(id,rows,{body:b,groups,note:'Eje de conteo desde cero. Seleccioná un año para seguir sus reportes.'})}
}
A.renderers['D1']=(rows,o={})=>rows.length?temporal('D1',rows,o):frame('D1',rows,{lead:'No hay registros en este alcance.'});
})(window);
