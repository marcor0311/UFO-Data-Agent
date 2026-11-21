# UFO Data Agent

## Fuentes de datos

La base se descarga de la [publicación original v0.17.0](https://github.com/UFOSINT/ufosint-explorer/releases/tag/v0.17.0), que integra datos de:

- UFOCAT
- UPDB
- UFO-search
- Capella / PhenomAInon

El proceso de integración está documentado en el [repositorio de origen](https://github.com/UFOSINT/ufo-dedup).

## Construir Bronze

Requisitos: Python 3.10+, `curl`, conexión a Internet y aproximadamente 1 GB libre.

Desde la raíz del repositorio:

```bash
python3 scripts/build_bronze.py
```

Descarga y verifica la base sin transformaciones en `data/bronze/ufo.db`.
