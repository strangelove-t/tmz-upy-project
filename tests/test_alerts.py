from collections import Counter
from pathlib import Path

import pytest

from tamizaje.alerts import AlertConfigError, evaluate_alerts, load_alert_config

CONFIG_DIR = Path(__file__).parents[1] / "config"
PRIORITY = "Atención prioritaria"
PREVENTIVE = "Seguimiento preventivo"
MANUAL = "Revisión manual"


@pytest.fixture(scope="module")
def config():
    return load_alert_config(CONFIG_DIR)


def levels(alerts) -> list[str]:
    return [alert.alert_level for alert in alerts]


def test_project_catalog_has_44_rules_on_24_questions(config) -> None:
    assert config.version == "0.1"
    assert len(config.rules) == 44
    assert len({rule.question_code for rule in config.rules}) == 24
    assert Counter(rule.match_type for rule in config.rules)["non_empty"] == 2


def test_mo09_always_creates_priority_attention(config) -> None:
    alerts = evaluate_alerts({"MO09": "Siempre"}, config)

    assert levels(alerts) == [PRIORITY]
    assert alerts[0].alert_category == "Permanencia"
    assert alerts[0].rule_version == "0.1"


def test_se04_sometimes_creates_preventive_follow_up(config) -> None:
    assert levels(evaluate_alerts({"SE04": "Algunas veces"}, config)) == [PREVENTIVE]


def test_dc02_yes_creates_priority_contact_request(config) -> None:
    alerts = evaluate_alerts({"DC02": "Sí"}, config)

    assert levels(alerts) == [PRIORITY]
    assert alerts[0].alert_category == config.contact_request_category


@pytest.mark.parametrize("code", ["DC01", "DC03"])
def test_open_text_creates_manual_review_without_copying_text(config, code) -> None:
    alerts = evaluate_alerts({code: "  Texto sintético  "}, config)

    assert levels(alerts) == [MANUAL]
    assert "sintético" not in alerts[0].trigger_response


@pytest.mark.parametrize("code", ["DC01", "DC03"])
def test_blank_open_text_creates_no_alert(config, code) -> None:
    assert evaluate_alerts({code: " \n "}, config) == ()


def test_unconfigured_or_missing_response_creates_no_alert(config) -> None:
    responses = {"MO09": "Nunca", "SE04": "Respuesta inventada"}

    assert evaluate_alerts(responses, config) == ()
    assert evaluate_alerts({}, config) == ()


def test_matching_is_exact_after_normalization(config) -> None:
    assert levels(evaluate_alerts({"DC02": " Sí\r\n"}, config)) == [PRIORITY]
    assert evaluate_alerts({"DC02": "Si, por favor"}, config) == ()


def test_several_rules_produce_several_alerts(config) -> None:
    alerts = evaluate_alerts(
        {"MO09": "Siempre", "SE04": "Algunas veces", "DC02": "Sí"}, config
    )

    assert sorted(alert.question_code for alert in alerts) == ["DC02", "MO09", "SE04"]


def write_alert_config(path: Path, rule_rows: str) -> None:
    path.mkdir()
    (path / "parameters.yaml").write_text(
        'active_alert_rules_version: "t"\n'
        "alert_levels: [Alta, Baja]\n"
        "contact_request_category: Contacto\n",
        encoding="utf-8",
    )
    (path / "questionnaire.csv").write_text(
        "QuestionCode,FormsNumber,QuestionText,QuestionType,Required,IsSensitive,"
        "QuestionnaireVersion,MappingStatus\n"
        "Q01,1,Synthetic question,single_choice,true,false,1.2,approved\n",
        encoding="utf-8",
    )
    (path / "alert_rules.csv").write_text(
        "RuleCode,QuestionCode,MatchType,TriggerResponse,AlertLevel,AlertCategory,"
        "AlertReason,SuggestedAction,RuleVersion\n" + rule_rows,
        encoding="utf-8",
    )


def test_load_alert_config_ignores_other_versions(tmp_path) -> None:
    config_dir = tmp_path / "config"
    write_alert_config(
        config_dir,
        "R1,Q01,exact,Yes,Alta,Cat,Motivo,Acción,t\n"
        "R2,Q01,exact,No,Inexistente,Cat,Motivo,Acción,old\n",
    )

    config = load_alert_config(config_dir)

    assert [rule.rule_code for rule in config.rules] == ["R1"]


@pytest.mark.parametrize(
    "rows",
    [
        "R1,Q99,exact,Yes,Alta,Cat,Motivo,Acción,t\n",
        "R1,Q01,exact,Yes,Media,Cat,Motivo,Acción,t\n",
        "R1,Q01,fuzzy,Yes,Alta,Cat,Motivo,Acción,t\n",
        "R1,Q01,exact,,Alta,Cat,Motivo,Acción,t\n",
        "R1,Q01,non_empty,Yes,Alta,Cat,Motivo,Acción,t\n",
        "R1,Q01,exact,Yes,Alta,Cat,Motivo,Acción,t\n"
        "R2,Q01,exact, yes ,Baja,Cat,Motivo,Acción,t\n",
        "R1,Q01,exact,Yes,Alta,Cat,Motivo,Acción,t\n"
        "R1,Q01,exact,No,Baja,Cat,Motivo,Acción,t\n",
    ],
)
def test_load_alert_config_rejects_invalid_rules(tmp_path, rows) -> None:
    config_dir = tmp_path / "config"
    write_alert_config(config_dir, rows)

    with pytest.raises(AlertConfigError, match="alert_rules.csv"):
        load_alert_config(config_dir)
