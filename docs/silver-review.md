# Revisión de Silver — 21 de noviembre de 2026

## Alcance y estado inicial

Revisión sobre Bronze v17 y Silver v2, desde `data/silver` en `e48b31d`.
Git estaba limpio y no había instrucciones `AGENTS.md` en el repositorio ni
sus directorios superiores. El PR #5 ya estaba fusionado en `main`, mediante
`512840d5b75f89431f58a7bd4b5788dc6d58b25f`, sin comentarios de revisión.
Esta iteración prepara Silver v3; no diseña Gold.

Los controles conservan el grano de informe, los IDs y las diez tablas de
origen. Las decisiones de país, fechas y duplicados se mantienen separadas:
no se atribuye certeza a un evento por tener campos normalizados.

## Países y coordenadas

Los 3.800 conflictos de país se distribuyen en 3.702 ubicaciones con
`geocode_src='geonames_city_only'`, 94 sin método declarado y cuatro con
`geonames_city_country`. La asociación observada y los ejemplos sugieren
selección de homónimos sin restringir el país; no acreditan qué país original
es el correcto. Ejemplos de Bronze:

| location.id | Texto | country | country_iso2 | Coordenadas |
|---|---|---|---|---|
| 139 | NEW BRUNSWICK | CA | US | 40.48622, -74.45182 |
| 865 | ONTARIO | CA | US | 34.06334, -117.65089 |

**Riesgo alto:** esos pares podían entrar en mapas y en agrupaciones estrictas
por satisfacer únicamente los límites numéricos. La política v3 pone en NULL
los pares completos válidos de las ubicaciones con búsqueda solo por ciudad y
conflicto de país. También pone en NULL las coordenadas de informes vinculados
que coinciden exactamente con el par de Bronze de esa ubicación. El nuevo
estado `coordinate_status='review'` las excluye de mapas y deduplicación antes
de formar grupos. Cada par original queda en `quality_issue`, y cada campo
modificado se reconcilia con Bronze mediante `silver_change`. No se elige un
país ni se introducen coordenadas alternativas. Los pares distintos de los
informes no se presumen derivados de esa geocodificación.

Los 98 conflictos con otros métodos continúan pendientes: no se ha demostrado
que sus coordenadas sean correctas ni se aplica a ellos esta regla específica.
Rango válido no equivale a localización verificada.

Se añade el alias explícito `Netherlands → NL`: los dos registros afectados ya
aportan `country_iso2='NL'`. La referencia versionada y
[UN M49](https://unstats.un.org/unsd/methodology/m49/overview/), consultada el
21 de noviembre de 2026, identifican `Netherlands (Kingdom of the)` con M49 528,
NL y NLD. Se conserva el nombre canónico del catálogo y el valor anterior en
la trazabilidad. Los demás países no reconocidos permanecen pendientes:
condados/ciudades en el campo país, áreas marítimas, fronteras, códigos no
catalogados y entidades históricas no admiten una sustitución general segura.
`USSR`, `French Morocco`, `Korea`, `OC`, `XK` y otros valores no se completan
mediante sucesores, proximidad ni el segundo código por sí solo.

## Fechas

Hay 762 informes con fecha no utilizable; cada uno tiene incidencias separadas
en `date_event` y `sighting_datetime`, por lo que sumar ambas duplica el número
de informes afectados.

| Patrón | Informes | Interpretación y tratamiento |
|---|---:|---|
| UFOCAT: `date_event='19'` | 682 | El texto original incluye `19--` y otras variantes incompletas. No permite establecer un año; permanece NULL. |
| UFOCAT: `0019-…` | 22 | El texto original contiene `19-MM-DD` o `19-MM-`; no permite determinar siglo o año completo. Se conserva como centinela pendiente. |
| UFOCAT: otros años de 1–3 cifras | 56 | Valores como `188`/`188--` y `956`/` 956--` pueden representar truncamientos o fechas antiguas. No se rellenan con ceros ni dígitos inferidos. |
| Capella: `2030-08-02` | 1 | Posterior a la referencia 2026-11-21. El texto original también dice 2030; no acredita otro año. |
| UFO-search: `1949-02-29` | 1 | Día imposible en un año no bisiesto. No existe evidencia para elegir otra fecha. |

**Riesgo medio:** recuperar fechas mediante reglas de longitud o completar
siglos introduciría una precisión y cronología no demostradas. No se cambian
las fechas parciales válidas, horas sin zona ni `date_event_raw`. El diagnóstico
incluye IDs de ejemplo, fuente y texto original para continuar la revisión en
las referencias documentales de origen.

## Pares candidatos

El resumen reproducible evalúa todos los pares originales contra los criterios
estrictos existentes y conserva sus decisiones. Cuenta cada par por su primer
impedimento en un orden explícito: fecha/hora, coordenadas, forma, hora original,
cantidad de descriptores y diferencias entre descriptores. Incluye fuentes,
método y un candidato de ejemplo; las categorías son excluyentes para contar,
aunque un par puede incumplir varios requisitos. No constituye un rechazo del
candidato ni confirma que represente dos eventos diferentes.

El resultado sobre los **243.318 pares** es `datetime_insufficient` en todos
los casos: falta fecha/hora válida con precisión de minuto o superior en al
menos uno de los extremos. Ese primer impedimento basta para impedir la
confirmación estricta. No implica que los demás criterios se cumplan. Las
fuentes tampoco tienen la misma cobertura temporal: todos los 296.956 informes
UPDB solo aportan precisión de día; UFOCAT sí tiene horas, pero eso no permite
atribuirlas a otro informe sin evidencia. La revisión no combina una fecha
parcial de un extremo con la hora del otro.

Los métodos originales incluyen `tier2c_updb_ufocat` (172.226),
`tier2d_ufosearch_ufocat` (31.299), `tier3_desc_fuzzy` (16.989) y tres variantes
`capella_favoured` (22.804 en conjunto). Un score elevado o un identificador de
fuente compartido siguen sin ser evidencia suficiente. Los grupos automáticos
se recalculan después de retirar coordenadas en revisión; no se equiparan con
los pares candidatos originales.

## Reproducción

```bash
python3 -m unittest discover -s tests -q
python3 scripts/build_silver.py --replace
python3 scripts/build_silver.py --verify-only
python3 scripts/review_silver.py
```

`ufo.validation.json` registra los controles y la reconciliación por campo.
`ufo.review.json` conserva consultas SQL, resultados, hashes de ambas bases,
hash del script y linaje. Ambos son salidas generadas excluidas de Git. Las bases
y los informes previos se archivan en `.history/`. La revisión usa conexiones
SQLite de solo lectura y no adjudica registros. Las pruebas nuevas cubren la
cuarentena previa a la agrupación, la conservación de coordenadas distintas,
los países inciertos y la cobertura sin doble conteo de los impedimentos.

## Resultado de la política v3

- 702.572 informes e identificadores conservados; Bronze mantiene tamaño y SHA-256.
- 3.702 ubicaciones y 9.035 informes con pares de coordenadas en revisión;
  ninguno de esos informes aparece en `sighting_for_map`.
- 484.810 informes con pares de coordenadas utilizables, frente a 493.845 antes
  de la cuarentena. La diferencia de 9.035 corresponde exactamente a los pares
  retirados; no se pierden informes.
- Dos países normalizados mediante el alias `Netherlands`; quedan 655 ubicaciones
  y tres encuentros nucleares con países no reconocidos, además de los 3.800
  conflictos de país. La cuarentena no cuenta como resolución de esos conflictos.
- 269.860 cambios por campo reconciliados con Bronze. Frente a 244.388 previos,
  hay 25.474 cambios de coordenadas adicionales y dos cambios de código de país
  que dejan de ser necesarios al conservar `NL`: incremento neto de 25.472.
- Se conservan 6.967 grupos estrictos y 691.600 eventos canónicos. La nueva
  cuarentena no alcanza a los miembros de esos grupos en este corpus.
- Los 243.318 pares candidatos originales siguen con `needs_review`.
- Construcción: 148 controles aprobados. Verificación posterior: 110 controles
  aprobados y 269.860 cambios reconciliados. Suite: 34 pruebas aprobadas.

SHA-256 de Silver v3:
`d7538c0e3ec3bc1a78665692823ad7f5ca9075930e69d3d16a1a63bab11d4f4c`.
