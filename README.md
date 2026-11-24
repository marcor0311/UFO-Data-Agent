<div align="center">

# UFO Data Agent

### Un siglo de reportes de fenómenos aéreos, en una sola conversación

Un agente conversacional que responde preguntas en lenguaje natural sobre más de 702.000 informes de UAP. Consulta solo datos preparados y verificados, y devuelve cada respuesta con su gráfico, su evidencia y sus límites.

[Galería](docs/images/README.md) — [Certificación](docs/certificacion.md) — [Iniciar localmente](#inicio-rápido) — [Documentación](#documentación)

</div>

<p align="center">
  <img src="docs/images/00-portada.png" alt="Portada del UFO Data Agent" width="100%" />
</p>

## Una pregunta, un gráfico y su evidencia

El agente interpreta la pregunta, elige la consulta tipada sobre la carga Gold aprobada y muestra la visualización que la responde. Cada resultado indica cuántos informes entran, cuáles quedan fuera y por qué.

<p align="center">
  <img src="docs/images/destacada-1-globo-1997.png" alt="Globo 3D con los 3.403 informes de 1997 en 2.052 ubicaciones" width="49%" />
  <img src="docs/images/destacada-2-mapa-3d-japon.png" alt="Mapa 3D de Japón con modelos 3D de las formas" width="49%" />
</p>
<p align="center">
  <img src="docs/images/destacada-3-mapa-2d-reino-unido.png" alt="Mapa 2D con los 22.503 informes del Reino Unido" width="49%" />
  <img src="docs/images/destacada-4-agrupaciones-eeuu.png" alt="Mapa de agrupaciones de informes en la misma semana y zona en Estados Unidos" width="49%" />
</p>
<p align="center">
  <img src="docs/images/destacada-5-formas-por-decada.png" alt="Composición de formas por década desde 1950" width="49%" />
  <img src="docs/images/destacada-6-mes-y-hora.png" alt="Matriz de informes por mes del año y hora del día" width="49%" />
</p>

## Qué puedes explorar

- **Tiempo:** año, década, mes, día, hora y día de la semana, con picos anómalos y cambios interanuales.
- **Geografía:** país, estado o provincia (EE. UU., Canadá y Australia), ciudad de la fuente, mapas de puntos, densidad, coropletas y globo 3D.
- **Descripción:** forma, color, movimiento, sonido, duración y testigos, con distribuciones, cuantiles y dispersión.
- **Proximidad:** distancia a instalaciones nucleares y enlaces entre celdas e instalaciones.
- **Procedencia y calidad:** fuentes, duplicados confirmados y pendientes, cobertura por campo y datos que faltan juntos.
- **Análisis:** 20 análisis tipados, entre ellos cascada, ranking acumulado, concentración, agrupaciones, embudo, UpSet, comparación de informes y K-means.

El agente integra UFOCAT, UPDB, UFO-search y Capella / PhenomAInon. La unidad es el **informe**: documenta lo que alguien declaró, no un hecho verificado. Las puntuaciones de modelo (engaño, calidad, sentimiento) se presentan como salidas de modelos heredados.

## Galería

La [galería completa](docs/images/README.md) reúne 87 capturas tomadas durante la certificación: las 60 preguntas del banco de evaluación y 24 preguntas que recorren todas las vistas y análisis, cada una con la respuesta real del modelo.

<p align="center">
  <img src="docs/images/galeria-datos-faltantes.png" alt="Combinaciones de datos que faltan juntos" width="49%" />
  <img src="docs/images/galeria-ranking-paises.png" alt="Ranking de los diez países con más informes entre 1990 y 2022" width="49%" />
</p>

## Inicio rápido

La demo con datos sintéticos, la carga completa con datos reales, el pipeline Bronze → Silver → Gold y el arranque de la API y la web están en [docs/inicio-rapido.md](docs/inicio-rapido.md).

## Documentación

- [Inicio rápido y operación](docs/inicio-rapido.md)
- Producto y diseño: [PRODUCT.md](PRODUCT.md), [DESIGN.md](DESIGN.md)
- Gold: [contrato](docs/gold-contract.md), [catálogo](docs/GOLD_CATALOG.md), [guía de dominio](docs/gold-domain-guide.md), [verificación](docs/gold-verification.md)
- Agente: [grafo LangGraph](docs/agente-langgraph.md), [preguntas y gráficos](docs/preguntas-y-graficos.md), [certificación](docs/certificacion.md)

## Tecnologías

<p><img src="https://img.shields.io/badge/Python-3776AB?style=flat-square&logo=python&logoColor=white" alt="Python"/> <img src="https://img.shields.io/badge/TypeScript-3178C6?style=flat-square&logo=typescript&logoColor=white" alt="TypeScript"/> <img src="https://img.shields.io/badge/React-20232A?style=flat-square&logo=react&logoColor=61DAFB" alt="React"/> <img src="https://img.shields.io/badge/Next.js-000000?style=flat-square&logo=nextdotjs&logoColor=white" alt="Next.js"/> <img src="https://img.shields.io/badge/Node.js-339933?style=flat-square&logo=nodedotjs&logoColor=white" alt="Node.js"/> <img src="https://img.shields.io/badge/FastAPI-009688?style=flat-square&logo=fastapi&logoColor=white" alt="FastAPI"/> <img src="https://img.shields.io/badge/LangGraph-1C3C3C?style=flat-square&logo=langgraph&logoColor=white" alt="LangGraph"/> <img src="https://img.shields.io/badge/SQLite-003B57?style=flat-square&logo=sqlite&logoColor=white" alt="SQLite"/> <img src="https://img.shields.io/badge/MapLibre-396CB2?style=flat-square&logo=maplibre&logoColor=white" alt="MapLibre"/> <img src="https://img.shields.io/badge/deck.gl-1B1B1B?style=flat-square&logo=uber&logoColor=white" alt="deck.gl"/> <img src="https://img.shields.io/badge/D3.js-F9A03C?style=flat-square&logo=d3&logoColor=white" alt="D3.js"/> <img src="https://img.shields.io/badge/GSAP-0AE448?style=flat-square&logo=greensock&logoColor=black" alt="GSAP"/> <img src="https://img.shields.io/badge/Playwright-2EAD33?style=flat-square&logo=playwright&logoColor=white" alt="Playwright"/> <img src="https://img.shields.io/badge/OpenAI-412991?style=flat-square&logo=openai&logoColor=white" alt="OpenAI"/></p>
