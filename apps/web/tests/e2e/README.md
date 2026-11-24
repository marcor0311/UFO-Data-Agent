# Pruebas de historial y navegación por teclado

Desde `apps/web`:

```sh
npm ci
npx playwright install chromium
npm run test:e2e
```

La configuración inicia la web en `http://127.0.0.1:3000`. Las pruebas simulan la
API, la sesión, el historial y las respuestas demoradas: no necesitan la API
real, una cuenta, un modelo ni la carga completa de Gold.

Para usar una web ya iniciada, define `PLAYWRIGHT_BASE_URL`. Opcionalmente,
`PLAYWRIGHT_CHROMIUM_EXECUTABLE_PATH` permite usar un ejecutable de Chromium
existente. Las pruebas unitarias siguen ejecutándose por separado con
`npm run test:unit` y no inician un servidor.

Los recorridos cubren una ventana de portátil de 1280×720 y su equivalente al
200 %: un viewport CSS de 640×360 con escala de dispositivo 2. Se comprueban
tanto el desplazamiento interno del panel como la posición de lectura en la
página cuando el diseño se reacomoda para el zoom. Las capturas se guardan en
`test-results/`.
