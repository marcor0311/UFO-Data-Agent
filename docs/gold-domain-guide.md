# Guía de dominio para el agente de UFO-Data-Agent

Esta guía indica al agente cómo interpretar Gold y cómo responder. Va con el
[contrato Gold](gold-contract.md) y el [catálogo generado](GOLD_CATALOG.md). Las
cifras corresponden a la carga Gold construida sobre Silver v6
(`72ada367…a92aa25e`). Cada resultado indica su `load_id`.

## Reglas de trabajo

1. **Nunca escribir SQL.** Usar solo las herramientas: `search_certified`,
   `run_certified`, `query` (contrato tipado), `describe` y `find_entities`.
2. **Buscar primero una consulta certificada.** Si `search_certified` devuelve
   una consulta aplicable y válida, ejecutarla con `run_certified`. Componer
   una consulta solo si ninguna aplica. Indicar siempre si el resultado es
   **certificado** o **compuesto** (`result_type`).
3. **Resolver entidades antes de filtrar.** Países, fuentes, orígenes, formas,
   colores e instalaciones se resuelven con `find_entities`; los filtros usan
   su `id` real (`US`, `UFOCAT`, `hanford-site`…).
4. **Declarar la elegibilidad.** Si la consulta usa año, mes, día, hora, mapa,
   país o proximidad sobre `fact_report`, declarar `eligibility`. El motor
   rechaza la consulta si falta. Los agregados `agg_*` ya la aplican.
5. **Mencionar las limitaciones** que devuelve el resultado, como mínimo las
   marcadas para la consulta certificada (`limitation`).
6. **Ofrecer “ver la consulta”** con `readable_query.texto` y la procedencia
   (`load_id`, fecha del snapshot).

## Glosario

| Término | Significado en Gold |
|---|---|
| **Informe** | Una fila de `fact_report`: un registro de una fuente, con un ID de Bronze. Hay 702.572. Es la unidad de conteo. No es un avistamiento confirmado ni un evento. |
| **Evento** | Solo existe para un **grupo de duplicados confirmado** (`fact_event`): informes con fecha, hora, coordenadas, forma y descriptores idénticos. Hay 6.959 eventos con 17.920 informes. |
| **Representante** | El informe de menor ID de un grupo confirmado (`is_canonical=1`). Los informes sin grupo también son su propio representante. Contarlos aplica una política, no da el número real de eventos. |
| **Candidato pendiente** | Informe que participa en algún par de `duplicate_candidate` sin evidencia suficiente (`needs_review`). Hay 243.318 pares y 311.628 informes con al menos un par. No se sabe si son duplicados o informes distintos. |
| **Coincidencia por revisar** | `has_pending_candidate`: marca de calidad, no un duplicado. El informe cuenta como un informe más; no se resta de ninguna cifra. |
| **Precisión de fecha** | `calendar_precision`: la precisión más fina que es segura (`day`, `month` o `year`). Una fecha puede tener día en la fuente y precisión segura de mes. |
| **Marcador de día** | Día `01`, `15` o fecha `01-01` que algunas fuentes usan cuando desconocen el día; se detecta por exceso estadístico en cada fuente. Esas fechas conservan el año (y el mes si corresponde), pero no entran en análisis por día. |
| **Fecha calificada** | Fecha con “about”, “~”, “or”, “?”, estaciones o fechas de publicación: se conserva en Silver, pero queda fuera del calendario. |
| **Evidencia externa** | Coordenada, país u hora que procede del catálogo fijado de UFO-search y no de Bronze (`uses_external_evidence=1`, 20.751 informes). |
| **Elegibilidad** | Condición mínima de cada análisis: calendario, mes, día, hora, mapa, país o proximidad nuclear. Cada resultado dice cuántos informes quedaron fuera y por qué. |
| **Puntuación de modelo** | `hoax_likelihood`, `quality_score`, sentimientos y emociones heredados del origen. Son salidas de modelos o heurísticas, no hechos. |

## Fuentes, cobertura y sesgos

| Fuente | Qué es | Informes | Años con fecha apta | Cobertura geográfica | Sesgos y huecos conocidos |
|---|---|---:|---|---|---|
| **UFOCAT** | Catálogo académico de CUFOS (UFOCAT 2023). | 320.412 | 34–2023; mediana 1980; pico en 1967 | 68 % de los informes con país son de EE. UU.; después Canadá, Reino Unido y Francia | Incluye 123.304 informes de origen NUFORC, que también aparecen en UPDB. Aporta casi todas las horas (220.918) y la mayoría de las formas. Exceso de días 01 y 15. |
| **UPDB** | Unified Phenomena Database (compilación de Publius a partir de NUFORC, MUFON, UFODNA, Blue Book y otros). | 296.956 | 100–2022; mediana 2010; 76 % desde 1995; pico en 2012 | 80 % de EE. UU. | **No tiene horas ni formas estandarizadas.** Mayor exceso de marcadores de día (01: 2,83×). Superpuesta con UFOCAT por NUFORC. |
| **UFO-search** | Majestic Timeline de Rich Geldreich, compilada de más de 19 fuentes históricas. | 54.751 | 1001–2023; mediana 1967; solo el 8 % desde 1995; pico en 1952 | 56 % de EE. UU.; Francia es la segunda | Sesgo histórico (oleadas de 1952 y 1954). **Sin formas estandarizadas.** Es la única fuente con evidencia externa: 12.529 coordenadas, 1.634 países y 12.640 horas del catálogo original. |
| **Capella** | Corpus PhenomAInon (0toAI LLC), solo campos factuales: archivos gubernamentales (Italia, Reino Unido, Blue Book, Canadá, Brasil), NIDS, BAASS, Skinwalker y pilotos. | 30.453 | 1783–2023; mediana 1988; pico en 2009 | Italia (12.075) por delante de EE. UU. (11.652) | Pocas horas (357). Muchas fechas en texto libre con precisión retirada o calificada. 1.298 días 01 marcados. |

Sesgos generales que el agente debe mencionar cuando apliquen:

- **Geografía:** el 72 % de los informes con país son de Estados Unidos. Un
  ranking de países refleja la cobertura de las fuentes, no la frecuencia real
  del fenómeno ni su población.
- **Época:** la frecuencia por año refleja también cómo se recopilaron los
  informes: UFO-search concentra oleadas históricas (mediana 1967) y UPDB es
  sobre todo reciente (76 % desde 1995).
- **Solapamiento:** NUFORC aparece en UFOCAT y en UPDB; sumar fuentes puede
  contar el mismo relato dos veces; se menciona como sesgo, sin restar informes.
- **Campos parciales:** las formas solo provienen de UFOCAT y Capella, y las
  horas casi solo de UFOCAT y UFO-search.

## Cómo responder las preguntas típicas

| Pregunta | Herramienta y consulta | Cómo redactar |
|---|---|---|
| **¿Cuántos…?** | `CQ01_REPORTS_BY_SOURCE` o `query` con `report_count`. | “Hay X **informes**…”, una sola cifra. Nunca “hubo X avistamientos”. Si preguntan por eventos, usar `CQ13_CONFIRMED_EVENTS` y explicar que solo hay eventos confirmados. |
| **¿Dónde…?** | País: `CQ07`/`CQ08`. Mapa: `CQ10` (densidad 5°) o `query` con `view: points` y `eligibility: ["map"]`. | Decir cuántos informes quedaron fuera del mapa o del país y que no se normaliza por población. Mencionar la evidencia externa si el resultado la cuenta. |
| **¿Cuándo…?** | Año: `CQ02`/`CQ03`. Mes: `CQ04`. Día de la semana y hora: `CQ05`/`CQ06`. Día concreto: `fact_report` con `eligibility: ["day"]`. | Indicar la elegibilidad aplicada y los excluidos (marcadores de día, fechas calificadas). La hora es local y sin zona horaria. |
| **¿Qué formas…?** | `CQ09_TOP_SHAPES`, o `fact_report` agrupando por `shape_code`. | Señalar que la mayoría de los informes no tiene forma y que UPDB y UFO-search no la aportan. |
| **¿Cerca de qué…?** | `CQ11` (bandas de distancia) y `CQ12` (instalaciones más cercanas). | Distancia a un catálogo local de instalaciones; cercanía no implica relación. |
| **¿Cuánto duran / cómo se mueven / qué color?** | `fact_report` agrupando por `duration_bucket`, `movement_type` o `color_family`. | Son clasificaciones de la fuente sobre el texto del testigo. |
| **¿Es un engaño? / ¿Es fiable?** | `report_model_output` con `avg_hoax_likelihood`. | “Según un modelo heredado del origen…”; nunca “es un engaño” ni “es verdadero”. |

## Frases prohibidas

- “Hubo X avistamientos”, “se vieron X ovnis”, “X ovnis reales”. Decir “X informes”.
- “Está comprobado”, “se demuestra”, “prueba que”, “es verdad que”.
- “Eventos únicos”, “sin duplicados hay X eventos”. Decir el número de informes y, si preguntan, los eventos confirmados.
- “Es un engaño”, “es falso”, “es auténtico” a partir de `hoax_likelihood` u otra puntuación.
- “Los ovnis prefieren…”, “aparecen cerca de bases porque…” o cualquier relación causal.
- “En todo el mundo” o “la frecuencia real” cuando el resultado depende de la cobertura de las fuentes.

## Cuándo pedir aclaración

- **Entidad ambigua:** `find_entities` devuelve varias coincidencias exactas
  (`Congo` → CD y CG; `Corea` → KR y KP). Preguntar cuál.
- **Entidad inexistente:** `find_entities` no devuelve nada (p. ej., “Narnia”).
  Decirlo y no sustituirla por otra.
- **“Eventos” o “avistamientos” sin más:** confirmar si se quiere el número de
  informes o los eventos confirmados.
- **Unidad subnacional** (estados, ciudades): Gold no publica regiones ni
  estados. Ofrecer el país o una celda espacial.
- **Período ambiguo** (“los noventa”, “el verano”): proponer el rango de años o
  el mes concreto. Las estaciones dependen del hemisferio y no se convierten.
- **Petición imposible por contrato** (más de 500 filas, SQL libre, sumar
  porcentajes): explicar el límite y proponer un agregado o filtros.
