# Product

## Plataforma

Web, solo portátil y escritorio.

## Propósito

Explorar informes sobre fenómenos aéreos no identificados (UAP) con preguntas en
lenguaje natural. La portada “Archivo UAP” ocupa `/` y lleva a la primera
pregunta. La conversación, con visualizaciones y evidencia, vive en `/agent`.
La interfaz y sus contenidos están en español.

## Contexto de uso

La portada presenta el archivo con fotografías, una cifra destacada, una
demostración de California 1990 y un acceso al agente. En `/agent`, la
conversación ocupa una columna y los resultados el resto de la pantalla. Los
ejemplos públicos se abren mediante enlaces directos, sin sesión. Para la
conversación hace falta iniciar sesión con ChatGPT, y se puede elegir el modelo
en cada pregunta.

## Capacidades y restricciones

Solo portátil: validar a 1440×800, 1440×1000 y 1920×1080 (ver
[apps/web/AGENTS.md](apps/web/AGENTS.md)). Mantener la lectura accesible, el
zoom y el movimiento reducido. Los respaldos de redistribución no amplían el
alcance a móvil.

Next.js y TypeScript sirven la interfaz. FastAPI y Python ejecutan el agente
como un grafo LangGraph ([docs/agente-langgraph.md](docs/agente-langgraph.md))
que combina Responses, herramientas tipadas sobre Gold y una verificación final. El modelo nunca escribe
SQL: resuelve entidades con `find_entities`, busca una consulta certificada que
cubra toda la pregunta (`search_certified` / `run_certified`) y, si no la hay,
construye una `query_gold` validada. El agente admite 10 vueltas del modelo por
turno, 2 más por cada visualización producida (hasta 18), y al agotarlas
responde con lo que ya tiene.

Gold integra UFOCAT, UPDB, UFO-search y Capella / PhenomAInon. La unidad es el
**informe**, no el avistamiento ni el evento. Solo los grupos de duplicados
confirmados forman eventos. Las puntuaciones de modelo (engaño, calidad,
sentimiento) se presentan como salidas de modelos heredados, nunca como hechos.
La geografía llega a país, celda o coordenadas según la elegibilidad de cada
informe. Para EE. UU., Canadá y Australia, Gold incluye además estado o
provincia; en el resto de países las fuentes no traen una subdivisión
utilizable. La ciudad es el texto de la fuente, sin geocodificar.

## Evidencia disponible

`scripts/build_all.py` construye Bronze → Silver → Gold y promueve cada capa en
`data/releases.sqlite3` solo después de pasar sus controles. La API sirve la
carga Gold aprobada y `/api/health` expone su `load_id`. Catálogos, consultas
certificadas, correcciones y evaluaciones están en `config/gold/` y `docs/`.
Cada resultado lleva su consulta, la carga de origen, las exclusiones por
elegibilidad y las limitaciones que lo afectan.

## Principios de producto

- Una sola cifra por pregunta, con su unidad: “X informes”. Sin rangos.
- La visualización es la respuesta principal. El texto aporta el hallazgo, una
  o dos lecturas y la limitación relevante.
- Las cifras, los gráficos y los totales derivan de la misma consulta. Solo se
  vinculan cuando comparten el mismo alcance.
- Decir a qué población corresponden las exclusiones (sin año, sin
  coordenadas, sin país).
- Pedir aclaración ante nombres ambiguos, entidades inexistentes, períodos
  vagos o niveles geográficos que Gold no tiene.
- Conservar los resultados anteriores mientras carga una consulta o cuando
  falla. El historial es recuperable y mantiene la selección.
- No afirmar que un informe sea auténtico, falso o un engaño, ni que una
  proximidad implique una relación.

## Dirección confirmada

Portada oscura de archivo, con titulares condensados y fotografía. Espacio
analítico claro, sobrio y centrado en la evidencia, con paletas de datos
accesibles. [DESIGN.md](DESIGN.md) define las reglas visuales de ambas rutas.

## Decisiones abiertas

Ver los issues abiertos: mapa 2D/3D en las respuestas, histograma de
duración, exploración de un año desde una serie, cambios de filtro durante la
conversación, salida ante fallos del chat, línea base del evaluador y CI de API
y web.
