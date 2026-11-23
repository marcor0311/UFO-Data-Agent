# Catálogo Gold (autogenerado)

Generado por `scripts/discover_gold.py`; no editar a mano.

- Carga Gold (`load_id`): `cb34d85bf862a18b55466abb2b22fc6b96a9219a3d018a6e7ab372063e665cb4`
- SHA-256 de Gold: `4fa5cb9488638807e1fe0ba085bafa9ffe1e897982fdc8016d39623ec28ec03a`
- SHA-256 de Silver: `72ada3670f79568025bc4f1c0184e4ae3b3c0236ece6f9f4a2483544a92aa25e`
- SHA-256 de Bronze: `0200337eb1eadabd337ac4f479fceceb5a810eec8ab072cd7a206523703820e0`
- Hash de definiciones: `04657006a72b938cc9bfd231663a737a8477d309edcbd62b5ec54ab23c90de43`
- Construida: 2026-11-23T02:55:25+00:00

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
| `fact_event` | 6.959 | 13 | Un grupo de duplicados confirmado por coincidencia exacta; no incluye informes únicos ni candidatos pendientes. |
| `fact_report` | 702.572 | 70 | Un informe: una fila por ID de sighting de Bronze. |
| `report_model_output` | 702.572 | 16 | Un informe; columnas producidas por clasificadores del origen, no hechos. |

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
| `report_count` | Informes (cota superior) | additive | upper | agg_country, agg_coverage, agg_month, agg_nuclear_band, agg_shape, agg_source, agg_spatial_cell, agg_weekday_hour, agg_year, fact_report, report_model_output |
| `report_count_excl_candidates` | Informes sin candidatos pendientes (cota inferior) | additive | lower | agg_country, agg_coverage, agg_month, agg_nuclear_band, agg_shape, agg_source, agg_spatial_cell, agg_weekday_hour, agg_year, fact_report |
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

## Relaciones

- fact_report.report_id es el ID de sighting en Bronze y Silver (una fila por informe).
- report_model_output.report_id = fact_report.report_id (1:1).
- fact_event.canonical_event_id = fact_report.report_id del representante; event_report enlaza cada miembro con su evento.
- fact_report.source_code → dim_source; origin_code → dim_origin; collection_code → dim_collection.
- fact_report.date_key → dim_date (fecha a su precisión segura: AAAA, AAAA-MM o AAAA-MM-DD).
- fact_report.country_iso2 → dim_country; shape_code → dim_shape; color_code → dim_color; duration_bucket → dim_duration_bucket; movement_type → dim_movement.
- fact_report.nearest_facility_key → dim_nuclear_facility; distance_band → dim_distance_band.
- agg_* se derivan de fact_report con el filtro de elegibilidad declarado en dataset_catalog.json; agg_coverage explica incluidos y excluidos de cada agregado.

## Limitaciones

- **reports_not_facts**: Cada fila es un informe registrado por una fuente, no un hecho verificado ni un avistamiento confirmado. Coincidir con Bronze no prueba que el relato sea verdadero.
- **pending_duplicates**: Hay pares candidatos de duplicado pendientes de evidencia: el número de informes se da como rango (report_count como cota superior y report_count_excl_candidates como cota inferior). Ninguno de los dos es un número de eventos.
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
