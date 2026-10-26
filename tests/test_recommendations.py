import shutil
from decimal import Decimal
from pathlib import Path

import pytest
from synthetic_forms import project_config, synthetic_rows

from tamizaje.database import connect_database, import_preview, initialize_database
from tamizaje.importers import preview_csv
from tamizaje.models import EngineConfigError, load_engine_config
from tamizaje.recommendations import (
    RecommendationConfigError,
    load_recommendations,
    recommendation_for,
)
from tamizaje.scoring import AreaResult
from tamizaje.scoring_config import load_scoring_config

CONFIG_DIR = Path(__file__).parents[1] / "config"


def result(light: str | None, complete: bool = True) -> AreaResult:
    return AreaResult(
        "A01",
        None,
        Decimal("50") if complete else None,
        light,
        1,
        1,
        1,
        complete,
        "0.2",
    )


def test_project_catalog_covers_every_area_and_light() -> None:
    recommendations = load_recommendations(CONFIG_DIR, load_scoring_config(CONFIG_DIR))

    assert len(recommendations) == 27


@pytest.mark.parametrize(
    ("code", "audience", "expected"),
    [
        (
            "REC-A01-V",
            "staff",
            "Reconocer la fortaleza e invitar al alumno a participar como "
            "«par de apoyo» académico.",
        ),
        (
            "REC-A01-A",
            "staff",
            "Sugerir asesorías académicas con apoyo de estudiantes que tengan "
            "facilidad para la asignatura.",
        ),
        (
            "REC-A02-V",
            "staff",
            "Es importante reforzar los hábitos de estudio favorables e "
            "identificar los que se pueden mejorar o fortalecer.",
        ),
        (
            "REC-A02-R",
            "staff",
            "Ofrecer un taller y/o una sesión individual de hábitos de estudio "
            "que incluya organización del tiempo, reglas mnemotécnicas, "
            "cuadros comparativos, etc.",
        ),
        (
            "REC-A03-A",
            "staff",
            "Promover actividades de exploración profesional, como las "
            "estadías, la movilidad estudiantil y el campo de trabajo, "
            "entre otras.",
        ),
        (
            "REC-A03-R",
            "staff",
            "Ofrecer orientación vocacional y agendar una cita con el área "
            "de Orientación Psicopedagógica.",
        ),
        (
            "REC-A04-A",
            "staff",
            "Brindar estrategias de socialización y la oportunidad de acudir "
            "a las diversas áreas de ayuda en caso de que lo requiera, además "
            "de proporcionar seguimiento por parte del área de tutorías.",
        ),
        (
            "REC-A04-R",
            "staff",
            "Brindar estrategias de socialización y, en caso de que se requiera, "
            "solicitarle que acuda a su tutor o al área de Orientación "
            "Psicopedagógica.",
        ),
        (
            "REC-A06-A",
            "staff",
            "Explorar las redes de apoyo en los diversos contextos donde "
            "interactúa (UPY, familia, salón de clase, etc.) y proporcionar "
            "seguimiento por parte del área de tutorías.",
        ),
        (
            "REC-A06-R",
            "staff",
            "Explorar las redes de apoyo en los diversos contextos donde "
            "interactúa (UPY, familia, salón de clase, etc.). Si el alumno se "
            "encuentra actualmente en una situación socioemocional, es "
            "recomendable buscar apoyo del área de Orientación Psicopedagógica "
            "y realizar seguimiento en el área de tutorías.",
        ),
        (
            "REC-A07-V",
            "student",
            "El cuidado emocional también conlleva hábitos como la higiene del "
            "sueño, el cuidado de la alimentación y el cuidado físico. "
            "Continúa cuidándote.",
        ),
        (
            "REC-A08-R",
            "student",
            "Es importante comunicar tu afectación al área de Orientación "
            "Psicopedagógica para determinar si existe alguna adecuación para "
            "tu condición física.",
        ),
        (
            "REC-A09-A",
            "staff",
            "Identificar los factores que pudieran incidir en la continuidad y "
            "permanencia, y mantener el seguimiento por parte del área de "
            "tutorías.",
        ),
        (
            "REC-A09-R",
            "staff",
            "Identificar los factores que pudieran incidir en la continuidad y "
            "permanencia, y proporcionar seguimiento por parte del área de "
            "tutoría. En caso de requerirse, canalizar al área de Orientación "
            "Psicopedagógica.",
        ),
    ],
)
def test_teacher_reviewed_recommendation_texts(code, audience, expected) -> None:
    recommendations = load_recommendations(CONFIG_DIR, load_scoring_config(CONFIG_DIR))
    recommendation = next(
        item for item in recommendations if item.recommendation_code == code
    )
    actual = (
        recommendation.student_recommendation
        if audience == "student"
        else recommendation.staff_recommendation
    )

    assert actual == expected


def test_project_config_uses_mexico_timezone() -> None:
    assert str(load_engine_config(CONFIG_DIR).report_timezone) == "America/Mexico_City"


def test_engine_config_rejects_unknown_report_timezone(tmp_path) -> None:
    config_dir = tmp_path / "config"
    shutil.copytree(CONFIG_DIR, config_dir)
    parameters = config_dir / "parameters.yaml"
    parameters.write_text(
        parameters.read_text(encoding="utf-8").replace(
            "America/Mexico_City", "Invalid/Timezone"
        ),
        encoding="utf-8",
    )

    with pytest.raises(EngineConfigError, match="parameters.yaml"):
        load_engine_config(config_dir)


def test_recommendation_matches_area_and_light() -> None:
    recommendations = load_recommendations(CONFIG_DIR, load_scoring_config(CONFIG_DIR))

    assert recommendation_for(result("Rojo"), recommendations).recommendation_code == (
        "REC-A01-R"
    )
    assert recommendation_for(result(None, complete=False), recommendations) is None


def test_incomplete_catalog_is_rejected(tmp_path) -> None:
    config_dir = tmp_path / "config"
    config_dir.mkdir()
    for name in (
        "parameters.yaml",
        "areas.csv",
        "area_items.csv",
        "scoring_options.csv",
        "questionnaire.csv",
    ):
        (config_dir / name).write_bytes((CONFIG_DIR / name).read_bytes())
    lines = (CONFIG_DIR / "recommendations.csv").read_text(encoding="utf-8")
    (config_dir / "recommendations.csv").write_text(
        "\n".join(lines.splitlines()[:-1]) + "\n", encoding="utf-8"
    )

    with pytest.raises(RecommendationConfigError, match="no cubre"):
        load_recommendations(config_dir, load_scoring_config(config_dir))


def test_end_to_end_import_with_project_configuration(tmp_path) -> None:
    questionnaire, engine = project_config()
    content = synthetic_rows(
        questionnaire,
        engine,
        [
            {},
            {"MO09": "Siempre", "DC02": "Sí", "DC01": "Texto sintético"},
            {"CF05": "No aplica", "SE04": "Algunas veces"},
        ],
    )
    preview = preview_csv("synthetic.csv", content, questionnaire=questionnaire)
    assert preview.mapping.is_valid
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

    assert connection.execute(
        "SELECT COUNT(*), SUM(is_complete), COUNT(recommendation_code) "
        "FROM area_results"
    ).fetchone() == (27, 27, 27)
    cases = connection.execute(
        "SELECT s.source_row_number, c.case_level, c.case_source, "
        "c.total_alert_count FROM cases c JOIN submissions s "
        "ON s.id = c.submission_id ORDER BY s.source_row_number"
    ).fetchall()
    assert cases == [
        (3, "Atención prioritaria", "Solicitud del alumno", 3),
        (4, "Seguimiento preventivo", "Alerta automática", 1),
    ]
