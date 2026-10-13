from pathlib import Path

import pytest
import yaml
from synthetic_forms import project_config, synthetic_rows

from tamizaje.database import connect_database, import_preview, initialize_database
from tamizaje.importers import preview_csv
from tamizaje.questionnaire import load_questionnaire
from tamizaje.repository import sensitive_notices_frame
from tamizaje.sensitive_summary import (
    SensitiveConfigError,
    build_sensitive_summary,
    load_sensitive_config,
)

ROOT = Path(__file__).parents[1]


def imported_submission(tmp_path, overrides):
    questionnaire, engine = project_config()
    content = synthetic_rows(questionnaire, engine, [overrides])
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
    return connection, 1


def test_loads_four_sensitive_categories() -> None:
    questionnaire = load_questionnaire(ROOT / "config" / "questionnaire.csv")
    config = load_sensitive_config(ROOT / "config", questionnaire)

    assert [item.code for item in config.categories] == [
        "neurodevelopment",
        "mental_health",
        "personality",
        "physical_health",
    ]


def test_rejects_non_sensitive_question(tmp_path) -> None:
    questionnaire = load_questionnaire(ROOT / "config" / "questionnaire.csv")
    raw = yaml.safe_load(
        (ROOT / "config" / "sensitive_summary.yaml").read_text("utf-8")
    )
    raw["categories"][0]["trigger_question"] = "PA01"
    (tmp_path / "sensitive_summary.yaml").write_text(
        yaml.safe_dump(raw, allow_unicode=True), encoding="utf-8"
    )

    with pytest.raises(SensitiveConfigError, match="pregunta sensible"):
        load_sensitive_config(tmp_path, questionnaire)


def test_builds_one_consolidated_summary(tmp_path) -> None:
    connection, submission_id = imported_submission(
        tmp_path,
        {
            "ND01": "Sí",
            "ND02": "TDAH; Dislexia",
            "ND03": "Sí",
            "ND06": "Sí",
            "ND07": "Tiempo adicional",
            "CF01": "Sí",
            "CF02": "Movilidad reducida",
            "CF08": "Sí",
        },
    )
    questionnaire = load_questionnaire(ROOT / "config" / "questionnaire.csv")
    config = load_sensitive_config(ROOT / "config", questionnaire)

    summary = build_sensitive_summary(connection, submission_id, config)

    assert summary.has_sensitive_declaration
    assert [item.code for item in summary.categories] == [
        "neurodevelopment",
        "physical_health",
    ]
    assert summary.requested_support
    assert not summary.requires_review
    connection.close()


def test_diagnosis_without_affirmative_trigger_requires_review(tmp_path) -> None:
    connection, submission_id = imported_submission(
        tmp_path, {"SE01": "No", "SE02": "Ansiedad"}
    )
    questionnaire = load_questionnaire(ROOT / "config" / "questionnaire.csv")
    config = load_sensitive_config(ROOT / "config", questionnaire)

    summary = build_sensitive_summary(connection, submission_id, config)

    assert summary.has_sensitive_declaration
    assert summary.requires_review
    connection.close()


def test_summary_keeps_relevant_negative_answers(tmp_path) -> None:
    connection, submission_id = imported_submission(
        tmp_path, {"ND01": "Sí", "ND02": "TDAH", "ND03": "No"}
    )
    questionnaire = load_questionnaire(ROOT / "config" / "questionnaire.csv")
    config = load_sensitive_config(ROOT / "config", questionnaire)

    summary = build_sensitive_summary(connection, submission_id, config)

    assert ("Confirmación profesional declarada", "No") in summary.categories[0].fields
    connection.close()


def test_summary_is_read_only(tmp_path) -> None:
    connection, submission_id = imported_submission(tmp_path, {"AP01": "Sí"})
    questionnaire = load_questionnaire(ROOT / "config" / "questionnaire.csv")
    config = load_sensitive_config(ROOT / "config", questionnaire)
    before = {
        table: connection.execute(f"SELECT COUNT(*) FROM {table}").fetchone()[0]
        for table in ("cases", "alerts", "area_results")
    }

    build_sensitive_summary(connection, submission_id, config)

    after = {
        table: connection.execute(f"SELECT COUNT(*) FROM {table}").fetchone()[0]
        for table in before
    }
    assert after == before
    connection.close()


def test_notices_include_current_submission_without_risk_case(tmp_path) -> None:
    connection, _ = imported_submission(
        tmp_path, {"AP01": "Sí", "AP02": "Diagnóstico sintético"}
    )
    questionnaire = load_questionnaire(ROOT / "config" / "questionnaire.csv")
    config = load_sensitive_config(ROOT / "config", questionnaire)

    notices = sensitive_notices_frame(connection, config)

    assert len(notices) == 1
    assert notices.iloc[0]["category_labels"] == "Personalidad"
    assert notices.iloc[0]["case_id"] is None
    assert connection.execute("SELECT COUNT(*) FROM cases").fetchone()[0] == 0
    connection.close()
