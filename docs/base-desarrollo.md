# Base compartida de desarrollo

La revisión del issue #49 se realizó en Windows con un clon limpio de `main` en el commit `08acfcdaa33bb3550f6e7d7dc333f9871322edbc`, con Python 3.12.4 y Node.js 24.21.0.

| Componente | Archivos versionados |
| --- | --- |
| API | `apps/api/src/app/main.py` y `apps/api/pyproject.toml` |
| Web | `apps/web/src/app/page.tsx`, `apps/web/scripts/dev.mjs`, `apps/web/package.json` y `apps/web/package-lock.json` |
| Evaluación | `scripts/run_agent_evals.py`, `scripts/run_gold_evals.py`, `docs/GOLD_EVALS.json` y `apps/api/tests/test_agent_evals.py` |

## Comprobaciones en el clon

Desde la raíz del repositorio, en PowerShell:

```powershell
python -m venv apps/api/.venv
.\apps\api\.venv\Scripts\python.exe -m pip install -e './apps/api[test]'
.\apps\api\.venv\Scripts\python.exe -X utf8 scripts/run_agent_evals.py --help
npm.cmd --prefix apps/web ci
npm.cmd --prefix apps/web run typecheck
```

En Windows, la construcción de Gold para las pruebas fallaba al adjuntar la base Silver mediante una URI de SQLite. La conexión principal ahora habilita el soporte de URI para conservar `mode=ro&immutable=1` al adjuntar Silver. Las pruebas de rutas y evaluación se ejecutan con datos sintéticos:

```powershell
.\apps\api\.venv\Scripts\python.exe -X utf8 -m pytest apps/api/tests/test_routes.py apps/api/tests/test_agent_evals.py -q
```

`git ls-files -ci --exclude-standard` no devolvió archivos. `git check-ignore` confirmó las exclusiones para los siguientes ejemplos:

```powershell
git check-ignore -v data/bronze/ufo.db data/silver/ufo.db data/gold/serving/ufo_gold_serving.db data/releases.sqlite3 data/agent/chats.sqlite3 .env .env.local apps/api/.venv/Scripts/python.exe apps/web/node_modules/next/package.json apps/web/.next/build-manifest.json apps/web/test-results/results.json
```

La ejecución del evaluador con un modelo real requiere una cuenta y queda dentro del alcance del #43. El arranque de la aplicación con una muestra reproducible corresponde al #50.
