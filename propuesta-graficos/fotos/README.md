# Capturas de las vistas implementadas

Cada captura muestra el panel de resultados de `/agent` con datos reales de la carga Gold aprobada (`3f1da0ee`), consultados por la API de la app. No se usó `DB Test`. Resolución: 1440×1000.

| Captura | Propuesta | Vista | Issue | Consulta |
| --- | --- | --- | --- | --- |
| [01](01-composicion-por-archivo.png) | Composición por archivo | `stacked` | #80 | Informes por década y fuente desde 1940 |
| [02](02-matriz-pais-decada.png) | Región por año (adaptada a país × década) | `matrix` | #81 | 12 países, décadas desde 1940 |
| [03](03-cambio-entre-periodos.png) | Cambios de composición entre períodos | `dumbbell` | #82 | Formas en los años 70 frente a los 2010 |
| [04](04-cronologia.png) | Cronología | `timeline` | #83 | Informes de EE. UU. del 13 de marzo de 1997 (luces de Phoenix) |
| [06](06-histograma-duracion.png) | Histograma de duración | `histogram` | #53 | Todos los informes; tramos de 5, 10 o 15 min |
| [07](07-duracion-acumulada.png) | Duración acumulada | `ecdf` | #85 | Todos los informes; umbrales de 1, 5, 15 y 60 min |
| [08](08-calendario-ano-mes.png) | Calendario por meses (ya integrado, de referencia) | `month_calendar` | #77 | 1995–2000 |

La comparación de informes (#84) no se incluyó: queda pendiente con un caso de uso más claro.
