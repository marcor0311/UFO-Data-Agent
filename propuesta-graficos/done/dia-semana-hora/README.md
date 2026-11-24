# Día de la semana por hora consignada

**Estado, Implementada** en el Data Agent como vista `hour_weekday`.

Matriz de siete días por 24 horas. Usa el día validado y la hora textualmente consignada, con selección por celda.

## Utilidad para el Data Agent

Comparar el patrón de horarios registrados y hacer visibles los requisitos de cobertura de la serie.

## Recursos originales

[fuente-original.txt](fuente-original.txt) contiene el fragmento del renderizador de DB Test. Los [fragmentos analíticos](../../_compartido/js/analitica-uap.fragmentos.txt) y de [presentación](../../_compartido/js/sketchbook-base.fragmentos.txt) aportan preparación de datos, estilos de dibujo y selección.

Referencias archivadas: [D15-interactivo.html-fragment](referencias/D15-interactivo.html-fragment) (fragmento original de revisión), [D15-interactivo.svg](referencias/D15-interactivo.svg) (SVG original), [D15.png](referencias/D15.png) (lámina o revisión original), [D15.svg](referencias/D15.svg) (SVG original), [propuesta-v2.json](referencias/propuesta-v2.json) (ficha original v2 y su prompt).

El [fragmento de exportación](fuente-estatica.original.txt) y los [estilos originales](../../_compartido/estilos-exportacion.original.txt) documentan cómo se produjo la lámina en DB Test.

## Tecnologías y datos

**Tecnologías.** JavaScript/SVG. La lámina usa NumPy y Matplotlib.

**Datos.** IDs, fecha de evento con día válido y hora explícita, California y entorno, 2001–2007. Véanse los [recursos compartidos](../../_compartido/README.md#datos-necesarios).

## Cómo revisar la referencia

Consulta la lámina D15 en `referencias/`. Para revisar las interacciones existentes, abre el [observatorio original](../../../DB%20Test/observatorio.html) y busca **Día de la semana × hora consignada** en **Explorar herramientas**. El recorte y la pregunta del prototipo están en la ficha v2.

## Prompt de ejemplo

> Agrupa los reportes por día de la semana y hora consignada. Indica cómo manejaste los registros sin hora y las zonas desconocidas.

## Límites y pendientes

No convierte zonas horarias. La medianoche puede contener un valor por defecto. La lámina inicia en lunes y la vista viva en domingo.
