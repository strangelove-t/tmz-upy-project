import csv
import shutil
import subprocess
from dataclasses import replace
from datetime import UTC, datetime

import pytest
from synthetic_forms import project_config, synthetic_rows

import tamizaje.reports as reports_module
from tamizaje.database import connect_database, import_preview, initialize_database
from tamizaje.importers import preview_csv
from tamizaje.reports import (
    ReportError,
    build_report_data,
    export_batch,
    generate_report,
    load_template,
    report_filename,
)

EMAIL = "synthetic001@example.edu"


@pytest.fixture
def imported(tmp_path):
    questionnaire, engine = project_config()
    content = synthetic_rows(
        questionnaire,
        engine,
        [
            {
                "MO09": "Siempre",
                "SE04": "Siempre",
                "DC02": "Sí",
                "DC01": "Texto abierto sintético",
                "SE01": "Sí",
            },
            {"ADM_EMAIL": "otro@example.edu"},
        ],
    )
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
    submission_id = connection.execute(
        "SELECT id FROM submissions ORDER BY id LIMIT 1"
    ).fetchone()[0]
    return connection, engine, submission_id


def flatten(data: dict) -> str:
    return repr(data)


def test_student_report_excludes_internal_information(imported) -> None:
    connection, engine, submission_id = imported
    data = build_report_data(
        connection, submission_id, engine, load_template("student")
    )
    text = flatten(data)

    assert len(data["areas"]) == 9
    assert data["recommendations"]
    assert "No constituye un diagnóstico" in data["disclaimer"]
    for (alert_reason,) in connection.execute("SELECT alert_reason FROM alerts"):
        assert alert_reason not in text
    for forbidden in ("Atención prioritaria", "AL-", "Texto abierto", EMAIL):
        assert forbidden not in text


def test_tutor_report_covers_all_areas_without_diagnoses_by_default(imported) -> None:
    connection, engine, submission_id = imported
    data = build_report_data(connection, submission_id, engine, load_template("tutor"))
    text = flatten(data)

    assert set(data) == set(load_template("tutor").fields)
    assert [line.area_code for line in data["areas"]] == [
        f"A{number:02d}" for number in range(1, 10)
    ]
    staff_texts = {r.staff_recommendation for r in engine.recommendations}
    assert all(text in staff_texts for _, text in data["recommendations"])
    for forbidden in (EMAIL, "Texto abierto sintético", "sensitive_summary"):
        assert forbidden not in text


def test_template_cannot_request_unauthorized_fields(imported) -> None:
    connection, engine, submission_id = imported
    template = replace(load_template("tutor"), fields=("student_name", "alerts"))

    with pytest.raises(ReportError, match="no autorizados"):
        build_report_data(connection, submission_id, engine, template)


def test_report_filename_names_student_safely_and_prevents_collisions() -> None:
    first = report_filename("student", "synthetic-001", "Ana María / López")

    assert first == report_filename("student", "synthetic-001", "Ana María / López")
    assert first != report_filename("student", "synthetic-002", "Ana María / López")
    assert "Ana_Maria_Lopez" in first
    assert "/" not in first and first.endswith(".pdf")


def test_report_filename_keeps_long_full_name() -> None:
    name = "Ana " + " ".join(["López"] * 24)
    filename = report_filename("tutor", "synthetic-long", name)

    assert "Ana_" + "_".join(["Lopez"] * 24) in filename
    assert len(filename) <= 255


def test_generated_pdf_is_valid(imported) -> None:
    connection, engine, submission_id = imported

    for report_type in ("student", "tutor"):
        filename, content = generate_report(
            connection, submission_id, engine, report_type
        )
        assert filename.startswith(report_type)
        assert "Estudiante_Sintetico_001" in filename
        assert content.startswith(b"%PDF") and content.rstrip().endswith(b"%%EOF")


def test_tutor_pdf_repeats_area_header_when_it_spans_pages(imported) -> None:
    if not shutil.which("pdftotext"):
        pytest.skip("pdftotext no está disponible")
    connection, engine, submission_id = imported
    _, content = generate_report(connection, submission_id, engine, "tutor")

    text = subprocess.run(
        ["pdftotext", "-", "-"], input=content, capture_output=True, check=True
    ).stdout.decode()
    assert text.count("Área e interpretación") >= 2


def test_export_batch_writes_manifest_and_audit(imported, tmp_path) -> None:
    connection, engine, _ = imported
    output_dir = tmp_path / "exports" / "lote"

    manifest = export_batch(connection, engine, output_dir)

    with manifest.open(encoding="utf-8-sig", newline="") as stream:
        rows = list(csv.DictReader(stream))
    assert [row["correo"] for row in rows] == [EMAIL, "otro@example.edu"]
    for row in rows:
        assert (output_dir / row["reporte_estudiante"]).is_file()
        assert (output_dir / row["expediente_tutor"]).is_file()
    assert connection.execute("SELECT COUNT(*) FROM exports").fetchone()[0] == 4


def test_export_batch_neutralizes_spreadsheet_formulas(imported, tmp_path) -> None:
    connection, engine, submission_id = imported
    connection.execute(
        "UPDATE students SET student_upn = ?, student_name = ? WHERE id = "
        "(SELECT student_id FROM submissions WHERE id = ?)",
        ("+SUM(1,1)", "=2+2", submission_id),
    )

    manifest = export_batch(connection, engine, tmp_path / "exports")

    with manifest.open(encoding="utf-8-sig", newline="") as stream:
        first = next(csv.DictReader(stream))
    assert first["correo"] == "'+SUM(1,1)"
    assert first["nombre"] == "'=2+2"


def test_report_date_uses_configured_timezone(imported, monkeypatch) -> None:
    connection, engine, submission_id = imported

    class FixedDateTime(datetime):
        @classmethod
        def now(cls, tz=None):
            instant = cls(2026, 10, 8, 1, 0, tzinfo=UTC)
            return instant.astimezone(tz) if tz else instant.replace(tzinfo=None)

    monkeypatch.setattr(reports_module, "datetime", FixedDateTime)

    data = build_report_data(
        connection, submission_id, engine, load_template("student")
    )
    assert data["generated_at"] == "2026-10-07"


def test_student_report_rejects_sensitive_option(imported) -> None:
    connection, engine, submission_id = imported

    with pytest.raises(ReportError, match="alumno"):
        generate_report(
            connection,
            submission_id,
            engine,
            "student",
            include_sensitive=True,
        )


def test_tutor_report_excludes_sensitive_summary_by_default(imported) -> None:
    connection, engine, submission_id = imported
    data = build_report_data(connection, submission_id, engine, load_template("tutor"))
    assert "sensitive_summary" not in data


def test_tutor_report_can_include_whitelisted_summary(imported) -> None:
    connection, engine, submission_id = imported
    data = build_report_data(
        connection,
        submission_id,
        engine,
        load_template("tutor"),
        include_sensitive=True,
    )
    assert data["sensitive_summary"].has_sensitive_declaration
    assert "Texto abierto sintético" not in repr(data)


def test_report_explains_traffic_lights_and_areas(imported) -> None:
    connection, engine, submission_id = imported
    data = build_report_data(connection, submission_id, engine, load_template("tutor"))
    assert set(data["traffic_light_legend"]) == {
        "Verde",
        "Amarillo",
        "Rojo",
        "Pendiente de revisión",
    }
    assert all(line.description for line in data["areas"])
    assert all(line.interpretation for line in data["areas"])


def test_export_audit_records_sensitive_choice(imported, tmp_path) -> None:
    connection, engine, _ = imported
    export_batch(
        connection,
        engine,
        tmp_path / "exports-sensitive",
        include_sensitive_tutor=True,
    )
    flags = connection.execute(
        "SELECT export_type, includes_sensitive_summary FROM exports ORDER BY id"
    ).fetchall()
    assert flags == [("student", 0), ("tutor", 1), ("student", 0), ("tutor", 1)]


def test_exports_schema_has_sensitive_summary_flag(imported) -> None:
    connection, _, _ = imported
    columns = {
        row[1] for row in connection.execute("PRAGMA table_info(exports)").fetchall()
    }
    assert "includes_sensitive_summary" in columns


def pdf_text(content: bytes) -> str:
    return subprocess.run(
        ["pdftotext", "-", "-"], input=content, capture_output=True, check=True
    ).stdout.decode()


def test_tutor_pdf_shows_actions_and_conditions_only_when_authorized(
    imported,
) -> None:
    if not shutil.which("pdftotext"):
        pytest.skip("pdftotext no está disponible")
    connection, engine, submission_id = imported

    _, default = generate_report(connection, submission_id, engine, "tutor")
    _, sensitive = generate_report(
        connection, submission_id, engine, "tutor", include_sensitive=True
    )

    text = pdf_text(default)
    assert "Acciones sugeridas para la tutoría" in text
    assert "Cómo leer el semáforo" in text
    assert "Condiciones y apoyos declarados" not in text
    assert "Condiciones y apoyos declarados" in pdf_text(sensitive)
    assert EMAIL not in pdf_text(sensitive)
