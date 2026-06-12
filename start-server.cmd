@echo off
setlocal

set "PYTHON="
for /f "delims=" %%I in ('where python 2^>nul') do if not defined PYTHON set "PYTHON=%%I"

if not defined PYTHON (
  set "PYTHON=C:\Users\narcan\.cache\codex-runtimes\codex-primary-runtime\dependencies\python\python.exe"
)

if not exist "%PYTHON%" (
  echo Python 3.12 or newer is required.
  pause
  exit /b 1
)

cd /d "%~dp0"
"%PYTHON%" server.py

if errorlevel 1 pause
endlocal
