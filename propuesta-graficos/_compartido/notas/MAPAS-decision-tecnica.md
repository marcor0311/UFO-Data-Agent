# Cartografía del prototipo local · 19 de octubre de 2026

Se mantiene **MapLibre GL JS 5.24.0 + deck.gl 9.4.0**, OpenStreetMap vía OpenFreeMap y elevación Mapzen Terrarium. Mapterhorn queda como fuente alternativa de elevación. El archivo sigue siendo local; las teselas se consultan por internet.

## Regresión localizada y reparada

El host vacío del mapa tenía `.geo-canvas { position:absolute; inset:0 }`. Al iniciar, MapLibre le agrega `.maplibregl-map`. Su CSS, incorporado después y con igual especificidad, impone `position:relative`. El host no tenía altura propia: sus hijos posicionados absolutamente no le aportan altura. El mapa podía emitir un render mientras su contenedor recortaba el contenido a altura cero. Las pruebas previas de worker y estado no comprobaban esta cascada.

La regla ahora se limita a los hijos del contenedor cartográfico y tiene mayor especificidad: posición absoluta y ancho/alto del 100%, también después de agregarse la clase del SDK. Se aplica tanto al archivo general como a Roswell, Socorro y Nimitz. No se volvió a cambiar de motor para resolver este fallo de estilos.

`verificar-estilos-mapa.py` reproduce la cascada anterior y comprueba la regla corregida en el HTML construido. Es una comprobación de declaraciones CSS, **no una captura ni una prueba de layout en navegador**. La comprobación visual del archivo continúa pendiente por la restricción de automatización de `file://`.

## Comparación de opciones

| Elemento | Decisión y motivo |
|---|---|
| OpenStreetMap + Mapzen | Complementarios. OSM aporta calles y edificios; Mapzen aporta elevación. Ambos ya están configurados. La integridad de edificios y sus alturas varía. |
| MapLibre + deck.gl | Complementarios. Un motor de navegación y terreno, más capas de registros, agrupaciones y selección. La capa analítica ahora usa el modo superpuesto: su propio canvas conserva los símbolos visibles frente al terreno. Los modelos conservan profundidad entre sus triángulos. El modo intercalado es otra opción del motor, pero no es el modo activo de esta reparación. [Documentación oficial](https://deck.gl/docs/developer-guide/base-maps/using-with-maplibre). |
| glTF/GLB | Formatos de objetos, no motores alternativos. deck.gl permite escenas glTF con `ScenegraphLayer`. Se reservarán a objetos documentados con unidades, escala, procedencia y función claras. Se incorporaron mallas sólidas locales mediante SimpleMeshLayer, sin cargadores ni archivos remotos. glTF sigue siendo una opción para futuros modelos documentados. [ScenegraphLayer](https://deck.gl/docs/api-reference/mesh-layers/scenegraph-layer). |
| Mapzen / Mapterhorn | Alternativas por vista: no superponer dos terrenos. La codificación del DEM debe corresponder a su proveedor. MapLibre admite Terrarium y Terrain RGB. [Especificación](https://maplibre.org/maplibre-style-spec/sources/#raster-dem). |
| Mapbox | Alternativa a MapLibre como motor principal. No hace falta sumar otro motor para resolver la altura del contenedor ni para combinar relieve y edificios. Se conserva la implementación abierta ya integrada. |
| CesiumJS + Google Photorealistic 3D Tiles | Opción apropiada para una experiencia centrada en mallas fotográficas y globo. Introduciría otro motor y configuración de acceso al contenido; el tutorial de Cesium requiere cuenta/token y habilitar Google Tiles. Se deja fuera de la corrección actual. [Guía oficial de Cesium](https://cesium.com/learn/cesiumjs-learn/cesiumjs-photorealistic-3d-tiles), [Google: contenido 3D](https://developers.google.com/maps/documentation/tile/3d-tiles-overview). |

La elección de motor es una decisión de arquitectura para este prototipo; no afirma superioridad universal ni que la apariencia final ya esté verificada.

## Comparación con el ejemplo local de Data

Se revisó, sin modificar, `data agent chatgpt/ufo-dataset-dashboard/src/content/dashboard/CityScene.jsx`. Ese ejemplo pinta geometría de edificios, calles y una malla de elevación ya cargadas usando Canvas 2D con proyección 3D. No usa un worker de MapLibre. Esto explica una diferencia de dependencias, pero no demuestra por sí solo por qué fallaba el navegador actual. La regresión de tamaño sí se reproduce en la cascada del artefacto actual.

Se usó la skill **Data / visualize-data** para conservar significado y trazabilidad: coordenadas reales, mismas selecciones por ID, detalle al seleccionar y separación entre registros y referencias. El terreno no prueba un avistamiento, ni los marcadores indican altitud de vuelo. Cartografía actual no equivale a paisaje histórico.

## Comprobaciones realizadas

- HTTP con `Origin:null`: estilo, catálogo vectorial, sprite JSON/PNG, glifos, catálogo Mapterhorn y una tesela vectorial y DEM por cada caso: 12 respuestas 200, con CORS público. El punto de Nimitz consultado está en el océano; una tesela vectorial pequeña allí no representa por sí misma un fallo.
- Resultado de esas solicitudes: `verificacion-experiencia/servicios-mapa.json`. No demuestra cobertura exhaustiva ni composición WebGL.
- Regresión CSS, integridad del HTML y worker nativo en Node correctos. Se conservaron las 60 comprobaciones de datos/estado y ocho de carga y área con dobles del SDK.
- Pendiente: inspección visual real, gestos, terreno/edificios al acercarse y rendimiento en el navegador del usuario. Los recorridos analíticos también requieren una revisión posterior de profundidad; esta reparación no los presenta como terminados.

## Área de trabajo

El motor recibe el encuadre regional antes de cargar el estilo. La navegación queda limitada a la extensión investigada con un margen; se desactivan las copias mundiales. La caché se limita a 96 teselas por fuente y los DEM se acotan a ese margen geográfico. Las teselas activas dependen del encuadre y el zoom: el límite de caché no equivale a un límite fijo de memoria total. [Opciones oficiales de MapLibre](https://maplibre.org/maplibre-gl-js/docs/API/type-aliases/MapOptions/).

Aplicar un rectángulo o lazo conserva sus IDs y límites geográficos. Ambos pasan de 2D a 3D en el archivo y los tres casos; las cámaras se guardan por área para evitar heredar encuadres de otra región. Una selección nueva desde gráficos calcula su propia extensión; quitar filtros devuelve el contexto regional. El botón «Volver al área» recupera el encuadre. Las referencias fuera de una selección siguen siendo consultables como contexto, sin ampliar automáticamente el área de trabajo.

`verificar-area-investigacion.cjs` comprueba ocho contratos de propagación y restablecimiento de área/IDs. `verificar-carga-mapas.cjs` comprueba ocho contratos de carga, encuadre inicial, caché, límites del DEM y fallos visibles. Son pruebas con adaptadores, sin certificar mapa visible ni rendimiento real.
