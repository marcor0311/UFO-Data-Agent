# DB Test/sketchbook-v2/generar.py, líneas 109–114. Usar exportar-estatico.py.
# Exact recorded hour only; preserve timezone caveat.
rs=[r for r in ml if r['dt'] and r['dt']['ordinal'] is not None and re.search(r'[T ]\d{2}:\d{2}',r['date'])];m=np.zeros((7,24),int)
for r in rs:
 d=datetime.date.fromisoformat(r['date'][:10]);h=int(re.search(r'[T ](\d{2}):',r['date']).group(1));m[d.weekday(),h]+=1
fig,ax=new();ax.imshow(m,cmap=cmap,aspect='auto',vmin=0);ax.set_xticks(np.arange(0,24,2));ax.set_yticks(range(7),['Lun','Mar','Mié','Jue','Vie','Sáb','Dom']);ax.tick_params(length=0,pad=10);ax.set_xlabel('Hora consignada en el registro');note(fig,f'N con día y hora = {len(rs)} / {len(ml)} · sin conversión de zona horaria · medianoche puede incluir horas por defecto')
save('D15','Día de la semana × hora consignada','Explora patrones de documentación horaria y permite abrir cualquier bloque. Es una comparación de las horas escritas en el archivo; el gráfico avisará sobre zonas desconocidas y posibles valores por defecto.',fig,'California y entorno · 2001–2007')
