# Auditoría del mapa, 19 de octubre de 2026

Alcance inicial: código actual, contratos de dibujo y documentación del motor. No es una inspección visual del navegador: la automatización de `file://` fue rechazada y no se eludió. `view_image` permite inspeccionar imágenes guardadas, pero no capturar esa pestaña.

## Hallazgos antes de corregir

- **P1, Marcadores ocultos.** ScatterplotLayer no configura billboard ni una política de visibilidad analítica. En la integración intercalada comparte profundidad con el terreno/edificios. Dos metros sobre una elevación consultada no garantizan visibilidad; un disco horizontal tampoco mantiene su legibilidad al inclinar la cámara.
- **P1, Elevaciones tardías.** La consulta devuelve null mientras llegan teselas; el código lo convierte a cero. Solo invalida las posiciones cuando `sourcedata.isSourceLoaded` es verdadero para toda la fuente. Un tile disponible puede no actualizar los marcadores durante la carga global.
- **P1, Área incompleta en el chat.** Existían límites de navegación y selección por ratón, pero faltaba una instrucción de área que filtrara registros y preservara el alcance al cambiar la representación.
- **P1, Representación no implementada.** El prompt no ofrecía elegir puntos o modelos con volumen. Los puntos solo codificaban posiciones, sin representar las formas del archivo.
- **P2, Cambio 2D/3D dentro del caso.** El control cartográfico no sincronizaba la etapa de la historia; otro render podía restaurar la etapa anterior.
- **P2, Controles.** La barra puede saturarse en pantallas estrechas. La nueva elección de representación debe ocupar un solo control y mantener acceso al ratón y teclado.

## Dirección de reparación

Usar una capa analítica superpuesta, separada de la profundidad del mapa, con puntos que miran a la cámara. Mantener profundidad entre los propios modelos para conservar su volumen. Recalcular elevación al llegar cada tesela y al terminar movimientos, sin una animación perpetua. Los modelos serán símbolos de la forma reportada, de tamaño de pantalla acotado, no reconstrucciones ni medidas de un objeto observado. Formas desconocidas permanecen como puntos.

Un área pedida por lugar/radio o coordenadas debe filtrar los registros, acotar el terreno y conservarse entre puntos/modelos y 2D/3D. La región y período de cada muestra siguen siendo límites de los datos disponibles.

Fuentes primarias: [integración MapLibre y terreno](https://deck.gl/docs/api-reference/maplibre/overview), [modos de superposición](https://deck.gl/docs/developer-guide/base-maps/using-with-maplibre), [profundidad y z-fighting](https://deck.gl/docs/developer-guide/tips-and-tricks), [geometría 3D](https://deck.gl/docs/api-reference/mesh-layers/simple-mesh-layer).

## Resultado de la reparación

- Superposición independiente del depth buffer del mapa. Puntos billboard con contorno blanco, profundidad desactivada y tamaño en píxeles; referencias, grupos y límites siguen esa política. Los modelos sí conservan profundidad interna. Esto prioriza legibilidad analítica: no sirve para deducir visibilidad tras una montaña.
- Actualización de elevaciones por tesela disponible, agrupada en un solo frame; se conserva la última altura cuando una consulta temporalmente devuelve null. Se libera el frame pendiente al cerrar la vista y se elimina el relieve al pasar a 2D.
- Cuatro mallas 3D locales, normales válidas y material iluminado. Los símbolos tienen tamaño acotado de pantalla y línea al punto de referencia; se limita a 60 modelos visibles y una representación por celda de 40 px para contener solapamiento. Todos los puntos y fichas permanecen disponibles. No se atribuyen medidas ni altitudes reales.
- Prompt de lugar/radio o latitud/longitud, filtro por distancia geodésica, contorno persistente del área y carga de zonas incluso con cero reportes. Cambio puntos/modelos desde chat o selector nativo, conservando límites e IDs.
- La etapa del caso se sincroniza con el control 2D/3D. El selector Mostrar evita añadir otra fila de botones; controles cartográficos de al menos 44 px.

## Evidencia y límites

`verificar-marcadores-mapa.cjs`: contratos de visibilidad, canvas separado, alturas al cargar teselas, cambio de representación, mallas finitas con normales unitarias, distancias y contorno geodésico. `verificar-prompts-mapa.cjs`: lugar/radio, puntos/modelos, 2D/3D, los tres casos, área sin reportes y rechazo de nombres/radios no admitidos. Estas pruebas usan adaptadores del motor, sin navegador/GPU.

Se renderizaron las mallas reales con un rasterizador CPU y se inspeccionó `verificacion-experiencia/modelos-formas.png` mediante view_image. Se revisó volumen, silueta, normales y tamaño comparativo; la imagen es independiente del mapa y no prueba composición, picking, gestos ni rendimiento en navegador. El render es reproducible con `renderizar-modelos-mapa.cjs` desde la raíz del proyecto.

Pendiente: inspección real de la experiencia a tamaño de escritorio y móvil, oclusión visual durante el cambio de teselas, foco/teclado, selección táctil y rendimiento de los dos contextos WebGL. La restricción de automatización del archivo local impide certificar esa parte. No se ha puntuado la aplicación completa ni se declara terminada la auditoría visual.

## Refinamiento de performance solicitado

Se añadió un presupuesto estricto de polígonos para las figuras: 18.000 triángulos / 60 modelos en escritorio y 9.000 / 30 modelos en vistas estrechas. Cada instancia cuenta para ese presupuesto. Tres niveles conservan volumen, normales y material: las mallas redondeadas pasan por 252 / 440 / 840 triángulos; discos por 192 / 288 / 480; triangulares por 48 / 96 / 144. El nivel más alto se reserva a pocas figuras cercanas. Las doce combinaciones de forma/detalle se reutilizan. Los registros que no reciben modelo conservan su punto, selección y ficha.

Prueba nueva: `verificar-presupuesto-modelos.cjs`, con 224 escenarios y comprobación del coste de las capas del adaptador. Se actualizó e inspeccionó el render independiente de las mallas con detalle medio. La prueba valida el presupuesto geométrico; no sustituye medir FPS, memoria total, gestos o rendimiento WebGL real.

## Acceso a formas sin malla

Se incorporó una distinción redundante en forma y texto: anillo blanco con contorno para modelos no disponibles; punto azul para representaciones simplificadas que sí tienen un modelo; ancla pequeña junto a los modelos dibujados. La forma registrada se conserva y no se sustituye por una geometría inventada. La leyenda agrupa por representación del área, abre listas filtradas y permite restaurar todos los registros sin cambiar el alcance del análisis. Se mueve la lista delante de las notas de fuentes para que ese acceso sea directo.

`verificar-sin-modelo.cjs` comprueba los estilos de los anillos, leyenda/conteos, tooltip con forma original, ficha por ID, lista de registros sin modelo, restauración, cambio a puntos y distinción respecto a modelos simplificados por densidad. No se añaden mallas ni se amplía el presupuesto de polígonos. Son contratos de código con dobles del SDK; la revisión visual del mapa sigue pendiente.

## Fallo SimpleMeshLayer comunicado y reproducido

El usuario observó `Cannot read properties of undefined (reading 'length')` al inicializar la figura triangular. Se reprodujo exactamente con el SDK deck.gl 9.4.0 incorporado: su normalizador lee `attribute.value.length / attribute.size`, pero la malla enviada exponía arreglos tipados sin descriptores. Las pruebas anteriores con dobles del SDK no ejecutaban ese normalizador y no detectaban el problema.

Reparación: cada malla incorpora `attributes.POSITION` y `attributes.NORMAL` con `size:3` y `value` apuntando a los mismos buffers existentes, más topología y número de vértices. No se duplican datos ni cambian las cantidades de triángulos. `verificar-formato-mallas.cjs` reproduce el fallo del formato anterior y ejecuta `SimpleMeshLayer.getBounds` de la biblioteca real, que atraviesa el mismo normalizador y constructor Geometry usados por las mallas. Las doce combinaciones actuales pasan. No ejecuta shaders ni renderizado WebGL.

Se aislaron errores de modelos de la carga del mapa: un fallo de SimpleMeshLayer vuelve a puntos, conserva el área y los registros y muestra el motivo. El caso se prueba en `verificar-carga-mapas.cjs`; otros errores cartográficos mantienen su tratamiento específico. Siguen pendientes las comprobaciones visuales/GPU del navegador, sin presentar estas pruebas como equivalentes.
