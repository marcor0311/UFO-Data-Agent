# Preguntas sobre Silver y Gold y su gráfico en el Data Agent

Inventario de las preguntas que admite el archivo, agrupadas por tema, con la respuesta a una sola duda: **¿el Data Agent tiene un gráfico para responderla?**

Cada pregunta se tradujo a la consulta tipada (`query_gold`) o al análisis (`analyze`) que usaría el agente, y se ejecutó contra la carga Gold aprobada (`caca588120ee…`) con [scripts/validar_preguntas.py](../scripts/validar_preguntas.py). Una pregunta cuenta como respondida cuando el motor devuelve filas con su vista. Las que no tienen respuesta explican qué dato falta.

```sh
apps/api/.venv/bin/python scripts/validar_preguntas.py
```

El script termina con error si una pregunta que hoy tiene gráfico deja de tenerlo, así que sirve también como prueba de regresión. Mide la capacidad del contrato y de las vistas; no mide si el modelo elige siempre esa consulta, que es lo que cubren las [evaluaciones del agente](../scripts/run_agent_evals.py).

## Resumen

| Resultado | Antes | Ahora |
| --- | ---: | ---: |
| Con gráfico completo | 74 | 122 |
| Con gráfico parcial (recortado o aproximado) | 4 | 0 |
| Sin gráfico: faltaba una métrica o una vista sobre Gold | 33 | 0 |
| Sin gráfico: el dato solo estaba en Silver | 15 | 0 |
| Sin respuesta posible: el dato no existe | — | 4 |
| **Total** | **126** | **126** |

Las cuatro sin respuesta no dependen de una vista: la población por país no está en ninguna capa, el texto del relato no se conserva desde Bronze, el número de objetos solo existe en Bronze (Silver lo descarta) y los “ovnis reales” no existen por diseño, porque el archivo cuenta informes. El agente lo dice y ofrece lo más cercano.

## Qué cambió para responderlas

| Hueco | Solución |
| --- | --- |
| El mapa de puntos cortaba en 500 informes | `points` dibuja toda la selección: un punto por informe hasta 20.000 y, por encima, uno por coordenada con su número de informes. `density` admite hasta 20.000 celdas. |
| Mezclas con muchas categorías | `stacked` reúne la cola de la segunda dimensión en “Otras” y conserva los totales. |
| Medianas y cuantiles | Métricas `median_duration_min`, `p25_…`, `p75_…`, `median_witnesses`, `median_nuclear_distance_km`, `median_sentiment_score`, `median_richness_score` y la vista `boxplot`. |
| Porcentajes condicionados | Banderas por informe en Gold y ratios recalculados: `core_fields_pct`, `map_usable_pct`, `map_without_country_pct`, `placeholder_risk_pct`, `description_pct`, `known_shape_pct`, `long_duration_pct`, `within_10km_pct`, `within_50km_pct`, `confirmed_group_pct`, `reused_id_pct` y otros. |
| Atributos que no se podían agrupar | `witness_band`, `pending_pair_band`, `source_record_reused` y `emotion_28_dominant` son dimensiones; `richness_score`, `sentiment_score`, NRC y las siete emociones tienen métricas. |
| Distribuciones de otras medidas | `histogram` y `ecdf` aceptan `measure` (testigos, cola de duración, distancia, sentimiento, VADER, RoBERTa, riqueza, calidad, engaño) y un panel por fuente; `scatter` cruza duración × testigos y VADER × RoBERTa. |
| Cálculos de varias etapas | Herramienta `analyze` con 20 análisis tipados (patrón `match_result` del agente de Messi): cascada, fuente dominante, anomalías diarias, interanual, día típico por mes, desvío mes × hora, ranking acumulado, concentración, cambio por celda, primera aparición, clusters, enlaces con instalaciones, embudo, UpSet, comparación de informes, K-means, retención, solapamiento de fuentes, diversidad y observado/esperado. |
| Datos que solo estaban en Silver | Gold publica estado o provincia (EE. UU., Canadá, Australia) y ciudad, sonido, dirección, clima, entorno, Vallée, código de evento, fecha y hora originales, etiquetas de comportamiento, señales de posible engaño, pares candidatos con método y similitud, el registro de reglas de calidad y de cambios de Silver, los registros de recuperación de naves y de encuentros nucleares, y el catálogo completo de instalaciones. |

Gold se reconstruyó con el pipeline oficial y superó sus 890 controles; la verificación independiente, las certificadas y las evaluaciones de Gold siguen en verde.

## Inventario

“Antes” es el estado al empezar esta revisión; “Ahora”, el de la carga actual. “Sí (cifras)” significa que la respuesta es una o pocas cifras y se muestra como tarjetas. El número de la primera columna es el de la pregunta en el script.

### Volumen y procedencia

12 de 12 con gráfico; 3 nuevas o completadas en esta versión.

| # | Pregunta | Antes | Ahora | Vista o motivo |
| ---: | --- | --- | --- | --- |
| 1 | ¿Cuántos informes hay en total? | Sí | Sí (cifras) | `table` |
| 2 | ¿Cuántos informes aporta cada fuente? | Sí | Sí | `bars` |
| 3 | ¿De qué orígenes (NUFORC, MUFON, Blue Book…) vienen los informes? | Sí | Sí | `bars` |
| 4 | ¿Cuántos informes vienen de NUFORC? | Sí | Sí (cifras) | `table` |
| 5 | ¿Qué colección contiene cada fuente? | Sí | Sí | `matrix` |
| 6 | ¿Qué orígenes aparecen dentro de cada fuente? | Sí | Sí | `matrix` |
| 7 | ¿Qué fuente tiene más informes con evidencia externa? | Sí | Sí | `bars` |
| 8 | ¿Desde qué año y hasta qué año tiene informes cada fuente? | Sí | Sí (cifras) | `table` |
| 9 | ¿Cómo cambia la mezcla de fuentes por década? | Sí | Sí | `stacked` |
| 10 | ¿Cuánto aportó cada fuente al cambio entre 2000–2009 y 2010–2019? (cascada) | No | Sí | `waterfall` · análisis `period_change` |
| 11 | ¿En qué fuente se concentra cada origen (fuente dominante y su porcentaje)? | No | Sí | `bars` · análisis `dominant_share` |
| 12 | ¿Cuántos informes de cada fuente reutilizan un ID de su archivo de origen? | No | Sí | `bars` |

### Tiempo

17 de 17 con gráfico; 4 nuevas o completadas en esta versión.

| # | Pregunta | Antes | Ahora | Vista o motivo |
| ---: | --- | --- | --- | --- |
| 13 | ¿Cómo evolucionan los informes por año? | Sí | Sí | `timeseries` |
| 14 | ¿Cuántos informes hay por década? | Sí | Sí | `timeseries` |
| 15 | ¿Qué año tuvo más informes? | Sí | Sí | `timeseries` |
| 16 | ¿Cómo evoluciona cada fuente año a año? | Sí | Sí | `timeseries` |
| 17 | ¿Qué meses del año acumulan más informes? | Sí | Sí | `bars` |
| 18 | ¿Hay picos o estacionalidad mes a mes entre 1990 y 2020? | Sí | Sí | `month_calendar` |
| 19 | ¿Cómo evoluciona la serie mensual (año-mes) desde 2000? | Sí | Sí | `timeseries` |
| 20 | ¿Qué días de la semana y a qué hora se consignan más informes? | Sí | Sí | `hour_weekday` |
| 21 | ¿A qué hora del día se reportan más? | Sí | Sí | `bars` |
| 22 | ¿Qué día de la semana tiene más informes? | Sí | Sí | `bars` |
| 23 | ¿Qué pasó el 13 de marzo de 1997 (luces de Phoenix)? | Sí | Sí | `timeline` |
| 24 | ¿Qué fechas concretas acumulan más informes? | Sí | Sí | `bars` |
| 25 | ¿Cómo se reparte la hora consignada dentro de cada mes (mes × hora)? | Sí | Sí | `matrix` |
| 26 | ¿Qué fechas quedan muy por encima de su referencia local de 28 días? (picos anómalos) | No | Sí | `timeseries` · análisis `daily_anomalies` |
| 27 | ¿Cuánto cambió cada mes respecto al mismo mes del año anterior? | No | Sí | `timeseries` · análisis `yoy_change` |
| 28 | ¿Qué mes tiene el volumen diario típico más alto? (cajas por día) | No | Sí | `boxplot` · análisis `daily_distribution_by_month` |
| 29 | ¿En qué meses la hora consignada se aleja más del patrón global? | No | Sí | `matrix` · análisis `hour_month_deviation` |

### Geografía

19 de 20 con gráfico; 9 nuevas o completadas en esta versión; 1 sin el dato.

| # | Pregunta | Antes | Ahora | Vista o motivo |
| ---: | --- | --- | --- | --- |
| 30 | ¿Qué países tienen más informes? | Sí | Sí | `bars` |
| 31 | Mapa de informes por país | Sí | Sí | `choropleth` |
| 32 | ¿Cuántos informes hay en México? | Sí | Sí (cifras) | `table` |
| 33 | ¿En cuántos países distintos hay informes? | Sí | Sí (cifras) | `table` |
| 34 | ¿Dónde se concentran los informes (celdas de 5°)? | Sí | Sí | `density` |
| 35 | ¿Dónde se concentran en celdas de 1° en Estados Unidos? | Sí | Sí | `density` |
| 36 | Muéstrame los informes de Brasil en el mapa | Parcial | Sí | `points` · 5.300 informes, todos |
| 37 | Muéstrame en un globo todos los informes con coordenadas | Sí | Sí | `globe` |
| 38 | ¿Cuántos informes hay en el área que dibujé (Rectángulo/Lazo)? | Parcial | Sí | `points` · 6.766 informes, todos |
| 39 | ¿Cómo cambió el top de países por década? | Sí | Sí | `matrix` |
| 40 | ¿Qué formas predominan en cada país? | Sí | Sí | `matrix` |
| 41 | ¿De qué fuente vienen los informes de cada país? | Sí | Sí | `stacked` |
| 42 | ¿Cuántos informes hay en California / Texas / una ciudad? | No (Silver) | Sí (cifras) | `table` |
| 43 | ¿Cuántos informes por 100.000 habitantes tiene cada país? | No | No | Ni Silver ni Gold tienen población; habría que incorporar una fuente externa fijada. |
| 44 | ¿Cuándo aparece por primera vez cada celda de 1° (crecimiento de cobertura)? | No | Sí | `density` · análisis `first_appearance` |
| 45 | ¿Qué países entraron o salieron del top 10 acumulado desde 1940? (bump chart) | No | Sí | `bump` · análisis `rank_over_time` |
| 46 | ¿Qué proporción de informes cae en el 1 % de celdas más concurridas? | No | Sí | `curve` · análisis `concentration` |
| 47 | ¿Qué celdas de EE. UU. subieron o bajaron entre 2000s y 2010s? | No | Sí | `density` · análisis `cell_change` |
| 48 | ¿Cuántas fuentes distintas contribuyen a cada celda? | No | Sí | `density` |
| 49 | ¿Qué celdas acumulan ≥4 informes en una misma semana? (clusters) | No | Sí | `clusters` · análisis `clusters` |

### Descriptores

25 de 27 con gráfico; 8 nuevas o completadas en esta versión; 2 sin el dato.

| # | Pregunta | Antes | Ahora | Vista o motivo |
| ---: | --- | --- | --- | --- |
| 50 | ¿Qué formas se reportan más? | Sí | Sí | `bars` |
| 51 | ¿Cuántos informes de triángulos hay? | Sí | Sí (cifras) | `table` |
| 52 | ¿Qué formas ganaron o perdieron peso entre los 70 y los 2000? | Sí | Sí | `dumbbell` |
| 53 | ¿Cómo cambia la mezcla de formas por década? | Parcial | Sí | `stacked` |
| 54 | ¿Qué fuentes aportan cada forma? | Sí | Sí | `matrix` |
| 55 | ¿De qué colores se reportan? | Sí | Sí | `bars` |
| 56 | ¿Cuántos informes de color rojo exacto (tono)? | Sí | Sí | `bars` |
| 57 | ¿Qué colores tienen las esferas? | Sí | Sí | `bars` |
| 58 | ¿Qué forma y color aparecen juntos? | Sí | Sí | `matrix` |
| 59 | ¿Cómo se mueven los objetos reportados? | Sí | Sí | `bars` |
| 60 | ¿Qué movimiento tiene cada forma? | Sí | Sí | `matrix` |
| 61 | ¿Cuánto duran en general (tramos)? | Sí | Sí | `bars` |
| 62 | ¿Cómo se distribuye la duración en minutos? | Sí | Sí | `histogram` |
| 63 | ¿Qué porcentaje dura hasta 5 minutos? | Sí | Sí | `ecdf` |
| 64 | ¿Cuánto duran los triángulos frente a los discos? | Sí | Sí | `matrix` |
| 65 | ¿Qué clases Hynek (CE1, CE2, CE3…) aparecen? | Sí | Sí | `bars` |
| 66 | ¿Cuántos informes mencionan medios (foto/video)? | Sí | Sí | `bars` |
| 67 | ¿Qué fuentes tienen más informes con descripción? | Sí | Sí | `bars` |
| 68 | ¿Cuántos testigos suele tener un informe? | No | Sí | `bars` |
| 69 | ¿Duran más los informes con más testigos? (dispersión) | No | Sí | `scatter` · medida `duration_witnesses` |
| 70 | ¿Cuál es la mediana de duración por forma? | No | Sí | `boxplot` |
| 71 | ¿Dónde están las duraciones largas de la cola (> 1 h)? | No | Sí | `histogram` · medida `duration_tail` |
| 72 | ¿Qué sonido, dirección o clima describen los testigos? | No (Silver) | Sí | `bars` |
| 73 | ¿Qué clasificación Vallée o tipo de evento tienen? | No (Silver) | Sí | `bars` |
| 74 | ¿Qué etiquetas de comportamiento aparecen (flota, cambia de color…)? | No (Silver) | Sí | `bars` |
| 75 | ¿Qué dice el texto original del testigo? | No (Silver) | No | Bronze y Silver no conservan el relato: solo el indicador has_description y las puntuaciones derivadas. |
| 76 | ¿Cuántos objetos se vieron en cada informe? | No (Silver) | No | Solo Bronze tiene num_objects; Silver no lo conserva, así que Gold no puede publicarlo sin cambiar Silver. |

### Proximidad

10 de 10 con gráfico; 5 nuevas o completadas en esta versión.

| # | Pregunta | Antes | Ahora | Vista o motivo |
| ---: | --- | --- | --- | --- |
| 77 | ¿Cuántos informes hay a menos de 10, 25, 50… km de una instalación? | Sí | Sí | `bars` |
| 78 | ¿Qué instalaciones quedan como las más cercanas a más informes? | Sí | Sí | `bars` |
| 79 | ¿Cuántos informes hay cerca de Hanford? | Sí | Sí | `bars` |
| 80 | ¿Qué distancia media a la instalación más cercana tiene cada país? | Sí | Sí | `bars` |
| 81 | ¿Cambia la distancia por década? | Sí | Sí | `stacked` |
| 82 | ¿Qué porcentaje de cada país está a menos de 10 km? (coropleta de %) | No | Sí | `choropleth` |
| 83 | ¿Cómo se distribuye la distancia exacta (curva acumulada en km)? | No | Sí | `ecdf` · medida `nuclear_distance` |
| 84 | ¿Qué celdas conectan con qué instalación? (mapa de enlaces) | No | Sí | `links` · análisis `facility_links` |
| 85 | ¿Qué encuentros nucleares (misiles afectados, sistema de armas) hay? | No (Silver) | Sí | `points` · 35 informes, todos |
| 86 | ¿Qué instalaciones del catálogo excluido existen? | No (Silver) | Sí | `bars` |

### Duplicados y eventos

7 de 8 con gráfico; 2 nuevas o completadas en esta versión; 1 sin el dato.

| # | Pregunta | Antes | Ahora | Vista o motivo |
| ---: | --- | --- | --- | --- |
| 87 | ¿Cuántos eventos confirmados hay? | Sí | Sí (cifras) | `table` |
| 88 | ¿Qué tamaño tienen los grupos confirmados? | Sí | Sí | `bars` |
| 89 | ¿Cuántos informes hay por estado de duplicado? | Sí | Sí | `bars` |
| 90 | ¿Qué fuentes tienen más coincidencias por revisar? | Sí | Sí | `bars` |
| 91 | ¿Cómo evolucionan por año los eventos confirmados? | Sí | Sí | `timeseries` |
| 92 | ¿Cuántos ovnis reales / eventos únicos hubo? | No | No | No existe por diseño: el archivo cuenta informes y eventos confirmados; el agente lo explica sin gráfico. |
| 93 | ¿Cuántas coincidencias por revisar tiene cada informe marcado? | No | Sí | `bars` |
| 94 | ¿Qué similitud y método tiene cada par candidato? | No (Silver) | Sí | `bars` |

### Calidad y cobertura

15 de 15 con gráfico; 7 nuevas o completadas en esta versión.

| # | Pregunta | Antes | Ahora | Vista o motivo |
| ---: | --- | --- | --- | --- |
| 95 | ¿Cuántos informes quedan fuera de cada análisis (mapa, país, hora…)? | Sí | Sí | `stacked` |
| 96 | ¿Por qué motivos quedan fuera del mapa? | Sí | Sí | `bars` |
| 97 | ¿Qué precisión de fecha tiene cada fuente? | Sí | Sí | `stacked` |
| 98 | ¿Cuál es el estado y la certeza de las fechas? | Sí | Sí | `matrix` |
| 99 | ¿Qué precisión de reloj tiene cada fuente? | Sí | Sí | `stacked` |
| 100 | ¿Qué fuentes tienen marcadores de día? | Sí | Sí | `stacked` |
| 101 | ¿De dónde vienen las coordenadas (Bronze o catálogo externo)? | Sí | Sí | `stacked` |
| 102 | ¿Qué estado tienen los países (válido, contradictorio…)? | Sí | Sí | `bars` |
| 103 | ¿Qué porcentaje de cada fuente tiene país, día y coordenadas a la vez? | No | Sí | `bars` |
| 104 | ¿Qué combinaciones de datos faltantes se repiten? (UpSet) | No | Sí | `upset` · análisis `missing_combinations` |
| 105 | ¿Cómo cambió el % con coordenadas utilizables por año? | No | Sí | `timeseries` |
| 106 | ¿Dónde se pierde cobertura de año a mes, día y hora? (embudo) | No | Sí | `funnel` · análisis `funnel` |
| 107 | ¿Qué reglas de calidad dispararon más incidencias? | No (Silver) | Sí | `bars` |
| 108 | ¿Qué cambió Silver respecto a Bronze en cada informe? | No (Silver) | Sí | `bars` |
| 109 | ¿Qué texto original de fecha u hora tenía el informe? | No (Silver) | Sí | `compare` · análisis `compare_reports` |

### Salidas de modelo

14 de 14 con gráfico; 7 nuevas o completadas en esta versión.

| # | Pregunta | Antes | Ahora | Vista o motivo |
| ---: | --- | --- | --- | --- |
| 110 | ¿Qué probabilidad media de engaño asigna el modelo por fuente? | Sí | Sí | `bars` |
| 111 | ¿Qué calidad documental media tiene cada forma? | Sí | Sí | `bars` |
| 112 | ¿Cómo evoluciona el sentimiento VADER por año? | Sí | Sí | `timeseries` |
| 113 | ¿Qué sentimiento RoBERTa tiene cada país? | Sí | Sí | `choropleth` |
| 114 | ¿Qué emoción dominante predomina (7 clases)? | Sí | Sí | `bars` |
| 115 | ¿Qué tono (positivo/negativo) tienen los relatos? | Sí | Sí | `bars` |
| 116 | ¿Qué emoción domina en cada fuente? | Sí | Sí | `stacked` |
| 117 | ¿Qué emoción fina (28 clases) domina? | No | Sí | `bars` |
| 118 | ¿Qué riqueza media tiene cada fuente? | No | Sí | `bars` |
| 119 | ¿Cómo se reparte la puntuación de sentimiento? (histograma) | No | Sí | `histogram` · medida `sentiment` |
| 120 | ¿Cuánto difieren VADER y RoBERTa? (dispersión) | No | Sí | `scatter` · medida `vader_roberta` |
| 121 | ¿Qué puntuaciones NRC (miedo, alegría…) tiene el relato? | No (Silver) | Sí | `bars` |
| 122 | ¿Qué banderas de engaño activó el modelo? | No (Silver) | Sí | `bars` |
| 123 | ¿Qué perfiles de duración y testigos aparecen con K-means? | No | Sí | `scatter` · análisis `kmeans_profiles` |

### Casos y registros especiales

3 de 3 con gráfico; 3 nuevas o completadas en esta versión.

| # | Pregunta | Antes | Ahora | Vista o motivo |
| ---: | --- | --- | --- | --- |
| 124 | ¿En qué se parecen los informes #8137 y #8138? | No | Sí | `compare` · análisis `compare_reports` |
| 125 | ¿Qué casos de recuperación de naves (crash retrieval) hay? | No (Silver) | Sí | `points` · 14 informes, todos |
| 126 | ¿Qué informes hay en Roswell (Nuevo México) en julio de 1947? | Parcial | Sí | `timeline` |
