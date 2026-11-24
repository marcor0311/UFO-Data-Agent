# Contrato Gold de UFO-Data-Agent

Gold es la capa analítica y semántica del **data agent propio** del proyecto. Se
construye solo por lectura sobre Silver v6 y no está pensada para integrarse con
herramientas de BI de terceros. El agente nunca escribe SQL: consulta Gold con
herramientas tipadas y consultas certificadas.

- Política: [`config/gold/gold.json`](../config/gold/gold.json), versión `gold_version=1`.
- Catálogos: [`dataset_catalog.json`](../config/gold/dataset_catalog.json),
  [`metric_catalog.json`](../config/gold/metric_catalog.json) y
  [`dimension_catalog.json`](../config/gold/dimension_catalog.json).
- Catálogo generado con perfiles reales: [GOLD_CATALOG.md](GOLD_CATALOG.md).
- Guía para el agente: [gold-domain-guide.md](gold-domain-guide.md).
- Verificación: [gold-verification.md](gold-verification.md).

## Entradas fijadas y construcción

| Requisito | Implementación |
|---|---|
| Cadena de custodia | Bronze se fija por tamaño y SHA-256 en `config/bronze.json`. Silver se reconstruye en cada equipo, así que su SHA no se fija: identifica el archivo exacto que aprobó su informe. `gold_common.silver_provenance()` exige un informe válido (`layer="silver"`, `passed` exactamente `true`, SHA y tamaño del archivo) y un linaje completo hacia la Bronze y la receta vigentes. Rechaza un informe ausente, vacío o mal formado y los snapshots con WAL pendiente. |
| Silver aprobado para el snapshot exacto | El build ejecuta `check_silver_ready.readiness()` sobre la Silver aprobada en el catálogo y exige `ready_for_gold=true` con los mismos SHA. Dentro de una misma ejecución, la aceptación completa corre una sola vez por Silver exacta. El resultado se guarda en `silver.readiness.json` de la versión Gold, y Silver no se escribe. |
| Solo lectura | Silver y Bronze se abren con `mode=ro&immutable=1`. El build vuelve a calcular ambos SHA al final y aborta si cambiaron durante la lectura. |
| Manifiesto | `ufo_gold.manifest.json` de la versión: `gold_version`, `load_id`, `built_at`, SHA de Silver, Bronze y Gold, `run_id` y fecha de referencia de Silver, hash de definiciones (código y catálogos) y filas por tabla. |
| `load_id` determinista | SHA-256 de `gold_version` + SHA de Silver + SHA de Bronze + hash de definiciones. Con las mismas entradas y definiciones se obtiene la misma carga. |
| Publicación por versión | Gold, la caché, sus manifiestos, las certificaciones, las referencias y las evaluaciones se construyen en un candidato nuevo (`data/gold/versions/<versión>/`). Nunca se reemplaza una base publicada. La verificación independiente y `ready_for_agent` se ejecutan sobre ese candidato exacto, y después se promueve con una sola transacción en `data/releases.sqlite3` (`scripts/releases.py`). Si algo falla o el proceso se interrumpe, sigue vigente la carga aprobada anterior. |

El hash de definiciones incluye `scripts/gold_common.py`, `scripts/build_gold.py`,
la política, los tres catálogos, los nombres de países en español y
`config/countries.json`, con los finales de línea normalizados a LF. Así, un
checkout de Windows con CRLF da la misma huella. Excluye las consultas certificadas, las correcciones y
el set de evaluación: registrar una verificación no cambia la carga verificada.

## Grano y vocabulario

- La unidad base es el **informe**: `fact_report` tiene una fila por ID de
  `sighting` de Bronze. Son **702.572** filas, conciliadas exactamente con Silver
  y Bronze, en total, por fuente e ID a ID.
- Los **eventos** existen solo para grupos de duplicados **confirmados**:
  `fact_event` tiene **6.959** eventos y `event_report` enlaza sus **17.920**
  informes.
- Un conteo de informes nunca se llama “avistamientos” ni “eventos”.

## Modelo

| Tabla | Grano | Notas |
|---|---|---|
| `fact_report` | Informe | Claves a dimensiones, banderas de elegibilidad, motivo de exclusión por análisis, estado de duplicado y bases de evidencia. |
| `report_model_output` | Informe | Sentimiento, emociones, `hoax_likelihood`, `quality_score`, `richness_score`. Salidas de modelos, separadas de los hechos. |
| `fact_event` / `event_report` | Evento confirmado / informe miembro | Tamaño, fuentes, fecha, país y forma del representante. |
| `dim_source`, `dim_origin`, `dim_collection` | — | 4 fuentes con informes, 13 orígenes, 3 colecciones, con etiquetas en español. |
| `dim_date` | Fecha a su precisión segura | 30.711 claves `AAAA`, `AAAA-MM` o `AAAA-MM-DD`, con precisión explícita, día de la semana y etiquetas. |
| `dim_country` | País | 249 códigos ISO2 con alfa-3, M49, nombre en inglés (catálogo UN M49) y en español. |
| `dim_shape`, `dim_color`, `dim_duration_bucket`, `dim_movement` | — | 28 formas, 21 colores en 16 familias, 5 tramos de duración y 6 tipos de movimiento, en español. |
| `dim_nuclear_facility`, `dim_distance_band` | — | 47 instalaciones del catálogo de Silver, agrupadas por nombre, y 8 bandas de distancia. |
| `dim_weekday`, `dim_month`, `dim_duplicate_status`, `dim_exclusion_reason`, `dim_eligibility` | — | Vocabularios cerrados. |
| `agg_year`, `agg_month`, `agg_weekday_hour`, `agg_country`, `agg_shape`, `agg_source`, `agg_spatial_cell`, `agg_nuclear_band` | Ver catálogo | Precalculados desde `fact_report` con su filtro de elegibilidad. |
| `agg_coverage` | Agregado × estado × motivo × fuente | Informes incluidos y excluidos de cada agregado, con su motivo. |
| `report_behavior_tag`, `report_hoax_flag` | Informe × etiqueta | Etiquetas de comportamiento y señales heurísticas de posible engaño de `sighting_analysis`; `report_count` cuenta informes distintos. |
| `candidate_pair` | Par candidato | Pares por revisar de Silver con método, similitud (y su banda), par de fuentes y decisión. |
| `quality_issue_summary`, `silver_change_summary` | Tabla × columna × regla (× fuente) | Registro de incidencias de calidad y de cambios de Silver sobre Bronze, resumido. |
| `fact_crash_retrieval`, `fact_nuclear_encounter` | Caso | Registros especiales de relatos compilados (14 y 35 casos), con fecha, país y coordenadas aptas cuando son válidas. |
| `facility_catalog` | Fila del catálogo | Las 75 filas físicas de instalaciones de Silver; `admitted=1` marca las que entran en la proximidad. |

`fact_report` publica además códigos cerrados derivados de los descriptores de
Silver ([scripts/gold_descriptors.py](../scripts/gold_descriptors.py)): estado o
provincia (`region_code`, solo EE. UU., Canadá y Australia, y solo si el país es
el canónico), ciudad (`city_name`, texto de la fuente), sonido, dirección,
tiempo, entorno, Vallée y código de evento; la fecha y la hora originales en
texto; bandas de testigos y de coincidencias por revisar; y banderas 0/1 que son
el numerador de los porcentajes condicionados (`has_core_fields`,
`map_without_country`, `within_10km`…). `report_model_output` añade las ocho
puntuaciones NRC y las siete probabilidades del modelo de emociones.

Lo nulo sigue nulo: no se imputan fechas, coordenadas, países ni formas. Gold
publica un valor temporal o geográfico **solo si el informe es elegible** para
ese análisis; si no, la columna queda nula y `*_exclusion` dice por qué.

Un valor desconocido en un vocabulario cerrado (forma, color, fuente, origen…)
detiene el build: no se reetiqueta en silencio.

## Duplicados no resueltos

No se fusiona ni se borra ningún informe. Los **243.318** pares candidatos
pendientes (`needs_review`) afectan a **311.628** informes
(`has_pending_candidate=1`). El estado `duplicate_status` toma, en este orden:
`confirmed_canonical`, `confirmed_member`, `pending_candidate` y `unique`. Hay
9.041 informes de grupos confirmados que además tienen un par pendiente:
conservan su estado confirmado y `has_pending_candidate=1`.

Cada informe es una unidad de conteo. Un par pendiente no prueba que dos
informes sean el mismo relato, así que **`report_count` es la única cifra de
informes** (702.572 en total) y no se publica un rango. Solo los grupos
confirmados (`fact_event`) se tratan como duplicados.

`has_pending_candidate` queda como marca de calidad del registro, al estilo de
una expectativa de tipo *warn* en Databricks: no excluye informes. Las métricas
`pending_candidate_reports` y `report_count_excl_candidates` (390.944) siguen
disponibles si se piden de forma explícita, pero el motor no las añade a las
consultas y la interfaz no las presenta como un segundo conteo.

## Elegibilidad por análisis

La elegibilidad se impone en el código. En `fact_report` el agente debe
declararla (`eligibility`) cuando usa una columna que la requiere; los agregados
la aplican por construcción. Hay implicaciones: día ⇒ mes ⇒ calendario,
hora ⇒ calendario y proximidad ⇒ mapa. La puerta comprueba que se cumplen en
los datos.

| Código | Bandera | Regla | Elegibles | Fuera |
|---|---|---|---:|---:|
| `calendar` | `usable_for_calendar` | Silver `usable_for_calendar=1` | 695.034 | 7.538 |
| `month` | `usable_for_month_analysis` | Silver `usable_for_month_analysis=1` | 677.377 | 25.195 |
| `day` | `usable_for_day_analysis` | Silver `usable_for_day_analysis=1` | 592.979 | 109.593 |
| `hour` | `usable_for_hour_analysis` | Calendario apto y reloj de minuto, segundo o fracción | 233.854 | 468.718 |
| `day` + `hour` | ambas | Matriz día de la semana × hora | 213.104 | 489.468 |
| `map` | `usable_for_map` | Silver `usable_for_map=1` | 495.019 | 207.553 |
| `country` | `usable_for_country` | Silver `usable_for_country=1` | 626.833 | 75.739 |
| `nuclear_proximity` | `usable_for_nuclear_proximity` | Silver `usable_for_nuclear_proximity=1` | 495.019 | 207.553 |

La hora exige además calendario apto, porque Silver conserva la precisión de
reloj de 61 informes de Capella con fecha calificada (“approximately 1300
hours”, “Summer 67”). Esa hora no se usa. Los motivos de exclusión
(`dim_exclusion_reason`, 24 códigos) son excluyentes por análisis. Sumar los
excluidos de análisis distintos cuenta el mismo informe varias veces.

## Evidencia externa y puntuaciones de modelo

- `uses_external_evidence` (20.751 informes de UFO-search) se conserva por
  informe, y cada agregado lleva `external_evidence_reports`. Cuando una
  consulta incluye informes con evidencia externa, el resultado lo declara con
  su conteo. `coordinate_basis`, `country_basis`, `time_basis` y `clock_basis`
  permiten separar la procedencia, y `uses_external_evidence=0` da un análisis
  solo con Bronze.
- Sentimiento, emociones, `hoax_likelihood` y `quality_score` están en
  `report_model_output`. Sus métricas llevan `model_output: true`, y el
  resultado añade la limitación `model_scores`. Nunca se presentan como
  hechos.

## Capa semántica

### Métricas

`metric_catalog.json` define 21 métricas (10 aditivas, 3 ratios y 8 no aditivas) con código, etiqueta en español,
definición, unidad, tipo y datasets:

- **Aditivas:** conteos de informes y de eventos.
- **Ratios:** `external_evidence_pct`, `pending_candidate_pct` y `media_pct`.
  Declaran numerador, denominador y factor, y se recalculan en cada grupo.
- **No aditivas:** países distintos, primer y último año, distancia media y
  medias de modelo. Se calculan sobre las filas de origen de cada grupo.

Las expresiones son operaciones cerradas (`count`, `sum`, `count_distinct`,
`avg`, `min`, `max`) sobre columnas validadas; el catálogo no contiene SQL.

### Dimensiones

`dimension_catalog.json` define 69 dimensiones con estos campos:

- valores permitidos (enumeración, tabla de dimensión o rango);
- elegibilidad mínima (`requires`) y precisión mínima;
- datasets que la contienen y métricas compatibles.

La puerta comprueba que el catálogo coincide con el esquema en ambos sentidos.

### Contrato de consulta (`scripts/gold_query.py`)

```json
{"dataset": "fact_report", "filters": [{"column": "country_iso2", "op": "eq", "value": "AR"}],
 "group_by": ["event_year"], "metrics": ["report_count"], "eligibility": ["calendar", "country"],
 "view": "timeseries", "order_by": null, "descending": true, "limit": 100, "rollup": false, "title": "…"}
```

- Campos desconocidos → rechazo (equivalente a `extra='forbid'`). No hay campo para SQL.
- Operadores: `eq`, `ne`, `in` (1–100 valores), `gte`, `lte` e `is_null`.
- Límites: 12 filtros, 4 dimensiones, 8 métricas y `limit` ≤ 500 (`density` admite hasta 20.000 celdas).
- `measure` (opcional, solo `histogram`, `ecdf` y `scatter`): la medida que se agrupa en tramos. Solo entra en el hash de la consulta cuando existe.
- Métricas de cuantil (`op: quantile`): SQLite no tiene percentiles, así que el motor las calcula después de la consulta agrupada, por rango más cercano sobre los valores no nulos de cada grupo.
- Valores escalares finitos; los booleanos no valen como enteros.
- `area` (opcional): polígono de 3 a 400 vértices `[lng, lat]` dibujado en un mapa de la web. Limita la consulta a los informes dentro de la forma; exige coordenadas (`fact_report`, eligibility `map`) y no admite `globe`. El agente no lo envía: mientras hay un área activa, la API lo añade a cada `query_gold` y rechaza `run_certified` (`area_active`). Solo entra en el hash de la consulta cuando existe.
- Identificadores validados contra el catálogo; valores validados contra los
  permitidos y ligados como parámetros.
- Presupuesto de instrucciones SQLite: 400 millones de pasos de la VM,
  comprobados cada 10.000; si se excede, `budget`.

Combinaciones prohibidas, con su código de error:

| Caso | Código |
|---|---|
| Agrupar o filtrar por día, mes, año, hora, país, mapa o proximidad sin declarar la elegibilidad | `eligibility_missing` |
| `is_null` sobre una columna sujeta a elegibilidad sin declararla (usar `*_exclusion`) | `gated_null_filter` |
| Pedir con `query_gold` una vista de análisis (`waterfall`, `bump`, `curve`, `clusters`, `links`, `funnel`, `upset`, `compare`) | `view_contract` |
| Sumar o promediar un porcentaje (`sum_*_pct`, `avg_*_pct`) | `ratio_not_summable` |
| Sumar todas las resoluciones de celdas o todos los agregados de cobertura | `partition_required` |
| Métrica fuera de su dataset (p. ej., `event_count` sobre informes) | `metric_unavailable` |
| Métrica inexistente (p. ej., “ovnis reales”) | `metric_unknown` |
| Vista incompatible con el dataset o con la agrupación | `view_incompatible`, `view_contract` |
| Elegibilidad no disponible en un agregado | `eligibility_unavailable` |

### Vistas (`VIEWS`)

| Vista | Datasets | Contrato |
|---|---|---|
| `table` | todos | Tarjetas para un total y tabla para listados o grupos. |
| `bars` | informes, eventos, modelo y agregados no espaciales | Métricas y una o dos dimensiones. |
| `timeseries` | `fact_report`, `report_model_output`, `fact_event`, `agg_year`, `agg_month` | La primera dimensión es temporal (`event_year`, `decade`, `year_month` o `event_date`). |
| `points` | `fact_report`, `fact_crash_retrieval`, `fact_nuclear_encounter` | Filas sin métricas; exige `map`. Sin `limit`: un punto por informe hasta 20.000 y, por encima, uno por coordenada idéntica con su número de informes (`points.grouped`). |
| `density` | `agg_spatial_cell`, `fact_report` | Agrupa por celda de 1° o 5°. |
| `globe` | `fact_report` | Informes sobre un globo: solo `report_count`, sin `group_by` y con `map`; admite filtros. El servidor agrupa por coordenadas idénticas y devuelve todas las ubicaciones, sin el `limit`. |
| `choropleth` | `agg_country`, `fact_report`, `report_model_output` | Agrupa solo por `country_iso2`. |
| `hour_weekday` | `agg_weekday_hour`, `fact_report` | Agrupa exactamente por `weekday` y `event_hour`. |
| `stacked` | Los mismos que `bars` | Una métrica y exactamente dos dimensiones; 100 % por valor de la primera. |
| `matrix` | Los mismos que `bars` | Una métrica y exactamente dos dimensiones (filas, columnas). |
| `dumbbell` | `fact_report`, `agg_year`, `agg_shape` | Agrupa por `[decade` o `event_year`, categoría`]` y filtra el período con `in` y exactamente dos valores. |
| `timeline` | `fact_report` | Listado sin métricas con eligibility `day`, ordenado por `event_date`. |
| `histogram`, `ecdf` | `fact_report`, `report_model_output` | Solo `report_count` y como mucho un `group_by` (un panel por valor). `measure` elige la medida: `duration` (por defecto, tramos de un minuto hasta 60), `duration_tail`, `witnesses`, `nuclear_distance`, `sentiment`, `vader`, `roberta`, `richness`, `quality`, `hoax`; `ecdf` solo `duration` y `nuclear_distance`. La cola y los informes sin valor se cuentan aparte. |
| `boxplot` | `fact_report`, `report_model_output` | Una métrica de cuantil y como mucho un `group_by`; cada fila lleva los percentiles 5, 25, 50, 75 y 95. |
| `scatter` | `fact_report`, `report_model_output` | Solo `report_count`, sin `group_by`, con `measure` `duration_witnesses` o `vader_roberta`: conteos por celda de las dos medidas. |
| `stacked` (cola) | — | Si la segunda dimensión tiene más de 12 valores, la cola se reúne en “Otras” conservando los totales. |
| Vistas de análisis | — | `waterfall`, `bump`, `curve`, `clusters`, `links`, `funnel`, `upset` y `compare` solo las produce [scripts/gold_analysis.py](../scripts/gold_analysis.py) (herramienta `analyze`). |
| `month_calendar` | `agg_month`, `fact_report` | Agrupa exactamente por `event_year` y `event_month`. Exige filtrar `event_year` a un rango de hasta 40 años y un `limit` de al menos 12 × años. |

### Análisis (`scripts/gold_analysis.py`)

Cálculos de varias etapas que una consulta agrupada no expresa. Cada análisis
tiene parámetros tipados (rechazo de campos desconocidos, rangos y
dimensiones validadas), valida sus filtros con el mismo contrato que
`query_gold`, declara la elegibilidad de las columnas que usa y respeta el área
seleccionada. Devuelve el mismo sobre de resultado, con `query.analysis`,
`query.params`, `metric_labels` y `analysis` (totales, perfiles, fechas
destacadas…). Análisis disponibles: `period_change`, `dominant_share`,
`daily_anomalies`, `yoy_change`, `daily_distribution_by_month`,
`hour_month_deviation`, `rank_over_time`, `concentration`, `cell_change`,
`first_appearance`, `clusters`, `facility_links`, `funnel`,
`missing_combinations`, `compare_reports`, `kmeans_profiles`, `retention`,
`source_overlap`, `diversity` y `obs_expected`.

### Resultado

Cada resultado incluye:

- `rows` (con etiquetas `*_label` en español), `truncated`, `row_count`,
  `matched_source_rows`, `empty` y `total` si se pidió `rollup`;
- `result_type` (`certified` o `composed`) y `certified_query_id`;
- `readable_query`: filtros, agrupación, métricas, elegibilidad, orden y
  límite, en español, para la opción “ver la consulta”;
- `eligibility_applied`, con las implicadas, y `exclusions`: base, elegibles,
  excluidos y motivo;
- `external_evidence_reports`;
- `provenance`: `gold_load_id` y los SHA-256 de Gold, Silver y Bronze, de las
  definiciones, del motor, de la caché y de la consulta;
- `snapshot`: fecha de construcción y fecha de referencia de Silver;
- `limitations`: las que aplican a la consulta, por código.

### Consultas certificadas

`config/gold/certified_queries.json` contiene 17 consultas para las preguntas
frecuentes. Cada una lleva:

- título, descripción y 2–3 ejemplos en español;
- la consulta en el contrato tipado y las vistas recomendadas;
- la limitación que se debe mencionar;
- `query_sha256` y el resultado esperado (filas y `rows_sha256`);
- la verificación (`load_id`, fecha y hash del motor).

Una consulta es certificada solo si su hash actual coincide y su `load_id` es
el de la carga activa. Si cambia la consulta o la carga, pierde la
certificación hasta repetir el build de Gold, que certifica y verifica desde
Silver una copia dentro de la versión. `config/gold/certified_queries.json`
contiene las definiciones y solo cambia con `build_all.py --actualizar-referencias`
o con `gold_query.py certify`. El agente usa
`search_certified` (léxico con pesos IDF) antes de componer.

### Caché de servicio (`scripts/discover_gold.py`)

`discover_gold.py` hace lo siguiente:

1. Verifica el SHA de Gold y que las definiciones no hayan cambiado.
2. Copia Gold a `serving/ufo_gold_serving.db` de la misma versión y añade
   índices. Si ya existe una caché, no la reemplaza.
3. Embebe en una tabla `metadata` los catálogos, perfiles, etiquetas, valores
   permitidos y entidades.
4. Deja el archivo en modo `0444`.
5. Escribe un manifiesto con `cache_version`, SHA-256, `load_id` y SHA de Gold.

El consumidor (`Analytics`) rechaza la caché si la versión, el SHA o la carga no
coinciden, y la abre con `mode=ro&immutable=1` y `query_only`.

## Puerta de aceptación (`scripts/check_gold_ready.py`)

`ready_for_agent=true` solo si pasan todos los controles:

- **Manifiesto y entradas:** SHA de Gold, cadena de custodia de Silver, SHA de
  Silver y Bronze iguales al manifiesto, definiciones vigentes, `load_id`
  recalculado y la aceptación de Silver sobre el snapshot exacto, compartida con
  el resto de la ejecución.
- **Conciliación con Silver y Bronze:** total, conjunto de IDs, conteo por
  fuente, y banderas, bases y valores informe a informe.
- **Agregados:** cada uno, grupo a grupo y en ambos sentidos, coincide con
  `fact_report` bajo su elegibilidad; incluidos + excluidos = total, e
  incluidos = agregado.
- **Elegibilidad:** ningún valor de día, mes, mapa u otro análisis aparece en
  un informe no elegible, ni falta en uno elegible; implicaciones y regla
  horaria verificadas.
- **Cotas de duplicados:** inferior ≤ superior, la diferencia igual a los
  candidatos pendientes de cada fila, y el total de pendientes igual al de
  Silver.
- **Catálogos ⇔ esquema** en ambos sentidos, incluidas las métricas
  compatibles.
- **Integridad:** referencial (`foreign_key_check` y etiquetas) y claves
  únicas.
- **Consultas certificadas:** válidas, sin cambios y que reproducen su hash.
- **Verificación independiente** y **set de evaluación** aprobados para la
  carga actual.
- Silver y Bronze sin cambios al terminar.

## Límites

- Un informe no es un hecho verificado. Que un valor coincida con Bronze o con
  el catálogo de origen no prueba que sea verdadero.
- Los 243.318 pares pendientes siguen sin resolver: el número de eventos reales
  es desconocido y solo se publica un rango de informes.
- La cobertura depende de cada fuente y época. Predomina Estados Unidos (72 %
  de los informes con país) y NUFORC aparece en UFOCAT y en UPDB.
- Los marcadores de día reducen la precisión de 68.588 informes; su año se
  conserva.
- La evidencia externa (20.751 informes) no puede confirmarse con Bronze.
- Las puntuaciones de modelo no son hechos ni verificaciones.
- La proximidad se mide respecto del catálogo local de 47 instalaciones;
  cercanía no implica relación.
- La hora es local y sin zona horaria; muchas horas están redondeadas a la hora
  en punto.
- Gold no publica estados, ciudades ni regiones.
