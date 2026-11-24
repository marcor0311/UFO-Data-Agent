# Prototipos animados

El globo (06) está implementado como vista `globe`; los demás quedan como [sugerencias](../pendientes/animados-sugeridos/README.md).

Cada prototipo tiene una captura (`.png`). Los videos `.webm` (unos 31 MB) no se suben al repositorio. Todos usan datos agregados de la carga Gold aprobada (`3f1da0ee`), extraídos en solo lectura. No se usó `DB Test`.

Para verlos en vivo, desde `propuesta-graficos/`:

```sh
python3 -m http.server 8765
```

y abre `http://127.0.0.1:8765/prototipos-animados/01-mapa-animado-por-ano.html` (o cualquier otro).

| # | Prototipo | Qué anima | Datos de Gold |
| --- | --- | --- | --- |
| 01 | Mapa animado año a año | Destellos por celda de 1° de 1940 a 2023, con rastro acumulado | `fact_report`: año, celda 1°, mapa + calendario |
| 02 | Columnas 3D | Columnas que crecen con los informes acumulados mientras gira la cámara | Igual que 01 |
| 03 | Arcos a instalaciones nucleares | Pulsos de cada zona a su instalación más cercana (menos de 500 km) | `nearest_facility_key`, `nuclear_distance_km`, `dim_nuclear_facility` |
| 04 | Encuentros según Hynek | Mapa por década coloreado por clase; los encuentros cercanos de tercer tipo en magenta | `hynek`, década, celda 1° |
| 05 | Colores reportados | Recorre cada color declarado y al final los mezcla | `color_family`, celda 1° |
| 06 | Globo 3D | Globo que gira con todos los informes con coordenadas | celda 1° |
| 07 | Reloj radial | Aguja que barre las 24 horas por los 12 meses | `event_hour`, `event_month` |
| 08 | Río de formas | Proporción de cada forma por década, revelada de izquierda a derecha | `shape_code`, década |
| 09 | Carrera de países | Diez primeros países por informes acumulados, año a año | `country_iso2`, año |
| 10 | Movimiento por forma | Partículas que se mueven como declara el testigo (lineal, suspendido, rápido…) | `movement_type`, `shape_code` |
