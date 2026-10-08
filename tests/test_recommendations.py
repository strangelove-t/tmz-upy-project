from decimal import Decimal
from pathlib import Path

import pytest
from synthetic_forms import project_config, synthetic_rows

from tamizaje.database import connect_database, import_preview, initialize_database
from tamizaje.importers import preview_csv
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
        "A01", None, Decimal("50") if complete else None, light, 1, 1, 1,
        complete, "0.2",
    )


def test_project_catalog_covers_every_area_and_light() -> None:
    recommendations = load_recommendations(
        CONFIG_DIR, load_scoring_config(CONFIG_DIR)
    )

    assert len(recommendations) == 27


def test_recommendation_matches_area_and_light() -> None:
    recommendations = load_recommendations(
        CONFIG_DIR, load_scoring_config(CONFIG_DIR)
    )

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
