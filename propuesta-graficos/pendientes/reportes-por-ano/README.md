# Reportes por año

**Estado, Recuperada**

Barras con eje desde cero y selección de un año para inspeccionar sus reportes. Se recuperó D1 y la variante temporal compartida que admite año, mes y series por fuente.

## Utilidad para el Data Agent

Dar una entrada al volumen y la cobertura temporal del archivo antes de filtrar por período.

## Recursos originales

[fuente-original.txt](fuente-original.txt) contiene el fragmento del renderizador de DB Test. Los [fragmentos analíticos](../../_compartido/js/analitica-uap.fragmentos.txt) y de [presentación](../../_compartido/js/sketchbook-base.fragmentos.txt) aportan preparación de datos, estilos de dibujo y selección.

Referencias archivadas: [D1-interactivo.html-fragment](referencias/D1-interactivo.html-fragment) (fragmento original de revisión), [D1-interactivo.svg](referencias/D1-interactivo.svg) (SVG original), [D1.png](referencias/D1.png) (lámina o revisión original), [D1.svg](referencias/D1.svg) (SVG original), [propuesta-v1.json](referencias/propuesta-v1.json) (ficha original v1), [propuesta-v2.json](referencias/propuesta-v2.json) (ficha original v2 y su prompt).

El [fragmento de exportación](fuente-estatica.original.txt) y los [estilos originales](../../_compartido/estilos-exportacion.original.txt) documentan cómo se produjo la lámina en DB Test.

## Tecnologías y datos

**Tecnologías.** JavaScript y SVG. La lámina D1 se puede regenerar con NumPy y Matplotlib.

**Datos.** Los IDs y la fecha de evento validada para California 1990–1999. Granularidad mes solo para registros con ese dato. Véanse los [recursos compartidos](../../_compartido/README.md#datos-necesarios).

## Cómo revisar la referencia

Consulta la lámina D1 en `referencias/`. Para revisar las interacciones existentes, abre el [observatorio original](../../../DB%20Test/observatorio.html) y busca **Reportes por año** en **Explorar herramientas**. El recorte y la pregunta del prototipo están en la ficha v2.

## Prompt de ejemplo

> Cuenta los reportes de California por año entre 1990 y 1999 y deja abrir los registros detrás de cada barra.

## Límites y pendientes

Cuenta filas del archivo sin deduplicación. El volumen puede cambiar con la cobertura de las fuentes.
