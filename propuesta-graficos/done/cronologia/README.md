# Cronología

**Estado: Implementada** en el Data Agent como vista `timeline` ([#83](https://github.com/marcor0311/UFO-Data-Agent/issues/83)).

Secuencia paginada de ocho tarjetas alternadas con fecha, localidad, forma e ID. Solo entra una fecha con precisión diaria; las marcas abren el inspector.

## Utilidad para el Data Agent

Reconstruir el orden documental de un corte y recuperar fichas concretas sin simular distancias temporales.

## Recursos originales

[fuente-original.txt](fuente-original.txt) contiene el fragmento del renderizador de DB Test. Los [fragmentos analíticos](../../_compartido/js/analitica-uap.fragmentos.txt) y de [presentación](../../_compartido/js/sketchbook-base.fragmentos.txt) aportan preparación de datos, estilos de dibujo y selección.

Referencias archivadas: [D9-interactivo.html-fragment](referencias/D9-interactivo.html-fragment) (fragmento original de revisión), [D9-interactivo.svg](referencias/D9-interactivo.svg) (SVG original), [D9.png](referencias/D9.png) (lámina o revisión original), [D9.svg](referencias/D9.svg) (SVG original), [propuesta-v1.json](referencias/propuesta-v1.json) (ficha original v1), [propuesta-v2.json](referencias/propuesta-v2.json) (ficha original v2 y su prompt).

El [fragmento de exportación](fuente-estatica.original.txt) y los [estilos originales](../../_compartido/estilos-exportacion.original.txt) documentan cómo se produjo la lámina en DB Test.

## Tecnologías y datos

**Tecnologías.** JavaScript/SVG. Lámina de seis fichas en NumPy/Matplotlib.

**Datos.** IDs, fechas de evento válidas con día, localidad y forma del corte de California, 1995. Véanse los [recursos compartidos](../../_compartido/README.md#datos-necesarios).

## Cómo revisar la referencia

Consulta la lámina D9 en `referencias/`. Para revisar las interacciones existentes, abre el [observatorio original](../../../DB%20Test/observatorio.html) y busca **Cronología de registros** en **Explorar herramientas**. El recorte y la pregunta del prototipo están en la ficha v2.

## Prompt de ejemplo

> Muéstrame una cronología de California en 1995. Mantén visible la fecha y el ID y contabiliza fechas parciales por separado.

## Límites y pendientes

La separación visual entre tarjetas es uniforme. Falta evaluar un eje que represente el tiempo transcurrido y decidir cómo integrar el archivo de fechas parciales.
