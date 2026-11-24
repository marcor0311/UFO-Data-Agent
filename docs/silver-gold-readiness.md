# Silver v6: preparación para Gold

## Alcance de la aceptación

Silver conserva una representación validada y sin agregar de cada informe de
Bronze. Normaliza campos, valida tipos y relaciones, agrupa duplicados con
evidencia estricta, recupera información demostrable y publica métricas de
calidad. El grano de consumo es **un informe**. Gold podrá definir dimensiones,
medidas y agregaciones sobre esas representaciones.

Este criterio sigue la separación descrita por
[Databricks para medallion](https://docs.databricks.com/aws/en/lakehouse/medallion).
Sus [expectativas de calidad](https://docs.databricks.com/aws/en/ldp/expectations)
admiten conservar valores con métricas, excluirlos del consumo o detener una
actualización. Los [patrones de expectativas](https://docs.databricks.com/aws/en/ldp/expectation-patterns)
incluyen cuarentena y reconciliación de conteos y claves. En este repositorio
se implementan esos controles con SQLite; no se ejecuta un servicio Databricks
ni se atribuye una certificación de esa empresa.

La aceptación exige que **todos los controles del contrato pasen**. La
completitud de cada campo se mide por separado. Un país desconocido o un
candidato de duplicación pendiente conservan su incertidumbre. La cuarentena
evita un uso indebido, pero no cuenta como corrección de la fuente.

## Correcciones de la auditoría Silver–Bronze (v6)

La auditoría completa de v5 contra Bronze aprobó conservación, reconciliación,
tipos, dominios, duplicación y grano, pero rechazó la capa por estos motivos.
v6 los corrige así:

| Hallazgo de la auditoría | Corrección en v6 |
|---|---|
| 1.818 días `01` de Capella certificados como `source` sin aparecer en el texto (`07/52 → 1952-07-01`) | Fuera de la gramática, cada componente canónico debe aparecer en `date_event_raw`. Se retiran día o mes sintéticos (`07/52 → 1952-07`, `coarsened`). Si el año no aparece (`20 Feb`) o el texto da un año imposible (`GIUGNO 3003`), la fecha queda `qualified` (`unsupported`). |
| 573 fechas con “about”, “~”, “or”, “?” como `source` | Calificadores ampliados (aproximación, alternativas, intervalos, fechas relativas, de reporte o publicación). El formato italiano de Capella se reconoce: sus calificadores posteriores a la fecha afectan a la hora. |
| Exceso de días `01` en UPDB sin señalar | `temporal_placeholder_profile` mide por fuente los días `01`, `15` y `01-01`. Los patrones con exceso de 1,25× o más marcan `day_placeholder_risk`/`month_placeholder_risk` y bajan `calendar_precision`. |
| 23 fechas en revisión con etiqueta de precisión | Una fecha sin valor tiene precisión `unknown`. |
| `1975 (as listed on website cover page)` y `1938 (September)` | El primero queda calificado (fecha de publicación). El segundo conserva `1938-09`. |
| `~30 (99 ft, per Scully)` y `component-only…` | `silver_rescued_value` incluye las anotaciones de medidas aproximadas y deja de listar cadenas vacías. |
| 7.208 pares válidos de Bronze sustituidos por el catálogo, 2.289 desplazados más de 1.000 km; 1.385 cuarentenas esquivadas; 2.455 países contradictorios | El catálogo solo rellena lo que Bronze no tiene o lo corrobora. Si discrepa (más de 50 km o país incompatible), ninguna versión se publica y ambas se conservan. Una cuarentena de Bronze nunca se levanta. |
| Datos externos no declarados por informe | `coordinate_basis`, `country_basis`, `time_basis`, `clock_basis` y `uses_external_evidence` en `sighting_analytical`. |
| “10.963 informes agrupados” | Hay **17.920 informes en grupos**; **10.961** no son representantes. |

Las expresiones reconocidas y sus límites están en `scripts/silver_analytics.py`
y en las pruebas de `tests/`. Los años de dos cifras pueden corroborar el
siglo que asignó el origen, pero Silver no lo deduce por sí misma. El perfil de
marcadores es estadístico: no identifica qué informe concreto usó un marcador.
Por eso la fecha se conserva y solo se limita la precisión apta para análisis.

## Recuperaciones con evidencia

El [manual oficial UFOCAT 2023](https://cufos.org/PDFs/UFOCAT%20Codebook%202023.pdf),
páginas 16–18, permite interpretar los códigos `196.`, `196E`, `196M` y `196L`
como incertidumbre dentro de los años 1960–1969. Se conserva toda la década,
sin elegir un año ni acotar arbitrariamente “principio”, “mitad” o “final”.
La interpretación es específica de UFOCAT. Los códigos de estación conservan
solo el año o mes explícito. Las horas incompletas o corruptas que el importador
había aceptado por prefijo pierden su precisión de minuto; la fecha válida se
conserva. Los otros años truncados siguen pendientes.

Se recuperaron campos factuales del
[JSON original de UFO-search](https://github.com/richgel999/ufo_data/blob/04d698ee322f63ee582651f7581a58c8ae135cca/bin/majestic.json).
La revisión fijada contiene 54.751 IDs únicos, coincidentes con los de esta
fuente en Bronze. El enlace exige también igualdad exacta de `date_event_raw`.
Las referencias extraídas están versionadas en
`config/silver-source-times.json` y `config/silver-source-geography.json`.
Solo contienen identificadores, fechas, horas, coordenadas, países y marcas de
interpretación; no incluyen narraciones ni índices de búsqueda textuales.

Las 19.064 horas originales se conservan en `time_raw`. Un timestamp requiere
un día válido, una hora completa sin aproximación, certeza temporal apta y
ausencia de fechas alternativas o periodos. Nunca se une la hora de otro
informe ni se infiere una zona horaria.

Los 20.156 registros con geografía estructurada aportan coordenadas de catálogo.
Se validan por rango y dominio, y se comparan con el par y el país de Bronze
antes de aplicarlas al informe enlazado (`source_geography_evidence`). Los
66 registros identificados como lunares, planetarios u orbitales tienen mapa y
país terrestre no aplicables. Las coordenadas fuera de rango permanecen en la
evidencia. Un país original reconocido se publica por informe; las etiquetas
que abarcan varios países o regiones no se convierten en un país único; solo
sirven para detectar contradicciones (`region_members` de la política). El país
que realizó una prueba nuclear no se confunde con el país donde ocurrió.

Las ubicaciones compartidas mantienen sus valores y estados, pues una
corrección demostrada para un informe no acredita los otros informes que las
usan. `country_basis`, `coordinate_basis` y las tablas `source_*_evidence`
explican la procedencia de la representación analítica de cada informe.

Cada coordenada rellenada obliga a recalcular las medidas de proximidad con
las instalaciones nucleares pertinentes del catálogo local. Se mantiene el
algoritmo esférico del origen: Haversine, radio 6371 km y redondeo a 0,1 km.
La distancia es relativa a ese catálogo, no a todas las instalaciones mundiales.
Los grupos de duplicados se reconstruyen después de todas estas correcciones.

Para reproducir las referencias desde la copia original fijada:

```bash
python3 scripts/prepare_silver_evidence.py --timeline /ruta/majestic.json
```

El extractor comprueba el SHA-256 original antes de escribir. La construcción
normal de Silver usa las referencias locales y no requiere red.

## Aceptación ejecutable

```bash
python3 scripts/build_silver.py --replace
python3 scripts/check_silver_ready.py
python3 scripts/review_silver.py
```

El segundo comando vuelve a verificar la base real, sus hashes, la política,
el código, las referencias, el linaje, las claves y las reglas por dimensión.
Reproduce las decisiones temporales y geográficas desde los valores originales,
incluidas las omisiones de evidencia. Termina con código distinto de cero ante
un incumplimiento. Su resultado se guarda en `data/silver/ufo.readiness.json`.
Gold debe depender de la ejecución satisfactoria de este comando para el
snapshot exacto que va a consumir; leer un informe antiguo no constituye una
verificación del estado actual.

La publicación de una nueva Silver ocurre después de validar el archivo
temporal completo. La versión anterior y su informe quedan archivados en
`.history/`. Bronze conserva su tamaño y hash. Ante nuevas filas append-only
en Bronze, se usa su nuevo snapshot/manifiesto y se vuelve a construir Silver:
la reconstrucción completa incorpora también registros tardíos y recalcula los
grupos, sin descartar informes por su orden de llegada. No hay watermark que
elimine observaciones antiguas. El hash del snapshot impide aceptar cambios
inadvertidos de esquema o contenido. Al versionar un nuevo manifiesto se debe
revisar también el esquema y actualizar el contrato cuando corresponda.

## Consumo desde Gold

| Necesidad | Entrada y condición |
|---|---|
| Contar informes | `sighting_analytical`: exactamente una fila por ID de Bronze. |
| Analizar años | `sighting_reports_for_time_analysis`; respetar `date_certainty`. |
| Analizar meses | `sighting_analytical WHERE usable_for_month_analysis=1`. |
| Analizar días | `sighting_analytical WHERE usable_for_day_analysis=1`; excluye los marcadores de día de cada fuente. |
| Analizar intervalos | `temporal_evidence`: no asignar el intervalo a un único año. |
| Analizar horas | Timestamp con `datetime_precision` de minuto, segundo o fracción; respetar `timezone_status`. `time_raw` puede ser aproximada. |
| Mapear informes | `sighting_reports_for_map`; conservar `coordinate_basis` al interpretar precisión. |
| Agrupar por país | `sighting_analytical WHERE usable_for_country=1`; conservar `country_basis`. |
| Solo Bronze | Filtrar `uses_external_evidence=0`, o la procedencia de la dimensión analizada. |
| Analizar proximidad | `sighting_analytical WHERE usable_for_nuclear_proximity=1`. |
| Aplicar deduplicación | `event_membership` y representantes de `sighting_canonical`; preservar todas las fuentes. |
| Medir incidencias | `quality_summary` por regla y `duplicate_review` por par. |

Los representantes no prueban que los candidatos pendientes correspondan a
eventos distintos. Gold debe llamar “informes” a los conteos por informe y
documentar la política si utiliza representantes. La suma de incidencias de
reglas distintas puede contar el mismo informe varias veces.

El informe de preparación incluye cobertura por fuente y dimensión, controles
aprobados, campos reconciliados, candidatos pendientes y SHA-256 de la salida.
Esas métricas definen el estado verificable de esta versión.

## Resultado de la construcción completa

La construcción v6 aprobó **178 controles**, conservó los **702.572 informes**
y reconcilió **395.318 cambios por campo** con Bronze y `silver_change`.
Bronze mantuvo el tamaño y el SHA-256 fijados. La salida v5 quedó archivada en
`.history/`. La comprobación posterior del archivo publicado aprobó **140
controles** y generó `ufo.readiness.json` con `ready_for_gold=true`.

Una re-auditoría independiente, que no importa código del proyecto, repitió los
controles del informe sobre v6 y obtuvo estos resultados:

- 0 días de Capella sin respaldo textual.
- 0 fechas con lenguaje aproximado certificadas como `source`.
- 0 años de calendario ausentes del texto.
- 0 fechas nulas con etiqueta de precisión.
- 0 marcas de marcador erróneas.
- 0 discrepancias en las 20.156 decisiones geográficas.
- 0 pares válidos de Bronze sustituidos y 0 desplazamientos publicados de más de 1.000 km.
- 0 informes en cuarentena en el mapa.
- 702.572 filas para 702.572 IDs.

Los scripts originales del auditor confirmaron la trazabilidad (0 cambios sin
registro ni entradas huérfanas), la proximidad recalculada (12.529 de 12.529) y
los grupos (0 discrepancias).

| Tratamiento verificado | Informes |
|---|---:|
| Fechas de Capella con precisión sintética retirada (`coarsened`) | 1.812 |
| Fechas cuyo año no aparece en el texto (`unsupported`, fuera del calendario) | 485 |
| Fechas de Capella contradictorias con su texto, en revisión | 81 |
| Informes con riesgo de marcador de día (precisión de mes o año) | 68.588 |
| Horas originales recuperadas como texto | 19.064 |
| Timestamps recuperados con día y hora exactos del mismo registro | 12.640 |
| Coordenadas de catálogo que rellenan un par ausente | 12.529 |
| Pares de Bronze corroborados por el catálogo (50 km o menos) | 3.887 |
| Coordenadas en revisión por contradicción entre catálogo y Bronze | 2.285 |
| Países del catálogo que rellenan una ubicación sin país | 1.634 |
| Países en revisión por contradicción entre catálogo y Bronze | 1.215 |
| Registros originales fuera de la superficie terrestre | 66 |

Son conteos de tratamientos, que pueden solaparse entre filas; no se suman
como registros diferentes.

| Fuente | Informes | Calendario | Mes | Día | Mapa | País | Con evidencia externa |
|---|---:|---:|---:|---:|---:|---:|---:|
| Capella | 30.453 | 25.695 | 24.301 | 21.313 | 11.147 | 28.100 | 0 |
| UFO-search | 54.751 | 53.254 | 51.306 | 47.925 | 21.578 | 26.068 | 20.751 |
| UFOCAT | 320.412 | 319.129 | 309.188 | 267.870 | 295.883 | 284.826 | 0 |
| UPDB | 296.956 | 296.956 | 292.582 | 255.871 | 166.411 | 287.839 | 0 |
| Total | 702.572 | 695.034 | 677.377 | 592.979 | 495.019 | 626.833 | 20.751 |

Respecto a v5, el calendario baja de 696.098 a 695.034 informes, el mapa de
498.689 a 495.019 y el país de 627.827 a 626.833. Son informes que v5 publicaba
sin respaldo en el texto o en Bronze. Dentro del mapa, 12.529 informes usan
coordenadas del catálogo, y 1.634 países proceden del catálogo.

Patrones de marcador detectados (observados frente a la línea base):

| Fuente | Día `01` | Día `15` | `01-01` |
|---|---:|---:|---:|
| UPDB | 2,83× | 1,80× | 2,66× |
| Capella | 1,80× | — | 1,67× |
| UFOCAT | 1,42× | 1,36× | 1,57× |
| UFO-search | — | — | 1,32× |

Se mantienen **6.959 grupos estrictos**, con **17.920 informes en grupos**, de
los cuales **10.961 no son representantes**. Los dos grupos de Capella de v5
desaparecen porque su texto (`TUESDAY 18 AUG 2300 (L)`) no contiene el año, y
una fecha calificada no confirma una identidad. Los **243.318 pares
candidatos** siguen pendientes de evidencia suficiente. No hay coincidencias
estrictas que el algoritmo haya dejado sin confirmar ni informes en cuarentena
publicados en la vista de mapa.

## Límites que no se resuelven en Silver

- Que un valor coincida con Bronze o con su catálogo no prueba que sea
  históricamente exacto.
- Los candidatos pendientes no prueban que sean eventos distintos. Los
  representantes no se cuentan como eventos reales.
- Las coordenadas y países rellenados desde UFO-search proceden de una fuente
  externa fijada por SHA-256. Bronze no puede confirmarlos y quedan declarados
  por informe.

SHA-256 de Silver v6:
`72ada3670f79568025bc4f1c0184e4ae3b3c0236ece6f9f4a2483544a92aa25e`.
