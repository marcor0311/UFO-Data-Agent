# Biblioteca de propuestas gráficas

Recuperación del prototipo **DB Test** y de su Sketchbook v2 para evaluación visual y técnica. La biblioteca agrupa 13 recuperaciones, cuatro propuestas experimentales y dos ideas. El mapa 3D de duración por forma conserva sus componentes reutilizables con el ensamblaje pendiente.

| Propuesta | Categoría | Estado |
| --- | --- | --- |
| [Visualización de modelos 3D](done/modelos-3d/) | Modelos | Implementada |
| [Comparación de reportes](pendientes/comparacion-reportes/) | Registros | Recuperada |
| [Mapas 2D](pendientes/mapas-2d/) | Cartografía | Recuperada |
| [Mapa 3D de duración por forma](pendientes/mapa-3d-duracion-por-forma/) | Cartografía | Recuperada (parcial) |
| [Reportes por año](pendientes/reportes-por-ano/) | Tiempo | Recuperada |
| [Formas reportadas](pendientes/formas-reportadas/) | Composición | Recuperada |
| [Histograma de duración](done/histograma-duracion/) | Distribución | Implementada (`histogram`) |
| [Región por año](done/region-por-ano/) | Tiempo y región | Implementada (`matrix`) |
| [Calendario por meses del año](done/calendario-meses/) | Tiempo | Implementada (`month_calendar`) |
| [Día de la semana por hora consignada](done/dia-semana-hora/) | Tiempo | Implementada (`hour_weekday`) |
| [Composición por archivo](done/composicion-por-archivo/) | Procedencia | Implementada (`stacked`) |
| [Mapa 2D de clusters](pendientes/mapa-2d-clusters/) | Cartografía | Recuperada |
| [Mapa 3D de clusters](pendientes/mapa-3d-clusters/) | Cartografía | Recuperada |
| [Cronología](done/cronologia/) | Tiempo | Implementada (`timeline`) |
| [Cambios de composición entre períodos](done/cambios-composicion-periodos/) | Composición | Implementada (`dumbbell`) |
| [Duración acumulada](done/duracion-acumulada/) | Distribución | Implementada (`ecdf`) |
| [Duración de testigos](pendientes/duracion-testigos/) | Relación entre variables | Experimental |
| [Machine Learning – Clustering](pendientes/machine-learning-clustering/) | Método analítico | Solo idea |
| [Perfiles de duración y K-means](pendientes/perfiles-duracion-k-means/) | Método analítico | Solo idea |

Las capturas de las vistas implementadas están en [fotos/](fotos/). Las propuestas están separadas en [pendientes/](pendientes/) y [done/](done/), que reúne las ya implementadas en el Data Agent. Al implementar una, se mueve de `pendientes/` a `done/` y se actualiza su estado.

## Consultar las propuestas

Las carpetas reúnen los archivos originales, sus extractos, las fichas y los prompts de origen. Las láminas de `referencias/` proceden de DB Test. Para ver una interacción, sigue la ruta al prototipo original indicada en su ficha.

[Recursos y datos compartidos](_compartido/README.md). Los snapshots grandes y la base SQLite están en [DB Test](../DB%20Test/).

El código de montaje y exportación preparado durante la recuperación se conserva en [avance/](avance/README.md).
