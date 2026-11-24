# Duración de testigos

**Estado: Implementada** en el Data Agent como vista `scatter` con `measure: duration_witnesses` (dispersión agregada en escalas logarítmicas). Los testigos también se agrupan por `witness_band`.

Dispersión de duración reportada y número de testigos. Los pares de valores idénticos se dibujan juntos y permiten abrir las filas mediante un punto o un rectángulo.

## Utilidad para el Data Agent

Examinar la relación de dos variables registradas, el tamaño de su intersección y posibles patrones de cobertura.

## Recursos originales

[fuente-original.txt](fuente-original.txt) contiene el fragmento del renderizador de DB Test. Los [fragmentos analíticos](../../_compartido/js/analitica-uap.fragmentos.txt) y de [presentación](../../_compartido/js/sketchbook-base.fragmentos.txt) aportan preparación de datos, estilos de dibujo y selección.

Referencias archivadas: [D17-interactivo.html-fragment](referencias/D17-interactivo.html-fragment) (fragmento original de revisión), [D17-interactivo.svg](referencias/D17-interactivo.svg) (SVG original), [D17.png](referencias/D17.png) (lámina o revisión original), [D17.svg](referencias/D17.svg) (SVG original), [propuesta-v2.json](referencias/propuesta-v2.json) (ficha original v2 y su prompt).

El [fragmento de exportación](fuente-estatica.original.txt) y los [estilos originales](../../_compartido/estilos-exportacion.original.txt) documentan cómo se produjo la lámina en DB Test.

## Tecnologías y datos

**Tecnologías.** JavaScript/SVG. D17 usa `scatter` con `variable: 'witnesses'`; la lámina usa NumPy/Matplotlib.

**Datos.** IDs, duración y número de testigos no negativos en la intersección válida, California y entorno 2001–2007. Véanse los [recursos compartidos](../../_compartido/README.md#datos-necesarios).

## Cómo revisar la referencia

Consulta la lámina D17 en `referencias/`. Para revisar las interacciones existentes, abre el [observatorio original](../../../DB%20Test/observatorio.html) y busca **Duración × testigos** en **Explorar herramientas**. El recorte y la pregunta del prototipo están en la ficha v2.

## Prompt de ejemplo

> Compara duración reportada y número de testigos en California y su entorno entre 2001 y 2007. Agrupa valores idénticos e indica cuántos reportes quedaron fuera por faltantes.

## Límites y pendientes

Los dos ejes llevan una transformación y la cobertura de testigos es escasa. La vista viva permite cambiar a completitud; el resultado de D17 ordinario usa testigos. Debe evaluarse en qué recortes aporta señal interpretable.
