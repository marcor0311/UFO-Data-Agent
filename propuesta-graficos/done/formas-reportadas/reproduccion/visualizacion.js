/* Renderizador recuperado de DB Test/sketchbook-integrado.js. */
(function(root){'use strict';
const {A,esc,f,txt,line,svg,pick,sel,frame,blue,gray,grid,colors,memo,keyOf}=root.UAPSketchbookDrawing;
A.renderers['D2']=(rows,o={})=>rows.length?A.render('categories',rows,{dimension:'shape',...o}):frame('D2',rows,{lead:'No hay registros en este alcance.'});
})(window);
