# Globo 3D

**Estado: Implementada** en el Data Agent como vista `globe` ([#89](https://github.com/marcor0311/UFO-Data-Agent/issues/89)).

Globo nocturno que gira con todos los informes con coordenadas aptas, cada uno en su ubicación declarada. Se arrastra para girarlo y se acerca con la rueda o con los botones. El giro se pausa con un botón, al arrastrar y cuando el sistema pide movimiento reducido. Los informes con coordenadas idénticas comparten un punto, cuyo tamaño y brillo crecen con ellos.

Con **Rectángulo** o **Lazo** se dibuja un área sobre el globo y se abre debajo en el mapa 2D y 3D con exactamente las ubicaciones que quedan dentro de la forma, todas y sin límite de filas. Ese mapa tiene las mismas herramientas (Mover, Rectángulo, Lazo), como en DB Test: resalta los informes seleccionados y lista sus identificadores. Esc cancela el dibujo. El área seleccionada queda activa en la conversación: las preguntas siguientes (por ejemplo, “solo 1995 a 1999”) se limitan a ella hasta pulsar “Quitar área”.

## Utilidad para el Data Agent

Dar una vista del planeta completo, que el mapa plano deforma cerca de los polos, y acercarse a una región sin cambiar de vista.

## Origen

Prototipo animado [06-globo.html](prototipo/06-globo.html), con su [captura](prototipo/06-globo.png) y su [grabación](prototipo/06-globo.webm). El resto de prototipos animados se descartó porque no encajaba en el proyecto. Para verlo en vivo, sirve la carpeta `propuesta-graficos/` (`python3 -m http.server 8765`) y abre `http://127.0.0.1:8765/done/globo-3d/prototipo/06-globo.html`.

Capturas con datos reales de Gold: [globo-app.png](referencias/globo-app.png), con zoom [globo-app-zoom.png](referencias/globo-app-zoom.png), lazo [lazo.png](referencias/lazo.png) y área abierta en el mapa 2D con selección [area-sel.png](referencias/area-sel.png).

## Tecnologías y datos

**Tecnologías.** deck.gl 9.4 (`_GlobeView`, `ScatterplotLayer`, `GeoJsonLayer`) y la geometría de `world-atlas`.

**Datos.** `fact_report` con `report_count`, sin `group_by` y con eligibility `map`. El servidor agrupa por coordenadas idénticas y devuelve todas las ubicaciones (79.381 en la carga actual), sin el límite de 500 filas.

## Prompt de ejemplo

> Muéstrame en un globo dónde se concentran los informes con coordenadas.

## Límites

El globo es solo la vista global y no admite filtros; las preguntas con país, año o forma usan el mapa 2D y 3D. La respuesta del globo pesa unos 4 MB y tarda unos 5 s en calcularse. Muchas coordenadas son el centro de una ciudad, no el lugar exacto del avistamiento. La concentración en Norteamérica refleja la cobertura de las fuentes, en su mayoría estadounidenses. Cuenta informes, no área ni población.
