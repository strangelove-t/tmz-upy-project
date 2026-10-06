"""Carga y validación estricta de reglas de scoring versionadas."""

import csv
from dataclasses import dataclass
from decimal import Decimal, InvalidOperation
from pathlib import Path

import yaml

from tamizaje.normalization import normalize_text
from tamizaje.questionnaire import load_questionnaire

AREA_COLUMNS = (
    "AreaCode",
    "AreaName",
    "ExpectedItemCount",
    "MinimumValidItemCount",
    "GreenMin",
    "YellowMin",
    "Version",
)
ITEM_COLUMNS = ("AreaCode", "QuestionCode", "Weight", "Version")
OPTION_COLUMNS = (
    "QuestionCode",
    "Response",
    "ResponseAlias",
    "CorrectedValue",
    "IncludeInAverage",
    "Version",
)


class ScoringConfigError(ValueError):
    """La configuración de scoring es inválida."""


@dataclass(frozen=True)
class AreaDefinition:
    area_code: str
    area_name: str
    expected_item_count: int
    minimum_valid_item_count: int
    green_min: Decimal
    yellow_min: Decimal


@dataclass(frozen=True)
class AreaItem:
    area_code: str
    question_code: str
    weight: Decimal


@dataclass(frozen=True)
class ScoringOption:
    question_code: str
    response: str
    response_alias: str | None
    corrected_value: Decimal | None
    include_in_average: bool


@dataclass(frozen=True)
class ScoringConfig:
    version: str
    scale_min: Decimal
    scale_max: Decimal
    incomplete_area_policy: str
    areas: tuple[AreaDefinition, ...]
    items: tuple[AreaItem, ...]
    options: tuple[ScoringOption, ...]


def _decimal(value: object, source: str) -> Decimal:
    try:
        return Decimal(str(value))
    except (InvalidOperation, ValueError) as error:
        raise ScoringConfigError(f"Valor numérico inválido en {source}.") from error


def _read_rows(path: Path, columns: tuple[str, ...]) -> list[dict[str, str]]:
    try:
        with path.open(encoding="utf-8-sig", newline="") as stream:
            reader = csv.DictReader(stream)
            if tuple(reader.fieldnames or ()) != columns:
                raise ScoringConfigError(
                    f"Los encabezados de {path.name} no cumplen el contrato."
                )
            return list(reader)
    except OSError as error:
        raise ScoringConfigError(f"No fue posible leer {path.name}.") from error


def _parse_bool(value: str, source: str) -> bool:
    normalized = value.strip().lower()
    if normalized == "true":
        return True
    if normalized == "false":
        return False
    raise ScoringConfigError(f"Valor booleano inválido en {source}.")


def load_scoring_config(config_dir: Path) -> ScoringConfig:
    """Carga la versión activa y valida todas sus referencias y límites."""
    parameters_path = config_dir / "parameters.yaml"
    try:
        parameters = yaml.safe_load(parameters_path.read_text(encoding="utf-8"))
        version = str(parameters["active_scoring_version"])
        version_parameters = parameters["scoring_versions"][version]
        scale_min = _decimal(version_parameters["scale_min"], "parameters.yaml")
        scale_max = _decimal(version_parameters["scale_max"], "parameters.yaml")
        policy = str(version_parameters["incomplete_area_policy"])
    except (KeyError, TypeError, OSError, yaml.YAMLError) as error:
        raise ScoringConfigError("parameters.yaml no cumple el contrato.") from error
    if scale_min >= scale_max or policy != "no_score":
        raise ScoringConfigError("parameters.yaml contiene una política inválida.")

    questionnaire = load_questionnaire(config_dir / "questionnaire.csv")
    question_codes = {
        question.question_code
        for question in questionnaire
        if question.question_code is not None
    }

    areas: list[AreaDefinition] = []
    for row_number, row in enumerate(
        _read_rows(config_dir / "areas.csv", AREA_COLUMNS), start=2
    ):
        if row["Version"] != version:
            continue
        try:
            area = AreaDefinition(
                area_code=row["AreaCode"].strip(),
                area_name=row["AreaName"].strip(),
                expected_item_count=int(row["ExpectedItemCount"]),
                minimum_valid_item_count=int(row["MinimumValidItemCount"]),
                green_min=_decimal(row["GreenMin"], "areas.csv"),
                yellow_min=_decimal(row["YellowMin"], "areas.csv"),
            )
        except (TypeError, ValueError) as error:
            raise ScoringConfigError(
                f"Fila inválida en areas.csv:{row_number}."
            ) from error
        if (
            not area.area_code
            or not area.area_name
            or area.expected_item_count < 1
            or not 1 <= area.minimum_valid_item_count <= area.expected_item_count
            or not Decimal("0")
            <= area.yellow_min
            < area.green_min
            <= Decimal("100")
        ):
            raise ScoringConfigError(f"Fila inválida en areas.csv:{row_number}.")
        areas.append(area)
    area_codes = [area.area_code for area in areas]
    if not areas or len(area_codes) != len(set(area_codes)):
        raise ScoringConfigError("areas.csv contiene códigos duplicados o vacíos.")

    items: list[AreaItem] = []
    for row_number, row in enumerate(
        _read_rows(config_dir / "area_items.csv", ITEM_COLUMNS), start=2
    ):
        if row["Version"] != version:
            continue
        item = AreaItem(
            area_code=row["AreaCode"].strip(),
            question_code=row["QuestionCode"].strip(),
            weight=_decimal(row["Weight"], "area_items.csv"),
        )
        if (
            item.area_code not in set(area_codes)
            or item.question_code not in question_codes
            or item.weight <= 0
        ):
            raise ScoringConfigError(
                f"Referencia inválida en area_items.csv:{row_number}."
            )
        items.append(item)
    item_keys = [(item.area_code, item.question_code) for item in items]
    assigned_questions = [item.question_code for item in items]
    if len(item_keys) != len(set(item_keys)) or len(assigned_questions) != len(
        set(assigned_questions)
    ):
        raise ScoringConfigError("area_items.csv contiene reactivos duplicados.")
    for area in areas:
        actual_count = sum(item.area_code == area.area_code for item in items)
        if actual_count != area.expected_item_count:
            raise ScoringConfigError(
                f"El conteo de {area.area_code} no coincide en areas.csv."
            )

    options: list[ScoringOption] = []
    seen_option_keys: set[tuple[str, str]] = set()
    scored_questions = set(assigned_questions)
    for row_number, row in enumerate(
        _read_rows(config_dir / "scoring_options.csv", OPTION_COLUMNS), start=2
    ):
        if row["Version"] != version:
            continue
        include = _parse_bool(row["IncludeInAverage"], "scoring_options.csv")
        corrected = (
            _decimal(row["CorrectedValue"], "scoring_options.csv")
            if row["CorrectedValue"].strip()
            else None
        )
        option = ScoringOption(
            question_code=row["QuestionCode"].strip(),
            response=row["Response"].strip(),
            response_alias=row["ResponseAlias"].strip() or None,
            corrected_value=corrected,
            include_in_average=include,
        )
        if (
            option.question_code not in scored_questions
            or not option.response
            or (include and corrected is None)
            or (
                corrected is not None
                and not scale_min <= corrected <= scale_max
            )
        ):
            raise ScoringConfigError(
                f"Fila inválida en scoring_options.csv:{row_number}."
            )
        labels = (option.response, option.response_alias)
        for label in labels:
            if label is None:
                continue
            key = (option.question_code, normalize_text(label).casefold())
            if key in seen_option_keys:
                raise ScoringConfigError(
                    f"Opción duplicada en scoring_options.csv:{row_number}."
                )
            seen_option_keys.add(key)
        options.append(option)
    questions_with_options = {option.question_code for option in options}
    if questions_with_options != scored_questions:
        raise ScoringConfigError(
            "scoring_options.csv no cubre todos los reactivos configurados."
        )

    return ScoringConfig(
        version=version,
        scale_min=scale_min,
        scale_max=scale_max,
        incomplete_area_policy=policy,
        areas=tuple(areas),
        items=tuple(items),
        options=tuple(options),
    )
