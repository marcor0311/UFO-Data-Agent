# Arrancar con una muestra Gold

La muestra usa los datos sintéticos de las pruebas de API. Puedes comprobar
la salud de la API y explorar «Informes por fuente» sin descargar bases de
datos ni iniciar sesión. Necesitas Python 3.11 o superior con SQLite, Node.js
20.9 o superior y acceso a los registros de paquetes para la instalación inicial.

Desde la raíz de un clon limpio, en PowerShell:

```powershell
python -m venv apps/api/.venv
.\apps\api\.venv\Scripts\python.exe -m pip install -e apps/api
npm.cmd --prefix apps/web ci
python scripts/build_demo.py
$env:AGENT_GOLD_SERVING = (Resolve-Path data/demo/serving/ufo_gold_serving.db).Path
$env:AGENT_CERTIFIED_QUERIES = (Resolve-Path data/demo/certified_queries.json).Path
npm.cmd --prefix apps/web run dev
```

En macOS o Linux:

```sh
python3 -m venv apps/api/.venv
apps/api/.venv/bin/python -m pip install -e apps/api
npm --prefix apps/web ci
python3 scripts/build_demo.py
export AGENT_GOLD_SERVING="$PWD/data/demo/serving/ufo_gold_serving.db"
export AGENT_CERTIFIED_QUERIES="$PWD/data/demo/certified_queries.json"
npm --prefix apps/web run dev
```

`build_demo.py` genera la muestra y sus consultas certificadas en `data/demo/`,
una carpeta ignorada por Git. Puedes omitir ese comando si ya tienes una muestra
válida. Para regenerarla, mueve esa carpeta y vuelve a ejecutar el script.

## Verificar el resultado

1. Abre [la salud de la API](http://127.0.0.1:8000/api/health). Debe devolver HTTP 200 y `"status": "ok"`.
2. Abre [el agente](http://127.0.0.1:3000/agent), entra en **Explorar datos → Consultas de ejemplo** y abre **Informes por fuente**. El resultado debe mostrar un gráfico de barras con datos sintéticos. La consulta también se puede comprobar en [el endpoint público del ejemplo](http://127.0.0.1:8000/api/agent/certified/CQ_TEST_SOURCES).

Si la página no abre, revisa que `npm run dev` siga activo, que se hayan
iniciado ambos servicios y que los puertos estén libres. Puedes cambiarlos con
`AGENT_DEV_WEB_PORT` y `AGENT_DEV_API_PORT` antes de arrancar.

Si la API informa que Gold no está disponible, comprueba que existen la base de
servicio, su manifiesto junto a ella y `certified_queries.json`, y que ambas
variables apuntan a archivos de la misma muestra. Reinicia los servicios
después de cambiar las variables.

## Usar la carga completa

Detén los servicios y abre una terminal nueva o elimina de la sesión
`AGENT_GOLD_SERVING` y `AGENT_CERTIFIED_QUERIES`. Construye o selecciona una carga
aprobada según la [guía del pipeline local](pipeline-local.md) y vuelve a ejecutar
`npm --prefix apps/web run dev` (`npm.cmd` en PowerShell). La API tomará la carga
aprobada del catálogo de versiones.
