@echo off
setlocal
pushd "%~dp0..\.." || exit /b 1

rem Use the same Python environment as the development server.
if not exist "apps\api\.venv\Scripts\python.exe" (
    echo [Carga completa] Falta el entorno virtual de la API. Instala las dependencias segun la guia.
    popd
    exit /b 1
)
if not exist "apps\web\node_modules\.bin\next.cmd" (
    echo [Carga completa] Faltan las dependencias de la web. Ejecuta npm.cmd --prefix apps/web ci.
    popd
    exit /b 1
)
where npm.cmd >nul 2>&1 || set "PATH=%ProgramFiles%\nodejs;%PATH%"
where npm.cmd >nul 2>&1 || (
    echo [Carga completa] No se encuentra npm.cmd. Instala Node.js o abre una terminal nueva.
    popd
    exit /b 1
)

set "AGENT_GOLD_SERVING="
set "AGENT_CERTIFIED_QUERIES="

echo [Carga completa] Construyendo Bronze, Silver y Gold...
"apps\api\.venv\Scripts\python.exe" -X utf8 scripts/build_all.py
set "full_exit=%ERRORLEVEL%"
if not "%full_exit%"=="0" (
    echo [Carga completa] Fallo el pipeline. La API y la web no se iniciaron.
    popd
    exit /b %full_exit%
)

echo [Carga completa] Iniciando la API y la web con la carga Gold aprobada...
call npm.cmd --prefix apps/web run dev
set "full_exit=%ERRORLEVEL%"
popd
exit /b %full_exit%
