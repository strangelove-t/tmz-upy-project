from datetime import date
from pathlib import Path

import pytest
from app_helpers import configured_app, run_authenticated_page
from synthetic_forms import project_config, synthetic_rows

from tamizaje import ui
from tamizaje.database import (
    connect_database,
    import_preview,
    initialize_database,
    update_case,
)
from tamizaje.importers import preview_csv
from tamizaje.repository import operational_counts

PAGES_DIR = Path(__file__).parents[1] / "pages"
PAGES = sorted(path.name for path in PAGES_DIR.glob("*.py"))
DATA_PAGES = [name for name in PAGES if name != "6_Administracion.py"]


@pytest.fixture
def synthetic_database(tmp_path, monkeypatch):
    questionnaire, engine = project_config()
    students = [{} for _ in range(5)]
    students[1].update({"MO09": "Siempre", "DC02": "Sí"})
    students[2].update({"DC01": "Texto sintético", "SE04": "Algunas veces"})
    students[3].update({"CF05": "No aplica", "PA01": "Totalmente en desacuerdo"})
    students.append({"DG03": "G-02", "PE02": "Nada probable"})
    content = synthetic_rows(questionnaire, engine, students)
    preview = preview_csv("synthetic.csv", content, questionnaire=questionnaire)
    database_path = tmp_path / "tamizaje.db"
    connection = connect_database(database_path)
    initialize_database(connection)
    import_preview(
        connection,
        preview,
        questionnaire,
        engine.scoring,
        alert_config=engine.alerts,
        recommendations=engine.recommendations,
    )
    connection.close()
    monkeypatch.setattr(ui, "DATABASE_PATH", database_path)
    monkeypatch.setattr(ui, "EXPORTS_DIR", tmp_path / "exports")
    return database_path


def run_page(name: str, *, authenticated: bool = True):
    if authenticated:
        return run_authenticated_page(name)
    # Sin sesión se ejecuta la página directamente: su propia puerta debe
    # detenerla aunque alguien la abra sin pasar por el router.
    return configured_app(f"pages/{name}").run()


def test_all_six_pages_exist() -> None:
    assert len(PAGES) == 6


@pytest.mark.parametrize("name", PAGES)
def test_pages_require_authentication_before_reading(
    name, synthetic_database
) -> None:
    app = run_page(name, authenticated=False)

    assert not app.exception
    assert any(field.label == "Contraseña" for field in app.text_input)
    assert not app.dataframe
    assert not app.metric


@pytest.mark.parametrize("name", DATA_PAGES)
def test_pages_without_database_show_guidance(name, tmp_path, monkeypatch) -> None:
    monkeypatch.setattr(ui, "DATABASE_PATH", tmp_path / "missing.db")

    app = run_page(name)

    assert not app.exception
    assert any("Aún no hay datos" in info.value for info in app.info)
    assert not (tmp_path / "missing.db").exists()


@pytest.mark.parametrize("name", PAGES)
def test_pages_render_with_synthetic_database(name, synthetic_database) -> None:
    app = run_page(name)

    assert not app.exception
    assert not app.error


def test_cases_page_puts_contact_request_first(synthetic_database) -> None:
    app = run_page("2_Casos.py")

    table = app.dataframe[0].value
    assert table.iloc[0]["Pidió contacto"] == "Sí"
    assert set(table["Pidió contacto"]) <= {"Sí", "No"}
    assert table["#"].tolist() == list(range(1, len(table) + 1))


def test_cases_page_updates_follow_up(synthetic_database) -> None:
    app = run_page("2_Casos.py")
    form_status = next(box for box in app.selectbox if box.label == "Estado")
    form_status.set_value("En seguimiento")
    next(
        button for button in app.button if button.label == "Guardar seguimiento"
    ).click()
    app.run()

    assert not app.exception
    connection = connect_database(synthetic_database)
    statuses = [row[0] for row in connection.execute("SELECT case_status FROM cases")]
    connection.close()
    assert "En seguimiento" in statuses


def test_small_group_aggregates_are_hidden(synthetic_database) -> None:
    app = run_page("3_Grupos.py")
    group = next(box for box in app.selectbox if box.label == "Grupo")
    group.set_value("G-02").run()

    assert any("menos de 5 alumnos" in warning.value for warning in app.warning)
    assert not app.dataframe


def test_home_prioritizes_daily_work(synthetic_database) -> None:
    app = run_page("1_Resumen.py")

    assert app.title[0].value == "Inicio"
    labels = {metric.label for metric in app.metric}
    assert {
        "Casos prioritarios",
        "Solicitudes de contacto",
        "Seguimientos",
        "Alumnos procesados",
    } <= labels
    assert any("Siguientes casos" in header.value for header in app.subheader)
    next_cases = app.dataframe[0].value
    assert 1 <= len(next_cases) <= 5
    assert next_cases["#"].tolist() == sorted(next_cases["#"])


def test_operational_counts_follow_open_cases(synthetic_database) -> None:
    _, engine = project_config()
    connection = connect_database(synthetic_database)
    case_ids = [row[0] for row in connection.execute("SELECT id FROM cases")]
    # Fixture: [prioritario con contacto, revisión manual, prioritario].
    update_case(connection, case_ids[0], next_follow_up_at="2026-01-10")
    update_case(
        connection, case_ids[1], next_follow_up_at="2026-01-01", case_status="Cerrado"
    )
    update_case(connection, case_ids[2], next_follow_up_at="2026-01-20")

    counts = operational_counts(connection, engine, date(2026, 1, 15))
    connection.close()

    assert counts == {
        "priority_cases": 2,
        "contact_requests": 1,
        "pending_followups": 1,
        "students": 6,
    }


def test_cases_has_clear_filters_and_work_sections(synthetic_database) -> None:
    app = run_page("2_Casos.py")

    assert any(expander.label == "Filtrar casos" for expander in app.expander)
    assert {tab.label for tab in app.tabs} >= {
        "Motivo y alertas",
        "Seguimiento",
        "Notas",
    }
    assert any(button.label == "Guardar seguimiento" for button in app.button)


def test_cases_explains_empty_filter_results(synthetic_database) -> None:
    app = run_page("2_Casos.py")
    search = next(field for field in app.text_input if "Buscar" in field.label)
    search.input("nadie-coincide").run()

    assert any("Sin resultados para estos filtros" in info.value for info in app.info)
    assert not app.tabs


def test_cases_confirms_saved_follow_up(synthetic_database) -> None:
    app = run_page("2_Casos.py")
    save = next(b for b in app.button if b.label == "Guardar seguimiento")
    save.click()
    app.run()

    assert any("Seguimiento actualizado" in item.value for item in app.success)


def test_cases_filters_persist_across_pages(synthetic_database) -> None:
    app = run_page("2_Casos.py")
    next(field for field in app.text_input if "Buscar" in field.label).input(
        "nadie-coincide"
    ).run()

    app.switch_page("pages/1_Resumen.py").run()
    app.switch_page("pages/2_Casos.py").run()

    search = next(field for field in app.text_input if "Buscar" in field.label)
    assert search.value == "nadie-coincide"


def test_student_record_groups_information_by_task(synthetic_database) -> None:
    app = run_page("4_Estudiantes.py")

    assert {tab.label for tab in app.tabs} >= {
        "Resultados",
        "Seguimiento",
        "Respuestas",
    }
    sensitive = next(toggle for toggle in app.toggle if "sensibles" in toggle.label)
    assert sensitive.value is False
    assert any(button.label == "Ver reportes del alumno" for button in app.button)


def test_student_record_opens_reports_for_same_student(synthetic_database) -> None:
    app = run_page("4_Estudiantes.py")
    search = next(field for field in app.text_input if "Buscar" in field.label)
    search.input("synthetic003@example.edu").run()

    next(b for b in app.button if b.label == "Ver reportes del alumno").click().run()

    connection = connect_database(synthetic_database)
    expected = connection.execute(
        "SELECT su.id FROM submissions su JOIN students st ON st.id = su.student_id "
        "WHERE st.student_upn = 'synthetic003@example.edu'"
    ).fetchone()[0]
    connection.close()
    assert app.title[0].value == "Reportes"
    selected = next(box for box in app.selectbox if box.label == "Estudiante")
    assert selected.value == expected


def test_reports_separates_individual_and_batch_flows(synthetic_database) -> None:
    app = run_page("5_Reportes.py")

    assert {tab.label for tab in app.tabs} == {"Individual", "Por lote"}
    assert any("confidencial" in warning.value.lower() for warning in app.warning)
    assert any("Vista previa" in header.value for header in app.subheader)


def test_groups_show_selection_and_coverage_first(synthetic_database) -> None:
    app = run_page("3_Grupos.py")

    labels = [metric.label for metric in app.metric]
    assert labels[:2] == ["Alumnos evaluados", "Casos abiertos"]


def test_administration_separates_safe_preview_and_real_import() -> None:
    app = run_page("6_Administracion.py")

    assert app.title[0].value == "Administración"
    assert any("modo de prueba" in info.value.lower() for info in app.info)
    assert any(expander.label == "Recalcular resultados" for expander in app.expander)
    headers = [header.value for header in app.subheader]
    assert headers[:2] == ["1. Archivo", "2. Validación"]


def test_administration_shows_versions_and_last_import(synthetic_database) -> None:
    app = run_page("6_Administracion.py")

    labels = {metric.label for metric in app.metric}
    assert {"Última importación", "Scoring", "Reglas de alerta"} <= labels


class FakeUpload:
    name = "synthetic.csv"

    def __init__(self, content: bytes) -> None:
        self._content = content

    def getvalue(self) -> bytes:
        return self._content


@pytest.fixture
def uploaded_csv(tmp_path, monkeypatch):
    """CSV sintético de 16 registros servido por un file_uploader simulado."""
    import streamlit

    questionnaire, engine = project_config()
    content = synthetic_rows(questionnaire, engine, [{} for _ in range(16)])
    monkeypatch.setattr(
        streamlit, "file_uploader", lambda *args, **kwargs: FakeUpload(content)
    )
    monkeypatch.setattr(ui, "DATABASE_PATH", tmp_path / "tamizaje.db")
    return tmp_path / "tamizaje.db"


def test_administration_safe_mode_never_persists(uploaded_csv) -> None:
    app = run_page("6_Administracion.py")

    assert [header.value for header in app.subheader] == [
        "1. Archivo",
        "2. Validación",
        "3. Resumen",
        "4. Confirmación",
    ]
    analyzed = next(m for m in app.metric if m.label == "Registros analizados")
    assert analyzed.value == "14"
    assert not any("Importar" in button.label for button in app.button)
    assert not uploaded_csv.exists()


def test_administration_real_import_requires_reinforced_confirmation(
    uploaded_csv,
) -> None:
    app = run_page("6_Administracion.py")
    app.toggle[0].set_value(False).run()

    importer = next(b for b in app.button if b.label.startswith("Importar"))
    assert importer.label == "Importar 2 registros reales"
    assert importer.disabled

    app.checkbox[0].check().run()
    next(field for field in app.text_input if "IMPORTAR" in field.label).input(
        "IMPORTAR"
    ).run()
    importer = next(b for b in app.button if b.label.startswith("Importar"))
    assert not importer.disabled
    importer.click().run()

    assert any("Importación completada" in item.value for item in app.success)
    connection = connect_database(uploaded_csv)
    lines = [
        row[0]
        for row in connection.execute(
            "SELECT source_row_number FROM submissions ORDER BY 1"
        )
    ]
    connection.close()
    assert lines == [16, 17]


def test_cases_open_by_clicking_a_row(synthetic_database) -> None:
    app = run_page("2_Casos.py")
    table = app.dataframe[0].value
    assert any(header.value.startswith("#1 · ") for header in app.subheader)

    app.session_state["cases_table"] = {
        "selection": {"rows": [], "columns": [], "cells": [[2, "Nivel"]]}
    }
    app.run()

    expected = f"#3 · {table.iloc[2]['Alumno']}"
    assert any(header.value == expected for header in app.subheader)
    assert not any(box.label == "Caso" for box in app.selectbox)


@pytest.mark.parametrize("name", DATA_PAGES)
def test_daily_pages_avoid_technical_jargon(name, synthetic_database) -> None:
    app = run_page(name)
    texts = " ".join(
        element.value
        for kind in ("title", "caption", "markdown", "info", "warning", "subheader")
        for element in getattr(app, kind)
        if isinstance(element.value, str)
    ).casefold()

    for jargon in ("scoring", "envío", "vigente", "versión", "huella", "none"):
        assert jargon not in texts, jargon


@pytest.mark.parametrize(
    ("value", "expected"),
    [
        ("2026-10-06", "06/10/2026"),
        ("2026-10-06T22:30:00+00:00", "06/10/2026 16:30"),
        (None, "—"),
        ("", "—"),
        ("texto-no-fecha", "texto-no-fecha"),
    ],
)
def test_format_date_uses_day_month_year(value, expected) -> None:
    _, engine = project_config()

    assert ui.format_date(value, engine.report_timezone) == expected
