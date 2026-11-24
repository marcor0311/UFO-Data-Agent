---
name: UFO Data Agent / Archivo UAP
description: Portada de archivo oscura y espacio analítico claro para explorar informes UAP en español.
colors:
  archive-backdrop: "#0b1016"
  archive-surface: "#111923"
  archive-ink: "#f0f3f6"
  archive-muted: "#b6c2cf"
  archive-signal: "#c6d9e9"
  archive-rule: "#354352"
  page: "#f9f9f7"
  surface: "#fcfcfb"
  surface-2: "#f3f2ee"
  ink: "#0b0b0b"
  ink-2: "#52514e"
  muted: "#898781"
  grid: "#e1e0d9"
  axis: "#c3c2b7"
  accent: "#2a78d6"
  critical: "#d03b3b"
  series-1: "#2a78d6"
  series-2: "#eb6834"
  empty-cell: "#f0efec"
  seq-100: "#cde2fb"
  seq-400: "#3987e5"
  seq-700: "#0d366b"
  chat-background: "#f1f6fb"
  chat-surface: "#ffffff"
  chat-ink: "#0f2a44"
  chat-muted: "#4a5f74"
  chat-line: "#d9e5f0"
  chat-line-strong: "#bfd2e4"
  chat-blue: "#1f5389"
  chat-blue-hover: "#376fa7"
  chat-blue-soft: "#dceaf8"
typography:
  archive-display:
    fontFamily: '"Barlow Condensed", "Arial Narrow", sans-serif'
    fontSize: "clamp(6rem, 11.7vw, 13rem)"
    fontWeight: 700
    lineHeight: 0.91
    letterSpacing: "-.035em"
  archive-headline:
    fontFamily: '"Barlow Condensed", "Arial Narrow", sans-serif'
    fontSize: "clamp(3.5rem, 5.8vw, 5.8rem)"
    fontWeight: 700
    letterSpacing: "-.017em"
  archive-body:
    fontFamily: '"Manrope", sans-serif'
    fontSize: "clamp(1.25rem, 2.05vw, 2rem)"
    lineHeight: 1.4
  chat:
    fontFamily: '"Manrope", system-ui, sans-serif'
    fontSize: "14px"
    lineHeight: 1.55
  answer:
    fontFamily: '"Manrope", system-ui, sans-serif'
    fontSize: "16px"
    lineHeight: 1.65
  data:
    fontFamily: 'system-ui, -apple-system, "Segoe UI", sans-serif'
    fontSize: "15px"
    lineHeight: 1.5
rounded:
  code: "4px"
  action: "6px"
  button: "8px"
  card: "10px"
  composer: "14px"
spacing:
  chat-gutter: "24px"
  chat-gutter-wide: "32px"
  turn: "28px"
  archive-gutter: "clamp(1.25rem, 6vw, 6rem)"
---

# Sistema de diseño: UFO Data Agent

## Resumen

Este documento describe el sistema implementado. [PRODUCT.md](PRODUCT.md) define
el alcance y las capacidades. El historial de cambios pertenece a Git y a los PR.

Hay dos superficies con sistemas separados:

- **Archivo UAP (`/`)**: fondo noche, fotografía de archivo, titulares
  condensados en Barlow Condensed y lectura en Manrope. Tokens en
  `apps/web/src/app/landing.module.css`.
- **Agente (`/agent`)**: conversación azul pálido a la izquierda y resultados
  sobre superficie clara. Tokens `--chat-*` en `.workspace` y paleta de datos
  en `:root`, ambos en `apps/web/src/app/globals.css`.

**Regla de alcance.** Los tokens `archive-*` solo se aplican a la portada; los
`chat-*` solo a la cabecera y la columna de conversación. Los gráficos usan
siempre la paleta de datos de `:root`.

## Colores

| Superficie | Tokens | Uso |
| --- | --- | --- |
| Portada | `archive-backdrop`, `archive-surface`, `archive-ink`, `archive-muted` | Fondo continuo, paneles y lectura |
| Portada | `archive-signal`, `archive-rule` | Foco visible y divisores |
| Conversación | `chat-background`, `chat-surface`, `chat-ink`, `chat-muted`, `chat-line*` | Columna, tarjetas, texto y bordes |
| Conversación | `chat-blue`, `chat-blue-hover`, `chat-blue-soft` | Acciones, pregunta del usuario y resaltes |
| Datos | `series-1`, `series-2` | Primera y segunda serie categórica |
| Datos | `seq-100` … `seq-700` | Escala secuencial de densidad y coropletas |
| Datos | `empty-cell` | Celdas sin datos, distintas de cero |
| Datos | `grid`, `axis`, `ink-2`, `muted` | Rejilla, ejes y etiquetas |
| Estados | `critical` | Avisos y errores; el error del chat usa `#fbece7` / `#8a3324` |

Mantener un contraste mínimo de 4.5:1 en texto normal y 3:1 en texto grande y
marcas de datos. Una celda ausente nunca se pinta como un cero: usa
`empty-cell` y se nombra en la tabla exacta. El color no es la única pista,
porque series, celdas y marcadores llevan nombre y valor accesibles.

## Tipografía

La portada carga Barlow Condensed Bold (`--archive-display`) para titulares y
cifras, y Manrope (`--archive-body`) para la lectura. El agente carga Manrope
como `--chat-font` en la conversación. Los gráficos y tablas usan la pila del
sistema (`--font`). Usar cifras tabulares en tablas y tarjetas, títulos sin
punto final y texto erguido.

En la conversación, la interfaz usa 14px, la respuesta 16px con interlineado
1.65, la bienvenida 22px y el texto auxiliar 13px. El compositor usa 16px.

**Lectura escalable.** Conservar la lectura y las acciones con zoom al 200% y
con espaciado personalizado. Redistribuir antes que recortar.

## Layout

Solo portátil: 1440×800, 1440×1000 y 1920×1080.

### Portada

Secciones a ancho completo con margen `archive-gutter`: héroe con fotografía,
galería del archivo, cifra destacada, briefing con la demostración de
California 1990 y un cierre fotográfico con “Entrar al Data Agent”. Un enlace
de salto lleva a `#contenido`.

### Agente

`.workspace` ocupa `100dvh` (mínimo 560px), con una cabecera de 56px que
contiene la marca, la navegación con indicador animado y la sesión. Debajo,
`.layout` reparte una columna de conversación `clamp(420px, 30vw, 500px)` y el
panel de resultados en el ancho restante. Ambos paneles desplazan su contenido
de forma independiente. Desde 1700px el margen interior pasa de 24px a 32px.
Con puntero fino por debajo de 900px de ancho o 544px de alto, el layout se
apila como respaldo de accesibilidad, no como variante móvil.

## Profundidad y movimiento

El agente separa grupos con superficies y bordes. La única sombra es la del
desplegable del historial. Las transiciones de vista animan el indicador de
navegación (0.28s) y el cambio de panel de exploración (0.3s). Las animaciones
se envuelven en `prefers-reduced-motion: no-preference`.

## Formas

Código 4px, acciones de texto 6px, botones 8px, tarjetas de consulta e
historial 10px, compositor 14px. La pregunta del usuario usa una burbuja
`14px 14px 4px 14px` alineada a la derecha. Los puntos de carga son circulares.

## Componentes

### Conversación

- **Bienvenida**: título, explicación breve y ejemplos públicos que se abren
  por enlace directo.
- **Turno**: la pregunta es un botón con `aria-pressed` que reactiva su
  resultado. La respuesta es texto plano o Markdown mínimo. Un `details`
  muestra la traza de herramientas.
- **Pendiente y error**: el pendiente usa tres puntos y texto. El error
  conserva el borrador y los resultados anteriores.
- **Compositor**: textarea de hasta 192px, selector de modelo por pregunta y
  botón de envío. Enter envía y Shift+Enter añade una línea.
- **Historial**: desplegable con las conversaciones guardadas y la actual
  marcada con `aria-current`.

### Resultados

El registro de vistas (`components/views/registry.tsx`) admite `table`,
`bars`, `timeseries`, `points`, `density`, `choropleth` y `hour_weekday`. Las
reglas de cada vista:

- Una tabla sin filas se presenta como tarjetas de cifra (`stat-grid`).
- Una métrica por panel: nunca dos escalas en un eje.
- Los mapas por país muestran la cobertura real y los países sin datos.
- La matriz día y hora distingue entre ceros y celdas ausentes.
- Cada resultado lleva la tabla exacta, la procedencia (`provenance`), las
  exclusiones por elegibilidad y las limitaciones.
- Gráficos y totales se vinculan solo si comparten el mismo alcance.

## Hacer y no hacer

### Hacer

- Mantener separados los sistemas de cada ruta.
- Nombrar la unidad (“informes”) en títulos, tarjetas y ejes.
- Mostrar la población excluida junto a cada cifra que la tenga.
- Comprobar el contenido real en las tres resoluciones.

### No hacer

- Usar los colores del archivo en gráficos.
- Pintar como cero una celda sin datos.
- Presentar puntuaciones de modelo como hechos o una proximidad como relación.
- Añadir sombras o decoración a los paneles analíticos.
