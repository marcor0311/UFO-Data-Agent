# Certificación del Data Agent

| Elemento | Valor |
| --- | --- |
| Carga Gold | `caca588120ee86fa0da4c802cf6613466444c07bd5b893af37e378b548422059` |
| Modelo | `gpt-6.1-sol` |
| Fecha | 2026-11-24T23:03:55+00:00 |
| Evaluaciones aprobadas | **46 de 60** |
| Con cifras correctas | 54 de 60 |

La evaluación ejecuta `docs/GOLD_EVALS.json` con el agente completo y el modelo en vivo, y califica cada respuesta con las reglas de `scripts/run_agent_evals.py`: filas de referencia, consulta esperada o equivalente, limitaciones obligatorias, consulta certificada primero cuando corresponde y ausencia de frases prohibidas. El informe completo está en [certificacion-gpt-6.1-sol.json](certificacion-gpt-6.1-sol.json).

## Correcciones tras la revisión

Después de la evaluación se corrigieron cuatro problemas visibles en la galería, y E041 y G24 se volvieron a preguntar con el mismo modelo (sus capturas muestran la respuesta nueva; la nota de arriba corresponde a la ejecución original):

- Las zonas dentro de un país usan el mapa de puntos 2D y 3D centrado en ese país, no la densidad mundial (E041).
- El globo admite filtros, como el año (G24).
- El mapa muestra un solo mundo, sin países repetidos, y se encuadra en el grueso de los informes; la densidad también se acerca cuando la selección es regional.
- La composición con «Otras» ya no repite la categoría (G20).

## Por categoría

| Categoría | Aprobadas |
| --- | --- |
| frequent | 17 de 20 |
| trap | 14 de 15 |
| uncommon | 15 de 25 |

## Lectura

Ninguna respuesta falló por frases prohibidas, errores de ejecución ni conducta ante preguntas trampa salvo E056. Las 14 no aprobadas fallan las mismas dos comprobaciones estrictas: las filas no coinciden exactamente con la referencia y la consulta no es la esperada ni equivalente. En 8 de ellas las cifras sí son correctas, pero con otra forma (otro orden, otro límite o columnas de más), por eso 54 de 60 respuestas tienen las cifras correctas. Las otras 6 eligen una agrupación o un filtro distinto al de la referencia. El issue #43 sigue abierto para afinar el evaluador.

## Por pregunta

| ID | Categoría | Resultado | Comprobaciones que fallaron |
| --- | --- | --- | --- |
| E001 | frequent | Aprobada |  |
| E002 | frequent | Aprobada |  |
| E003 | frequent | Aprobada |  |
| E004 | frequent | Aprobada |  |
| E005 | frequent | Aprobada |  |
| E006 | frequent | Aprobada |  |
| E007 | frequent | Aprobada |  |
| E008 | frequent | Aprobada |  |
| E009 | frequent | Aprobada |  |
| E010 | frequent | Aprobada |  |
| E011 | frequent | Aprobada |  |
| E012 | frequent | Aprobada |  |
| E013 | frequent | Aprobada |  |
| E014 | frequent | Aprobada |  |
| E015 | frequent | Aprobada |  |
| E016 | frequent | No aprobada | `reference_rows`, `used_certified`, `expected_query_or_equivalent` |
| E017 | frequent | No aprobada | `reference_rows`, `used_certified`, `expected_query_or_equivalent` |
| E018 | frequent | No aprobada | `reference_rows`, `used_certified`, `expected_query_or_equivalent` |
| E019 | frequent | Aprobada |  |
| E020 | frequent | Aprobada |  |
| E021 | uncommon | Aprobada |  |
| E022 | uncommon | Aprobada |  |
| E023 | uncommon | No aprobada | `reference_rows`, `expected_query_or_equivalent` |
| E024 | uncommon | Aprobada |  |
| E025 | uncommon | No aprobada | `reference_rows`, `expected_query_or_equivalent` |
| E026 | uncommon | No aprobada | `reference_rows`, `expected_query_or_equivalent` |
| E027 | uncommon | Aprobada |  |
| E028 | uncommon | Aprobada |  |
| E029 | uncommon | No aprobada | `reference_rows`, `expected_query_or_equivalent` |
| E030 | uncommon | Aprobada |  |
| E031 | uncommon | No aprobada | `reference_rows`, `expected_query_or_equivalent` |
| E032 | uncommon | Aprobada |  |
| E033 | uncommon | Aprobada |  |
| E034 | uncommon | No aprobada | `reference_rows`, `expected_query_or_equivalent` |
| E035 | uncommon | No aprobada | `reference_rows`, `expected_query_or_equivalent` |
| E036 | uncommon | Aprobada |  |
| E037 | uncommon | Aprobada |  |
| E038 | uncommon | No aprobada | `reference_rows`, `expected_query_or_equivalent` |
| E039 | uncommon | Aprobada |  |
| E040 | uncommon | Aprobada |  |
| E041 | uncommon | No aprobada | `reference_rows`, `expected_query_or_equivalent` |
| E042 | uncommon | No aprobada | `reference_rows`, `expected_query_or_equivalent` |
| E043 | uncommon | Aprobada |  |
| E044 | uncommon | Aprobada |  |
| E045 | uncommon | Aprobada |  |
| E046 | trap | Aprobada |  |
| E047 | trap | Aprobada |  |
| E048 | trap | Aprobada |  |
| E049 | trap | Aprobada |  |
| E050 | trap | Aprobada |  |
| E051 | trap | Aprobada |  |
| E052 | trap | Aprobada |  |
| E053 | trap | Aprobada |  |
| E054 | trap | Aprobada |  |
| E055 | trap | Aprobada |  |
| E056 | trap | No aprobada | `reference_rows`, `expected_query_or_equivalent` |
| E057 | trap | Aprobada |  |
| E058 | trap | Aprobada |  |
| E059 | trap | Aprobada |  |
| E060 | trap | Aprobada |  |
