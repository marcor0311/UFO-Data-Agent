# Pipeline local Bronze → Silver → Gold

Esta guía explica cómo construir los datos en tu equipo, en macOS o en Windows,
con un solo comando: `scripts/build_all.py`. Solo necesitas Python y SQLite. Si
la Bronze ya está en el disco, el pipeline funciona sin Internet.

## 1. Instalación desde un checkout limpio

Requisitos:

- Python 3.11 o superior, con su `sqlite3` estándar.
- `git`, para clonar el repositorio. El pipeline funciona aunque `git` no esté
  instalado: el commit solo se registra como dato informativo.
- `curl`, solo para descargar Bronze la primera vez. Viene con macOS y con
  Windows 10 y versiones posteriores.
- Espacio libre en disco: unos 4 GB la primera vez (733 MB de Bronze, ~1 GB de
  Silver y ~0,9 GB de Gold con su caché), más ~2 GB por cada versión que se
  conserve. El comando calcula el espacio necesario antes de empezar y se
  detiene si no alcanza.

**macOS / Linux**

```bash
git clone https://github.com/marcor0311/UFO-Data-Agent.git
cd UFO-Data-Agent
brew install python@3.14            # si python3 --version es anterior a 3.11
python3 scripts/build_all.py
```

**Windows (PowerShell)**

```powershell
git clone https://github.com/marcor0311/UFO-Data-Agent.git
cd UFO-Data-Agent
winget install Python.Python.3.12   # si py -3.12 no existe
py -3.12 scripts\build_all.py
```

Si `python3` es anterior a 3.11 en macOS, el comando se relanza solo con el
Python más reciente que encuentre. En Windows indica el comando `py -3.12`.

## 2. Qué hace el comando

| Fase | Pasos | Publicación |
|---|---|---|
| `bronze` | Descarga Bronze o reutiliza la copia local, y comprueba tamaño, SHA-256, integridad y conteos | `data/bronze/ufo.db` (fijada por `config/bronze.json`) |
| `silver` | Construye Silver en una versión nueva y comprueba la cadena de custodia, la aceptación completa y la revisión | Promueve el par Silver + informe |
| `gold` | Comprueba la custodia y la aceptación de la Silver aprobada. Luego, en un candidato: modelo, caché de servicio, certificaciones, verificación independiente, evaluaciones y `ready_for_agent` | Promueve la carga |

Cada versión vive en un directorio inmutable con nombre único:

```
data/
  releases.sqlite3                     catálogo: versión aprobada de cada capa
  .build.lock                          bloqueo de publicación
  build.metrics.json                   métricas del último build
  bronze/ufo.db
  silver/versions/<UTC>-<pid>-<id>/    ufo.db, ufo.validation.json, ufo.readiness.json,
                                       ufo.review.json, release.json
  gold/versions/<UTC>-<pid>-<id>/      ufo_gold.db (+ manifiesto), silver.readiness.json,
                                       serving/, certified_queries.json, GOLD_EVALS.json,
                                       ufo_gold.verification.json, evals/<load_id>.json,
                                       ufo_gold.readiness.json, docs/, release.json
```

- **Promoción atómica.** Una versión solo se promueve cuando pasan todos sus
  controles, y la promoción es una sola transacción SQLite sobre
  `releases.sqlite3`. Antes de ese commit sigue vigente la versión aprobada
  anterior, aunque el proceso falle o se interrumpa.
- **Sin reemplazos.** Ningún paso sobrescribe una base que pueda tener lectores
  abiertos y la publicación no usa `os.link()`.
- **Un solo build a la vez.** Un segundo build sobre el mismo directorio de datos
  termina enseguida con el código 3 y no crea ningún candidato. Si el proceso
  muere, el sistema operativo libera el bloqueo.
- **Versiones conservadas.** Se conservan la versión vigente y la anterior de
  cada capa (`--conservar N`), además de la Silver de la que proviene cada Gold
  conservada.
- **Custodia de Silver.** Gold solo lee una Silver que cumple todo esto: no tiene
  WAL pendiente; su informe tiene `layer="silver"` y `passed` exactamente `true`;
  el SHA-256 y el tamaño del archivo coinciden con el informe; y su linaje está
  completo, apunta a la Bronze oficial y coincide con la receta vigente
  (política, código y referencias). Un informe ausente, vacío o mal formado se
  rechaza. La Bronze se comprueba por tamaño y SHA-256.
- **Sin trabajo repetido.** Todo el comando corre en un solo proceso. Cada
  archivo estable se hashea una vez y cada Silver exacta se acepta una vez. Una
  invocación nueva vuelve a verificar todo lo que reutiliza. Al final se
  muestran la duración por fase, las lecturas completas de hash y el espacio
  usado. Las mismas métricas quedan en `data/build.metrics.json`.

## 3. Opciones

```bash
python3 scripts/build_all.py --desde silver   # Silver y Gold; Bronze se reutiliza
python3 scripts/build_all.py --desde gold     # solo Gold, sobre la Silver aprobada
python3 scripts/build_all.py --solo silver    # una sola fase
python3 scripts/build_all.py --estado         # versiones aprobadas
python3 scripts/build_all.py --datos D:\ufo   # otro directorio de datos (o UFO_DATA_DIR)
python3 scripts/build_all.py --fuente-bronze /ruta/ufo.db   # Bronze desde un archivo local, sin Internet
```

`--desde gold` y `--solo gold` aplican las mismas precondiciones que el build
completo: custodia y aceptación de la Silver aprobada antes de leerla.

## 4. Referencias versionadas

El build no reescribe `config/gold/certified_queries.json`, `docs/GOLD_EVALS.json`
ni `docs/GOLD_CATALOG.*`. Los resultados de cada carga (resultados esperados de
las certificadas, respuestas de referencia de la verificación independiente,
evaluaciones y catálogo) se guardan dentro de su versión. Para actualizar los
archivos versionados a partir de la carga aprobada hay que pedirlo
explícitamente:

```bash
python3 scripts/build_all.py --actualizar-referencias
```

La actualización se niega si las consultas certificadas o las preguntas de
evaluación cambiaron después de esa carga. En ese caso, reconstruye con
`--desde gold`. Las operaciones explícitas anteriores siguen disponibles:
`gold_query.py certify` y `verify_gold_independent.py --write-references`.

## 5. Recuperación tras un fallo

1. Lee el mensaje `PIPELINE DETENIDO en “fase”`. Indica la causa y las versiones
   que siguen vigentes, que no cambian.
2. El candidato fallido se conserva para diagnosticarlo en
   `data/<capa>/versions/`. Su informe de esa fase está dentro del directorio,
   y `data/build.metrics.json` registra el error.
3. Corrige la causa y repite desde esa fase, por ejemplo
   `python3 scripts/build_all.py --desde gold`. El siguiente build correcto
   retira los candidatos huérfanos.
4. Si el mensaje es `Otro build está publicando`, espera a que termine. Si ese
   proceso ya murió, basta con repetir el comando.
5. La API sigue sirviendo la carga aprobada. Una carga nueva se activa al
   reiniciar la API. `/api/health` muestra `gold_load_id`, `serving_load_id` y
   `readiness_load_id`, que siempre coinciden.

Los archivos sueltos de antes del catálogo (`data/silver/ufo.db`,
`data/gold/ufo_gold.db`, `data/gold/serving/`) no se adoptan como vigentes. Se
pueden borrar después del primer build con versiones.

## 6. Pruebas

Las pruebas usan datos sintéticos en directorios temporales. No necesitan los
datos reales ni modifican los snapshots ni las referencias del checkout.

```bash
# macOS / Linux
python3 -m unittest discover -s tests -q
apps/api/.venv/bin/python -m pytest apps/api/tests -q
```

```powershell
# Windows (PowerShell)
py -3.12 -m unittest discover -s tests -q
py -3.12 -m venv apps\api\.venv
apps\api\.venv\Scripts\python -m pip install -e "apps/api[test]"
apps\api\.venv\Scripts\python -m pytest apps\api\tests -q
```

`tests/test_gold_evals.py` y una prueba de `apps/api/tests/test_tools.py` usan la
carga real aprobada. Si no hay ninguna, se omiten.
