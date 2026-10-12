# Condiciones sensibles y reportes comprensibles Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Mostrar una síntesis configurable de condiciones y apoyos en Inicio, Casos y Estudiantes, permitir su inclusión explícita sólo en el expediente para tutor y hacer ambos PDF comprensibles.

**Architecture:** `sensitive_summary.py` será la única capa que interpreta respuestas `ND`, `SE`, `AP` y `CF` mediante YAML validado; las páginas y el generador de reportes consumirán su resultado inmutable. El aviso será una proyección informativa separada de `alerts` y `cases`; la opción sensible viajará explícitamente hasta el PDF y quedará auditada.

**Tech Stack:** Python 3.12+, SQLite, Pydantic, PyYAML, Streamlit 1.65, ReportLab, pandas y pytest; sin dependencias nuevas.

**Design:** `docs/superpowers/specs/2026-10-12-condiciones-sensibles-y-reportes-comprensibles-design.md`

---

### Task 1: Configuración y modelo de síntesis sensible

**Files:**
- Create: `config/sensitive_summary.yaml`
- Create: `src/tamizaje/sensitive_summary.py`
- Create: `tests/test_sensitive_summary.py`
- Modify: `src/tamizaje/models.py`

- [ ] **Step 1: Write failing configuration tests**

Crear fixtures sintéticos y exigir carga estricta, orden estable y rechazo de
códigos inexistentes:

```python
def test_loads_four_sensitive_categories(project_config_dir):
    config = load_sensitive_config(project_config_dir, questionnaire())
    assert [item.code for item in config.categories] == [
        "neurodevelopment", "mental_health", "personality", "physical_health"
    ]


def test_rejects_non_sensitive_question(tmp_path):
    write_config(tmp_path, trigger="PA01")
    with pytest.raises(SensitiveConfigError, match="pregunta sensible"):
        load_sensitive_config(tmp_path, questionnaire())
```

- [ ] **Step 2: Run tests to verify RED**

Run: `.venv/bin/pytest tests/test_sensitive_summary.py -v`
Expected: FAIL porque el módulo y el archivo no existen.

- [ ] **Step 3: Add validated configuration types**

Implementar modelos inmutables con Pydantic:

```python
class SensitiveField(BaseModel):
    model_config = ConfigDict(frozen=True)
    question_code: str
    label: str
    role: Literal[
        "diagnosis", "professional", "impact", "treatment",
        "prior_support", "requested_support", "recommendation"
    ]


class SensitiveCategory(BaseModel):
    model_config = ConfigDict(frozen=True)
    code: str
    label: str
    trigger_question: str
    affirmative_values: tuple[str, ...]
    fields: tuple[SensitiveField, ...]


class SensitiveConfig(BaseModel):
    model_config = ConfigDict(frozen=True)
    version: str
    categories: tuple[SensitiveCategory, ...]
```

`load_sensitive_config()` debe normalizar valores afirmativos y comprobar que
todos los códigos existen y tienen `is_sensitive=True` en el catálogo.

- [ ] **Step 4: Define all four categories in YAML**

Registrar los disparadores `ND01`, `SE01`, `AP01`, `CF01` y mapear los campos
aprobados de `ND02`–`ND07`, `SE02`–`SE08`, `AP02`–`AP04` y `CF02`–`CF09` a sus
roles. Usar etiquetas institucionales, no nombres clínicos inferidos.

- [ ] **Step 5: Run tests and commit**

Run: `.venv/bin/pytest tests/test_sensitive_summary.py -v`
Expected: PASS.

```bash
git add config/sensitive_summary.yaml src/tamizaje/sensitive_summary.py src/tamizaje/models.py tests/test_sensitive_summary.py
git commit -m "feat: add configurable sensitive summary model"
```

### Task 2: Construcción de la síntesis y avisos informativos

**Files:**
- Modify: `src/tamizaje/sensitive_summary.py`
- Modify: `src/tamizaje/repository.py`
- Modify: `tests/test_sensitive_summary.py`
- Modify: `tests/test_pages.py`

- [ ] **Step 1: Write failing synthesis tests**

Cubrir activación consolidada, datos parciales y separación de riesgo:

```python
def test_builds_one_consolidated_summary(imported_sensitive_submission):
    summary = build_sensitive_summary(connection, submission_id, config)
    assert summary.has_sensitive_declaration
    assert [item.code for item in summary.categories] == [
        "neurodevelopment", "physical_health"
    ]
    assert summary.requested_support


def test_diagnosis_without_affirmative_trigger_requires_review(imported):
    summary = build_sensitive_summary(connection, submission_id, config)
    assert summary.has_sensitive_declaration
    assert summary.requires_review


def test_summary_does_not_change_cases_or_alerts(imported):
    before = counts(connection, "cases", "alerts", "area_results")
    build_sensitive_summary(connection, submission_id, config)
    assert counts(connection, "cases", "alerts", "area_results") == before
```

- [ ] **Step 2: Run tests to verify RED**

Run: `.venv/bin/pytest tests/test_sensitive_summary.py -v`
Expected: FAIL por funciones de construcción inexistentes.

- [ ] **Step 3: Implement immutable summaries**

Añadir contratos explícitos:

```python
@dataclass(frozen=True)
class SensitiveCategorySummary:
    code: str
    label: str
    fields: tuple[tuple[str, str], ...]
    requires_review: bool


@dataclass(frozen=True)
class SensitiveSummary:
    categories: tuple[SensitiveCategorySummary, ...]
    requested_support: bool
    current_impact: bool
    config_version: str

    @property
    def has_sensitive_declaration(self) -> bool:
        return bool(self.categories)

    @property
    def requires_review(self) -> bool:
        return any(item.requires_review for item in self.categories)
```

Consultar únicamente `responses` para el envío. Omitir respuestas vacías y
negativas; si el disparador es afirmativo sin detalle, producir
`("Condición", "Declarada; detalle no especificado")`.

- [ ] **Step 4: Add repository projection for current submissions**

Crear `sensitive_notices_frame(connection, config)` con columnas
`submission_id`, `student_name`, `group_name`, `category_labels`,
`requested_support`, `requires_review` y `case_id`. Debe incluir envíos vigentes
sin caso y hacer como máximo una fila por envío.

- [ ] **Step 5: Run focused regression tests and commit**

Run: `.venv/bin/pytest tests/test_sensitive_summary.py tests/test_pages.py -v`
Expected: PASS sin cambios en prioridades existentes.

```bash
git add src/tamizaje/sensitive_summary.py src/tamizaje/repository.py tests/test_sensitive_summary.py tests/test_pages.py
git commit -m "feat: derive informational sensitive notices"
```

### Task 3: Inicio y Casos

**Files:**
- Modify: `pages/1_Resumen.py`
- Modify: `pages/2_Casos.py`
- Modify: `src/tamizaje/ui.py`
- Modify: `tests/test_pages.py`

- [ ] **Step 1: Write failing page tests**

```python
def test_home_counts_sensitive_notices_without_raising_priority(sensitive_db):
    app = run_page("1_Resumen.py")
    metric = next(m for m in app.metric if m.label == "Información declarada por revisar")
    assert metric.value == "2"
    assert operational_case_order(sensitive_db) == original_case_order(sensitive_db)


def test_cases_lists_informational_student_without_risk_case(sensitive_db):
    app = run_page("2_Casos.py")
    assert any(h.value == "Avisos informativos" for h in app.subheader)
    assert "Neurodivergencia" in app.dataframe[0].value["Categorías"].iloc[0]
    assert not dataframe_contains_diagnosis(app.dataframe[0].value)
```

- [ ] **Step 2: Run tests to verify RED**

Run: `.venv/bin/pytest tests/test_pages.py -k 'sensitive or informational' -v`
Expected: FAIL porque las superficies no existen.

- [ ] **Step 3: Add neutral shared renderer**

En `ui.py`, añadir `show_sensitive_summary(summary)` que renderice tarjetas por
categoría y el texto fijo de no diagnóstico. No usar colores del semáforo ni
mostrar valores vacíos.

- [ ] **Step 4: Add Inicio metric and Casos section**

Inicio mostrará una quinta métrica y enlace a Casos. Casos mostrará
**Avisos informativos** separado de la tabla operativa. En la tabla de casos,
añadir `Información sensible` con Sí/No; al abrir un caso, añadir la pestaña
**Condiciones y apoyos**. Un aviso sin caso debe poder abrir su detalle sin
crear o actualizar un caso.

- [ ] **Step 5: Run page tests and commit**

Run: `.venv/bin/pytest tests/test_pages.py -v`
Expected: PASS, incluida la prioridad previa.

```bash
git add pages/1_Resumen.py pages/2_Casos.py src/tamizaje/ui.py tests/test_pages.py
git commit -m "feat: show neutral health notices in daily workflow"
```

### Task 4: Condiciones y apoyos en Estudiantes

**Files:**
- Modify: `pages/4_Estudiantes.py`
- Modify: `tests/test_pages.py`

- [ ] **Step 1: Write failing privacy tests**

```python
def test_student_record_has_structured_sensitive_tab(sensitive_db):
    app = run_page("4_Estudiantes.py")
    assert [tab.label for tab in app.tabs] == [
        "Resultados", "Seguimiento", "Condiciones y apoyos", "Respuestas"
    ]
    assert any("declarada" in text.value.lower() for text in app.markdown)


def test_raw_sensitive_responses_remain_closed(sensitive_db):
    app = run_page("4_Estudiantes.py")
    toggle = next(t for t in app.toggle if "sensibles" in t.label)
    assert toggle.value is False
```

- [ ] **Step 2: Run tests to verify RED**

Run: `.venv/bin/pytest tests/test_pages.py -k 'structured_sensitive or raw_sensitive' -v`
Expected: FAIL por la pestaña inexistente.

- [ ] **Step 3: Render the shared summary**

Construir la síntesis antes de cerrar la conexión y usar
`show_sensitive_summary()` en la pestaña nueva. Mostrar estado vacío cuando no
haya declaración y advertencia de revisión cuando existan contradicciones. No
cambiar la pestaña Respuestas.

- [ ] **Step 4: Run tests and commit**

Run: `.venv/bin/pytest tests/test_pages.py -v`
Expected: PASS.

```bash
git add pages/4_Estudiantes.py tests/test_pages.py
git commit -m "feat: add conditions and support to student record"
```

### Task 5: Contrato seguro del expediente para tutor

**Files:**
- Create: `templates/tutor_report.json`
- Modify: `templates/student_report.json`
- Delete: `templates/advisor_report.json`
- Modify: `src/tamizaje/reports.py`
- Modify: `tests/test_reports.py`

- [ ] **Step 1: Write failing report-boundary tests**

```python
def test_student_report_rejects_sensitive_option(imported):
    with pytest.raises(ReportError, match="alumno"):
        generate_report(connection, submission_id, engine, "student", include_sensitive=True)


def test_tutor_report_excludes_sensitive_summary_by_default(imported):
    data = build_report_data(connection, submission_id, engine, load_template("tutor"))
    assert "sensitive_summary" not in data


def test_tutor_report_can_include_whitelisted_summary(imported):
    data = build_report_data(
        connection, submission_id, engine, load_template("tutor"),
        include_sensitive=True,
    )
    assert data["sensitive_summary"].has_sensitive_declaration
    assert "Texto abierto sintético" not in repr(data)
```

- [ ] **Step 2: Run tests to verify RED**

Run: `.venv/bin/pytest tests/test_reports.py -v`
Expected: FAIL por tipo y opción inexistentes.

- [ ] **Step 3: Rename the template and add explicit option**

Crear plantilla `tutor` versión `2.0`, conservar sólo áreas `A01`–`A04` y
autorizar `sensitive_summary` como campo condicional. Cambiar firmas:

```python
def build_report_data(
    connection, submission_id, engine, template, *, include_sensitive=False
) -> dict: ...


def generate_report(
    connection, submission_id, engine, report_type, *, include_sensitive=False
) -> tuple[str, bytes]: ...
```

Rechazar la opción para `student` antes de consultar respuestas sensibles. El
nombre nuevo será `tutor_<hash>.pdf`; no migrar registros históricos `advisor`.

- [ ] **Step 4: Render the confidential section**

Cuando exista, añadir **Condiciones y apoyos declarados** y
**Confidencial — uso exclusivo de Orientación y Tutorías**. Renderizar sólo los
campos de `SensitiveSummary`; nunca respuestas crudas, alertas o notas.

- [ ] **Step 5: Run report tests and commit**

Run: `.venv/bin/pytest tests/test_reports.py -v`
Expected: PASS.

```bash
git add templates src/tamizaje/reports.py tests/test_reports.py
git commit -m "feat: add opt-in sensitive tutor report"
```

### Task 6: Auditoría, descarga individual y lote

**Files:**
- Modify: `src/tamizaje/database.py`
- Modify: `src/tamizaje/reports.py`
- Modify: `pages/5_Reportes.py`
- Modify: `tests/test_database.py`
- Modify: `tests/test_reports.py`
- Modify: `tests/test_pages.py`

- [ ] **Step 1: Write failing migration and interaction tests**

```python
def test_existing_database_adds_sensitive_export_flag(old_database):
    initialize_database(old_database)
    columns = {row[1] for row in old_database.execute("PRAGMA table_info(exports)")}
    assert "includes_sensitive_summary" in columns


def test_tutor_sensitive_toggle_defaults_false(sensitive_db):
    app = run_page("5_Reportes.py")
    choose_report(app, "Expediente para tutor")
    toggle = next(t for t in app.checkbox if "diagnósticos" in t.label)
    assert toggle.value is False
```

- [ ] **Step 2: Run tests to verify RED**

Run: `.venv/bin/pytest tests/test_database.py tests/test_reports.py tests/test_pages.py -k 'export or tutor' -v`
Expected: FAIL por columna y controles inexistentes.

- [ ] **Step 3: Add backward-compatible audit migration**

En `initialize_database()`, inspeccionar `PRAGMA table_info(exports)` y ejecutar:

```sql
ALTER TABLE exports
ADD COLUMN includes_sensitive_summary INTEGER NOT NULL DEFAULT 0
CHECK (includes_sensitive_summary IN (0, 1));
```

Ampliar `record_export(..., includes_sensitive_summary=False)` y todas sus
llamadas. Guardar sólo el booleano, nunca categorías o diagnósticos.

- [ ] **Step 4: Build individual opt-in flow**

Renombrar etiquetas a tutor. Mostrar el checkbox únicamente para `tutor`,
reiniciarlo mediante una clave ligada a `submission_id` y `report_type`, mostrar
advertencia al activarlo y pasar el valor idéntico a vista previa, PDF y
auditoría. El reporte del alumno no mostrará el control.

- [ ] **Step 5: Build batch opt-in flow**

Cambiar `export_batch(..., include_sensitive_tutor=False)`. Añadir checkbox
desactivado y confirmación adicional cuando esté activo. Actualizar manifiesto a
`expediente_tutor`; el resumen indicará cantidad de PDF sensibles sin detallar
su contenido.

- [ ] **Step 6: Run tests and commit**

Run: `.venv/bin/pytest tests/test_database.py tests/test_reports.py tests/test_pages.py -v`
Expected: PASS.

```bash
git add src/tamizaje/database.py src/tamizaje/reports.py pages/5_Reportes.py tests
git commit -m "feat: audit sensitive tutor exports"
```

### Task 7: Explicaciones y contexto de resultados

**Files:**
- Create: `config/report_content.yaml`
- Modify: `src/tamizaje/reports.py`
- Modify: `pages/5_Reportes.py`
- Modify: `tests/test_reports.py`
- Modify: `tests/test_pages.py`

- [ ] **Step 1: Write failing content tests**

```python
def test_report_explains_each_traffic_light(imported):
    data = report_data(imported, "student")
    assert set(data["traffic_light_legend"]) == {
        "Verde", "Amarillo", "Rojo", "Pendiente de revisión"
    }


def test_every_area_has_description_and_interpretation(imported):
    data = report_data(imported, "student")
    assert all(line.description for line in data["areas"])
    assert all(line.interpretation for line in data["areas"])
```

- [ ] **Step 2: Run tests to verify RED**

Run: `.venv/bin/pytest tests/test_reports.py -k 'explains or description' -v`
Expected: FAIL por campos inexistentes.

- [ ] **Step 3: Add validated presentation content**

Definir en YAML la introducción, leyenda de cuatro estados y descripción de las
nueve áreas. Validar cobertura exacta contra áreas del scoring. Construir la
interpretación a partir del estado con plantillas neutrales; una puntuación
faltante debe producir **Pendiente de revisión**, nunca `0`.

- [ ] **Step 4: Redesign PDF and preview**

Extender `AreaLine` con `description` e `interpretation`. En ReportLab, presentar
introducción, leyenda, tarjetas o filas ampliadas por área, fortalezas,
necesidades, acciones y recursos. En Streamlit, reflejar el mismo contenido con
expanders por área. Verificar saltos de página y encabezados repetibles.

- [ ] **Step 5: Run tests and commit**

Run: `.venv/bin/pytest tests/test_reports.py tests/test_pages.py -v`
Expected: PASS.

```bash
git add config/report_content.yaml src/tamizaje/reports.py pages/5_Reportes.py tests
git commit -m "feat: explain report results and actions"
```

### Task 8: Documentación, QA visual y cierre

**Files:**
- Modify: `docs/OPERACION_LOCAL.md`
- Modify: `docs/checklists/QA_UX_UI.md`
- Modify: `docs/checklists/ACEPTACION_PILOTO.md`
- Modify: `docs/HANDOFF_2026-10-08.md`
- Modify: `README.md`

- [ ] **Step 1: Update operating and privacy documentation**

Documentar diferencia entre alumno y tutor, opción apagada, confirmación por
lote, auditoría y eliminación segura de exportaciones. Añadir al diccionario de
configuración cómo cambiar disparadores y textos sin modificar código.

- [ ] **Step 2: Run automated verification**

Run:

```bash
.venv/bin/pytest -v
.venv/bin/ruff check .
.venv/bin/python -m compileall -q src tests scripts app.py pages
git diff --check
git ls-files data exports .streamlit/secrets.toml
```

Expected: toda la suite pasa; lint y compilación sin errores; el último comando
sólo lista `data/.gitkeep` y `exports/.gitkeep`.

- [ ] **Step 3: Perform synthetic PDF QA**

Generar cuatro PDF sintéticos: alumno, tutor sin síntesis, tutor con síntesis y
tutor con datos parciales. Renderizarlos a imágenes y comprobar título,
descripciones, leyenda, saltos de página, marca confidencial e inclusiones. No
usar el CSV ni la base reales.

- [ ] **Step 4: Perform local UI QA**

Ejecutar Streamlit en `127.0.0.1`, recorrer Inicio → Casos → Estudiantes →
Reportes y comprobar a 1366 × 768 que el detalle sensible no aparece en tablas,
el checkbox inicia apagado y la vista previa coincide con cada PDF.

- [ ] **Step 5: Record acceptance evidence and commit**

Dejar sin marcar únicamente las tareas presenciales de la maestra. Registrar
conteos y resultados técnicos, nunca nombres, correos o diagnósticos.

```bash
git add README.md docs
git commit -m "docs: hand off sensitive summaries and tutor reports"
```

## Final acceptance gate

- El aviso consolidado cubre `ND`, `SE`, `AP` y `CF` sin tocar prioridad.
- Un alumno sin caso de riesgo puede aparecer en Avisos informativos.
- Casos y Estudiantes presentan la misma síntesis.
- El PDF del alumno rechaza datos sensibles por contrato.
- Tutor excluye por defecto e incluye sólo tras decisión manual.
- Vista previa, PDF y auditoría coinciden.
- Los reportes explican áreas y semáforos con texto además de color.
- Ningún fixture, log, captura o commit contiene datos reales.
