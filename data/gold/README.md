# Gold

Modelo analítico de solo lectura sobre Silver v6, base del data agent propio.
Las bases y los informes generados no se versionan en Git. Sí se versionan el
código, los catálogos semánticos, las consultas certificadas y el set de
evaluación.

Cada carga es un directorio inmutable `versions/<UTC>-<pid>-<id>/`. Solo se
publica la versión que el catálogo `data/releases.sqlite3` marca como aprobada,
después de pasar todos sus controles:

| Archivo de la versión | Contenido |
|---|---|
| `ufo_gold.db` | Modelo Gold: `fact_report`, `report_model_output`, `fact_event`, `event_report`, dimensiones `dim_*` y agregados `agg_*`. |
| `ufo_gold.manifest.json` | `gold_version`, `load_id`, fecha, SHA-256 de Silver, Bronze y Gold, hash de definiciones, filas por tabla y totales. |
| `silver.readiness.json` | Resultado de `check_silver_ready.py` sobre el snapshot exacto leído. No sustituye el informe de Silver. |
| `serving/ufo_gold_serving.db` | Caché de servicio indexada y de solo lectura, con el catálogo embebido. Su manifiesto fija `cache_version` y SHA-256. |
| `certified_queries.json` | Consultas certificadas con su resultado esperado para esta carga. |
| `ufo_gold.verification.json` | Verificación independiente desde Silver. |
| `GOLD_EVALS.json` | Set de evaluación con las respuestas de referencia calculadas para esta carga. |
| `evals/<load_id>.json` | Resultados del set de evaluación y deriva respecto de la carga anterior. |
| `ufo_gold.readiness.json` | Puerta de aceptación: `ready_for_agent`. |
| `docs/` | `GOLD_CATALOG.json`, `GOLD_CATALOG.md` y `GOLD_ENTITIES.json` de esta carga. |
| `release.json` | Lista de archivos con su SHA-256 y tamaño. El catálogo guarda su hash. |
| `build.metrics.json` | Duración por fase, lecturas de hash y espacio del build que la produjo. |

Construcción completa y publicación:

```bash
python3 scripts/build_all.py --desde gold
```

Los CLI individuales siguen disponibles. Por defecto trabajan sobre la versión
aprobada, o sobre `--version DIR`, y nunca la promueven ni la reescriben:
`build_gold.py`, `discover_gold.py`, `verify_gold_independent.py`,
`run_gold_evals.py`, `check_gold_ready.py` y `gold_query.py`. Los informes que
generan a mano quedan en `data/gold/`, fuera de las versiones.

Los archivos sueltos de antes del catálogo (`ufo_gold.db`, `serving/`,
`.history/`, `evals/`) no se adoptan como vigentes y se pueden borrar.

Ver la [operación local](../../docs/pipeline-local.md), el
[contrato Gold](../../docs/gold-contract.md), la
[verificación](../../docs/gold-verification.md) y la
[guía de dominio](../../docs/gold-domain-guide.md).
