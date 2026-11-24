/* Renderizador recuperado de DB Test/sketchbook-integrado.js. */
(function(root){'use strict';
const {A,esc,f,txt,line,svg,pick,sel,frame,blue,gray,grid,colors,memo,keyOf}=root.UAPSketchbookDrawing;
function temporal(id,rows,o={}){
 if(id==='D16'){const by=id==='D16'?'year':'source',gs=A.group(rows,by).sort((a,b)=>a.key.localeCompare(b.key)),types=id==='D16'?[...new Set(rows.map(r=>r.source))]:['año','mes','día','Sin fecha'],groups=new Map();let body='';gs.slice(0,15).forEach((g,i)=>{let x=200;body+=txt(184,50+i*28,g.key,'text-anchor="end"');types.forEach((type,j)=>{const rs=g.rows.filter(r=>id==='D16'?r.source===type:(r.dt?.precision||'Sin fecha')===type),w=rs.length/Math.max(1,g.n)*570,key=i+'|'+j;groups.set(key,{key:g.key+' · '+type,rows:rs});body+=pick(`<rect x="${x}" y="${33+i*28}" width="${w}" height="21" fill="${colors[j%colors.length]}"/>`,key,`${g.key} · ${type}: ${rs.length}/${g.n}`);x+=w})});types.forEach((t,i)=>body+=txt(30+(i%4)*205,gs.length*28+70+Math.floor(i/4)*20,t,`style="fill:${colors[i%colors.length]}"`));return frame(id,rows,{body,groups,height:Math.max(280,gs.length*28+130),note:'Barras al 100%; cada segmento conserva sus conteos e IDs. Compará magnitudes en D1/D11.'})}
}
A.renderers['D16']=(rows,o={})=>rows.length?temporal('D16',rows,o):frame('D16',rows,{lead:'No hay registros en este alcance.'});
})(window);
