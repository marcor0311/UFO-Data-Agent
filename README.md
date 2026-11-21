# UFO Data Agent

Base reproducible para el Data Agent. La capa **Bronze** conserva el snapshot
público de avistamientos exactamente como fue publicado: sin limpiar, completar,
deduplicar ni modificar tablas o columnas. Silver y Gold se construirán a partir
de esta base en etapas posteriores.

## Crear la base con un comando

Requisitos: Python 3.10+, `curl`, conexión a Internet y aproximadamente 1 GB libre.
No requiere instalar paquetes de Python ni clonar repositorios adicionales.

Desde la raíz del repositorio:

```bash
python3 scripts/build_bronze.py
```

El comando descarga la publicación fija **v0.17.0**, verifica tamaño y SHA-256,
integridad SQLite, relaciones y conteos esperados. Termina con código 0 si pasa
todos los controles y código 1 si falla.

Genera localmente:

```text
data/bronze/
├── ufo.db                        # Snapshot oficial sin transformaciones
└── ufo.validation.json    # Procedencia, esquema, conteos y validación
```

Si la base ya existe y coincide con el archivo oficial, la reutiliza y vuelve
a validarla. Las descargas interrumpidas se conservan como `.part` y se reanudan
al repetir el comando. Si encuentra una base distinta, la conserva y falla;
no la sobrescribe. Una descarga que no coincide con el tamaño o SHA-256
esperados permanece como `.part` y no se acepta como Bronze.

Para verificar sin descargar:

```bash
python3 scripts/build_bronze.py --verify-only
```

El script resuelve sus rutas respecto al repositorio, aunque se ejecute desde
otro directorio. `--database RUTA` permite elegir otro destino.

## Contenido y límites

Fuente: [publicación original v0.17.0](https://github.com/UFOSINT/ufosint-explorer/releases/tag/v0.17.0).
El archivo oficial ocupa **733.192.192 bytes**. La versión, URL, SHA-256 y los
conteos esperados se fijan en [el manifiesto](config/bronze.json).

| Fuente de importación | Avistamientos |
| --- | ---: |
| UFOCAT | 320.412 |
| UPDB | 296.956 |
| UFO-search | 54.751 |
| Capella | 30.453 |
| **Total** | **702.572** |

La base contiene diez tablas: `sighting`, `sighting_analysis`, `location`,
`source_database`, `source_origin`, `source_collection`, `duplicate_candidate`,
`facility`, `nuclear_encounter` y `crash_retrieval`.

- `sighting` tiene 99 columnas: 9 completas, 57 con cobertura parcial y 33 vacías.
  Los vacíos se conservan; no equivalen a ceros.
- `description`, `summary`, `notes` y `raw_json` no se publican en `sighting`.
  `has_description` indica que había texto en el corpus original; no contiene
  ese relato. Esta base no permite reconstruir los textos privados.
- Hay 493.879 pares de coordenadas no nulos, de los cuales 493.845 están dentro
  de los límites geográficos. También existen 8 pares parciales y 22 fechas
  UFOCAT `0019-...` asociadas a un sentinela de siglo. Bronze conserva esos valores.
- La clave de un avistamiento es `sighting.id`. No usar `source_record_id`
  como clave única: UFOCAT reutiliza identificadores.
- Los 243.318 pares de `duplicate_candidate` son candidatos a revisión,
  no instrucciones para borrar registros.

La validación acredita que tenemos la publicación oficial completa; no acredita
la exactitud o veracidad de cada avistamiento. Las correcciones corresponden a
capas posteriores y deben preservar Bronze.

## Consultar Bronze

Abrir la base en modo de solo lectura para evitar modificar el snapshot:

```python
from pathlib import Path
import sqlite3

path = Path("data/bronze/ufo.db").resolve()
with sqlite3.connect(path.as_uri() + "?mode=ro", uri=True) as db:
    total = db.execute("SELECT COUNT(*) FROM sighting").fetchone()[0]
    print(total)  # 702572
```

## Qué se guarda en Git

Se versionan el script, el manifiesto, las pruebas y esta documentación.
`data/` está excluido de Git: cada integrante genera su copia con el mismo
comando, sin subir el archivo de aproximadamente 700 MiB al repositorio.

Para ejecutar las pruebas del proceso de descarga y validación:

```bash
python3 -m unittest discover -s tests -v
```
