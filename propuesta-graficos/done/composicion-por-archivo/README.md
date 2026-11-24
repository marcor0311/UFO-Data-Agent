# Composición por archivo

**Estado, Implementada** en el Data Agent como vista `stacked` ([#80](https://github.com/marcor0311/UFO-Data-Agent/issues/80)). Captura: [fotos/](../../fotos/).

Barras apiladas al 100% por año y fuente. Cada tramo puede abrir los informes y conserva los conteos detrás del porcentaje.

## Utilidad para el Data Agent

Separar un cambio de mezcla de procedencias de un cambio en el volumen de reportes.

## Recursos originales

[fuente-original.txt](fuente-original.txt) contiene el fragmento del renderizador de DB Test. Los [fragmentos analíticos](../../_compartido/js/analitica-uap.fragmentos.txt) y de [presentación](../../_compartido/js/sketchbook-base.fragmentos.txt) aportan preparación de datos, estilos de dibujo y selección.

Referencias archivadas: [D16-interactivo.html-fragment](referencias/D16-interactivo.html-fragment) (fragmento original de revisión), [D16-interactivo.svg](referencias/D16-interactivo.svg) (SVG original), [D16.png](referencias/D16.png) (lámina o revisión original), [D16.svg](referencias/D16.svg) (SVG original), [propuesta-v2.json](referencias/propuesta-v2.json) (ficha original v2 y su prompt).

El [fragmento de exportación](fuente-estatica.original.txt) y los [estilos originales](../../_compartido/estilos-exportacion.original.txt) documentan cómo se produjo la lámina en DB Test.

## Tecnologías y datos

**Tecnologías.** JavaScript/SVG. La lámina estática utiliza NumPy/Matplotlib.

**Datos.** IDs, año, `database_name` y totales por año del corte California 1990–1999. Véanse los [recursos compartidos](../../_compartido/README.md#datos-necesarios).

## Cómo revisar la referencia

Consulta la lámina D16 en `referencias/`. Para revisar las interacciones existentes, abre el [observatorio original](../../../DB%20Test/observatorio.html) y busca **Composición del archivo por fuente** en **Explorar herramientas**. El recorte y la pregunta del prototipo están en la ficha v2.

## Prompt de ejemplo

> Compara la participación de cada archivo por año en California durante los noventa. Incluye los conteos al examinar cada porcentaje.

## Límites y pendientes

El denominador es el total de filas del año en el recorte. Puede haber solapamiento entre fuentes y el porcentaje no mide exhaustividad.
