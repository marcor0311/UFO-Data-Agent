# Recursos originales compartidos

El código y las dependencias proceden de DB Test. Las copias completas conservan sus archivos originales y los extractos indican el archivo y las líneas de origen.

| Recurso | Uso en el prototipo |
| --- | --- |
| [analitica-uap.fragmentos.txt](js/analitica-uap.fragmentos.txt) | Normalización de fechas y medidas, renderizadores SVG y lógica del inspector. El cálculo de DBSCAN se conserva como dependencia de los dos mapas de clusters. |
| [sketchbook-base.fragmentos.txt](js/sketchbook-base.fragmentos.txt) | Utilidades de presentación y envoltorio original de las vistas del Sketchbook. |
| [mapa-clusters.fragmentos.txt](js/mapa-clusters.fragmentos.txt) | Capa original de M1 y M1b, filtros por radio y ventana y montaje sobre el motor geográfico. |
| [mapas-geograficos.js](js/mapas-geograficos.js) y [mapas-analiticos.js](js/mapas-analiticos.js) | Montaje geográfico, eventos de selección, prompts geográficos y mallas por categoría. |
| [css/](css/) | Hojas originales de análisis y Sketchbook, más reglas de mapa y visor extraídas de `experiencia-conversacional.css`. |
| [vendor/](vendor/) | MapLibre GL JS 5.24.0 y deck.gl 9.4.0 con sus licencias. También conserva Three.js, OrbitControls y su licencia para el respaldo histórico. [Documentación original del worker](vendor/MAP-WORKER.md). |
| [datos/](datos/) | Fuentes originales de extracción, perfil de los cortes, empaquetado y contornos GeoJSON. |
| [estilos-exportacion.original.txt](estilos-exportacion.original.txt) | Constantes y funciones de NumPy y Matplotlib que acompañan a los extractos estáticos. |
| [notas/](notas/) y [pruebas/](pruebas/) | Auditorías y pruebas del proyecto de origen sobre los modelos, los prompts y el motor cartográfico. Los scripts conservan los supuestos de DB Test. |

## Datos necesarios

| Archivo en DB Test | Uso |
| --- | --- |
| `ufo_public.db` | Base SQLite de procedencia. La unidad es el reporte y el identificador es `sighting.id`. |
| `assets/analitica/sketchbook-v2.json` | Recortes `ca`, `historic` y `ml` del Sketchbook. |
| `assets/analitica/cohortes.json` | Recortes regionales de análisis y del mapa general. El [perfil original](datos/perfil.json) contiene las consultas de extracción. |
| `muestra-uap.json` | Muestra del comparador de reportes. |
| `sketchbook-v2/data.json` | Entrada del generador de láminas de DB Test. |

Los recortes se conservan en su ubicación original. Describen la población del prototipo, con sus propias reglas de cobertura y precisión. Una evaluación posterior en Gold deberá alinear el grano, los criterios de elegibilidad y el tratamiento de duplicados.

Para ver las interacciones, abre el [observatorio original](../../DB%20Test/observatorio.html). Cada ficha indica dónde encontrar su vista y qué requiere.
