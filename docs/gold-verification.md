# Verificación de Gold

## Publicación por versión (24 de noviembre de 2026, UTC)

El pipeline se ejecutó completo con `scripts/build_all.py` en macOS (Python
3.14.7), sobre un directorio de datos temporal (`--datos`). Bronze se copió
desde un archivo local, sin Internet. Las cifras proceden de
`build.metrics.json`.

| Ejecución | Resultado |
|---|---|
| `build_all.py` (lanzado con Python 3.9, se relanzó solo con 3.14) | 405 s. Bronze 18 s, Silver 146 s, aceptación de Silver 47 s (una sola vez), modelo Gold 56 s, caché 25 s, verificación independiente 76 s, evaluaciones 4 s y `ready_for_agent` 22 s (543 controles). |
| `--desde gold` tras cambiar `scripts/build_silver.py` | Rechazada antes de leer Silver: “Silver está desactualizada (code_sha256, run_id)”. La carga aprobada no cambió. |
| `--desde silver` con el código final | 380 s. 22 lecturas completas de hash (2,40 GiB) y ningún archivo leído dos veces. Evaluaciones 60/60 con referencias de la carga y sin deriva. Quedan dos versiones por capa. |
| API sobre la carga aprobada | `/api/health` devuelve el mismo `load_id` en `gold_load_id`, `serving_load_id` y `readiness_load_id`, también mientras otro build publicaba. |

En las tres ejecuciones, `config/gold/certified_queries.json`, `docs/GOLD_EVALS.json`
y `docs/GOLD_CATALOG.*` quedaron sin cambios.

## Construcción del 23 de noviembre de 2026 (flujo anterior)

Resultado de la construcción y verificación completa del 23 de noviembre de 2026
(UTC), con los scripts por separado y las rutas fijas de entonces. Todas las
cifras proceden de la salida real de los scripts.

| Identificador | Valor |
|---|---|
| `load_id` | `cb34d85bf862a18b55466abb2b22fc6b96a9219a3d018a6e7ab372063e665cb4` |
| SHA-256 de Silver v6 | `72ada3670f79568025bc4f1c0184e4ae3b3c0236ece6f9f4a2483544a92aa25e` (sin cambios al terminar) |
| SHA-256 de Bronze | `0200337eb1eadabd337ac4f479fceceb5a810eec8ab072cd7a206523703820e0` (sin cambios al terminar) |
| SHA-256 de Gold | `4fa5cb9488638807e1fe0ba085bafa9ffe1e897982fdc8016d39623ec28ec03a`; las tres construcciones del día produjeron el mismo archivo byte a byte |
| SHA-256 de la caché de servicio | `222ab556822456d3d3d2825fce1da01539038fca6ed880646d658212700f4cec` (`cache_version=1`) |
| Hash de definiciones | `04657006a72b938cc9bfd231663a737a8477d309edcbd62b5ec54ab23c90de43` |

## Comandos y resultado

| Paso | Comando | Resultado |
|---|---|---|
| Modelo | `python3.14 scripts/build_gold.py` | Ejecuta antes la puerta de Silver (140 controles, `ready_for_gold=true`). Gold queda publicada con 515 controles internos aprobados, en 121 s. |
| Caché y catálogo | `python3.14 scripts/discover_gold.py` | Caché v1, perfiles de 29 tablas y entidades, en 31 s. Dos ejecuciones dieron el mismo SHA de caché. |
| Certificación | `python3.14 scripts/gold_query.py certify` | 17 consultas con resultado esperado y hash para la carga. |
| Verificación independiente | `python3.14 scripts/verify_gold_independent.py --write-references` | Aprobada en 98 s con 30 controles; escribe las 48 respuestas de referencia. Sin `--write-references` la repetición aprobó 78 controles, incluida la coincidencia de esas 48 referencias. |
| Evaluación | `python3.14 scripts/run_gold_evals.py` | **60/60 aprobadas** (20 frecuentes, 25 poco comunes y 15 trampas), con referencias de esta carga. Se informa una deriva, E025, respecto de la carga de desarrollo `0f6e0f1c…`, donde esa pregunta fallaba antes de declarar las implicaciones entre elegibilidades. |
| Puerta | `python3.14 scripts/check_gold_ready.py` | **`ready_for_agent=true`**, con 544 controles y 0 fallos en 108 s: 408 de catálogo, 32 de elegibilidad, 23 de agregados, 17 certificadas, 12 referenciales, 10 de cobertura, 9 de cotas y el resto de entradas, conciliación, eventos, claves, caché, verificación y evaluación. |
| Pruebas | `python3.14 -m unittest discover -s tests` | **87 pruebas OK** en 14 s: 57 de Bronze y Silver, que ya existían, 28 de Gold con datos sintéticos y 2 de integración sobre los datos reales. |

## Totales conciliados

| Medida | Gold | Recalculado desde Silver |
|---|---:|---:|
| Informes (`fact_report`) | 702.572 | 702.572 |
| Informes sin candidatos pendientes (cota inferior) | 390.944 | 390.944 |
| Informes con par candidato pendiente | 311.628 | 311.628 |
| Pares candidatos pendientes | 243.318 | 243.318 |
| Eventos confirmados (`fact_event`) | 6.959 | 6.959 |
| Informes en eventos confirmados | 17.920 | 17.920 |
| Informes con evidencia externa | 20.751 | 20.751 |

| Fuente | Informes | Sin candidatos pendientes | Con candidato pendiente | Con evidencia externa |
|---|---:|---:|---:|---:|
| Capella | 30.453 | 21.843 | 8.610 | 0 |
| UFO-search | 54.751 | 40.440 | 14.311 | 20.751 |
| UFOCAT | 320.412 | 168.810 | 151.602 | 0 |
| UPDB | 296.956 | 159.851 | 137.105 | 0 |
| **Total** | **702.572** | **390.944** | **311.628** | **20.751** |

| Agregado | Elegibilidad | Incluidos | Excluidos | Filas |
|---|---|---:|---:|---:|
| `agg_year` | calendario | 695.034 | 7.538 | 1.521 (605 años, del 34 al 2023) |
| `agg_month` | mes | 677.377 | 25.195 | 6.529 |
| `agg_weekday_hour` | día + hora | 213.104 | 489.468 | 450 |
| `agg_country` | país | 626.833 | 75.739 | 661 (231 países) |
| `agg_shape` | ninguna (incluye “sin forma”) | 702.572 | 0 | 58 |
| `agg_source` | ninguna | 702.572 | 0 | 26 |
| `agg_spatial_cell` | mapa | 495.019 por resolución | 207.553 | 13.739 (6.081 celdas de 1°, 1.023 de 5°) |
| `agg_nuclear_band` | proximidad | 495.019 | 207.553 | 901 |

Además, `fact_report` con `eligibility: ["hour"]` deja 233.854 informes con hora
y 468.718 fuera.

## Qué verifica cada control

### Puerta de aceptación (`check_gold_ready.py`)

- **Entradas:** SHA de Gold, Silver y Bronze; definiciones vigentes; `load_id`
  recalculado; y una ejecución nueva de la puerta de Silver sobre el snapshot
  exacto.
- **Conciliación:** total, IDs en ambos sentidos con Silver y con Bronze, conteo
  por fuente, y 16 banderas y bases más coordenadas y país, informe a informe,
  contra `sighting_analytical`.
- **Agregados:** cada agregado, y cada resolución espacial, es igual grupo a
  grupo y en ambos sentidos (`EXCEPT`) a `fact_report` bajo su elegibilidad.
- **Cobertura:** incluidos + excluidos = 702.572 en cada agregado, e incluidos
  = suma del agregado; ningún agregado temporal, geográfico o de proximidad
  tiene claves nulas.
- **Elegibilidad:** los 19 valores con elegibilidad existen si, y solo si, el
  informe es elegible; cada motivo de exclusión es coherente con su bandera; se
  cumplen las implicaciones (día ⇒ mes ⇒ calendario, hora ⇒ calendario,
  proximidad ⇒ mapa) y la regla horaria.
- **Cotas:** en cada fila de cada agregado, inferior ≤ superior y superior −
  inferior = pendientes; el total de informes pendientes es igual al de Silver,
  y los extremos de pares suman el doble de los pares.
- **Eventos:** 6.959 eventos, 17.920 miembros, un representante por evento y
  `member_count` coherente.
- **Integridad:** `integrity_check`, `foreign_key_check`, etiquetas de todas
  las dimensiones y claves únicas.
- **Catálogo ⇔ esquema:** columnas de cada dataset, dimensiones declaradas y
  presentes, métricas por dataset, cotas emparejadas, métricas compatibles y
  ninguna dimensión huérfana.
- **Caché y documentos:** caché, `GOLD_CATALOG.json` y `GOLD_ENTITIES.json`
  corresponden a la carga.
- **Consultas certificadas:** las 17 son válidas, no cambiaron y reproducen su
  `rows_sha256`.
- **Verificación independiente y evaluación:** aprobadas para la carga.
- Silver y Bronze sin cambios al terminar.

### Verificación independiente (`verify_gold_independent.py`)

El script no importa ningún módulo Gold. Lee Silver directamente
(`sighting_analytical`, `duplicate_candidate`, `duplicate_resolution`,
`event_membership` y `duplicate_group`) y obtiene cada atributo con su propio
código: el día de la semana con `strftime('%w')` de SQLite en lugar de
`datetime`, las celdas con división entera y las bandas leyendo solo sus
límites de la política. Después compara:

- **Totales:** por fuente, año, país y forma, contra los agregados Gold.
- **Cotas de duplicados:** total y por año.
- **Muestra informe a informe:** 2.002 informes (semilla fija 20261122 más el
  primer y el último ID), en 50 columnas de `fact_report`.
- **Consultas certificadas:** cada una se evalúa con un intérprete propio del
  contrato y se compara con su resultado esperado (filas, filas de origen y
  truncado).
- **Set de evaluación:** con `--write-references` calcula la respuesta de
  referencia de cada pregunta que se responde; sin la opción, comprueba que las
  referencias guardadas siguen coincidiendo.

### Set de evaluación (`docs/GOLD_EVALS.json`)

El set tiene 60 preguntas en español:

- **20 frecuentes:** cubiertas por las 17 consultas certificadas.
- **25 poco comunes:** requieren componer una consulta.
- **15 trampas:**
  - 9 deben rechazarse: “ovnis reales”, día sin elegibilidad, eventos sobre
    informes, sumar porcentajes, sumar resoluciones, mes sin elegibilidad,
    mapa sin coordenadas, SQL y más de 500 filas;
  - 3 deben aclararse: Congo, Corea, Narnia;
  - 3 se responden con advertencias obligatorias: proximidad nuclear como
    prueba, `hoax_likelihood` como engaño confirmado y “avistamientos” en 1997.

Para cada pregunta que se responde, el ejecutor comprueba:

- que `search_certified` encuentra la consulta certificada esperada, en las
  frecuentes;
- que el resultado es certificado o compuesto según corresponda;
- que la consulta y la vista son las esperadas;
- que aparecen las limitaciones obligatorias;
- que las filas, las filas de origen y el total coinciden con la referencia
  independiente;
- que la procedencia es la de la carga actual.

Los resultados se guardan en `data/gold/evals/<load_id>.json`. Si cambia el
hash de una respuesta respecto de otra carga, se informa como deriva.

`forbidden_phrases` y `note` describen lo que el agente no debe decir. El
ejecutor no evalúa la redacción, porque eso requiere el modelo de lenguaje.

### Pruebas unitarias (`tests/test_gold.py`)

Usan una Silver y una Bronze sintéticas (`tests/gold_fixture.py`), por lo que
también corren en CI sin datos. Cubren:

- **Build:** conciliación y `model_checks` completos; valores con elegibilidad y
  motivos (marcadores de día y de 01-01, fecha calificada con reloj, intervalo,
  borde de celda 90°/180°, bandas); agregados y cotas.
- **Entradas y publicación:** SHA fijado incorrecto, puerta de Silver de otro
  snapshot, validación fallida que conserva la salida anterior, Silver
  modificado durante la lectura, archivo histórico, `load_id` determinista y
  vocabulario sin etiqueta.
- **Contrato e inyección:** campos extra, SQL, NaN, booleanos como enteros,
  límite, identificadores con comillas y valores ligados.
- **Combinaciones prohibidas, ratios y cotas:** día y mes sin elegibilidad,
  sumar porcentajes, particiones, métricas no disponibles, vistas, `is_null`
  sobre columnas con elegibilidad, implicaciones; ratios recalculados en el
  total; cotas emparejadas y coherentes.
- **Resultados:** exclusiones que suman, truncado, resultado vacío, presupuesto
  de instrucciones, procedencia, consulta legible y limitaciones.
- **Certificación y caché:** pérdida de certificación al cambiar la consulta o
  la carga, entidades ambiguas e inexistentes, y caché con SHA incorrecto.
- **Archivos semánticos:** registro de correcciones, forma del set de
  evaluación y consultas certificadas válidas en el contrato.

`tests/test_gold_evals.py` ejecuta el set de evaluación y las consultas
certificadas sobre los datos reales; se omite si la caché local no existe.

## Hallazgo sobre Silver (no bloqueante)

61 informes de Capella tienen `datetime_precision='second'` con una fecha
`qualified`. Ejemplos:

| ID | Fecha original |
|---|---|
| 672699 | `14 July 1952, approximately 1300 hours` |
| 674362 | `Summer 67`, guardada como `1967-07-01T01:00:00` |
| 674761 | `April 1970(approx)` |

Para encontrarlos:

```sql
SELECT id, date_event_raw, sighting_datetime FROM sighting_analytical
WHERE clock_basis IS NOT NULL AND usable_for_calendar = 0;
```

Silver no los publica en el calendario y su contrato pide respetar
`date_certainty`, así que no viola sus reglas. Pero un consumidor que solo
mirara `datetime_precision` usaría esas horas. Gold exige calendario apto para
usar la hora y no modifica Silver.

## Límites de esta verificación

- Verifica que Gold representa fielmente Silver v6 con las reglas declaradas.
  No verifica que los informes sean verdaderos. Coincidir con Bronze tampoco lo
  prueba.
- La verificación independiente reutiliza las vistas de consumo de Silver
  (`sighting_analytical`) y los límites de bandas y celdas de la política. Es
  independiente del código Gold, no de Silver.
- El set de evaluación comprueba herramientas y datos, no la redacción de un
  modelo de lenguaje en vivo.
