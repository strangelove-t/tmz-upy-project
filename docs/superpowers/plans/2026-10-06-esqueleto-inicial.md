# Esqueleto inicial Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Dejar un proyecto Python 3.12 instalable, seguro y ejecutable que replique la estructura acordada en el handoff sin implementar lógica de negocio.

**Architecture:** El proyecto usa layout `src/` con un paquete `tamizaje`, una entrada Streamlit multipágina y configuración externa versionada. Los módulos futuros sólo documentan sus responsabilidades; los catálogos conservan contratos de columnas sin inventar reglas, y los datos operativos permanecen fuera de Git.

**Tech Stack:** Python 3.12, Streamlit, Pandas, Plotly, ReportLab, Pydantic, PyYAML, Pytest, Ruff y SQLite de la biblioteca estándar.

---

### Task 1: Metadatos, seguridad y documentación

**Files:**
- Create: `pyproject.toml`
- Create: `.gitignore`
- Create: `.env.example`
- Create: `README.md`
- Create: `run_windows.bat`
- Create: `data/.gitkeep`
- Create: `exports/.gitkeep`

- [ ] **Step 1: Crear los metadatos del proyecto**

Definir en `pyproject.toml` Python `>=3.12`, setuptools con descubrimiento bajo
`src`, las seis dependencias de ejecución del handoff y los extras `pytest` y
`ruff`. Configurar Pytest con `pythonpath = ["src"]` y Ruff para Python 3.12.

- [ ] **Step 2: Proteger datos y artefactos**

Añadir a `.gitignore` entornos, cachés, secretos, SQLite, importaciones, PDFs,
manifiestos CSV, respuestas de Forms y logs. Mantener `data/` y `exports/`
mediante `.gitkeep`.

- [ ] **Step 3: Documentar instalación y operación**

Explicar en `README.md` la creación de `.venv`, `pip install -e ".[dev]"`,
`streamlit run app.py`, `pytest` y `ruff check .`, junto con las restricciones
de confidencialidad. Crear `.env.example` sin secretos.

- [ ] **Step 4: Crear el lanzador de Windows**

Hacer que `run_windows.bat` valide `.venv\Scripts\python.exe` y ejecute
`python -m streamlit run app.py`; si falta el entorno debe imprimir las órdenes
de preparación y terminar con código distinto de cero.

- [ ] **Step 5: Validar los archivos base**

Run: `git check-ignore .env data/example.db exports/example/report.pdf responses_test.xlsx`
Expected: las cuatro rutas aparecen como ignoradas.

### Task 2: Paquete y estructura de fuentes

**Files:**
- Create: `src/tamizaje/__init__.py`
- Create: `src/tamizaje/importers.py`
- Create: `src/tamizaje/validation.py`
- Create: `src/tamizaje/normalization.py`
- Create: `src/tamizaje/scoring.py`
- Create: `src/tamizaje/alerts.py`
- Create: `src/tamizaje/cases.py`
- Create: `src/tamizaje/triage.py`
- Create: `src/tamizaje/recommendations.py`
- Create: `src/tamizaje/reports.py`
- Create: `src/tamizaje/database.py`
- Create: `src/tamizaje/models.py`
- Create: `tests/test_scoring.py`

- [ ] **Step 1: Escribir la prueba de humo fallida**

```python
from tamizaje import SCORING_VERSION


def test_scoring_version_matches_handoff() -> None:
    assert SCORING_VERSION == "0.2"
```

- [ ] **Step 2: Ejecutar la prueba y confirmar RED**

Run: `python3 -m pytest tests/test_scoring.py -v`
Expected: FAIL porque `tamizaje` o `SCORING_VERSION` todavía no existe.

- [ ] **Step 3: Crear el paquete mínimo**

Definir `SCORING_VERSION = "0.2"` en `src/tamizaje/__init__.py`. Crear cada
módulo restante con un docstring que describa la responsabilidad indicada por
su nombre, sin funciones ficticias, excepciones `NotImplementedError` ni lógica.

- [ ] **Step 4: Ejecutar la prueba y confirmar GREEN**

Run: `python3 -m pytest tests/test_scoring.py -v`
Expected: `1 passed`.

### Task 3: Configuración, plantillas y referencias

**Files:**
- Create: `config/README.md`
- Create: `config/questionnaire.csv`
- Create: `config/areas.csv`
- Create: `config/scoring_options.csv`
- Create: `config/alert_rules.csv`
- Create: `config/recommendations.csv`
- Create: `config/parameters.yaml`
- Create: `templates/student_report.json`
- Create: `templates/advisor_report.json`
- Create: `references/README.md`
- Create: `tests/fixtures/synthetic_responses.csv`
- Create: `tests/test_import.py`
- Create: `tests/test_alerts.py`
- Create: `tests/test_cases.py`
- Create: `tests/test_reports.py`

- [ ] **Step 1: Crear contratos de configuración sin reglas**

Crear cada CSV con una única fila de encabezados derivada de los campos que el
handoff asigna a ese catálogo. Definir en YAML `questionnaire_version: null`,
`scoring_version: "0.2"` y los umbrales `green_min: 70`, `yellow_min: 40`.
Documentar en `config/README.md` que deben incorporarse los catálogos oficiales.

- [ ] **Step 2: Crear plantillas JSON mínimas**

Usar objetos JSON con `template_version`, `report_type` y una lista `fields`
vacía. No autorizar campos sensibles por anticipado.

- [ ] **Step 3: Reservar fixtures y suites futuras**

Crear el CSV sintético vacío sólo con encabezados administrativos no sensibles.
Crear los cuatro módulos de prueba restantes únicamente con docstrings; no usar
pruebas omitidas ni pruebas que siempre pasen.

- [ ] **Step 4: Documentar referencias ausentes**

Enumerar en `references/README.md` los dos XLSX y `questions.json` requeridos,
su origen esperado y la prohibición de sustituirlos con contenido inventado.

- [ ] **Step 5: Validar formatos estáticos**

Run: `python3 -m json.tool templates/student_report.json`
Expected: imprime JSON válido.

Run: `python3 -m json.tool templates/advisor_report.json`
Expected: imprime JSON válido.

### Task 4: Interfaz Streamlit mínima

**Files:**
- Create: `app.py`
- Create: `pages/1_Resumen.py`
- Create: `pages/2_Casos.py`
- Create: `pages/3_Grupos.py`
- Create: `pages/4_Estudiantes.py`
- Create: `pages/5_Reportes.py`

- [ ] **Step 1: Crear la entrada principal**

Configurar título y layout con `st.set_page_config`, mostrar “Tamizaje y
Orientación UPY”, el carácter local de la aplicación, `SCORING_VERSION` y el
estado sin datos. No crear entradas ni leer archivos.

- [ ] **Step 2: Crear las cinco páginas**

Cada página configura su título, describe brevemente su futura responsabilidad
y muestra que la funcionalidad está pendiente. No duplicar componentes ni
añadir navegación personalizada: Streamlit descubre `pages/` nativamente.

- [ ] **Step 3: Verificar sintaxis y estilo**

Run: `python3 -m compileall -q app.py pages src tests`
Expected: exit code 0.

Run: `python3 -m ruff check .`
Expected: `All checks passed!`.

### Task 5: Verificación integral

**Files:**
- Modify only if a verification exposes a defect in the files above.

- [ ] **Step 1: Ejecutar pruebas**

Run: `python3 -m pytest -v`
Expected: `1 passed` sin errores ni pruebas omitidas.

- [ ] **Step 2: Comprobar arranque de Streamlit**

Run: `python3 -m streamlit run app.py --server.headless true --server.port 8502`
Expected: el proceso informa una URL local y no emite traceback; terminarlo
después de la comprobación.

- [ ] **Step 3: Revisar el estado final**

Run: `git status --short`
Expected: sólo aparecen los archivos del esqueleto, el handoff y la
documentación de diseño/plan; no aparecen datos, bases, secretos ni cachés.

- [ ] **Step 4: No crear commit**

Entregar los cambios sin `git commit` y sin publicar al remoto, según el diseño
aprobado.
