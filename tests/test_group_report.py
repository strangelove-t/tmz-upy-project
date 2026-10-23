import shutil
import subprocess

import pytest
from synthetic_forms import project_config, synthetic_rows

from tamizaje.database import connect_database, import_preview, initialize_database
from tamizaje.group_report import (
    GroupReportError,
    build_group_report,
    group_report_filename,
    render_group_pdf,
)
from tamizaje.importers import preview_csv
from tamizaje.repository import cases_frame


@pytest.fixture
def group_database(tmp_path):
    questionnaire, engine = project_config()
    rows = [{} for _ in range(5)] + [{"DG03": "G-02"}]
    rows[0] = {"MO09": "Siempre", "DC02": "Sí"}
    rows[1] = {"PA01": "Totalmente en desacuerdo", "PE02": "Nada probable"}
    rows[2] = {"DC02": "Sí"}
    rows[3] = {"DC01": "Situación confidencial sintética"}
    content = synthetic_rows(questionnaire, engine, rows)
    preview = preview_csv("synthetic.csv", content, questionnaire=questionnaire)
    connection = connect_database(tmp_path / "tamizaje.db")
    initialize_database(connection)
    import_preview(
        connection,
        preview,
        questionnaire,
        engine.scoring,
        alert_config=engine.alerts,
        recommendations=engine.recommendations,
    )
    yield connection, engine
    connection.close()


def test_group_report_has_nine_area_summary_and_safe_priority_list(
    group_database,
) -> None:
    connection, engine = group_database
    report = build_group_report(connection, engine, "Carrera Sintética", "G-01")

    assert report.student_count == 5
    assert len(report.areas) == len(engine.scoring.areas) == 9
    assert sum(report.open_cases_by_level.values()) >= 1
    assert all(sum(area.distribution.values()) == 5 for area in report.areas)
    expected = cases_frame(connection, engine)
    expected = expected[
        (expected["group_name"] == "G-01") & (expected["case_status"] != "Cerrado")
    ]
    assert [student.name for student in report.students] == expected[
        "student_name"
    ].tolist()
    assert report.students[0].name == "Estudiante Sintético 001"
    assert report.students[0].requested_contact
    assert report.students[0].alert_count >= 1
    assert "example.edu" not in repr(report)
    assert "MO09" not in repr(report)
    assert "Situación confidencial sintética" not in repr(report)
    assert "alert_reason" not in repr(report)


def test_closed_case_is_not_in_group_list(group_database) -> None:
    connection, engine = group_database
    connection.execute(
        "UPDATE cases SET case_status = 'Cerrado' WHERE submission_id = "
        "(SELECT su.id FROM submissions su JOIN students st "
        "ON st.id = su.student_id WHERE st.student_upn = ?)",
        ("synthetic001@example.edu",),
    )
    report = build_group_report(connection, engine, "Carrera Sintética", "G-01")
    assert "Estudiante Sintético 001" not in [
        student.name for student in report.students
    ]


def test_group_list_matches_cases_before_recalculation(group_database) -> None:
    connection, engine = group_database
    connection.execute(
        "UPDATE cases SET scoring_version = 'anterior', rule_version = 'anterior' "
        "WHERE submission_id = (SELECT su.id FROM submissions su "
        "JOIN students st ON st.id = su.student_id WHERE st.student_upn = ?)",
        ("synthetic001@example.edu",),
    )
    expected = cases_frame(connection, engine)
    expected = expected[
        (expected["group_name"] == "G-01") & (expected["case_status"] != "Cerrado")
    ]

    report = build_group_report(connection, engine, "Carrera Sintética", "G-01")

    assert [student.name for student in report.students] == expected[
        "student_name"
    ].tolist()


def test_small_or_missing_group_cannot_be_exported(group_database) -> None:
    connection, engine = group_database
    with pytest.raises(GroupReportError, match="menos de"):
        build_group_report(connection, engine, "Carrera Sintética", "G-02")
    with pytest.raises(GroupReportError, match="no existe"):
        build_group_report(connection, engine, "Carrera Sintética", "G-99")


def test_incomplete_result_is_pending_and_not_averaged(group_database) -> None:
    connection, engine = group_database
    submission_id = connection.execute(
        "SELECT su.id FROM submissions su JOIN students st ON st.id = su.student_id "
        "WHERE st.student_upn = 'synthetic001@example.edu'"
    ).fetchone()[0]
    connection.execute(
        "UPDATE area_results SET is_complete = 0, normalized_score = NULL, "
        "traffic_light = NULL WHERE submission_id = ? AND area_code = 'A01'",
        (submission_id,),
    )

    report = build_group_report(connection, engine, "Carrera Sintética", "G-01")
    area = next(area for area in report.areas if area.code == "A01")
    assert area.complete_count == 4
    assert area.distribution["Pendiente"] == 1
    assert sum(item.distribution["Pendiente"] for item in report.areas) == 1


def test_only_current_submission_is_counted(group_database) -> None:
    connection, engine = group_database
    baseline = build_group_report(connection, engine, "Carrera Sintética", "G-01")
    submission_id = connection.execute("SELECT id FROM submissions LIMIT 1").fetchone()[
        0
    ]
    connection.execute(
        "UPDATE submissions SET is_current = 0 WHERE id = ?", (submission_id,)
    )
    with pytest.raises(GroupReportError, match="menos de"):
        build_group_report(connection, engine, "Carrera Sintética", "G-01")
    assert baseline.student_count == 5


def test_group_pdf_explains_results_and_names_group(group_database) -> None:
    connection, engine = group_database
    report = build_group_report(connection, engine, "Carrera Sintética", "G-01")
    content = render_group_pdf(report)
    filename = group_report_filename(report)

    assert content.startswith(b"%PDF") and content.rstrip().endswith(b"%%EOF")
    assert filename.endswith(".pdf")
    assert "G-01" in filename and filename.endswith(".pdf")

    if shutil.which("pdftotext"):
        text = subprocess.run(
            ["pdftotext", "-", "-"], input=content, capture_output=True, check=True
        ).stdout.decode()
        for area in engine.scoring.areas:
            assert area.area_name in text
        assert "Grupo G-01" in text
        assert "Verde" in text and "Amarillo" in text and "Rojo" in text
        assert "Atención prioritaria" in text
        assert "Alumnos que requieren acompañamiento" in text
        assert "Estudiante Sintético 001" in text
        assert "Resultados completos" not in text
        assert "example.edu" not in text
        assert "Situación confidencial sintética" not in text


def test_group_pdf_repeats_student_header_for_large_group(tmp_path) -> None:
    if not shutil.which("pdftotext"):
        pytest.skip("pdftotext no está disponible")
    questionnaire, engine = project_config()
    content = synthetic_rows(questionnaire, engine, [{"DC02": "Sí"} for _ in range(24)])
    preview = preview_csv("large-synthetic.csv", content, questionnaire=questionnaire)
    connection = connect_database(tmp_path / "large.db")
    initialize_database(connection)
    import_preview(
        connection,
        preview,
        questionnaire,
        engine.scoring,
        alert_config=engine.alerts,
        recommendations=engine.recommendations,
    )
    report = build_group_report(connection, engine, "Carrera Sintética", "G-01")
    text = subprocess.run(
        ["pdftotext", "-", "-"],
        input=render_group_pdf(report),
        capture_output=True,
        check=True,
    ).stdout.decode()
    connection.close()

    assert text.count("Pidió contacto") >= 3
    assert "Estudiante Sintético 001" in text
    assert "Estudiante Sintético 024" in text


def test_group_average_takes_the_color_of_its_thresholds(group_database) -> None:
    connection, engine = group_database
    report = build_group_report(connection, engine, "Carrera Sintética", "G-01")
    thresholds = {area.area_code: area for area in engine.scoring.areas}

    for area in report.areas:
        definition = thresholds[area.code]
        if area.average is None:
            assert area.level == "Pendiente de revisión"
        elif area.average >= definition.green_min:
            assert area.level == "Verde"
        elif area.average >= definition.yellow_min:
            assert area.level == "Amarillo"
        else:
            assert area.level == "Rojo"


def test_group_pdf_uses_the_same_identity(group_database) -> None:
    connection, engine = group_database
    report = build_group_report(connection, engine, "Carrera Sintética", "G-01")

    content = render_group_pdf(report)

    assert b"Lato-Black" in content and b"/Subtype /Image" in content
    assert b"Grupo G-01" in content  # título en los metadatos
