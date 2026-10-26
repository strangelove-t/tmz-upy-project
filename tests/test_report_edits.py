import shutil
import subprocess
from dataclasses import replace

import pytest
from test_reports import imported  # noqa: F401  (fixture sintético)

from tamizaje.group_report import build_group_report, render_group_pdf
from tamizaje.report_edits import (
    MAX_TEXT_LENGTH,
    ReportEditError,
    apply_edits,
    clear_edits,
    editable_texts,
    group_subject,
    load_edits,
    save_edits,
)
from tamizaje.reports import (
    build_report_data,
    export_batch,
    generate_report,
    load_template,
    prepare_report,
)


def pdf_text(content: bytes) -> str:
    if not shutil.which("pdftotext"):
        pytest.skip("pdftotext no está disponible")
    return subprocess.run(
        ["pdftotext", "-", "-"], input=content, capture_output=True, check=True
    ).stdout.decode()


def raw_data(connection, engine, submission_id, report_type):
    return build_report_data(
        connection, submission_id, engine, load_template(report_type)
    )


def test_student_editable_texts_cover_printed_texts_and_notes(imported) -> None:  # noqa: F811
    connection, engine, submission_id = imported
    texts = editable_texts(raw_data(connection, engine, submission_id, "student"),
                           "student")

    assert {"student_introduction", "disclaimer", "notes"} <= set(texts)
    assert texts["notes"] == ""
    # Sólo se ofrecen recomendaciones que el PDF del alumno imprime.
    data = raw_data(connection, engine, submission_id, "student")
    printed = {
        line.area_code for line in data["areas"]
        if line.traffic_light in ("Rojo", "Amarillo") and line.recommendation
    }
    offered = {key.split(":")[1] for key in texts if key.startswith("recommendation:")}
    assert offered == printed


def test_tutor_editable_texts_include_interpretations(imported) -> None:  # noqa: F811
    connection, engine, submission_id = imported
    texts = editable_texts(raw_data(connection, engine, submission_id, "tutor"),
                           "tutor")

    assert {"introduction", "disclaimer", "notes"} <= set(texts)
    assert sum(key.startswith("interpretation:") for key in texts) == 9
    assert all(f"recommendation:A0{n}" in texts for n in range(1, 10))


def test_only_changed_texts_are_stored_and_can_be_restored(imported) -> None:  # noqa: F811
    connection, engine, submission_id = imported
    defaults = editable_texts(
        raw_data(connection, engine, submission_id, "tutor"), "tutor"
    )
    values = dict(defaults, introduction="Introducción editada.", notes="  Nota.  ")

    save_edits(connection, "tutor", str(submission_id), values, defaults)

    assert load_edits(connection, "tutor", str(submission_id)) == {
        "introduction": "Introducción editada.",
        "notes": "Nota.",
    }
    # Volver al texto original elimina la edición.
    save_edits(connection, "tutor", str(submission_id),
               dict(values, introduction=defaults["introduction"]), defaults)
    assert set(load_edits(connection, "tutor", str(submission_id))) == {"notes"}

    clear_edits(connection, "tutor", str(submission_id))
    assert load_edits(connection, "tutor", str(submission_id)) == {}


def test_edits_reject_unknown_fields_and_long_texts(imported) -> None:  # noqa: F811
    connection, engine, submission_id = imported
    defaults = editable_texts(
        raw_data(connection, engine, submission_id, "tutor"), "tutor"
    )

    with pytest.raises(ReportEditError):
        save_edits(connection, "tutor", "1", {"student_name": "Otro"}, defaults)
    with pytest.raises(ReportEditError):
        save_edits(connection, "tutor", "1",
                   {"notes": "x" * (MAX_TEXT_LENGTH + 1)}, defaults)
    assert load_edits(connection, "tutor", "1") == {}


def test_empty_text_restores_the_original(imported) -> None:  # noqa: F811
    connection, engine, submission_id = imported
    defaults = editable_texts(
        raw_data(connection, engine, submission_id, "tutor"), "tutor"
    )

    save_edits(connection, "tutor", "1", {"introduction": "   "}, defaults)

    assert load_edits(connection, "tutor", "1") == {}


def test_apply_edits_changes_texts_but_never_results(imported) -> None:  # noqa: F811
    connection, engine, submission_id = imported
    data = raw_data(connection, engine, submission_id, "tutor")

    edited = apply_edits(data, "tutor", {
        "recommendation:A01": "Acción editada.",
        "interpretation:A01": "Interpretación editada.",
        "notes": "Nota del tutor.",
    })

    line = next(item for item in edited["areas"] if item.area_code == "A01")
    original = next(item for item in data["areas"] if item.area_code == "A01")
    assert line.recommendation == "Acción editada."
    assert line.interpretation == "Interpretación editada."
    assert (line.score, line.traffic_light) == (original.score,
                                                original.traffic_light)
    assert ("Preparación académica", "Acción editada.") in edited["recommendations"]
    assert edited["notes"] == "Nota del tutor."
    assert original.recommendation != "Acción editada."  # no muta el original


def test_generated_pdfs_use_saved_edits(imported, tmp_path) -> None:  # noqa: F811
    connection, engine, submission_id = imported
    for report_type, field in (("student", "student_introduction"),
                               ("tutor", "introduction")):
        _, data = prepare_report(connection, submission_id, engine, report_type)
        defaults = editable_texts(data, report_type)
        save_edits(connection, report_type, str(submission_id), dict(
            defaults, **{field: f"Texto editado {report_type}.",
                         "notes": f"Nota para {report_type}."}
        ), defaults)

        _, pdf = generate_report(connection, submission_id, engine, report_type)
        text = pdf_text(pdf)
        assert f"Texto editado {report_type}." in text
        assert f"Nota para {report_type}." in text

    manifest = export_batch(connection, engine, tmp_path / "lote")
    tutor_pdf = next(manifest.parent.glob("tutor_Estudiante_Sintetico_001_*.pdf"))
    assert "Nota para tutor." in pdf_text(tutor_pdf.read_bytes())


def test_group_report_accepts_introduction_and_notes(imported) -> None:  # noqa: F811
    connection, engine, _ = imported
    engine = replace(engine, minimum_group_size=1)
    report = build_group_report(connection, engine, "Carrera Sintética", "G-01")
    subject = group_subject("Carrera Sintética", "G-01")
    defaults = editable_texts(report, "group")
    save_edits(connection, "group", subject,
               dict(defaults, introduction="Intro grupal editada.",
                    notes="Nota grupal."), defaults)

    edited = apply_edits(report, "group", load_edits(connection, "group", subject))

    text = pdf_text(render_group_pdf(edited))
    assert "Intro grupal editada." in text and "Nota grupal." in text
