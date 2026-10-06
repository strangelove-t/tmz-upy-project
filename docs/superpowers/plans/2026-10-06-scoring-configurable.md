# Motor de scoring configurable Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [x]`) syntax for tracking.

**Goal:** Calcular y persistir las nueve áreas mediante catálogos versionados, sin reglas de negocio codificadas en Python.

**Architecture:** Un cargador estricto compone la configuración activa desde YAML y CSV. Un motor puro transforma respuestas por código en resultados de área; una capa SQLite persiste esos resultados de forma versionada y la importación invoca ambas dentro de su transacción.

**Tech Stack:** Python 3.12, `csv`, `dataclasses`, `decimal`, `sqlite3`, PyYAML, Pydantic, Pytest y Ruff.

---

## Reglas de ejecución

- No crear commits.
- No leer respuestas reales; el PDF canónico y el handoff son las fuentes.
- Usar TDD y fixtures enteramente sintéticos.
- No añadir dependencias.

### Task 1: Contrato y validación de configuración

**Files:**
- Create: `src/tamizaje/scoring_config.py`
- Modify: `tests/test_scoring.py`

- [x] Escribir pruebas RED para cargar versión activa, áreas, reactivos y opciones.
- [x] Probar rechazo de versión ausente, duplicados normalizados, referencias
  inexistentes, pesos no positivos, valores fuera de escala, umbrales fuera de
  orden y conteos distintos a `ExpectedItemCount`.
- [x] Implementar modelos inmutables y `load_scoring_config(config_dir)` con
  mensajes que sólo expongan archivo, fila y códigos.
- [x] Ejecutar `.venv/bin/python -m pytest tests/test_scoring.py -v` hasta GREEN.

### Task 2: Poblar los catálogos v0.2

**Files:**
- Modify: `config/parameters.yaml`
- Modify: `config/areas.csv`
- Create: `config/area_items.csv`
- Modify: `config/scoring_options.csv`
- Modify: `config/README.md`

- [x] Declarar las nueve áreas, sus 64 reactivos, peso `1`, conteo mínimo igual
  al esperado y umbrales `70/40`.
- [x] Registrar opciones directas, invertidas y especiales por `QuestionCode`.
- [x] Registrar `CF05 / No aplica` con `IncludeInAverage=false` y valor vacío.
- [x] Validar contra el PDF canónico y el handoff: 64 reactivos, nueve áreas,
  códigos únicos por versión y cobertura completa de opciones.
- [x] Añadir una prueba que cargue los catálogos reales y confirme los conteos
  esperados sin leer el CSV de respuestas.

### Task 3: Motor puro de cálculo

**Files:**
- Modify: `src/tamizaje/scoring.py`
- Modify: `tests/test_scoring.py`

- [x] Escribir pruebas RED para promedio ponderado, normalización, umbrales
  exactos, inversión, exclusión y área incompleta.
- [x] Implementar `score_responses(responses, config)` y `AreaResult` sin códigos,
  umbrales ni valores de respuesta embebidos.
- [x] Representar incidencias sólo con `QuestionCode` y tipo de error.
- [x] Confirmar que el resultado contiene nueve áreas y ningún puntaje global.
- [x] Ejecutar las pruebas hasta GREEN.

### Task 4: Persistencia versionada

**Files:**
- Modify: `src/tamizaje/database.py`
- Modify: `tests/test_scoring.py`
- Modify: `tests/test_import.py`

- [x] Escribir prueba RED del esquema `area_results` y clave compuesta por envío,
  área y versión.
- [x] Implementar la tabla con precisión numérica sin redondeo de presentación.
- [x] Implementar `persist_area_results` para reemplazar transaccionalmente sólo
  la misma versión.
- [x] Probar coexistencia de versiones y rollback ante fallo.
- [x] Ejecutar pruebas de scoring e importación hasta GREEN.

### Task 5: Integración controlada con importación

**Files:**
- Modify: `src/tamizaje/database.py`
- Modify: `app.py`
- Modify: `tests/test_import.py`
- Modify: `tests/test_app.py`

- [x] Escribir prueba RED: una importación sintética completa produce nueve
  resultados `0.2` dentro de la misma transacción.
- [x] Cargar configuración al iniciar la app y bloquear importación si es
  inválida, sin mostrar respuestas.
- [x] Pasar la configuración a `import_preview`, calcular cada envío después de
  insertar respuestas y persistir resultados antes de confirmar la transacción.
- [x] Probar que un error de scoring revierte importación, alumno, envío,
  respuestas y resultados.
- [x] Ejecutar pruebas de importación e interfaz hasta GREEN.

### Task 6: Documentación y verificación

**Files:**
- Modify: `docs/Handoff_Tamizaje_UPY_App_Local.md`
- Modify: `docs/superpowers/plans/2026-10-06-scoring-configurable.md`

- [x] Documentar contrato, versión activa, cambio de parámetros y política de no
  sobrescritura histórica.
- [x] Ejecutar `.venv/bin/python -m pytest -v`.
- [x] Ejecutar `.venv/bin/ruff check .`.
- [x] Ejecutar `.venv/bin/python -m compileall -q app.py pages src tests`.
- [x] Arrancar Streamlit en modo headless y detenerlo.
- [x] Confirmar que no existe `data/tamizaje.db` y que no se importaron datos
  reales.
