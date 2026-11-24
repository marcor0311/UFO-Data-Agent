# Reconstrucción del mapa 3D de duración por forma

En el prototipo, D4 presenta cajas de duración por forma. El mapa de terreno y el catálogo morfológico están en módulos distintos. Estos prompts describen un posible ensamblaje a evaluar después.

## Preparar el mismo recorte

> Usa California, 1990–1999. Conserva ID, forma normalizada, fecha, coordenadas y procedencia. Convierte a minutos solo las duraciones válidas en segundos. Informa N total, N con duración, N con coordenadas y N en la intersección. Mantén los valores desconocidos y la cola de duración accesibles.

## Probar una vista combinada

> Abre el mapa 3D con el relieve real del motor original. Compara las formas por color o filtro y muestra el rango de duración en minutos con una escala declarada. Mantén la elevación para el terreno. Presenta al lado mediana, IQR y N por forma con el renderizador D4. Usa una selección común por ID y permite volver a 2D con el mismo ámbito.

## Evaluar antes de incorporar

> Verifica que los N del mapa y de D4 coincidan para el ámbito acordado, o explica las exclusiones por coordenadas y duración. Abre una ficha desde una marca, comprueba la unidad, conserva el filtro y prueba el respaldo si las teselas fallan. Señala las formas de N bajo, los faltantes y la incertidumbre de las coordenadas.

- [D4 y su renderer](fuente-original.txt) proporcionan las cajas y la selección estadística.
- [Motor cartográfico](../../_compartido/js/mapas-geograficos.js) conserva terreno, área y selección.
- [Mallas y lógica espacial](../../_compartido/js/mapas-analiticos.js) aporta la representación por forma.
- [Mapa 3D de clusters](../mapa-3d-clusters/) demuestra cómo montar una capa analítica sobre el motor y mantener la posición al cargar nuevas teselas.

Queda por decidir si la codificación de duración será por clases o escala continua, qué agrupaciones aparecerán en la leyenda y cómo representar las colas sin confundir duración con tamaño o altitud.
