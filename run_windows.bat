@echo off
setlocal
cd /d "%~dp0"

if not exist ".venv\Scripts\python.exe" (
    echo No se encontro el entorno virtual .venv.
    echo Ejecuta: py -3.12 -m venv .venv
    echo Despues: .venv\Scripts\python.exe -m pip install -e ".[dev]"
    exit /b 1
)

".venv\Scripts\python.exe" -m streamlit run app.py --server.address 127.0.0.1
