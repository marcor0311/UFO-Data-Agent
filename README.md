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

Descarga la base propia del proyecto desde el release `bronze-v17`, la verifica
y la guarda en `data/bronze/v17/ufo.db`. La versión queda fijada en
`config/bronze.v17.json`; los cambios futuros se publican como versiones nuevas.
