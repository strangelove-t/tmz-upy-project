"""Contrato y carga estricta del diccionario del cuestionario."""

import csv
from dataclasses import dataclass
from pathlib import Path
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, ValidationError, model_validator

from tamizaje.normalization import normalize_text

CATALOG_COLUMNS = (
    "QuestionCode",
    "FormsNumber",
    "QuestionText",
    "QuestionType",
    "Required",
    "IsSensitive",
    "QuestionnaireVersion",
    "MappingStatus",
)
ALIAS_COLUMNS = (
    "AliasText",
    "QuestionCode",
    "SourceQuestionnaireVersion",
    "CanonicalQuestionnaireVersion",
    "Reason",
)

QuestionType = Literal[
    "administrative",
    "integer",
    "likert_frequency",
    "likert_agreement",
    "single_choice",
    "ordinal_choice",
    "multiple_choice",
    "open_text",
]
MappingStatus = Literal["pending_review", "verified_text", "approved"]


class QuestionnaireCatalogError(ValueError):
    """Error seguro de estructura o consistencia del catálogo."""


class QuestionDefinition(BaseModel):
    model_config = ConfigDict(frozen=True, str_strip_whitespace=True)

    question_code: str | None = None
    forms_number: int | None = Field(default=None, ge=1)
    question_text: str = Field(min_length=1)
    question_type: QuestionType | None = None
    required: bool | None = None
    is_sensitive: bool | None = None
    questionnaire_version: str = Field(min_length=1)
    mapping_status: MappingStatus

    @model_validator(mode="after")
    def require_approved_mapping(self) -> "QuestionDefinition":
        missing_forms_number = (
            self.forms_number is None and self.question_type != "administrative"
        )
        if self.mapping_status == "approved" and (
            not self.question_code
            or missing_forms_number
            or self.question_type is None
            or self.required is None
            or self.is_sensitive is None
        ):
            raise ValueError("Una pregunta aprobada requiere un mapeo completo.")
        if self.mapping_status == "verified_text" and (
            not self.question_code or self.forms_number is None
        ):
            raise ValueError(
                "Una pregunta con texto verificado requiere código y número."
            )
        return self


class QuestionAlias(BaseModel):
    model_config = ConfigDict(frozen=True, str_strip_whitespace=True)

    alias_text: str = Field(min_length=1)
    question_code: str = Field(min_length=1)
    source_questionnaire_version: str = Field(min_length=1)
    canonical_questionnaire_version: str = Field(min_length=1)
    reason: str = Field(min_length=1)


@dataclass(frozen=True)
class HeaderAssignment:
    column_index: int
    question_code: str


@dataclass(frozen=True)
class HeaderMappingResult:
    assignments: tuple[HeaderAssignment, ...] = ()
    verified_indices: tuple[int, ...] = ()
    pending_indices: tuple[int, ...] = ()
    unknown_indices: tuple[int, ...] = ()
    ambiguous_indices: tuple[int, ...] = ()
    missing_required_codes: tuple[str, ...] = ()

    @property
    def approved_count(self) -> int:
        return len(self.assignments)

    @property
    def verified_count(self) -> int:
        return len(self.verified_indices)

    @property
    def is_valid(self) -> bool:
        return not (
            self.verified_indices
            or self.pending_indices
            or self.unknown_indices
            or self.ambiguous_indices
            or self.missing_required_codes
        )


def compare_headers(
    headers: tuple[str, ...],
    questionnaire: tuple[QuestionDefinition, ...],
    pending_headers: tuple[str, ...] = (),
    aliases: tuple[QuestionAlias, ...] = (),
) -> HeaderMappingResult:
    by_text: dict[str, list[QuestionDefinition]] = {}
    for question in questionnaire:
        by_text.setdefault(normalize_text(question.question_text), []).append(question)
    mapped_by_code = {
        question.question_code: question
        for question in questionnaire
        if question.mapping_status in {"approved", "verified_text"}
        and question.question_code is not None
    }
    aliases_by_text: dict[str, list[QuestionAlias]] = {}
    for alias in aliases:
        aliases_by_text.setdefault(normalize_text(alias.alias_text), []).append(alias)

    assignments: list[HeaderAssignment] = []
    verified_indices: list[int] = []
    pending_indices: list[int] = []
    unknown_indices: list[int] = []
    ambiguous_indices: list[int] = []
    normalized_pending = {normalize_text(header) for header in pending_headers}

    for column_index, header in enumerate(headers, start=1):
        matches = by_text.get(normalize_text(header), [])
        approved = [item for item in matches if item.mapping_status == "approved"]
        verified = [
            item for item in matches if item.mapping_status == "verified_text"
        ]
        alias_matches = aliases_by_text.get(normalize_text(header), [])
        if len(approved) > 1:
            ambiguous_indices.append(column_index)
        elif len(approved) == 1:
            question_code = approved[0].question_code
            if question_code is None:
                ambiguous_indices.append(column_index)
            else:
                assignments.append(HeaderAssignment(column_index, question_code))
        elif len(alias_matches) > 1:
            ambiguous_indices.append(column_index)
        elif len(alias_matches) == 1:
            question_code = alias_matches[0].question_code
            target = mapped_by_code.get(question_code)
            if target is None:
                ambiguous_indices.append(column_index)
            elif target.mapping_status == "verified_text":
                verified_indices.append(column_index)
            else:
                assignments.append(HeaderAssignment(column_index, question_code))
        elif len(verified) > 1:
            ambiguous_indices.append(column_index)
        elif len(verified) == 1:
            verified_indices.append(column_index)
        elif matches or normalize_text(header) in normalized_pending:
            pending_indices.append(column_index)
        else:
            unknown_indices.append(column_index)

    assigned_codes = {assignment.question_code for assignment in assignments}
    missing_required_codes = tuple(
        question.question_code
        for question in questionnaire
        if question.mapping_status == "approved"
        and question.required
        and question.question_code not in assigned_codes
        and question.question_code is not None
    )

    return HeaderMappingResult(
        assignments=tuple(assignments),
        verified_indices=tuple(verified_indices),
        pending_indices=tuple(pending_indices),
        unknown_indices=tuple(unknown_indices),
        ambiguous_indices=tuple(ambiguous_indices),
        missing_required_codes=missing_required_codes,
    )


def _optional_bool(value: str) -> bool | None:
    normalized = value.strip().lower()
    if not normalized:
        return None
    if normalized == "true":
        return True
    if normalized == "false":
        return False
    raise ValueError("El valor booleano no es válido.")


def load_questionnaire(path: Path) -> tuple[QuestionDefinition, ...]:
    questions: list[QuestionDefinition] = []
    seen_codes: set[str] = set()
    seen_numbers: set[int] = set()
    seen_texts: set[str] = set()

    with path.open(encoding="utf-8-sig", newline="") as stream:
        reader = csv.DictReader(stream)
        if tuple(reader.fieldnames or ()) != CATALOG_COLUMNS:
            raise QuestionnaireCatalogError(
                "Los encabezados del catálogo no cumplen el contrato requerido."
            )

        for row_number, row in enumerate(reader, start=2):
            try:
                question = QuestionDefinition(
                    question_code=row["QuestionCode"] or None,
                    forms_number=(
                        int(row["FormsNumber"]) if row["FormsNumber"] else None
                    ),
                    question_text=row["QuestionText"],
                    question_type=row["QuestionType"] or None,
                    required=_optional_bool(row["Required"]),
                    is_sensitive=_optional_bool(row["IsSensitive"]),
                    questionnaire_version=row["QuestionnaireVersion"],
                    mapping_status=row["MappingStatus"],
                )
            except (KeyError, TypeError, ValueError, ValidationError) as error:
                raise QuestionnaireCatalogError(
                    f"El catálogo contiene una fila inválida en la fila {row_number}."
                ) from error

            normalized_text = normalize_text(question.question_text)
            duplicate = (
                question.question_code in seen_codes
                if question.question_code is not None
                else False
            )
            duplicate = duplicate or (
                question.forms_number in seen_numbers
                if question.forms_number is not None
                else False
            )
            duplicate = duplicate or normalized_text in seen_texts
            if duplicate:
                raise QuestionnaireCatalogError(
                    "El catálogo contiene una asignación duplicada "
                    f"en la fila {row_number}."
                )

            if question.question_code is not None:
                seen_codes.add(question.question_code)
            if question.forms_number is not None:
                seen_numbers.add(question.forms_number)
            seen_texts.add(normalized_text)
            questions.append(question)

    return tuple(questions)


def load_questionnaire_aliases(
    path: Path, questionnaire: tuple[QuestionDefinition, ...]
) -> tuple[QuestionAlias, ...]:
    mapped_codes = {
        question.question_code
        for question in questionnaire
        if question.mapping_status in {"approved", "verified_text"}
        and question.question_code is not None
    }
    aliases: list[QuestionAlias] = []
    seen_texts: set[str] = set()

    with path.open(encoding="utf-8-sig", newline="") as stream:
        reader = csv.DictReader(stream)
        if tuple(reader.fieldnames or ()) != ALIAS_COLUMNS:
            raise QuestionnaireCatalogError(
                "Los encabezados del catálogo de alias no cumplen el contrato."
            )

        for row_number, row in enumerate(reader, start=2):
            try:
                alias = QuestionAlias(
                    alias_text=row["AliasText"],
                    question_code=row["QuestionCode"],
                    source_questionnaire_version=row[
                        "SourceQuestionnaireVersion"
                    ],
                    canonical_questionnaire_version=row[
                        "CanonicalQuestionnaireVersion"
                    ],
                    reason=row["Reason"],
                )
            except (KeyError, TypeError, ValueError, ValidationError) as error:
                raise QuestionnaireCatalogError(
                    "El catálogo de alias contiene una fila inválida "
                    f"en la fila {row_number}."
                ) from error

            normalized_alias = normalize_text(alias.alias_text)
            if (
                alias.question_code not in mapped_codes
                or normalized_alias in seen_texts
            ):
                raise QuestionnaireCatalogError(
                    "El catálogo de alias contiene una referencia inválida "
                    f"en la fila {row_number}."
                )
            aliases.append(alias)
            seen_texts.add(normalized_alias)

    return tuple(aliases)
