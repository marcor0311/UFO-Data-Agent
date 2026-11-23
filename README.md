# UFO Data Agent

## Ejecutar la aplicación local

Desde la raíz del repositorio, prepara la API y la web una vez:

```bash
python3.14 -m venv apps/api/.venv
apps/api/.venv/bin/python -m pip install -e apps/api
npm --prefix apps/web ci
```

`npm --prefix apps/web run dev` inicia la web y la API. Abre `http://127.0.0.1:3000`
para que el navegador conserve la cookie al volver de ChatGPT. El catálogo
requiere la caché de servicio generada al construir Gold. Si ya tienes una API
en ejecución, puedes iniciar solo la web con `npm --prefix apps/web run dev:web`.

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

El [contrato analítico de Silver v4](docs/silver-contract.md) define el grano,
las recuperaciones de precisión temporal, los intervalos, las vistas por informe,
los valores rescatados y los controles de aceptación de la capa.

## Construir Gold

Gold es la capa analítica y semántica del data agent propio. Se construye solo
por lectura sobre Silver v6 y Bronze, cuyos SHA-256 están fijados en
`config/gold/gold.json`. Requiere Python 3.11+; en macOS se usa `python3.14`,
porque el `python3` del sistema (3.9) no interpreta fechas ISO con fracciones.
Necesita unos 1,5 GB libres. En orden:

```bash
python3.14 scripts/build_gold.py                                   # modelo Gold (ejecuta la puerta de Silver)
python3.14 scripts/discover_gold.py                                # perfil, catálogo y caché de servicio
python3.14 scripts/gold_query.py certify                           # resultados esperados de las consultas certificadas
python3.14 scripts/verify_gold_independent.py --write-references   # verificación independiente desde Silver
python3.14 scripts/run_gold_evals.py                               # set de evaluación por load_id
python3.14 scripts/check_gold_ready.py                             # puerta: ready_for_agent
```

`fact_report` tiene un informe por ID de Bronze (702.572). Los eventos existen
solo para los 6.959 grupos de duplicados confirmados. Toda cifra de informes es
un rango: entre 390.944 y 702.572, por los pares candidatos pendientes. Los
análisis por año, mes, día, hora, mapa, país y proximidad aplican su elegibilidad
y declaran cuántos informes quedaron fuera.

El agente nunca escribe SQL: usa `scripts/gold_query.py`, que ofrece un
contrato tipado, consultas certificadas, vistas, procedencia y limitaciones.

- [Contrato Gold](docs/gold-contract.md)
- [Catálogo generado](docs/GOLD_CATALOG.md) y [entidades](docs/GOLD_ENTITIES.json)
- [Guía de dominio para el agente](docs/gold-domain-guide.md)
- [Verificación y evaluación](docs/gold-verification.md)
- [Consultas certificadas](config/gold/certified_queries.json),
  [set de evaluación](docs/GOLD_EVALS.json) y
  [registro de correcciones](config/gold/corrections.json)

Límites: un informe no es un hecho verificado, y coincidir con Bronze no prueba
que sea verdad. Además:

- hay duplicados pendientes;
- hay sesgos por fuente y época;
- los marcadores de día reducen la precisión de algunas fechas;
- parte de los valores procede de evidencia externa;
- las puntuaciones de modelo no son hechos.
