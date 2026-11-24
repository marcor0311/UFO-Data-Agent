# DB Test/sketchbook-v2/generar.py, líneas 104–108. Usar exportar-estatico.py.
fig,ax=new();rs=[r for r in ca if r['dt'] and r['dt']['month']];m=np.array([[sum(r['year']==y and r['dt']['month']==mo for r in rs) for mo in range(1,13)]for y in years]);ax.imshow(m,cmap=cmap,aspect='auto',vmin=0);ax.set_xticks(range(12),['Ene','Feb','Mar','Abr','May','Jun','Jul','Ago','Sep','Oct','Nov','Dic']);ax.set_yticks(range(10),years);ax.tick_params(length=0,pad=8)
for i in range(10):
 for j in range(12):ax.text(j,i,str(m[i,j]),ha='center',va='center',fontsize=11,color='white' if m[i,j]>m.max()*.65 else INK)
note(fig,f'{len(rs)} reportes con mes / {n} · sin mes = {n-len(rs)} · celdas = conteos, no tasas ni estacionalidad confirmada')
save('D14','Calendario de meses por año','Matriz que permite distinguir un pico puntual de un patrón mensual repetido. Seleccionar filas, columnas o celdas conservará sus reportes; nunca se asignará un mes a las fechas anuales.',fig,'California · 1990–1999')
