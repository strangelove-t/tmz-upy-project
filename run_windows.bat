@echo off
setlocal
cd /d "%~dp0"
title Tamizaje UPY - no cierres esta ventana

if not exist ".venv\Scripts\python.exe" (
    echo No se encontro el entorno virtual .venv.
    echo Pide apoyo al equipo de desarrollo.
    echo.
    echo Soporte: py -3.12 -m venv .venv
    echo          .venv\Scripts\python.exe -m pip install -e ".[dev]"
    pause
    exit /b 1
)

echo Tamizaje UPY se esta abriendo en el navegador...
echo Para terminar usa el boton "Salir de la aplicacion" en el menu de la izquierda.
echo.

rem headless false: el navegador se abre solo en cuanto la aplicacion esta lista.
".venv\Scripts\python.exe" -m streamlit run app.py --server.address 127.0.0.1 --server.headless false
