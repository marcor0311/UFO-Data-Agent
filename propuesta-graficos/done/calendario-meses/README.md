# Calendario por meses del año

**Estado · Implementada** en el Data Agent como vista `month_calendar` ([#77](https://github.com/marcor0311/UFO-Data-Agent/issues/77)). Además de la matriz, muestra por año los informes cuyo mes no se puede calcular, el total anual y los totales del período.

Matriz año × mes con recuento e IDs seleccionables. Excluye del eje mensual las fechas que solo consignan un año.

## Utilidad para el Data Agent

Reconocer picos puntuales y comparar la cobertura mensual entre años.

## Recursos originales

[fuente-original.txt](fuente-original.txt) contiene el fragmento del renderizador de DB Test. Los [fragmentos analíticos](../../_compartido/js/analitica-uap.fragmentos.txt) y de [presentación](../../_compartido/js/sketchbook-base.fragmentos.txt) aportan preparación de datos, estilos de dibujo y selección.

Referencias archivadas: [D14-interactivo.html-fragment](referencias/D14-interactivo.html-fragment) (fragmento original de revisión), [D14-interactivo.svg](referencias/D14-interactivo.svg) (SVG original), [D14.png](referencias/D14.png) (lámina o revisión original), [D14.svg](referencias/D14.svg) (SVG original), [propuesta-v2.json](referencias/propuesta-v2.json) (ficha original v2 y su prompt).

El [fragmento de exportación](fuente-estatica.original.txt) y los [estilos originales](../../_compartido/estilos-exportacion.original.txt) documentan cómo se produjo la lámina en DB Test.

## Tecnologías y datos

**Tecnologías.** JavaScript/SVG. Lámina en NumPy y Matplotlib.

**Datos.** IDs, año y mes validados y corte de California, 1990–1999. El año se conserva aunque el mes falte. Véanse los [recursos compartidos](../../_compartido/README.md#datos-necesarios).

## Cómo revisar la referencia

Consulta la lámina D14 en `referencias/`. Para revisar las interacciones existentes, abre el [observatorio original](../../../DB%20Test/observatorio.html) y busca **Calendario de meses por año** en **Explorar herramientas**. El recorte y la pregunta del prototipo están en la ficha v2.

## Prompt de ejemplo

> Prepara un calendario de reportes por mes y año para California. Indica cuántos reportes no tienen mes.

## Límites y pendientes

El recuento de celdas describe documentación. Repetición visual y diferencias entre meses no bastan para establecer estacionalidad.
