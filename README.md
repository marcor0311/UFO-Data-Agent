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

Descarga y verifica la base sin transformaciones en `data/bronze/ufo.db`.
