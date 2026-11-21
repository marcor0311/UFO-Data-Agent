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
