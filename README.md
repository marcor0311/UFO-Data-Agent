# UFO Data Agent

Integra UFOCAT, UPDB, UFO-search y Capella / PhenomAInon en un data agent.

## 1. Construir los datos (un solo comando)

Requisitos: Python 3.11+ con SQLite, `curl` solo para la primera descarga de
Bronze y ~4 GB libres. Guía completa, con Windows y la recuperación tras un
fallo: [docs/pipeline-local.md](docs/pipeline-local.md).

```bash
python3 scripts/build_all.py          # macOS / Linux
py -3.12 scripts\build_all.py         # Windows (PowerShell)
```

Construye Bronze → Silver → Gold → `ready_for_agent` y se detiene en el primer
paso que falle. Cada capa se construye en una versión nueva bajo
`data/<capa>/versions/` y se promueve con una sola transacción en
`data/releases.sqlite3`, después de pasar todos sus controles. Hasta entonces
sigue vigente la versión aprobada anterior, aunque el proceso falle o se
interrumpa. Solo un build publica a la vez. Si Bronze ya está en el disco, no
hace falta Internet.

```bash
python3 scripts/build_all.py --desde silver   # Silver y Gold (Bronze se reutiliza)
python3 scripts/build_all.py --desde gold     # solo Gold, sobre la Silver aprobada
python3 scripts/build_all.py --estado         # versiones aprobadas
python3 scripts/build_all.py --actualizar-referencias   # copiar certificaciones y evaluaciones a config/ y docs/
```

Gold solo acepta una Silver con un informe válido (`passed: true`), sin cambios
después de validarla, construida desde la Bronze oficial (tamaño y SHA-256) y
al día con la política y el código actuales. Si no, indica el motivo y pide
regenerar con `--desde silver`. El build no reescribe las referencias
versionadas: los resultados de cada carga se guardan en su versión.

## 2. Ejecutar la aplicación

```bash
python3.14 -m venv apps/api/.venv
apps/api/.venv/bin/python -m pip install -e apps/api
npm --prefix apps/web ci
npm --prefix apps/web run dev        # web + API (solo web: run dev:web)
```

Abre `http://127.0.0.1:3000` (no `localhost`, para conservar la cookie de ChatGPT).
La API sirve la carga Gold aprobada en el catálogo. Una carga nueva se activa al
reiniciarla, y `/api/health` muestra su `load_id`.

## Documentación

- Producto y diseño: [PRODUCT.md](PRODUCT.md), [DESIGN.md](DESIGN.md)
- Silver: [contrato](data/silver/README.md), [contrato analítico](docs/silver-contract.md), [revisión](docs/silver-review.md)
- Pipeline local: [operación en macOS y Windows](docs/pipeline-local.md)
- Gold: [contrato](docs/gold-contract.md), [catálogo](docs/GOLD_CATALOG.md), [guía de dominio](docs/gold-domain-guide.md), [verificación](docs/gold-verification.md)

Límites: un informe no es un hecho verificado; hay duplicados pendientes, sesgos
por fuente y época, y parte de los valores procede de evidencia externa.
