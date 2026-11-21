# Silver

La política v3 de `config/silver.json` se aplica a Bronze v17. Conserva las 10
tablas originales, todas sus filas y sus identificadores. Omite las 41 columnas
vacías aprobadas y cuatro índices asociados. Añade columnas de calidad, tablas
de trazabilidad y vistas de eventos canónicos. Bronze permanece intacta.

## Construcción y revisión

```bash
python3 scripts/build_silver.py
python3 scripts/build_silver.py --verify-only
```

Si ya existe una Silver validada, reconstruir con:

```bash
python3 scripts/build_silver.py --replace
```

La base e informe anteriores se conservan en `.history/<SHA-256-anterior>/`.
Una entrada, política o validación fallida no sustituye la salida existente.
También se puede construir otra copia con `--database RUTA`.

## Reglas aplicadas

- **Texto:** recortar espacios exteriores y convertir cadenas vacías en NULL
  únicamente en los campos declarados. `0`, `[]`, `none` en sonido y categorías
  de desconocido no se convierten globalmente en faltantes.
  Los marcadores `null`, `none`, `n/a` y `nan` se convierten en NULL únicamente
  en ciudad y estado, según la configuración explícita por columna. `NA` como
  país conserva su significado de Namibia.
- **Fechas:** validar el calendario y normalizar el formato. Conservar año,
  mes, día y precisión horaria reales en `date_precision`, `datetime_precision`
  y `event_year`. No inventar día, hora ni zona; `timezone_status` distingue
  un offset conocido de una hora sin zona declarada. Fechas inválidas, futuras
  respecto de `quality.reference_date` y centinelas UFOCAT `0019-…` quedan NULL
  y registradas para revisión. No se altera `date_event_raw`.
- **Coordenadas:** solo publicar pares completos dentro de los límites
  geográficos. Los pares inválidos o incompletos pasan a NULL; se conserva el
  registro y se añade `coordinate_status`. Coordenadas obligatorias inválidas
  detienen la construcción. Una geocodificación `geonames_city_only` con países
  contradictorios queda NULL con `coordinate_status='review'`. Se aplica también
  a los informes vinculados que copian exactamente ese par original; otros pares
  distintos se conservan. `coordinate_country_conflict` conserva el par original
  y la evidencia del conflicto. Se evalúa antes de agrupar duplicados.
- **Países:** normalizar nombres y códigos con el catálogo local versionado
  `config/countries.json`, derivado de [UN M49](https://unstats.un.org/unsd/methodology/m49/overview/).
  El código TW se documenta adicionalmente con el catálogo de UNCTAD. Si las
  representaciones discrepan o son históricas/ambiguas, el país canónico queda
  NULL y `country_status` señala revisión. No se adivina un país por una ciudad
  ni se convierte automáticamente un país histórico en su sucesor actual.
- **Tipos y dominios:** validar números, booleanos, rangos, categorías y
  estructura JSON. Los valores no utilizables pasan a NULL y se registran.
  `craft_size_m` conserva las estimaciones como números acompañados de
  `craft_size_status='approximate'`; descripciones sin medida quedan registradas
  como `unquantified`.
- **Duplicados:** confirmar únicamente coincidencias exactas de fecha y hora
  conocidas, coordenadas, forma y todos los descriptores comparados, con al menos
  dos descriptores adicionales informativos. El score de similitud o un
  `source_record_id` repetido no bastan. Se conserva cada informe y se asigna
  como representante el menor `sighting.id` del grupo. Los candidatos sin
  evidencia suficiente permanecen en revisión.

## Tablas y vistas para consumidores

| Objeto | Uso |
|---|---|
| `sighting` y demás tablas originales | Informes limpios, con IDs y filas conservados; pueden contener NULL legítimos y estados de revisión. |
| `event_membership` | Vínculo de cada informe con su evento canónico. |
| `duplicate_group` / `duplicate_resolution` | Grupos confirmados y decisión explicada para cada candidato. |
| `sighting_canonical` | Un representante por evento; consultar el vínculo para todas sus fuentes. |
| `sighting_for_map` | Eventos canónicos con coordenadas utilizables. |
| `sighting_for_time_analysis` | Eventos canónicos con fecha válida; filtrar por precisión según el análisis. |
| `duplicate_review` / `quality_review` | Casos pendientes de evidencia; no se eliminan silenciosamente. |
| `reused_source_key` | Identificadores de fuente reutilizados; no son automáticamente duplicados. |
| `quality_rule` / `quality_issue` | Contrato, gravedad, valor original y tratamiento de cada incidencia. |
| `silver_change` | Valores anterior y nuevo y regla de cada campo original modificado. |
| `silver_run` | Versión, hashes de código, política y catálogo, referencia temporal y procedencia. |

La vista canónica facilita contar eventos sin perder los informes. La agrupación
automática sigue un criterio conservador; no acredita la veracidad del fenómeno
ni resuelve por sí sola las coincidencias que requieren evaluación humana.

## Validación y reproducibilidad

La salida y `ufo.validation.json` no se incluyen en Git. El informe diferencia
la comprobación de la proyección previa a la limpieza de los controles finales.
Registra reglas, incidencias, campos modificados, decisiones de deduplicación,
conteos, esquema, métricas finales y SHA-256. Cada cambio se reconcilia contra
Bronze y su registro de trazabilidad. Se verifican integridad, relaciones,
dominios y cobertura de todos los informes y candidatos.

`--verify-only` vuelve a leer los datos, comprueba los hashes y reconcilia los
cambios sin modificar la base. Si cambian el código, la política o el catálogo,
se requiere reconstruir Silver. La referencia temporal es explícita para que
repetir la transformación no dependa del día de ejecución.

## Revisión pendiente reproducible

```bash
python3 scripts/review_silver.py
```

Verifica la salida y genera `data/silver/ufo.review.json` sin modificar las bases.
Incluye hashes, linaje, SQL ejecutado, conflictos por método de geocodificación,
países no reconocidos y fechas pendientes junto con `date_event_raw` de Bronze.
Para los candidatos ofrece conteos por fuentes, método y primer impedimento
estricto, con un ID de ejemplo. El orden del `CASE` forma parte del contrato de
ese resumen: cada par aparece una vez, aunque puede incumplir varios criterios.
Un impedimento no demuestra que sean eventos distintos. Un
`strict_match_unconfirmed` exige investigar una posible discrepancia del algoritmo.

La revisión de esta iteración y sus límites están documentados en
[docs/silver-review.md](../../docs/silver-review.md). Las coordenadas válidas por
rango no acreditan por sí solas una ubicación correcta; los conflictos de país
sin la evidencia específica de búsqueda solo por ciudad continúan pendientes.
