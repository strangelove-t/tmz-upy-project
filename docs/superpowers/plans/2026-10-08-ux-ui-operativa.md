# UX/UI operativa Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Convertir la interfaz Streamlit existente en una herramienta operativa clara para la maestra, con Inicio orientado a pendientes, navegación por tareas y consistencia visual en las seis áreas.

**Architecture:** `app.py` se convertirá en el router autenticado mediante `st.navigation`; la importación actual se moverá a Administración y Resumen evolucionará a Inicio. `src/tamizaje/ui.py` concentrará tema y componentes visuales pequeños, mientras cada página conserva su lógica y consultas actuales.

**Tech Stack:** Python 3.12, Streamlit 1.65, pandas, Plotly, pytest y CSS mínimo embebido; sin dependencias nuevas.

**Precondition:** Completar primero `docs/superpowers/plans/2026-10-08-acceso-local-y-piloto.md` y trabajar sólo con base sintética o líneas 2–15.

---

### Task 1: Navegación y sistema visual compartido

**Files:**
- Modify: `app.py`
- Create: `pages/6_Administracion.py`
- Modify: `pages/1_Resumen.py`
- Modify: `pages/2_Casos.py`
- Modify: `pages/3_Grupos.py`
- Modify: `pages/4_Estudiantes.py`
- Modify: `pages/5_Reportes.py`
- Modify: `src/tamizaje/ui.py`
- Modify: `.streamlit/config.toml`
- Modify: `tests/test_app.py`
- Modify: `tests/test_pages.py`

- [ ] **Step 1: Write failing navigation tests**

Actualizar `test_app.py` para autenticar la sesión según el plan previo y exigir
que la entrada muestre Inicio y registre las seis páginas en este orden:

```python
def test_authenticated_app_opens_operational_home() -> None:
    app = configured_app()
    app.session_state["authenticated"] = True
    app.run()

    assert not app.exception
    assert app.title[0].value == "Inicio"
    assert list(app._registered_pages.values())[0]["page_name"] == "Inicio"
```

En `test_pages.py`, ampliar `PAGES` para incluir `6_Administracion.py` y cambiar
los nombres esperados sin perder las pruebas de acceso y ausencia de base.

- [ ] **Step 2: Run tests to verify RED**

Run: `.venv/bin/pytest tests/test_app.py tests/test_pages.py -v`
Expected: FAIL porque `app.py` todavía contiene importación y no registra Inicio.

- [ ] **Step 3: Add the shared visual primitives**

En `ui.py`, añadir funciones pequeñas y nativas:

```python
def apply_theme() -> None:
    st.markdown(
        """
        <style>
        .block-container {max-width: 1180px; padding-top: 2rem;}
        [data-testid="stMetric"] {
            background: #ffffff; border: 1px solid #dfe5ea;
            border-radius: 12px; padding: 1rem;
        }
        div[data-testid="stForm"] {
            border: 1px solid #dfe5ea; border-radius: 12px; padding: 1rem;
        }
        :focus-visible {outline: 3px solid #0b6e75; outline-offset: 2px;}
        </style>
        """,
        unsafe_allow_html=True,
    )


def page_header(title: str, description: str) -> None:
    st.title(title)
    st.caption(description)
```

Agregar a `.streamlit/config.toml` un tema claro con contraste verificable:

```toml
[theme]
primaryColor = "#0B6E75"
backgroundColor = "#F6F8FA"
secondaryBackgroundColor = "#FFFFFF"
textColor = "#172026"
```

- [ ] **Step 4: Build the authenticated navigation router**

Mover el contenido de importación y recálculo de `app.py` sin cambios
funcionales a `pages/6_Administracion.py`. Dejar `app.py` como entrada:

```python
import streamlit as st

from tamizaje.ui import apply_theme, require_authentication

st.set_page_config(page_title="Tamizaje UPY", layout="wide")
require_authentication()
apply_theme()
navigation = st.navigation(
    [
        st.Page("pages/1_Resumen.py", title="Inicio", icon=":material/home:"),
        st.Page("pages/2_Casos.py", title="Casos", icon=":material/assignment:"),
        st.Page("pages/4_Estudiantes.py", title="Estudiantes", icon=":material/school:"),
        st.Page("pages/3_Grupos.py", title="Grupos", icon=":material/groups:"),
        st.Page("pages/5_Reportes.py", title="Reportes", icon=":material/description:"),
        st.Page("pages/6_Administracion.py", title="Administración", icon=":material/settings:"),
    ]
)
navigation.run()
```

Retirar `st.set_page_config()` de las seis páginas y llamar `apply_theme()` al
ejecutarlas directamente desde pruebas. `require_context()` conservará la
protección de autenticación y datos.

- [ ] **Step 5: Run tests to verify GREEN**

Run: `.venv/bin/pytest tests/test_app.py tests/test_pages.py -v`
Expected: all passed.

- [ ] **Step 6: Commit**

```bash
git add app.py pages src/tamizaje/ui.py .streamlit/config.toml tests/test_app.py tests/test_pages.py
git commit -m "feat: add task-oriented navigation and visual system"
```

### Task 2: Inicio orientado a pendientes

**Files:**
- Modify: `pages/1_Resumen.py`
- Modify: `src/tamizaje/repository.py`
- Modify: `tests/test_pages.py`

- [ ] **Step 1: Write failing home tests**

Con la base sintética, exigir los elementos operativos:

```python
def test_home_prioritizes_daily_work(synthetic_database) -> None:
    app = run_authenticated_page("1_Resumen.py")

    labels = {metric.label for metric in app.metric}
    assert "Casos prioritarios" in labels
    assert "Solicitudes de contacto" in labels
    assert "Seguimientos pendientes" in labels
    assert "Alumnos procesados" in labels
    assert any("Siguientes casos" in header.value for header in app.subheader)
```

- [ ] **Step 2: Run test to verify RED**

Run: `.venv/bin/pytest tests/test_pages.py::test_home_prioritizes_daily_work -v`
Expected: FAIL por etiquetas y lista operativa inexistentes.

- [ ] **Step 3: Add the smallest repository query needed**

Añadir `operational_counts(connection, engine, today)` que reutilice
`cases_frame` y `area_results_frame` y devuelva sólo:

```python
{
    "priority_cases": int,
    "contact_requests": int,
    "pending_followups": int,
    "students": int,
}
```

Un seguimiento cuenta como pendiente cuando tiene fecha menor o igual a hoy y
el caso no está cerrado. No crear una clase ni una capa adicional.

- [ ] **Step 4: Redesign Inicio**

Mostrar cuatro métricas en la primera fila, hasta cinco casos priorizados en una
tabla compacta, dos gráficas accionables (casos por nivel y promedio por área) y
enlaces nativos con `st.page_link` a Casos y Estudiantes. Mantener la protección
de grupos pequeños en los agregados existentes.

- [ ] **Step 5: Run tests to verify GREEN**

Run: `.venv/bin/pytest tests/test_pages.py::test_home_prioritizes_daily_work -v`
Expected: PASS.

- [ ] **Step 6: Commit**

```bash
git add pages/1_Resumen.py src/tamizaje/repository.py tests/test_pages.py
git commit -m "feat: make home dashboard action oriented"
```

### Task 3: Flujo operativo de Casos

**Files:**
- Modify: `pages/2_Casos.py`
- Modify: `tests/test_pages.py`

- [ ] **Step 1: Write failing interaction tests**

Conservar las pruebas de prioridad y guardado existentes y añadir:

```python
def test_cases_has_clear_filters_and_work_sections(synthetic_database) -> None:
    app = run_authenticated_page("2_Casos.py")

    assert any(expander.label == "Filtrar casos" for expander in app.expander)
    assert {tab.label for tab in app.tabs} >= {
        "Motivo y alertas", "Seguimiento", "Notas"
    }
    assert any(button.label == "Guardar seguimiento" for button in app.button)
```

- [ ] **Step 2: Run test to verify RED**

Run: `.venv/bin/pytest tests/test_pages.py::test_cases_has_clear_filters_and_work_sections -v`
Expected: FAIL porque filtros y formulario están en un flujo lineal.

- [ ] **Step 3: Reorganize without changing persistence**

Mover filtros a `st.expander("Filtrar casos", expanded=False)`. Mantener la tabla
priorizada como elemento principal y reorganizar el caso seleccionado en tres
tabs: Motivo y alertas, Seguimiento y Notas. Reutilizar sin cambios
`update_case()` y `add_case_note()`. Añadir mensajes “Sin resultados para estos
filtros” y “Seguimiento actualizado” sin información personal.

- [ ] **Step 4: Run focused and regression tests**

Run: `.venv/bin/pytest tests/test_pages.py -v`
Expected: all passed, incluidas actualización, prioridad y privacidad de grupos.

- [ ] **Step 5: Commit**

```bash
git add pages/2_Casos.py tests/test_pages.py
git commit -m "feat: streamline case review workflow"
```

### Task 4: Estudiantes, Grupos y Reportes

**Files:**
- Modify: `pages/3_Grupos.py`
- Modify: `pages/4_Estudiantes.py`
- Modify: `pages/5_Reportes.py`
- Modify: `tests/test_pages.py`

- [ ] **Step 1: Write failing page-structure tests**

```python
def test_student_record_groups_information_by_task(synthetic_database) -> None:
    app = run_authenticated_page("4_Estudiantes.py")
    assert {tab.label for tab in app.tabs} >= {
        "Resultados", "Seguimiento", "Respuestas"
    }
    sensitive = next(toggle for toggle in app.toggle if "sensibles" in toggle.label)
    assert sensitive.value is False


def test_reports_separates_individual_and_batch_flows(synthetic_database) -> None:
    app = run_authenticated_page("5_Reportes.py")
    assert {tab.label for tab in app.tabs} == {"Individual", "Por lote"}
    assert any("confidencial" in warning.value.lower() for warning in app.warning)
```

Mantener `test_small_group_aggregates_are_hidden` como regresión obligatoria.

- [ ] **Step 2: Run tests to verify RED**

Run: `.venv/bin/pytest tests/test_pages.py -v`
Expected: FAIL porque Estudiantes y Reportes todavía son páginas lineales.

- [ ] **Step 3: Reorganize the three pages**

- Estudiantes: encabezado administrativo compacto y tabs Resultados,
  Seguimiento y Respuestas; el interruptor sensible permanece apagado.
- Grupos: selector y cobertura primero, escalas 0–100 consistentes y mensaje
  explicativo cuando el umbral bloquea datos.
- Reportes: tabs Individual y Por lote, vista previa antes de descargar,
  advertencia de confidencialidad en lote y confirmación de ubicación.

No cambiar consultas, lista blanca de reportes ni reglas de confidencialidad.

- [ ] **Step 4: Run focused tests to verify GREEN**

Run: `.venv/bin/pytest tests/test_pages.py tests/test_reports.py -v`
Expected: all passed.

- [ ] **Step 5: Commit**

```bash
git add pages/3_Grupos.py pages/4_Estudiantes.py pages/5_Reportes.py tests/test_pages.py
git commit -m "feat: clarify student group and report workflows"
```

### Task 5: Administración guiada y estados

**Files:**
- Modify: `pages/6_Administracion.py`
- Modify: `tests/test_app.py`
- Modify: `tests/test_pages.py`

- [ ] **Step 1: Write failing administration tests**

```python
def test_administration_separates_safe_preview_and_real_import() -> None:
    app = run_authenticated_page("6_Administracion.py")
    assert app.title[0].value == "Administración"
    assert any("modo de prueba" in info.value.lower() for info in app.info)
    assert any(expander.label == "Recalcular resultados" for expander in app.expander)
```

- [ ] **Step 2: Run test to verify RED**

Run: `.venv/bin/pytest tests/test_pages.py::test_administration_separates_safe_preview_and_real_import -v`
Expected: FAIL porque la importación conserva la presentación técnica anterior.

- [ ] **Step 3: Present import as four visible stages**

Usar encabezados Archivo, Validación, Resumen y Confirmación. Mantener el toggle
seguro activo por defecto. Mostrar la confirmación real sólo cuando el modo de
prueba esté apagado y el mapeo sea válido. Colocar recálculo dentro de
`st.expander("Recalcular resultados")` y conservar su checkbox obligatorio.

- [ ] **Step 4: Run tests to verify GREEN**

Run: `.venv/bin/pytest tests/test_app.py tests/test_pages.py -v`
Expected: all passed.

- [ ] **Step 5: Commit**

```bash
git add pages/6_Administracion.py tests/test_app.py tests/test_pages.py
git commit -m "feat: guide administrative import workflow"
```

### Task 6: QA visual, accesibilidad y aceptación

**Files:**
- Create: `docs/checklists/QA_UX_UI.md`
- Modify: `docs/checklists/ACEPTACION_PILOTO.md`
- Modify: `docs/OPERACION_LOCAL.md`
- Modify: `README.md`
- Modify: `docs/HANDOFF_2026-10-08.md`

- [ ] **Step 1: Create the QA checklist**

Incluir controles verificables para las seis páginas en 1366 × 768 y 1920 ×
1080: texto cortado, scroll horizontal, jerarquía, estados vacíos, filtros,
teclado, foco, contraste, semáforo con etiqueta, grupos pequeños, contenido
sensible cerrado y ausencia de datos reales en capturas.

- [ ] **Step 2: Run automated verification**

Run: `.venv/bin/pytest -v`
Expected: all tests passed.

Run: `.venv/bin/ruff check .`
Expected: `All checks passed!`.

Run: `.venv/bin/python -m compileall -q src tests scripts app.py pages`
Expected: exit code 0.

- [ ] **Step 3: Run visual review with synthetic data**

Iniciar la aplicación únicamente en `127.0.0.1`, usar la base sintética del
piloto, capturar las seis páginas en 1366 × 768 y 1920 × 1080, revisar todos los
estados del checklist y eliminar las capturas al concluir. No usar el CSV real
ni persistir datos de aceptación en `data/tamizaje.db`.

- [ ] **Step 4: Verify PDFs and repository hygiene**

Renderizar ambos tipos de PDF sintético con `pdftoppm`, revisar todas las páginas
y borrar temporales. Ejecutar:

```bash
git diff --check
git ls-files data exports .streamlit/secrets.toml
```

Expected: sin errores; sólo `data/.gitkeep` y `exports/.gitkeep` rastreados.

- [ ] **Step 5: Record evidence and leave institutional approval open**

Marcar únicamente checks comprobados. Mantener sin marcar la aceptación visual
de la maestra y la autorización para procesar líneas 16 en adelante.

- [ ] **Step 6: Commit**

```bash
git add README.md docs/OPERACION_LOCAL.md docs/HANDOFF_2026-10-08.md docs/checklists/ACEPTACION_PILOTO.md docs/checklists/QA_UX_UI.md
git commit -m "docs: record UX UI quality assurance"
```
