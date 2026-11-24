# Catálogo Gold (autogenerado)

Generado por `scripts/discover_gold.py`; no editar a mano.

- Carga Gold (`load_id`): `caca588120ee86fa0da4c802cf6613466444c07bd5b893af37e378b548422059`
- SHA-256 de Gold: `ad6e4612fb34bc5496a1b0f69dcf02351bcef421f1c0566d086bb4916aba83e3`
- SHA-256 de Silver: `c6a298ec7641c48c62d1c43b42dcac99d076f6556e8ef0a446d9327adc60a22f`
- SHA-256 de Bronze: `0200337eb1eadabd337ac4f479fceceb5a810eec8ab072cd7a206523703820e0`
- Hash de definiciones: `7fc0f72aea38ba39d729a0d776058205bef73943a5ec6ad481f6abf74d4d6bd4`
- Construida: 2026-11-24T19:02:24+00:00

## Tablas

| Tabla | Filas | Columnas | Grano |
|---|---:|---:|---|
| `agg_country` | 661 | 6 | País ISO2 × fuente. |
| `agg_coverage` | 129 | 9 | Agregado × estado × motivo × fuente. Cada agregado suma el total de informes: filtra o agrupa por aggregate_code. |
| `agg_month` | 6.529 | 8 | Año × mes × fuente. |
| `agg_nuclear_band` | 901 | 7 | Banda de distancia × instalación más cercana × fuente. |
| `agg_shape` | 58 | 6 | Forma estandarizada (incluida la ausencia de forma) × fuente. |
| `agg_source` | 26 | 7 | Fuente × colección × origen. |
| `agg_spatial_cell` | 13.739 | 8 | Resolución × celda × fuente. Cada resolución contiene todos los informes del mapa: filtra una sola resolución. |
| `agg_weekday_hour` | 450 | 7 | Día de la semana ISO × hora local declarada × fuente. |
| `agg_year` | 1.521 | 7 | Año × fuente. |
| `candidate_pair` | 243.318 | 11 | Un par de informes que Silver propuso como posible duplicado y dejó por revisar. |
| `dim_collection` | 3 | 4 | dimensión |
| `dim_color` | 21 | 4 | dimensión |
| `dim_country` | 249 | 6 | dimensión |
| `dim_date` | 30.711 | 9 | dimensión |
| `dim_distance_band` | 8 | 5 | dimensión |
| `dim_duplicate_status` | 4 | 2 | dimensión |
| `dim_duration_bucket` | 5 | 5 | dimensión |
| `dim_eligibility` | 7 | 4 | dimensión |
| `dim_exclusion_reason` | 24 | 2 | dimensión |
| `dim_month` | 12 | 2 | dimensión |
| `dim_movement` | 6 | 2 | dimensión |
| `dim_nuclear_facility` | 47 | 7 | dimensión |
| `dim_origin` | 13 | 4 | dimensión |
| `dim_shape` | 28 | 2 | dimensión |
| `dim_source` | 4 | 10 | dimensión |
| `dim_weekday` | 7 | 2 | dimensión |
| `event_report` | 17.920 | 4 | Un informe miembro de un grupo confirmado. |
| `facility_catalog` | 75 | 9 | Una fila física del catálogo de instalaciones; admitted=1 si entra en el cálculo de proximidad. |
| `fact_crash_retrieval` | 14 | 18 | Un caso del registro de supuestas recuperaciones de naves; relatos, no hechos. |
| `fact_event` | 6.959 | 13 | Un grupo de duplicados confirmado por coincidencia exacta; no incluye informes únicos ni candidatos pendientes. |
| `fact_nuclear_encounter` | 35 | 21 | Un caso del registro de encuentros con instalaciones nucleares; relatos, no hechos. |
| `fact_report` | 702.572 | 93 | Un informe: una fila por ID de sighting de Bronze. |
| `quality_issue_summary` | 66 | 7 | Tabla × columna × regla × acción × severidad × fuente. |
| `report_behavior_tag` | 542.608 | 9 | Un informe × una etiqueta de comportamiento detectada en su texto por el origen. |
| `report_hoax_flag` | 49.823 | 9 | Un informe × una señal heurística del origen (texto muy corto, frases genéricas…). |
| `report_model_output` | 702.572 | 31 | Un informe; columnas producidas por clasificadores del origen, no hechos. |
| `silver_change_summary` | 64 | 5 | Tabla × columna × regla × fuente. |

Tipos, nulos, rangos, valores categóricos y conteos por columna: [GOLD_CATALOG.json](GOLD_CATALOG.json).

## Informes por fuente

| Fuente | Informes | Sin candidatos pendientes | Con candidato pendiente | Con evidencia externa |
|---|---:|---:|---:|---:|
| Capella | 30.453 | 21.843 | 8.610 | 0 |
| UFO-search | 54.751 | 40.440 | 14.311 | 20.751 |
| UFOCAT | 320.412 | 168.810 | 151.602 | 0 |
| UPDB | 296.956 | 159.851 | 137.105 | 0 |

## Cobertura de cada agregado

| Agregado | Elegibilidad | Incluidos | Excluidos |
|---|---|---:|---:|
| `agg_country` | country | 626.833 | 75.739 |
| `agg_month` | month | 677.377 | 25.195 |
| `agg_nuclear_band` | nuclear_proximity | 495.019 | 207.553 |
| `agg_shape` | none | 702.572 | 0 |
| `agg_source` | none | 702.572 | 0 |
| `agg_spatial_cell` | map | 495.019 | 207.553 |
| `agg_weekday_hour` | day+hour | 213.104 | 489.468 |
| `agg_year` | calendar | 695.034 | 7.538 |

## Métricas

| Código | Etiqueta | Tipo | Cota de duplicados | Datasets |
|---|---|---|---|---|
| `report_count` | Informes | additive | — | agg_country, agg_coverage, agg_month, agg_nuclear_band, agg_shape, agg_source, agg_spatial_cell, agg_weekday_hour, agg_year, fact_report, report_behavior_tag, report_hoax_flag, report_model_output |
| `report_count_excl_candidates` | Informes sin coincidencias por revisar | additive | — | agg_country, agg_coverage, agg_month, agg_nuclear_band, agg_shape, agg_source, agg_spatial_cell, agg_weekday_hour, agg_year, fact_report |
| `pending_candidate_reports` | Informes con par candidato pendiente | additive | — | agg_country, agg_coverage, agg_month, agg_nuclear_band, agg_shape, agg_source, agg_spatial_cell, agg_weekday_hour, agg_year, fact_report |
| `external_evidence_reports` | Informes con evidencia externa | additive | — | agg_country, agg_coverage, agg_month, agg_nuclear_band, agg_shape, agg_source, agg_spatial_cell, agg_weekday_hour, agg_year, fact_report |
| `confirmed_group_reports` | Informes en grupos confirmados | additive | — | fact_report |
| `canonical_representative_reports` | Representantes canónicos | additive | — | fact_report |
| `media_reports` | Informes que mencionan medios | additive | — | fact_report |
| `event_count` | Eventos confirmados | additive | — | fact_event |
| `event_member_reports` | Informes miembros de eventos confirmados | additive | — | event_report, fact_event |
| `external_evidence_pct` | % de informes con evidencia externa | ratio | — | agg_country, agg_month, agg_nuclear_band, agg_shape, agg_source, agg_spatial_cell, agg_weekday_hour, agg_year, fact_report |
| `pending_candidate_pct` | % de informes con candidato pendiente | ratio | — | agg_country, agg_month, agg_nuclear_band, agg_shape, agg_source, agg_spatial_cell, agg_weekday_hour, agg_year, fact_report |
| `media_pct` | % de informes que mencionan medios | ratio | — | fact_report |
| `distinct_country_count` | Países distintos | non_additive | — | agg_country, fact_report |
| `first_year` | Primer año con informes | non_additive | — | agg_month, agg_year, fact_report |
| `last_year` | Último año con informes | non_additive | — | agg_month, agg_year, fact_report |
| `avg_nuclear_distance_km` | Distancia media a la instalación del catálogo más cercana | non_additive | — | fact_report |
| `scored_reports` | Informes con puntuación de riesgo de engaño | additive | — | report_model_output |
| `avg_hoax_likelihood` | Probabilidad media de engaño (modelo) | non_additive | — | report_model_output |
| `avg_quality_score` | Puntuación media de riqueza del origen | non_additive | — | report_model_output |
| `avg_vader_compound` | Sentimiento medio VADER (modelo) | non_additive | — | report_model_output |
| `avg_roberta_sentiment` | Sentimiento medio RoBERTa (modelo) | non_additive | — | report_model_output |
| `core_fields_reports` | Informes con país, día y coordenadas | additive | — | fact_report |
| `core_fields_pct` | % con país, día y coordenadas | ratio | — | fact_report |
| `map_usable_reports` | Informes con coordenadas aptas | additive | — | fact_report |
| `map_usable_pct` | % con coordenadas aptas | ratio | — | fact_report |
| `country_usable_reports` | Informes con país apto | additive | — | fact_report |
| `country_usable_pct` | % con país apto | ratio | — | fact_report |
| `day_usable_reports` | Informes con día fiable | additive | — | fact_report |
| `day_usable_pct` | % con día fiable | ratio | — | fact_report |
| `hour_usable_reports` | Informes con hora consignada fiable | additive | — | fact_report |
| `hour_usable_pct` | % con hora fiable | ratio | — | fact_report |
| `map_without_country_reports` | Informes con coordenadas pero sin país apto | additive | — | fact_report |
| `map_without_country_pct` | % con coordenadas pero sin país | ratio | — | fact_report |
| `placeholder_risk_reports` | Informes con marcador de día o mes | additive | — | fact_report |
| `placeholder_risk_pct` | % con marcador de día o mes | ratio | — | fact_report |
| `description_reports` | Informes con descripción | additive | — | fact_report |
| `description_pct` | % con descripción | ratio | — | fact_report |
| `description_and_media_reports` | Informes con descripción y medios | additive | — | fact_report |
| `description_and_media_pct` | % con descripción y medios | ratio | — | fact_report |
| `known_shape_reports` | Informes con forma conocida | additive | — | fact_report |
| `known_shape_pct` | % con forma conocida | ratio | — | fact_report |
| `positive_duration_reports` | Informes con duración positiva | additive | — | fact_report |
| `long_duration_reports` | Informes de más de una hora | additive | — | fact_report |
| `long_duration_pct` | % de más de una hora (entre duraciones positivas) | ratio | — | fact_report |
| `witnessed_reports` | Informes con testigos consignados | additive | — | fact_report |
| `witnessed_pct` | % con testigos consignados | ratio | — | fact_report |
| `proximity_reports` | Informes aptos para proximidad | additive | — | fact_report |
| `within_10km_reports` | Informes a menos de 10 km | additive | — | fact_report |
| `within_10km_pct` | % a menos de 10 km | ratio | — | fact_report |
| `within_50km_reports` | Informes a menos de 50 km | additive | — | fact_report |
| `within_50km_pct` | % a menos de 50 km | ratio | — | fact_report |
| `confirmed_group_pct` | % en grupos confirmados | ratio | — | fact_report |
| `reused_id_reports` | Informes con ID de origen repetido | additive | — | fact_report |
| `reused_id_pct` | % con ID de origen repetido | ratio | — | fact_report |
| `distinct_source_count` | Fuentes distintas | non_additive | — | fact_report |
| `median_duration_min` | Mediana de duración (min) | non_additive | — | fact_report |
| `p25_duration_min` | Percentil 25 de duración (min) | non_additive | — | fact_report |
| `p75_duration_min` | Percentil 75 de duración (min) | non_additive | — | fact_report |
| `median_witnesses` | Mediana de testigos | non_additive | — | fact_report |
| `median_nuclear_distance_km` | Mediana de distancia a la instalación más cercana | non_additive | — | fact_report |
| `avg_sentiment_score` | Sentimiento medio heredado (modelo) | non_additive | — | report_model_output |
| `median_sentiment_score` | Mediana de sentimiento heredado (modelo) | non_additive | — | report_model_output |
| `avg_richness_score` | Riqueza media del relato (heurística) | non_additive | — | report_model_output |
| `median_richness_score` | Mediana de riqueza del relato (heurística) | non_additive | — | report_model_output |
| `avg_nrc_joy` | NRC medio de alegría (léxico) | non_additive | — | report_model_output |
| `avg_nrc_fear` | NRC medio de miedo (léxico) | non_additive | — | report_model_output |
| `avg_nrc_anger` | NRC medio de ira (léxico) | non_additive | — | report_model_output |
| `avg_nrc_sadness` | NRC medio de tristeza (léxico) | non_additive | — | report_model_output |
| `avg_nrc_surprise` | NRC medio de sorpresa (léxico) | non_additive | — | report_model_output |
| `avg_nrc_disgust` | NRC medio de asco (léxico) | non_additive | — | report_model_output |
| `avg_nrc_trust` | NRC medio de confianza (léxico) | non_additive | — | report_model_output |
| `avg_nrc_anticipation` | NRC medio de anticipación (léxico) | non_additive | — | report_model_output |
| `avg_emotion_7_surprise` | Probabilidad media de sorpresa (modelo de 7 clases) | non_additive | — | report_model_output |
| `avg_emotion_7_fear` | Probabilidad media de miedo (modelo de 7 clases) | non_additive | — | report_model_output |
| `avg_emotion_7_neutral` | Probabilidad media de neutral (modelo de 7 clases) | non_additive | — | report_model_output |
| `avg_emotion_7_anger` | Probabilidad media de ira (modelo de 7 clases) | non_additive | — | report_model_output |
| `avg_emotion_7_disgust` | Probabilidad media de asco (modelo de 7 clases) | non_additive | — | report_model_output |
| `avg_emotion_7_sadness` | Probabilidad media de tristeza (modelo de 7 clases) | non_additive | — | report_model_output |
| `avg_emotion_7_joy` | Probabilidad media de alegría (modelo de 7 clases) | non_additive | — | report_model_output |
| `sentiment_scored_reports` | Informes con sentimiento puntuado | additive | — | report_model_output |
| `sentiment_scored_pct` | % con sentimiento puntuado | ratio | — | report_model_output |
| `vader_scored_reports` | Informes con VADER puntuado | additive | — | report_model_output |
| `vader_scored_pct` | % con VADER puntuado | ratio | — | report_model_output |
| `roberta_scored_reports` | Informes con RoBERTa puntuado | additive | — | report_model_output |
| `roberta_scored_pct` | % con RoBERTa puntuado | ratio | — | report_model_output |
| `emotion_scored_reports` | Informes con emoción de 7 clases puntuado | additive | — | report_model_output |
| `emotion_scored_pct` | % con emoción de 7 clases puntuado | ratio | — | report_model_output |
| `quality_scored_reports` | Informes con calidad documental puntuado | additive | — | report_model_output |
| `quality_scored_pct` | % con calidad documental puntuado | ratio | — | report_model_output |
| `richness_scored_reports` | Informes con riqueza puntuado | additive | — | report_model_output |
| `richness_scored_pct` | % con riqueza puntuado | ratio | — | report_model_output |
| `members_with_pending_reports` | Miembros con coincidencia por revisar | additive | — | fact_event |
| `members_with_pending_pct` | % de miembros con coincidencia por revisar | ratio | — | fact_event |
| `pair_count` | Pares candidatos | additive | — | candidate_pair |
| `avg_similarity` | Similitud media del par | non_additive | — | candidate_pair |
| `issue_count` | Incidencias de calidad | additive | — | quality_issue_summary |
| `change_count` | Cambios de Silver | additive | — | silver_change_summary |
| `case_count` | Casos del registro | additive | — | fact_crash_retrieval, fact_nuclear_encounter |
| `missiles_affected_total` | Misiles afectados (según el registro) | additive | — | fact_nuclear_encounter |
| `facility_count` | Instalaciones | additive | — | facility_catalog |

## Relaciones

- fact_report.report_id es el ID de sighting en Bronze y Silver (una fila por informe).
- report_model_output.report_id = fact_report.report_id (1:1).
- fact_event.canonical_event_id = fact_report.report_id del representante; event_report enlaza cada miembro con su evento.
- fact_report.source_code → dim_source; origin_code → dim_origin; collection_code → dim_collection.
- fact_report.date_key → dim_date (fecha a su precisión segura: AAAA, AAAA-MM o AAAA-MM-DD).
- fact_report.country_iso2 → dim_country; shape_code → dim_shape; color_code → dim_color; duration_bucket → dim_duration_bucket; movement_type → dim_movement.
- fact_report.nearest_facility_key → dim_nuclear_facility; distance_band → dim_distance_band.
- agg_* se derivan de fact_report con el filtro de elegibilidad declarado en dataset_catalog.json; agg_coverage explica incluidos y excluidos de cada agregado.
- report_behavior_tag y report_hoax_flag: una fila por informe y etiqueta (report_id → fact_report); report_count cuenta informes distintos.
- candidate_pair.report_id_a / report_id_b → fact_report: pares por revisar de Silver con método y similitud.
- quality_issue_summary y silver_change_summary resumen el registro de calidad y de cambios de Silver; source_code solo para filas de sighting.
- fact_crash_retrieval y fact_nuclear_encounter son registros especiales de casos compilados, sin relación por ID con fact_report.
- facility_catalog.nearest_facility_key → dim_nuclear_facility para las instalaciones admitidas (admitted=1).

## Limitaciones

- **reports_not_facts**: Cada fila es un informe registrado por una fuente, no un hecho verificado ni un avistamiento confirmado. Coincidir con Bronze no prueba que el relato sea verdadero.
- **pending_duplicates**: Algunos informes tienen coincidencias por revisar con otros. No están confirmados como duplicados: cada uno cuenta como un informe.
- **confirmed_events_only**: Los eventos existen solo para los grupos de duplicados confirmados por coincidencia exacta. Los informes únicos y los candidatos pendientes no son eventos.
- **eligibility_calendar**: Solo informes con fecha apta para calendario; quedan fuera fechas calificadas, intervalos, faltantes, inválidas y en revisión.
- **eligibility_month**: Solo informes con mes fiable; quedan fuera las fechas de solo año y las 01-01 de fuentes con exceso de ese marcador.
- **eligibility_day**: Solo informes con día fiable; quedan fuera los días 01 y 15 de las fuentes con exceso de marcadores, además de las fechas de mes o año.
- **eligibility_hour**: Solo informes con hora de minuto o mejor y fecha apta. Es hora local declarada sin zona horaria; muchas horas están redondeadas a la hora en punto.
- **eligibility_map**: Solo informes con coordenadas completas, en rango y fuera de cuarentena. Una coordenada puede ser el centro de una ciudad, no el lugar exacto del testigo.
- **eligibility_country**: Solo informes con país canónico consistente; los países contradictorios, históricos o no reconocidos quedan fuera.
- **eligibility_nuclear_proximity**: La distancia es a la instalación más cercana del catálogo local de Silver (bases, laboratorios y polígonos), no a todas las instalaciones del mundo. Cercanía no implica relación.
- **day_placeholders**: Algunas fuentes usan días marcadores (01, 15 o 01-01) cuando no conocen la fecha exacta; Silver reduce la precisión de esos informes en lugar de inventar o borrar fechas.
- **model_scores**: Sentimiento, emociones, hoax_likelihood y quality_score son salidas de modelos o heurísticas heredadas del origen, no hechos ni verificaciones. No se presentan como verdad.
- **source_bias**: La cobertura depende de cada fuente y época: predominan los informes de Estados Unidos y de los años con sistemas de reporte en línea; NUFORC aparece en UFOCAT y en UPDB.
- **external_evidence**: Parte de las coordenadas, países u horas procede del catálogo fijado de UFO-search y no de Bronze (uses_external_evidence=1).
