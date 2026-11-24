# Mapa 3D de clusters

**Estado · Recuperada**

La misma capa de grupos de M1 sobre mapa inclinado a 60°, con terreno y ajuste de posición al cargar teselas. Conserva ruido, IDs, radio y ventana.

## Utilidad para el Data Agent

Inspeccionar la distribución espacial de un conjunto en el contexto regional del relieve.

## Recursos originales

La [capa original M1/M1b](../../_compartido/js/mapa-clusters.fragmentos.txt) comparte el cálculo de membresía, radio y ventana temporal. El [motor](../../_compartido/js/mapas-geograficos.js) y la [lógica espacial](../../_compartido/js/mapas-analiticos.js) aportan las interacciones cartográficas.

Referencias archivadas: [M1b-interactivo.html-fragment](referencias/M1b-interactivo.html-fragment) (fragmento original de revisión), [M1b.png](referencias/M1b.png) (lámina o revisión original), [M1b.svg](referencias/M1b.svg) (SVG original), [propuesta-v2.json](referencias/propuesta-v2.json) (ficha original v2 y su prompt).

El [fragmento de exportación](fuente-estatica.original.txt) y los [estilos originales](../../_compartido/estilos-exportacion.original.txt) documentan cómo se produjo la lámina en DB Test.

## Tecnologías y datos

**Tecnologías.** JavaScript, DBSCAN original, MapLibre GL JS 5.24.0 y deck.gl 9.4.0. Mapzen Terrarium y respaldo Mapterhorn suministran elevación; la lámina usa NumPy/Matplotlib.

**Datos.** El mismo corte de California y entorno, 2004, con IDs, coordenadas y día válido. La configuración inicial coincide con M1. Véanse los [recursos compartidos](../../_compartido/README.md#datos-necesarios).

## Cómo revisar la referencia

Consulta la lámina M1b en `referencias/`. Para revisar las interacciones existentes, abre el [observatorio original](../../../DB%20Test/observatorio.html) y busca **Mapa 3D · Clusters** en **Explorar herramientas**. El recorte y la pregunta del prototipo están en la ficha v2.

## Prompt de ejemplo

> Muestra en 3D los grupos de California de 2004 con radio de 25 km, ventana de 7 días y mínimo 4. Conserva la lista de informes y el ruido.

## Límites y pendientes

El relieve es terreno contemporáneo y no altura o trayectoria de un objeto. La lámina M1b es un boceto de la capa, no una captura 3D. La vista interactiva depende de teselas y WebGL2.
