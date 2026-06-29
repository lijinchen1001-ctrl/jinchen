@echo off
setlocal
cd /d "%~dp0"

set "CODEX_PY=C:\Users\13002\.cache\codex-runtimes\codex-primary-runtime\dependencies\python\python.exe"

if exist "%CODEX_PY%" (
  "%CODEX_PY%" "%~dp0desktop_pet.py"
  exit /b %errorlevel%
)

where python >nul 2>nul
if %errorlevel%==0 (
  python "%~dp0desktop_pet.py"
  exit /b %errorlevel%
)

echo Python was not found.
pause
