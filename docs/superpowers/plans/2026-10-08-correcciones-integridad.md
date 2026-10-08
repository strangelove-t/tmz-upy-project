# Correcciones de integridad Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Corregir casos obsoletos, inyección de fórmulas CSV, fechas UTC y exposición de grupos pequeños sin perder historial.

**Architecture:** Se amplía el caso con un indicador calculado y migrable; las vistas sólo priorizan casos activos. La exportación y la fecha se corrigen en sus límites de salida, mientras el umbral de privacidad se aplica antes de renderizar datos individuales.

**Tech Stack:** Python 3.12, SQLite, Streamlit, pytest, stdlib `csv` y `zoneinfo`.

---

### Task 1: Ciclo de vida activo del caso

**Files:**
- Modify: `tests/test_cases.py`
- Modify: `src/tamizaje/database.py`
- Modify: `src/tamizaje/repository.py`

- [ ] **Step 1: Write the failing tests**

Agregar pruebas que importen un caso, conserven seguimiento y nota, recalculen con una regla que no coincida y verifiquen `is_active = 0`; después recalcular con la regla original y verificar reactivación. Agregar una migración sobre una tabla `cases` previa y comprobar que la columna se crea con valor `1`. Verificar mediante `cases_frame` que el caso inactivo no se prioriza.

- [ ] **Step 2: Run tests to verify they fail**

Run: `.venv/bin/pytest tests/test_cases.py -v`
Expected: FAIL porque `cases.is_active` no existe y la consulta aún incluye casos obsoletos.

- [ ] **Step 3: Write minimal implementation**

Añadir a la creación de `cases`:

```sql
is_active INTEGER NOT NULL DEFAULT 1 CHECK (is_active IN (0, 1))
```

Después de `CREATE TABLE IF NOT EXISTS`, inspeccionar `PRAGMA table_info(cases)` y ejecutar `ALTER TABLE cases ADD COLUMN is_active INTEGER NOT NULL DEFAULT 1 CHECK (is_active IN (0, 1))` sólo si falta. En `process_submission`, desactivar el caso existente cuando `case is None`; al insertar o actualizar un caso calculado, dejar `is_active = 1`. En `cases_frame`, añadir `c.is_active = 1` a la cláusula de filtrado.

- [ ] **Step 4: Run tests to verify they pass**

Run: `.venv/bin/pytest tests/test_cases.py -v`
Expected: PASS.

### Task 2: Salidas seguras y fecha configurable

**Files:**
- Modify: `tests/test_reports.py`
- Modify: `tests/test_recommendations.py`
- Modify: `src/tamizaje/models.py`
- Modify: `src/tamizaje/reports.py`
- Modify: `config/parameters.yaml`

- [ ] **Step 1: Write the failing tests**

Agregar una prueba de lote con nombre y correo que comiencen con caracteres de fórmula y exigir que ambos inicien con `'` en el CSV. Agregar una prueba de configuración que rechace una zona inválida. Sustituir el reloj del módulo de reportes por una fecha UTC cercana al cambio de día y comprobar que la fecha corresponde a `America/Mexico_City`.

- [ ] **Step 2: Run tests to verify they fail**

Run: `.venv/bin/pytest tests/test_reports.py tests/test_recommendations.py -v`
Expected: FAIL por celdas sin neutralizar y ausencia de `report_timezone`.

- [ ] **Step 3: Write minimal implementation**

Añadir `report_timezone: ZoneInfo` a `EngineConfig`, cargar `report_timezone` desde YAML mediante `ZoneInfo`, y declarar `report_timezone: America/Mexico_City`. Generar `generated_at` con `datetime.now(engine.report_timezone)`. Añadir una función privada que anteponga `'` cuando una celda no vacía empiece con `=+-@\t\r`, y aplicarla únicamente a correo y nombre en el manifiesto.

- [ ] **Step 4: Run tests to verify they pass**

Run: `.venv/bin/pytest tests/test_reports.py tests/test_recommendations.py -v`
Expected: PASS.

### Task 3: Privacidad de grupos pequeños

**Files:**
- Modify: `tests/test_pages.py`
- Modify: `pages/3_Grupos.py`

- [ ] **Step 1: Write the failing test**

Ampliar `test_small_group_aggregates_are_hidden` para exigir que, al seleccionar `G-02`, no exista ningún `st.dataframe` con estudiantes.

- [ ] **Step 2: Run test to verify it fails**

Run: `.venv/bin/pytest tests/test_pages.py::test_small_group_aggregates_are_hidden -v`
Expected: FAIL porque actualmente se muestra la tabla individual.

- [ ] **Step 3: Write minimal implementation**

Mover la construcción y renderizado de “Estudiantes priorizados” al bloque `else` que sólo se ejecuta si el grupo alcanza `minimum_group_size`.

- [ ] **Step 4: Run test to verify it passes**

Run: `.venv/bin/pytest tests/test_pages.py::test_small_group_aggregates_are_hidden -v`
Expected: PASS.

### Task 4: Documentación y verificación integral

**Files:**
- Modify: `docs/HANDOFF_2026-10-07.md`

- [ ] **Step 1: Update handoff**

Documentar `is_active`, la migración, neutralización CSV, `report_timezone` y que grupos pequeños no presentan datos individuales. Retirar la limitación que afirmaba que los casos sin alertas permanecían sin cambios.

- [ ] **Step 2: Run complete verification**

Run: `.venv/bin/pytest -v`
Expected: todas las pruebas aprobadas.

Run: `.venv/bin/ruff check .`
Expected: `All checks passed!`

Run: `.venv/bin/python -m compileall -q src tests app.py pages`
Expected: exit code 0.

- [ ] **Step 3: Render synthetic PDFs**

Generar ambos PDFs con datos sintéticos, usar `pdftoppm` y revisar que no haya texto cortado y que la fecha sea local.

- [ ] **Step 4: Commit**

```bash
git add config/parameters.yaml docs/HANDOFF_2026-10-07.md pages/3_Grupos.py src/tamizaje/database.py src/tamizaje/models.py src/tamizaje/reports.py src/tamizaje/repository.py tests/test_cases.py tests/test_pages.py tests/test_reports.py tests/test_recommendations.py docs/superpowers/plans/2026-10-08-correcciones-integridad.md
git commit -m "fix: harden case lifecycle and report exports"
```
