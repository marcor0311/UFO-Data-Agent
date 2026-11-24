# Mapa 3D de duración por forma

**Estado: Implementada** en el Data Agent: cajas de duración por forma con `boxplot` y `median_duration_min`, mapa de la mediana por celda con `density` filtrando una forma, y modelos 3D por forma en `points`.

Propuesta de combinar cartografía con relieve y una comparación de las duraciones por forma normalizada. Se recuperó el diagrama de cajas D4 como referencia cuantitativa y los componentes originales de terreno, símbolos y selección.

## Utilidad para el Data Agent

Inspeccionar si las duraciones reportadas y sus faltantes cambian entre formas dentro de una región, con una forma de volver a los informes originales.

## Recursos originales

[fuente-original.txt](fuente-original.txt) conserva `boxes()`, el renderizador de D4. [respaldo-terreno.js](respaldo-terreno.js) conserva el relieve regional anterior. El [motor cartográfico](../../_compartido/js/mapas-geograficos.js) y las [mallas de formas](../../_compartido/js/mapas-analiticos.js) se reutilizan por separado. [PROMPTS.md](PROMPTS.md) documenta qué quedaría por ensamblar.

Referencias archivadas: [D4-interactivo.html-fragment](referencias/D4-interactivo.html-fragment) (fragmento original de revisión), [D4-interactivo.svg](referencias/D4-interactivo.svg) (SVG original), [D4.png](referencias/D4.png) (lámina o revisión original), [D4.svg](referencias/D4.svg) (SVG original), [propuesta-v1.json](referencias/propuesta-v1.json) (ficha original v1), [propuesta-v2.json](referencias/propuesta-v2.json) (ficha original v2 y su prompt), [region-dem.json](referencias/region-dem.json) (grilla original de elevaciones).

## Tecnologías y datos

**Tecnologías.** Diagrama D4 en JavaScript/SVG. El componente cartográfico reutilizable usa MapLibre GL JS 5.24.0, deck.gl 9.4.0 y WebGL2, con terreno Mapzen Terrarium y respaldo Mapterhorn.

**Datos.** ID, coordenadas válidas, forma normalizada, duración original en segundos, fecha y procedencia. D4 usa California 1990–1999 y conserva las exclusiones por duración. Véanse los [recursos compartidos](../../_compartido/README.md#datos-necesarios).

## Cómo revisar la referencia

En el [observatorio original](../../../DB%20Test/observatorio.html), busca **Duración por forma** para consultar D4. El motor de relieve se puede revisar por separado en [Mapa 3D de clusters](../mapa-3d-clusters/).

## Prompt de ejemplo

> En California entre 1990 y 1999, abre un mapa 3D con relieve para comparar duración reportada por forma. Muestra la misma selección en cajas, incluye N y faltantes y deja abrir cada reporte por su ID.

## Límites y pendientes

No se localizó una implementación original que combine el mapa 3D con la duración por forma. Se conservan las piezas y los prompts para evaluarla posteriormente.
