"""Síntesis configurable de condiciones y apoyos declarados."""

import sqlite3
from dataclasses import dataclass
from pathlib import Path
from typing import Literal

import yaml
from pydantic import BaseModel, ConfigDict, Field, ValidationError

from tamizaje.normalization import normalize_text
from tamizaje.questionnaire import QuestionDefinition


class SensitiveConfigError(ValueError):
    """La configuración sensible no cumple el contrato seguro."""


SensitiveRole = Literal[
    "diagnosis",
    "professional",
    "impact",
    "treatment",
    "prior_support",
    "requested_support",
    "recommendation",
]


class SensitiveField(BaseModel):
    model_config = ConfigDict(frozen=True, str_strip_whitespace=True)
    question_code: str = Field(min_length=1)
    label: str = Field(min_length=1)
    role: SensitiveRole


class SensitiveCategory(BaseModel):
    model_config = ConfigDict(frozen=True, str_strip_whitespace=True)
    code: str = Field(min_length=1)
    label: str = Field(min_length=1)
    trigger_question: str = Field(min_length=1)
    affirmative_values: tuple[str, ...] = Field(min_length=1)
    fields: tuple[SensitiveField, ...] = Field(min_length=1)


class SensitiveConfig(BaseModel):
    model_config = ConfigDict(frozen=True, str_strip_whitespace=True)
    version: str = Field(min_length=1)
    categories: tuple[SensitiveCategory, ...] = Field(min_length=1)


@dataclass(frozen=True)
class SensitiveCategorySummary:
    code: str
    label: str
    fields: tuple[tuple[str, str], ...]
    requires_review: bool = False


@dataclass(frozen=True)
class SensitiveSummary:
    categories: tuple[SensitiveCategorySummary, ...]
    requested_support: bool
    current_impact: bool
    config_version: str

    @property
    def has_sensitive_declaration(self) -> bool:
        return bool(self.categories)

    @property
    def requires_review(self) -> bool:
        return any(item.requires_review for item in self.categories)


def load_sensitive_config(
    config_dir: Path, questionnaire: tuple[QuestionDefinition, ...]
) -> SensitiveConfig:
    try:
        raw = yaml.safe_load(
            (config_dir / "sensitive_summary.yaml").read_text(encoding="utf-8")
        )
        config = SensitiveConfig.model_validate(raw)
    except (OSError, yaml.YAMLError, ValidationError, TypeError) as error:
        raise SensitiveConfigError(
            "sensitive_summary.yaml no cumple el contrato."
        ) from error

    by_code = {item.question_code: item for item in questionnaire}
    category_codes = [category.code for category in config.categories]
    if len(category_codes) != len(set(category_codes)):
        raise SensitiveConfigError("Las categorías sensibles están duplicadas.")
    for category in config.categories:
        codes = [
            category.trigger_question,
            *(field.question_code for field in category.fields),
        ]
        if len(codes) != len(set(codes)):
            raise SensitiveConfigError("Una categoría repite preguntas sensibles.")
        for code in codes:
            question = by_code.get(code)
            if question is None or question.is_sensitive is not True:
                raise SensitiveConfigError(
                    f"{code} debe corresponder a una pregunta sensible aprobada."
                )
    return config


_NEGATIVE = {"", "no", "nunca", "ninguna", "ninguno", "no aplica"}


def _positive(value: str) -> bool:
    return normalize_text(value).casefold() not in _NEGATIVE


def build_sensitive_summary(
    connection: sqlite3.Connection,
    submission_id: int,
    config: SensitiveConfig,
) -> SensitiveSummary:
    responses = dict(
        connection.execute(
            "SELECT question_code, response_raw FROM responses "
            "WHERE submission_id = ? AND is_sensitive = 1",
            (submission_id,),
        ).fetchall()
    )
    summaries: list[SensitiveCategorySummary] = []
    requested_support = False
    current_impact = False
    for category in config.categories:
        trigger = normalize_text(responses.get(category.trigger_question, ""))
        affirmative = {
            normalize_text(value).casefold() for value in category.affirmative_values
        }
        trigger_active = trigger.casefold() in affirmative
        diagnosis_present = any(
            field.role == "diagnosis"
            and _positive(responses.get(field.question_code, ""))
            for field in category.fields
        )
        if not trigger_active and not diagnosis_present:
            continue
        fields = tuple(
            (field.label, normalize_text(responses.get(field.question_code, "")))
            for field in category.fields
            if _positive(responses.get(field.question_code, ""))
        )
        if trigger_active and not fields:
            fields = (("Condición", "Declarada; detalle no especificado"),)
        requested_support = requested_support or any(
            field.role == "requested_support"
            and _positive(responses.get(field.question_code, ""))
            for field in category.fields
        )
        current_impact = current_impact or any(
            field.role == "impact" and _positive(responses.get(field.question_code, ""))
            for field in category.fields
        )
        summaries.append(
            SensitiveCategorySummary(
                code=category.code,
                label=category.label,
                fields=fields,
                requires_review=diagnosis_present and not trigger_active,
            )
        )
    return SensitiveSummary(
        categories=tuple(summaries),
        requested_support=requested_support,
        current_impact=current_impact,
        config_version=config.version,
    )
