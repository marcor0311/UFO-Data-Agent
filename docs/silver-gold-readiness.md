# Silver v5: preparación para Gold

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

## Recuperaciones con evidencia

El [manual oficial UFOCAT 2023](https://cufos.org/PDFs/UFOCAT%20Codebook%202023.pdf),
páginas 16–18, permite interpretar los códigos `196.`, `196E`, `196M` y `196L`
como incertidumbre dentro de los años 1960–1969. Se conserva toda la década,
sin elegir un año ni acotar arbitrariamente «principio», «mitad» o «final».
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
Se validan por rango y dominio antes de aplicarlas al informe enlazado. Los
66 registros identificados como lunares, planetarios u orbitales tienen mapa y
país terrestre no aplicables. Las coordenadas fuera de rango permanecen en la
evidencia. Un país original reconocido se publica por informe; las etiquetas
que abarcan varios países o regiones no se convierten en un país único. El país
que realizó una prueba nuclear no se confunde con el país donde ocurrió.

Las ubicaciones compartidas mantienen sus valores y estados, pues una
corrección demostrada para un informe no acredita los otros informes que las
usan. `country_basis`, `coordinate_basis` y las tablas `source_*_evidence`
explican la procedencia de la representación analítica de cada informe.

Cada coordenada modificada obliga a recalcular las medidas de proximidad con
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
| Analizar calendario | `sighting_reports_for_time_analysis`; respetar `date_precision` y `date_certainty`. |
| Analizar intervalos | `temporal_evidence`: no asignar el intervalo a un único año. |
| Analizar horas | Timestamp con `datetime_precision` de minuto, segundo o fracción; respetar `timezone_status`. `time_raw` puede ser aproximada. |
| Mapear informes | `sighting_reports_for_map`; conservar `coordinate_basis` al interpretar precisión. |
| Agrupar por país | `sighting_analytical WHERE usable_for_country=1`; conservar `country_basis`. |
| Analizar proximidad | `sighting_analytical WHERE usable_for_nuclear_proximity=1`. |
| Aplicar deduplicación | `event_membership` y representantes de `sighting_canonical`; preservar todas las fuentes. |
| Medir incidencias | `quality_summary` por regla y `duplicate_review` por par. |

Los representantes no prueban que los candidatos pendientes correspondan a
eventos distintos. Gold debe llamar «informes» a los conteos por informe y
documentar la política si utiliza representantes. La suma de incidencias de
reglas distintas puede contar el mismo informe varias veces.

El informe de preparación incluye cobertura por fuente y dimensión, controles
aprobados, campos reconciliados, candidatos pendientes y SHA-256 de la salida.
Esas métricas definen el estado verificable de esta versión.

## Resultado de la construcción completa

La construcción v5 aprobó **173 controles**, conservó los **702.572 informes**
y reconcilió **402.990 cambios por campo** con Bronze y `silver_change`.
Bronze mantuvo el tamaño y SHA-256 fijados. La salida anterior quedó archivada.
La comprobación posterior del archivo publicado aprobó **135 controles** y
generó `ufo.readiness.json` con `ready_for_gold=true`.

| Recuperación o tratamiento verificado | Informes |
|---|---:|
| Horas originales recuperadas como texto | 19.064 |
| Timestamps recuperados con día y hora exactos del mismo registro | 12.640 |
| Coordenadas originales terrestres publicadas | 20.086 |
| Países inequívocos disponibles en el catálogo original | 15.380 |
| Registros originales identificados fuera de la superficie terrestre | 66 |
| Décadas UFOCAT conservadas como intervalos | 398 |

Son conteos de tratamientos, con posible solapamiento entre filas; no se suman
como registros diferentes. Publicar coordenadas de catálogo puede corregir un
par anterior o recuperar uno ausente. Los cuatro pares terrestres originales
fuera de rango siguen en la evidencia y no se aplican como reemplazo.

La cobertura de mapa y proximidad pasa de 484.428 a **498.689 informes**:
**14.261 informes adicionales**. La cobertura de país canónico pasa de 626.420
a **627.827 informes**, con **1.407 adicionales**. Se mantienen **696.098
informes** aptos para calendario; rescatar horas e intervalos no convierte
fechas inciertas en días ciertos.

Se mantienen **6.961 grupos estrictos**, con **10.963 informes agrupados** y
**691.609 representantes**. Los **243.318 pares candidatos** siguen pendientes
de evidencia suficiente; las nuevas horas no convierten automáticamente una
similitud en identidad de evento.
La revisión clasifica todos los pares sin doble conteo: 227.921 siguen sin
fecha/hora suficiente y 15.397 presentan primero otro impedimento comprobado.
No hay coincidencias estrictas que el algoritmo haya dejado sin confirmar ni
informes en cuarentena publicados en la vista de mapa.

SHA-256 de Silver v5:
`1059516e6d41f2f3986811a1c55c2a6b546936e8f64c8095c0545d8aa5028851`.
