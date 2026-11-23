# Cambios de composición entre períodos

**Estado · Experimental**

Gráfico de puntos unidos que compara las proporciones de cada forma en dos períodos del recorte. La vista viva corta en el año medio.

## Utilidad para el Data Agent

Detectar categorías que aparecen con mayor o menor frecuencia relativa y revisar la población de ambos intervalos.

## Recursos originales

[fuente-original.txt](fuente-original.txt) contiene el fragmento del renderizador de DB Test. Los [fragmentos analíticos](../_compartido/js/analitica-uap.fragmentos.txt) y de [presentación](../_compartido/js/sketchbook-base.fragmentos.txt) aportan preparación de datos, estilos de dibujo y selección.

Referencias archivadas: [D12-interactivo.html-fragment](referencias/D12-interactivo.html-fragment) (fragmento original de revisión), [D12-interactivo.svg](referencias/D12-interactivo.svg) (SVG original), [D12.png](referencias/D12.png) (lámina o revisión original), [D12.svg](referencias/D12.svg) (SVG original), [propuesta-v2.json](referencias/propuesta-v2.json) (ficha original v2 y su prompt).

El [fragmento de exportación](fuente-estatica.original.txt) y los [estilos originales](../_compartido/estilos-exportacion.original.txt) documentan cómo se produjo la lámina en DB Test.

## Tecnologías y datos

**Tecnologías.** JavaScript/SVG. Lámina de California 1990–1994 frente a 1995–1999 con NumPy/Matplotlib.

**Datos.** Año con fecha validada, forma normalizada e ID, California 1990–1999. Véanse los [recursos compartidos](../_compartido/README.md#datos-necesarios).

## Cómo revisar la referencia

Consulta la lámina D12 en `referencias/`. Para revisar las interacciones existentes, abre el [observatorio original](../../DB%20Test/observatorio.html) y busca **Cambios de composición entre períodos** en **Explorar herramientas**. El recorte y la pregunta del prototipo están en la ficha v2.

## Prompt de ejemplo

> Compara la proporción de formas entre 1990–1994 y 1995–1999. Muestra los N de ambos tramos y las diferencias en puntos porcentuales.

## Límites y pendientes

La vista viva toma hasta doce formas y la lámina toma siete. La selección de dos intervalos arbitrarios mencionada en el diseño queda pendiente.
