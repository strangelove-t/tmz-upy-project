"""Carga versionada y evaluación de alertas directas, independiente del scoring."""

import csv
from collections.abc import Mapping
from dataclasses import dataclass
from pathlib import Path
from typing import Literal

import yaml

from tamizaje.normalization import normalize_text
from tamizaje.questionnaire import load_questionnaire

ALERT_COLUMNS = (
    "RuleCode",
    "QuestionCode",
    "MatchType",
    "TriggerResponse",
    "AlertLevel",
    "AlertCategory",
    "AlertReason",
    "SuggestedAction",
    "RuleVersion",
)
MatchType = Literal["exact", "non_empty"]


class AlertConfigError(ValueError):
    """La configuración de alertas es inválida."""


@dataclass(frozen=True)
class AlertRule:
    rule_code: str
    question_code: str
    match_type: MatchType
    trigger_response: str | None
    alert_level: str
    alert_category: str
    alert_reason: str
    suggested_action: str
    rule_version: str


@dataclass(frozen=True)
class AlertConfig:
    version: str
    levels: tuple[str, ...]
    contact_request_category: str
    rules: tuple[AlertRule, ...]


@dataclass(frozen=True)
class TriggeredAlert:
    rule_code: str
    question_code: str
    trigger_response: str
    alert_level: str
    alert_category: str
    alert_reason: str
    suggested_action: str
    rule_version: str


def load_alert_config(config_dir: Path) -> AlertConfig:
    """Carga la versión activa de reglas y valida sus referencias."""
    try:
        parameters = yaml.safe_load(
            (config_dir / "parameters.yaml").read_text(encoding="utf-8")
        )
        version = str(parameters["active_alert_rules_version"])
        levels = tuple(str(level) for level in parameters["alert_levels"])
        contact_category = str(parameters["contact_request_category"])
    except (KeyError, TypeError, OSError, yaml.YAMLError) as error:
        raise AlertConfigError("parameters.yaml no cumple el contrato.") from error
    if not levels or len(levels) != len(set(levels)):
        raise AlertConfigError("parameters.yaml contiene niveles inválidos.")

    questionnaire = load_questionnaire(config_dir / "questionnaire.csv")
    question_codes = {
        question.question_code
        for question in questionnaire
        if question.question_code is not None
    }

    try:
        with (config_dir / "alert_rules.csv").open(
            encoding="utf-8-sig", newline=""
        ) as stream:
            reader = csv.DictReader(stream)
            if tuple(reader.fieldnames or ()) != ALERT_COLUMNS:
                raise AlertConfigError(
                    "Los encabezados de alert_rules.csv no cumplen el contrato."
                )
            rows = list(reader)
    except OSError as error:
        raise AlertConfigError("No fue posible leer alert_rules.csv.") from error

    rules: list[AlertRule] = []
    seen_codes: set[str] = set()
    seen_triggers: set[tuple[str, str | None]] = set()
    for row_number, row in enumerate(rows, start=2):
        if row["RuleVersion"].strip() != version:
            continue
        match_type = row["MatchType"].strip()
        trigger = normalize_text(row["TriggerResponse"]) or None
        rule = AlertRule(
            rule_code=row["RuleCode"].strip(),
            question_code=row["QuestionCode"].strip(),
            match_type=match_type,  # type: ignore[arg-type]
            trigger_response=trigger,
            alert_level=row["AlertLevel"].strip(),
            alert_category=row["AlertCategory"].strip(),
            alert_reason=row["AlertReason"].strip(),
            suggested_action=row["SuggestedAction"].strip(),
            rule_version=version,
        )
        trigger_key = (
            rule.question_code,
            trigger.casefold() if trigger is not None else None,
        )
        if (
            not rule.rule_code
            or rule.rule_code in seen_codes
            or rule.question_code not in question_codes
            or match_type not in ("exact", "non_empty")
            or (match_type == "exact") != (trigger is not None)
            or rule.alert_level not in levels
            or not rule.alert_category
            or not rule.alert_reason
            or not rule.suggested_action
            or trigger_key in seen_triggers
        ):
            raise AlertConfigError(f"Fila inválida en alert_rules.csv:{row_number}.")
        seen_codes.add(rule.rule_code)
        seen_triggers.add(trigger_key)
        rules.append(rule)
    if not rules:
        raise AlertConfigError("alert_rules.csv no contiene la versión activa.")

    return AlertConfig(
        version=version,
        levels=levels,
        contact_request_category=contact_category,
        rules=tuple(rules),
    )


def evaluate_alerts(
    responses: Mapping[str, str], config: AlertConfig
) -> tuple[TriggeredAlert, ...]:
    """Cada regla coincidente produce una alerta; nunca se infieren respuestas."""
    alerts = []
    for rule in config.rules:
        response = normalize_text(responses.get(rule.question_code) or "")
        if rule.match_type == "non_empty":
            matched = bool(response)
        else:
            matched = (
                rule.trigger_response is not None
                and response.casefold() == rule.trigger_response.casefold()
            )
        if matched:
            alerts.append(
                TriggeredAlert(
                    rule_code=rule.rule_code,
                    question_code=rule.question_code,
                    # El texto abierto no se copia a la alerta; sólo su presencia.
                    trigger_response=(
                        response if rule.match_type == "exact" else "(texto abierto)"
                    ),
                    alert_level=rule.alert_level,
                    alert_category=rule.alert_category,
                    alert_reason=rule.alert_reason,
                    suggested_action=rule.suggested_action,
                    rule_version=rule.rule_version,
                )
            )
    return tuple(alerts)
