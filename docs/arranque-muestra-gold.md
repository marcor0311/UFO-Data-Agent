# Arrancar con una muestra Gold

La muestra usa los datos sintéticos de las pruebas de API. Puedes comprobar
la salud de la API y explorar «Informes por fuente» sin descargar bases de
datos ni iniciar sesión. Necesitas Python 3.11 o superior con SQLite, Node.js
20.9 o superior y acceso a los registros de paquetes para instalar las dependencias.

## Instalar Python y Node.js

Si ya tienes ambos, continúa con el arranque. Para probar en Windows Sandbox
x64, copia el repositorio dentro del Sandbox y haz doble clic en
`install_demo_windows.cmd`. También puedes ejecutarlo en PowerShell desde la raíz:

```powershell
.\install_demo_windows.cmd
```

El comando aplica la política de ejecución solo al proceso de PowerShell que
inicia el instalador. El script descarga los instaladores oficiales, verifica
su firma y arranca la muestra. Requiere acceso a Internet dentro del Sandbox.

En Debian y Ubuntu (x64 o ARM64):

```sh
bash scripts/install_demo_linux.sh
```

El script instala Python y el soporte para entornos virtuales con `apt`,
descarga Node.js 22 para el usuario actual y arranca la muestra.

## Arrancar la muestra

Si ya tienes Python y Node.js en el `PATH`, puedes arrancar directamente con
los comandos siguientes. Los instaladores de arriba ya incluyen este paso.

Desde la raíz de un clon limpio, en PowerShell:

```powershell
python scripts/run_demo.py
```

En macOS o Linux:

```sh
python3 scripts/run_demo.py
```

El lanzador prepara `apps/api/.venv`, instala las dependencias de API y web,
genera o reutiliza la muestra en `data/demo/` y arranca ambos servicios. Configura
`AGENT_GOLD_SERVING` y `AGENT_CERTIFIED_QUERIES` solo para los procesos que inicia.
Verifica `/api/health` y el ejemplo público antes de imprimir el enlace al gráfico.
Deja la terminal abierta mientras usas la app y pulsa `Ctrl+C` para detenerla.
Para verificar el arranque y detener los servicios automáticamente, añade `--check`.
Para regenerar la muestra, mueve `data/demo/` y vuelve a ejecutar el lanzador.

## Verificar el resultado

1. Abre [la salud de la API](http://127.0.0.1:8000/api/health). Debe devolver HTTP 200 y `"status": "ok"`.
2. Abre [el agente](http://127.0.0.1:3000/agent), entra en **Explorar datos → Consultas de ejemplo** y abre **Informes por fuente**. El resultado debe mostrar un gráfico de barras con datos sintéticos. La consulta también se puede comprobar en [el endpoint público del ejemplo](http://127.0.0.1:8000/api/agent/certified/CQ_TEST_SOURCES).

Si la página no abre, revisa que el lanzador siga activo, que se hayan
iniciado ambos servicios y que los puertos estén libres. Puedes cambiarlos con
`AGENT_DEV_WEB_PORT` y `AGENT_DEV_API_PORT` antes de arrancar.

Si la API informa que Gold no está disponible, comprueba que existen la base de
servicio, su manifiesto junto a ella y `certified_queries.json`, y que ambas
variables apuntan a archivos de la misma muestra. Reinicia los servicios
después de cambiar las variables.

## Usar la carga completa

En Windows, detén la demo y ejecuta desde la raíz:

```powershell
.\run_full_windows.cmd
```

El comando usa las dependencias de la app ya instaladas. Ejecuta `build_all.py`
y, si el pipeline termina correctamente, arranca la API y la web con la carga
Gold aprobada. Las variables de la demo se limpian solo para ese arranque.

Para hacerlo manualmente, sigue los pasos de abajo.

Detén el lanzador. Si definiste `AGENT_GOLD_SERVING` o `AGENT_CERTIFIED_QUERIES`
manualmente, elimina esas variables de la sesión. Construye o selecciona una carga
aprobada según la [guía del pipeline local](pipeline-local.md) y vuelve a ejecutar
`npm --prefix apps/web run dev` (`npm.cmd` en PowerShell). La API tomará la carga
aprobada del catálogo de versiones.
