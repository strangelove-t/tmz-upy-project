from pathlib import Path

import pytest
from app_helpers import configured_app
from synthetic_forms import project_config, synthetic_rows

from tamizaje import ui
from tamizaje.database import connect_database, import_preview, initialize_database
from tamizaje.importers import preview_csv

PAGES_DIR = Path(__file__).parents[1] / "pages"
PAGES = sorted(path.name for path in PAGES_DIR.glob("*.py"))


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
    return configured_app(f"pages/{name}", authenticated=authenticated).run()


@pytest.mark.parametrize("name", PAGES)
def test_pages_require_authentication_before_reading(
    name, synthetic_database
) -> None:
    app = run_page(name, authenticated=False)

    assert not app.exception
    assert any(field.label == "Contraseña" for field in app.text_input)
    assert not app.dataframe
    assert not app.metric


@pytest.mark.parametrize("name", PAGES)
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
    assert table.iloc[0]["Solicitó contacto"]
    assert table["Prioridad"].tolist() == list(range(1, len(table) + 1))


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
