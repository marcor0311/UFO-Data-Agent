# Duración acumulada

**Estado: Implementada** en el Data Agent como vista `ecdf` ([#85](https://github.com/marcor0311/UFO-Data-Agent/issues/85)).

Función de distribución empírica acumulada (ECDF) por duración válida. La vista viva ofrece umbrales seleccionables de 1, 5, 15 y 60 minutos cuando aplican.

## Utilidad para el Data Agent

Responder preguntas de porcentaje hasta un límite sin elegir intervalos de histograma.

## Recursos originales

[fuente-original.txt](fuente-original.txt) contiene el fragmento del renderizador de DB Test. Los [fragmentos analíticos](../../_compartido/js/analitica-uap.fragmentos.txt) y de [presentación](../../_compartido/js/sketchbook-base.fragmentos.txt) aportan preparación de datos, estilos de dibujo y selección.

Referencias archivadas: [D13-interactivo.html-fragment](referencias/D13-interactivo.html-fragment) (fragmento original de revisión), [D13-interactivo.svg](referencias/D13-interactivo.svg) (SVG original), [D13.png](referencias/D13.png) (lámina o revisión original), [D13.svg](referencias/D13.svg) (SVG original), [propuesta-v2.json](referencias/propuesta-v2.json) (ficha original v2 y su prompt).

El [fragmento de exportación](fuente-estatica.original.txt) y los [estilos originales](../../_compartido/estilos-exportacion.original.txt) documentan cómo se produjo la lámina en DB Test.

## Tecnologías y datos

**Tecnologías.** JavaScript/SVG. La lámina utiliza NumPy/Matplotlib.

**Datos.** ID y duración no negativa en minutos, con N válido y faltantes, California 1990–1999. Véanse los [recursos compartidos](../../_compartido/README.md#datos-necesarios).

## Cómo revisar la referencia

Consulta la lámina D13 en `referencias/`. Para revisar las interacciones existentes, abre el [observatorio original](../../../DB%20Test/observatorio.html) y busca **Duración acumulada, ECDF** en **Explorar herramientas**. El recorte y la pregunta del prototipo están en la ficha v2.

## Prompt de ejemplo

> ¿Qué porcentaje de los reportes con duración registrada dura hasta cinco minutos? Muéstrame la curva acumulada, el N y los faltantes.

## Límites y pendientes

La vista viva usa log(1+minutos) y la lámina usa una escala simétrica logarítmica. La selección viva recupera los informes hasta el umbral.
