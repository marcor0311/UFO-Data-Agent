# Histograma de duración

**Estado · Implementada** en el Data Agent como vista `histogram` ([#53](https://github.com/marcor0311/UFO-Data-Agent/issues/53)). Captura: [fotos/](../../fotos/).

Histograma de intervalos iguales de 5, 10 o 15 minutos hasta 60. La cola superior y los registros sin duración tienen acceso separado. El núcleo compartido conserva también la alternativa con intervalos en escala logarítmica.

## Utilidad para el Data Agent

Entender la distribución y la asimetría de duración sin ocultar valores extremos ni imputar faltantes.

## Recursos originales

[fuente-original.txt](fuente-original.txt) contiene el fragmento del renderizador de DB Test. Los [fragmentos analíticos](../../_compartido/js/analitica-uap.fragmentos.txt) y de [presentación](../../_compartido/js/sketchbook-base.fragmentos.txt) aportan preparación de datos, estilos de dibujo y selección.

Referencias archivadas: [D3-interactivo.html-fragment](referencias/D3-interactivo.html-fragment) (fragmento original de revisión), [D3-interactivo.svg](referencias/D3-interactivo.svg) (SVG original), [D3.png](referencias/D3.png) (lámina o revisión original), [D3.svg](referencias/D3.svg) (SVG original), [propuesta-v1.json](referencias/propuesta-v1.json) (ficha original v1), [propuesta-v2.json](referencias/propuesta-v2.json) (ficha original v2 y su prompt).

El [fragmento de exportación](fuente-estatica.original.txt) y los [estilos originales](../../_compartido/estilos-exportacion.original.txt) documentan cómo se produjo la lámina en DB Test.

## Tecnologías y datos

**Tecnologías.** JavaScript y SVG. La lámina se exporta con NumPy y Matplotlib.

**Datos.** Duraciones no negativas en segundos convertidas a minutos, IDs y metadatos de California 1990–1999. Véanse los [recursos compartidos](../../_compartido/README.md#datos-necesarios).

## Cómo revisar la referencia

Consulta la lámina D3 en `referencias/`. Para revisar las interacciones existentes, abre el [observatorio original](../../../DB%20Test/observatorio.html) y busca **Duración · histograma** en **Explorar herramientas**. El recorte y la pregunta del prototipo están en la ficha v2.

## Prompt de ejemplo

> Grafica las duraciones reportadas en intervalos de cinco minutos. Muestra cuántas superan una hora y cuántas no tienen duración.

## Límites y pendientes

Una duración asentada puede ser aproximada. El panel principal de D3 termina en 60 minutos y documenta la cola por separado.
