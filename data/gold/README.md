# Gold

Modelo analítico de solo lectura sobre Silver v6, base del data agent propio.
Las bases y los informes generados no se versionan; el código, los catálogos
semánticos, las consultas certificadas y el set de evaluación sí.

| Archivo generado | Contenido |
|---|---|
| `ufo_gold.db` | Modelo Gold: `fact_report`, `report_model_output`, `fact_event`, `event_report`, dimensiones `dim_*` y agregados `agg_*`. |
| `ufo_gold.manifest.json` | `gold_version`, `load_id`, fecha, SHA-256 de Silver, Bronze y Gold, hash de definiciones, filas por tabla y totales. |
| `silver.readiness.json` | Resultado de `check_silver_ready.py` sobre el snapshot exacto leído (no sustituye el informe de Silver). |
| `serving/ufo_gold_serving.db` | Caché de servicio indexada y de solo lectura con el catálogo embebido; su manifiesto fija `cache_version` y SHA-256. |
| `ufo_gold.verification.json` | Verificación independiente desde Silver, por `load_id`. |
| `evals/<load_id>.json` | Resultados del set de evaluación y deriva respecto de cargas anteriores. |
| `ufo_gold.readiness.json` | Puerta de aceptación: `ready_for_agent`. |
| `.history/<sha256>/` | Salida Gold anterior y su manifiesto, archivados antes de publicar una nueva. |

Construcción completa, en este orden:

```bash
python3.14 scripts/build_gold.py
python3.14 scripts/discover_gold.py
python3.14 scripts/gold_query.py certify
python3.14 scripts/verify_gold_independent.py --write-references
python3.14 scripts/run_gold_evals.py
python3.14 scripts/check_gold_ready.py
```

Ver el [contrato Gold](../../docs/gold-contract.md), la
[verificación](../../docs/gold-verification.md) y la
[guía de dominio](../../docs/gold-domain-guide.md).
