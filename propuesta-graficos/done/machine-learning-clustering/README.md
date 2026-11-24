# Machine Learning – Clustering

**Estado: Implementada** en el Data Agent con los análisis `clusters` (por radio y días, o por semana y celda) y `kmeans_profiles`.

## Concepto

Conservar la idea de identificar agrupaciones exploratorias de informes según una distancia o un conjunto de atributos definidos.

## Utilidad

Puede sugerir subconjuntos para revisar concentración, duplicación probable o cobertura, con los IDs que permiten volver al archivo.

## Implementación futura

Requiere acordar variables, reglas de elegibilidad y unidades. Para espacio y tiempo, se pueden comparar ventanas y radios y evaluar la estabilidad de las membresías, la sensibilidad a fuentes y el porcentaje sin asignación. La selección de tecnología queda pendiente de esa evaluación.

## Prompt de ejemplo

> Explora si los grupos persisten al variar el radio y la ventana temporal. Resume los parámetros, los informes excluidos y lo que cambia.

## Límites y pendientes

Los grupos dependen del método, la densidad de reportes y posibles duplicados. Conviene interpretar la asignación como un resultado exploratorio del archivo.
