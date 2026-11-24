@echo off
setlocal
powershell.exe -NoProfile -ExecutionPolicy Bypass -File "%~dp0install_demo_windows.ps1" %*
set "demo_exit=%ERRORLEVEL%"
if not "%demo_exit%"=="0" if "%~1"=="" pause
exit /b %demo_exit%
