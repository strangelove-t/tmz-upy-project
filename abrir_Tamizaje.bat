@echo off
title Tamizaje UPY
cd /d "%~dp0"

if not exist ".venv\Scripts\python.exe" (
    echo ERROR: No se encontro el entorno virtual .venv
    pause
    exit /b 1
)

call ".venv\Scripts\activate.bat"
call ".\run_windows.bat"

if errorlevel 1 pause
