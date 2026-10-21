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


@pytest.fixture
def group_database(tmp_path):
    questionnaire, engine = project_config()
    rows = [{} for _ in range(5)] + [{"DG03": "G-02"}]
    rows[0] = {"MO09": "Siempre", "DC02": "Sí"}
    rows[1] = {"PA01": "Totalmente en desacuerdo"}
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


def test_group_report_has_aggregate_nine_area_summary(group_database) -> None:
    connection, engine = group_database
    report = build_group_report(connection, engine, "Carrera Sintética", "G-01")

    assert report.student_count == 5
    assert len(report.areas) == len(engine.scoring.areas) == 9
    assert report.complete_results + report.pending_results == 45
    assert sum(report.open_cases_by_level.values()) >= 1
    assert all(sum(area.distribution.values()) == 5 for area in report.areas)
    assert "Estudiante Sintético" not in repr(report)
    assert "example.edu" not in repr(report)
    assert "MO09" not in repr(report)


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
    assert report.pending_results == 1


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


def test_group_pdf_is_valid_and_filename_is_anonymous(group_database) -> None:
    connection, engine = group_database
    report = build_group_report(connection, engine, "Carrera Sintética", "G-01")
    content = render_group_pdf(report)
    filename = group_report_filename(report)

    assert content.startswith(b"%PDF") and content.rstrip().endswith(b"%%EOF")
    assert filename.endswith(".pdf")
    assert "Carrera" not in filename and "G-01" not in filename

    if shutil.which("pdftotext"):
        text = subprocess.run(
            ["pdftotext", "-", "-"], input=content, capture_output=True, check=True
        ).stdout.decode()
        for area in engine.scoring.areas:
            assert area.area_name in text
        assert "Casos abiertos por nivel" in text
        assert "Estudiante Sintético" not in text
        assert "example.edu" not in text
