# DB Test/sketchbook-v2/generar.py, líneas 97–101. Usar exportar-estatico.py.
fig,ax=new();style(ax,'x');cats=[k for k,v in cn.most_common(7)];a=[r for r in ca if r['year']<=1994];b=[r for r in ca if r['year']>=1995]
for i,k in enumerate(cats):
 p=100*sum(r['shape']==k for r in a)/len(a);q=100*sum(r['shape']==k for r in b)/len(b);ax.plot([p,q],[i,i],color='#c9d8c7',lw=3);ax.scatter([p,q],[i,i],color=[GRAY,GREEN],s=85,zorder=3);ax.text(max(p,q)+1,i,f'{q-p:+.1f} pp',va='center',fontsize=11)
ax.set_yticks(range(len(cats)),cats);ax.invert_yaxis();ax.set_xlim(0,46);ax.set_xlabel('Porcentaje de todos los reportes del intervalo');note(fig,f'Gris: 1990–1994 (N={len(a)}) · verde: 1995–1999 (N={len(b)}) · 7 categorías visibles; cola accesible')
save('D12','Cambios de composición entre períodos','El gráfico de puntos unidos muestra qué formas ganan o pierden participación sin confundirlo con el crecimiento del total. La implementación permitirá elegir dos intervalos y ver conteos junto con porcentajes.',fig,'California · 1990–1994 frente a 1995–1999')
