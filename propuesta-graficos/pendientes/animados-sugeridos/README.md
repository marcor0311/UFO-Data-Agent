# Gráficos animados sugeridos

**Estado: Sugerencia.** Prototipos sueltos sobre datos agregados de Gold (carga `3f1da0ee`), sin integrar en la app. El globo ya está implementado en [done/globo-3d](../../done/globo-3d/).

Los prototipos están en [prototipos-animados/](../../prototipos-animados/) y sus capturas en [fotos/](../../fotos/README.md), que explica cómo abrirlos en vivo.

| # | Prototipo | Qué anima | Captura |
| --- | --- | --- | --- |
| 01 | Mapa animado año a año | Destellos por celda de 1° de 1940 a 2023, con rastro acumulado | [01](../../fotos/01-mapa-animado-por-ano.png) |
| 02 | Columnas 3D | Columnas que crecen con los informes acumulados mientras gira la cámara | [02](../../fotos/02-columnas-3d.png) |
| 03 | Arcos a instalaciones nucleares | Pulsos de cada zona a su instalación más cercana (menos de 500 km); la cercanía no implica relación | [03](../../fotos/03-arcos-nucleares.png) |
| 04 | Encuentros según Hynek | Mapa por década coloreado por clase | [04](../../fotos/04-hynek-por-decada.png) |
| 05 | Colores reportados | Recorre cada color declarado y al final los mezcla | [05](../../fotos/05-colores-reportados.png) |
| 07 | Reloj radial | Aguja que barre las 24 horas por los 12 meses | [07](../../fotos/07-reloj-radial.png) |
| 08 | Río de formas | Proporción de cada forma por década | [08](../../fotos/08-rio-de-formas.png) |
| 09 | Carrera de países | Diez primeros países por informes acumulados, año a año | [09](../../fotos/09-carrera-paises.png) |
| 10 | Movimiento por forma | Partículas que se mueven como declara el testigo | [10](../../fotos/10-movimiento-por-forma.png) |

## Pendientes antes de integrar alguno

- En los mapas planos queda una línea tenue cerca de 65° N.
- Las clases NO y DO de Hynek se etiquetaron como objeto nocturno y diurno; el catálogo de Gold no trae su definición.
- Los datos de cada prototipo son extractos estáticos: integrarlos exige una vista con contrato en `scripts/gold_query.py`, como el resto.
