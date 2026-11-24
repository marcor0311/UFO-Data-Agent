# Mapa 2D de clusters

**Estado, Recuperada**

Mapa plano de concentraciones espacio-temporales, con controles de radio y ventana, lista de grupos, registros fuera de grupo e inspector por selección.

## Utilidad para el Data Agent

Examinar concentraciones del archivo y consultar los informes que sostienen cada agrupación.

## Recursos originales

La [capa original M1/M1b](../../_compartido/js/mapa-clusters.fragmentos.txt) comparte el cálculo de membresía, radio y ventana temporal. El [motor](../../_compartido/js/mapas-geograficos.js) y la [lógica espacial](../../_compartido/js/mapas-analiticos.js) aportan las interacciones cartográficas.

Referencias archivadas: [M1-interactivo.html-fragment](referencias/M1-interactivo.html-fragment) (fragmento original de revisión), [M1.png](referencias/M1.png) (lámina o revisión original), [M1.svg](referencias/M1.svg) (SVG original), [propuesta-v2.json](referencias/propuesta-v2.json) (ficha original v2 y su prompt).

El [fragmento de exportación](fuente-estatica.original.txt) y los [estilos originales](../../_compartido/estilos-exportacion.original.txt) documentan cómo se produjo la lámina en DB Test.

## Tecnologías y datos

**Tecnologías.** JavaScript, DBSCAN original, MapLibre GL JS 5.24.0 y deck.gl 9.4.0. La lámina usa NumPy/Matplotlib y contornos GeoJSON.

**Datos.** IDs georreferenciados y fechas con día válido del corte California y entorno, 2004. Radio 25 km, ventana 7 días y mínimo 4 en la configuración inicial. Véanse los [recursos compartidos](../../_compartido/README.md#datos-necesarios).

## Cómo revisar la referencia

Consulta la lámina M1 en `referencias/`. Para revisar las interacciones existentes, abre el [observatorio original](../../../DB%20Test/observatorio.html) y busca **Mapa 2D, Clusters** en **Explorar herramientas**. El recorte y la pregunta del prototipo están en la ficha v2.

## Prompt de ejemplo

> Abre un mapa 2D de concentraciones de reportes en California en 2004, con 25 km y 7 días. Incluye los registros fuera de grupo.

## Límites y pendientes

El zoom no modifica el modelo. Las teselas requieren red y el mapa puede mostrar un mensaje de respaldo. La lámina es una proyección de revisión y sus cifras se obtuvieron con el snapshot estático.
