# Contrato de Silver para analítica — políticas v4 a v6

La política vigente es **v6**. Sus correcciones de la auditoría Silver–Bronze,
las recuperaciones de fuente, las excepciones geográficas y la aceptación para
Gold se documentan en [Silver lista para Gold](silver-gold-readiness.md). Los
resultados numéricos de v4 que aparecen al final son históricos; el informe
generado identifica la salida actual mediante SHA-256.

## Criterio y alcance

Silver se construye de forma reproducible sobre el snapshot fijado de Bronze v17.
Mantiene sus diez tablas, todas sus filas e identificadores y sus campos con
información. Las 41 columnas omitidas se comprueban vacías antes de cada
construcción. El grano principal es **un informe**, no un fenómeno demostrado ni
un evento cuya independencia esté confirmada.

La implementación aplica estas recomendaciones oficiales, consultadas el
22 de noviembre de 2026:

- [Databricks: arquitectura medallion](https://docs.databricks.com/aws/en/lakehouse/medallion):
  Silver valida, limpia, normaliza y conserva una representación detallada de
  cada registro para análisis. Las agregaciones de negocio corresponden a Gold.
- [Databricks: expectativas de calidad](https://docs.databricks.com/aws/en/ldp/expectations):
  las reglas pueden conservar datos con métricas, excluirlos o detener un flujo.
  Aquí se conserva cada informe; un campo dudoso no invalida sus otras dimensiones.
- [Databricks: patrones de expectativas](https://docs.databricks.com/aws/en/ldp/expectation-patterns):
  cuarentena, comparación de conteos, detección de registros ausentes y unicidad
  de claves. Aquí se implementan controles equivalentes mediante SQLite, SQL,
  claves, trazabilidad y validación antes de publicar la salida.

Es una aplicación del patrón en este repositorio SQLite, con reglas de dominio
explícitas y comprobables. Las recomendaciones no son una certificación de
Databricks ni una garantía sobre la veracidad de las observaciones.

## Recuperar información sin inventar precisión

El parser de origen había convertido algunas expresiones parciales en días
concretos. La política v4 contrasta los campos canónicos con formas explícitas
admitidas de `date_event_raw`:

| Evidencia | Representación analítica |
|---|---|
| `Summer 1953`, aunque el origen diga `1953-07-01` | `1953`, precisión de año y certeza `coarsened`. |
| `Late 8/1947` | `1947-08`, sin día. |
| UFOCAT `1974-03- M`, aunque el origen conserve solo `1974` | `1974-03`; se conserva la letra original sin asignarle un día. |
| `1995/1996` | Intervalo inclusivo de años 1995–1996, sin fecha puntual. |
| `1950's` | Intervalo inclusivo 1950–1959, sin elegir 1950 como año del informe. |
| Fecha con `approximate`, duda o calificador no interpretable | Valor de origen conservado y marcado `qualified`; fuera de calendario y deduplicación estricta. |
| Dos representaciones temporales inequívocas pero contradictorias | Fecha canónica desconocida, evidencia y valores anteriores conservados. |
| Año truncado, siglo desconocido, día imposible o fecha futura | Sin completar ni corregir cifras; evidencia disponible para revisión. |

Se admiten únicamente gramáticas ancladas, calendario válido y precisión
explícita. No se emplea un parser difuso que rellene componentes con la fecha
actual. Las fechas numéricas con mes/día ambiguos no se reinterpretan; los años
de dos cifras no se expanden. Un año aislado de cuatro cifras con cero inicial
no se recupera como año por sí solo. Los centinelas UFOCAT siguen en revisión.
Las estaciones no se convierten en meses porque dependen del hemisferio.
Los calificadores dentro de una década no se convierten en subrangos
arbitrarios: `mid-1990s` conserva la envolvente 1990–1999 y la expresión original.
El calendario validado es el gregoriano proléptico de `datetime`; no se
convierten calendarios históricos sin metadatos.
Winter y prosa relativa permanecen calificadas. No se obtiene la fecha del
evento de un año que únicamente corresponde a su publicación o reporte.
Desde v6, el texto libre fuera de la gramática solo certifica los componentes
que contiene: cada año, mes y día canónico debe aparecer en `date_event_raw`
en una expresión de fecha explícita (numérica, con nombre de mes en inglés o
italiano, compacta o grupo militar día-hora). Lo demás se retira o califica.

`temporal_evidence` conserva expresión, interpretación, candidato, límites de
años y si cambió algún campo de origen. `applied=0` en un intervalo puede
significar que la fecha puntual ya estaba vacía: el intervalo sí se conserva.
`date_certainty='source'` identifica precisión del campo canónico sin un
calificador detectado; no certifica que el informe sea históricamente exacto.

Los tiempos conservan su offset conocido y sus dígitos fraccionales. No se
infiere zona horaria ni se traslada una hora de un informe a otro. Un campo
parcial no se convierte en timestamp para facilitar deduplicaciones.

## Geografía y rescate de valores

La política v4 pone en revisión los pares completos con representaciones de
país reconocidas pero contradictorias, cualquiera que sea su método de
geocodificación. También los pares de informes que copian exactamente los de
su ubicación original. Se conserva un par distinto del informe, pues no hay
evidencia de que provenga de esa geocodificación.

El país canónico requiere representaciones compatibles con el catálogo
versionado. `country_evidence` conserva ambos valores originales y reconoce
cada código de forma independiente. Es posible analizar **el país declarado**
o la discrepancia entre representaciones, sin presentarlo como país resuelto.
No se convierten países históricos en sucesores actuales ni se adivinan países
por condados, ciudades, mares o fronteras.

Las dependencias también se invalidan: una distancia y un sitio nuclear más
cercano calculados desde un par de coordenadas no utilizable dejan de publicarse
en sus campos canónicos. `geographic_dependency` conserva los dos valores
originales; no se recalculan usando otra ciudad, país o catálogo de instalaciones
supuesto. Las medidas asociadas a pares utilizables se conservan como medidas
del origen, sin atribuir una verificación nueva a su catálogo o algoritmo.

Los valores retirados de campos canónicos siguen en Bronze, en `silver_change`
y, cuando corresponde, en `quality_issue`. La vista `silver_rescued_value`
permite recuperarlos directamente como JSON sin abrir otra base. Un valor
rescatado conserva su problema: no vuelve automáticamente a ser utilizable.
`0`, sonido `none`, país `NA` (Namibia) y JSON vacío conservan sus significados
según columna. No hay un reemplazo global de marcadores.

## Vistas y denominadores

`sighting_analytical` conserva exactamente una fila por informe, incluso cuando
faltan ubicación, fecha o país. Incluye fuente, representante canónico, país
canónico, ambas representaciones de país y límites temporales disponibles.

- `usable_for_map`: par completo dentro de rango y fuera de cuarentena.
- `usable_for_nuclear_proximity`: par utilizable y ambos campos de proximidad
  presentes. Sigue siendo una medida heredada del origen.
- `usable_for_calendar`: fecha válida, con certeza `source` o `coarsened`.
- `usable_for_country`: país canónico consistente y reconocido.
- `is_canonical`: representante elegido por el criterio estricto; no prueba que
  sea diferente de todos los candidatos pendientes.

Los clasificadores, probabilidades, sentimientos y puntuaciones heredados se
conservan con su significado de origen. En particular, `quality_score` no es
la calificación de cumplimiento del contrato Silver y no se recalcula como si
se conociera otro algoritmo de clasificación.

Estos indicadores no son un puntaje de calidad general. Un informe sin fecha
puede servir para analizar formas o países, y uno sin país puede servir para
analizar años. `quality_summary.affected_records` cuenta una vez cada registro
por regla/acción; sumar reglas puede contar el mismo informe varias veces.
`field_profile` del informe de construcción conserva los denominadores y la
completitud de cada campo original. Los perfiles no convierten ausencia en error.

Ejemplos de uso con grano explícito:

```sql
-- Informes por año conocido; incluye fechas parciales sin inventar día.
SELECT event_year, COUNT(*) AS reports
FROM sighting_reports_for_time_analysis
GROUP BY event_year;

-- Intervalos disponibles; no asignarlos a un único año para contar eventos.
SELECT id, source_name, date_event_raw, evidence_year_min, evidence_year_max
FROM sighting_analytical
WHERE date_status='range';

-- Discrepancias entre representaciones, conservando las dos alternativas.
SELECT id, source_name, country_reported, country_coded,
       reported_iso2, coded_iso2
FROM sighting_analytical
WHERE country_status IN ('conflict','unrecognized');

-- Vista por informe: cada fila representa un informe, incluidos duplicados.
SELECT id, lat, lng, canonical_event_id, is_canonical
FROM sighting_reports_for_map;
```

Las vistas existentes `sighting_for_map` y `sighting_for_time_analysis` usan
representantes canónicos; las nuevas vistas `sighting_reports_*` conservan
todos los informes elegibles. No se deben mezclar esos denominadores. Hay pares
pendientes que pueden corresponder al mismo evento: contar representantes
canónicos es aplicar una política explícita, no conocer el total real de eventos.

## Controles de aceptación

| Requisito | Evidencia exigida antes de publicar Silver |
|---|---|
| Bronze intacta | Tamaño y SHA-256 fijados, antes y después de construir. |
| Ninguna fila o clave perdida | Conteos y comparación bidireccional de IDs de las diez tablas. |
| Trazabilidad completa | Reconciliación de cada campo alterado con Bronze y `silver_change`. |
| Dominios, tipos, JSON y relaciones | Validadores por columna, catálogo, integridad SQLite y claves foráneas. |
| Precisión temporal y cobertura de evidencia | Reejecución de la gramática sobre todos los informes de Bronze; comparación de valores, certeza, rangos y evidencia, incluidas omisiones. |
| Dependencias geográficas | Ninguna distancia o instalación cercana canónica si el par de coordenadas no es utilizable; valores originales rescatables. |
| Cuarentena geográfica completa | Cálculo independiente desde Bronze, comparación de claves y de incidencias. |
| Vistas sin pérdidas ni multiplicación | Cobertura de todos los IDs, conteo de filas y flags por dimensión. |
| Agrupación reversible | Cobertura de membresía, representantes mínimos, tamaños y decisiones por candidato; exclusión de fechas calificadas. |
| Reproducibilidad | Hashes de código —incluido `silver_analytics.py`—, política, catálogo y fuente; ejecución sin consultas de red. |
| Uso analítico verificable | Perfil por campo, cobertura por fuente, diagnóstico de candidatos y pruebas de casos adversos. |

Las violaciones de identidad, integridad, linaje o reconciliación detienen la
construcción. Los defectos de valores se conservan y se separan por dimensión.
La salida previa y su informe se archivan antes de sustituir una salida validada.

## Reproducción y asuntos de origen

```bash
python3 -m unittest discover -s tests -q
python3 scripts/build_silver.py --replace
python3 scripts/build_silver.py --verify-only
python3 scripts/review_silver.py
```

Los informes generados y bases no se versionan en Git. El código, las reglas,
las pruebas y este contrato sí. El catálogo de países se consulta localmente.
La referencia temporal sigue fijada en 2026-11-21 para no cambiar el resultado
únicamente por el día de ejecución.

El cierre de la capa significa que las reglas y las representaciones son
consistentes, comprobadas y utilizables con los filtros declarados. No significa
que desaparezcan las incertidumbres del material de origen. Las fechas sin
siglo, fuentes sin hora, países históricos o contradictorios y pares sin
identidad demostrable siguen accesibles con sus estados. Resolverlos requiere
evidencia de origen; no es correcto fabricarla para obtener cero incidencias.

La suite también se ejecuta mediante `.github/workflows/test-silver.yml` en los
PR que afectan Silver. Ese trabajo usa fixtures sintéticos y no descarga las
bases. Su resultado demuestra regresiones de contrato; la comprobación sobre
los 702.572 informes requiere además construir y verificar el snapshot completo.

## Resultado verificado de v4

Construcción completa: **171 controles aprobados**. Verificación posterior del
archivo: **133 controles aprobados** y **301.194 campos reconciliados** contra
Bronze. Suite local: **45 pruebas aprobadas**. Se conservan las diez tablas de
origen, sus claves y los **702.572 informes**, también presentes una vez cada
uno en `sighting_analytical`. Bronze conserva su tamaño y SHA-256 fijados.

| Recuperación o tratamiento | Informes |
|---|---:|
| Fechas puntuales parciales recuperadas desde un campo vacío | 865 |
| Meses explícitos de UFOCAT recuperados donde el origen solo conservaba año | 4.009 |
| Precisión excesiva retirada de fechas de Capella | 854 |
| Intervalos conservados sin elegir un año o fecha puntual | 149 |
| Contradicciones inequívocas entre representaciones temporales puestas en revisión | 7 |
| Pares geográficos en revisión por conflicto de país | 9.417 |
| Medidas de proximidad retiradas por coordenadas no utilizables | 9.451 |

Los 149 intervalos son 88 rangos explícitos y 61 décadas. De ellos, 148 ya
carecían de fecha puntual y uno había sido convertido indebidamente en una.
Los dos campos de proximidad se retiran en los mismos 9.451 informes: 9.417
pares en revisión y 34 pares inválidos. No se suman esas dos columnas como si
fueran informes distintos. Los valores originales siguen rescatables.

Respecto a la v3 aprobada, el incremento del ledger se explica exactamente:
269.860 + 960 cambios adicionales de coordenadas + 11.472 cambios temporales
(dos campos en 5.736 informes) + 18.902 campos de proximidad = **301.194**.

| Fuente | Informes conservados | Calendario utilizable | Mapa utilizable | País canónico utilizable |
|---|---:|---:|---:|---:|
| Capella | 30.453 | 26.757 | 11.147 | 28.100 |
| UFO-search | 54.751 | 53.256 | 10.987 | 25.655 |
| UFOCAT | 320.412 | 319.129 | 295.883 | 284.826 |
| UPDB | 296.956 | 296.956 | 166.411 | 287.839 |
| Total | 702.572 | 696.098 | 484.428 | 626.420 |

Las columnas son elegibilidades independientes, no conjuntos excluyentes ni
porcentajes de calidad global. Los 484.428 informes con mapa utilizable conservan
también la proximidad heredada utilizable. `country_evidence` conserva 203.331
ubicaciones, 14 registros de recuperación de restos y 35 encuentros nucleares.

La agrupación más conservadora produce **6.961 grupos** y **691.609
representantes canónicos**, sin eliminar informes. Hay 6.959 grupos de UFOCAT
y dos de Capella. La auditoría de la base v3 archivada confirma que los dos
grupos de Capella ya existían: la afirmación previa de que todos los grupos
automáticos eran UFOCAT era demasiado amplia. Los grupos siguen siendo
independientes de los **243.318 pares candidatos originales** que conservan
su revisión pendiente.

La comprobación adicional del corpus no encontró discrepancias entre año y
fecha en las tablas de restos/encuentros nucleares, probabilidades softmax
completas desviadas de 1 por más de 0,001, ni dominantes de emoción incompatibles
con sus probabilidades por más de 0,000001. Son comprobaciones del snapshot;
no recalibran los modelos del origen ni validan sus inferencias semánticas.

También se ejecutaron estas consultas sobre la salida final; todas devolvieron
cero. No hay pares recuperables por enlace a una ubicación válida ni timestamps
precisos asociados a una fecha parcial en este corpus:

```sql
SELECT COUNT(*) FROM sighting s JOIN location l ON l.id=s.location_id
WHERE s.coordinate_status IN ('missing','partial') AND l.coordinate_status='valid';

SELECT COUNT(*) FROM sighting
WHERE date_precision IN ('year','month')
  AND datetime_precision IN ('minute','second','fractional_second');

SELECT COUNT(*) FROM sighting
WHERE date_status='valid' AND sighting_datetime IS NOT NULL
  AND substr(date_event,1,10)!=substr(sighting_datetime,1,10);

SELECT COUNT(*) FROM sighting
WHERE coordinate_status!='valid'
  AND (distance_to_nearest_nuclear_site_km IS NOT NULL
       OR nearest_nuclear_site_name IS NOT NULL);
```

SHA-256 de la salida final:
`91a4c7b06590bea6b5ed5c6cc67935163b873141ca8b24806536323021dd736d`.
El diagnóstico generado contiene SQL, conteos, hashes y linaje para reproducir
los resultados. Las limitaciones de origen siguen declaradas en sus estados;
no se han convertido en valores ciertos para cerrar artificialmente incidencias.
