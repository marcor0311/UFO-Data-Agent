# Formas reportadas

**Estado, Recuperada**

Barras horizontales de las formas normalizadas, con recuento, proporción, búsqueda, paginación y acceso a los informes de una categoría. Incluye “Sin clasificar”.

## Utilidad para el Data Agent

Comparar la mezcla de formas en un corte y localizar categorías con cobertura baja o ausente.

## Recursos originales

[fuente-original.txt](fuente-original.txt) contiene el fragmento del renderizador de DB Test. Los [fragmentos analíticos](../../_compartido/js/analitica-uap.fragmentos.txt) y de [presentación](../../_compartido/js/sketchbook-base.fragmentos.txt) aportan preparación de datos, estilos de dibujo y selección.

Referencias archivadas: [D2-interactivo.html-fragment](referencias/D2-interactivo.html-fragment) (fragmento original de revisión), [D2-interactivo.svg](referencias/D2-interactivo.svg) (SVG original), [D2.png](referencias/D2.png) (lámina o revisión original), [D2.svg](referencias/D2.svg) (SVG original), [propuesta-v1.json](referencias/propuesta-v1.json) (ficha original v1), [propuesta-v2.json](referencias/propuesta-v2.json) (ficha original v2 y su prompt).

## Tecnologías y datos

**Tecnologías.** JavaScript/SVG. D2 delega en `categories` con dimensión `shape`.

**Datos.** IDs, `standardized_shape`, fecha y región del corte `ca`. Los faltantes se conservan como “Sin clasificar”. Véanse los [recursos compartidos](../../_compartido/README.md#datos-necesarios).

## Cómo revisar la referencia

Consulta la lámina D2 en `referencias/`. Para revisar las interacciones existentes, abre el [observatorio original](../../../DB%20Test/observatorio.html) y busca **Formas reportadas** en **Explorar herramientas**. El recorte y la pregunta del prototipo están en la ficha v2.

## Prompt de ejemplo

> Muestra las formas reportadas en California durante los noventa. Incluye los informes sin clasificar y deja consultar cualquier categoría.

## Límites y pendientes

La forma es una etiqueta del registro. Variar la fuente o el período puede alterar las proporciones.
