# Mapas 2D

**Estado, Recuperada**

Mapa detallado por puntos con controles de movimiento, rectángulo y lazo, búsqueda, lista paginada y ficha. Conserva el encuadre y los IDs de la selección. Incluye el respaldo regional Canvas como fuente para el host original.

## Utilidad para el Data Agent

Explorar la ubicación de un conjunto de reportes y trasladar a una tabla los IDs seleccionados.

## Recursos originales

[respaldo-canvas.js](respaldo-canvas.js) recoge el respaldo Canvas del mapa general. El [motor original](../../_compartido/js/mapas-geograficos.js) y sus [estilos](../../_compartido/css/mapa-geografico.css) aportan cartografía, navegación y selección. [mapas-analiticos.js](../../_compartido/js/mapas-analiticos.js) aporta geometría, filtros y prompts.

Referencias archivadas: [map.png](referencias/map.png) (lámina o revisión original), [western-us-nasa.jpg](referencias/western-us-nasa.jpg) (textura NASA del respaldo regional).

## Tecnologías y datos

**Tecnologías.** MapLibre GL JS 5.24.0, deck.gl 9.4.0, WebGL2 y worker clásico incorporado. El respaldo usa Canvas 2D y la textura regional NASA.

**Datos.** IDs, coordenadas válidas, forma, fecha y procedencia. La muestra general original se documenta en `assets/analitica/cohortes.json`. Véanse los [recursos compartidos](../../_compartido/README.md#datos-necesarios).

## Cómo revisar la referencia

En el [observatorio original](../../../DB%20Test/observatorio.html), elige **Mapa 2D**. Los controles propios del mapa permiten encuadrar, seleccionar y abrir reportes.

## Prompt de ejemplo

> Muéstrame en un mapa 2D los reportes de California y Nevada entre 1990 y 1999. Deja seleccionar un área y consultar sus informes por ID.

## Límites y pendientes

Los mapas detallados usan teselas públicas. El respaldo Canvas conserva la fuente y textura de la vista regional anterior. Las coordenadas pueden representar localidades aproximadas.
