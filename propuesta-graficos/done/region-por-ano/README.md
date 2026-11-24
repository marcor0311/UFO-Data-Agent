# Región por año

**Estado, Implementada** en el Data Agent como vista `matrix` ([#81](https://github.com/marcor0311/UFO-Data-Agent/issues/81), adaptada a país × década). Captura: [fotos/](../../fotos/).

Matriz de conteos de California y Nevada por año, con celdas que seleccionan los IDs de cada par. Continúa la matriz estática v1.

## Utilidad para el Data Agent

Comparar el momento en que crece o cae la cobertura por región y revisar qué reportes explican cada celda.

## Recursos originales

[fuente-original.txt](fuente-original.txt) contiene el fragmento del renderizador de DB Test. Los [fragmentos analíticos](../../_compartido/js/analitica-uap.fragmentos.txt) y de [presentación](../../_compartido/js/sketchbook-base.fragmentos.txt) aportan preparación de datos, estilos de dibujo y selección.

Referencias archivadas: [D6-interactivo.html-fragment](referencias/D6-interactivo.html-fragment) (fragmento original de revisión), [D6-interactivo.svg](referencias/D6-interactivo.svg) (SVG original), [D6.png](referencias/D6.png) (lámina o revisión original), [D6.svg](referencias/D6.svg) (SVG original), [propuesta-v1.json](referencias/propuesta-v1.json) (ficha original v1), [propuesta-v2.json](referencias/propuesta-v2.json) (ficha original v2 y su prompt).

[fuente-estatica-v1.js](fuente-estatica-v1.js) conserva `matrix()` y las utilidades del generador v1.

## Tecnologías y datos

**Tecnologías.** JavaScript y SVG. Se conserva el fragmento `matrix()` del generador v1 como fuente de la lámina original.

**Datos.** IDs, año válido y región de California o Nevada en `historic` (1990–1999). Véanse los [recursos compartidos](../../_compartido/README.md#datos-necesarios).

## Cómo revisar la referencia

Consulta la lámina D6 en `referencias/`. Para revisar las interacciones existentes, abre el [observatorio original](../../../DB%20Test/observatorio.html) y busca **Región × año** en **Explorar herramientas**. El recorte y la pregunta del prototipo están en la ficha v2.

## Prompt de ejemplo

> Compara California y Nevada año por año entre 1990 y 1999. Deja abrir los reportes asociados a cada celda.

## Límites y pendientes

La vista viva muestra conteos. La normalización porcentual mencionada en la ficha de diseño v1 queda pendiente, y California/Nevada pertenecen al recorte del prototipo.
