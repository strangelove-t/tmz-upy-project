import re
from decimal import Decimal
from pathlib import Path

import pytest
from synthetic_forms import project_config, synthetic_rows

from tamizaje.database import connect_database, import_preview, initialize_database
from tamizaje.importers import preview_csv
from tamizaje.reports import (
    AreaLine,
    build_report_data,
    generate_report,
    load_template,
)
from tamizaje.student_report import (
    ASSETS_DIR,
    build_student_view,
    contact_line,
    scale_note,
    score_text,
)

ROOT = Path(__file__).parents[1]


def area(code: str, light: str | None, score: str | None, rec: str | None = None):
    return AreaLine(
        area_code=code,
        area_name=f"Área {code}",
        score=Decimal(score) if score is not None else None,
        traffic_light=light,
        recommendation=rec,
        description=f"Descripción {code}",
        interpretation="",
    )


LABELS = {
    "Rojo": "Atender",
    "Amarillo": "Dar seguimiento",
    "Verde": "Fortaleza",
    "Pendiente de revisión": "Sin información",
}


@pytest.mark.parametrize(
    ("score", "expected"),
    [
        (Decimal("69.6"), "69"),
        (Decimal("70"), "70"),
        (Decimal("39.99"), "39"),
        (Decimal("100"), "100"),
        (Decimal("0"), "0"),
        (None, "—"),
    ],
)
def test_score_text_never_crosses_a_threshold(score, expected) -> None:
    assert score_text(score) == expected


def test_student_view_orders_attention_first_and_counts_levels() -> None:
    data = {
        "areas": [
            area("A01", "Verde", "90", "rec verde"),
            area("A02", None, None),
            area("A03", "Amarillo", "50", "rec amarilla"),
            area("A04", "Rojo", "10", "rec roja"),
        ]
    }

    view = build_student_view(data, LABELS)

    assert [item.area_code for item in view.areas] == ["A04", "A03", "A01", "A02"]
    assert [item.label for item in view.areas] == [
        "Atender",
        "Dar seguimiento",
        "Fortaleza",
        "Sin información",
    ]
    assert view.counts == {"Verde": 1, "Amarillo": 1, "Rojo": 1}
    assert [(name, level) for name, _, level in view.focus] == [
        ("Área A04", "Rojo"),
        ("Área A03", "Amarillo"),
    ]
    assert view.strengths == ["Área A01"]
    assert view.missing == ["Área A02"]


def test_scale_note_follows_configured_thresholds() -> None:
    assert scale_note({"green_min": 70, "yellow_min": 40}) == (
        "Fortaleza desde 70, seguimiento de 40 a 69 y atención por debajo de 40."
    )
    assert scale_note(None) == "Entre más alta la cifra, mayor fortaleza."


def test_contact_line_is_omitted_until_configured() -> None:
    assert contact_line({"contact": ""}) is None
    assert contact_line({"contact": "  "}) is None
    assert contact_line({}) is None
    assert contact_line({"contact": "Edificio A · orientacion@example.edu"}) == (
        "Edificio A · orientacion@example.edu"
    )


def test_student_template_only_whitelists_rendered_fields() -> None:
    template = load_template("student")

    assert template.title == "Reporte de orientación"
    assert template.contact == ""
    assert {"scoring_version", "traffic_light_legend"}.isdisjoint(template.fields)
    assert {
        "student_introduction",
        "score_scale",
        "areas",
        "recommendations",
        "contact",
    } <= set(template.fields)


def test_report_assets_are_versioned_with_their_license() -> None:
    for name in ("Lato-Regular.ttf", "Lato-Bold.ttf", "Lato-Black.ttf", "OFL.txt"):
        assert (ASSETS_DIR / "fonts" / name).is_file(), name
    assert (ASSETS_DIR / "logo_upy.png").is_file()


@pytest.fixture
def synthetic_student():
    questionnaire, engine = project_config()
    student = {
        **{f"PA{i:02d}": "Totalmente en desacuerdo" for i in range(1, 10)},
        "PA10": "Nunca",
        **{f"HO{i:02d}": "Algunas veces" for i in range(1, 11)},
        "MO01": "Respuesta no configurada",
    }
    preview = preview_csv(
        "synthetic.csv",
        synthetic_rows(questionnaire, engine, [student]),
        questionnaire=questionnaire,
    )
    connection = connect_database(":memory:")
    initialize_database(connection)
    import_preview(
        connection,
        preview,
        questionnaire,
        engine.scoring,
        alert_config=engine.alerts,
        recommendations=engine.recommendations,
    )
    return connection, engine


def test_student_data_feeds_the_view(synthetic_student) -> None:
    connection, engine = synthetic_student
    data = build_report_data(connection, 1, engine, load_template("student"))

    view = build_student_view(data, data["student_labels"])

    assert data["score_scale"] == {"green_min": 70, "yellow_min": 40}
    assert view.counts == {"Verde": 6, "Amarillo": 1, "Rojo": 1}
    assert view.missing == ["Motivación y elección de carrera"]
    assert [level for _, _, level in view.focus] == ["Rojo", "Amarillo"]


def test_student_pdf_is_branded_and_fits_two_pages(synthetic_student) -> None:
    connection, engine = synthetic_student

    _, pdf = generate_report(connection, 1, engine, "student")

    assert pdf.startswith(b"%PDF") and pdf.rstrip().endswith(b"%%EOF")
    assert len(re.findall(rb"/Type /Page[^s]", pdf)) <= 2
    assert b"Lato-Black" in pdf and b"Lato-Regular" in pdf
    assert b"/Subtype /Image" in pdf
    assert b"Reporte de orienta" in pdf  # título en los metadatos


def test_tutor_pdf_uses_the_same_identity(synthetic_student) -> None:
    connection, engine = synthetic_student

    _, pdf = generate_report(connection, 1, engine, "tutor")

    assert pdf.startswith(b"%PDF")
    assert b"Lato-Black" in pdf and b"Lato-Regular" in pdf
    assert b"/Subtype /Image" in pdf
    assert b"Expediente acad" in pdf  # título en los metadatos
