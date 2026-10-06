# Tamizaje y Orientación UPY

Aplicación local para procesar por lote respuestas exportadas de Microsoft
Forms. El instrumento orienta el seguimiento institucional; no produce
diagnósticos psicológicos ni clínicos.

## Requisitos

- Python 3.12
- Una computadora institucional con cifrado de disco
- El repositorio configurado como privado

## Preparación

En PowerShell o una terminal ubicada en el repositorio:

```bash
python -m venv .venv
```

Activa el entorno en Windows:

```powershell
.venv\Scripts\Activate.ps1
```

O en Linux y macOS:

```bash
source .venv/bin/activate
```

Instala el proyecto y sus herramientas de desarrollo:

```bash
python -m pip install -e ".[dev]"
```

## Ejecución

```bash
python -m streamlit run app.py
```

En Windows también se puede usar `run_windows.bat` después de preparar `.venv`.
La interfaz se abre en el navegador, pero el proceso y los datos permanecen en
la computadora local.

## Verificación

```bash
python -m pytest
python -m ruff check .
```

## Fuentes de verdad

El diccionario v1.2 y los catálogos de scoring v0.2 están disponibles en
`config/`. Las áreas, pesos, respuestas corregidas, exclusiones, umbrales y
versión activa son configurables; consulta `config/README.md` antes de cambiar
una regla. Alertas, recomendaciones y dashboards permanecen como fases
posteriores.

## Confidencialidad

- No uses datos reales en commits, issues, pruebas, capturas o pull requests.
- Conserva las exportaciones originales fuera del repositorio, en almacenamiento
  institucional autorizado y restringido.
- No sincronices bases o reportes con cuentas personales.
- Cierra la aplicación antes de copiar o respaldar SQLite.
- No publiques este repositorio.

### Archivo de respuestas disponible

En el archivo actualmente alojado en `data/`:

- La línea 1 contiene los encabezados.
- Las líneas 2 a 15 corresponden a 14 registros de prueba.
- Desde la línea 16 en adelante existen datos reales, sensibles y
  confidenciales.
- Sólo el encabezado y las líneas 2 a 15 pueden utilizarse durante el desarrollo
  y las pruebas locales.
- Los datos reales no deben copiarse a `tests/fixtures/`, logs, documentación,
  capturas, mensajes, commits ni salidas de depuración.
- Si se necesita un fixture versionado, debe generarse de forma sintética o
  anonimizarse y revisarse manualmente antes de añadirlo a Git.

Los archivos CSV y XLSX ubicados en `data/` están excluidos mediante
`.gitignore`. Esta exclusión reduce el riesgo de publicación accidental, pero
no sustituye los controles institucionales de acceso, cifrado y respaldo.

## Estado y continuidad

El estado técnico detallado, las decisiones vigentes y el procedimiento para
continuar se encuentran en `docs/HANDOFF_2026-10-06.md`.
