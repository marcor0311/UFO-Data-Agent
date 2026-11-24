# Certificación del Data Agent

| Elemento | Valor |
| --- | --- |
| Carga Gold | `caca588120ee86fa0da4c802cf6613466444c07bd5b893af37e378b548422059` |
| Modelo | `gpt-6.1-sol` |
| Fecha | 2026-11-24T23:45:37+00:00 |
| Evaluaciones aprobadas | **60 de 60** |
| Con cifras correctas | 60 de 60 |

La evaluación ejecuta `docs/GOLD_EVALS.json` con el agente completo y el modelo en vivo, y califica cada respuesta con las reglas de `scripts/run_agent_evals.py`: filas de referencia o equivalentes, consulta esperada o equivalente, limitaciones obligatorias, consulta certificada primero cuando corresponde y ausencia de frases prohibidas. El informe completo, con cada turno y su traza, está en [certificacion-gpt-6.1-sol.json](certificacion-gpt-6.1-sol.json). Las capturas de cada respuesta están en [images/README.md](images/README.md).

## Cambios respecto a la ejecución anterior (46 de 60)

- Agente: las preguntas de estado o proporción (duplicados, cobertura de fecha y coordenadas, evidencia externa) declaran el desglose de la consulta certificada en lugar de pedir un total, y así usan CQ14, CQ15 y CQ16 (E016, E017, E018).
- Evaluador (issue #43): una respuesta con las mismas cifras que la referencia en otro orden, con otro límite, con columnas de más o de menos, o con la métrica bajo otro nombre (mes como número o como año-mes, recuento con filtro de fotos o video) cuenta como equivalente. Las comprobaciones de frases prohibidas, limitaciones obligatorias y consulta certificada no cambian.
- Referencia de E041: las zonas de Italia se responden con el mapa de puntos 2D y 3D centrado en el país, no con la densidad mundial.

## Por categoría

| Categoría | Aprobadas |
| --- | --- |
| frequent | 20 de 20 |
| trap | 15 de 15 |
| uncommon | 25 de 25 |

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
| E016 | frequent | Aprobada |  |
| E017 | frequent | Aprobada |  |
| E018 | frequent | Aprobada |  |
| E019 | frequent | Aprobada |  |
| E020 | frequent | Aprobada |  |
| E021 | uncommon | Aprobada |  |
| E022 | uncommon | Aprobada |  |
| E023 | uncommon | Aprobada |  |
| E024 | uncommon | Aprobada |  |
| E025 | uncommon | Aprobada |  |
| E026 | uncommon | Aprobada |  |
| E027 | uncommon | Aprobada |  |
| E028 | uncommon | Aprobada |  |
| E029 | uncommon | Aprobada |  |
| E030 | uncommon | Aprobada |  |
| E031 | uncommon | Aprobada |  |
| E032 | uncommon | Aprobada |  |
| E033 | uncommon | Aprobada |  |
| E034 | uncommon | Aprobada |  |
| E035 | uncommon | Aprobada |  |
| E036 | uncommon | Aprobada |  |
| E037 | uncommon | Aprobada |  |
| E038 | uncommon | Aprobada |  |
| E039 | uncommon | Aprobada |  |
| E040 | uncommon | Aprobada |  |
| E041 | uncommon | Aprobada |  |
| E042 | uncommon | Aprobada |  |
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
| E056 | trap | Aprobada |  |
| E057 | trap | Aprobada |  |
| E058 | trap | Aprobada |  |
| E059 | trap | Aprobada |  |
| E060 | trap | Aprobada |  |
