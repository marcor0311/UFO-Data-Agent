# UFO Data Agent

## Fuentes de datos

La base integra datos de:

- UFOCAT
- UPDB
- UFO-search
- Capella / PhenomAInon

## Construir Bronze

Requisitos: Python 3.10+, `curl`, conexión a Internet y aproximadamente 1 GB libre.

Desde la raíz del repositorio:

```bash
python3 scripts/build_bronze.py
```

Descarga Bronze desde Releases de este mismo proyecto y verifica la base en
`data/bronze/ufo.db`. Silver y Gold se generarán a partir de esta base mediante
los scripts de transformación del repositorio.

## Construir Silver

Con Bronze disponible localmente, SQLite con funciones JSON habilitadas y
aproximadamente 3 GB adicionales libres para construcción, temporales e historial:

```bash
python3 scripts/build_silver.py
```

Genera `data/silver/ufo.db` con las reglas de `config/silver.json`: omite las 41
columnas vacías aprobadas, normaliza fechas, geografía, texto y tipos, registra
incidencias y agrupa duplicados con evidencia estricta. Conserva las 10 tablas
originales, todas sus filas e identificadores; añade trazabilidad y vistas para
análisis. Bronze permanece intacta. El resultado se acompaña de
`data/silver/ufo.validation.json`.

Para revisar la base o actualizar una salida validada guardando la anterior:

```bash
python3 scripts/build_silver.py --verify-only
python3 scripts/build_silver.py --replace
```

Las versiones anteriores quedan en `data/silver/.history/`. Para generar otra copia:

```bash
python3 scripts/build_silver.py --database /tmp/ufo-silver.db
```

Ver el [contrato de Silver](data/silver/README.md) para las reglas, tablas,
vistas, tratamiento de incertidumbre y validaciones.

Para diagnosticar los casos pendientes con consultas reproducibles:

```bash
python3 scripts/review_silver.py
```

Consulta la [revisión de Silver](docs/silver-review.md) para los hallazgos,
correcciones y límites de interpretación de la política v3.

El [contrato analítico de Silver](docs/silver-contract.md) define el grano,
las recuperaciones de precisión temporal, los intervalos, las vistas por informe,
los valores rescatados y los controles de aceptación de la capa.

La política actual es **v5**. Recupera campos factuales de las fuentes originales
por ID y fecha idénticos, conserva su procedencia y recalcula las dependencias
geográficas. Antes de consumir esta salida desde Gold:

```bash
python3 scripts/check_silver_ready.py
```

El comando termina con error si la salida no corresponde a Bronze, código,
política y referencias actuales o incumple el contrato. Genera
`data/silver/ufo.readiness.json` con cobertura, incidencias y reglas de consumo.
Ver el [cierre de Silver para Gold](docs/silver-gold-readiness.md).
