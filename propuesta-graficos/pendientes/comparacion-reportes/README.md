# Comparación de reportes

**Estado: Descartada.** La vista `compare` se retiró en [#86](https://github.com/marcor0311/UFO-Data-Agent/pull/86) por decisión de producto.

Dos fichas y una tabla de trece campos con controles para cambiar ambos reportes y abrirlos por separado. Destaca coincidencias entre valores presentes.

## Utilidad para el Data Agent

Contrastar cómo se describen dos informes, qué campos coinciden y qué datos faltan antes de leer su procedencia.

## Recursos originales

[comparacion.original.txt](comparacion.original.txt) conserva el render y los controles de `compareCases` de `mejoras-data-agent.js`. [comparacion.css](comparacion.css) reúne las reglas originales extraídas del HTML.

## Tecnologías y datos

**Tecnologías.** JavaScript, DOM, selectores nativos y CSS. La función y los controles vienen de `compareCases`.

**Datos.** Dos filas con ID original, fecha, localidad, forma original y normalizada, duración, testigos, cantidad de objetos, procedencia y marcas documentales. El ejemplo usa la muestra original de 240 filas. Véanse los [recursos compartidos](../../_compartido/README.md#datos-necesarios).

## Cómo revisar la referencia

En el [observatorio original](../../../DB%20Test/observatorio.html), solicita “Compará las características de dos eventos UAP” o busca **Comparar eventos**. Los selectores originales cambian las dos fichas.

## Prompt de ejemplo

> Compara los reportes #8137 y otro de la muestra que yo seleccione. Destaca solo los campos registrados que coinciden y abre las fichas por separado.

## Límites y pendientes

El selector original usa IDs internos y la ficha muestra el ID de la base. Las coincidencias no identifican duplicados ni establecen un origen común. Las marcas de foto y video no traen por sí solas los archivos correspondientes.
