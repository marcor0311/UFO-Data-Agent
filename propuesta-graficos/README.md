# Biblioteca de propuestas gráficas

Propuestas recuperadas del prototipo **DB Test** y de su Sketchbook v2, más las ideas nuevas. Solo hay dos estados:

- [done/](done/): la propuesta ya es una vista o un análisis del Data Agent.
- [pendientes/](pendientes/README.md): todavía no se puede responder con un gráfico del agente. Hoy no queda ninguna.

Al implementar una propuesta, se mueve de `pendientes/` a `done/` y se actualiza su estado. Las preguntas que cada vista responde, y las que no tienen respuesta en los datos, están en [docs/preguntas-y-graficos.md](../docs/preguntas-y-graficos.md).

## Done

| Propuesta | Categoría | Vista o análisis del agente |
| --- | --- | --- |
| [Reportes por año](done/reportes-por-ano/) | Tiempo | `timeseries` |
| [Calendario por meses del año](done/calendario-meses/) | Tiempo | `month_calendar` |
| [Día de la semana por hora consignada](done/dia-semana-hora/) | Tiempo | `hour_weekday` |
| [Cronología](done/cronologia/) | Tiempo | `timeline` |
| [Región por año](done/region-por-ano/) | Tiempo y región | `matrix` |
| [Formas reportadas](done/formas-reportadas/) | Composición | `bars` |
| [Composición por archivo](done/composicion-por-archivo/) | Procedencia | `stacked` |
| [Cambios de composición entre períodos](done/cambios-composicion-periodos/) | Composición | `dumbbell` |
| [Histograma de duración](done/histograma-duracion/) | Distribución | `histogram` |
| [Duración acumulada](done/duracion-acumulada/) | Distribución | `ecdf` |
| [Mapas 2D](done/mapas-2d/) | Cartografía | `points` |
| [Globo 3D](done/globo-3d/) | Cartografía | `globe` |
| [Visualización de modelos 3D](done/modelos-3d/) | Modelos | estilo “Modelos” de `points` |
| [Mapa 3D de duración por forma](done/mapa-3d-duracion-por-forma/) | Cartografía | `boxplot` y `density` con `median_duration_min` |
| [Mapa 2D de clusters](done/mapa-2d-clusters/) | Cartografía | análisis `clusters` |
| [Mapa 3D de clusters](done/mapa-3d-clusters/) | Cartografía | análisis `clusters` en el mapa 3D |
| [Duración de testigos](done/duracion-testigos/) | Relación entre variables | `scatter` (`duration_witnesses`) |
| [Comparación de reportes](done/comparacion-reportes/) | Registros | análisis `compare_reports` |
| [Machine Learning – Clustering](done/machine-learning-clustering/) | Método analítico | análisis `clusters` y `kmeans_profiles` |
| [Perfiles de duración y K-means](done/perfiles-duracion-k-means/) | Método analítico | análisis `kmeans_profiles` |

## Vistas nuevas sin ficha de DB Test

Surgieron al cubrir las preguntas sin gráfico. Están en el [motor](../scripts/gold_query.py), los [análisis](../scripts/gold_analysis.py) y el [registro web](../apps/web/src/components/views/registry.tsx).

| Vista | Responde |
| --- | --- |
| `boxplot` | Medianas y cuantiles de duración, testigos, distancia o puntuaciones por grupo. |
| `histogram` y `ecdf` con `measure` | Distribución de testigos, cola de duración, distancia, sentimiento y otras medidas, con un panel por fuente. |
| `scatter` | Duración × testigos, VADER × RoBERTa y perfiles K-means. |
| `waterfall` | Aporte de cada categoría al cambio entre dos períodos (`period_change`). |
| `bump` | Entradas y salidas del top acumulado (`rank_over_time`). |
| `curve` | Concentración de informes en las celdas más concurridas (`concentration`). |
| `density` divergente y por años | Celdas que suben o bajan (`cell_change`) y primera aparición con deslizador (`first_appearance`). |
| `links` | Celdas unidas con su instalación más cercana (`facility_links`). |
| `funnel` y `upset` | Cobertura que se pierde de año a hora y datos que faltan juntos. |
| `compare` | Dos informes campo a campo. |

## Recursos compartidos

El código original de DB Test que comparten las fichas (extractos, estilos, MapLibre, deck.gl y Three.js) está en [_compartido/](_compartido/README.md). Los snapshots grandes y la base SQLite están en [DB Test](../DB%20Test/).

El código de montaje y exportación preparado durante la recuperación está en [_compartido/reproduccion/](_compartido/reproduccion/README.md) y, para cada propuesta, en su carpeta `reproduccion/`.
