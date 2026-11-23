# Motor cartográfico del HTML local

La versión actual incorpora `maplibre-gl-5.24.0.js`, el bundle standalone original del paquete npm maplibre-gl 5.24.0, con su CSS y licencia. El cargador lo inserta como script clásico al abrir un mapa. Ese SDK genera su propio Blob con el worker clásico integrado.

No se realiza una importación ESM del motor ni se configura un worker externo o un marcador .cjs. El intento previo con MapLibre 6.15.0 y worker convertido no quedó validado en el navegador del usuario y se retiró de la ruta de ejecución. Sus archivos permanecen como fuentes históricas sin incorporarse al HTML.

`python3 build-observatorio.py` embebe dos SDKs: MapLibre standalone (que incluye el worker) y deck.gl. `python3 verificar-integridad.py` compara ambos payloads con los recursos locales y verifica que repetir el build no cambia el HTML.

`node verificar-worker.cjs` carga el SDK standalone real en un contexto Node, obtiene el Blob de worker que ese mismo SDK genera, lo ejecuta y comprueba dos respuestas del protocolo MapLibre. No abre una página ni acredita WebGL, teselas o compatibilidad final con file://.

`node verificar-carga-mapas.cjs` comprueba el ciclo de carga con dobles del SDK: no retirar la pantalla antes del render, mostrar errores tardíos y capturar fallos de integración de capas. No es prueba visual.

La licencia original está en `maplibre-gl-5.24.0-LICENSE.txt`. Contexto de la elección: [migración oficial v5→v6](https://maplibre.org/maplibre-gl-js/docs/guides/v5-to-v6-migration-guide/), [discusión del proyecto sobre HTML local](https://github.com/maplibre/maplibre-gl-js/discussions/8225).
